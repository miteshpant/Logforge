"""
The rule-based NLQ processor builds SQL as text. Service names come from the
tenant's logs, so they are attacker-influenced: they must not be able to
change the query (found by the Phase 8 security review: a service named
x') OR (1=1) OR service IN ('y removed the tenant filter).
"""

import asyncio

from services.nlq_processor import NLQProcessor, QueryIntent


def sql_for(services, intent_type="errors"):
    processor = NLQProcessor.__new__(NLQProcessor)
    from services.nlq_processor import TimeRange
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    intent = QueryIntent(type=intent_type, confidence=0.9, entities={
        "time_range": TimeRange(start=now - timedelta(hours=1), end=now, description="last hour"),
        "services": services, "metrics": []}, keywords=[])
    return asyncio.run(processor._generate_sql(intent, "tenant-a", 100))


def test_service_names_cannot_change_the_query():
    evil = "x') OR (1=1) OR service IN ('y"
    sql = sql_for([evil, "checkout"])
    assert "OR (1=1)" not in sql and evil not in sql
    assert "'checkout'" in sql


def test_ordinary_service_names_still_filter():
    sql = sql_for(["api-gateway", "payments.v2"])
    assert "service IN ('api-gateway', 'payments.v2')" in sql
