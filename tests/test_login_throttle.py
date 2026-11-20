"""
Tests for ENH-013 -- login brute-force and credential-stuffing defence.

`POST /v1/auth/login` was public with no attempt counter, no lockout and no IP
throttle. Two consequences:

* Unlimited password guessing against a known email list.
* A cheap CPU-exhaustion vector: bcrypt at 12 rounds is deliberately expensive,
  so every guess costs us far more than it costs the attacker.

A fake in-memory Redis is used to observe the counting contract. This is test
scaffolding for a call boundary, not mocked application data.
"""

import pytest

from login_throttle import (
    LoginThrottle,
    LoginThrottleError,
    ThrottlePolicy,
    _hash_identifier,
)


class _FakeRedisClient:
    """Minimal in-memory stand-in for the Redis commands used here."""

    def __init__(self, fail=False):
        self.store = {}
        self.expiries = {}
        self.fail = fail

    def _guard(self):
        if self.fail:
            raise ConnectionError("redis unavailable")

    async def incr(self, key):
        self._guard()
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def get(self, key):
        self._guard()
        return self.store.get(key)

    async def expire(self, key, seconds):
        self._guard()
        self.expiries[key] = seconds
        return True

    async def delete(self, key):
        self._guard()
        self.store.pop(key, None)
        return True


class _FakeRedisManager:
    def __init__(self, fail=False):
        self.client = _FakeRedisClient(fail=fail)


def _throttle(fail=False, **policy_kwargs):
    policy = ThrottlePolicy(
        max_attempts_per_account=policy_kwargs.get("max_attempts_per_account", 5),
        account_window_seconds=policy_kwargs.get("account_window_seconds", 900),
        max_attempts_per_ip=policy_kwargs.get("max_attempts_per_ip", 20),
        ip_window_seconds=policy_kwargs.get("ip_window_seconds", 900),
    )
    return LoginThrottle(redis_manager=_FakeRedisManager(fail=fail), policy=policy)


EMAIL = "victim@example.com"
IP = "203.0.113.5"


# ---------------------------------------------------------------------------
# Account lockout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_allowed_when_no_failures():
    throttle = _throttle()
    assert (await throttle.check(EMAIL, IP)).allowed is True


@pytest.mark.asyncio
async def test_account_locks_after_threshold():
    throttle = _throttle(max_attempts_per_account=3)

    for _ in range(3):
        await throttle.record_failure(EMAIL, IP)

    decision = await throttle.check(EMAIL, IP)
    assert decision.allowed is False
    assert decision.scope == "account"


@pytest.mark.asyncio
async def test_account_still_allowed_below_threshold():
    throttle = _throttle(max_attempts_per_account=5)

    for _ in range(4):
        await throttle.record_failure(EMAIL, IP)

    assert (await throttle.check(EMAIL, IP)).allowed is True


@pytest.mark.asyncio
async def test_successful_login_clears_account_counter():
    """A legitimate user who mistypes twice must not stay penalised."""
    throttle = _throttle(max_attempts_per_account=3)

    await throttle.record_failure(EMAIL, IP)
    await throttle.record_failure(EMAIL, IP)
    await throttle.record_success(EMAIL)
    await throttle.record_failure(EMAIL, IP)

    assert (await throttle.check(EMAIL, IP)).allowed is True


@pytest.mark.asyncio
async def test_lockout_is_per_account():
    """Locking one account must not lock an unrelated one."""
    throttle = _throttle(max_attempts_per_account=2, max_attempts_per_ip=1000)

    for _ in range(2):
        await throttle.record_failure(EMAIL, IP)

    assert (await throttle.check(EMAIL, IP)).allowed is False
    assert (await throttle.check("other@example.com", IP)).allowed is True


# ---------------------------------------------------------------------------
# IP throttling -- catches spraying that an account counter misses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ip_throttle_catches_spraying_across_accounts():
    """
    Credential stuffing hits MANY accounts once each, so a per-account counter
    never trips. The IP counter is what stops it.
    """
    throttle = _throttle(max_attempts_per_account=100, max_attempts_per_ip=5)

    for i in range(5):
        await throttle.record_failure(f"user{i}@example.com", IP)

    decision = await throttle.check("fresh@example.com", IP)
    assert decision.allowed is False
    assert decision.scope == "ip"


@pytest.mark.asyncio
async def test_ip_throttle_is_per_ip():
    throttle = _throttle(max_attempts_per_account=100, max_attempts_per_ip=3)

    for i in range(3):
        await throttle.record_failure(f"user{i}@example.com", IP)

    assert (await throttle.check("x@example.com", IP)).allowed is False
    assert (await throttle.check("x@example.com", "198.51.100.9")).allowed is True


