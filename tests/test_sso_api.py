"""
SSO routes (Phase 14), with a mock IdP: start sends the browser to the IdP
with PKCE and a signed state cookie; the callback checks it all, creates
or signs in the user with their mapped role, and hands the UI a session.
"""

import os
import sys
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
sys.path.insert(0, os.path.dirname(__file__))

from test_oidc import DISCOVERY, ISSUER, JWKS, KEY, PROVIDER  # noqa: E402


class Store:
    def __init__(self):
        self.providers = {"p1": PROVIDER}
        self.saved = []

    def get(self, pid, tenant=None):
        p = self.providers.get(pid)
        return p if p and (tenant is None or p.tenant_id == tenant) else None

    def for_domain(self, domain):
        return [p for p in self.providers.values() if domain in p.allowed_domains]

    def list(self, tenant):
        return [p for p in self.providers.values() if p.tenant_id == tenant]

    def save(self, provider, user, deleted=False):
        provider.id = provider.id or "p2"
        self.saved.append((provider, deleted))
        return provider


class Users:
    def __init__(self, existing=None):
        self.users = dict(existing or {})
        self.updates = []

    async def get_user_by_email(self, email):
        return self.users.get(email)

    async def create_user(self, data):
        user = SimpleNamespace(id="new-user", email=data["email"], name=data["name"], status=data["status"])
        self.users[data["email"]] = user
        return user

    async def update_user(self, uid, fields):
        self.updates.append((uid, fields))


class Roles:
    def __init__(self, held=None):
        self.held = list(held or [])
        self.assigned, self.removed = [], []

    async def get_user_roles(self, uid):
        return [SimpleNamespace(tenant_id=t, role=r) for t, r in self.held]

    async def assign_role(self, user_id, tenant_id, role, granted_by):
        self.assigned.append((user_id, tenant_id, role.value, granted_by))

    async def remove_role(self, user_id, tenant_id, role):
        self.removed.append((user_id, tenant_id, role.value))


