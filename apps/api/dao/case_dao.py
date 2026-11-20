"""
Case storage (Phase 2): cases_mt (one row version per change, read FINAL)
and case_events_mt (append-only timeline and audit trail). Every query is
tenant-scoped and parameterised.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cases import Case
from database_layer import DatabaseLayer

_CASE_COLUMNS = ("tenant_id", "id", "title", "severity", "status", "assignee", "description", "tags", "alert_ids",
                 "entities", "group_key", "created_by", "created_at", "updated_at", "acknowledged_at",
                 "contained_at", "resolved_at", "last_alert_at", "close_reason", "merged_into", "version")
_TIMES = ("created_at", "updated_at", "acknowledged_at", "contained_at", "resolved_at", "last_alert_at")
_EVENT_COLUMNS = ("tenant_id", "case_id", "id", "ts", "seq", "actor", "kind", "data")
_last_version = 0


def _ms(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _next_version() -> int:
    """Strictly increasing within the process (microseconds since epoch)."""
    global _last_version
    _last_version = max(_last_version + 1, time.time_ns() // 1000)
    return _last_version


class CaseDAO:
    def __init__(self):
        self.db = DatabaseLayer("CaseDAO", os.getenv("CASE_SERVICE_KEY", "case-dao-service-key"))

    # -- writes ------------------------------------------------------------
    async def save(self, case: Case) -> None:
        row = case.to_row()
        params = {k: row.get(k) for k in _CASE_COLUMNS if k != "version"}
        for key in _TIMES:
            params[key] = _ms(row.get(key))
        params["version"] = _next_version()
        columns = ", ".join(_CASE_COLUMNS)
        values = ", ".join(f"%({c})s" for c in _CASE_COLUMNS)
        await self.db.execute_update(f"INSERT INTO cases_mt ({columns}) VALUES ({values})", params)

    async def save_all(self, cases: Sequence[Case]) -> None:
        for case in cases:
            await self.save(case)

    async def append_events(self, events: Sequence[Dict[str, Any]]) -> None:
        if not events:
            return
        params: Dict[str, Any] = {}
        tuples = []
        for i, event in enumerate(events):
            params.update({
                f"tenant_id_{i}": event["tenant_id"], f"case_id_{i}": event["case_id"], f"id_{i}": event["id"],
                f"ts_{i}": _ms(event["ts"]), f"seq_{i}": i, f"actor_{i}": event.get("actor") or "", f"kind_{i}": event["kind"],
                f"data_{i}": json.dumps(event.get("data") or {}, default=str),
            })
            tuples.append("(" + ", ".join(f"%({c}_{i})s" for c in _EVENT_COLUMNS) + ")")
        await self.db.execute_update(
            f"INSERT INTO case_events_mt ({', '.join(_EVENT_COLUMNS)}) VALUES " + ", ".join(tuples), params)

    # -- SLA targets (per tenant) ---------------------------------------------
    async def sla_overrides(self, tenant_id: str) -> str:
        """The tenant's SLA overrides as JSON ('{}' for the defaults)."""
        try:
            rows = await self.db.fetch_all(
                "SELECT argMax(overrides, updated_at) AS overrides FROM case_sla_mt WHERE customer_id = %(t)s",
                {"t": tenant_id})
        except Exception as e:
            if "UNKNOWN_TABLE" in str(e) or "doesn't exist" in str(e):
                return "{}"  # migration 039 not applied: the defaults
            raise
        return (rows[0].get("overrides") if rows else None) or "{}"

    async def save_sla_overrides(self, tenant_id: str, overrides_json: str, actor: str) -> None:
        await self.db.execute_update(
            "INSERT INTO case_sla_mt (customer_id, overrides, updated_by) VALUES (%(t)s, %(o)s, %(a)s)",
            {"t": tenant_id, "o": overrides_json, "a": actor})

    # -- reads -------------------------------------------------------------
    async def get(self, tenant_id: str, case_id: str) -> Optional[Case]:
        rows = await self.db.fetch_all(
            "SELECT * FROM cases_mt FINAL WHERE tenant_id = %(tenant_id)s AND id = %(id)s",
            {"tenant_id": tenant_id, "id": case_id})
        return Case.from_row(rows[0]) if rows else None

    async def get_many(self, tenant_id: str, case_ids: Sequence[str]) -> List[Case]:
        if not case_ids:
            return []
        rows = await self.db.fetch_all(
            "SELECT * FROM cases_mt FINAL WHERE tenant_id = %(tenant_id)s AND id IN %(ids)s",
            {"tenant_id": tenant_id, "ids": list(case_ids)})
        return [Case.from_row(r) for r in rows or []]

    async def list(self, tenant_id: str, status: Optional[Sequence[str]] = None, assignee: Optional[str] = None,
                   severity: Optional[str] = None, q: Optional[str] = None, limit: int = 50,
                   offset: int = 0, entity: Optional[str] = None) -> Tuple[List[Case], int]:
        where = ["tenant_id = %(tenant_id)s"]
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        if status:
            where.append("status IN %(status)s")
            params["status"] = list(status)
        if assignee:
            where.append("assignee = %(assignee)s")
            params["assignee"] = assignee
        if severity:
            where.append("severity = %(severity)s")
            params["severity"] = severity
        if q:
            where.append("positionCaseInsensitiveUTF8(title, %(q)s) > 0")
            params["q"] = q
        if entity:
            # an exact value in the entities JSON ({"src_ip": ["1.2.3.4"], ...}), quoted as JSON writes it
            import json as _json

            where.append("positionUTF8(entities, %(entity)s) > 0")
            params["entity"] = _json.dumps(str(entity))
        clause = " AND ".join(where)
        rows = await self.db.fetch_all(
            f"SELECT * FROM cases_mt FINAL WHERE {clause} ORDER BY updated_at DESC "
            "LIMIT %(limit)s OFFSET %(offset)s", {**params, "limit": limit, "offset": offset})
        total = await self.db.fetch_all(f"SELECT count() AS total FROM cases_mt FINAL WHERE {clause}", params)
        return [Case.from_row(r) for r in rows or []], int((total or [{}])[0].get("total", 0))

    async def for_metrics(self, tenant_id: str, since: datetime) -> List[Case]:
        """Cases created since `since`, plus every case still open."""
        rows = await self.db.fetch_all(
            "SELECT * FROM cases_mt FINAL WHERE tenant_id = %(tenant_id)s AND merged_into = '' "
            "AND (created_at >= %(since)s OR status NOT IN ('resolved', 'false_positive'))",
            {"tenant_id": tenant_id, "since": _ms(since)})
        return [Case.from_row(r) for r in rows or []]

    async def find_open_by_group_key(self, tenant_id: str, group_key: str, since: datetime) -> Optional[Case]:
        rows = await self.db.fetch_all(
            "SELECT * FROM cases_mt FINAL WHERE tenant_id = %(tenant_id)s AND group_key = %(group_key)s "
            "AND status NOT IN ('resolved', 'false_positive') AND last_alert_at >= %(since)s "
            "ORDER BY last_alert_at DESC LIMIT 1",
            {"tenant_id": tenant_id, "group_key": group_key, "since": _ms(since)})
        return Case.from_row(rows[0]) if rows else None

    @staticmethod
    def _decode_event(row: Dict[str, Any]) -> Dict[str, Any]:
        event = dict(row)
        try:
            event["data"] = json.loads(row.get("data") or "{}")
        except ValueError:
            event["data"] = {}
        ts = event.get("ts")
        if isinstance(ts, datetime):
            event["ts"] = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).isoformat()
        return event

    async def events(self, tenant_id: str, case_id: str) -> List[Dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT id, case_id, ts, seq, actor, kind, data FROM case_events_mt "
            "WHERE tenant_id = %(tenant_id)s AND case_id = %(case_id)s ORDER BY ts, seq",
            {"tenant_id": tenant_id, "case_id": case_id})
        return [self._decode_event(r) for r in rows or []]

    async def events_between(self, tenant_id: str, start: datetime, end: datetime,
                             limit: int = 100_000) -> List[Dict[str, Any]]:
        rows = await self.db.fetch_all(
            "SELECT id, case_id, ts, seq, actor, kind, data FROM case_events_mt WHERE tenant_id = %(tenant_id)s "
            "AND ts >= %(start)s AND ts < %(end)s ORDER BY ts, seq LIMIT %(limit)s",
            {"tenant_id": tenant_id, "start": _ms(start), "end": _ms(end), "limit": limit})
        return [self._decode_event(r) for r in rows or []]
