"""
Regression test: login must not issue a token to a non-active account.

validate_session() only accepts ACTIVE users, but login never checked status.
A `pending` user (the state every admin-created user starts in) therefore got a
200 with a token, and then every request failed with 401 "Invalid or expired
session" -- in the UI this looked like a broken login. Found in the live QA run.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from models import LoginRequest, User, UserStatus


def _user(status):
    now = datetime.now(timezone.utc)
    return User(id="u1", email="dana@acme.example", name="Dana", password_hash="x",
                status=status, created_at=now, updated_at=now)


def _wire(monkeypatch, user):
    import login_throttle
    from routers import auth_api

    throttle = MagicMock()
    throttle.check = AsyncMock(return_value=SimpleNamespace(allowed=True))
    throttle.record_failure = AsyncMock()
    throttle.record_success = AsyncMock()
    monkeypatch.setattr(login_throttle, "get_login_throttle", lambda: throttle)

    svc = MagicMock()
    svc.authenticate_user = AsyncMock(return_value=user)
    svc.create_session = AsyncMock(side_effect=AssertionError("session must not be created"))
    monkeypatch.setattr(auth_api, "get_user_service", lambda: svc)
    return auth_api, throttle, svc


def _request():
    return SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"), headers={})


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [UserStatus.PENDING, UserStatus.INACTIVE, UserStatus.SUSPENDED])
async def test_non_active_account_gets_403_and_no_session(monkeypatch, status):
    auth_api, throttle, svc = _wire(monkeypatch, _user(status))

    with pytest.raises(HTTPException) as exc:
        await auth_api.login_user(
            LoginRequest(email="dana@acme.example", password="Correct-Pass-123!"), _request()
        )

    assert exc.value.status_code == 403
    assert status.value in exc.value.detail
    svc.create_session.assert_not_called()
    # The password was correct: this is not a brute-force signal.
    throttle.record_failure.assert_not_called()
