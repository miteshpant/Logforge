"""
AI storage (Phase 8, migration 025): tenant settings (ai_settings_mt, latest
row wins) and the audit log (ai_audit_mt, TTL from config/ai.yml).
"""

from __future__ import annotations

import builtins
import json
import os
from datetime import datetime, timezone
from typing import Any

AUDIT_COLUMNS = ["tenant_id", "request_id", "seq", "ts", "user_id", "feature", "kind", "provider", "model",
                 "external", "content", "input_tokens", "output_tokens"]


def _db():
    from database_layer import DatabaseLayer

    return DatabaseLayer("AIStore", os.getenv("AI_STORE_SERVICE_KEY", "ai-store-service-key"))


class SettingsStore:
    def __init__(self, db=None):
        self.db = db or _db()

    async def get(self, tenant_id: str) -> dict[str, Any] | None:
        rows = await self.db.fetch_all(
            "SELECT settings FROM ai_settings_mt WHERE tenant_id = %(t)s ORDER BY seq DESC LIMIT 1",
            {"t": tenant_id}) or []
        return json.loads(rows[0]["settings"]) if rows else None

    async def save(self, tenant_id: str, settings: dict[str, Any], actor: str) -> None:
        now = datetime.now(timezone.utc)
        await self.db.insert_rows("ai_settings_mt", [[tenant_id, int(now.timestamp() * 1_000_000),
                                                      json.dumps(settings), now, actor]],
                                  ["tenant_id", "seq", "settings", "updated_at", "updated_by"])


class AuditStore:
    _retention_applied: int | None = None

    def __init__(self, db=None):
        self.db = db or _db()

    async def apply_retention(self, days: int) -> None:
        """Set the audit TTL to the configured retention (once per process)."""
        if AuditStore._retention_applied == days:
            return
        await self.db.execute_update(
            f"ALTER TABLE ai_audit_mt MODIFY TTL toDateTime(ts) + INTERVAL {int(days)} DAY", {})
        AuditStore._retention_applied = days

    async def record(self, rows: builtins.list[dict[str, Any]]) -> None:
        if rows:
            await self.db.insert_rows("ai_audit_mt", [[r[c] for c in AUDIT_COLUMNS] for r in rows], AUDIT_COLUMNS)

    async def list(self, tenant_id: str, request_id: str | None = None, limit: int = 200) -> builtins.list[dict[str, Any]]:
        where, params = "tenant_id = %(t)s", {"t": tenant_id, "limit": int(limit)}
        if request_id:
            where += " AND request_id = %(r)s"
            params["r"] = request_id
        rows = await self.db.fetch_all(
            f"SELECT * FROM (SELECT * FROM ai_audit_mt WHERE {where} ORDER BY ts DESC, request_id, seq DESC "
            f"LIMIT %(limit)s) ORDER BY ts, request_id, seq", params) or []
        return [dict(r) for r in rows]

    async def usage(self, tenant_id: str, since: datetime) -> dict[str, int]:
        rows = await self.db.fetch_all(
            "SELECT sum(input_tokens + output_tokens) AS tokens, uniqExact(request_id) AS requests "
            "FROM ai_audit_mt WHERE tenant_id = %(t)s AND ts >= %(since)s", {"t": tenant_id, "since": since}) or []
        row = rows[0] if rows else {}
        return {"tokens": int(row.get("tokens") or 0), "requests": int(row.get("requests") or 0)}
