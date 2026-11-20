"""
Archive search and rehydration (Phase 12): LogforgeQL over a tenant's Parquet
archives, and copying archived days back into ClickHouse for a while.
"""

import os
import sys
from datetime import date, datetime, timezone

import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "apps", "api"), os.path.dirname(__file__)]

import archive_query as aq  # noqa: E402
import storage_tiers as st  # noqa: E402
from test_tier_manager import CFG, FakeClient, FakeObjects  # noqa: E402

TODAY = date(2026, 11, 20)


def d(n):
    return date.fromordinal(TODAY.toordinal() - n)


def test_source_reads_exactly_the_archived_days():
    one = aq.source("t1", "logs", [date(2026, 1, 2)])
    assert one == "s3(logforge_archive, filename = 't1/logs/2026/01/02.parquet', format = 'Parquet')"
    two = aq.source("t1", "logs", [date(2026, 1, 3), date(2026, 1, 2)])
    assert "filename = 't1/logs/{2026/01/02,2026/01/03}.parquet'" in two
    with pytest.raises(st.PolicyError):
        aq.source("t'1", "logs", [date(2026, 1, 2)])
    with pytest.raises(ValueError):
        aq.source("t1", "logs", [])


def test_days_in_window():
    archived = {date(2026, 1, 1): 1, date(2026, 1, 5): 1, date(2026, 2, 1): 1}
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    end = datetime(2026, 1, 31, tzinfo=timezone.utc)
    assert aq.days_in(archived, start, end) == [date(2026, 1, 1), date(2026, 1, 5)]


def test_compile_over_archives_keeps_the_tenant_filter_and_skips_the_rollup():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 3, tzinfo=timezone.utc)
    compiled = aq.compile_archive("error | stats count() by service", "t1", [date(2026, 1, 2)], start, end)
    assert "FROM s3(logforge_archive, filename = 't1/logs/2026/01/02.parquet'" in compiled.sql
    assert "customer_id = " in compiled.sql and "t1" in compiled.params.values()
    assert compiled.rollup is False


def test_plan_keeps_rehydrated_days_until_their_hold_ends():
    policy = st.Policy("logs", 30, 365)
    actions = st.plan(policy, TODAY, {d(100): 5}, {d(100): 5}, held={d(100)})
    assert actions == []
    actions = st.plan(policy, TODAY, {d(100): 5}, {d(100): 5}, held=set())
    assert [(a.kind, a.day) for a in actions] == [("delete", d(100))]


class RehydrateClient(FakeClient):
    def __init__(self, present, file_rows, **kw):
        super().__init__(**kw)
        self.present = present  # days the tenant still has in ClickHouse
        self.file_rows = file_rows

    def query(self, sql, parameters=None):
        if "toDate(" in sql and "IN {days:Array(Date)}" in sql:
            self.statements.append((sql, parameters))
            return type(self).result([(day, 1) for day in self.present])
        if "system.parts" in sql:
            self.statements.append((sql, parameters))
            return type(self).result([("p1",)])
        if sql.startswith("SELECT count() FROM logs_raw_mt"):
            self.statements.append((sql, parameters))
            return type(self).result([(self.file_rows[parameters["day"]],)])
        return super().query(sql, parameters)

    @staticmethod
    def result(rows):
        from test_tier_manager import FakeResult

        return FakeResult(rows)


def test_rehydrate_copies_archived_days_back_and_holds_them():
    import tier_manager as tm

    manifest = {("t1", "logs"): {d(100): 5, d(101): 4, d(102): 3}}
    client = RehydrateClient(present=[d(101)], file_rows={d(100).isoformat(): 5, d(102).isoformat(): 3},
                             manifest=manifest)
    mgr = tm.TierManager(client, FakeObjects(), CFG)
    out = mgr.rehydrate("t1", "logs", d(102), d(100), keep_days=7, user_id="u1", today=TODAY)
    # loaded into a staging copy, then attached: attaching doesn't fire the
    # materialized views, so entity counts aren't inflated by a rehydration
    inserts = [s for s, _ in client.statements if s.startswith("INSERT INTO _rehydrate_")]
    assert len(inserts) == 2 and all("FROM s3(logforge_archive" in s for s in inserts)
    assert not [s for s, _ in client.statements if s.startswith("INSERT INTO logs_raw_mt")]
    commands = [s for s, _ in client.statements]
    assert any(s.startswith("CREATE TABLE _rehydrate_") and "AS logs_raw_mt" in s for s in commands)
    assert any("ATTACH PARTITION ID 'p1' FROM _rehydrate_" in s for s in commands)
    assert any(s.startswith("DROP TABLE IF EXISTS _rehydrate_") for s in commands)
    assert out["rehydrated_days"] == 2 and out["rows"] == 8
    assert out["skipped"] == [{"day": d(101).isoformat(), "reason": "still in ClickHouse"}]
    holds = [p for s, p in client.statements if s.startswith("INSERT INTO rehydrations_mt")]
    assert {p["day"] for p in holds} == {d(100).isoformat(), d(102).isoformat()}
    assert all(p["until"] == date.fromordinal(TODAY.toordinal() + 7).isoformat() for p in holds)


def test_rehydrate_limits():
    import tier_manager as tm

    mgr = tm.TierManager(FakeClient(), FakeObjects(), CFG)
    with pytest.raises(st.PolicyError, match="keep"):
        mgr.rehydrate("t1", "logs", d(10), d(5), keep_days=0, user_id="u", today=TODAY)
    with pytest.raises(st.PolicyError, match="keep"):
        mgr.rehydrate("t1", "logs", d(10), d(5), keep_days=tm.MAX_REHYDRATE_KEEP_DAYS + 1, user_id="u", today=TODAY)
    with pytest.raises(st.PolicyError, match="days"):
        mgr.rehydrate("t1", "logs", d(100), d(5), keep_days=3, user_id="u", today=TODAY)
    with pytest.raises(st.PolicyError, match="before"):
        mgr.rehydrate("t1", "logs", d(5), d(10), keep_days=3, user_id="u", today=TODAY)


def test_archive_queries_may_span_a_year_but_event_queries_keep_their_limit():
    from datetime import timedelta

    from fastapi import HTTPException

    from routers.query import logql_window

    body = {"start_time": "2025-12-01T00:00:00Z", "end_time": "2026-11-01T00:00:00Z"}
    start, end = logql_window({}, body, max_window=timedelta(days=aq.MAX_WINDOW_DAYS))
    assert (end - start).days == 335
    with pytest.raises(HTTPException) as err:
        logql_window({}, body)
    assert "LOGFORGE_MAX_QUERY_WINDOW_DAYS" in err.value.detail
    with pytest.raises(HTTPException) as err:
        logql_window({}, {"start_time": "2024-01-01T00:00:00Z", "end_time": "2026-01-01T00:00:00Z"},
                     max_window=timedelta(days=aq.MAX_WINDOW_DAYS))
    assert "LOGFORGE_MAX_ARCHIVE_WINDOW_DAYS" in err.value.detail
