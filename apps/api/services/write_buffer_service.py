"""
High-Performance Write Buffer Service

Batches log writes to ClickHouse to amortize network overhead.
Instead of 40ms per log, batching 100 logs takes ~50ms total.

Performance characteristics:
- Single log: 40ms (flushes on timeout)
- 100 logs: ~50ms (batched insert)
- 1000 logs: ~100ms (batched insert)

Buffer Strategy:
- Flush when buffer reaches size threshold (default: 100 logs)
- Flush on time interval (default: 100ms) to prevent stale data
- Separate buffers per customer for tenant isolation
- Separate buffers for raw vs normalized tables
"""

import asyncio
import json
import os
import re
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BufferConfig:
    """Configuration for write buffer behavior"""
    max_buffer_size: int = 100  # Flush when buffer reaches this size
    flush_interval_ms: int = 100  # Flush at least this often (milliseconds)
    max_retry_attempts: int = 3  # Retry failed flushes
    retry_delay_ms: int = 50  # Delay between retries

    # ENH-007: hard ceilings. Without these a sustained ClickHouse outage grows
    # the in-memory buffer until the process is OOM-killed, losing every
    # buffered log. Overflow is routed to a dead-letter sink instead, so the
    # loss is bounded, durable, and replayable.
    max_buffered_logs_per_customer: int = 50_000
    max_buffered_logs_total: int = 500_000
    dead_letter_dir: Optional[str] = None  # defaults to LOGFORGE_DLQ_DIR or ./dlq


@dataclass
class BufferStats:
    """Statistics for monitoring buffer performance"""
    total_logs_buffered: int = 0
    total_logs_flushed: int = 0
    total_flushes: int = 0
    total_flush_time_ms: float = 0.0
    flush_by_size: int = 0  # Flushes triggered by size threshold
    flush_by_time: int = 0  # Flushes triggered by time interval
    flush_errors: int = 0
    avg_batch_size: float = 0.0
    avg_flush_time_ms: float = 0.0

    # ENH-007: overflow accounting. `logs_dead_lettered` is the number of logs
    # written to the DLQ because the buffer was full; it is the key signal that
    # the pipeline is shedding data and must be alerted on.
    logs_dead_lettered: int = 0
    dead_letter_failures: int = 0
    retry_attempts: int = 0

    def update_averages(self):
        if self.total_flushes > 0:
            self.avg_batch_size = self.total_logs_flushed / self.total_flushes
            self.avg_flush_time_ms = self.total_flush_time_ms / self.total_flushes


class DeadLetterSink:
    """
    Durable overflow sink for logs that cannot be written to ClickHouse
    (ENH-007).

    Newline-delimited JSON on local disk, one file per customer per process.
    Deliberately simple: the point is that overflow leaves the process's heap
    and survives a crash, so an outage costs bounded memory and nothing is
    dropped without a durable record. A Kafka-backed DLQ with automated replay
    is the longer-term goal.
    """

    def __init__(self, directory: Optional[str] = None):
        self.directory = Path(
            directory
            or os.getenv("LOGFORGE_DLQ_DIR")
            or Path.cwd() / "dlq"
        )
        self._lock = threading.Lock()

    def write(self, customer_id: str, logs: List[Dict[str, Any]], reason: str) -> int:
        """
        Persist logs to the dead-letter sink.

        Returns the number of records written. Raises on I/O failure -- the
        caller must know when overflow could not be persisted, because that is
        the point at which data is genuinely lost.
        """
        if not logs:
            return 0

        # Keep the filename filesystem-safe without collapsing distinct tenants.
        # The customer id is caller-influenced, so path separators AND parent
        # references are both neutralised -- otherwise a tenant id such as
        # "../../etc/passwd" would escape the DLQ directory.
        # Collapse parent references first, then map any remaining unsafe
        # character to '_'. A value that reduces to nothing meaningful (e.g.
        # "..." or "///") becomes "unknown" rather than an empty filename.
        safe_customer = customer_id.replace("..", "_")
        safe_customer = re.sub(r"[^A-Za-z0-9_.-]", "_", safe_customer)
        if not safe_customer.strip("._-"):
            safe_customer = "unknown"
        path = self.directory / f"{safe_customer}.dlq.jsonl"

        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                for record in logs:
                    handle.write(
                        json.dumps(
                            {
                                "customer_id": customer_id,
                                "reason": reason,
                                "dead_lettered_at": datetime.now(timezone.utc).isoformat(),
                                "record": record,
                            },
                            default=str,
                        )
                        + "\n"
                    )
        return len(logs)


