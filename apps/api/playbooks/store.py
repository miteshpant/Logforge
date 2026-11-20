"""Playbook and run storage (Phase 13): playbooks_mt, playbook_runs_mt."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .engine import Run


class PlaybookStore:
    def __init__(self, client):
        self.client = client

    # -- definitions ------------------------------------------------------------

    def list(self, tenant_id: str, enabled_only: bool = False) -> List[Dict[str, Any]]:
        having = " AND argMax(enabled, updated_at) = 1" if enabled_only else ""
        rows = self.client.query(
            "SELECT id, argMax(name, updated_at), argMax(definition, updated_at), argMax(enabled, updated_at), "
            "argMax(updated_by, updated_at), max(updated_at) FROM playbooks_mt WHERE customer_id = {tenant:String} "
            f"GROUP BY id HAVING argMax(deleted, updated_at) = 0{having} ORDER BY id",
            parameters={"tenant": tenant_id}).result_rows
        return [{"id": r[0], "name": r[1], "definition": r[2], "enabled": bool(r[3]), "updated_by": r[4],
                 "updated_at": str(r[5])} for r in rows]

    def get(self, tenant_id: str, playbook_id: str) -> Optional[Dict[str, Any]]:
        return next((p for p in self.list(tenant_id) if p["id"] == playbook_id), None)

    def tenants(self) -> List[str]:
        rows = self.client.query(
            "SELECT customer_id FROM (SELECT customer_id, id, argMax(enabled, updated_at) AS e, "
            "argMax(deleted, updated_at) AS d FROM playbooks_mt GROUP BY customer_id, id) "
            "WHERE e = 1 AND d = 0 GROUP BY customer_id").result_rows
        return [r[0] for r in rows]

    def save(self, tenant_id: str, name: str, definition: str, enabled: bool, user_id: str,
             playbook_id: Optional[str] = None, deleted: bool = False) -> Dict[str, Any]:
        pid = playbook_id or uuid.uuid4().hex
        # client.insert, not a bound INSERT ... SELECT: bound String parameters can't carry newlines (YAML)
        self.client.insert("playbooks_mt", [[tenant_id, pid, name, definition, int(enabled), int(deleted), user_id or ""]],
                           column_names=["customer_id", "id", "name", "definition", "enabled", "deleted", "updated_by"])
        return {"id": pid, "name": name, "definition": definition, "enabled": enabled, "updated_by": user_id}

    # -- runs ---------------------------------------------------------------------

    def save_run(self, run: Run) -> None:
        created = datetime.fromisoformat(str(run.created_at).replace("Z", "+00:00"))
        self.client.insert("playbook_runs_mt", [[
            run.tenant_id, run.id, run.playbook_id, run.trigger, run.trigger_ref, run.status,
            json.dumps(run.to_dict(), default=str), created]],
            column_names=["customer_id", "id", "playbook_id", "trigger", "trigger_ref", "status", "state", "created_at"])

    def _runs(self, tenant_id: str, where: str, params: Dict[str, Any], limit: int) -> List[Run]:
        rows = self.client.query(
            "SELECT argMax(state, updated_at) FROM playbook_runs_mt WHERE customer_id = {tenant:String} "
            f"{where} GROUP BY id ORDER BY max(created_at) DESC LIMIT {int(limit)}",
            parameters={"tenant": tenant_id, **params}).result_rows
        return [Run.from_dict(json.loads(r[0])) for r in rows]

    def get_run(self, tenant_id: str, run_id: str) -> Optional[Run]:
        runs = self._runs(tenant_id, "AND id = {id:String}", {"id": run_id}, 1)
        return runs[0] if runs else None

    def list_runs(self, tenant_id: str, status: Optional[str] = None, limit: int = 100) -> List[Run]:
        runs = self._runs(tenant_id, "", {}, limit if not status else 1000)
        return [r for r in runs if not status or r.status == status][:limit]

    def started(self, tenant_id: str, playbook_id: str, trigger_refs: List[str]) -> set:
        if not trigger_refs:
            return set()
        rows = self.client.query(
            "SELECT DISTINCT trigger_ref FROM playbook_runs_mt WHERE customer_id = {tenant:String} "
            "AND playbook_id = {playbook:String} AND trigger_ref IN {refs:Array(String)}",
            parameters={"tenant": tenant_id, "playbook": playbook_id, "refs": trigger_refs}).result_rows
        return {r[0] for r in rows}
