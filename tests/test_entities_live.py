"""
Entities against ClickHouse (Phase 11): events written to logs_raw_mt appear
in entities_mt and entity_edges_mt through the materialized views of
migration 026, and EntityStore reads them back. Uses a fresh tenant id.

Needs ClickHouse with the migrations applied (LOGFORGE_TEST_CLICKHOUSE);
skipped otherwise, unless LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from test_logql_pipeline_live import _client


class Adapter:
    """The DatabaseLayer methods EntityStore uses, over a clickhouse_connect client."""

    def __init__(self, client):
        self.client = client

    async def fetch_all(self, sql, params):
        return list(self.client.query(sql, parameters=params).named_results())


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse is required but not reachable")
        pytest.skip("ClickHouse not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    if not client.query("EXISTS TABLE entities_mt").result_rows[0][0]:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("migration 026 is not applied")
        pytest.skip("migration 026 is not applied")
    return client


def test_events_become_entities_and_relationships(client):
    from entities import EntityStore

    tenant = f"entities-live-{uuid.uuid4().hex[:8]}"
    t0 = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    rows = []
    for i in range(3):
        rows.append([t0 + timedelta(minutes=i), "web-1", "sshd", "info", "Accepted password", "", "",
                     json.dumps({"dst_ip": "10.0.0.9"}), 0, "203.0.113.7", "bob", t0, 0, 16, "v1", tenant])
    rows.append([t0 + timedelta(minutes=5), "", "cloudtrail", "info", "ConsoleLogin", "", "",
                 json.dumps({"recipientAccountId": "123456789012", "user": "alice", "hostname": "aws"}), 0, "",
                 "", t0, 0, 16, "v1", tenant])
    columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
               "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
    client.insert("logs_raw_mt", rows, column_names=columns)
    store = EntityStore(Adapter(client))

    found = {(e["entity_type"], e["value"]): e for e in asyncio.run(store.search(tenant))}
    assert found[("user", "bob")]["events"] == 3
    assert found[("ip", "203.0.113.7")]["first_seen"].startswith(t0.isoformat()[:16])
    assert ("ip", "10.0.0.9") in found and ("cloud_account", "123456789012") in found
    assert ("user", "alice") in found and ("host", "aws") in found
    related = {(r["entity_type"], r["value"]) for r in asyncio.run(store.related(tenant, "host", "web-1"))}
    assert {("user", "bob"), ("ip", "203.0.113.7"), ("service", "sshd")} <= related
    bob = asyncio.run(store.get(tenant, "user", "bob"))
    assert bob["events"] == 3 and asyncio.run(store.get(tenant, "user", "nobody")) is None


def test_baselines_flag_a_users_unusual_last_day(client):
    from entity_baselines import BaselineStore

    tenant = f"baselines-live-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).replace(minute=30, second=0, microsecond=0)
    columns = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
               "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
    rows = []

    def add(at, host, user, country):
        rows.append([at, host, "sshd", "info", "Accepted password", "", "", json.dumps({"geo": {"country": country}}),
                     0, "10.0.0.5", user, at, 0, 16, "v1", tenant])

    for day in range(2, 22):
        for hour in (9, 11, 14, 16):
            add(now - timedelta(days=day) + timedelta(hours=hour - now.hour), "ws-1", "bob", "DE")
    for i in range(12):  # the last day: 03:00 from Romania, across many hosts
        add(now - timedelta(hours=now.hour - 3 if now.hour > 3 else 1, minutes=i), f"srv-{i}", "bob", "RO")
    for u in range(10):
        add(now - timedelta(hours=2), "ws-9", f"peer{u}", "DE")
    client.insert("logs_raw_mt", rows, column_names=columns)

    found = asyncio.run(BaselineStore(Adapter(client)).anomalies(tenant, "user", ["bob"], now=now))
    kinds = {a.kind for a in found["bob"]}
    assert {"country", "volume", "peers"} <= kinds, found
