"""
Durable ingest (Phase 12): an acknowledged batch survives the API replica
that consumed it being killed.

The log subscriber used to auto-commit Kafka offsets every 5 s for every
message fetched, whether or not it had been written; the batch then sat in
the in-process write buffer for up to 100 ms. A replica killed in between
lost those batches for good (the chaos test lost 40 of 5,160 acknowledged
events). Now the log subscriber commits only offsets whose batch is in
ClickHouse, retrying a failed write (a replica failing over) instead of
dead-lettering it to the dying replica's disk.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from events.offsets import OffsetTracker  # noqa: E402


def test_offsets_are_committed_only_up_to_the_first_unfinished_message():
    t = OffsetTracker()
    for offset in (10, 11, 12, 13):
        t.track("p0", offset)
    t.track("p1", 5)
    assert t.committable() == {}
    t.done("p0", 11)
    t.done("p0", 12)
    assert t.committable() == {}  # 10 is still being written
    t.done("p0", 10)
    assert t.committable() == {"p0": 13}  # Kafka commits the next offset to read
    t.done("p1", 5)
    t.done("p0", 13)
    assert t.committable() == {"p0": 14, "p1": 6}
    assert t.committable() == {}  # nothing new since the last commit
    assert t.pending() == 0


def test_revoked_partitions_are_forgotten():
    t = OffsetTracker()
    t.track("p0", 1)
    t.track("p1", 1)
    t.revoke(["p0"])
    t.done("p1", 1)
    t.done("p0", 1)  # finished after its partition moved: not ours to commit
    assert t.committable() == {"p1": 2}


def test_write_now_reports_failure_and_does_not_dead_letter(tmp_path):
    from services.write_buffer_service import BufferConfig, WriteBufferService

    calls = []

    async def failing(customer_id, raw, normalized):
        calls.append(len(raw))
        return False

    buf = WriteBufferService(BufferConfig(max_retry_attempts=2, retry_delay_ms=1, dead_letter_dir=str(tmp_path)))
    buf.set_flush_callback(failing)
    assert asyncio.run(buf.write_now("acme", [{"msg": "a"}, {"msg": "b"}])) is False
    assert calls == [2, 2]  # retried, then reported to the caller
    assert list(tmp_path.iterdir()) == []  # not dead-lettered: the caller retries, Kafka keeps it

    async def ok(customer_id, raw, normalized):
        return True

    buf.set_flush_callback(ok)
    assert asyncio.run(buf.write_now("acme", [{"msg": "a"}])) is True


def test_the_log_subscriber_commits_after_processing():
    from events.subscribers import EventSubscriberManager

    configs = EventSubscriberManager().subscriber_configs
    logs = configs["log_subscriber"]
    assert logs.commit_after_processing is True and logs.enable_auto_commit is False
    assert logs.retry_budget_s >= 60


def test_a_failed_event_is_retried_until_it_succeeds_then_marked_done():
    from events.subscribers import process_until_done

    attempts = []

    async def flaky():
        attempts.append(1)
        return len(attempts) >= 3

    ok = asyncio.run(process_until_done(flaky, budget_s=5, delay_s=0.01))
    assert ok is True and len(attempts) == 3

    async def broken():
        return False

    assert asyncio.run(process_until_done(broken, budget_s=0.05, delay_s=0.01)) is False


# The batch endpoint used to answer 200 and publish to Kafka afterwards, in a
# background task: a replica killed in between lost a batch the shipper had
# been told was accepted (the chaos test lost 20 events this way after the
# consumer fix). It now waits for the broker's acknowledgement first.

def _entries(n):
    from models import LogEntry

    return [LogEntry(service="svc", msg=f"m{i}") for i in range(n)]


def test_batch_ingest_answers_only_after_kafka_acknowledged(monkeypatch):
    from unittest.mock import MagicMock

    from routers import ingestion

    published = []

    async def publish(logs, customer_id, endpoint, format_type, bytes_processed, processing_time_ms):
        published.append((len(logs), customer_id, endpoint))
        return True

    monkeypatch.setattr(ingestion, "check_ingest_capacity", lambda: None)
    monkeypatch.setattr(ingestion, "publish_logs_durably", publish)
    tasks = MagicMock()
    out = asyncio.run(ingestion.ingest_logs_batch(background_tasks=tasks, batch=_entries(3), customer_id="t1",
                                                  pipeline=None))
    assert out.processed_count == 3
    assert published == [(3, "t1", "/logs/batch")]
    tasks.add_task.assert_not_called()  # nothing left to do after the answer


def test_batch_ingest_is_a_503_when_kafka_did_not_take_it(monkeypatch):
    from unittest.mock import MagicMock

    import pytest
    from fastapi import HTTPException

    from routers import ingestion

    async def publish(*args, **kwargs):
        return False

    monkeypatch.setattr(ingestion, "check_ingest_capacity", lambda: None)
    monkeypatch.setattr(ingestion, "publish_logs_durably", publish)
    with pytest.raises(HTTPException) as err:
        asyncio.run(ingestion.ingest_logs_batch(background_tasks=MagicMock(), batch=_entries(2), customer_id="t1",
                                                pipeline=None))
    assert err.value.status_code == 503  # the shipper retries


def test_durable_ingest_can_be_turned_off(monkeypatch):
    from unittest.mock import MagicMock

    from routers import ingestion

    async def publish(*args, **kwargs):
        raise AssertionError("not used when LOGFORGE_DURABLE_INGEST=off")

    monkeypatch.setenv("LOGFORGE_DURABLE_INGEST", "off")
    monkeypatch.setattr(ingestion, "check_ingest_capacity", lambda: None)
    monkeypatch.setattr(ingestion, "publish_logs_durably", publish)
    monkeypatch.setattr(ingestion, "process_logs_and_tracking_background", MagicMock())
    tasks = MagicMock()
    asyncio.run(ingestion.ingest_logs_batch(background_tasks=tasks, batch=_entries(1), customer_id="t1",
                                            pipeline=None))
    tasks.add_task.assert_called_once()
