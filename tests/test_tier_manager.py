"""
TierManager (Phase 12): carries out the storage tier plan against ClickHouse
and object storage. These tests use a fake ClickHouse client that records
statements; tests/test_storage_tiers_live.py runs it against the real stack.
"""

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import storage_tiers as st  # noqa: E402
import tier_manager as tm  # noqa: E402

TODAY = date(2026, 11, 20)


def d(n):
    return date.fromordinal(TODAY.toordinal() - n)


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Answers the few queries TierManager makes; records every statement."""

    def __init__(self, policies=("default", "tiered"), table_policy="default", days=None, file_rows=None,
                 manifest=None, stored=None, held=None):
        self.policies = policies
        self.table_policy = table_policy
        self.days = days or {}          # (tenant, type) -> {day: rows}
        self.file_rows = file_rows or {}  # object key -> rows read back
        self.manifest = manifest or {}  # (tenant, type) -> {day: rows}
        self.stored = stored or []      # (tenant, type, searchable, archive)
        self.held = held or {}          # (tenant, type) -> {rehydrated days}
        self.statements = []

    def query(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        if "system.storage_policies" in sql:
            return FakeResult([(p,) for p in self.policies])
        if "system.tables" in sql:
            return FakeResult([(self.table_policy,)])
        if "system.columns" in sql:
            return FakeResult([("ts",), ("customer_id",), ("msg",)])
        if "FROM tenant_retention_mt" in sql:
            return FakeResult(list(self.stored))
        if "FROM rehydrations_mt" in sql:
            return FakeResult([(t, day) for (t, dtype), days in self.held.items() if dtype == parameters["type"]
                               for day in days])
        if "FROM archive_manifest_mt" in sql:
            rows = []
            for (tenant, dtype), days in self.manifest.items():
                if dtype == parameters["type"]:
                    rows += [(tenant, day, n, st.archive_key(tenant, dtype, day)) for day, n in days.items()]
            return FakeResult(rows)
        if "FROM s3(" in sql:
            key = re.search(r"filename = '([^']+)'", sql).group(1)
            return FakeResult([(self.file_rows.get(key, 0),)])
        if "GROUP BY customer_id, day" in sql:
            rows = []
            for (tenant, dtype), days in self.days.items():
                if f"FROM {CFG.data_types[dtype].table} " in sql:
                    rows += [(tenant, day, n) for day, n in days.items()]
            return FakeResult(rows)
        raise AssertionError(f"unexpected query {sql}")

    def command(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        return None

    def commands(self, word):
        return [s for s, _ in self.statements if s.lstrip().startswith(word)]


class FakeObjects:
    def __init__(self):
        self.deleted = []

    def size(self, key):
        return 1234

    def delete(self, key):
        self.deleted.append(key)


CFG = st.load_config()


def test_ensure_warm_moves_tables_to_the_tiered_policy_and_sets_ttl_without_rewriting_parts():
    client = FakeClient()
    status = tm.TierManager(client, FakeObjects(), CFG).ensure_tables()
    assert status["warm"] is True
    alters = client.commands("ALTER TABLE")
    assert any("logs_raw_mt MODIFY SETTING storage_policy = 'tiered'" in a for a in alters)
    ttl = [a for a in alters if "logs_raw_mt MODIFY TTL" in a][0]
    assert "TO VOLUME 'warm'" in ttl
    assert "materialize_ttl_after_modify = 0" in ttl  # no rewrite of existing parts
    assert {t["table"] for t in status["tables"]} == {"logs_raw_mt", "security_events_mt", "traces_mt", "metrics_mt"}


def test_ensure_without_object_storage_sets_only_the_delete_backstop():
    client = FakeClient(policies=("default",))
    status = tm.TierManager(client, FakeObjects(), CFG).ensure_tables()
    assert status["warm"] is False
    alters = client.commands("ALTER TABLE")
    assert not any("storage_policy" in a for a in alters)
    assert all("TO VOLUME" not in a for a in alters)
    assert any(f"toIntervalDay({CFG.max_searchable_days}) DELETE" in a for a in alters)


def test_table_already_on_the_tiered_policy_is_not_switched_again():
    client = FakeClient(table_policy="tiered")
    tm.TierManager(client, FakeObjects(), CFG).ensure_tables()
    assert not any("storage_policy" in a for a in client.commands("ALTER TABLE"))


def test_run_archives_verifies_and_deletes_in_one_pass():
    key = st.archive_key("t1", "logs", d(31))
    client = FakeClient(days={("t1", "logs"): {d(31): 7}}, file_rows={key: 7})
    report = tm.TierManager(client, FakeObjects(), CFG).run(TODAY)
    inserts = client.commands("INSERT INTO FUNCTION s3")
    assert len(inserts) == 1 and f"filename = '{key}'" in inserts[0] and "Parquet" in inserts[0]
    assert "s3_truncate_on_insert = 1" in inserts[0]
    manifest = [s for s in client.commands("INSERT INTO archive_manifest_mt")]
    assert manifest
    deletes = client.commands("ALTER TABLE logs_raw_mt DELETE")
    assert len(deletes) == 1
    assert report["archived"] == 1 and report["deleted_days"] == 1 and report["errors"] == []


def test_run_does_not_delete_when_the_archive_reads_back_short():
    key = st.archive_key("t1", "logs", d(31))
    client = FakeClient(days={("t1", "logs"): {d(31): 7}}, file_rows={key: 6})
    report = tm.TierManager(client, FakeObjects(), CFG).run(TODAY)
    assert client.commands("ALTER TABLE logs_raw_mt DELETE") == []
    assert report["deleted_days"] == 0
    assert report["errors"] and "6 of 7" in report["errors"][0]


def test_run_honours_each_tenants_policy():
    client = FakeClient(days={("t1", "logs"): {d(20): 5}, ("t2", "logs"): {d(20): 5}},
                        stored=[("t1", "logs", 14, 0)])
    tm.TierManager(client, FakeObjects(), CFG).run(TODAY)
    deletes = client.statements
    deleted = [p for s, p in deletes if s.startswith("ALTER TABLE logs_raw_mt DELETE")]
    assert [p["tenant"] for p in deleted] == ["t1"]  # t2 keeps the default 30 days


def test_run_expires_old_archives():
    objects = FakeObjects()
    client = FakeClient(manifest={("t1", "logs"): {d(400): 3}})
    report = tm.TierManager(client, objects, CFG).run(TODAY)
    assert objects.deleted == [st.archive_key("t1", "logs", d(400))]
    assert report["expired"] == 1
    assert any("'expired'" in s or (p or {}).get("status") == "expired"
               for s, p in client.statements if "archive_manifest_mt" in s and s.startswith("INSERT"))


def test_policies_api_helpers_round_trip():
    client = FakeClient(stored=[("t1", "logs", 14, 730)])
    mgr = tm.TierManager(client, FakeObjects(), CFG)
    policies = mgr.policies("t1")
    assert policies["logs"] == st.Policy("logs", 14, 730)
    assert policies["security"] == CFG.defaults["security"]
    mgr.set_policy("t1", st.Policy("traces", 7, 0), "u1")
    inserted = [p for s, p in client.statements if s.startswith("INSERT INTO tenant_retention_mt")]
    assert inserted and inserted[0]["type"] == "traces" and inserted[0]["searchable"] == 7


def test_run_can_be_limited_to_some_tenants():
    client = FakeClient(days={("t1", "logs"): {d(40): 5}, ("t2", "logs"): {d(40): 5}},
                        stored=[("t1", "logs", 30, 0), ("t2", "logs", 30, 0)])
    tm.TierManager(client, FakeObjects(), CFG).run(TODAY, tenants=["t2"])
    deleted = [p["tenant"] for s, p in client.statements if s.startswith("ALTER TABLE logs_raw_mt DELETE")]
    assert deleted == ["t2"]


def test_run_leaves_rehydrated_days_alone():
    client = FakeClient(days={("t1", "logs"): {d(100): 5}}, manifest={("t1", "logs"): {d(100): 5}},
                        held={("t1", "logs"): {d(100)}})
    report = tm.TierManager(client, FakeObjects(), CFG).run(TODAY)
    assert client.commands("ALTER TABLE logs_raw_mt DELETE") == []
    assert report["deleted_days"] == 0
