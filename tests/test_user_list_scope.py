"""
GET /v1/users (Phase 14 fix): a tenant admin lists their tenant's users, not
every user on the platform; a platform admin still sees everyone.
"""

import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))


def user(uid, email, status="active"):
    return SimpleNamespace(id=uid, email=email, name=email.split("@")[0], status=status, created_at="2026-11-20T00:00:00",
                           updated_at="2026-11-20T00:00:00", last_login_at=None, email_verified_at=None)


ALL = {"a1": user("a1", "dana@acme.test"), "a2": user("a2", "lee@acme.test", "inactive"),
       "g1": user("g1", "eve@globex.test")}


class Users:
    async def list_users(self, page, page_size, status, search):
        return {"users": list(ALL.values()), "total_count": len(ALL)}

    async def get_user_by_id(self, uid):
        return ALL.get(uid)


class Roles:
    async def get_tenant_users(self, tenant_id, role=None):
        held = {"acme": ["a1", "a2", "a1"], "globex": ["g1"]}[tenant_id]
        return [SimpleNamespace(user_id=u) for u in held]


def call(monkeypatch, roles, tenant="acme", **kw):
    import routers.user_api as module

    monkeypatch.setattr(module, "get_user_service", lambda: Users())
    monkeypatch.setattr(module, "_role_service", lambda: Roles())
    request = SimpleNamespace(headers={"X-Customer-ID": tenant}, state=SimpleNamespace(roles=roles))
    args = {"page": 1, "page_size": 50, "search": None, "status": None, **kw}
    return asyncio.run(module.list_users(current_user=ALL["a1"], request=request, **args))


def test_a_tenant_admin_sees_their_tenants_users_only(monkeypatch):
    out = call(monkeypatch, [{"tenant_id": "acme", "role": "tenant_admin"}])
    assert [u.email for u in out.users] == ["dana@acme.test", "lee@acme.test"] and out.total_count == 2
    out = call(monkeypatch, [{"tenant_id": "acme", "role": "tenant_admin"}], search="lee")
    assert [u.email for u in out.users] == ["lee@acme.test"]
    out = call(monkeypatch, [{"tenant_id": "acme", "role": "tenant_admin"}], status="active")
    assert [u.email for u in out.users] == ["dana@acme.test"]
    out = call(monkeypatch, [{"tenant_id": "acme", "role": "tenant_admin"}], page=2, page_size=1)
    assert [u.email for u in out.users] == ["lee@acme.test"] and out.total_count == 2


def test_a_platform_admin_still_sees_everyone(monkeypatch):
    out = call(monkeypatch, [{"tenant_id": "platform", "role": "super_admin"}])
    assert out.total_count == 3
