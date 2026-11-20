"""
Storage tiers against the real stack (Phase 12): ClickHouse with the `tiered`
policy and the `logforge_archive` named collection (compose mounts
infra/docker/clickhouse/config.d/s3_storage.xml), and MinIO.

A tenant's day past its searchable period is written to Parquet by
ClickHouse, read back and counted, deleted from ClickHouse, then expires.
Only this test's tenant is touched.

    LOGFORGE_TEST_CLICKHOUSE=localhost:8124 LOGFORGE_S3_ENDPOINT=http://localhost:9003 \
        pytest tests/test_storage_tiers_live.py
"""

import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "apps", "api"), os.path.dirname(__file__)]

from test_logql_pipeline_live import _client  # noqa: E402

COLUMNS = ["ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip", "user_id",
           "ingested_at", "severity_num", "facility", "parser_version", "customer_id"]


@pytest.fixture(scope="module")
def stack():
    client = _client()
    if client is None:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            pytest.fail("ClickHouse is required")
        pytest.skip("ClickHouse is not reachable")
    os.environ.setdefault("LOGFORGE_S3_ENDPOINT", "http://localhost:9003")
    os.environ.setdefault("LOGFORGE_S3_ACCESS_KEY", "minio")
    os.environ.setdefault("LOGFORGE_S3_SECRET_KEY", "minio123")
    import storage_tiers as st
    import tier_manager as tm

    cfg = st.load_config()
    objects = tm.S3Objects(cfg.archive_bucket)
    try:
        objects.ensure_buckets(cfg.archive_bucket, cfg.warm_bucket)
    except Exception as e:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            raise
        pytest.skip(f"object storage is not reachable: {e}")
    return client, tm.TierManager(client, objects, cfg), st, tm


def _rows(tenant, day, n):
    at = datetime.combine(day, time(12), tzinfo=timezone.utc)
    return [[at + timedelta(seconds=i), "h1", "api", "info", f"event {i} of {day}", "", "", '{"k": "v"}', 200,
             "10.0.0.1", "u1", at, 6, 16, "v1", tenant] for i in range(n)]


def test_tables_are_tiered(stack):
    client, mgr, st, _ = stack
    status = mgr.ensure_tables()
    assert status["warm"] is True, "the server has no `tiered` storage policy (s3_storage.xml not mounted?)"
    policy = client.query("SELECT storage_policy, engine_full FROM system.tables WHERE database = currentDatabase() "
                          "AND name = 'logs_raw_mt'").result_rows[0]
    assert policy[0] == "tiered"
    assert "TO VOLUME 'warm'" in policy[1]
    volumes = client.query("SELECT volume_name, disks FROM system.storage_policies "
                           "WHERE policy_name = 'tiered' ORDER BY volume_priority").result_rows
    assert [v[0] for v in volumes] == ["default", "warm"]  # the hot volume keeps the old policy's name


def test_data_older_than_hot_days_lands_on_warm_and_stays_searchable(stack):
    client, mgr, st, _ = stack
    mgr.ensure_tables()
    tenant = f"tiers-warm-{uuid.uuid4().hex[:8]}"
    old = date.today() - timedelta(days=60)  # older than hot_days: the TTL puts it on warm when written
    client.insert("logs_raw_mt", _rows(tenant, old, 20), column_names=COLUMNS)
    where = ("database = currentDatabase() AND table = 'logs_raw_mt' AND active AND "
             "min_time <= {at:DateTime} AND max_time >= {at:DateTime} AND partition LIKE {p:String}")
    params = {"at": datetime.combine(old, time(12)), "p": f"%{tenant}%"}
    partitioned_by_tenant = client.query(f"SELECT count() FROM system.parts WHERE {where}",
                                         parameters=params).result_rows[0][0] > 0
    if not partitioned_by_tenant:  # partitioned by month only (migration 011): find the month's parts
        params["p"] = "%"
    disks = {r[0] for r in client.query(f"SELECT DISTINCT disk_name FROM system.parts WHERE {where}",
                                        parameters=params).result_rows}
    assert disks == {"s3_warm"}
    n = client.query("SELECT count(), max(msg) FROM logs_raw_mt WHERE customer_id = {t:String}",
                     parameters={"t": tenant}).result_rows[0]
    assert n[0] == 20 and n[1].startswith("event")
    client.command("ALTER TABLE logs_raw_mt DELETE WHERE customer_id = {t:String} SETTINGS mutations_sync = 2",
                   parameters={"t": tenant})


def test_retention_archives_verifies_deletes_and_expires(stack):
    client, mgr, st, tm = stack
    mgr.ensure_tables()
    tenant = f"tiers-{uuid.uuid4().hex[:8]}"
    today = date.today()
    old, recent = today - timedelta(days=35), today - timedelta(days=10)
    client.insert("logs_raw_mt", _rows(tenant, old, 5) + _rows(tenant, recent, 3), column_names=COLUMNS)
    mgr.set_policy(tenant, st.Policy("logs", 30, 365), "test")
    assert mgr.policies(tenant)["logs"] == st.Policy("logs", 30, 365)

    report = mgr.run(today, tenants=[tenant])
    assert report["errors"] == []
    assert report["archived"] == 1 and report["archived_rows"] == 5
    assert report["deleted_days"] == 1 and report["deleted_rows"] == 5
    left = client.query("SELECT toDate(ts), count() FROM logs_raw_mt WHERE customer_id = {t:String} GROUP BY 1",
                        parameters={"t": tenant}).result_rows
    assert left == [(recent, 3)]

    key = st.archive_key(tenant, "logs", old)
    back = client.query(f"SELECT count(), any(msg), any(customer_id) FROM s3({tm.ARCHIVE_COLLECTION}, "
                        f"filename = '{key}', format = 'Parquet')").result_rows[0]
    assert back[0] == 5 and back[1].startswith("event") and back[2] == tenant
    assert mgr.archived("logs", tenant)[tenant][old][0] == 5
    assert mgr.objects.size(key) > 0

    # a year on: the archive of `old` expires (and `recent` is archived, then deleted)
    later = old + timedelta(days=365)
    report = mgr.run(later, tenants=[tenant])
    assert report["errors"] == []
    assert report["expired"] >= 1
    assert old not in mgr.archived("logs", tenant).get(tenant, {})
    with pytest.raises(Exception):
        mgr.objects.size(key)
    # clean up the rest
    for day in list(mgr.archived("logs", tenant).get(tenant, {})):
        mgr.objects.delete(st.archive_key(tenant, "logs", day))
    client.command("ALTER TABLE logs_raw_mt DELETE WHERE customer_id = {t:String} SETTINGS mutations_sync = 2",
                   parameters={"t": tenant})