@pytest.fixture
def sso(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.sso_api as module

    state = SimpleNamespace(store=Store(), users=Users(), roles=Roles(), claims={}, token_requests=[])

    def idp(request: httpx.Request):
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(200, json=DISCOVERY)
        if request.url.path == "/jwks":
            return httpx.Response(200, json=JWKS)
        if request.url.path == "/token":
            form = parse_qs(request.content.decode())
            state.token_requests.append(form)
            if form["code"] != ["good-code"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": "logforge", "sub": "s1", "email": "dana@acme.test", "email_verified": True,
                      "nonce": state.nonce, "iat": now, "exp": now + 300, "groups": ["secops"], **state.claims}
            return httpx.Response(200, json={"id_token": jwt.encode(claims, KEY, algorithm="RS256",
                                                                    headers={"kid": "k1"})})
        return httpx.Response(404)

    async def session(user, tenant, role, request):
        return {"access_token": f"at-{user.id}-{tenant}-{role}", "expires_at": "2026-11-21T00:00:00"}

    monkeypatch.setattr(module, "_store", lambda: state.store)
    monkeypatch.setattr(module, "_users", lambda: state.users)
    monkeypatch.setattr(module, "_roles", lambda: state.roles)
    monkeypatch.setattr(module, "_session", session)
    monkeypatch.setattr(module, "_http", lambda: httpx.AsyncClient(transport=httpx.MockTransport(idp)))
    monkeypatch.setenv("LOGFORGE_PUBLIC_URL", "https://ui.acme.test")
    monkeypatch.setenv("LOGFORGE_API_PUBLIC_URL", "https://api.acme.test")
    app = FastAPI()
    app.include_router(module.login_router)
    app.include_router(module.router)
    client = TestClient(app, base_url="https://api.acme.test", follow_redirects=False)
    client.state = state

    def start(next_path="/security/cases"):
        r = client.get(f"/v1/auth/sso/p1/start?next={next_path}")
        assert r.status_code == 303, r.text
        q = parse_qs(urlparse(r.headers["location"]).query)
        state.nonce = q["nonce"][0]
        return q

    client.start = start
    return client


def landing(response):
    assert response.status_code == 303
    url = urlparse(response.headers["location"])
    return url, parse_qs(url.fragment), parse_qs(url.query)


def test_discover_by_email_domain(sso):
    assert sso.get("/v1/auth/sso/discover?email=dana@acme.test").json() == {"providers": [{"id": "p1", "name": "Acme SSO"}]}
    assert sso.get("/v1/auth/sso/discover?email=dana@other.test").json() == {"providers": []}


def test_a_first_sign_in_creates_the_user_with_the_mapped_role(sso):
    q = sso.start()
    assert q["redirect_uri"] == ["https://api.acme.test/v1/auth/sso/callback"]
    r = sso.get(f"/v1/auth/sso/callback?code=good-code&state={q['state'][0]}")
    url, fragment, _ = landing(r)
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://ui.acme.test/login/sso"
    assert fragment["access_token"] == ["at-new-user-acme-security_analyst"]
    assert fragment["next"] == ["/security/cases"]
    assert sso.state.roles.assigned == [("new-user", "acme", "security_analyst", "sso:p1")]
    assert "email_verified_at" in sso.state.users.updates[0][1]
    # the code was exchanged with the PKCE verifier and the client secret
    form = sso.state.token_requests[0]
    assert form["code_verifier"][0] and form["client_secret"] == ["s3cret"]


def test_group_changes_move_the_role_both_ways(sso):
    dana = SimpleNamespace(id="u1", email="dana@acme.test", status="active")
    sso.state.users = Users({"dana@acme.test": dana})
    sso.state.roles = Roles([("acme", "tenant_admin")])
    sso.state.claims = {"groups": ["secops"]}  # no longer in it-admins
    q = sso.start()
    _, fragment, _ = landing(sso.get(f"/v1/auth/sso/callback?code=good-code&state={q['state'][0]}"))
    assert fragment["access_token"] == ["at-u1-acme-security_analyst"]
    assert sso.state.roles.removed == [("u1", "acme", "tenant_admin")]


def test_an_account_with_access_elsewhere_cannot_sign_in_through_a_tenants_idp(sso):
    victim = SimpleNamespace(id="u7", email="dana@acme.test", status="active")
    sso.state.users = Users({"dana@acme.test": victim})
    sso.state.roles = Roles([("other-tenant", "tenant_admin")])
    q = sso.start()
    _, fragment, query = landing(sso.get(f"/v1/auth/sso/callback?code=good-code&state={q['state'][0]}"))
    assert not fragment and "outside this organisation" in query["sso_error"][0]
    assert sso.state.roles.assigned == []


@pytest.mark.parametrize("tamper", ["state", "cookie", "code", "unverified", "domain", "no-role"])
def test_refusals_land_on_the_login_page_with_a_reason(sso, tamper):
    q = sso.start()
    state = q["state"][0]
    code = "good-code"
    if tamper == "state":
        state = "someone-elses"
    elif tamper == "cookie":
        sso.cookies.clear()
    elif tamper == "code":
        code = "stolen"
    elif tamper == "unverified":
        sso.state.claims = {"email_verified": False}
    elif tamper == "domain":
        sso.state.claims = {"email": "mallory@evil.test"}
    elif tamper == "no-role":
        sso.state.store.providers["p1"] = type(PROVIDER)(**{**PROVIDER.__dict__, "default_role": None})
        sso.state.claims = {"groups": ["sales"]}
    _, fragment, query = landing(sso.get(f"/v1/auth/sso/callback?code={code}&state={state}"))
    assert not fragment and query["sso_error"][0]
    assert sso.state.roles.assigned == []


def test_next_cannot_leave_the_ui(sso):
    q = sso.start(next_path="https://evil.test/x")
    _, fragment, _ = landing(sso.get(f"/v1/auth/sso/callback?code=good-code&state={q['state'][0]}"))
    assert fragment["next"] == ["/centrum"]


def test_provider_settings_keep_the_secret_write_only_and_refuse_platform_roles(sso):
    from tenant_dependencies import get_middleware_tenant_id

    sso.app.dependency_overrides[get_middleware_tenant_id] = lambda: "acme"
    listed = sso.get("/v1/sso/providers").json()
    assert listed["providers"][0]["client_secret_set"] is True and "client_secret" not in listed["providers"][0]
    body = {"name": "Okta", "issuer": "https://acme.okta.test", "client_id": "c", "client_secret": "x",
            "role_mapping": {"admins": "super_admin"}, "allowed_domains": ["acme.test"]}
    assert sso.post("/v1/sso/providers", json=body).status_code == 422
    body["role_mapping"] = {"admins": "tenant_admin"}
    assert sso.post("/v1/sso/providers", json={**body, "allowed_domains": []}).status_code == 422
    created = sso.post("/v1/sso/providers", json=body)
    assert created.status_code == 201 and "client_secret" not in created.json()["provider"]
    assert sso.post("/v1/sso/providers", json={**body, "issuer": "http://plain.test"}).status_code == 422


def test_the_middleware_lets_sign_in_through_and_guards_settings():
    from authn_authz_middleware import UnifiedAuthMiddleware, get_endpoint_permission

    mw = UnifiedAuthMiddleware.__new__(UnifiedAuthMiddleware)
    mw.public_endpoints = []
    assert mw._is_public_endpoint("/v1/auth/sso/callback") and mw._is_public_endpoint("/v1/auth/sso/p1/start")
    assert not mw._is_public_endpoint("/v1/sso/providers")
    assert get_endpoint_permission("/v1/sso/providers", "POST") == "settings:write:tenant"
    assert get_endpoint_permission("/v1/sso/providers", "GET") == "settings:read:tenant"
