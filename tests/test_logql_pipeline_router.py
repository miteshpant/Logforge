"""
POST /v1/query/logql runs pipeline queries (Phase 6) through the pipeline
compiler, and every other query exactly as before.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import routers.query as qr


class FakeClient:
    def __init__(self, names=("service", "count"), rows=(("api", 3),)):
        self.calls = []
        self.names, self.rows = list(names), [list(r) for r in rows]

    def query(self, sql, parameters=None, settings=None):
        self.calls.append((sql, parameters, settings))
        return SimpleNamespace(column_names=self.names, result_rows=self.rows)


class FakeEngine:
    def __init__(self, client):
        self.client = client
        self.v1_requests = []

    async def execute_query(self, request):
        self.v1_requests.append(request)
        from models import QueryResponse
        return QueryResponse(logs=[], aggregations={}, total_count=0)


@pytest.fixture
def engine(monkeypatch):
    import query_cost

    async def no_tier(tenant_id):
        return None

    fake = FakeEngine(FakeClient())
    monkeypatch.setattr(qr, "query_engine", fake)
    monkeypatch.setattr(query_cost, "tier_for", no_tier)
    return fake


def run_calls(client):
    """The executed statements (not the EXPLAIN ESTIMATE run first)."""
    return [c for c in client.calls if not c[0].startswith("EXPLAIN")]


def call(body, tenant="acme"):
    return asyncio.run(qr.logql_query(body, customer_id=tenant))


def test_pipeline_queries_use_the_pipeline_compiler(engine):
    response = call({"query": "| stats count() by service | sort -count | last 7d"})
    assert response["result_type"] == "table" and response["columns"] == ["service", "count"]
    assert response["logs"] == [{"service": "api", "count": 3}] and response["total_count"] == 1
    sql, params, settings = run_calls(engine.client)[0]
    assert "acme" in params.values() and "acme" not in sql
    assert settings["max_execution_time"] > 0 and settings["readonly"] == 2
    window = response["time_range"]
    span = datetime.fromisoformat(window["end_time"]) - datetime.fromisoformat(window["start_time"])
    assert span.total_seconds() == 7 * 86400
    assert engine.v1_requests == []


def test_original_queries_keep_the_original_engine(engine):
    call({"query": '| where level = "error" | stats count() by service'})
    assert len(engine.v1_requests) == 1 and run_calls(engine.client) == []


def test_pipeline_errors_are_400s(engine):
    with pytest.raises(HTTPException) as exc:
        call({"query": "| stats count() by service | where level = \"x\""})
    assert exc.value.status_code == 400 and "level is not available" in exc.value.detail


def test_variables_are_passed_as_values(engine):
    call({"query": "| where service = $svc | stats count() by service", "variables": {"svc": "api"}})
    sql, params, _ = run_calls(engine.client)[0]
    assert "api" in params.values() and "'api'" not in sql
    with pytest.raises(HTTPException) as exc:
        call({"query": "| where service = $svc | head 1", "variables": {"svc": {"nested": 1}}})
    assert exc.value.status_code == 400


def test_database_errors_do_not_leak_sql(engine, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Code: 62. Syntax error near SELECT secret FROM other_tenant")
    monkeypatch.setattr(engine.client, "query", boom)
    with pytest.raises(HTTPException) as exc:
        call({"query": "| stats count() as n by service"})
    assert exc.value.status_code == 500 and "other_tenant" not in str(exc.value.detail)


def test_naive_window_values_are_utc(engine):
    response = call({"query": "| stats count() as n", "start_time": "2026-11-19T10:00:00",
                     "end_time": "2026-11-19T11:00:00"})
    assert response["time_range"]["start_time"].startswith("2026-11-19T10:00:00")
    _, params, _ = run_calls(engine.client)[0]
    assert datetime(2026, 11, 19, 10, tzinfo=timezone.utc) in params.values()


def test_lookups_are_loaded_for_queries_that_use_them(engine, monkeypatch):
    import lookup_tables

    calls = []

    class DAO:
        async def list(self, tenant):
            calls.append(tenant)
            return [lookup_tables.LookupTable(name="users", kind="csv", columns=["user_id", "dept"], key="user_id",
                                              row_count=2, version=4)]

    monkeypatch.setattr(lookup_tables, "LookupDAO", DAO)
    call({"query": "| lookup users user_id | stats count() by dept"})
    sql, params, _ = run_calls(engine.client)[0]
    assert calls == ["acme"] and "version = 4" in sql and "users" in params.values()
    call({"query": "| stats count() as n by service"})
    assert calls == ["acme"]  # not loaded when no lookup is used
    with pytest.raises(HTTPException) as exc:
        call({"query": "| lookup nope user_id"})
    assert exc.value.status_code == 400 and "Unknown lookup: nope" in exc.value.detail


def test_a_query_over_the_time_limit_is_explained(engine, monkeypatch):
    """Found by the 100 M-row benchmark: ClickHouse's timeout came back as a
    bare 500 "LogQL query failed"."""
    def slow(sql, parameters=None, settings=None):
        if sql.startswith("EXPLAIN"):
            return SimpleNamespace(column_names=["rows"], result_rows=[[10]])
        raise RuntimeError("Code: 159. DB::Exception: Timeout exceeded: elapsed 30.0 seconds, maximum: 30. "
                           "(TIMEOUT_EXCEEDED)")
    monkeypatch.setattr(engine.client, "query", slow)
    with pytest.raises(HTTPException) as exc:
        call({"query": "| stats count() as n by service"})
    assert exc.value.status_code == 504 and "30 s" in exc.value.detail and "Narrow" in exc.value.detail
