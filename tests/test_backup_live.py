"""
Backup and restore against the real stack (Phase 12): ClickHouse with the
logforge_backups named collection (compose mounts infra/docker/clickhouse/config.d/s3_storage.xml)
and MinIO.

Always: a scratch database (events, configuration, a materialized view)
is backed up, dropped, restored and verified, then extended and backed up
incrementally. With LOGFORGE_BACKUP_FULL=1 (CI, where the database is
small) the whole logforge database is backed up and restored into a new
database and verified table by table.

    LOGFORGE_TEST_CLICKHOUSE=localhost:8124 pytest tests/test_backup_live.py
"""

import os
import sys
import uuid

import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "apps", "api"), os.path.dirname(__file__)]

from test_logql_pipeline_live import _client  # noqa: E402


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
    import backup

    objects = backup.S3Manifests()
    try:
        from tier_manager import S3Objects

        S3Objects(objects.bucket).ensure_buckets(objects.bucket)
    except Exception as e:
        if os.getenv("LOGFORGE_REQUIRE_CLICKHOUSE"):
            raise
        pytest.skip(f"object storage is not reachable: {e}")
    return client, objects, backup


def _drop(client, *databases):
    for db in databases:
        client.command(f"DROP DATABASE IF EXISTS {db} SYNC")


def test_backup_drop_restore_and_incremental(stack):
    client, objects, backup = stack
    tag = uuid.uuid4().hex[:8]
    db, again = f"lf_bk_{tag}", f"lf_bk_{tag}_inc"
    try:
        client.command(f"CREATE DATABASE {db}")
        client.command(f"CREATE TABLE {db}.events (customer_id String, ts DateTime, msg String) "
                       "ENGINE = MergeTree ORDER BY (customer_id, ts)")
        client.command(f"CREATE TABLE {db}.settings (customer_id String, k String, v String, at DateTime) "
                       "ENGINE = ReplacingMergeTree(at) ORDER BY (customer_id, k)")
        client.command(f"CREATE TABLE {db}.per_tenant (customer_id String, n UInt64) "
                       "ENGINE = SummingMergeTree ORDER BY customer_id")
        client.command(f"CREATE MATERIALIZED VIEW {db}.per_tenant_mv TO {db}.per_tenant AS "
                       f"SELECT customer_id, count() AS n FROM {db}.events GROUP BY customer_id")
        client.command(f"INSERT INTO {db}.events SELECT toString(number % 3), now() - number, "
                       f"concat('event ', toString(number)) FROM numbers(5000)")
        client.command(f"INSERT INTO {db}.settings VALUES ('0', 'retention', '30', now()), ('1', 'retention', '90', now())")

        full = backup.create(client, objects, db, f"{db}-full")
        assert full["status"] == "BACKUP_CREATED"
        assert full["tables"]["events"] == 5000 and full["tables"]["settings"] == 2
        assert "per_tenant_mv" not in full["tables"]
        # the backup is <bucket>/<name>/..., restorable by a new server
        assert f"{db}-full/.backup" in objects.keys(prefix=f"{db}-full/")

        _drop(client, db)
        with pytest.raises(backup.BackupError, match="exists"):
            client.command(f"CREATE DATABASE {db}")
            backup.restore(client, objects, f"{db}-full")
        _drop(client, db)
        out = backup.restore(client, objects, f"{db}-full")
        assert out["status"] == "RESTORED"
        report = backup.verify(client, objects, f"{db}-full")
        assert report["ok"], report
        assert client.query(f"SELECT sum(n) FROM {db}.per_tenant").result_rows[0][0] == 5000
        # the view works again after the restore
        client.command(f"INSERT INTO {db}.events VALUES ('0', now(), 'after restore')")
        assert client.query(f"SELECT sum(n) FROM {db}.per_tenant").result_rows[0][0] == 5001

        inc = backup.create(client, objects, db, f"{db}-inc", base=f"{db}-full")
        assert inc["base"] == f"{db}-full" and inc["tables"]["events"] == 5001
        backup.restore(client, objects, f"{db}-inc", as_database=again)
        assert backup.verify(client, objects, f"{db}-inc", again)["ok"]
        names = [b["name"] for b in backup.list_backups(objects)]
        assert f"{db}-inc" in names and f"{db}-full" in names
    finally:
        _drop(client, db, again)


@pytest.mark.skipif(not os.getenv("LOGFORGE_BACKUP_FULL"), reason="set LOGFORGE_BACKUP_FULL=1 (CI) to back up "
                                                                   "the whole logforge database")
def test_the_whole_logforge_database_round_trips(stack):
    client, objects, backup = stack
    name = f"ci-{uuid.uuid4().hex[:8]}"
    target = f"lf_restored_{uuid.uuid4().hex[:8]}"
    try:
        made = backup.create(client, objects, "logforge", name)
        assert made["status"] == "BACKUP_CREATED" and len(made["tables"]) > 50
        backup.restore(client, objects, name, as_database=target)
        report = backup.verify(client, objects, name, target)
        assert report["ok"], report["mismatches"]
    finally:
        _drop(client, target)
