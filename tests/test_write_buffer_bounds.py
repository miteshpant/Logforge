"""
Tests for ENH-007 -- bounded write buffer with a dead-letter path.

Before this change, a failed flush prepended rows back into the same in-memory
buffer with no size cap and no retry ceiling. A sustained ClickHouse outage
therefore grew the buffer until the process was OOM-killed, losing every
buffered log at once -- the worst possible outcome, since the data was accepted
from the customer with a 202.

`BufferConfig.max_retry_attempts` and `retry_delay_ms` were also declared but
never referenced, so operators believed retries were happening when they were not.

These tests pin: memory stays bounded, retries actually occur, and overflow is
durably dead-lettered rather than dropped or accumulated.
"""

import json

import pytest

from services.write_buffer_service import (
    BufferConfig,
    DeadLetterSink,
    WriteBufferService,
)


def _logs(count, prefix="log"):
    return [{"msg": f"{prefix}-{i}", "customer_id": "t1"} for i in range(count)]


@pytest.fixture
def dlq_dir(tmp_path):
    return tmp_path / "dlq"


@pytest.fixture
def sink(dlq_dir):
    return DeadLetterSink(str(dlq_dir))


def _service(sink, **config_overrides):
    settings = {
        "max_buffer_size": 1_000_000,  # disable size-triggered flush unless asked
        "flush_interval_ms": 100,
        "max_retry_attempts": 3,
        "retry_delay_ms": 0,  # keep tests fast
    }
    settings.update(config_overrides)
    return WriteBufferService(
        config=BufferConfig(**settings), dead_letter_sink=sink
    )


# ---------------------------------------------------------------------------
# Memory bounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_customer_cap_is_enforced(sink):
    svc = _service(sink, max_buffered_logs_per_customer=10)

    accepted = await svc.add_logs("t1", raw_logs=_logs(25))

    buffered = len(svc.buffers["t1"].raw_logs)
    assert buffered == 10, f"Buffer exceeded its per-customer cap: {buffered}"
    assert accepted is False, "Caller must be told that logs were shed."


@pytest.mark.asyncio
async def test_global_cap_is_enforced_across_customers(sink):
    svc = _service(
        sink, max_buffered_logs_per_customer=1000, max_buffered_logs_total=15
    )

    await svc.add_logs("t1", raw_logs=_logs(10))
    await svc.add_logs("t2", raw_logs=_logs(10))

    total = sum(
        len(b.raw_logs) + len(b.normalized_logs) for b in svc.buffers.values()
    )
    assert total == 15, f"Global cap not enforced: {total} buffered"


@pytest.mark.asyncio
async def test_overflow_is_dead_lettered_not_dropped(sink, dlq_dir):
    svc = _service(sink, max_buffered_logs_per_customer=10)

    await svc.add_logs("t1", raw_logs=_logs(25))

    assert svc.stats.logs_dead_lettered == 15
    dlq_file = dlq_dir / "t1.dlq.jsonl"
    assert dlq_file.exists(), "Overflow must be persisted durably."

    lines = dlq_file.read_text().strip().split("\n")
    assert len(lines) == 15
    record = json.loads(lines[0])
    assert record["customer_id"] == "t1"
    assert record["reason"] == "buffer_capacity_exceeded"
    assert "record" in record


@pytest.mark.asyncio
async def test_buffer_does_not_grow_without_bound_during_outage(sink):
    """
    The headline regression: a persistent downstream failure must not grow the
    heap. Previously every failed flush pushed rows back in.
    """
    svc = _service(sink, max_buffer_size=10, max_buffered_logs_per_customer=50)

    async def always_fail(customer_id, raw, normalized):
        return False

    svc.set_flush_callback(always_fail)

    for _ in range(50):
        await svc.add_logs("t1", raw_logs=_logs(10))

    buffered = len(svc.buffers["t1"].raw_logs) + len(svc.buffers["t1"].normalized_logs)
    assert buffered <= 50, f"Buffer grew unbounded during outage: {buffered}"
    assert svc.stats.logs_dead_lettered > 0


# ---------------------------------------------------------------------------
# Retries actually happen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_is_retried_up_to_configured_attempts(sink):
    svc = _service(sink, max_retry_attempts=3)
    attempts = []

    async def failing(customer_id, raw, normalized):
        attempts.append(1)
        return False

    svc.set_flush_callback(failing)
    await svc.add_logs("t1", raw_logs=_logs(5))
    await svc._flush_customer_buffer("t1")

    assert len(attempts) == 3, (
        f"Expected 3 attempts from max_retry_attempts, got {len(attempts)}. "
        "The retry config was previously dead code."
    )


@pytest.mark.asyncio
async def test_flush_succeeding_on_retry_is_not_dead_lettered(sink):
    svc = _service(sink, max_retry_attempts=3)
    calls = {"n": 0}

    async def flaky(customer_id, raw, normalized):
        calls["n"] += 1
        return calls["n"] >= 2  # fail once, then succeed

    svc.set_flush_callback(flaky)
    await svc.add_logs("t1", raw_logs=_logs(5))
    result = await svc._flush_customer_buffer("t1")

    assert result is True
    assert svc.stats.logs_dead_lettered == 0
    assert svc.stats.retry_attempts == 1


