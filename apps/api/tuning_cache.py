"""
Per-tenant detection tuning for the live path, cached briefly so the
detection loop doesn't query the database per batch. Changes made through
the API invalidate the tenant's entry immediately on this process; other
processes pick them up within TTL_SECONDS.
"""

from __future__ import annotations

import time
from typing import Dict, Tuple

from detection_tuning import TuningSet

TTL_SECONDS = 60
_cache: Dict[str, Tuple[float, TuningSet]] = {}


async def get_tuning(tenant_id: str) -> TuningSet:
    hit = _cache.get(tenant_id)
    if hit and time.monotonic() - hit[0] < TTL_SECONDS:
        return hit[1]
    from dao.tuning_dao import TuningDAO

    records = await TuningDAO().list_records(tenant_id)
    tuning = TuningSet.from_records(records)
    _cache[tenant_id] = (time.monotonic(), tuning)
    return tuning


def invalidate(tenant_id: str) -> None:
    _cache.pop(tenant_id, None)
