"""
Account flows (Phase 14): password reset, invitations and email
verification send their links by email; a verification token must be
valid for this user and address; a password reset ends every session;
accepting an invitation grants the invited role.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import account_tokens  # noqa: E402

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


# -- signed tokens -------------------------------------------------------------------

def test_a_verification_token_is_bound_to_the_user_the_address_and_the_purpose():
    token = account_tokens.issue("u1", "Dana@acme.test", "verify_email", timedelta(hours=24), now=NOW)
    assert account_tokens.check(token, "u1", "dana@acme.test", "verify_email", now=NOW + timedelta(hours=1))
    assert not account_tokens.check(token, "u2", "dana@acme.test", "verify_email", now=NOW)
    assert not account_tokens.check(token, "u1", "lee@acme.test", "verify_email", now=NOW)  # address changed
    assert not account_tokens.check(token, "u1", "dana@acme.test", "other", now=NOW)
    assert not account_tokens.check(token, "u1", "dana@acme.test", "verify_email", now=NOW + timedelta(hours=25))
    expires, sig = token.split(".")
    assert not account_tokens.check(f"{int(expires) + 999}.{sig}", "u1", "dana@acme.test", "verify_email", now=NOW)
    for junk in ("", "x", "1.2.3", "abc.def", "invalid-verification-token"):
        assert not account_tokens.check(junk, "u1", "dana@acme.test", "verify_email", now=NOW)


# -- the routes ----------------------------------------------------------------------

class Users:
    def __init__(self):
        self.users = {"u1": SimpleNamespace(id="u1", email="dana@acme.test", name="Dana", email_verified_at=None,
                                            password_hash="x", password_reset_token="reset-tok",
                                            password_reset_expires=None, updated_at=None)}
        self.updates, self.revoked, self.created = [], [], []

    async def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email.lower()), None)

    async def get_user_by_reset_token(self, token):
        return next((u for u in self.users.values() if u.password_reset_token == token), None)

    async def update_user(self, user_id, fields):
        self.updates.append((user_id, fields))

    async def revoke_all_user_sessions_for_security(self, user_id, current_session_token=None):
        self.revoked.append(user_id)
        return 3

    async def create_user(self, data):
        user = SimpleNamespace(id="u9", email=data["email"], name=data["name"], status=data["status"],
                               created_at=NOW, updated_at=NOW, last_login_at=None, email_verified_at=None)
        self.created.append(user)
        return user


class Invitations:
    def __init__(self):
        self.accepted = []

    async def create_invitation(self, email, tenant_id, role, invited_by):
        return {"invitation_id": "inv1", "invitation_token": "invite-tok", "invitation_expires": NOW + timedelta(days=7),
                "invited_email": email, "email": email, "tenant_id": tenant_id, "role": role.value}

    async def validate_invitation(self, token, email):
        if token != "invite-tok":
            return None
        return {"id": "inv1", "email": email, "tenant_id": "acme", "role": "security_analyst", "invited_by": "u1"}

    async def accept_invitation(self, token, invitation_id):
        self.accepted.append(invitation_id)
        return True


class Roles:
    def __init__(self):
        self.assigned = []

    async def assign_role(self, user_id, tenant_id, role, granted_by, **kw):
        self.assigned.append((user_id, tenant_id, getattr(role, "value", role), granted_by))


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    import account_emails
    import routers.auth_api as module

    users, invitations, roles, sent = Users(), Invitations(), Roles(), []

    async def send(message):
        sent.append(message)
        return True

    monkeypatch.setattr(module, "get_user_service", lambda: users)
    monkeypatch.setattr(module, "invitation_manager", invitations)
    monkeypatch.setattr(module, "_role_service", lambda: roles)
    monkeypatch.setattr(account_emails, "send", send)
    monkeypatch.setenv("LOGFORGE_PUBLIC_URL", "https://logforge.acme.test/")
    app = FastAPI()

    @app.middleware("http")
    async def roles_state(request: Request, call_next):
        request.state.roles = [{"tenant_id": "acme", "role": "tenant_admin"}]
        return await call_next(request)

    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: users.users["u1"]
    client = TestClient(app)
    client.users, client.invitations, client.roles, client.sent = users, invitations, roles, sent
    return client


def link_token(body: str, path: str):
    url = next(w for w in body.split() if w.startswith("https://logforge.acme.test" + path))
    return parse_qs(urlparse(url).query)


def test_password_reset_emails_a_link_and_the_reset_ends_every_session(api):
    assert api.post("/v1/auth/password/reset", json={"email": "dana@acme.test"}).status_code == 200
    message = api.sent[-1]
    assert message["to"] == ["dana@acme.test"] and "reset" in message["subject"].lower()
    token = link_token(message["body"], "/reset-password")["token"][0]
    assert token == api.users.updates[-1][1]["password_reset_token"]

    # unknown addresses get the same answer and no email
    assert api.post("/v1/auth/password/reset", json={"email": "nobody@acme.test"}).status_code == 200
    assert len(api.sent) == 1

    bad = api.post("/v1/auth/password/reset-confirm", json={"token": "nope", "new_password": "N3w-Passw0rd!x"})
    assert bad.status_code == 400
    ok = api.post("/v1/auth/password/reset-confirm", json={"token": token, "new_password": "N3w-Passw0rd!x"})
    assert ok.status_code == 200, ok.text
    assert api.users.revoked == ["u1"]


def test_an_invitation_is_emailed_and_accepting_it_grants_the_role(api):
    r = api.post("/v1/auth/invite", json={"email": "lee@acme.test", "tenant_id": "acme", "role": "security_analyst"})
    assert r.status_code == 200, r.text
    message = api.sent[-1]
    assert message["to"] == ["lee@acme.test"]
    query = link_token(message["body"], "/accept-invite")
    assert query["token"] == ["invite-tok"] and query["email"] == ["lee@acme.test"] and query["tenant"] == ["acme"]

    r = api.post("/v1/auth/accept-invite", json={"invitation_token": "invite-tok", "email": "lee@acme.test",
                                                 "name": "Lee", "password": "Str0ng-Passw0rd!", "tenant_id": "acme"})
    assert r.status_code == 201, r.text
    assert api.roles.assigned == [("u9", "acme", "security_analyst", "u1")]  # granted by the inviter
    assert api.invitations.accepted == ["inv1"]


def test_email_verification_needs_the_token_that_was_sent(api):
    assert api.post("/v1/auth/verify-email").status_code == 200
    token = link_token(api.sent[-1]["body"], "/verify-email")["token"][0]

    bad = api.post("/v1/auth/verify-email-confirm", json={"token": "invalid-verification-token"})
    assert bad.status_code == 400
    assert not any("email_verified_at" in f for _, f in api.users.updates)

    ok = api.post("/v1/auth/verify-email-confirm", json={"token": token})
    assert ok.status_code == 200, ok.text
    assert any("email_verified_at" in f for _, f in api.users.updates)


def test_email_failures_do_not_leak_whether_an_account_exists(api, monkeypatch):
    import account_emails

    async def broken(message):
        return False

    monkeypatch.setattr(account_emails, "send", broken)
    assert api.post("/v1/auth/password/reset", json={"email": "dana@acme.test"}).json() == \
        api.post("/v1/auth/password/reset", json={"email": "nobody@acme.test"}).json()


def test_messages_link_to_the_public_url(monkeypatch):
    import account_emails

    monkeypatch.setenv("LOGFORGE_PUBLIC_URL", "https://lf.example/")
    m = account_emails.verify_message("a@b.test", "t0k")
    assert "https://lf.example/verify-email?token=t0k" in m["body"]
    m = account_emails.invite_message("a+x@b.test", "t", "acme", "security_analyst", "Dana")
    assert "email=a%2Bx%40b.test" in m["body"] and "Dana" in m["body"]
