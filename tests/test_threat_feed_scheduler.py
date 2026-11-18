"""
Threat feed scheduler (Phase 3): every minute, run each tenant's due feeds.
One failing feed doesn't stop the others; after a successful run the tenant's
in-memory index is reloaded, and the new indicators are handed to the
retro-hunt hook.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from threat_feed_scheduler import run_due_feeds
from threat_intel_store import FeedConfig, IndicatorIndex

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def feed(fid, url="https://feed.example/list.txt", **extra):
    return FeedConfig.from_dict({"id": fid, "name": fid, "kind": "plain", "url": url, **extra})


class DAO:
    def __init__(self, feeds):
        self.feeds = feeds
        self.upserts, self.runs = [], []

    async def list_feeds(self, tenant_id=None):
        return self.feeds

    async def existing_keys(self, tenant_id, keys):
        return set()

    async def upsert_indicators(self, tenant_id, indicators, feed_id, now):
        self.upserts.append((tenant_id, feed_id, [i.value for i in indicators]))

    async def record_run(self, tenant_id, feed, now, status, count, error):
        self.runs.append((tenant_id, feed.id, status))


def test_runs_due_feeds_per_tenant_and_survives_failures():
    dao = DAO([("acme", feed("ok")), ("acme", feed("broken", url="https://broken.example/x")),
               ("beta", feed("recent", last_run_at=(T0 - timedelta(minutes=5)).isoformat()))])

    async def fetch(request):
        if "broken" in request["url"]:
            raise ConnectionError("connection refused")
        return 200, "203.0.113.50\n"

    index = IndicatorIndex(loader=lambda t, n: _empty(), ttl_seconds=3600)
    index._sets["acme"] = (T0, {})
    hunted = []

    async def retro_hunt(tenant_id, keys):
        hunted.append((tenant_id, keys))

    results = asyncio.run(run_due_feeds(dao, fetch=fetch, index=index, now=T0, on_new=retro_hunt))
    assert [(r["tenant_id"], r["feed_id"], r["status"]) for r in results] == [
        ("acme", "ok", "ok"), ("acme", "broken", "error")]
    assert dao.upserts == [("acme", "ok", ["203.0.113.50"])]
    assert "acme" not in index._sets  # reloaded on next lookup
    assert hunted == [("acme", [("ip", "203.0.113.50")])]


async def _empty():
    return []
