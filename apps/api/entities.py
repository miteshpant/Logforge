"""
Entities (Phase 11): users, hosts, IP addresses, services and cloud accounts
seen in a tenant's events, kept by materialized views (migration 026) with
first and last seen, an event count, and which entities appear together.

EntityStore reads them:

* search(): entities of a type (or all), optionally matching a substring,
  most recently seen first;
* get(): one entity's summary;
* related(): the entities seen with it (both directions of an edge);
* query_for(): the LogforgeQL that finds an entity's events, used for its
  timeline and by the copilot and the Log Explorer links.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

TYPES = ("user", "host", "ip", "service", "cloud_account")
# where each type lives in an event (columns first, then attrs)
FIELDS = {
    "user": ("user_id", "attrs.user"),
    "host": ("host", "attrs.hostname"),
    "ip": ("src_ip", "attrs.src_ip", "attrs.dst_ip"),
    "service": ("service",),
    "cloud_account": ("attrs.recipientAccountId", "attrs.ocsf.cloud.account.uid"),
}
# alert entity fields (case_service.ENTITY_FIELDS) -> entity types
ALERT_TYPES = {"src_ip": "ip", "dst_ip": "ip", "user": "user", "hostname": "host"}


class EntityError(ValueError):
    pass


def check(entity_type: str, value: str) -> None:
    if entity_type not in TYPES:
        raise EntityError(f"unknown entity type {entity_type!r} (one of {', '.join(TYPES)})")
    if not value or len(value) > 512:
        raise EntityError("an entity needs a value (up to 512 characters)")


def query_for(entity_type: str, value: str) -> str:
    check(entity_type, value)
    quoted = json.dumps(value)
    return "| where " + " or ".join(f"{f} = {quoted}" for f in FIELDS[entity_type])


def _summary(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for key in ("first_seen", "last_seen"):
        if hasattr(out.get(key), "isoformat"):
            out[key] = out[key].isoformat()
    out["events"] = int(out.get("events") or 0)
    return out


class EntityStore:
    def __init__(self, db=None):
        if db is None:
            import os

            from database_layer import DatabaseLayer

            db = DatabaseLayer("EntityService", os.getenv("ENTITY_SERVICE_KEY", "entity-service-key"))
        self.db = db

    async def search(self, tenant_id: str, entity_type: Optional[str] = None, q: str = "",
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        if entity_type is not None and entity_type not in TYPES:
            raise EntityError(f"unknown entity type {entity_type!r}")
        where = ["customer_id = %(tenant)s"]
        params: Dict[str, Any] = {"tenant": tenant_id, "limit": min(max(limit, 1), 500), "offset": max(offset, 0)}
        if entity_type:
            where.append("entity_type = %(type)s")
            params["type"] = entity_type
        if q:
            where.append("positionCaseInsensitive(value, %(q)s) > 0")
            params["q"] = q[:200]
        rows = await self.db.fetch_all(
            "SELECT entity_type, value, min(first_seen) AS first_seen, max(last_seen) AS last_seen, "
            "sum(events) AS events FROM entities_mt WHERE " + " AND ".join(where) +
            " GROUP BY entity_type, value ORDER BY last_seen DESC LIMIT %(limit)s OFFSET %(offset)s", params)
        return [_summary(r) for r in rows]

    async def get(self, tenant_id: str, entity_type: str, value: str) -> Optional[Dict[str, Any]]:
        check(entity_type, value)
        rows = await self.db.fetch_all(
            "SELECT entity_type, value, min(first_seen) AS first_seen, max(last_seen) AS last_seen, "
            "sum(events) AS events FROM entities_mt WHERE customer_id = %(tenant)s AND entity_type = %(type)s "
            "AND value = %(value)s GROUP BY entity_type, value", {"tenant": tenant_id, "type": entity_type,
                                                                   "value": value})
        return _summary(rows[0]) if rows else None

    async def related(self, tenant_id: str, entity_type: str, value: str, limit: int = 50) -> List[Dict[str, Any]]:
        check(entity_type, value)
        params = {"tenant": tenant_id, "type": entity_type, "value": value, "limit": min(max(limit, 1), 200)}
        rows = await self.db.fetch_all(
            "SELECT entity_type, value, min(first_seen) AS first_seen, max(last_seen) AS last_seen, "
            "sum(events) AS events FROM ("
            " SELECT b_type AS entity_type, b AS value, first_seen, last_seen, events FROM entity_edges_mt"
            " WHERE customer_id = %(tenant)s AND a_type = %(type)s AND a = %(value)s"
            " UNION ALL"
            " SELECT a_type AS entity_type, a AS value, first_seen, last_seen, events FROM entity_edges_mt"
            " WHERE customer_id = %(tenant)s AND b_type = %(type)s AND b = %(value)s"
            ") GROUP BY entity_type, value ORDER BY events DESC LIMIT %(limit)s", params)
        return [_summary(r) for r in rows]
