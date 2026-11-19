"""
A tenant has exactly one active subscription, and the newest change wins.

Plan changes inserted a new 'active' row without retiring the old one, and
the timestamps were stored at whole-second precision (client-side binding
dropped the fraction). Two changes in the same second left two active rows
with identical `started_at`, so `ORDER BY started_at DESC LIMIT 1` returned
either one: a freshly upgraded tenant intermittently got its old plan and
403 feature_not_subscribed (seen as an intermittent route-test failure;
12 tenants had duplicate active rows).
"""

import re
from datetime import datetime, timezone

import pytest

from dao.subscription_dao import SubscriptionDAO


class _FakeDB:
    def __init__(self, rows=None):
        self.queries = []
        self.rows = rows or []

    async def execute_query(self, sql, params=None):
        self.queries.append((" ".join(sql.split()), params))
        return self.rows


@pytest.fixture
def dao():
    instance = SubscriptionDAO.__new__(SubscriptionDAO)
    instance.db = _FakeDB()
    return instance


def _data(**overrides):
    data = {"tenant_id": "t1", "subscribed_features": ["*"], "subscription_tier": "enterprise",
            "billing_cycle": "monthly",
            "started_at": datetime(2026, 11, 17, 13, 46, 22, 123456, tzinfo=timezone.utc)}
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_creating_a_subscription_retires_the_tenants_active_ones_first(dao):
    await dao.create_subscription(_data())

    retire, insert = dao.db.queries[0], dao.db.queries[1]
    assert retire[0].startswith("ALTER TABLE tenant_subscriptions_mt UPDATE status = 'inactive'")
    assert "WHERE tenant_id = %(tenant_id)s AND status = 'active'" in retire[0]
    assert "mutations_sync = 2" in retire[0]  # finished before the new row is visible
    assert retire[1] == {"tenant_id": "t1"}
    assert insert[0].startswith("INSERT INTO tenant_subscriptions_mt")


@pytest.mark.asyncio
async def test_timestamps_keep_millisecond_precision(dao):
    await dao.create_subscription(_data())
    params = dao.db.queries[1][1]

    assert params["started_at"] == "2026-11-17 13:46:22.123"
    for key in ("created_at", "updated_at"):
        assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}", params[key]), params[key]


@pytest.mark.asyncio
async def test_lookup_breaks_ties_by_creation_time(dao):
    await dao.get_subscription_by_tenant("t1")
    sql = dao.db.queries[0][0]
    assert "ORDER BY started_at DESC, created_at DESC LIMIT 1" in sql
