"""
Case storage (Phase 2, migration 017).

cases_mt is a ReplacingMergeTree keyed by (tenant_id, id): each save writes a
new row version and reads use FINAL. case_events_mt is append-only: the case
timeline and audit trail. Every query is tenant-scoped and parameterised.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

from cases import new_case
from dao.case_dao import CaseDAO

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls = []

    async def fetch_all(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self.rows

    async def execute_update(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return True


def dao(rows=None):
    instance = CaseDAO.__new__(CaseDAO)
    instance.db = FakeDB(rows)
    return instance


def run(coro):
    return asyncio.run(coro)


def sample():
    return new_case("acme", "Brute force", "alice", T0, alerts=[
        {"id": "a1", "severity": "high", "entities": {"src_ip": ["203.0.113.9"]}}])


def test_save_writes_a_new_version_with_millisecond_times():
    case, _ = sample()
    d = dao()
    run(d.save(case))
    sql, params = d.db.calls[0]
    assert sql.startswith("INSERT INTO cases_mt")
    assert params["tenant_id"] == "acme" and params["id"] == case.id
    assert params["created_at"] == "2026-11-18 09:00:00.000"
    assert params["acknowledged_at"] is None
    assert json.loads(params["entities"]) == {"src_ip": ["203.0.113.9"]}
    assert params["alert_ids"] == ["a1"] and isinstance(params["version"], int)
    run(d.save(case))
    assert d.db.calls[1][1]["version"] > params["version"]


def test_events_are_appended_with_json_data():
    _, events = sample()
    d = dao()
    run(d.append_events(events))
    assert len(d.db.calls) == 1
    sql, params = d.db.calls[0]
    assert sql.startswith("INSERT INTO case_events_mt")
    # one multi-row INSERT with numbered parameters
    assert params["kind_0"] == "created" and json.loads(params["data_0"])["title"] == "Brute force"
    assert params["kind_1"] == "alert_attached" and params["ts_0"] == "2026-11-18 09:00:00.000"
    # events of one action share a timestamp; seq keeps their order
    assert (params["seq_0"], params["seq_1"]) == (0, 1)


def test_get_reads_the_latest_version_for_the_tenant():
    case, _ = sample()
    d = dao([case.to_row() | {"created_at": T0, "updated_at": T0}])
    loaded = run(d.get("acme", case.id))
    sql, params = d.db.calls[0]
    assert "FROM cases_mt FINAL" in sql and "tenant_id = %(tenant_id)s AND id = %(id)s" in sql
    assert loaded.id == case.id and loaded.entities == {"src_ip": ["203.0.113.9"]}
    assert run(dao([]).get("acme", "nope")) is None


def test_list_filters_and_pages():
    d = dao([])
    d.db.rows = []
    run(d.list("acme", status=["new", "investigating"], assignee="bob", severity="high", q="brute",
               limit=20, offset=40))
    sql, params = d.db.calls[0]
    assert "status IN %(status)s" in sql and "assignee = %(assignee)s" in sql and "severity = %(severity)s" in sql
    assert "positionCaseInsensitiveUTF8(title, %(q)s) > 0" in sql
    assert "LIMIT %(limit)s OFFSET %(offset)s" in sql
    assert params["status"] == ["new", "investigating"] and params["limit"] == 20 and params["offset"] == 40
    assert "count() AS total" in d.db.calls[1][0]


def test_find_open_case_for_a_group_key():
    d = dao([])
    run(d.find_open_by_group_key("acme", "src_ip=203.0.113.9", T0 - timedelta(hours=24)))
    sql, params = d.db.calls[0]
    assert "group_key = %(group_key)s" in sql and "status NOT IN ('resolved', 'false_positive')" in sql
    assert "last_alert_at >= %(since)s" in sql and "ORDER BY last_alert_at DESC LIMIT 1" in sql


def test_timeline_is_ordered_and_decoded():
    rows = [{"id": "e1", "case_id": "c1", "ts": T0, "seq": 0, "actor": "alice", "kind": "comment",
             "data": '{"text": "hi", "mentions": []}'}]
    d = dao(rows)
    events = run(d.events("acme", "c1"))
    assert "ORDER BY ts, seq" in d.db.calls[0][0]
    assert events[0]["data"] == {"text": "hi", "mentions": []} and events[0]["ts"] == T0.isoformat()


def test_audit_export_reads_a_time_range():
    d = dao([])
    run(d.events_between("acme", T0, T0 + timedelta(days=1), limit=1000))
    sql, params = d.db.calls[0]
    assert "FROM case_events_mt WHERE tenant_id = %(tenant_id)s AND ts >= %(start)s AND ts < %(end)s" in sql
    assert params["start"] == "2026-11-18 09:00:00.000" and params["limit"] == 1000
