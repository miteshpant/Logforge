"""
Threat feed scheduler (Phase 3): every minute, run each tenant's due feeds
(threat_intel_store.run_feed). One failing feed doesn't stop the others.
After a successful run the tenant's in-memory index is reloaded and the new
indicators go to the retro-hunt hook.

THREAT_FEEDS_SCHEDULER=off disables it (feeds can still be run on demand).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import structlog

from threat_intel_store import due_feeds, get_indicator_index, run_feed

logger = structlog.get_logger(__name__)
TICK_SECONDS = 60

OnNew = Callable[[str, List[Any]], Awaitable[Any]]


async def run_due_feeds(dao, fetch=None, index=None, now: Optional[datetime] = None,
                        on_new: Optional[OnNew] = None) -> List[Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    index = index or get_indicator_index()
    by_tenant: Dict[str, List[Any]] = {}
    for tenant_id, feed in await dao.list_feeds():
        by_tenant.setdefault(tenant_id, []).append(feed)
    results = []
    for tenant_id, feeds in by_tenant.items():
        for feed in due_feeds(feeds, now):
            result = await run_feed(tenant_id, feed, dao, fetch=fetch, now=now)
            results.append({"tenant_id": tenant_id, "feed_id": feed.id, **result})
            if result["status"] == "ok":
                index.invalidate(tenant_id)
                if result["new"] and on_new is not None:
                    try:
                        await on_new(tenant_id, result["new"])
                    except Exception as e:
                        logger.warning(f"Retro-hunt after {feed.name} failed: {e}")
    return results


async def scheduler_loop() -> None:
    from threat_intel_store import ThreatIntelDAO

    dao = ThreatIntelDAO()
    while True:
        try:
            hook = None
            try:
                from retro_hunt import retro_hunt_new_indicators as hook  # noqa: F811
            except ImportError:
                pass
            for result in await run_due_feeds(dao, on_new=hook):
                logger.info("Threat feed run", tenant_id=result["tenant_id"], feed_id=result["feed_id"],
                            status=result["status"], count=result["count"], new=len(result["new"]),
                            error=result["error"])
        except Exception as e:
            logger.error(f"Threat feed scheduler tick failed: {e}")
        await asyncio.sleep(TICK_SECONDS)


def start_scheduler() -> bool:
    if os.getenv("THREAT_FEEDS_SCHEDULER", "on").lower() in ("off", "false", "0"):
        return False
    asyncio.create_task(scheduler_loop())
    return True
