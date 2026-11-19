"""
Pack adapters (Phase 7): how the pack manager reads, writes and deletes each
kind of object for a tenant, and the store of install manifests.

`current` returns the stored object in a stable form (or None). The manager
hashes it right after writing and again later; a different hash means the
tenant changed the object.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pack_manager import Manifest

logger = logging.getLogger(__name__)


def _actor_for(pack) -> str:
    return f"pack:{pack.id}"


class LookupAdapter:
    kind = "lookup"

    def __init__(self, dao=None):
        from lookup_tables import LookupDAO

        self.dao = dao or LookupDAO()

    async def prepare(self, tenant_id, pack):
        pass

    async def current(self, tenant_id, key, ref):
        table = await self.dao.get(tenant_id, key)
        if table is None:
            return None
        return {"columns": table.columns, "key": table.key, "rows": await self.dao.all_rows(tenant_id, table)}

    async def write(self, tenant_id, key, definition, ref, pack):
        await self.dao.save(tenant_id, key, "csv", definition["columns"], definition["key"], definition["rows"],
                            f"From the {pack.name} pack", _actor_for(pack))
        return key

    async def delete(self, tenant_id, key, ref):
        await self.dao.delete(tenant_id, key, "pack-manager")


class PipelineAdapter:
    kind = "pipeline"

    def __init__(self, registry=None):
        from pipeline_store import get_pipeline_registry

        self.registry = registry or get_pipeline_registry()

    async def prepare(self, tenant_id, pack):
        pass

    async def current(self, tenant_id, key, ref):
        record = await self.registry.dao.get(tenant_id, key)
        if record is None:
            return None
        return {"name": record.name, "description": record.description, "routing": record.routing,
                "enabled": record.enabled, **record.definition()}

    async def write(self, tenant_id, key, definition, ref, pack):
        from pipeline_store import PipelineRecord

        record = PipelineRecord.from_dict({**definition, "id": key})
        await self.registry.dao.save(tenant_id, record, _actor_for(pack))
        return key

    async def delete(self, tenant_id, key, ref):
        await self.registry.dao.delete(tenant_id, key, "pack-manager")

    async def finish(self, tenant_id):
        self.registry.invalidate(tenant_id)


class RuleAdapter:
    """Pack rules are gated together (correlations may reference each other)
    and stored in sigma_rules_mt as created_by = pack:<id>."""

    kind = "rule"

    def __init__(self, db=None):
        if db is None:
            from database_layer import DatabaseLayer

            db = DatabaseLayer("SecurityDAO", os.getenv("SECURITY_SERVICE_KEY", "security-dao-service-key"))
        self.db = db
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.touched = False

    async def prepare(self, tenant_id, pack):
        from detection_as_code import _gate

        if not pack.rules:
            return
        rows, rejected = _gate(tenant_id, list(pack.rules))
        if rejected:
            raise ValueError("; ".join(f"{r['rule']}: {r['reason']}" for r in rejected))
        for row in rows:
            row["created_by"] = _actor_for(pack)
            self.rows[row["id"]] = row

    async def _row(self, tenant_id, key):
        found = await self.db.fetch_all(
            "SELECT id, name, description, rule_content, severity, is_enabled, created_by FROM sigma_rules_mt "
            "WHERE customer_id = %(customer_id)s AND id = %(id)s ORDER BY updated_at DESC LIMIT 1",
            {"customer_id": tenant_id, "id": key}) or []
        return found[0] if found else None

    async def current(self, tenant_id, key, ref):
        row = await self._row(tenant_id, key)
        if row is None:
            return None
        return {k: row.get(k) for k in ("name", "description", "rule_content", "severity", "is_enabled",
                                        "created_by")}

    async def write(self, tenant_id, key, definition, ref, pack):
        from mitre_default_loader import MitreDefaultLoader

        writer = MitreDefaultLoader.__new__(MitreDefaultLoader)
        writer.database = self.db
        row = self.rows[key]
        if await self._row(tenant_id, key) is None:
            await writer._insert_default_sigma_rule(row)
        else:
            await writer._update_default_sigma_rule(row)
        self.touched = True
        return key

    async def delete(self, tenant_id, key, ref):
        await self.db.execute_update(
            "ALTER TABLE sigma_rules_mt DELETE WHERE customer_id = %(customer_id)s AND id = %(id)s "
            "AND startsWith(created_by, 'pack:') SETTINGS mutations_sync = 2", {"customer_id": tenant_id, "id": key})
        self.touched = True

    async def finish(self, tenant_id):
        if self.touched:
            try:
                from events.management.cache.sigma_rule_cache import SigmaRuleCache

                await SigmaRuleCache().invalidate_customer_cache(tenant_id)
            except Exception as e:  # the cache expires on its own; installs must not fail on it
                logger.warning(f"Could not refresh the rule cache for {tenant_id}: {e}")


class SearchAdapter:
    kind = "search"

    def __init__(self, store=None):
        from saved_searches import SearchStore

        self.store = store or SearchStore()

    async def prepare(self, tenant_id, pack):
        pass

    async def current(self, tenant_id, key, ref):
        search = await self.store.get(tenant_id, key)
        if search is None:
            return None
        return {"name": search.name, "description": search.description, "enabled": search.enabled,
                **search.definition()}

    async def write(self, tenant_id, key, definition, ref, pack):
        from saved_searches import SavedSearch

        await self.store.save(tenant_id, SavedSearch.from_dict({**definition, "id": key}), _actor_for(pack))
        return key

    async def delete(self, tenant_id, key, ref):
        await self.store.delete(tenant_id, key, "pack-manager")


class DashboardAdapter:
    """Dashboards are keyed by name in a pack; the stored dashboard's id is the ref."""

    kind = "dashboard"

    def __init__(self, service=None):
        from services.dashboard_service import DashboardService

        self.service = service or DashboardService()

    async def prepare(self, tenant_id, pack):
        pass

    async def _find(self, tenant_id, name):
        for d in await self.service.dashboard_dao.list_dashboards(tenant_id, limit=500) or []:
            if d.get("name") == name:
                return d.get("id") or d.get("dashboard_id")
        return None

    @staticmethod
    def _normal(dashboard):
        widgets = sorted(dashboard.get("widgets") or [], key=lambda w: (w.get("position") or {}).get("x", 0))
        return {"name": dashboard.get("name"), "description": dashboard.get("description", ""),
                "variables": dashboard.get("filters") or [],
                "panels": [{"name": w.get("name"), "type": w.get("type"),
                            "query": (w.get("query_definition") or {}).get("logql"), "size": w.get("size")}
                           for w in widgets]}

    async def current(self, tenant_id, key, ref):
        ref = ref or await self._find(tenant_id, key)
        if not ref:
            return None
        dashboard = await self.service.get_dashboard(ref, tenant_id)
        return self._normal(dashboard) if dashboard else None

    async def _widgets(self, tenant_id, dashboard_id, definition):
        for i, panel in enumerate(definition["panels"]):
            await self.service.create_widget({
                "dashboard_id": dashboard_id, "customer_id": tenant_id, "name": panel["name"], "type": panel["type"],
                "query_definition": {"logql": panel["query"]}, "size": panel["size"], "position": {"x": i, "y": 0},
                "refresh_interval": 300})

    async def write(self, tenant_id, key, definition, ref, pack):
        if ref and await self.service.get_dashboard(ref, tenant_id):
            await self.service.update_dashboard(ref, tenant_id, {"name": definition["name"],
                                                                 "description": definition["description"],
                                                                 "filters": definition["variables"]})
            existing = await self.service.get_dashboard(ref, tenant_id)
            for widget in existing.get("widgets") or []:
                await self.service.delete_widget(widget["id"], tenant_id)
            await self._widgets(tenant_id, ref, definition)
            return ref
        created = await self.service.create_dashboard({
            "customer_id": tenant_id, "name": definition["name"], "description": definition["description"],
            "filters": definition["variables"], "layout": {"columns": 4}, "tags": [f"pack:{pack.id}"],
            "created_by": _actor_for(pack)})
        dashboard_id = created["dashboard_id"]
        await self._widgets(tenant_id, dashboard_id, definition)
        return dashboard_id

    async def delete(self, tenant_id, key, ref):
        ref = ref or await self._find(tenant_id, key)
        if ref:
            await self.service.delete_dashboard(ref, tenant_id)


