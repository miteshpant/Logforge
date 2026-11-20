"""
SCIM 2.0 user provisioning (Phase 14), for Okta, Entra ID and other IdPs.

  /scim/v2/ServiceProviderConfig, /ResourceTypes, /Schemas
  /scim/v2/Users            GET (filter: userName, emails.value or externalId eq "…"; startIndex, count), POST
  /scim/v2/Users/{id}       GET, PUT, PATCH, DELETE

Authenticated by a tenant's SCIM token (Authorization: Bearer lfscim_…),
created in Settings → Authentication (/v1/scim/tokens, settings:write).

A token sees and changes only the users with a role in its tenant, and
only their roles in that tenant. Roles are the SCIM `roles` attribute
(tenant roles only; viewer when none is given).
- active=false: the account is deactivated if this tenant is its only
  one; otherwise its roles here are removed. Sessions end either way.
- DELETE removes the roles here (and deactivates the account if it has
  none left anywhere), ends its sessions, and the user drops out of the
  tenant's SCIM view.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from sso.oidc import TENANT_ROLES

router = APIRouter(prefix="/scim/v2", tags=["scim"])
settings_router = APIRouter(prefix="/v1/scim/tokens", tags=["scim"])

USER = "urn:ietf:params:scim:schemas:core:2.0:User"
LIST = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
ERROR = "urn:ietf:params:scim:api:messages:2.0:Error"
PATCH_OP = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
MEDIA = "application/scim+json"
FILTER = re.compile(r'^\s*(userName|emails\.value|emails|externalId)\s+eq\s+"([^"]*)"\s*$', re.I)


class ScimError(Exception):
    def __init__(self, status: int, detail: str, scim_type: Optional[str] = None):
        self.status, self.detail, self.scim_type = status, detail, scim_type


def _error(e: ScimError) -> JSONResponse:
    body = {"schemas": [ERROR], "status": str(e.status), "detail": e.detail}
    if e.scim_type:
        body["scimType"] = e.scim_type
    return JSONResponse(body, status_code=e.status, media_type=MEDIA)


# -- dependency hooks (replaced in tests) --------------------------------------------

def _client():
    from dependencies import get_clickhouse_client

    return get_clickhouse_client()


def _users():
    from routers.auth_api import get_user_service

    return get_user_service()


def _roles():
    from routers.role_api import get_role_service

    return get_role_service()


def _links():
    from scim.tokens import LinkStore

    return LinkStore(_client())


async def _resolve(token: str) -> Optional[str]:
    from scim.tokens import TokenStore

    return await asyncio.to_thread(TokenStore(_client()).resolve, token)


async def _tenant(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    tenant = await _resolve(token) if token else None
    if not tenant:
        raise ScimError(401, "A valid SCIM token is required")
    return tenant


# -- representation -----------------------------------------------------------------------

def _value(x) -> str:
    return getattr(x, "value", x)


async def _tenant_roles(tenant: str, user_id: str) -> List[str]:
    return [_value(r.role) for r in await _roles().get_user_roles(user_id, tenant)
            if getattr(r, "tenant_id", tenant) == tenant]


async def _resource(tenant: str, user, request: Request) -> Dict[str, Any]:
    roles = await _tenant_roles(tenant, user.id)
    parts = (user.name or "").split(" ", 1)
    external = await asyncio.to_thread(_links().get, tenant, user.id)
    body = {"schemas": [USER], "id": user.id, "userName": user.email, "displayName": user.name,
            "name": {"formatted": user.name, "givenName": parts[0], "familyName": parts[1] if len(parts) > 1 else ""},
            "emails": [{"value": user.email, "primary": True, "type": "work"}],
            "active": _value(user.status) == "active" and bool(roles),
            "roles": [{"value": r, "primary": i == 0} for i, r in enumerate(sorted(roles, key=TENANT_ROLES.index))],
            "meta": {"resourceType": "User", "created": str(getattr(user, "created_at", "")),
                     "lastModified": str(getattr(user, "updated_at", "")),
                     "location": f"{str(request.base_url).rstrip('/')}/scim/v2/Users/{user.id}"}}
    if external:
        body["externalId"] = external
    return body


async def _member(tenant: str, user_id: str):
    """The user, if they have a role in this tenant; else 404 (never reveal other tenants' users)."""
    user = await _users().get_user_by_id(user_id)
    if not user or not await _tenant_roles(tenant, user_id):
        raise ScimError(404, f"User {user_id} not found")
    return user


def _name(body: Dict[str, Any], fallback: str) -> str:
    name = body.get("name") or {}
    full = " ".join(p for p in (name.get("givenName"), name.get("familyName")) if p)
    return body.get("displayName") or name.get("formatted") or full or fallback


def _roles_from(value: Any) -> List[str]:
    roles = [str(r.get("value") if isinstance(r, dict) else r) for r in (value or [])]
    bad = [r for r in roles if r not in TENANT_ROLES]
    if bad:
        raise ScimError(400, f"Unknown or non-tenant role {bad[0]!r} (roles: {', '.join(TENANT_ROLES)})", "invalidValue")
    return roles


async def _set_roles(tenant: str, user_id: str, wanted: List[str], actor: str) -> None:
    from models import UserRole

    current = set(await _tenant_roles(tenant, user_id))
    for role in set(wanted) - current:
        await _roles().assign_role(user_id=user_id, tenant_id=tenant, role=UserRole(role), granted_by=actor)
    for role in current - set(wanted):
        await _roles().remove_role(user_id, tenant, UserRole(role))


async def _set_active(tenant: str, user, active: bool, actor: str) -> None:
    from models import UserStatus

    elsewhere = [r for r in await _roles().get_user_roles(user.id) if r.tenant_id != tenant]
    if active:
        if _value(user.status) != "active":
            await _users().update_user(user.id, {"status": UserStatus.ACTIVE})
        if not await _tenant_roles(tenant, user.id):
            await _set_roles(tenant, user.id, ["viewer"], actor)
        return
    await _users().revoke_all_user_sessions_for_security(user.id)
    if elsewhere:
        await _set_roles(tenant, user.id, [], actor)
    else:
        await _users().update_user(user.id, {"status": UserStatus.INACTIVE})


async def _apply(tenant: str, user, body: Dict[str, Any], actor: str, replace: bool) -> None:
    fields: Dict[str, Any] = {}
    if replace or "name" in body or "displayName" in body:
        name = _name(body, user.name)
        if name != user.name:
            fields["name"] = name
    if fields:
        await _users().update_user(user.id, fields)
    if "roles" in body or replace:
        await _set_roles(tenant, user.id, _roles_from(body.get("roles")) or ["viewer"], actor)
    if "externalId" in body:
        await asyncio.to_thread(_links().set, tenant, user.id, body.get("externalId"))
    if "active" in body:
        await _set_active(tenant, user, bool(body["active"]), actor)


def _patch_body(user, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """PatchOp (add/replace/remove on active, roles, name.*, displayName, externalId) as a partial body."""
    out: Dict[str, Any] = {}
    parts = (user.name or "").split(" ", 1)
    name = {"givenName": parts[0], "familyName": parts[1] if len(parts) > 1 else ""}
    for op in operations:
        kind = str(op.get("op", "")).lower()
        path, value = op.get("path"), op.get("value")
        if kind not in ("add", "replace", "remove"):
            raise ScimError(400, f"Unsupported patch op {op.get('op')!r}", "invalidSyntax")
        if kind == "remove":
            value = [] if path == "roles" else None
        items = value.items() if path is None and isinstance(value, dict) else [(path, value)]
        for key, val in items:
            key = str(key or "")
            if key in ("name.givenName", "name.familyName"):
                name[key.split(".")[1]] = val or ""
                out["name"] = dict(name)
            elif key == "name" and isinstance(val, dict):
                name.update({k: v for k, v in val.items() if k in name})
                out["name"] = dict(name)
            elif key in ("active", "roles", "displayName", "externalId"):
                out[key] = (str(val).lower() == "true") if key == "active" and isinstance(val, str) else val
            elif key in ("userName", "emails"):
                raise ScimError(400, "Changing the address isn't supported; deprovision and provision again",
                                "mutability")
            else:
                raise ScimError(400, f"Unsupported patch path {key!r}", "invalidPath")
    return out


def _json(body: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse(body, status_code=status, media_type=MEDIA, headers=headers)


# -- routes ---------------------------------------------------------------------------------

def scim_route(fn):
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ScimError as e:
            return _error(e)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    import inspect

    wrapper.__signature__ = inspect.signature(fn)
    return wrapper


@router.get("/ServiceProviderConfig")
@scim_route
async def service_provider_config(request: Request):
    await _tenant(request)
    return _json({"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
                  "patch": {"supported": True}, "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
                  "filter": {"supported": True, "maxResults": 200}, "changePassword": {"supported": False},
                  "sort": {"supported": False}, "etag": {"supported": False},
                  "authenticationSchemes": [{"type": "oauthbearertoken", "name": "SCIM token",
                                             "description": "A tenant SCIM token from Settings → Authentication"}]})


@router.get("/ResourceTypes")
@scim_route
async def resource_types(request: Request):
    await _tenant(request)
    return _json({"schemas": [LIST], "totalResults": 1, "Resources": [
        {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"], "id": "User", "name": "User",
         "endpoint": "/Users", "schema": USER}]})


@router.get("/Schemas")
@scim_route
async def schemas(request: Request):
    await _tenant(request)
    attrs = ["userName", "name", "displayName", "emails", "active", "roles", "externalId"]
    return _json({"schemas": [LIST], "totalResults": 1, "Resources": [
        {"id": USER, "name": "User", "attributes": [{"name": a} for a in attrs]}]})


@router.get("/Users")
@scim_route
async def list_users(request: Request, filter: Optional[str] = None, startIndex: int = 1, count: int = 100):
    tenant = await _tenant(request)
    match: Optional[Tuple[str, str]] = None
    if filter:
        m = FILTER.match(filter)
        if not m:
            raise ScimError(400, 'Only userName, emails.value or externalId eq "value" filters are supported',
                            "invalidFilter")
        match = (m.group(1).lower(), m.group(2))
    ids = sorted({r.user_id for r in await _roles().get_tenant_users(tenant)})
    users = []
    for uid in ids:
        user = await _users().get_user_by_id(uid)
        if not user:
            continue
        if match:
            attr, value = match
            if attr == "externalid":
                if (await asyncio.to_thread(_links().get, tenant, uid)) != value:
                    continue
            elif user.email.lower() != value.lower():
                continue
        users.append(user)
    start, count = max(1, startIndex), max(0, min(count, 200))
    page = users[start - 1:start - 1 + count]
    return _json({"schemas": [LIST], "totalResults": len(users), "startIndex": start, "itemsPerPage": len(page),
                  "Resources": [await _resource(tenant, u, request) for u in page]})


@router.get("/Users/{user_id}")
@scim_route
async def get_user(user_id: str, request: Request):
    tenant = await _tenant(request)
    return _json(await _resource(tenant, await _member(tenant, user_id), request))


@router.post("/Users")
@scim_route
async def create_user(request: Request):
    import secrets

    from models import UserStatus

    tenant = await _tenant(request)
    body = await request.json()
    email = str(body.get("userName") or next((e.get("value") for e in body.get("emails") or [] if e.get("value")), "")
                ).strip().lower()
    if "@" not in email:
        raise ScimError(400, "userName must be an email address", "invalidValue")
    roles = _roles_from(body.get("roles")) or ["viewer"]
    if await _users().get_user_by_email(email):
        raise ScimError(409, f"{email} already exists", "uniqueness")
    user = await _users().create_user({"email": email, "name": _name(body, email.split("@")[0]),
                                       "password": secrets.token_urlsafe(32) + "Aa1!", "status": UserStatus.ACTIVE})
    await _set_roles(tenant, user.id, roles, f"scim:{tenant}")
    if body.get("externalId"):
        await asyncio.to_thread(_links().set, tenant, user.id, body["externalId"])
    if body.get("active") is False:
        await _set_active(tenant, user, False, f"scim:{tenant}")
    resource = await _resource(tenant, await _users().get_user_by_id(user.id), request)
    return _json(resource, 201, {"Location": resource["meta"]["location"]})


@router.put("/Users/{user_id}")
@scim_route
async def replace_user(user_id: str, request: Request):
    tenant = await _tenant(request)
    user = await _member(tenant, user_id)
    body = await request.json()
    if str(body.get("userName", user.email)).lower() != user.email.lower():
        raise ScimError(400, "Changing the address isn't supported; deprovision and provision again", "mutability")
    await _apply(tenant, user, {"active": True, **body}, f"scim:{tenant}", replace=True)
    return _json(await _resource(tenant, await _users().get_user_by_id(user_id), request))


@router.patch("/Users/{user_id}")
@scim_route
async def patch_user(user_id: str, request: Request):
    tenant = await _tenant(request)
    user = await _member(tenant, user_id)
    body = await request.json()
    if PATCH_OP not in (body.get("schemas") or []):
        raise ScimError(400, "Expected a PatchOp", "invalidSyntax")
    await _apply(tenant, user, _patch_body(user, body.get("Operations") or []), f"scim:{tenant}", replace=False)
    updated = await _users().get_user_by_id(user_id)
    if not await _tenant_roles(tenant, user_id):  # deactivated out of this tenant
        return Response(status_code=204)
    return _json(await _resource(tenant, updated, request))


@router.delete("/Users/{user_id}")
@scim_route
async def delete_user(user_id: str, request: Request):
    from models import UserStatus

    tenant = await _tenant(request)
    user = await _member(tenant, user_id)
    await _users().revoke_all_user_sessions_for_security(user.id)
    await _set_roles(tenant, user.id, [], f"scim:{tenant}")
    if not await _roles().get_user_roles(user.id):
        await _users().update_user(user.id, {"status": UserStatus.INACTIVE})
    return Response(status_code=204)


# -- tokens (settings) ----------------------------------------------------------------------

from tenant_dependencies import MiddlewareTenant  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402


class TokenBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


def _tokens():
    from scim.tokens import TokenStore

    return TokenStore(_client())


@settings_router.get("")
async def list_tokens(customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    return {"tokens": await asyncio.to_thread(_tokens().list, customer_id), "base_path": "/scim/v2"}


@settings_router.post("", status_code=201)
async def create_token(body: TokenBody, request: Request, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    user = str(getattr(getattr(request.state, "user", None), "id", "") or "")
    created = await asyncio.to_thread(_tokens().create, customer_id, body.name, user)
    return {**created, "note": "Copy the token now: it isn't shown again."}


@settings_router.delete("/{token_id}")
async def revoke_token(token_id: str, customer_id: str = MiddlewareTenant) -> Dict[str, Any]:
    from fastapi import HTTPException

    if not await asyncio.to_thread(_tokens().revoke, customer_id, token_id):
        raise HTTPException(404, "No such token")
    return {"revoked": token_id}
