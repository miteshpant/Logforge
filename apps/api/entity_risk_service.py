"""
Tenant-wide entity risk (Phase 11): the alerts of the last 14 days, as case
alerts (entities extracted), ranked by entity_risk. Cached per tenant for a
minute, since an entity page and the risk list read the same ranking.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from entity_risk import WINDOW, Risk, attribute, rank

MAX_ALERTS = 20_000
TTL_SECONDS = 60
_cache: Dict[str, Tuple[float, List[Risk], Dict]] = {}


async def _alert_rows(tenant_id: str) -> List[Dict[str, Any]]:
    import os

    from database_layer import DatabaseLayer

    db = DatabaseLayer("EntityRiskService", os.getenv("ENTITY_SERVICE_KEY", "entity-service-key"))
    return await db.fetch_all(
        "SELECT id, rule_id, title, severity, status, raw_log_data, mitre_techniques, created_at "
        "FROM security_events_mt WHERE customer_id = %(tenant)s AND created_at >= now() - INTERVAL %(days)s DAY "
        "AND status != 'false_positive' ORDER BY created_at DESC LIMIT %(limit)s",
        {"tenant": tenant_id, "days": WINDOW.days, "limit": MAX_ALERTS})


def to_alerts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services.case_service import alert_summary

    out = []
    for row in rows:
        row = dict(row)
        if isinstance(row.get("raw_log_data"), str):
            try:
                row["raw_log_data"] = json.loads(row["raw_log_data"] or "{}")
            except ValueError:
                row["raw_log_data"] = {}
        if isinstance(row.get("created_at"), datetime) and row["created_at"].tzinfo is None:
            row["created_at"] = row["created_at"].replace(tzinfo=timezone.utc)
        out.append(alert_summary(row))
    return out


async def ranking(tenant_id: str, now: Optional[datetime] = None,
                  anomalies: Optional[Dict] = None) -> Tuple[List[Risk], Dict]:
    """(entities ranked by risk, alerts per entity)."""
    cached = _cache.get(tenant_id)
    if cached and time.monotonic() - cached[0] < TTL_SECONDS and anomalies is None:
        return cached[1], cached[2]
    alerts = to_alerts(await _alert_rows(tenant_id))
    ranked = rank(alerts, now or datetime.now(timezone.utc), anomalies=anomalies, limit=100_000)
    by_entity = attribute(alerts)
    _cache[tenant_id] = (time.monotonic(), ranked, by_entity)
    return ranked, by_entity


def clear_cache() -> None:
    _cache.clear()