@dataclass
class CustomerBuffer:
    """Buffer for a single customer's logs"""
    customer_id: str
    raw_logs: List[Dict[str, Any]] = field(default_factory=list)
    normalized_logs: List[Dict[str, Any]] = field(default_factory=list)
    last_flush_time: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


class WriteBufferService:
    """
    High-performance write buffer for ClickHouse inserts.

    Batches logs per customer and flushes based on size or time thresholds.
    Thread-safe for concurrent writes from multiple event handlers.
    """

    def __init__(
        self,
        config: Optional[BufferConfig] = None,
        dead_letter_sink: Optional[DeadLetterSink] = None,
    ):
        self.config = config or BufferConfig()
        self.buffers: Dict[str, CustomerBuffer] = {}
        self.stats = BufferStats()
        self._global_lock = threading.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._flush_callback: Optional[Callable] = None
        # ENH-007: durable overflow path so a downstream outage costs bounded
        # memory instead of an OOM kill that loses everything buffered.
        self._dead_letter_sink = dead_letter_sink or DeadLetterSink(
            self.config.dead_letter_dir
        )

        logger.info(
            "WriteBufferService initialized",
            max_buffer_size=self.config.max_buffer_size,
            flush_interval_ms=self.config.flush_interval_ms,
            max_buffered_logs_per_customer=self.config.max_buffered_logs_per_customer,
            max_buffered_logs_total=self.config.max_buffered_logs_total,
            dead_letter_dir=str(self._dead_letter_sink.directory)
        )

    def set_flush_callback(self, callback: Callable):
        """
        Set the callback function for flushing logs to ClickHouse.

        The callback should have signature:
            async def flush(customer_id: str, raw_logs: List, normalized_logs: List) -> bool
        """
        self._flush_callback = callback

    def _get_or_create_buffer(self, customer_id: str) -> CustomerBuffer:
        """Get or create a buffer for a customer (thread-safe)"""
        if customer_id not in self.buffers:
            with self._global_lock:
                if customer_id not in self.buffers:
                    self.buffers[customer_id] = CustomerBuffer(customer_id=customer_id)
        return self.buffers[customer_id]

    async def add_logs(
        self,
        customer_id: str,
        raw_logs: Optional[List[Dict[str, Any]]] = None,
        normalized_logs: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Add logs to the buffer for a customer.

        Automatically flushes if buffer size threshold is reached.

        Args:
            customer_id: Customer/tenant ID
            raw_logs: Raw log entries for logs_raw_mt table
            normalized_logs: Normalized log entries for logs_normalized_mt table

        Returns:
            True if logs were added successfully
        """
        buffer = self._get_or_create_buffer(customer_id)
        should_flush = False
        overflow_raw: List[Dict[str, Any]] = []
        overflow_normalized: List[Dict[str, Any]] = []

        with buffer.lock:
            # ENH-007: enforce ceilings BEFORE extending, so the heap can never
            # grow without bound during a downstream outage. Anything that does
            # not fit is dead-lettered rather than dropped or accumulated.
            room = self._remaining_capacity(buffer)

            if raw_logs:
                accepted, overflow_raw = self._split_at_capacity(raw_logs, room)
                buffer.raw_logs.extend(accepted)
                self.stats.total_logs_buffered += len(accepted)
                room -= len(accepted)

            if normalized_logs:
                accepted, overflow_normalized = self._split_at_capacity(
                    normalized_logs, room
                )
                buffer.normalized_logs.extend(accepted)
                # Don't double-count if both raw and normalized provided
                if not raw_logs:
                    self.stats.total_logs_buffered += len(accepted)

            # Check if we need to flush by size
            total_buffered = len(buffer.raw_logs) + len(buffer.normalized_logs)
            if total_buffered >= self.config.max_buffer_size:
                should_flush = True
                self.stats.flush_by_size += 1

        # Dead-letter outside the lock -- disk I/O must not block writers.
        if overflow_raw or overflow_normalized:
            self._dead_letter(
                customer_id,
                overflow_raw + overflow_normalized,
                reason="buffer_capacity_exceeded",
            )

        if should_flush:
            await self._flush_customer_buffer(customer_id)

        # Report whether everything was accepted into the durable path. Callers
        # need to know when the pipeline is shedding, so this is not always True.
        return not (overflow_raw or overflow_normalized)

    def _remaining_capacity(self, buffer: CustomerBuffer) -> int:
        """Free slots for this customer, honouring per-customer and global caps."""
        per_customer_used = len(buffer.raw_logs) + len(buffer.normalized_logs)
        per_customer_room = max(
            0, self.config.max_buffered_logs_per_customer - per_customer_used
        )

        total_used = sum(
            len(b.raw_logs) + len(b.normalized_logs) for b in self.buffers.values()
        )
        global_room = max(0, self.config.max_buffered_logs_total - total_used)

        return min(per_customer_room, global_room)

    @staticmethod
    def _split_at_capacity(
        logs: List[Dict[str, Any]], room: int
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Split into (accepted, overflow) at the available capacity."""
        if room <= 0:
            return [], list(logs)
        if len(logs) <= room:
            return list(logs), []
        return list(logs[:room]), list(logs[room:])

    def _dead_letter(
        self, customer_id: str, logs: List[Dict[str, Any]], reason: str
    ) -> None:
        """
        Persist logs that could not be buffered or flushed.

        A dead-letter write failure is the one case where data is genuinely
        lost, so it is logged at error level with a count and never silently
        ignored.
        """
        if not logs:
            return

        try:
            written = self._dead_letter_sink.write(customer_id, logs, reason)
            self.stats.logs_dead_lettered += written
            logger.error(
                "Logs dead-lettered -- pipeline is shedding data",
                customer_id=customer_id,
                count=written,
                reason=reason,
                dlq_dir=str(self._dead_letter_sink.directory),
            )
        except Exception as exc:
            self.stats.dead_letter_failures += len(logs)
            logger.error(
                "DATA LOSS: dead-letter write failed",
                customer_id=customer_id,
                count=len(logs),
                reason=reason,
                error=str(exc),
            )

    async def add_log(
        self,
        customer_id: str,
        raw_log: Optional[Dict[str, Any]] = None,
        normalized_log: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a single log to the buffer (convenience method).
        """
        raw_logs = [raw_log] if raw_log else None
        normalized_logs = [normalized_log] if normalized_log else None
        return await self.add_logs(customer_id, raw_logs, normalized_logs)

    async def _flush_customer_buffer(self, customer_id: str) -> bool:
        """
        Flush a specific customer's buffer to ClickHouse.

        ENH-007: on failure this used to prepend the rows back into the same
        in-memory buffer with no cap and no retry ceiling, so a sustained
        ClickHouse outage grew the heap until the process was OOM-killed --
        losing every buffered log at once. It now retries a bounded number of
        times (honouring `max_retry_attempts` / `retry_delay_ms`, which were
        previously declared but never used) and dead-letters whatever still
        cannot be written.
        """
        buffer = self.buffers.get(customer_id)
        if not buffer:
            return True

        raw_to_flush = []
        normalized_to_flush = []

        with buffer.lock:
            if not buffer.raw_logs and not buffer.normalized_logs:
                return True  # Nothing to flush

            # Move logs out of buffer
            raw_to_flush = buffer.raw_logs.copy()
            normalized_to_flush = buffer.normalized_logs.copy()
            buffer.raw_logs.clear()
            buffer.normalized_logs.clear()
            buffer.last_flush_time = time.time()

        if not raw_to_flush and not normalized_to_flush:
            return True

        # Perform the flush
        start_time = time.time()
        success = False

        try:
            success = await self._flush_with_retries(
                customer_id, raw_to_flush, normalized_to_flush
            )

            flush_time_ms = (time.time() - start_time) * 1000
            total_flushed = len(raw_to_flush) + len(normalized_to_flush)

            if success:
                self.stats.total_logs_flushed += total_flushed
                self.stats.total_flushes += 1
                self.stats.total_flush_time_ms += flush_time_ms
                self.stats.update_averages()

                logger.info(
                    f"Buffer flush completed",
                    customer_id=customer_id,
                    raw_count=len(raw_to_flush),
                    normalized_count=len(normalized_to_flush),
                    flush_time_ms=f"{flush_time_ms:.2f}",
                    avg_per_log_ms=f"{flush_time_ms/total_flushed:.3f}" if total_flushed > 0 else "N/A"
                )
            else:
                self.stats.flush_errors += 1
                # Retries are exhausted. Dead-letter rather than re-queue: the
                # buffer is shared and unbounded re-queueing is what caused the
                # OOM failure mode this ticket removes.
                self._dead_letter(
                    customer_id,
                    raw_to_flush + normalized_to_flush,
                    reason="flush_failed_after_retries",
                )
                logger.error(
                    "Buffer flush failed after retries; logs dead-lettered",
                    customer_id=customer_id,
                    raw_count=len(raw_to_flush),
                    normalized_count=len(normalized_to_flush),
                )

            return success

        except Exception as e:
            self.stats.flush_errors += 1
            logger.error(f"Buffer flush error for customer {customer_id}: {e}")
            self._dead_letter(
                customer_id,
                raw_to_flush + normalized_to_flush,
                reason=f"flush_exception:{type(e).__name__}",
            )
            return False

    async def _flush_with_retries(
        self,
        customer_id: str,
        raw_logs: List[Dict[str, Any]],
        normalized_logs: List[Dict[str, Any]],
    ) -> bool:
        """
        Attempt the flush up to `max_retry_attempts` times with a delay between
        tries.

        ENH-007: `BufferConfig.max_retry_attempts` and `retry_delay_ms` existed
        but were never referenced -- dead configuration that misled operators
        into thinking retries were happening. They are now honoured.
        """
        attempts = max(1, self.config.max_retry_attempts)
        delay_seconds = self.config.retry_delay_ms / 1000.0

        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self.stats.retry_attempts += 1
                await asyncio.sleep(delay_seconds)

            if self._flush_callback:
                success = await self._flush_callback(
                    customer_id, raw_logs, normalized_logs
                )
            else:
                success = await self._default_flush(
                    customer_id, raw_logs, normalized_logs
                )

            if success:
                if attempt > 1:
                    logger.info(
                        "Buffer flush succeeded on retry",
                        customer_id=customer_id,
                        attempt=attempt,
                    )
                return True

            logger.warning(
                "Buffer flush attempt failed",
                customer_id=customer_id,
                attempt=attempt,
                max_attempts=attempts,
            )

        return False

    async def _default_flush(
        self,
        customer_id: str,
        raw_logs: List[Dict[str, Any]],
        normalized_logs: List[Dict[str, Any]]
    ) -> bool:
        """Default flush implementation using log_processor"""
        try:
            from events.management.processors.log_processor import (
                process_dual_write_optimized,
                process_normalized_write_only,
                process_log_batch_with_client
            )

            if raw_logs and normalized_logs:
                # Dual write - both functions take List[Dict], not LogEntry
                return await process_dual_write_optimized(raw_logs, normalized_logs, customer_id)
            elif normalized_logs:
                # Normalized only
                return await process_normalized_write_only(normalized_logs, customer_id)
            elif raw_logs:
                # Raw only - need to convert to LogEntry for this function
                from models import LogEntry
                log_entries = []
                for log in raw_logs:
                    try:
                        log_entries.append(LogEntry(**log))
                    except Exception as e:
                        logger.warning(f"Failed to create LogEntry: {e}")
                        continue
                if log_entries:
                    return await process_log_batch_with_client(log_entries, customer_id)

            return True

        except Exception as e:
            logger.error(f"Default flush failed: {e}")
            return False

    async def flush_all(self) -> Dict[str, bool]:
        """Flush all customer buffers"""
        results = {}
        customer_ids = list(self.buffers.keys())

        for customer_id in customer_ids:
            results[customer_id] = await self._flush_customer_buffer(customer_id)

        return results

    async def start_periodic_flush(self):
        """Start the background periodic flush task"""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush_loop())
        logger.info("Periodic flush task started")

    async def stop_periodic_flush(self):
        """Stop the background periodic flush task and flush remaining logs"""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush_all()
        logger.info("Periodic flush task stopped, final flush completed")

    async def _periodic_flush_loop(self):
        """Background loop that flushes buffers periodically"""
        flush_interval_sec = self.config.flush_interval_ms / 1000.0

        while self._running:
            try:
                await asyncio.sleep(flush_interval_sec)

                current_time = time.time()
                customers_to_flush = []

                # Find buffers that need time-based flush
                for customer_id, buffer in self.buffers.items():
                    with buffer.lock:
                        has_data = buffer.raw_logs or buffer.normalized_logs
                        time_since_flush = current_time - buffer.last_flush_time
                        needs_flush = has_data and (time_since_flush * 1000) >= self.config.flush_interval_ms

                    if needs_flush:
                        customers_to_flush.append(customer_id)
                        self.stats.flush_by_time += 1

                # Flush identified buffers
                for customer_id in customers_to_flush:
                    await self._flush_customer_buffer(customer_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        self.stats.update_averages()

        # Calculate current buffer sizes
        current_buffered = 0
        buffer_counts = {}
        for customer_id, buffer in self.buffers.items():
            with buffer.lock:
                count = len(buffer.raw_logs) + len(buffer.normalized_logs)
                current_buffered += count
                if count > 0:
                    buffer_counts[customer_id] = count

        return {
            "config": {
                "max_buffer_size": self.config.max_buffer_size,
                "flush_interval_ms": self.config.flush_interval_ms
            },
            "stats": {
                "total_logs_buffered": self.stats.total_logs_buffered,
                "total_logs_flushed": self.stats.total_logs_flushed,
                "total_flushes": self.stats.total_flushes,
                "flush_by_size": self.stats.flush_by_size,
                "flush_by_time": self.stats.flush_by_time,
                "flush_errors": self.stats.flush_errors,
                "avg_batch_size": round(self.stats.avg_batch_size, 2),
                "avg_flush_time_ms": round(self.stats.avg_flush_time_ms, 2),
                # ENH-007: shedding signals. `logs_dead_lettered` rising means
                # the pipeline is discarding data from the hot path and must be
                # alerted on; `dead_letter_failures` means outright data loss.
                "retry_attempts": self.stats.retry_attempts,
                "logs_dead_lettered": self.stats.logs_dead_lettered,
                "dead_letter_failures": self.stats.dead_letter_failures
            },
            "limits": {
                "max_buffered_logs_per_customer": self.config.max_buffered_logs_per_customer,
                "max_buffered_logs_total": self.config.max_buffered_logs_total
            },
            "current_state": {
                "logs_in_buffer": current_buffered,
                "active_customers": len(buffer_counts),
                "buffer_counts_by_customer": buffer_counts
            },
            "performance": {
                "estimated_throughput_per_sec": round(
                    self.stats.avg_batch_size / (self.stats.avg_flush_time_ms / 1000)
                    if self.stats.avg_flush_time_ms > 0 else 0,
                    2
                )
            }
        }


# Global singleton instance
_write_buffer_instance: Optional[WriteBufferService] = None


def get_write_buffer() -> WriteBufferService:
    """Get the global write buffer instance"""
    global _write_buffer_instance
    if _write_buffer_instance is None:
        _write_buffer_instance = WriteBufferService()
    return _write_buffer_instance


async def init_write_buffer(config: Optional[BufferConfig] = None) -> WriteBufferService:
    """Initialize and start the write buffer service"""
    global _write_buffer_instance
    _write_buffer_instance = WriteBufferService(config)
    await _write_buffer_instance.start_periodic_flush()
    return _write_buffer_instance


async def shutdown_write_buffer():
    """Gracefully shutdown the write buffer (flushes remaining logs)"""
    global _write_buffer_instance
    if _write_buffer_instance:
        await _write_buffer_instance.stop_periodic_flush()
        _write_buffer_instance = None
