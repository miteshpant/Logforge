"""
Query cost estimation and per-plan limits (Phase 6).

ClickHouse's EXPLAIN ESTIMATE reports the rows a statement will read, from
the primary index, skip indexes and projections, without reading data. The
pipeline router checks it against the tenant's plan (config/query_limits.yml)
before running a query.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

_CONFIG = Path(__file__).parent / "config" / "query_limits.yml"
_TIER_TTL_SECONDS = 300
_tier_cache: Dict[str, tuple] = {}


@dataclass
class Limits:
    default: int
    tiers: Dict[str, int] = field(default_factory=dict)

    def max_rows(self, tier: Optional[str]) -> int:
        override = os.getenv("LOGFORGE_QUERY_MAX_ROWS")
        if override:
            return int(override)
        return self.tiers.get(str(tier or ""), self.default)


def load_limits(path: Path = _CONFIG) -> Limits:
    data = yaml.safe_load(path.read_text()) or {}
    default = int((data.get("default") or {}).get("max_rows_scanned", 500_000_000))
    tiers = {name: int((cfg or {}).get("max_rows_scanned", default)) for name, cfg in (data.get("tiers") or {}).items()}
    return Limits(default=default, tiers=tiers)


class QueryTooExpensive(ValueError):
    """The query would read more rows than the tenant's plan allows."""


async def tier_for(tenant_id: str) -> Optional[str]:
    """The tenant's subscription tier (cached for five minutes)."""
    cached = _tier_cache.get(tenant_id)
    if cached and time.monotonic() - cached[1] < _TIER_TTL_SECONDS:
        return cached[0]
    tier = None
    try:
        from services.subscription_service import SubscriptionService

        subscription = await SubscriptionService().get_tenant_subscription(tenant_id)
        value = getattr(subscription, "subscription_tier", None)
        tier = getattr(value, "value", value)
    except Exception as e:
        logger.warning(f"Could not read the subscription tier of {tenant_id}: {e}")
    _tier_cache[tenant_id] = (tier, time.monotonic())
    return tier


def estimate_rows(client, sql: str, params: Dict[str, Any]) -> Optional[int]:
    """Rows the statement would read, or None if ClickHouse cannot say."""
    try:
        result = client.query(f"EXPLAIN ESTIMATE {sql}", parameters=params, settings={"readonly": 2})
    except Exception as e:
        logger.warning(f"EXPLAIN ESTIMATE failed: {e}")
        return None
    names = list(result.column_names)
    if "rows" not in names:
        return None
    index = names.index("rows")
    return int(sum(int(row[index]) for row in result.result_rows))


def check(rows: Optional[int], tier: Optional[str], limits: Optional[Limits] = None) -> int:
    """The limit; raises QueryTooExpensive when the estimate is over it."""
    limits = limits or load_limits()
    limit = limits.max_rows(tier)
    if rows is not None and rows > limit:
        raise QueryTooExpensive(
            f"This query would read about {rows:,} rows; the {tier or 'default'} plan allows {limit:,} per "
            f"query. Narrow the time range, filter on service or level first, or count with stats count() "
            f"by service / level / status (those read the hourly counts).")
    return limit