def test_archive_search_and_rehydration(stack):
    client, mgr, st, tm = stack
    import archive_query
    from logql_pipeline import execute

    mgr.ensure_tables()
    tenant = f"tiers-rh-{uuid.uuid4().hex[:8]}"
    today = date.today()
    old = today - timedelta(days=40)
    client.insert("logs_raw_mt", _rows(tenant, old, 6), column_names=COLUMNS)
    mgr.set_policy(tenant, st.Policy("logs", 30, 365), "test")
    assert mgr.run(today, tenants=[tenant])["deleted_days"] == 1

    # searched in place: the same language, over the Parquet file
    start = datetime.combine(old, time(0), tzinfo=timezone.utc)
    end = start + timedelta(days=2)
    days = archive_query.days_in(mgr.archived("logs", tenant)[tenant], start, end)
    assert days == [old]
    compiled = archive_query.compile_archive('| where service = "api" | stats count() AS n, dc(msg) AS m',
                                             tenant, days, start, end)
    result = execute(client, compiled, {"readonly": 2})
    assert result["rows"][0]["n"] == 6 and result["rows"][0]["m"] == 6
    other = archive_query.compile_archive("*", "someone-else", days, start, end)
    assert "'someone-else/logs/" in other.sql and tenant not in other.sql  # only its own prefix is read

    # rehydrated: back in ClickHouse, without touching the entity counts
    def entity_events():
        return client.query("SELECT sum(events) FROM entities_mt WHERE customer_id = {t:String}",
                            parameters={"t": tenant}).result_rows[0][0]

    before = entity_events()
    out = mgr.rehydrate(tenant, "logs", old, old, keep_days=3, user_id="test", today=today)
    assert out["errors"] == [] and out["rehydrated_days"] == 1 and out["rows"] == 6
    n = client.query("SELECT count() FROM logs_raw_mt WHERE customer_id = {t:String}",
                     parameters={"t": tenant}).result_rows[0][0]
    assert n == 6
    assert entity_events() == before
    assert mgr.rehydrate(tenant, "logs", old, old, keep_days=3, user_id="test",
                         today=today)["skipped"][0]["reason"] == "still in ClickHouse"

    # the job keeps it while held, deletes it again after
    assert mgr.run(today, tenants=[tenant])["deleted_days"] == 0
    assert mgr.run(today + timedelta(days=4), tenants=[tenant])["deleted_days"] == 1

    for day in mgr.archived("logs", tenant).get(tenant, {}):
        mgr.objects.delete(st.archive_key(tenant, "logs", day))
    client.command("ALTER TABLE logs_raw_mt DELETE WHERE customer_id = {t:String} SETTINGS mutations_sync = 2",
                   parameters={"t": tenant})


def test_cost_report(stack):
    client, mgr, st, tm = stack
    import storage_costs

    tenant = f"tiers-cost-{uuid.uuid4().hex[:8]}"
    today = date.today()
    rows = []
    for back in range(1, 9):
        day = today - timedelta(days=back)
        at = datetime.combine(day, time(9), tzinfo=timezone.utc)
        for i in range(60):  # 60 debug lines from checkout, 20 info from auth, per day
            rows.append([at + timedelta(seconds=i), "h1", "checkout", "debug", f"cart {i} recalculated", "", "", "{}",
                         0, "", "", at, 7, 16, "v1", tenant])
        for i in range(20):
            rows.append([at + timedelta(seconds=i), "h1", "auth", "info", f"login ok u{i}", "", "", "{}", 0, "", "",
                         at, 6, 16, "v1", tenant])
    client.insert("logs_raw_mt", rows, column_names=COLUMNS)
    out = storage_costs.report(client, mgr.cfg, mgr.policies(tenant), tenant, today)
    assert out["ingest"]["events"] == 8 * 80
    assert out["ingest"]["by_source"][0]["service"] == "checkout"
    assert out["ingest"]["by_source"][0]["levels"] == {"debug": 480}
    assert out["noise"][0]["service"] == "checkout" and out["noise"][0]["drop_step"]["if"] == "level == 'debug'"
    logs = out["storage"][0]
    assert logs["data_type"] == "logs" and logs["hot"]["rows"] + logs["warm"]["rows"] == 640
    assert logs["bytes_per_row"] > 0
    assert out["projection"]["daily_events"] == 80 and out["projection"]["days_used"] == 7
    steady = out["projection"]["steady_state"]
    assert steady["hot"]["days"] == mgr.cfg.hot_days and steady["monthly_cost"]["total"] > 0
    client.command("ALTER TABLE logs_raw_mt DELETE WHERE customer_id = {t:String} SETTINGS mutations_sync = 2",
                   parameters={"t": tenant})
