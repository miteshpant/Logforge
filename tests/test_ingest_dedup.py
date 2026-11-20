"""Exactly-once ingest: a batch written twice (an in-process retry after an
insert that did succeed, or Kafka redelivering an unacknowledged message) is
stored once. Each insert carries an insert_deduplication_token derived from the
batch's content (not from ingested_at, which a redelivery restamps), and
logs_raw_mt keeps a deduplication window (migration 038)."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from events.management.processors import log_processor as lp  # noqa: E402
from models import LogEntry  # noqa: E402

TS = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def entries(svc="auth", ingested=None):
    return [LogEntry(ts=TS, service=svc, level="info", msg=f"login {i}", ingested_at=ingested) for i in range(3)]


def test_the_token_depends_on_content_not_on_ingest_time():
    a = lp.dedup_token("acme", entries(ingested=datetime(2026, 11, 20, 12, 1, tzinfo=timezone.utc)))
    b = lp.dedup_token("acme", entries(ingested=datetime(2026, 11, 20, 12, 5, tzinfo=timezone.utc)))
    assert a == b
    assert a != lp.dedup_token("other", entries())
    assert a != lp.dedup_token("acme", entries(svc="billing"))


def test_inserts_carry_the_token():
    seen = {}

    class Client:
        def insert(self, table, rows, column_names=None, settings=None):
            seen.update(table=table, settings=settings or {})

    asyncio.run(lp.process_log_batch_internal(entries(), Client(), "acme"))
    assert seen["table"] == "logs_raw_mt"
    assert seen["settings"]["insert_deduplication_token"] == lp.dedup_token("acme", entries())


def test_a_repeated_batch_is_stored_once():
    from test_logql_pipeline_live import _client

    client = _client()
    if client is None or not client.query(
            "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = 'logs_raw_mt' "
            "AND create_table_query LIKE '%non_replicated_deduplication_window%'").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse with migration 038 is required")
        pytest.skip("ClickHouse with migration 038 not reachable")
    tenant = f"dedup-{uuid.uuid4().hex[:8]}"
    batch = entries(svc=tenant)
    for _ in range(3):  # a retry and a redelivery
        asyncio.run(lp.process_log_batch_internal(batch, client, tenant))
    asyncio.run(lp.process_log_batch_internal(entries(svc=tenant + "-b"), client, tenant))  # a different batch
    count = client.query("SELECT count() FROM logs_raw_mt WHERE customer_id = {t:String}",
                         parameters={"t": tenant}).result_rows[0][0]
    assert count == 6
