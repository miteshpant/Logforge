"""Custom roles API (Phase 14): validation, members, and what a user's access is."""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))


class Store:
    def __init__(self):
        self.roles, self.held = {}, set()

    def list(self, tenant):
        return [r for r in self.roles.values() if r.tenant_id == tenant]

    def get(self, tenant, rid):
        r = self.roles.get(rid)
        return r if r and r.tenant_id == tenant else None

    def save(self, role, user, deleted=False):
        role.id = role.id or f"r{len(self.roles) + 1}"
        if deleted:
            self.roles.pop(role.id, None)
        else:
            self.roles[role.id] = role
        return role

    def members(self, tenant, rid):
        return sorted(u for t, r, u in self.held if (t, r) == (tenant, rid))

    def set_member(self, tenant, rid, user, by, member):
        (self.held.add if member else self.held.discard)((tenant, rid, user))

    def roles_of(self, tenant, user):
        return [self.roles[r] for t, r, u in self.held if (t, u) == (tenant, user) and r in self.roles]


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    import routers.auth_api as auth_api
    import routers.custom_roles_api as module
    from tenant_dependencies import get_middleware_tenant_id

    store = Store()

    class Users:
        async def get_user_tenant_roles(self, uid, tenant):
            return [{"role": "viewer"}] if uid in ("u1", "me") else []

    monkeypatch.setattr(module, "_store", lambda: store)
    monkeypatch.setattr(auth_api, "get_user_service", lambda: Users())
    app = FastAPI()

    @app.middleware("http")
    async def user(request: Request, call_next):
        request.state.user = SimpleNamespace(id="me")
        return await call_next(request)

    app.include_router(module.router)
    app.include_router(module.access_router)
    app.dependency_overrides[get_middleware_tenant_id] = lambda: "acme"
    client = TestClient(app)
    client.store = store
    return client


def test_create_validate_and_list(api):
    ok = api.post("/v1/roles/custom", json={"name": "Payments read", "permissions": ["dashboards:read"],
                                            "services": ["payments-*", "billing"]})
    assert ok.status_code == 201, ok.text
    role = ok.json()["role"]
    assert role["permissions"] == ["dashboards:read:tenant"] and role["services"] == ["billing", "payments-*"]
    for bad in ({"name": "x", "permissions": ["billing:*:platform"]}, {"name": "x", "permissions": ["*:*:*"]},
                {"name": "x", "permissions": [], "services": None},
                {"name": "x", "services": ["bad name; drop"]}, {"name": "x", "services": ["a*b"]}):
        assert api.post("/v1/roles/custom", json=bad).status_code == 422, bad
    listed = api.get("/v1/roles/custom").json()
    assert [r["name"] for r in listed["roles"]] == ["Payments read"] and "logs" in listed["resources"]


def test_members_and_my_access(api):
    rid = api.post("/v1/roles/custom", json={"name": "Auth only", "services": ["auth"]}).json()["role"]["id"]
    assert api.put(f"/v1/roles/custom/{rid}/members/nobody").status_code == 404  # not in this tenant
    assert api.put(f"/v1/roles/custom/{rid}/members/me").status_code == 200
    assert api.get("/v1/roles/custom").json()["roles"][0]["members"] == ["me"]
    assert api.get("/v1/auth/access").json() == {"custom_roles": ["Auth only"], "permissions": [],
                                                 "data_scope": {"services": ["auth"]}}
    assert api.delete(f"/v1/roles/custom/{rid}").status_code == 200
    assert api.get("/v1/auth/access").json()["data_scope"] is None
    assert api.store.held == set()


def test_updates_keep_the_id_and_unknown_roles_are_404(api):
    rid = api.post("/v1/roles/custom", json={"name": "R", "permissions": ["reports:read"]}).json()["role"]["id"]
    r = api.put(f"/v1/roles/custom/{rid}", json={"name": "R2", "permissions": ["reports:read"], "services": []})
    assert r.json()["role"]["id"] == rid and r.json()["role"]["services"] == []  # an empty scope: sees no logs
    assert api.put("/v1/roles/custom/nope", json={"name": "x", "permissions": ["reports:read"]}).status_code == 404
