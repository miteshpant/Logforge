"""
Bounded ingest worker pool (ENH-009).

Replaces the previous thread-per-batch model in
`dependencies.py::process_logs_and_tracking_background()`, which spawned a
daemon thread for every ingested batch, each building its own event loop and its
own ClickHouse client (which it then never used -- the downstream coroutine only
publishes a Kafka event).

That model had no upper bound: at even modest request rates it exhausted thread
stacks and file descriptors, and connection setup dominated latency. It capped
ingest throughput far below the hardware, which is the single biggest scale
limiter for an observability product.

Design
------
* A fixed number of asyncio worker tasks drain a **bounded** queue.
* When the queue is full, submission fails fast and is counted, rather than
  silently growing memory. That is the honest behaviour: the platform cannot
  keep accepting data it has no capacity to process (see ENH-029 for turning
  this into a 429 at the edge).
* Runs on the main event loop, so no per-batch loop creation and no thread
  churn.
* Queue depth and drop counts are exported so saturation is visible (ENH-019).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_WORKERS = 8
DEFAULT_QUEUE_SIZE = 10_000


@dataclass
class PipelineStats:
    submitted: int = 0
    processed: int = 0
    failed: int = 0
    dropped_queue_full: int = 0
    dropped_not_running: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "submitted": self.submitted,
            "processed": self.processed,
            "failed": self.failed,
            "dropped_queue_full": self.dropped_queue_full,
            "dropped_not_running": self.dropped_not_running,
        }


@dataclass
class _Batch:
    logs: List[Any]
    customer_id: str
    endpoint: str
    format_type: str
    log_count: int
    bytes_processed: int
    processing_time_ms: int


class IngestPipeline:
    """A bounded pool of workers processing ingest batches."""

    def __init__(
        self,
        workers: Optional[int] = None,
        queue_size: Optional[int] = None,
    ):
        self.worker_count = workers or int(
            os.getenv("INGEST_PIPELINE_WORKERS", DEFAULT_WORKERS)
        )
        self.queue_size = queue_size or int(
            os.getenv("INGEST_PIPELINE_QUEUE_SIZE", DEFAULT_QUEUE_SIZE)
        )
        self._queue: Optional[asyncio.Queue] = None
        self._workers: List[asyncio.Task] = []
        self._running = False
        self.stats = PipelineStats()

    # -- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return

        self._queue = asyncio.Queue(maxsize=self.queue_size)
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.worker_count)
        ]
        logger.info(
            "Ingest pipeline started",
            workers=self.worker_count,
            queue_size=self.queue_size,
        )

    async def stop(self, drain_timeout: float = 10.0) -> None:
        """Stop accepting work, drain what is queued, then cancel workers."""
        if not self._running:
            return

        self._running = False

        if self._queue is not None:
            try:
                # Give in-flight work a bounded chance to complete rather than
                # discarding logs that were already accepted from a customer.
                await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Ingest pipeline drain timed out; remaining work discarded",
                    remaining=self._queue.qsize(),
                )

        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        logger.info("Ingest pipeline stopped", stats=self.stats.as_dict())

    # -- submission ------------------------------------------------------

    def submit(
        self,
        logs: List[Any],
        customer_id: str,
        endpoint: str,
        format_type: str,
        log_count: int,
        bytes_processed: int,
        processing_time_ms: int,
    ) -> bool:
        """
        Queue a batch for processing.

        Returns False if the batch could not be accepted. Non-blocking by
        design: the caller is a request handler and must not wait on the
        pipeline.
        """
        if not self._running or self._queue is None:
            self.stats.dropped_not_running += 1
            logger.error(
                "Ingest pipeline is not running; batch dropped",
                customer_id=customer_id,
                log_count=log_count,
            )
            return False

        batch = _Batch(
            logs=logs,
            customer_id=customer_id,
            endpoint=endpoint,
            format_type=format_type,
            log_count=log_count,
            bytes_processed=bytes_processed,
            processing_time_ms=processing_time_ms,
        )

        try:
            self._queue.put_nowait(batch)
        except asyncio.QueueFull:
            # Fail fast and loudly. Growing an unbounded queue would trade a
            # visible drop for an invisible OOM later.
            self.stats.dropped_queue_full += 1
            logger.error(
                "Ingest queue full; batch dropped -- pipeline is saturated",
                customer_id=customer_id,
                log_count=log_count,
                queue_size=self.queue_size,
            )
            return False

        self.stats.submitted += 1
        return True

    # -- workers ---------------------------------------------------------

    async def _worker(self, index: int) -> None:
        assert self._queue is not None
        while True:
            batch = await self._queue.get()
            try:
                await self._process(batch)
                self.stats.processed += 1
            except asyncio.CancelledError:
                self._queue.task_done()
                raise
            except Exception as exc:
                self.stats.failed += 1
                logger.error(
                    "Ingest batch processing failed",
                    worker=index,
                    customer_id=batch.customer_id,
                    log_count=batch.log_count,
                    error=str(exc),
                )
            else:
                pass
            finally:
                self._queue.task_done()

    async def _process(self, batch: _Batch) -> None:
        """Run the existing event-publishing path for one batch."""
        import dependencies

        await dependencies.process_logs_and_tracking_async(
            batch.logs,
            batch.customer_id,
            batch.endpoint,
            batch.format_type,
            batch.log_count,
            batch.bytes_processed,
            batch.processing_time_ms,
            # The downstream coroutine does not use a ClickHouse client -- it
            # only publishes an event. The parameter is retained for signature
            # compatibility and is explicitly None rather than a wasted
            # connection per batch.
            None,
        )

    # -- back-pressure ---------------------------------------------------

    def is_saturated(self) -> bool:
        """
        Whether the pipeline is too full to accept more work (ENH-029).

        Checked by ingest endpoints BEFORE they return 202. Without this the API
        keeps answering "accepted" for data it has no capacity to persist,
        turning overload into silent loss instead of an honest rejection --
        and the customer only discovers it when they need the logs.

        The threshold is below 100% on purpose: batches are queued from a
        request handler after the check, so leaving headroom avoids accepting a
        request and then dropping it moments later.
        """
        if not self._running or self._queue is None:
            return True

        threshold = float(os.getenv("INGEST_SATURATION_THRESHOLD", "0.9"))
        return self._queue.qsize() >= self.queue_size * threshold

    def retry_after_seconds(self) -> int:
        """A conservative hint for how long a client should wait."""
        return int(os.getenv("INGEST_RETRY_AFTER_SECONDS", "5"))

    # -- introspection ---------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "workers": self.worker_count,
            "queue_size": self.queue_size,
            "queue_depth": self._queue.qsize() if self._queue else 0,
            "stats": self.stats.as_dict(),
        }


_pipeline: Optional[IngestPipeline] = None


def get_ingest_pipeline() -> IngestPipeline:
    """Get the shared ingest pipeline, constructing it on first use."""
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestPipeline()
    return _pipeline


async def start_ingest_pipeline() -> IngestPipeline:
    pipeline = get_ingest_pipeline()
    await pipeline.start()
    return pipeline


async def stop_ingest_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        await _pipeline.stop()


def reset_ingest_pipeline() -> None:
    """Reset the singleton (tests only)."""
    global _pipeline
    _pipeline = None
