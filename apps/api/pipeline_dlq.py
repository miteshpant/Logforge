"""
The ingest pipeline dead-letter queue (Phase 4): pipeline_dlq_mt.

Entries hold the event as it arrived, the pipeline and version, the failing
processor and the error. An entry is pending until it is replayed (sent
through ingest again, normally after the pipeline was fixed) or discarded.
Status changes are new row versions (ReplacingMergeTree, read FINAL).
"""

from __future__ import annotations

import json
import os
import time as _time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

_COLUMNS = ("tenant_id", "id", "pipeline_id", "pipeline_version", "processor", "processor_index", "tag", "error",
            "event", "failed_at", "status", "resolved_at", "resolved_by", "version")
STATUSES = ("pending", "replayed", "discarded")


def _ms(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):  # ISO text, e.g. an entry read back through the API
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class PipelineDLQ:
    def __init__(self, db=None):
        if db is None:
            from database_layer import DatabaseLayer

            db = DatabaseLayer("PipelineDAO", os.getenv("PIPELINE_SERVICE_KEY", "pipeline-dao-service-key"))
        self.db = db

    async def _insert(self, rows: Sequence[Dict[str, Any]]) -> None:
        for start in range(0, len(rows), 500):
            chunk = rows[start:start + 500]
            params: Dict[str, Any] = {}
            tuples = []
            for i, row in enumerate(chunk):
                for column in _COLUMNS:
                    params[f"{column}_{i}"] = row.get(column)
                tuples.append("(" + ", ".join(f"%({c}_{i})s" for c in _COLUMNS) + ")")
            await self.db.execute_update(f"INSERT INTO pipeline_dlq_mt ({', '.join(_COLUMNS)}) VALUES "
                                         + ", ".join(tuples), params)

    async def add(self, tenant_id: str, entries: Sequence[Dict[str, Any]]) -> None:
        version = _time.time_ns() // 1000
        await self._insert([{**e, "tenant_id": tenant_id, "event": json.dumps(e["event"], default=str),
                             "failed_at": _ms(e["failed_at"]), "status": "pending", "resolved_at": None,
                             "resolved_by": "", "version": version} for e in entries])

    @staticmethod
    def _public(row: Dict[str, Any]) -> Dict[str, Any]:
        out = {k: row.get(k) for k in _COLUMNS if k not in ("tenant_id", "version")}
        try:
            out["event"] = json.loads(row.get("event") or "{}")
        except ValueError:
            out["event"] = {"msg": row.get("event")}
        for key in ("failed_at", "resolved_at"):
            if isinstance(out.get(key), datetime):
                out[key] = out[key].replace(tzinfo=out[key].tzinfo or timezone.utc).isoformat()
        return out

    async def list(self, tenant_id: str, pipeline_id: Optional[str] = None, status: Optional[str] = "pending",
                   limit: int = 100, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        where = ["tenant_id = %(tenant_id)s"]
        params: Dict[str, Any] = {"tenant_id": tenant_id, "limit": limit, "offset": offset}
        if pipeline_id:
            where.append("pipeline_id = %(pipeline_id)s")
            params["pipeline_id"] = pipeline_id
        if status:
            where.append("status = %(status)s")
            params["status"] = status
        clause = " AND ".join(where)
        rows = await self.db.fetch_all(f"SELECT * FROM pipeline_dlq_mt FINAL WHERE {clause} ORDER BY failed_at DESC "
                                       "LIMIT %(limit)s OFFSET %(offset)s", params)
        total = await self.db.fetch_all(f"SELECT count() AS n FROM pipeline_dlq_mt FINAL WHERE {clause}", params)
        return [self._public(r) for r in rows or []], int((total or [{}])[0].get("n", 0))

    async def get_many(self, tenant_id: str, ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not ids:
            return []
        rows = await self.db.fetch_all("SELECT * FROM pipeline_dlq_mt FINAL WHERE tenant_id = %(tenant_id)s "
                                       "AND id IN %(ids)s", {"tenant_id": tenant_id, "ids": list(ids)})
        return [self._public(r) for r in rows or []]

    async def counts(self, tenant_id: str) -> Dict[str, Dict[str, int]]:
        rows = await self.db.fetch_all("SELECT pipeline_id, status, count() AS n FROM pipeline_dlq_mt FINAL "
                                       "WHERE tenant_id = %(tenant_id)s GROUP BY pipeline_id, status",
                                       {"tenant_id": tenant_id})
        out: Dict[str, Dict[str, int]] = {}
        for row in rows or []:
            out.setdefault(row["pipeline_id"], {s: 0 for s in STATUSES})[row["status"]] = int(row["n"])
        return out

    async def resolve(self, tenant_id: str, entries: Sequence[Dict[str, Any]], status: str, actor: str,
                      now: Optional[datetime] = None) -> None:
        if status not in ("replayed", "discarded"):
            raise ValueError(status)
        now = now or datetime.now(timezone.utc)
        version = _time.time_ns() // 1000
        await self._insert([{**e, "tenant_id": tenant_id, "event": json.dumps(e["event"], default=str),
                             "failed_at": _ms(e["failed_at"]), "status": status, "resolved_at": _ms(now),
                             "resolved_by": actor, "version": version} for e in entries])

    async def resolve_pending_again(self, tenant_id: str, entries: Sequence[Dict[str, Any]]) -> None:
        """Undo a status change (a replay that could not be submitted)."""
        version = _time.time_ns() // 1000
        await self._insert([{**e, "tenant_id": tenant_id, "event": json.dumps(e["event"], default=str),
                             "failed_at": _ms(e["failed_at"]), "status": "pending", "resolved_at": None,
                             "resolved_by": "", "version": version} for e in entries])
