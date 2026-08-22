"""
Tests for ENH-009 -- bounded ingest worker pool.

`process_logs_and_tracking_background()` spawned a **daemon thread per ingested
batch**, each building its own event loop and its own ClickHouse client, then
tearing both down. Three problems:

1. Unbounded thread and connection creation -- at modest request rates this
   exhausts thread stacks and file descriptors, capping ingest throughput far
   below the hardware. For an observability product, ingest throughput is the
   headline number.
2. Connection setup dominated per-batch latency.
3. The ClickHouse client was never used: the downstream coroutine only
   publishes a Kafka event. Every batch paid for a connection that did nothing.
"""

import asyncio

import pytest

import ingest_pipeline
from ingest_pipeline import IngestPipeline, reset_ingest_pipeline


@pytest.fixture(autouse=True)
def clean():
    reset_ingest_pipeline()
    yield
    reset_ingest_pipeline()


@pytest.fixture
def processed(monkeypatch):
    """Capture batches reaching the downstream coroutine."""
    seen = []

    async def _fake_process(self, batch):
        seen.append(batch)

    monkeypatch.setattr(IngestPipeline, "_process", _fake_process)
    return seen


def _submit(pipeline, customer_id="t1", count=1):
    return pipeline.submit(
        logs=[{"msg": "x"}],
        customer_id=customer_id,
        endpoint="/logs",
        format_type="json",
        log_count=count,
        bytes_processed=10,
        processing_time_ms=1,
    )


# ---------------------------------------------------------------------------
# Batches are processed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submitted_batch_is_processed(processed):
    pipeline = IngestPipeline(workers=2, queue_size=10)
    await pipeline.start()

    assert _submit(pipeline) is True
    await asyncio.wait_for(pipeline._queue.join(), timeout=2)

    assert len(processed) == 1
    await pipeline.stop()


@pytest.mark.asyncio
async def test_many_batches_are_all_processed(processed):
    pipeline = IngestPipeline(workers=4, queue_size=100)
    await pipeline.start()

    for _ in range(50):
        _submit(pipeline)
    await asyncio.wait_for(pipeline._queue.join(), timeout=5)

    assert len(processed) == 50
    assert pipeline.stats.processed == 50
    await pipeline.stop()


# ---------------------------------------------------------------------------
# Concurrency is bounded -- the headline fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_worker_count(monkeypatch):
    """
    The whole point: with thread-per-batch, 200 batches meant 200 threads. Here
    it must never exceed the configured worker count.
    """
    concurrent = 0
    peak = 0

    async def _slow_process(self, batch):
        nonlocal concurrent, peak
        concurrent += 1
        peak = max(peak, concurrent)
        await asyncio.sleep(0.01)
        concurrent -= 1

    monkeypatch.setattr(IngestPipeline, "_process", _slow_process)

    pipeline = IngestPipeline(workers=3, queue_size=500)
    await pipeline.start()

    for _ in range(100):
        _submit(pipeline)
    await asyncio.wait_for(pipeline._queue.join(), timeout=10)

    assert peak <= 3, f"Concurrency reached {peak}, above the 3-worker cap"
    await pipeline.stop()


@pytest.mark.asyncio
async def test_no_threads_are_spawned_per_batch(processed):
    """The previous implementation created a daemon thread for every batch."""
    import threading

    pipeline = IngestPipeline(workers=2, queue_size=100)
    await pipeline.start()

    before = threading.active_count()
    for _ in range(50):
        _submit(pipeline)
    await asyncio.wait_for(pipeline._queue.join(), timeout=5)
    after = threading.active_count()

    assert after <= before + 1, (
        f"Thread count grew from {before} to {after} -- batches are still "
        "spawning threads."
    )
    await pipeline.stop()


