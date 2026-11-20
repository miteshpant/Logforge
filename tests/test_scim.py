"""
SCIM 2.0 provisioning (Phase 14): an IdP creates, updates and deprovisions
a tenant's users with a tenant-scoped bearer token.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from scim import tokens  # noqa: E402

USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
PATCH = "urn:ietf:params:scim:api:messages:2.0:PatchOp"


def test_tokens_are_shown_once_and_stored_as_hashes():
    plain, digest = tokens.new_token()
    assert plain.startswith("lfscim_") and len(plain) > 40
    assert digest == tokens.digest(plain) and plain not in digest
    assert tokens.digest(plain + "x") != digest


# -- fakes ----------------------------------------------------------------------------

class Users:
    def __init__(self):
        self.users = {}
        self.revoked = []

    async def get_user_by_id(self, uid):
        return self.users.get(uid)

    async def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email.lower()), None)

    async def create_user(self, data):
        uid = f"u{len(self.users) + 1}"
        user = SimpleNamespace(id=uid, email=data["email"], name=data["name"], status=data["status"],
                               created_at="2026-11-20T10:00:00", updated_at="2026-11-20T10:00:00")
        self.users[uid] = user
        return user

    async def update_user(self, uid, fields):
        for k, v in fields.items():
            setattr(self.users[uid], k, v)

    async def revoke_all_user_sessions_for_security(self, uid, current_session_token=None):
        self.revoked.append(uid)
        return 1


class Roles:
    def __init__(self):
        self.held = []  # (user, tenant, role)

    async def get_user_roles(self, uid, tenant_id=None):
        return [SimpleNamespace(user_id=u, tenant_id=t, role=SimpleNamespace(value=r)) for u, t, r in self.held
                if u == uid and (tenant_id is None or t == tenant_id)]

    async def get_tenant_users(self, tenant_id, role=None):
        return [SimpleNamespace(user_id=u, tenant_id=t, role=SimpleNamespace(value=r)) for u, t, r in self.held
                if t == tenant_id]

    async def assign_role(self, user_id, tenant_id, role, granted_by):
        self.held.append((user_id, tenant_id, role.value))

    async def remove_role(self, user_id, tenant_id, role):
        self.held.remove((user_id, tenant_id, role.value))
        return True


@pytest.fixture
def scim(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.scim_api as module

    users, roles = Users(), Roles()

    async def resolve(token):
        return {"good-token": "acme", "other-token": "globex"}.get(token)

    monkeypatch.setattr(module, "_users", lambda: users)
    monkeypatch.setattr(module, "_roles", lambda: roles)
    monkeypatch.setattr(module, "_resolve", resolve)
    links = {}

    class Links:
        def get(self, tenant, uid):
            return links.get((tenant, uid))

        def set(self, tenant, uid, external):
            links[(tenant, uid)] = external

    monkeypatch.setattr(module, "_links", lambda: Links())
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app, headers={"Authorization": "Bearer good-token"})
    client.users, client.roles = users, roles
    return client


def new_user(scim, email="lee@acme.test", **extra):
    body = {"schemas": [USER_SCHEMA], "userName": email, "name": {"givenName": "Lee", "familyName": "Park"},
            "emails": [{"value": email, "primary": True}], "active": True, **extra}
    return scim.post("/scim/v2/Users", json=body)


def test_a_token_is_required_and_scim_errors_are_scim_shaped(scim):
    r = scim.get("/scim/v2/Users", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401 and r.json()["schemas"] == ["urn:ietf:params:scim:api:messages:2.0:Error"]
    assert scim.get("/scim/v2/Users", headers={"Authorization": ""}).status_code == 401


def test_create_with_roles_and_a_default(scim):
    r = new_user(scim, roles=[{"value": "security_analyst"}], externalId="okta-1")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["userName"] == "lee@acme.test" and body["active"] is True and body["externalId"] == "okta-1"
    assert body["roles"] == [{"value": "security_analyst", "primary": True}]
    assert r.headers["location"].endswith(f"/scim/v2/Users/{body['id']}")
    assert body["meta"]["resourceType"] == "User"
    # no roles given: the least privileged one
    r = new_user(scim, email="kim@acme.test")
    assert r.json()["roles"] == [{"value": "viewer", "primary": True}]
    # platform roles can't be provisioned
    assert new_user(scim, email="x@acme.test", roles=[{"value": "super_admin"}]).status_code == 400


def test_usernames_are_unique(scim):
    new_user(scim)
    r = new_user(scim)
    assert r.status_code == 409 and r.json()["scimType"] == "uniqueness"


def test_filtering_and_paging(scim):
    for i in range(3):
        new_user(scim, email=f"p{i}@acme.test")
    r = scim.get('/scim/v2/Users?filter=userName eq "p1@acme.test"').json()
    assert r["totalResults"] == 1 and r["Resources"][0]["userName"] == "p1@acme.test"
    r = scim.get("/scim/v2/Users?startIndex=2&count=1").json()
    assert r["totalResults"] == 3 and r["startIndex"] == 2 and len(r["Resources"]) == 1
    assert scim.get('/scim/v2/Users?filter=name.givenName co "x"').status_code == 400  # unsupported, said so


def test_tenants_only_see_their_own_users(scim):
    uid = new_user(scim).json()["id"]
    other = {"Authorization": "Bearer other-token"}
    assert scim.get(f"/scim/v2/Users/{uid}", headers=other).status_code == 404
    assert scim.get("/scim/v2/Users", headers=other).json()["totalResults"] == 0
    assert scim.delete(f"/scim/v2/Users/{uid}", headers=other).status_code == 404
    # and can't take over another tenant's user by creating the same address
    assert new_user(scim, email="lee@acme.test").status_code == 409


def test_deprovisioning_removes_access_and_ends_sessions(scim):
    uid = new_user(scim, roles=[{"value": "tenant_admin"}]).json()["id"]
    r = scim.patch(f"/scim/v2/Users/{uid}", json={"schemas": [PATCH], "Operations": [
        {"op": "replace", "value": {"active": False}}]})
    assert r.status_code == 200 and r.json()["active"] is False
    assert scim.users.revoked == [uid] and scim.users.users[uid].status.value == "inactive"
    # reactivating restores access
    r = scim.patch(f"/scim/v2/Users/{uid}", json={"schemas": [PATCH], "Operations": [
        {"op": "replace", "path": "active", "value": True}]})
    assert r.json()["active"] is True and scim.users.users[uid].status.value == "active"


def test_a_user_in_another_tenant_is_only_removed_from_this_one(scim):
    uid = new_user(scim).json()["id"]
    scim.roles.held.append((uid, "globex", "viewer"))
    assert scim.delete(f"/scim/v2/Users/{uid}").status_code == 204
    assert [(t, r) for u, t, r in scim.roles.held if u == uid] == [("globex", "viewer")]
    assert scim.users.users[uid].status.value == "active"  # still a globex user
    assert scim.users.revoked == [uid]
    assert scim.get(f"/scim/v2/Users/{uid}").status_code == 404


def test_patch_and_put_change_roles_and_names(scim):
    uid = new_user(scim).json()["id"]
    r = scim.patch(f"/scim/v2/Users/{uid}", json={"schemas": [PATCH], "Operations": [
        {"op": "replace", "path": "roles", "value": [{"value": "security_analyst"}]},
        {"op": "replace", "path": "name.givenName", "value": "Leigh"}]})
    assert r.status_code == 200, r.text
    assert r.json()["roles"] == [{"value": "security_analyst", "primary": True}]
    assert scim.users.users[uid].name == "Leigh Park"
    r = scim.put(f"/scim/v2/Users/{uid}", json={"schemas": [USER_SCHEMA], "userName": "lee@acme.test",
                                                  "displayName": "Lee P", "active": True,
                                                  "roles": [{"value": "viewer"}]})
    assert r.json()["roles"] == [{"value": "viewer", "primary": True}] and r.json()["displayName"] == "Lee P"
    assert [(t, rr) for u, t, rr in scim.roles.held if u == uid] == [("acme", "viewer")]


def test_discovery_endpoints(scim):
    config = scim.get("/scim/v2/ServiceProviderConfig").json()
    assert config["patch"]["supported"] is True and config["filter"]["supported"] is True
    assert config["authenticationSchemes"][0]["type"] == "oauthbearertoken"
    types = scim.get("/scim/v2/ResourceTypes").json()
    assert types["Resources"][0]["endpoint"] == "/Users"


def test_the_middleware_leaves_scim_to_its_token_and_guards_token_settings():
    from authn_authz_middleware import UnifiedAuthMiddleware, get_endpoint_permission

    mw = UnifiedAuthMiddleware.__new__(UnifiedAuthMiddleware)
    mw.public_endpoints = []
    assert mw._is_public_endpoint("/scim/v2/Users")
    assert get_endpoint_permission("/v1/scim/tokens", "POST") == "settings:write:tenant"
