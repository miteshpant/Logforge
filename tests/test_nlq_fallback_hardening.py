"""The rule-based NLQ (the answer when AI is off) binds every value as a query
parameter, checks the permission each intent needs, and refuses under a data
scope (it reads tables the scope doesn't filter), so it can be offered to
everyone with ai:read."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import data_scope  # noqa: E402
from services.nlq_processor import NLQProcessor, QueryIntent, TimeRange  # noqa: E402

TENANT = "tenant-a"


def intent(kind, services=()):
    now = datetime.now(timezone.utc)
    return QueryIntent(type=kind, confidence=0.9, keywords=[], entities={
        "time_range": TimeRange(start=now - timedelta(hours=1), end=now, description="last hour"),
        "services": list(services), "metrics": []})


class FakeDAO:
    def __init__(self):
        self.calls = []

    async def execute_query(self, sql, params=None):
        self.calls.append((sql, params))
        return []


def processor(kind):
    p = NLQProcessor.__new__(NLQProcessor)
    p.dao = FakeDAO()

    async def classify(question, customer_id):
        return intent(kind, ["checkout"])

    p._classify_intent = classify
    return p


def test_every_value_is_a_parameter():
    p = processor("errors")
    for kind in ("alerts", "errors", "performance", "traffic", "security", "general"):
        sql, params = asyncio.run(p._generate_sql(intent(kind, ["checkout"]), TENANT, 50))
        assert TENANT not in sql and "checkout" not in sql, kind
        assert "%(customer_id)s" in sql and params["customer_id"] == TENANT
        assert params["start"] < params["end"] and params["limit"] == 50
    sql, params = asyncio.run(p._generate_sql(intent("errors", ["checkout"]), TENANT, 50))
    assert "IN %(services)s" in sql and params["services"] == ("checkout",)


def test_each_intent_needs_its_own_permission():
    needed = {"alerts": "alerts:read:tenant", "security": "security:read:tenant", "errors": "logs:read:tenant",
              "performance": "observability:read:tenant", "traffic": "logs:read:tenant", "general": "logs:read:tenant"}
    for kind, permission in needed.items():
        p = processor(kind)
        asked = []
        result = asyncio.run(p.process_question("q", TENANT, allowed=lambda perm: asked.append(perm) or False))
        assert asked == [permission], kind
        assert p.dao.calls == [] and "permission" in result.answer.lower() and result.generated_sql == ""


def test_allowed_intent_runs_with_parameters():
    p = processor("errors")
    asyncio.run(p.process_question("q", TENANT, allowed=lambda perm: True))
    (sql, params), = p.dao.calls
    assert params["customer_id"] == TENANT and "%(customer_id)s" in sql


def test_refused_under_a_data_scope():
    p = processor("errors")
    with data_scope.scoped(data_scope.DataScope(services=("payments",))):
        result = asyncio.run(p.process_question("q", TENANT, allowed=lambda perm: True))
    assert p.dao.calls == [] and "scope" in result.answer.lower()


def test_performance_reads_span_latency_with_valid_functions():
    """It read a column logs_normalized_mt doesn't have, with QUANTILE (ClickHouse
    only knows quantile), so it always failed and answered 'no data'."""
    sql, _ = asyncio.run(processor("performance")._generate_sql(intent("performance"), TENANT, 10))
    assert "FROM traces_mt" in sql and "duration_ms" in sql and "QUANTILE(" not in sql
