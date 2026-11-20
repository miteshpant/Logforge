"""
MFA (roadmap: "MFA enforced at sign-in"). TOTP enrollment used to generate a
secret and store nothing, so no code was ever checked. Now an account with
confirmed MFA needs a code (or a one-time backup code) to sign in.
"""

import asyncio
import base64
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

import mfa  # noqa: E402

RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()  # RFC 6238 appendix B, SHA-1


@pytest.mark.parametrize("t, code", [(59, "287082"), (1111111109, "081804"), (1234567890, "005924"),
                                     (2000000000, "279037")])
def test_totp_matches_the_rfc_vectors(t, code):
    assert mfa.totp(RFC_SECRET, t) == code


def test_codes_are_accepted_one_step_either_way_and_never_twice():
    now = 1111111109
    code = mfa.totp(RFC_SECRET, now)
    step = mfa.check(RFC_SECRET, code, last_step=0, now=now + 25)  # the next 30 s window
    assert step == now // 30
    assert mfa.check(RFC_SECRET, code, last_step=step, now=now + 25) is None  # replay
    assert mfa.check(RFC_SECRET, code, last_step=0, now=now + 95) is None     # too old
    assert mfa.check(RFC_SECRET, "000000", last_step=0, now=now) is None
    assert mfa.check(RFC_SECRET, "abc", last_step=0, now=now) is None


def test_backup_codes_are_hashed_and_single_use():
    codes, hashes = mfa.new_backup_codes(8)
    assert len(codes) == 8 and not set(codes) & set(hashes)
    remaining = mfa.use_backup_code(hashes, codes[3].lower().replace("-", ""))  # forgiving input
    assert remaining is not None and len(remaining) == 7
    assert mfa.use_backup_code(remaining, codes[3]) is None


def test_a_challenge_is_bound_to_the_user_and_expires():
    token = mfa.challenge("u1", ttl=300)
    assert mfa.open_challenge(token) == "u1"
    with pytest.raises(mfa.MFAError):
        mfa.open_challenge(mfa.challenge("u1", ttl=-1))
    with pytest.raises(mfa.MFAError):
        mfa.open_challenge(token[:-3] + "abc")


# -- the routes -------------------------------------------------------------------------

class Store:
    def __init__(self):
        self.rows = {}

    def get(self, user_id):
        return self.rows.get(user_id)

    def save(self, user_id, record):
        self.rows[user_id] = dict(record)

    def delete(self, user_id):
        self.rows.pop(user_id, None)


USER = SimpleNamespace(id="u1", email="dana@acme.test", name="Dana", status=None, created_at="2026-11-20T00:00:00",
                       updated_at="2026-11-20T00:00:00", last_login_at=None, email_verified_at=None)


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.auth_api as module
    from models import UserStatus

    USER.status = UserStatus.ACTIVE
    store = Store()
    failures = []

    class Users:
        async def authenticate_user(self, email, password):
            return USER if password == "right-password" else None

        async def get_user_by_id(self, uid):
            return USER if uid == "u1" else None

    class Throttle:
        async def check(self, email, ip):
            return SimpleNamespace(allowed=True)

        async def record_failure(self, email, ip):
            failures.append(email)

        async def record_success(self, email):
            pass

    async def finish(user, request, email):
        from fastapi.responses import JSONResponse

        return JSONResponse({"access_token": f"session-for-{user.id}", "expires_at": "2026-11-21T00:00:00"})

    monkeypatch.setattr(module, "get_user_service", lambda: Users())
    monkeypatch.setattr(module, "_mfa_store", lambda: store)
    monkeypatch.setattr(module, "_finish_login", finish)
    monkeypatch.setattr("login_throttle.get_login_throttle", lambda: Throttle())
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: USER
    client = TestClient(app)
    client.store, client.failures = store, failures
    return client


def enroll(api):
    setup = api.post("/v1/auth/mfa/setup").json()
    assert setup["otpauth_url"].startswith("otpauth://totp/Logforge:dana%40acme.test?secret=")
    assert api.get("/v1/auth/mfa").json() == {"enabled": False, "pending": True, "backup_codes_left": 0}
    assert api.post("/v1/auth/mfa/confirm", json={"code": "000000"}).status_code == 400
    confirmed = api.post("/v1/auth/mfa/confirm", json={"code": mfa.totp(setup["secret"])}).json()
    assert len(confirmed["backup_codes"]) == 8
    return setup["secret"], confirmed["backup_codes"]


def test_without_mfa_the_password_is_enough(api):
    r = api.post("/v1/auth/login", json={"email": "dana@acme.test", "password": "right-password"})
    assert r.json()["access_token"] == "session-for-u1"


def test_with_mfa_the_password_alone_gets_no_session(api):
    secret, backups = enroll(api)
    first = api.post("/v1/auth/login", json={"email": "dana@acme.test", "password": "right-password"}).json()
    assert first["mfa_required"] is True and "access_token" not in first
    token = first["mfa_token"]
    bad = api.post("/v1/auth/login/mfa", json={"mfa_token": token, "code": "000000"})
    assert bad.status_code == 401 and api.failures == ["dana@acme.test"]
    # the confirming code was used for this window; the next window's code signs in, once
    code = mfa.totp(secret, step_offset=1)
    ok = api.post("/v1/auth/login/mfa", json={"mfa_token": token, "code": code})
    assert ok.json()["access_token"] == "session-for-u1"
    again = api.post("/v1/auth/login/mfa", json={"mfa_token": token, "code": code})
    assert again.status_code == 401
    # a backup code works once
    assert api.post("/v1/auth/login/mfa", json={"mfa_token": token, "code": backups[0]}).status_code == 200
    assert api.post("/v1/auth/login/mfa", json={"mfa_token": token, "code": backups[0]}).status_code == 401
    assert api.get("/v1/auth/mfa").json()["backup_codes_left"] == 7


def test_turning_mfa_off_needs_a_code(api):
    secret, _ = enroll(api)
    assert api.request("DELETE", "/v1/auth/mfa", json={"code": "000000"}).status_code == 400
    # the code that confirmed enrolment can't be replayed; the next window's code works
    assert api.request("DELETE", "/v1/auth/mfa", json={"code": mfa.totp(secret)}).status_code == 400
    assert api.request("DELETE", "/v1/auth/mfa", json={"code": mfa.totp(secret, step_offset=1)}).status_code == 200
    assert api.get("/v1/auth/mfa").json()["enabled"] is False


def test_the_secret_is_sealed_at_rest(monkeypatch):
    from integrations import secrets as sealing

    monkeypatch.setenv("LOGFORGE_SECRETS_KEY", sealing.new_key())
    inserted = []

    class Client:
        def insert(self, table, rows, column_names):
            inserted.append(dict(zip(column_names, rows[0])))

    secret = mfa.new_secret()
    mfa.MFAStore(Client()).save("u1", {"secret": secret, "confirmed": True, "backup_hashes": ["h"], "last_step": 5})
    assert inserted[0]["user_id"] == "u1" and secret not in str(inserted[0])
