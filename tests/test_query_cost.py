"""
Query cost estimation and per-plan limits (Phase 6).

Before a pipeline query runs, ClickHouse estimates the rows it will read
(EXPLAIN ESTIMATE: index-only, it reads no data). A query over the tenant's
plan limit is refused with a 400 that says how to narrow it, instead of
running for minutes and degrading the cluster. POST /v1/query/estimate
returns the estimate without running the query.

Limits come from config/query_limits.yml, by subscription tier.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import query_cost
import routers.query as qr


class Client:
    def __init__(self, estimate_rows=1000):
        self.estimate_rows, self.calls = estimate_rows, []

    def query(self, sql, parameters=None, settings=None):
        self.calls.append(sql)
        if sql.startswith("EXPLAIN ESTIMATE"):
            return SimpleNamespace(column_names=["database", "table", "parts", "rows", "marks"],
                                   result_rows=[["logforge", "logs_raw_mt", 3, self.estimate_rows, 9]])
        return SimpleNamespace(column_names=["service", "n"], result_rows=[["api", 1]])


@pytest.fixture
def engine(monkeypatch):
    client = Client()
    monkeypatch.setattr(qr, "query_engine", SimpleNamespace(client=client))
    tiers = {"acme": "startup", "big": "enterprise"}

    async def tier(tenant_id):
        return tiers.get(tenant_id)

    monkeypatch.setattr(query_cost, "tier_for", tier)
    return client


def test_limits_come_from_the_plan():
    limits = query_cost.load_limits()
    assert limits.max_rows("startup") < limits.max_rows("enterprise")
    assert limits.max_rows(None) == limits.max_rows("no-such-tier") == limits.default


def test_queries_over_the_plan_limit_are_refused_before_they_run(engine):
    engine.estimate_rows = query_cost.load_limits().max_rows("startup") + 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(qr.logql_query({"query": "| stats count() as n by service"}, customer_id="acme"))
    assert exc.value.status_code == 400
    assert "would read about" in exc.value.detail and "startup" in exc.value.detail
    assert all(sql.startswith("EXPLAIN ESTIMATE") for sql in engine.calls)  # never executed
    # a bigger plan runs the same query
    response = asyncio.run(qr.logql_query({"query": "| stats count() as n by service"}, customer_id="big"))
    assert response["query_info"]["estimated_rows"] == engine.estimate_rows


def test_the_estimate_endpoint(engine):
    engine.estimate_rows = 12345
    r = asyncio.run(qr.estimate_query({"query": "| stats count() by service", "since": "7d"}, customer_id="acme"))
    assert r["estimated_rows"] == 12345 and r["plan"] == "startup" and r["within_limit"] is True
    assert r["rollup"] is True and r["limit_rows"] == query_cost.load_limits().max_rows("startup")
    assert not any(sql.startswith("SELECT") for sql in engine.calls)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(qr.estimate_query({"query": "| nonsense"}, customer_id="acme"))
    assert exc.value.status_code == 400


def test_an_unavailable_estimate_does_not_block_the_query(engine, monkeypatch):
    def broken(sql, parameters=None, settings=None):
        if sql.startswith("EXPLAIN"):
            raise RuntimeError("EXPLAIN not supported here")
        return SimpleNamespace(column_names=["n"], result_rows=[[1]])

    monkeypatch.setattr(engine, "query", broken)
    response = asyncio.run(qr.logql_query({"query": "| stats count() as n"}, customer_id="acme"))
    assert response["logs"] == [{"n": 1}] and response["query_info"]["estimated_rows"] is None