# ---------------------------------------------------------------------------
# Retry-After
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_decision_carries_retry_after():
    throttle = _throttle(max_attempts_per_account=1, account_window_seconds=600)
    await throttle.record_failure(EMAIL, IP)

    decision = await throttle.check(EMAIL, IP)
    assert decision.retry_after_seconds == 600


@pytest.mark.asyncio
async def test_counters_get_an_expiry_window():
    """Without a TTL a counter would lock the account permanently."""
    throttle = _throttle(account_window_seconds=300)
    await throttle.record_failure(EMAIL, IP)

    expiries = throttle._redis.client.expiries
    assert any(v == 300 for v in expiries.values())


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_failure_blocks_login_by_default(monkeypatch):
    """
    Losing the throttle store must not silently reopen unlimited guessing.
    """
    monkeypatch.delenv("LOGIN_THROTTLE_REQUIRED", raising=False)
    throttle = _throttle(fail=True)

    with pytest.raises(LoginThrottleError):
        await throttle.check(EMAIL, IP)


@pytest.mark.asyncio
async def test_store_failure_can_be_explicitly_tolerated(monkeypatch):
    """Single-node deployments without Redis can opt out, loudly."""
    monkeypatch.setenv("LOGIN_THROTTLE_REQUIRED", "false")
    throttle = _throttle(fail=True)

    assert (await throttle.check(EMAIL, IP)).allowed is True


@pytest.mark.asyncio
async def test_record_failure_never_raises(monkeypatch):
    """Bookkeeping problems must not break the login response itself."""
    throttle = _throttle(fail=True)
    await throttle.record_failure(EMAIL, IP)  # must not raise


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------


def test_email_is_not_stored_in_plaintext_keys():
    """Redis keys (and backups, and `KEYS` output) must not leak account names."""
    throttle = _throttle()
    key = throttle._account_key(EMAIL)

    assert EMAIL not in key
    assert "victim" not in key


def test_identifier_hash_is_case_insensitive():
    assert _hash_identifier("User@Example.com") == _hash_identifier(
        "user@example.com"
    )


def test_identifier_hash_is_stable():
    assert _hash_identifier(EMAIL) == _hash_identifier(EMAIL)


# ---------------------------------------------------------------------------
# Endpoint wiring
# ---------------------------------------------------------------------------


def test_login_endpoint_checks_throttle_before_authentication():
    """
    The check must precede `authenticate_user`, or every guess still pays the
    bcrypt cost and the DoS vector remains open.
    """
    import inspect

    from routers import auth_api

    # Compare the AST, not the text: comments and the docstring both mention
    # `authenticate_user` before the real call, so string positions lie.
    import ast

    tree = ast.parse(inspect.getsource(auth_api.login_user).lstrip())
    func = tree.body[0]

    throttle_line = None
    auth_line = None

    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func

        if isinstance(target, ast.Attribute) and target.attr == "check":
            if isinstance(target.value, ast.Name) and target.value.id == "throttle":
                throttle_line = throttle_line or node.lineno
        if isinstance(target, ast.Attribute) and target.attr == "authenticate_user":
            auth_line = auth_line or node.lineno

    assert throttle_line is not None, "login_user never calls throttle.check()"
    assert auth_line is not None, "login_user never calls authenticate_user()"
    assert throttle_line < auth_line, (
        "Throttle must be checked before the expensive bcrypt verification, "
        "or every guess still costs us a full bcrypt round."
    )


def test_login_endpoint_returns_429_when_blocked():
    import inspect

    from routers import auth_api

    source = inspect.getsource(auth_api.login_user)
    assert "status_code=429" in source
    assert "Retry-After" in source


def test_login_endpoint_records_failures_and_successes():
    import inspect

    from routers import auth_api

    source = inspect.getsource(auth_api.login_user)
    assert "record_failure" in source
    # A session is issued only by _finish_login (after the password, or after the
    # MFA code when the account has MFA), and that is where success is recorded.
    assert "_finish_login(" in source
    assert "record_success" in inspect.getsource(auth_api._finish_login)
    # A wrong MFA code counts as a failed attempt too.
    mfa_source = inspect.getsource(auth_api.login_mfa)
    assert "record_failure" in mfa_source and "_finish_login(" in mfa_source


def test_failed_login_response_does_not_disclose_account_existence():
    import inspect

    from routers import auth_api

    source = inspect.getsource(auth_api.login_user)
    assert source.count('"Invalid email or password"') >= 1
    assert "user does not exist" not in source.lower()
