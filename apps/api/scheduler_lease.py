"""
One replica per tick for background schedulers.

Saved searches, scheduled reports, ticket sync and playbook dispatch run as
loops in every API process. Before a tick's work, a loop takes a lease in
Redis (SET NX, expiring just before the next tick); the replica that gets it
does the work and the others skip that tick. Without Redis each process runs
every tick, as a single replica would.
"""

from __future__ import annotations

import logging
import os
import socket

logger = logging.getLogger(__name__)

_HOLDER = f"{socket.gethostname()}:{os.getpid()}"


async def _client():
    from events.management.cache.redis_manager import get_raw_client

    return await get_raw_client()


async def acquire(name: str, tick_seconds: int) -> bool:
    """True if this process should run this tick of scheduler `name`."""
    try:
        client = await _client()
        if client is None:
            return True
        return bool(await client.set(f"logforge:lease:{name}", _HOLDER, nx=True, ex=max(1, int(tick_seconds) - 1)))
    except Exception as e:
        logger.warning("Scheduler lease %s unavailable, running this tick here: %s", name, e)
        return True
