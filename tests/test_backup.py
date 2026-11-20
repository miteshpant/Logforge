"""
Backup and restore (Phase 12): ClickHouse BACKUP/RESTORE to the s3_backups
disk, with a manifest of each table's rows to verify a restore against.
tests/test_backup_live.py runs it against the real stack.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import backup  # noqa: E402


class Result:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    def __init__(self, tables=None, counts=None, final=None, visible=None):
        self.final = final or {}
        self.visible = visible or {}
        self.tables = tables or [("logs_raw_mt", "MergeTree"), ("entities_mv", "MaterializedView"),
                                 ("saved_searches_mt", "ReplacingMergeTree")]
        self.counts = counts or {"logs_raw_mt": 10, "saved_searches_mt": 2}
        self.statements = []

    def query(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        if "system.tables" in sql:
            return Result([(n, e, self.counts.get(n, 0)) for n, e in self.tables])
        if sql.startswith("SELECT count() FROM"):
            table = sql.split("FROM ")[1].split()[0].split(".")[-1].strip("`")
            if "FINAL" in sql:
                return Result([(self.final.get(table, self.counts.get(table, 0)),)])
            return Result([(self.visible.get(table, self.counts.get(table, 0)),)])
        if "system.databases" in sql:
            return Result([(0,)])
        if "system.backups" in sql:
            return Result([("BACKUP_CREATED", "", 123, 456)])
        raise AssertionError(sql)

    def command(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        return "id\tBACKUP_CREATED"


class FakeObjects:
    def __init__(self):
        self.store = {}

    def put_json(self, key, data):
        self.store[key] = data

    def get_json(self, key):
        return self.store[key]

    def keys(self, prefix=""):
        return sorted(k for k in self.store if k.startswith(prefix))


def test_names_are_safe_and_dated():
    assert backup.name_for(datetime(2026, 11, 20, 3, 4, 5, tzinfo=timezone.utc)) == "logforge-20261120-030405"
    for bad in ("../x", "a b", "x'y", ""):
        with pytest.raises(backup.BackupError):
            backup.check_name(bad)


def test_create_backs_up_the_database_and_writes_a_manifest():
    client, objects = FakeClient(), FakeObjects()
    out = backup.create(client, objects, "logforge", "b1", now=datetime(2026, 11, 20, tzinfo=timezone.utc))
    sql = [s for s, _ in client.statements if s.startswith("BACKUP")][0]
    assert sql == "BACKUP DATABASE logforge TO S3(logforge_backups, 'b1')"
    manifest = objects.get_json("b1.manifest.json")
    assert manifest["tables"] == {"logs_raw_mt": 10, "saved_searches_mt": 2}  # views hold no rows of their own
    assert manifest["database"] == "logforge" and manifest["base"] is None
    assert out["name"] == "b1" and out["status"] == "BACKUP_CREATED"


def test_incremental_backup_names_its_base():
    client, objects = FakeClient(), FakeObjects()
    objects.put_json("b0.manifest.json", {"database": "logforge", "tables": {}})
    backup.create(client, objects, "logforge", "b1", base="b0")
    sql = [s for s, _ in client.statements if s.startswith("BACKUP")][0]
    assert sql.endswith("SETTINGS base_backup = S3(logforge_backups, 'b0')")
    with pytest.raises(backup.BackupError, match="no backup"):
        backup.create(client, objects, "logforge", "b2", base="missing")


def test_restore_to_another_database_and_verify():
    client, objects = FakeClient(), FakeObjects()
    objects.put_json("b1.manifest.json", {"database": "logforge", "tables": {"logs_raw_mt": 10,
                                                                             "saved_searches_mt": 2}})
    backup.restore(client, objects, "b1", as_database="logforge_restored")
    sql = [s for s, _ in client.statements if s.startswith("RESTORE")][0]
    assert sql == "RESTORE DATABASE logforge AS logforge_restored FROM S3(logforge_backups, 'b1')"
    report = backup.verify(FakeClient(counts={"logs_raw_mt": 10, "saved_searches_mt": 1}), objects, "b1",
                           "logforge_restored")
    assert report["ok"] is False
    assert report["mismatches"] == [{"table": "saved_searches_mt", "backed_up": 2, "restored": 1}]
    assert backup.verify(FakeClient(), objects, "b1", "logforge_restored")["ok"] is True


def test_restore_refuses_to_overwrite_an_existing_database_by_default():
    client, objects = FakeClient(), FakeObjects()
    objects.put_json("b1.manifest.json", {"database": "logforge", "tables": {}})
    with pytest.raises(backup.BackupError, match="exists"):
        backup.restore(client, objects, "b1", exists=lambda db: True)


def test_list_backups_from_manifests():
    objects = FakeObjects()
    objects.put_json("b1.manifest.json", {"name": "b1", "created_at": "2026-11-19T00:00:00+00:00", "tables": {"a": 1}})
    objects.put_json("b2.manifest.json", {"name": "b2", "created_at": "2026-11-20T00:00:00+00:00", "tables": {"a": 2}})
    assert [b["name"] for b in backup.list_backups(objects)] == ["b2", "b1"]


def test_collapsing_engines_are_counted_as_queries_see_them():
    """Replacing, Summing and Aggregating tables lose duplicate rows as they
    merge, so their raw part rows shrink after a restore without any loss:
    they are counted with FINAL, the rows a query sees."""
    client = FakeClient(counts={"logs_raw_mt": 10, "saved_searches_mt": 7}, final={"saved_searches_mt": 2})
    counts = backup._counts(client, "logforge")
    assert counts == {"logs_raw_mt": 10, "saved_searches_mt": 2}
    finals = [s for s, _ in client.statements if "FINAL" in s]
    assert finals == ["SELECT count() FROM logforge.`saved_searches_mt` FINAL"]


def test_rows_are_counted_as_queries_see_them_not_from_table_metadata():
    """Deleted rows stay in system.tables.total_rows until merged away, so the
    manifest overstated tables with deletions (users' sessions and roles)."""
    client = FakeClient(counts={"logs_raw_mt": 10, "saved_searches_mt": 2}, visible={"logs_raw_mt": 8})
    assert backup._counts(client, "logforge")["logs_raw_mt"] == 8
