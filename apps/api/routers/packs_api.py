"""
Source packs API (Phase 7), under /v1/packs.

Reading the catalogue needs logs:read; installing, upgrading and removing
need settings:write (tenant admins), because a pack writes pipelines,
rules, saved searches and dashboards at once. Every change is planned
first; an install keeps the tenant's local changes unless ?force=true.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from authn_authz_middleware import get_current_user
from error_handling import internal_error
from models import User
import pack_manager
from source_packs import default_packs_dir, load_catalogue, version_key

router = APIRouter(prefix="/v1/packs", tags=["packs"])

_cache: Dict[str, Any] = {"key": None, "packs": [], "errors": {}}
_locks: Dict[str, asyncio.Lock] = {}


def reset_catalogue() -> None:
    _cache.update(key=None, packs=[], errors={})


def _fingerprint(root: Path) -> Tuple:
    if not root.is_dir():
        return ()
    return tuple(sorted((str(p.relative_to(root)), p.stat().st_mtime_ns, p.stat().st_size)
                        for p in root.rglob("*") if p.is_file()))


def _catalogue():
    """The packs on disk, reloaded when a pack file changes (loading gates every rule)."""
    root = default_packs_dir()
    key = (str(root), _fingerprint(root))
    if _cache["key"] != key:
        packs, errors = load_catalogue(root)
        _cache.update(key=key, packs=packs, errors=errors)
    return _cache["packs"], _cache["errors"]


def _find(pack_id: str):
    packs, _ = _catalogue()
    for pack in packs:
        if pack.id == pack_id:
            return pack
    raise HTTPException(status_code=404, detail=f"No pack {pack_id}")


def _adapters():
    from pack_adapters import default_adapters

    return default_adapters()


def _store():
    from pack_adapters import PackStore

    return PackStore()


def _actor(user) -> str:
    return getattr(user, "email", None) or getattr(user, "id", "") or ""


def _lock(tenant_id: str) -> asyncio.Lock:
    return _locks.setdefault(tenant_id, asyncio.Lock())


@router.get("")
async def list_packs(customer_id: str = Header(..., alias="X-Customer-ID")):
    packs, errors = _catalogue()
    try:
        installed = {m.pack_id: m for m in await _store().list(customer_id)}
    except Exception as e:
        raise internal_error(e, "Failed to read installed packs", customer_id=customer_id)
    out: List[Dict[str, Any]] = []
    for pack in packs:
        manifest = installed.get(pack.id)
        version = manifest.version if manifest else None
        out.append({**pack.summary(), "installed_version": version,
                    "update_available": bool(version) and version_key(pack.version) > version_key(version)})
    return {"packs": out, "errors": errors}


@router.get("/{pack_id}")
async def get_pack(pack_id: str, customer_id: str = Header(..., alias="X-Customer-ID")):
    pack = _find(pack_id)
    manifest = await _store().get(customer_id, pack_id)
    return {**pack.detail(), "installed": manifest.to_public() if manifest else None}


async def _plan(pack, customer_id: str, force: bool):
    adapters = _adapters()
    manifest = await _store().get(customer_id, pack.id)
    try:
        return adapters, await pack_manager.plan(pack, manifest, adapters, customer_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{pack_id}/plan")
async def plan_pack(pack_id: str, force: bool = Query(False), customer_id: str = Header(..., alias="X-Customer-ID")):
    pack = _find(pack_id)
    _, plan = await _plan(pack, customer_id, force)
    return plan.to_public()


@router.post("/{pack_id}/install")
async def install_pack(pack_id: str, force: bool = Query(False, description="Overwrite local changes"),
                       customer_id: str = Header(..., alias="X-Customer-ID"),
                       user: User = Depends(get_current_user)):
    pack = _find(pack_id)
    async with _lock(customer_id):
        adapters, plan = await _plan(pack, customer_id, force)
        try:
            manifest = await pack_manager.apply(plan, adapters, customer_id, actor=_actor(user))
            await _store().save(customer_id, manifest)
        except HTTPException:
            raise
        except Exception as e:
            raise internal_error(e, "Failed to install the pack", customer_id=customer_id)
    return {"plan": plan.to_public(), "installed": manifest.to_public()}


@router.delete("/{pack_id}")
async def remove_pack(pack_id: str, customer_id: str = Header(..., alias="X-Customer-ID"),
                      user: User = Depends(get_current_user)):
    async with _lock(customer_id):
        store = _store()
        manifest = await store.get(customer_id, pack_id)
        if manifest is None:
            raise HTTPException(status_code=404, detail=f"{pack_id} is not installed")
        try:
            result = await pack_manager.uninstall(manifest, _adapters(), customer_id)
            await store.save(customer_id, manifest, removed=True)
        except Exception as e:
            raise internal_error(e, "Failed to remove the pack", customer_id=customer_id)
    return {"pack": pack_id, **result}
