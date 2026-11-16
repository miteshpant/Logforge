"""
Regression test: on a cache miss, AlertRuleCache must load the tenant's rules
from the database.

The cache's fallback called AlertService.get_alert_rules_for_customer(), which
did not exist. Every miss raised AttributeError, was logged, and returned [],
so log batches were never evaluated against alert rules. Found in the live QA
run as `'AlertService' object has no attribute 'get_alert_rules_for_customer'`
on every ingested batch.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_alert_service_exposes_the_method_the_cache_calls():
    from services.alert_service import AlertService

    assert callable(getattr(AlertService, "get_alert_rules_for_customer", None))


@pytest.mark.asyncio
async def test_get_alert_rules_for_customer_returns_enabled_rules_only():
    from services.alert_service import AlertService

    svc = AlertService.__new__(AlertService)
    svc.alert_dao = MagicMock()
    svc.alert_dao.list_alert_rules = AsyncMock(return_value=[{"id": "r1"}])

    rules = await svc.get_alert_rules_for_customer("tenant-1")

    assert rules == [{"id": "r1"}]
    svc.alert_dao.list_alert_rules.assert_awaited_once_with("tenant-1", enabled=True)


@pytest.mark.asyncio
async def test_cache_miss_falls_back_to_db_and_caches_result():
    from events.management.cache.alert_rule_cache import AlertRuleCache

    redis = MagicMock()
    redis.get = AsyncMock(return_value=[])  # cache miss
    cache = AlertRuleCache(redis_manager=redis)
    cache._cache_customer_rules = AsyncMock(return_value=True)

    rules = [{"id": "r1", "customer_id": "tenant-1", "enabled": True}]
    with patch("services.alert_service.AlertService") as svc_cls:
        svc_cls.return_value.get_alert_rules_for_customer = AsyncMock(return_value=rules)
        got = await cache.get_customer_rules("tenant-1")

    assert got == rules
    cache._cache_customer_rules.assert_awaited_once_with("tenant-1", rules)
