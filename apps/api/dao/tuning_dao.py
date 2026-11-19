"""
Detection tuning records (exclusions, throttles) per tenant, in
detection_tuning_mt (ReplacingMergeTree: each change is a new row version,
deletes are tombstones). Also reads a rule's detections by analyst verdict,
for exclusion suggestions.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from database_layer import DatabaseLayer
from detection_tuning import validate_record

logger = structlog.get_logger(__name__)

_FIELDS = "id, rule_id, kind, spec, reason, created_by, created_at, updated_at"


def _ms(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class TuningDAO:
    def __init__(self):
        self.db = DatabaseLayer("TuningDAO", os.getenv("TUNING_SERVICE_KEY", "tuning-dao-service-key"))

    @staticmethod
    def _decode(row: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(row)
        try:
            record["spec"] = json.loads(row.get("spec") or "{}")
        except ValueError:
            record["spec"] = {}
        for key in ("created_at", "updated_at"):
            if isinstance(record.get(key), datetime):
                record[key] = record[key].isoformat()
        return record

    async def list_records(self, tenant_id: str) -> List[Dict[str, Any]]:
        rows = await self.db.fetch_all(
            f"SELECT {_FIELDS} FROM detection_tuning_mt FINAL "
            "WHERE tenant_id = %(tenant_id)s AND deleted = 0 ORDER BY created_at",
            {"tenant_id": tenant_id})
        return [self._decode(r) for r in rows or []]

    async def _get(self, tenant_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        rows = await self.db.fetch_all(
            f"SELECT {_FIELDS} FROM detection_tuning_mt FINAL "
            "WHERE tenant_id = %(tenant_id)s AND id = %(id)s AND deleted = 0",
            {"tenant_id": tenant_id, "id": record_id})
        return rows[0] if rows else None

    async def _write(self, tenant_id: str, record: Dict[str, Any], deleted: int) -> Dict[str, Any]:
        params = {
            "tenant_id": tenant_id,
            "id": record["id"],
            "rule_id": str(record["rule_id"]),
            "kind": record["kind"],
            "spec": record["spec"] if isinstance(record["spec"], str) else json.dumps(record["spec"]),
            "reason": str(record.get("reason") or ""),
            "created_by": str(record.get("created_by") or ""),
            "created_at": record["created_at"] if isinstance(record["created_at"], str) else _ms(record["created_at"]),
            "updated_at": _ms(datetime.now(timezone.utc)),
            "deleted": deleted,
        }
        await self.db.execute_update(
            "INSERT INTO detection_tuning_mt (tenant_id, id, rule_id, kind, spec, reason, created_by, "
            "created_at, updated_at, deleted) VALUES (%(tenant_id)s, %(id)s, %(rule_id)s, %(kind)s, %(spec)s, "
            "%(reason)s, %(created_by)s, %(created_at)s, %(updated_at)s, %(deleted)s)", params)
        return params

    async def create(self, tenant_id: str, record: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        spec = validate_record(record)
        now = datetime.now(timezone.utc)
        stored = await self._write(tenant_id, {
            "id": str(uuid.uuid4()), "rule_id": record["rule_id"], "kind": record["kind"], "spec": spec,
            "reason": record.get("reason"), "created_by": user_id, "created_at": now}, deleted=0)
        return self._decode({k: stored[k] for k in _FIELDS.split(", ")})

    async def delete(self, tenant_id: str, record_id: str) -> bool:
        existing = await self._get(tenant_id, record_id)
        if existing is None:
            return False
        if isinstance(existing.get("created_at"), datetime):
            existing["created_at"] = _ms(existing["created_at"])
        await self._write(tenant_id, existing, deleted=1)
        return True

    async def detections_by_verdict(self, tenant_id: str, rule_id: str, days: int = 30,
                                    limit: int = 500) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """(events marked false positive, the rule's other events), newest first."""
        rows = await self.db.fetch_all(
            "SELECT status, raw_log_data FROM security_events_mt "
            "WHERE customer_id = %(tenant_id)s AND rule_id = %(rule_id)s "
            "AND created_at >= now64(3) - toIntervalDay(%(days)s) "
            "ORDER BY created_at DESC LIMIT %(limit)s",
            {"tenant_id": tenant_id, "rule_id": rule_id, "days": days, "limit": limit})
        false_positives, others = [], []
        for row in rows or []:
            try:
                data = json.loads(row.get("raw_log_data") or "")
            except ValueError:
                continue
            if isinstance(data, dict) and isinstance(data.get("normalized_log"), dict):
                data = data["normalized_log"]
            if not isinstance(data, dict):
                continue
            (false_positives if str(row.get("status")) == "false_positive" else others).append(data)
        return false_positives, others
