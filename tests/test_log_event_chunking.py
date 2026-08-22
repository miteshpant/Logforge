"""
Tests for ENH-024 -- oversized log batches must be chunked, not dropped.

The whole log payload travels inside the Kafka event
(`log_publisher.py` puts `batch_info["logs"]` in `event_data`). Kafka's
`max_request_size` is 1 MiB (`config/events.yml:9`), so a large ingest batch
produced a message the broker rejects.

Until ENH-006 that rejection was silent -- the publisher never awaited the
delivery future -- so an oversized batch simply vanished with metrics reporting
success. Chunking removes the failure; ENH-006 ensures any remaining failure is
at least visible.
"""

import json

import pytest

from events.publishers.log_publisher import LogEventPublisher


class _RecordingManager:
    """Captures published events instead of talking to a broker."""

    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)
        return {"kafka_main": True}


def _publisher():
    return LogEventPublisher(_RecordingManager())


def _log(size_bytes=100):
    """A log record whose serialized form is roughly `size_bytes`."""
    return {"msg": "x" * size_bytes, "service": "api"}


def _batch_info(logs):
    return {
        "batch_id": "batch-1",
        "log_count": len(logs),
        "bytes_processed": 1234,
        "endpoint": "/logs",
        "timestamp": "2026-01-01T00:00:00Z",
        "success_count": len(logs),
        "error_count": 0,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# Chunk sizing
# ---------------------------------------------------------------------------


def test_small_batch_is_a_single_chunk():
    publisher = _publisher()
    assert len(publisher._chunk_logs([_log(10) for _ in range(10)])) == 1


def test_empty_batch_still_produces_one_event():
    """A batch with no logs must still publish its metadata event."""
    publisher = _publisher()
    assert publisher._chunk_logs([]) == [[]]


def test_large_batch_is_split():
    publisher = _publisher()
    # ~2 MiB of records against a 700 KiB budget.
    logs = [_log(10_000) for _ in range(200)]

    chunks = publisher._chunk_logs(logs)

    assert len(chunks) > 1, "An oversized batch was not split"
    assert sum(len(c) for c in chunks) == len(logs), "Records were lost"


def test_every_chunk_is_within_the_size_budget():
    publisher = _publisher()
    logs = [_log(10_000) for _ in range(200)]

    for chunk in publisher._chunk_logs(logs):
        size = len(json.dumps(chunk, default=str).encode("utf-8"))
        assert size <= publisher.MAX_PAYLOAD_BYTES, (
            f"Chunk is {size} bytes, above the "
            f"{publisher.MAX_PAYLOAD_BYTES} budget"
        )


def test_no_records_are_duplicated_or_lost():
    publisher = _publisher()
    logs = [{"msg": f"unique-{i}"} for i in range(500)]

    flattened = [r for chunk in publisher._chunk_logs(logs) for r in chunk]

    assert flattened == logs, "Chunking must preserve order and content exactly"


def test_chunking_is_sized_by_bytes_not_record_count():
    """
    Log size varies by orders of magnitude between formats; a count-based split
    would still emit oversized messages for verbose records.
    """
    publisher = _publisher()

    many_small = publisher._chunk_logs([_log(10) for _ in range(500)])
    few_large = publisher._chunk_logs([_log(200_000) for _ in range(10)])

    assert len(many_small) == 1
    assert len(few_large) > 1


def test_single_oversized_record_is_isolated():
    """
    One giant record must not take a whole batch with it. It is emitted alone;
    if the broker rejects it, ENH-006 makes that visible.
    """
    publisher = _publisher()
    logs = [_log(10), {"msg": "y" * 2_000_000}, _log(10)]

    chunks = publisher._chunk_logs(logs)

    assert sum(len(c) for c in chunks) == 3
    giant = [c for c in chunks if any(len(r.get("msg", "")) > 1_000_000 for r in c)]
    assert len(giant) == 1 and len(giant[0]) == 1


def test_unserialisable_record_is_handled_conservatively():
    """An unserialisable record must not cause an under-count and an oversized message."""
    publisher = _publisher()

    class _Weird:
        pass

    chunks = publisher._chunk_logs([{"obj": _Weird()}, _log(10)])
    assert sum(len(c) for c in chunks) == 2


# ---------------------------------------------------------------------------
# Publishing behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_small_batch_publishes_one_event():
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10) for _ in range(5)]

    assert await publisher.publish_batch_ingested(
        "t1", _batch_info(logs), "json", 1.0
    ) is True

    assert len(manager.events) == 1
    assert manager.events[0].data["logs"] == logs


@pytest.mark.asyncio
async def test_large_batch_publishes_multiple_events():
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10_000) for _ in range(200)]

    assert await publisher.publish_batch_ingested(
        "t1", _batch_info(logs), "json", 1.0
    ) is True

    assert len(manager.events) > 1
    published = [r for e in manager.events for r in e.data["logs"]]
    assert len(published) == len(logs), "Chunked publish lost records"


@pytest.mark.asyncio
async def test_chunks_are_labelled():
    """A consumer must be able to tell a split batch from a whole one."""
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10_000) for _ in range(200)]

    await publisher.publish_batch_ingested("t1", _batch_info(logs), "json", 1.0)

    total = manager.events[0].data["chunk_count"]
    assert total == len(manager.events)
    assert [e.data["chunk_index"] for e in manager.events] == list(range(total))


@pytest.mark.asyncio
async def test_log_count_reflects_each_chunk_not_the_whole_batch():
    """
    Otherwise downstream metering and billing would multiply the batch size by
    the number of chunks.
    """
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10_000) for _ in range(200)]

    await publisher.publish_batch_ingested("t1", _batch_info(logs), "json", 1.0)

    assert sum(e.data["log_count"] for e in manager.events) == len(logs)


@pytest.mark.asyncio
async def test_bytes_processed_is_not_multiplied_across_chunks():
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10_000) for _ in range(200)]

    await publisher.publish_batch_ingested("t1", _batch_info(logs), "json", 1.0)

    assert sum(e.data["bytes_processed"] for e in manager.events) == 0, (
        "bytes_processed must be attributed once, not per chunk"
    )


@pytest.mark.asyncio
async def test_single_chunk_retains_original_batch_totals():
    """The common (unsplit) case must be byte-identical to previous behaviour."""
    manager = _RecordingManager()
    publisher = LogEventPublisher(manager)
    logs = [_log(10) for _ in range(3)]

    await publisher.publish_batch_ingested("t1", _batch_info(logs), "json", 1.0)

    event = manager.events[0]
    assert event.data["bytes_processed"] == 1234
    assert event.data["log_count"] == 3
    assert event.data["chunk_count"] == 1
