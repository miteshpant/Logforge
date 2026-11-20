"""
`| patterns` against ClickHouse (Phase 11): the window's lines are clustered
against the days before; a template the baseline never had is new. Uses a
fresh tenant id in logs_raw_mt.

Needs ClickHouse (LOGFORGE_TEST_CLICKHOUSE); skipped otherwise, unless
LOGFORGE_REQUIRE_CLICKHOUSE is set.
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from test_logql_pipeline_live import _client

COLUMNS = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip", "user_id",
           "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]


@pytest.fixture(scope="module")
def client():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse is required but not reachable")
        pytest.skip("ClickHouse not reachable (set LOGFORGE_TEST_CLICKHOUSE)")
    return client


def test_new_patterns_against_the_baseline(client):
    import pattern_query

    tenant = f"patterns-live-{uuid.uuid4().hex[:8]}"
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=1)
    r = random.Random(7)
    rows = []

    def add(at, service, msg):
        rows.append([at, "web-1", service, "info", msg, "", "", json.dumps({}), 0, "", "", at, 0, 16, "v1", tenant])

    for i in range(3000):  # the baseline: two days before
        at = start - timedelta(hours=48) + timedelta(seconds=i * 20)
        add(at, "checkout", f"order {r.randint(1, 10**6)} paid in {r.randint(10, 900)}ms")
        add(at, "auth", f"user u{r.randint(1, 500)} logged in from 10.0.{r.randint(0, 9)}.{r.randint(1, 250)}")
    for i in range(20_000):  # the window
        at = start + timedelta(seconds=i % 3500)
        add(at, "checkout", f"order {r.randint(1, 10**6)} paid in {r.randint(10, 900)}ms")
    for i in range(7):
        add(end - timedelta(minutes=5, seconds=i), "checkout",
            f"panic: runtime error: index out of range [{i}] with length {i}")
    client.insert("logs_raw_mt", rows, column_names=COLUMNS)

    began = time.perf_counter()
    result = pattern_query.run(client, '| where service = "checkout"', "all", tenant, start, end)
    took = time.perf_counter() - began
    assert result["patterns"]["lines"] == 20_007 and result["patterns"]["baseline_lines"] == 3000
    by = {row["pattern"]: row for row in result["rows"]}
    assert by["order <*> paid in <*>"]["count"] == 20_000 and by["order <*> paid in <*>"]["new"] == 0
    panic = by["panic: runtime error: index out of range [<*>] with length <*>"]
    assert panic["new"] == 1 and panic["count"] == 7 and panic["services"] == "checkout"
    new = pattern_query.run(client, '| where service = "checkout"', "new", tenant, start, end)["rows"]
    assert [row["pattern"] for row in new] == [panic["pattern"]]
    assert took < 10, took
