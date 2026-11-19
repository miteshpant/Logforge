"""
Pack manager (Phase 7): install, upgrade and remove a source pack for a
tenant, keeping the tenant's own changes.

An install is recorded as a manifest: for every object (kind:key), the hash
of the pack's definition, the hash of what was stored (read back after
writing) and a reference to the stored object. On upgrade, an object whose
stored hash no longer matches was changed by the tenant and is kept as it
is (unless forced); an object the tenant deleted is not recreated; an object
with the same name that this pack did not create is a conflict and is left
alone. Removing a pack deletes only the objects the tenant has not changed.

Objects are written through adapters (pack_adapters.py), one per kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from source_packs import canonical_hash

KINDS = ("lookup", "pipeline", "rule", "search", "dashboard")  # install order: lookups before what uses them
ACTIONS = ("create", "update", "unchanged", "keep_local", "deleted", "conflict", "remove")


@dataclass
class Manifest:
    pack_id: str
    version: str
    objects: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # key -> {pack_hash, installed_hash, ref}
    installed_at: Optional[datetime] = None
    installed_by: str = ""

    def to_public(self) -> Dict[str, Any]:
        return {"pack": self.pack_id, "version": self.version, "objects": sorted(self.objects),
                "installed_at": self.installed_at.isoformat() if isinstance(self.installed_at, datetime)
                else self.installed_at, "installed_by": self.installed_by}


@dataclass
class Action:
    key: str
    kind: str
    name: str
    reason: str
    definition: Any = None
    previous: Optional[Dict[str, Any]] = None

    def to_public(self) -> Dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "name": self.name, "reason": self.reason}


@dataclass
class Plan:
    pack: Any
    manifest: Optional[Manifest]
    actions: Dict[str, List[Action]] = field(default_factory=lambda: {a: [] for a in ACTIONS})

    def counts(self) -> Dict[str, int]:
        return {a: len(v) for a, v in self.actions.items()}

    def to_public(self) -> Dict[str, Any]:
        return {"pack": self.pack.id, "from_version": self.manifest.version if self.manifest else None,
                "to_version": self.pack.version, "counts": self.counts(),
                "actions": {a: [x.to_public() for x in v] for a, v in self.actions.items()}}


def _ordered(keys):
    return sorted(keys, key=lambda k: (KINDS.index(k.split(":", 1)[0]) if k.split(":", 1)[0] in KINDS else 99, k))


async def plan(pack, manifest: Optional[Manifest], adapters: Dict[str, Any], tenant_id: str,
               force: bool = False) -> Plan:
    result = Plan(pack=pack, manifest=manifest)
    for adapter in adapters.values():
        await adapter.prepare(tenant_id, pack)
    objects = pack.objects()
    previous = manifest.objects if manifest else {}
    for key in _ordered(objects):
        kind, name = key.split(":", 1)
        adapter = adapters[kind]
        definition = objects[key]
        prev = previous.get(key)
        current = await adapter.current(tenant_id, name, prev.get("ref") if prev else None)
        pack_hash = canonical_hash(definition)
        if prev is None:
            if current is not None:
                result.actions["conflict"].append(Action(key, kind, name, "exists, and this pack did not create it"))
            else:
                result.actions["create"].append(Action(key, kind, name, f"new in {pack.version}", definition))
            continue
        changed = current is not None and canonical_hash(current) != prev["installed_hash"]
        if current is None:
            if force:
                result.actions["create"].append(Action(key, kind, name, "deleted locally; recreated (force)",
                                                       definition, prev))
            else:
                result.actions["deleted"].append(Action(key, kind, name, "deleted locally; not recreated", None,
                                                        prev))
        elif changed and not force:
            result.actions["keep_local"].append(Action(key, kind, name, "changed locally; kept", None, prev))
        elif pack_hash == prev["pack_hash"] and not changed:
            result.actions["unchanged"].append(Action(key, kind, name, "no change", None, prev))
        else:
            reason = "changed locally; overwritten (force)" if changed else f"updated in {pack.version}"
            result.actions["update"].append(Action(key, kind, name, reason, definition, prev))
    for key in _ordered(k for k in previous if k not in objects):
        kind, name = key.split(":", 1)
        prev = previous[key]
        current = await adapters[kind].current(tenant_id, name, prev.get("ref"))
        if current is None:
            continue
        if canonical_hash(current) != prev["installed_hash"] and not force:
            result.actions["keep_local"].append(Action(key, kind, name,
                                                       f"dropped in {pack.version}, changed locally; kept"))
        else:
            result.actions["remove"].append(Action(key, kind, name, f"dropped in {pack.version}", None, prev))
    return result


async def apply(plan_: Plan, adapters: Dict[str, Any], tenant_id: str, actor: str = "",
                now: Optional[datetime] = None) -> Manifest:
    manifest = Manifest(pack_id=plan_.pack.id, version=plan_.pack.version, installed_at=now or datetime.now(
        timezone.utc), installed_by=actor)
    for action in plan_.actions["create"] + plan_.actions["update"]:
        adapter = adapters[action.kind]
        ref = (action.previous or {}).get("ref")
        ref = await adapter.write(tenant_id, action.name, action.definition, ref, plan_.pack)
        stored = await adapter.current(tenant_id, action.name, ref)
        manifest.objects[action.key] = {"pack_hash": canonical_hash(action.definition),
                                        "installed_hash": canonical_hash(stored), "ref": ref}
    for name in ("unchanged", "keep_local", "deleted"):
        for action in plan_.actions[name]:
            if action.previous is not None:
                manifest.objects[action.key] = dict(action.previous)
    for action in plan_.actions["remove"]:
        await adapters[action.kind].delete(tenant_id, action.name, (action.previous or {}).get("ref"))
    for adapter in adapters.values():
        finish = getattr(adapter, "finish", None)
        if finish is not None:
            await finish(tenant_id)
    return manifest


async def uninstall(manifest: Manifest, adapters: Dict[str, Any], tenant_id: str) -> Dict[str, List[str]]:
    """Delete the objects the tenant has not changed; keep (and report) the rest."""
    removed, kept = [], []
    for key in reversed(_ordered(manifest.objects)):
        kind, name = key.split(":", 1)
        entry = manifest.objects[key]
        current = await adapters[kind].current(tenant_id, name, entry.get("ref"))
        if current is None:
            continue
        if canonical_hash(current) != entry["installed_hash"]:
            kept.append(key)
            continue
        await adapters[kind].delete(tenant_id, name, entry.get("ref"))
        removed.append(key)
    for adapter in adapters.values():
        finish = getattr(adapter, "finish", None)
        if finish is not None:
            await finish(tenant_id)
    return {"removed": sorted(removed), "kept": sorted(kept)}
