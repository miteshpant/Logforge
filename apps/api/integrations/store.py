"""Integration storage (Phase 13): response_integrations_mt, secrets sealed."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from .secrets import SecretBox


class IntegrationStore:
    def __init__(self, client, box: Optional[SecretBox] = None):
        self.client = client
        self.box = box or SecretBox.from_env()

    def _rows(self, tenant_id: str, integration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        where = " AND id = {id:String}" if integration_id else ""
        params = {"tenant": tenant_id, **({"id": integration_id} if integration_id else {})}
        rows = self.client.query(
            "SELECT id, argMax(name, updated_at), argMax(kind, updated_at), argMax(config, updated_at), "
            "argMax(secrets, updated_at), argMax(enabled, updated_at), argMax(updated_by, updated_at), "
            "max(updated_at) FROM response_integrations_mt WHERE customer_id = {tenant:String}"
            f"{where} GROUP BY id HAVING argMax(deleted, updated_at) = 0 ORDER BY id",
            parameters=params).result_rows
        return [{"id": r[0], "name": r[1], "kind": r[2], "config": json.loads(r[3] or "{}"), "_secrets": r[4],
                 "enabled": bool(r[5]), "updated_by": r[6], "updated_at": str(r[7])} for r in rows]

    @staticmethod
    def public(row: Dict[str, Any], secret_names: List[str]) -> Dict[str, Any]:
        out = {k: v for k, v in row.items() if not k.startswith("_")}
        out["secrets_set"] = sorted(secret_names)
        return out

    def list(self, tenant_id: str) -> List[Dict[str, Any]]:
        return [self.public(r, list(self.box.open(r["_secrets"]))) for r in self._rows(tenant_id)]

    def get(self, tenant_id: str, integration_id: str, with_secrets: bool = False) -> Optional[Dict[str, Any]]:
        rows = self._rows(tenant_id, integration_id)
        if not rows:
            return None
        row = rows[0]
        opened = self.box.open(row["_secrets"])
        out = self.public(row, list(opened))
        if with_secrets:
            out["secrets"] = opened
        return out

    def _write(self, tenant_id: str, row: Dict[str, Any], sealed: str, user_id: str, deleted: bool = False) -> None:
        # client.insert, not a bound INSERT ... SELECT: bound String parameters can't carry newlines or tabs
        self.client.insert("response_integrations_mt", [[
            tenant_id, row["id"], row["name"], row["kind"], json.dumps(row.get("config") or {}), sealed,
            int(row.get("enabled", True)), int(deleted), user_id or ""]],
            column_names=["customer_id", "id", "name", "kind", "config", "secrets", "enabled", "deleted", "updated_by"])

    def save(self, tenant_id: str, row: Dict[str, Any], secrets: Optional[Dict[str, str]], user_id: str
             ) -> Dict[str, Any]:
        """Create (no id) or update. Secrets: names given replace, "" removes, names left out are kept."""
        existing = self.get(tenant_id, row["id"], with_secrets=True) if row.get("id") else None
        merged = dict(existing["secrets"]) if existing else {}
        for name, value in (secrets or {}).items():
            if value:
                merged[name] = value
            else:
                merged.pop(name, None)
        row = {**row, "id": row.get("id") or uuid.uuid4().hex}
        self._write(tenant_id, row, self.box.seal(merged), user_id)
        return self.public({**row, "updated_by": user_id}, list(merged))

    def merged_secrets(self, tenant_id: str, integration_id: Optional[str], secrets: Optional[Dict[str, str]]
                       ) -> Dict[str, str]:
        existing = self.get(tenant_id, integration_id, with_secrets=True) if integration_id else None
        merged = dict(existing["secrets"]) if existing else {}
        for name, value in (secrets or {}).items():
            if value:
                merged[name] = value
            else:
                merged.pop(name, None)
        return merged

    def delete(self, tenant_id: str, integration_id: str, user_id: str) -> bool:
        existing = self.get(tenant_id, integration_id)
        if not existing:
            return False
        self._write(tenant_id, existing, "", user_id, deleted=True)
        return True
