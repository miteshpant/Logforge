"""
A tenant's rules are reloaded after their cache entry is invalidated.

get_customer_rules returned cached results when EITHER the tenant's entry or
the default library's entry was present. After invalidate_customer_cache
(rule sync, rule edits) the library was still cached, so the tenant's own
rules were never reloaded and silently dropped out of live detection (found
live: git-synced rules didn't alert). Each part is now loaded on its own
miss, and a tenant with no rules is cached as an empty list.
"""

import asyncio
import sys
import types

from events.management.cache.sigma_rule_cache import SigmaRuleCache

MISSING = object()


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key, default=None):
        return self.store.get(key, default)

    async def set(self, key, value, *args, **kwargs):
        self.store[key] = value
        return True

    async def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0


def make_cache(monkeypatch, tenant_rules):
    calls = {"tenant": 0, "defaults": 0}

    class FakeService:
        async def get_sigma_rules_for_customer(self, customer_id):
            calls["tenant"] += 1
            return list(tenant_rules)

        async def get_default_sigma_rules(self):
            calls["defaults"] += 1
            return [{"id": "lib-1", "enabled": True}]

    module = types.ModuleType("services.security_service")
    module.SecurityService = FakeService
    monkeypatch.setitem(sys.modules, "services.security_service", module)
    cache = SigmaRuleCache(redis_manager=FakeRedis())
    return cache, calls


def ids(rules):
    return sorted(r["id"] for r in rules)


def test_tenant_rules_reload_after_invalidation_while_defaults_stay_cached(monkeypatch):
    cache, calls = make_cache(monkeypatch, [{"id": "acme-1", "enabled": True}])
    assert ids(asyncio.run(cache.get_customer_rules("acme"))) == ["acme-1", "lib-1"]
    asyncio.run(cache.invalidate_customer_cache("acme"))
    assert ids(asyncio.run(cache.get_customer_rules("acme"))) == ["acme-1", "lib-1"]
    assert calls == {"tenant": 2, "defaults": 1}


def test_a_tenant_without_rules_is_cached_as_empty(monkeypatch):
    cache, calls = make_cache(monkeypatch, [])
    asyncio.run(cache.get_customer_rules("empty"))
    asyncio.run(cache.get_customer_rules("empty"))
    assert calls["tenant"] == 1
