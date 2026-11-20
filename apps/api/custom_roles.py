"""
Custom roles (Phase 14): roles a tenant defines on top of the built-in ones.

A custom role adds permissions (tenant-scope `resource:actions:tenant`
strings, the same vocabulary as the built-in roles) and/or a data scope:
the services whose logs its holders may read (data_scope.py). Users keep
their built-in role (sign-in needs one); custom roles add to it.

- Permissions: a request is allowed if a built-in role or a custom role
  grants it.
- Data scope: if any of the user's custom roles has one, the user reads
  only the union of those roles' services; roles without a scope don't
  widen it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from data_scope import DataScope

CACHE_SECONDS = 30


def _tenant_resources() -> set:
    from authn_authz_middleware import ROLE_PERMISSIONS
    from models import UserRole

    tenant_roles = [UserRole.TENANT_ADMIN, UserRole.SECURITY_ANALYST, UserRole.DEVOPS_ENGINEER,
                    UserRole.COMPLIANCE_OFFICER, UserRole.VIEWER]
    return {p.split(":")[0] for r in tenant_roles for p in ROLE_PERMISSIONS[r]}


@dataclass
class CustomRole:
    id: str
    tenant_id: str
    name: str
    description: str = ""
    permissions: List[str] = field(default_factory=list)
    services: Optional[List[str]] = None  # None: no data scope
    masked_fields: List[str] = field(default_factory=list)  # field_masking.py

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def normalise(permissions: List[str]) -> List[str]:
    """Accept `resource:action` (the older API's form) as `resource:action:tenant`."""
    return [p if p.count(":") == 2 else f"{p}:tenant" for p in permissions]


def validate_permissions(permissions: List[str]) -> None:
    resources = _tenant_resources()
    for p in permissions:
        parts = p.split(":")
        if len(parts) != 3 or parts[2] != "tenant" or not parts[1]:
            raise ValueError(f"{p!r}: permissions look like resource:action:tenant")
        if parts[0] not in resources:
            raise ValueError(f"{p!r}: {parts[0]!r} isn't a tenant resource ({', '.join(sorted(resources))})")


def grants(permissions: List[str], required: str) -> bool:
    resource, action, scope = required.split(":")
    for p in permissions:
        r, a, s = p.split(":")
        if r not in ("*", resource):
            continue
        if a != "*" and action not in a.split(","):
            continue
        if s in ("*", scope):
            return True
    return False


def effective(roles: List[CustomRole]) -> Tuple[List[str], Optional[DataScope]]:
    permissions = sorted({p for r in roles for p in r.permissions})
    scoped = [r for r in roles if r.services is not None]
    scope = DataScope(services=tuple(sorted({s for r in scoped for s in r.services}))) if scoped else None
    return permissions, scope


def masked_fields(roles: List[CustomRole]):
    """Fields hidden from a holder of these roles: the union over them."""
    from field_masking import normalise_fields

    return normalise_fields(f for r in roles for f in (r.masked_fields or []))


def allowed(user_roles: List[Dict[str, Any]], roles: List[CustomRole], required: str, tenant_id: str) -> bool:
    from authn_authz_middleware import check_permission

    return check_permission(user_roles, required, tenant_id) or grants(effective(roles)[0], required)


class CustomRoleStore:
    _cache: Dict[Tuple[str, str], Tuple[float, List[CustomRole]]] = {}

    def __init__(self, client):
        self.client = client

    # roles
    def list(self, tenant_id: str) -> List[CustomRole]:
        rows = self.client.query(
            "SELECT id, argMax(name, updated_at), argMax(description, updated_at), argMax(permissions, updated_at), "
            "argMax(services, updated_at), argMax(scoped, updated_at), argMax(deleted, updated_at), "
            "argMax(masked_fields, updated_at) "
            "FROM custom_roles_mt WHERE customer_id = {tenant:String} GROUP BY id", parameters={"tenant": tenant_id}
        ).result_rows
        return sorted([CustomRole(id=r[0], tenant_id=tenant_id, name=r[1], description=r[2], permissions=list(r[3]),
                                  services=list(r[4]) if r[5] else None, masked_fields=list(r[7]))
                     for r in rows if not r[6]],
                      key=lambda r: r.name.lower())

    def get(self, tenant_id: str, role_id: str) -> Optional[CustomRole]:
        return next((r for r in self.list(tenant_id) if r.id == role_id), None)

    def save(self, role: CustomRole, user_id: str, deleted: bool = False) -> CustomRole:
        role.id = role.id or uuid.uuid4().hex
        self.client.insert("custom_roles_mt", [[
            role.tenant_id, role.id, role.name, role.description, list(role.permissions), list(role.services or []),
            int(role.services is not None), int(deleted), user_id or "", list(role.masked_fields or [])]],
            column_names=["customer_id", "id", "name", "description", "permissions", "services", "scoped", "deleted",
                          "updated_by", "masked_fields"])
        self._cache.clear()
        return role

    # members
    def _members(self, where: str, params: Dict[str, Any]) -> List[Tuple[str, str]]:
        rows = self.client.query(
            "SELECT user_id, role_id, argMax(deleted, updated_at) FROM custom_role_members_mt "
            f"WHERE customer_id = {{tenant:String}} {where} GROUP BY user_id, role_id", parameters=params).result_rows
        return [(r[0], r[1]) for r in rows if not r[2]]

    def set_member(self, tenant_id: str, role_id: str, user_id: str, by: str, member: bool) -> None:
        self.client.insert("custom_role_members_mt", [[tenant_id, user_id, role_id, by or "", int(not member)]],
                           column_names=["customer_id", "user_id", "role_id", "granted_by", "deleted"])
        self._cache.clear()

    def members(self, tenant_id: str, role_id: str) -> List[str]:
        return sorted(u for u, _ in self._members("AND role_id = {role:String}", {"tenant": tenant_id, "role": role_id}))

    def roles_of(self, tenant_id: str, user_id: str) -> List[CustomRole]:
        key = (tenant_id, user_id)
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        held = {r for _, r in self._members("AND user_id = {user:String}", {"tenant": tenant_id, "user": user_id})}
        roles = [r for r in self.list(tenant_id) if r.id in held] if held else []
        self._cache[key] = (time.monotonic() + CACHE_SECONDS, roles)
        return roles