# ---------------------------------------------------------------------------
# Back-pressure: fail fast and visibly, never grow without bound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_queue_rejects_rather_than_growing(monkeypatch):
    async def _blocked(self, batch):
        await asyncio.sleep(30)

    monkeypatch.setattr(IngestPipeline, "_process", _blocked)

    pipeline = IngestPipeline(workers=1, queue_size=2)
    await pipeline.start()

    results = [_submit(pipeline) for _ in range(20)]

    assert False in results, "A full queue must reject submissions"
    assert pipeline.stats.dropped_queue_full > 0
    assert pipeline._queue.qsize() <= 2, "Queue grew beyond its declared bound"

    await pipeline.stop(drain_timeout=0.1)


@pytest.mark.asyncio
async def test_drops_are_counted_not_silent(monkeypatch):
    """
    An invisible drop is worse than a visible one: it looks like the customer
    never sent the data.
    """
    async def _blocked(self, batch):
        await asyncio.sleep(30)

    monkeypatch.setattr(IngestPipeline, "_process", _blocked)

    pipeline = IngestPipeline(workers=1, queue_size=1)
    await pipeline.start()

    for _ in range(10):
        _submit(pipeline)

    assert pipeline.get_stats()["stats"]["dropped_queue_full"] > 0
    await pipeline.stop(drain_timeout=0.1)


@pytest.mark.asyncio
async def test_submission_before_start_is_rejected_and_counted():
    """A batch arriving before startup must be reported, not silently lost."""
    pipeline = IngestPipeline(workers=1, queue_size=10)

    assert _submit(pipeline) is False
    assert pipeline.stats.dropped_not_running == 1


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_failing_batch_does_not_kill_the_worker(monkeypatch):
    calls = []

    async def _sometimes_fails(self, batch):
        calls.append(batch)
        if len(calls) == 1:
            raise RuntimeError("kafka unavailable")

    monkeypatch.setattr(IngestPipeline, "_process", _sometimes_fails)

    pipeline = IngestPipeline(workers=1, queue_size=10)
    await pipeline.start()

    for _ in range(3):
        _submit(pipeline)
    await asyncio.wait_for(pipeline._queue.join(), timeout=5)

    assert len(calls) == 3, "Worker died after the first failure"
    assert pipeline.stats.failed == 1
    assert pipeline.stats.processed == 2
    await pipeline.stop()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_drains_outstanding_work(processed):
    """
    Batches already accepted from a customer get a bounded chance to complete
    rather than being discarded on shutdown.
    """
    pipeline = IngestPipeline(workers=2, queue_size=100)
    await pipeline.start()

    for _ in range(20):
        _submit(pipeline)
    await pipeline.stop(drain_timeout=5)

    assert len(processed) == 20


@pytest.mark.asyncio
async def test_start_is_idempotent(processed):
    pipeline = IngestPipeline(workers=2, queue_size=10)
    await pipeline.start()
    await pipeline.start()

    assert len(pipeline._workers) == 2
    await pipeline.stop()


@pytest.mark.asyncio
async def test_stats_expose_queue_depth_and_capacity():
    pipeline = IngestPipeline(workers=1, queue_size=7)
    await pipeline.start()

    stats = pipeline.get_stats()
    assert stats["queue_size"] == 7
    assert stats["running"] is True
    await pipeline.stop()


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


def test_background_entrypoint_no_longer_spawns_threads():
    import inspect

    import dependencies

    source = inspect.getsource(dependencies.process_logs_and_tracking_background)

    assert "threading.Thread" not in source, (
        "Thread-per-batch must not return -- it is the ENH-009 scale limiter."
    )
    assert "new_event_loop" not in source
    assert "get_ingest_pipeline" in source


def test_pipeline_is_started_and_stopped_in_lifespan():
    import inspect

    import dependencies

    source = inspect.getsource(dependencies.lifespan)
    assert "start_ingest_pipeline" in source
    assert "stop_ingest_pipeline" in source


def test_no_per_batch_clickhouse_client_is_created():
    """
    The old code opened and closed a ClickHouse connection per batch that the
    downstream coroutine never used.
    """
    import inspect

    source = inspect.getsource(ingest_pipeline.IngestPipeline._process)
    assert "get_client" not in source
