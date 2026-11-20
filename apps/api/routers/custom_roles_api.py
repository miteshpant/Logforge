"""
Custom roles (Phase 14), under /v1/roles/custom (roles:read / roles:write):

  GET    /v1/roles/custom                          roles, their members, and the permission vocabulary
  POST   /v1/roles/custom                          {name, description, permissions, services: null | [...],
                                                    masked_fields: [...]}
  PUT    /v1/roles/custom/{id}, DELETE /v1/roles/custom/{id}
  PUT    /v1/roles/custom/{id}/members/{user_id}   grant; DELETE to take back
  GET    /v1/auth/access                           the caller's custom roles, permissions and data scope
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from tenant_dependencies import MiddlewareTenant

import custom_roles as cr

router = APIRouter(prefix="/v1/roles/custom", tags=["roles"])
access_router = APIRouter(prefix="/v1/auth", tags=["roles"])
SERVICE = r"^[A-Za-z0-9._:/-]{1,128}\*?$"
FIELD = r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$"


class RoleBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=1000)
    permissions: List[str] = Field(default_factory=list, max_length=100)
    services: Optional[List[str]] = Field(None, max_length=200)
    masked_fields: List[str] = Field(default_factory=list, max_length=100)


def _store() -> cr.CustomRoleStore:
    from dependencies import get_clickhouse_client

    return cr.CustomRoleStore(get_clickhouse_client())


def _user(request: Request) -> str:
    return str(getattr(getattr(request.state, "user", None), "id", "") or "")


def _role(body: RoleBody, tenant_id: str, role_id: str = "") -> cr.CustomRole:
    import re

    permissions = cr.normalise(body.permissions)
    try:
        cr.validate_permissions(permissions)
    except ValueError as e:
        raise HTTPException(422, str(e))
    services = None
    if body.services is not None:
        services = sorted({s.strip() for s in body.services if s.strip()})
        bad = [s for s in services if not re.match(SERVICE, s)]
        if bad:
            raise HTTPException(422, f"{bad[0]!r} isn't a service name (letters, digits, . _ : / -, optionally ending in *)")
    masked = sorted({f.strip() for f in body.masked_fields if f.strip()})
    bad = [f for f in masked if not re.match(FIELD, f)]
    if bad:
        raise HTTPException(422, f"{bad[0]!r} isn't a field name (letters, digits, _ and dots)")
    if not permissions and services is None and not masked:
        raise HTTPException(422, "A custom role needs permissions, a data scope, masked fields, or a mix")
    return cr.CustomRole(id=role_id, tenant_id=tenant_id, name=body.name.strip(), description=body.description,
                         permissions=permissions, services=services, masked_fields=masked)


@router.get("")
async def list_roles(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    store = _store()
    roles = await asyncio.to_thread(store.list, customer_id)
    members = {r.id: await asyncio.to_thread(store.members, customer_id, r.id) for r in roles}
    return {"roles": [{**r.to_dict(), "members": members[r.id]} for r in roles],
            "resources": sorted(cr._tenant_resources())}


@router.post("", status_code=201)
async def create_role(body: RoleBody, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    role = await asyncio.to_thread(_store().save, _role(body, customer_id), _user(request))
    return {"role": role.to_dict()}


async def _existing(store, tenant_id: str, role_id: str) -> cr.CustomRole:
    found = await asyncio.to_thread(store.get, tenant_id, role_id)
    if not found:
        raise HTTPException(404, "No such role")
    return found


@router.put("/{role_id}")
async def update_role(role_id: str, body: RoleBody, request: Request, customer_id: str = MiddlewareTenant):
    store = _store()
    await _existing(store, customer_id, role_id)
    return {"role": (await asyncio.to_thread(store.save, _role(body, customer_id, role_id), _user(request))).to_dict()}


@router.delete("/{role_id}")
async def delete_role(role_id: str, request: Request, customer_id: str = MiddlewareTenant):
    store = _store()
    role = await _existing(store, customer_id, role_id)
    for member in await asyncio.to_thread(store.members, customer_id, role_id):
        await asyncio.to_thread(store.set_member, customer_id, role_id, member, _user(request), False)
    await asyncio.to_thread(store.save, role, _user(request), True)
    return {"deleted": role_id}


@router.put("/{role_id}/members/{user_id}")
async def add_member(role_id: str, user_id: str, request: Request, customer_id: str = MiddlewareTenant):
    from routers.auth_api import get_user_service

    store = _store()
    await _existing(store, customer_id, role_id)
    if not await get_user_service().get_user_tenant_roles(user_id, customer_id):
        raise HTTPException(404, "That user isn't in this tenant")
    await asyncio.to_thread(store.set_member, customer_id, role_id, user_id, _user(request), True)
    return {"role_id": role_id, "user_id": user_id, "member": True}


@router.delete("/{role_id}/members/{user_id}")
async def remove_member(role_id: str, user_id: str, request: Request, customer_id: str = MiddlewareTenant):
    store = _store()
    await _existing(store, customer_id, role_id)
    await asyncio.to_thread(store.set_member, customer_id, role_id, user_id, _user(request), False)
    return {"role_id": role_id, "user_id": user_id, "member": False}


@access_router.get("/access")
async def my_access(request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    roles = await asyncio.to_thread(_store().roles_of, customer_id, _user(request))
    permissions, scope = cr.effective(roles)
    from authn_authz_middleware import ROLE_PERMISSIONS, UserRole

    granted = []
    for assignment in getattr(request.state, "roles", None) or []:
        if assignment.get("tenant_id") not in (customer_id, "platform"):
            continue
        try:
            granted += ROLE_PERMISSIONS.get(UserRole(assignment["role"]), [])
        except ValueError:
            continue
    # role_permissions: the built-in roles' grants ("logs:read,search:tenant"),
    # so the UI can leave out what the caller would be refused.
    return {"custom_roles": [r.name for r in roles], "permissions": permissions,
            "role_permissions": sorted(set(granted)),
            "data_scope": {"services": list(scope.services)} if scope else None,
            "masked_fields": sorted(cr.masked_fields(roles))}
