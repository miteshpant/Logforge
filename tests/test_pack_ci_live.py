"""
Pack CI, live (Phase 7): each pack's parsed samples are stored in a scratch
copy of logs_raw_mt, and every dashboard panel and saved search of the pack
runs against them in ClickHouse. A query that errors fails the pack, and
each dashboard must show data from the samples.

Skipped without ClickHouse; the live-stack CI job runs it.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import dashboard_queries as dq
import logql_pipeline as lp
import pack_ci
import source_packs as sp
from test_logql_pipeline_live import MIGRATION, _client

NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
COLUMNS = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip", "user_id",
           "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]
CATALOGUE, _ = sp.load_catalogue()


def row(event, ts, tenant):
    status = event.get("status") or 0
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 0
    return [ts, str(event.get("host") or ""), str(event.get("service") or ""), str(event.get("level") or "info"),
            str(event.get("msg") or ""), str(event.get("trace_id") or ""), "", json.dumps(event.get("attrs") or {}),
            status, str(event.get("src_ip") or ""), str(event.get("user_id") or ""), ts, 0, 16, "v1", tenant]


@pytest.fixture(scope="module")
def ch():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE") == "1":
            pytest.fail("ClickHouse is not reachable and LOGFORGE_REQUIRE_CLICKHOUSE=1")
        pytest.skip("ClickHouse is not reachable")
    sql = "\n".join(l for l in open(MIGRATION).read().splitlines() if not l.lstrip().startswith("--"))
    for statement in sql.split(";"):
        if "CREATE TABLE" in statement:
            client.command(statement)
    table = f"test_packs_{uuid.uuid4().hex[:8]}"
    client.command(f"CREATE TABLE {table} AS logs_raw_mt")
    yield client, table
    client.command(f"DROP TABLE IF EXISTS {table}")


@pytest.mark.parametrize("pack", CATALOGUE, ids=[p.id for p in CATALOGUE])
def test_pack_queries_run_on_its_samples(ch, pack):
    client, table = ch
    tenant = f"pack-ci-{pack.id}"
    report = pack_ci.check_pack(pack, now=NOW)
    assert report.ok, report.failures
    rows = []
    for events in report.events.values():
        for i, event in enumerate(events):
            rows.append(row(event, NOW - timedelta(minutes=50) + timedelta(seconds=i * 10 % 2400), tenant))
    client.insert(table, rows, column_names=COLUMNS)
    if pack.lookups:
        client.insert("lookup_rows_mt", [[tenant, name, 1, key, values] for name, t in pack.lookups.items()
                                         for key, values in t["rows"].items()],
                      column_names=["tenant_id", "lookup", "version", "key", "values"])
    lookups = {name: lp.LookupMeta(name, 1, t["columns"], t["key"]) for name, t in pack.lookups.items()}
    start, end = NOW - timedelta(hours=1), NOW

    def run(query, variables=None):
        compiled = lp.compile_pipeline(query, customer_id=tenant, start=start, end=end, table=table,
                                       lookups=lookups, variables=variables or {})
        return lp.execute(client, compiled)

    try:
        for search in pack.searches:
            run(search.query)
        for dashboard in pack.dashboards:
            values = dq.resolve(dashboard["variables"], {})
            shown = 0
            for panel in dashboard["panels"]:
                result = run(panel["query"], values)
                shaped = dq.shape(panel["type"], result)
                shown += bool(result["rows"]) and shaped.get("value", 1) is not None
            assert shown, f"{dashboard['name']}: no panel shows data from the samples"
    finally:
        client.command("ALTER TABLE lookup_rows_mt DELETE WHERE tenant_id = %(t)s", {"t": tenant})