@pytest.mark.asyncio
async def test_exhausted_retries_dead_letter_the_batch(sink, dlq_dir):
    svc = _service(sink, max_retry_attempts=2)

    async def always_fail(customer_id, raw, normalized):
        return False

    svc.set_flush_callback(always_fail)
    await svc.add_logs("t1", raw_logs=_logs(7))
    result = await svc._flush_customer_buffer("t1")

    assert result is False
    assert svc.stats.logs_dead_lettered == 7
    assert (dlq_dir / "t1.dlq.jsonl").exists()


@pytest.mark.asyncio
async def test_flush_exception_dead_letters_the_batch(sink):
    svc = _service(sink, max_retry_attempts=1)

    async def boom(customer_id, raw, normalized):
        raise RuntimeError("clickhouse unreachable")

    svc.set_flush_callback(boom)
    await svc.add_logs("t1", raw_logs=_logs(4))
    result = await svc._flush_customer_buffer("t1")

    assert result is False
    assert svc.stats.logs_dead_lettered == 4


@pytest.mark.asyncio
async def test_failed_batch_is_not_requeued(sink):
    """Re-queueing is what made the buffer unbounded; it must not come back."""
    svc = _service(sink, max_retry_attempts=1)

    async def always_fail(customer_id, raw, normalized):
        return False

    svc.set_flush_callback(always_fail)
    await svc.add_logs("t1", raw_logs=_logs(5))
    await svc._flush_customer_buffer("t1")

    assert svc.buffers["t1"].raw_logs == []
    assert svc.buffers["t1"].normalized_logs == []


# ---------------------------------------------------------------------------
# Dead-letter durability and failure accounting
# ---------------------------------------------------------------------------


def test_dead_letter_sink_sanitises_customer_id(tmp_path):
    """
    A customer id reaches the filesystem as a filename, so path traversal must
    be neutralised -- otherwise a hostile tenant id could write outside the DLQ
    directory.
    """
    sink = DeadLetterSink(str(tmp_path))
    sink.write("../../etc/passwd", [{"msg": "x"}], "test")

    written = list(tmp_path.glob("*.dlq.jsonl"))
    assert len(written) == 1, "The file must land inside the DLQ directory."
    name = written[0].name
    assert "/" not in name
    assert ".." not in name
    # '..' is collapsed first, then anything outside [A-Za-z0-9_.-] becomes '_'.
    assert name == "____etc_passwd.dlq.jsonl"
    # The resolved path must stay inside the DLQ directory.
    assert written[0].resolve().parent == tmp_path.resolve()


def test_dead_letter_sink_rejects_empty_customer_id(tmp_path):
    sink = DeadLetterSink(str(tmp_path))
    sink.write("...", [{"msg": "x"}], "test")

    written = list(tmp_path.glob("*.dlq.jsonl"))
    assert written[0].name == "unknown.dlq.jsonl"


def test_dead_letter_sink_appends_across_calls(tmp_path):
    sink = DeadLetterSink(str(tmp_path))
    sink.write("t1", [{"msg": "a"}], "r1")
    sink.write("t1", [{"msg": "b"}], "r2")

    lines = (tmp_path / "t1.dlq.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2


def test_dead_letter_write_failure_is_counted_as_loss(sink, monkeypatch):
    svc = _service(sink)

    def explode(customer_id, logs, reason):
        raise OSError("disk full")

    monkeypatch.setattr(svc._dead_letter_sink, "write", explode)
    svc._dead_letter("t1", _logs(3), "test")

    assert svc.stats.dead_letter_failures == 3, (
        "A DLQ write failure is real data loss and must be counted explicitly."
    )
    assert svc.stats.logs_dead_lettered == 0


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_expose_shedding_signals(sink):
    svc = _service(sink, max_buffered_logs_per_customer=5)
    await svc.add_logs("t1", raw_logs=_logs(20))

    stats = svc.get_stats()

    assert stats["stats"]["logs_dead_lettered"] == 15
    assert "dead_letter_failures" in stats["stats"]
    assert "retry_attempts" in stats["stats"]
    assert stats["limits"]["max_buffered_logs_per_customer"] == 5


@pytest.mark.asyncio
async def test_normal_operation_is_unaffected(sink):
    """The happy path must keep working: accept, flush, report success."""
    svc = _service(sink, max_buffer_size=10)
    flushed = []

    async def ok(customer_id, raw, normalized):
        flushed.extend(raw)
        return True

    svc.set_flush_callback(ok)

    accepted = await svc.add_logs("t1", raw_logs=_logs(10))

    assert accepted is True
    assert len(flushed) == 10
    assert svc.stats.logs_dead_lettered == 0
    assert svc.stats.flush_errors == 0
