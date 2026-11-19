"""
Pipeline storage, routing and the per-tenant registry (Phase 4).

Storage: ingest_pipelines_mt keeps every saved version of every pipeline
(MergeTree ordered by tenant, pipeline, version); the latest version is the
current one and a delete is a tombstone version. So the history of a
pipeline is always available (GET /v1/pipelines/{id}/versions).

Routing (PipelineRouter.select): the pipeline named by the shipper wins;
otherwise the first enabled pipeline by priority whose `services` contain
the event's service or whose `if` condition is true; otherwise the tenant's
default pipeline.

PipelineRegistry caches each tenant's compiled pipelines for a short TTL
and is invalidated by the API on every change; it also holds the per-
pipeline stats (pipelines.PipelineStats), keyed by pipeline version.
"""

from __future__ import annotations

import json
import re
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from pipeline_conditions import ConditionError, compile_condition
from pipelines import Pipeline, PipelineError, PipelineStats

logger = structlog.get_logger(__name__)

_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
_COLUMNS = ("tenant_id", "pipeline_id", "version", "name", "description", "definition", "routing", "enabled",
            "deleted", "updated_at", "updated_by")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", name.strip().lower()).strip("-")[:64]


def _ms(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


@dataclass
class PipelineRecord:
    id: str
    name: str
    pipeline: Pipeline
    description: str = ""
    routing: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    version: int = 0
    updated_at: Optional[datetime] = None
    updated_by: str = ""
    builtin: bool = False
    _condition: Any = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineRecord":
        pipeline = Pipeline.from_dict(data)
        pid = str(data.get("id") or slug(pipeline.name))
        if not _ID.fullmatch(pid):
            raise PipelineError("id must be lowercase letters, digits, . _ or - (max 64)")
        routing = _routing(data.get("routing") or {})
        record = cls(id=pid, name=pipeline.name, pipeline=pipeline, description=pipeline.description, routing=routing,
                     enabled=bool(data.get("enabled", True)), version=int(data.get("version") or 0),
                     updated_at=data.get("updated_at"), updated_by=str(data.get("updated_by") or ""),
                     builtin=bool(data.get("builtin", False)))
        record._condition = compile_condition(routing["if"]) if routing["if"] else None
        return record

    def definition(self) -> Dict[str, Any]:
        d = self.pipeline.to_dict()
        return {"processors": d["processors"], "on_failure": d.get("on_failure", [])}

    def to_public(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "description": self.description, "enabled": self.enabled,
                "routing": self.routing, "version": self.version, "builtin": self.builtin,
                "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
                "updated_by": self.updated_by, **self.definition()}

    def matches(self, doc: Dict[str, Any]) -> bool:
        services = self.routing.get("services") or []
        if services and str(doc.get("service") or "").lower() in services:
            return True
        if self._condition is not None:
            try:
                return self._condition(doc)
            except ConditionError:
                return False
        return False


def _routing(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise PipelineError("routing must be an object")
    services = raw.get("services") or []
    if not isinstance(services, list) or not all(isinstance(s, str) and s.strip() for s in services):
        raise PipelineError("routing.services must be a list of service names")
    condition = str(raw.get("if") or "")
    if condition:
        try:
            compile_condition(condition)
        except ConditionError as e:
            raise PipelineError(f"routing.if: {e}") from None
    try:
        priority = int(raw.get("priority", 100))
    except (TypeError, ValueError):
        raise PipelineError("routing.priority must be a number") from None
    return {"services": [s.strip().lower() for s in services], "if": condition, "priority": priority,
            "default": bool(raw.get("default", False))}


class PipelineRouter:
    def __init__(self, records: List[PipelineRecord]):
        self.by_id = {r.id: r for r in records}
        self.ordered = sorted((r for r in records if r.enabled and not r.routing.get("default")),
                              key=lambda r: (r.routing.get("priority", 100), r.id))
        defaults = sorted((r for r in records if r.enabled and r.routing.get("default")),
                          key=lambda r: (r.routing.get("priority", 100), r.id))
        self.default = defaults[0] if defaults else None

    def get(self, pipeline_id: str) -> Optional[PipelineRecord]:
        return self.by_id.get(pipeline_id)

    def select(self, doc: Dict[str, Any], requested: Optional[str] = None) -> Optional[PipelineRecord]:
        if requested:
            record = self.by_id.get(requested)
            return record if record and record.enabled else None
        for record in self.ordered:
            if record.matches(doc):
                return record
        return self.default

    def __bool__(self) -> bool:
        return bool(self.by_id)


class PipelineDAO:
    def __init__(self, db=None):
        if db is None:
            import os

            from database_layer import DatabaseLayer

            db = DatabaseLayer("PipelineDAO", os.getenv("PIPELINE_SERVICE_KEY", "pipeline-dao-service-key"))
        self.db = db

    async def _insert(self, row: Dict[str, Any]) -> None:
        await self.db.execute_update(
            f"INSERT INTO ingest_pipelines_mt ({', '.join(_COLUMNS)}) VALUES ("
            + ", ".join(f"%({c})s" for c in _COLUMNS) + ")", row)

    async def _latest(self, tenant_id: str, pipeline_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        where = "tenant_id = %(tenant_id)s"
        if pipeline_id:
            where += " AND pipeline_id = %(pipeline_id)s"
            params["pipeline_id"] = pipeline_id
        return await self.db.fetch_all(
            f"SELECT * FROM ingest_pipelines_mt WHERE {where} ORDER BY pipeline_id, version DESC "
            "LIMIT 1 BY pipeline_id", params) or []

    @staticmethod
    def _record(row: Dict[str, Any]) -> Optional[PipelineRecord]:
        try:
            definition = json.loads(row["definition"]) if isinstance(row["definition"], str) else row["definition"]
            routing = json.loads(row["routing"]) if isinstance(row["routing"], str) else row["routing"]
            return PipelineRecord.from_dict({**definition, "id": row["pipeline_id"], "name": row["name"],
                                             "description": row.get("description", ""), "routing": routing,
                                             "enabled": bool(row["enabled"]), "version": row["version"],
                                             "updated_at": row.get("updated_at"),
                                             "updated_by": row.get("updated_by", "")})
        except (PipelineError, ValueError, KeyError, TypeError) as e:
            logger.warning(f"Skipping invalid stored pipeline {row.get('pipeline_id')}: {e}")
            return None

    async def list(self, tenant_id: str) -> List[PipelineRecord]:
        records = [self._record(r) for r in await self._latest(tenant_id) if not r.get("deleted")]
        return sorted((r for r in records if r), key=lambda r: r.id)

    async def get(self, tenant_id: str, pipeline_id: str) -> Optional[PipelineRecord]:
        rows = await self._latest(tenant_id, pipeline_id)
        if not rows or rows[0].get("deleted"):
            return None
        return self._record(rows[0])

    async def versions(self, tenant_id: str, pipeline_id: str) -> List[PipelineRecord]:
        rows = await self.db.fetch_all(
            "SELECT * FROM ingest_pipelines_mt WHERE tenant_id = %(tenant_id)s AND pipeline_id = %(pipeline_id)s "
            "ORDER BY version DESC LIMIT 100", {"tenant_id": tenant_id, "pipeline_id": pipeline_id}) or []
        return [r for r in (self._record(row) for row in rows if not row.get("deleted")) if r]

    async def _next_version(self, tenant_id: str, pipeline_id: str) -> int:
        rows = await self._latest(tenant_id, pipeline_id)
        return int(rows[0]["version"]) + 1 if rows else 1

    async def save(self, tenant_id: str, record: PipelineRecord, actor: str, now: Optional[datetime] = None
                   ) -> PipelineRecord:
        now = now or datetime.now(timezone.utc)
        record.version = await self._next_version(tenant_id, record.id)
        record.updated_at, record.updated_by = now, actor
        await self._insert({"tenant_id": tenant_id, "pipeline_id": record.id, "version": record.version,
                            "name": record.name, "description": record.description,
                            "definition": json.dumps(record.definition()), "routing": json.dumps(record.routing),
                            "enabled": 1 if record.enabled else 0, "deleted": 0, "updated_at": _ms(now),
                            "updated_by": actor})
        return record

    async def delete(self, tenant_id: str, pipeline_id: str, actor: str, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        await self._insert({"tenant_id": tenant_id, "pipeline_id": pipeline_id,
                            "version": await self._next_version(tenant_id, pipeline_id), "name": "", "description": "",
                            "definition": "{}", "routing": "{}", "enabled": 0, "deleted": 1, "updated_at": _ms(now),
                            "updated_by": actor})


class PipelineRegistry:
    """Each tenant's router (tenant pipelines over built-ins), cached for `ttl_seconds`."""

    def __init__(self, dao=None, ttl_seconds: int = 30, builtins: Optional[Dict[str, PipelineRecord]] = None):
        self._dao = dao
        self.ttl = ttl_seconds
        self._builtins = builtins
        self._routers: Dict[str, Tuple[float, PipelineRouter]] = {}
        self._stats: Dict[Tuple[str, str, int], PipelineStats] = {}

    @property
    def dao(self):
        if self._dao is None:
            self._dao = PipelineDAO()
        return self._dao

    def builtins(self) -> Dict[str, PipelineRecord]:
        if self._builtins is None:
            from builtin_pipelines import builtin_records

            self._builtins = builtin_records()
        return self._builtins

    async def router(self, tenant_id: str) -> PipelineRouter:
        cached = self._routers.get(tenant_id)
        if cached and _time.monotonic() - cached[0] < self.ttl:
            return cached[1]
        records = dict(self.builtins())
        try:
            tenant_records = await self.dao.list(tenant_id)
        except Exception:
            if cached:  # storage is down: keep routing with what we had
                logger.warning(f"Pipelines of {tenant_id} could not be reloaded; using the cached set")
                self._routers[tenant_id] = (_time.monotonic(), cached[1])
                return cached[1]
            raise
        for record in tenant_records:
            records[record.id] = record
        router = PipelineRouter(list(records.values()))
        self._routers[tenant_id] = (_time.monotonic(), router)
        return router

    def invalidate(self, tenant_id: Optional[str] = None) -> None:
        if tenant_id is None:
            self._routers.clear()
        else:
            self._routers.pop(tenant_id, None)

    def stats(self, tenant_id: str, record: PipelineRecord) -> PipelineStats:
        key = (tenant_id, record.id, record.version)
        stats = self._stats.get(key)
        if stats is None:
            stats = self._stats[key] = PipelineStats()
        return stats

    def stats_for(self, tenant_id: str, pipeline_id: str) -> Dict[int, PipelineStats]:
        return {v: s for (t, p, v), s in self._stats.items() if t == tenant_id and p == pipeline_id}


_registry: Optional[PipelineRegistry] = None


def get_pipeline_registry() -> PipelineRegistry:
    global _registry
    if _registry is None:
        _registry = PipelineRegistry()
    return _registry
