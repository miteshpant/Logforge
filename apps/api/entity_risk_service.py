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
_cache: Dict[str, Tuple[float, List[Risk], Dict, List[str]]] = {}


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


CANDIDATES = 30
BASELINE_TIMEOUT = 15.0


async def _anomalies(tenant_id: str, ranked: List[Risk], now: datetime) -> Dict:
    """Baseline anomalies (entity_baselines) for the top users, hosts and addresses by alert risk."""
    import asyncio

    from entity_baselines import BaselineStore

    store = BaselineStore()
    out: Dict = {}
    for etype in ("user", "host", "ip"):
        values = [r.value for r in ranked if r.entity_type == etype][:CANDIDATES]
        if not values:
            continue
        found = await asyncio.wait_for(store.anomalies(tenant_id, etype, values, now), BASELINE_TIMEOUT)
        for value, items in found.items():
            out[(etype, value)] = [a.to_public() for a in items]
    return out


async def ranking(tenant_id: str, now: Optional[datetime] = None) -> Tuple[List[Risk], Dict, List[str]]:
    """(entities ranked by risk, alerts per entity, flags). Risk includes baseline anomalies for the top
    candidates; if those can't be read in time, the ranking is by alerts and intel alone (flagged)."""
    cached = _cache.get(tenant_id)
    if cached and time.monotonic() - cached[0] < TTL_SECONDS:
        return cached[1], cached[2], cached[3]
    now = now or datetime.now(timezone.utc)
    alerts = to_alerts(await _alert_rows(tenant_id))
    ranked = rank(alerts, now, limit=100_000)
    flags: List[str] = []
    try:
        anomalies = await _anomalies(tenant_id, ranked, now)
    except Exception:  # noqa: BLE001 - a slow or failing baseline query must not hide the alert-based ranking
        anomalies, flags = {}, ["baselines_unavailable"]
    if anomalies:
        ranked = rank(alerts, now, anomalies=anomalies, limit=100_000)
    by_entity = attribute(alerts)
    _cache[tenant_id] = (time.monotonic(), ranked, by_entity, flags)
    return ranked, by_entity, flags


def clear_cache() -> None:
    _cache.clear()