def default_adapters() -> Dict[str, Any]:
    return {"lookup": LookupAdapter(), "pipeline": PipelineAdapter(), "rule": RuleAdapter(),
            "search": SearchAdapter(), "dashboard": DashboardAdapter()}


class PackStore:
    """Install manifests in pack_installs_mt (migration 024)."""

    def __init__(self, db=None):
        if db is None:
            from database_layer import DatabaseLayer

            db = DatabaseLayer("PackStore", os.getenv("PACK_STORE_SERVICE_KEY", "pack-store-service-key"))
        self.db = db

    async def _latest(self, tenant_id: str, pack_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        where = "tenant_id = %(tenant_id)s"
        if pack_id:
            where += " AND pack_id = %(pack_id)s"
            params["pack_id"] = pack_id
        return await self.db.fetch_all(
            f"SELECT * FROM pack_installs_mt WHERE {where} ORDER BY pack_id, seq DESC LIMIT 1 BY pack_id",
            params) or []

    @staticmethod
    def _manifest(row) -> Manifest:
        return Manifest(pack_id=row["pack_id"], version=row["version"], objects=json.loads(row["objects"] or "{}"),
                        installed_at=row.get("installed_at"), installed_by=row.get("installed_by", ""))

    async def list(self, tenant_id: str) -> List[Manifest]:
        return [self._manifest(r) for r in await self._latest(tenant_id) if not r.get("removed")]

    async def get(self, tenant_id: str, pack_id: str) -> Optional[Manifest]:
        rows = await self._latest(tenant_id, pack_id)
        return self._manifest(rows[0]) if rows and not rows[0].get("removed") else None

    async def save(self, tenant_id: str, manifest: Manifest, removed: bool = False) -> None:
        now = datetime.now(timezone.utc)
        await self.db.insert_rows("pack_installs_mt", [[
            tenant_id, manifest.pack_id, int(now.timestamp() * 1_000_000), manifest.version,
            json.dumps(manifest.objects), int(removed), manifest.installed_at or now, manifest.installed_by]],
            ["tenant_id", "pack_id", "seq", "version", "objects", "removed", "installed_at", "installed_by"])
