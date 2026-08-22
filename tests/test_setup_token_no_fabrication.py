"""
Tests for ENH-014 -- the setup-token path must never fabricate behaviour.

Two fabrications existed:

1. `get_setup_token_manager()` substituted a dummy object on construction
   failure whose `generate_setup_token()` returned a HARDCODED "test-token" and
   whose `is_setup_complete()` always returned True. A predictable bootstrap
   token is a platform-takeover primitive if anything ever honours it.

2. `SetupTokenManager.has_setup_completed()` fell back to "has any in-process
   token been used?" when its database query failed -- a question unrelated to
   whether a super admin exists. Answering wrongly either re-opens the bootstrap
   endpoint on a live platform or locks out a legitimate first admin.

Both now fail loudly instead of guessing.
"""

import inspect

import pytest

import authn_authz_middleware as aam
from authn_authz_middleware import SetupTokenManager, get_setup_token_manager


# ---------------------------------------------------------------------------
# No dummy manager
# ---------------------------------------------------------------------------


def test_construction_failure_propagates(monkeypatch):
    """A platform that cannot reach its database must not pretend to bootstrap."""
    monkeypatch.setattr(aam, "_setup_token_manager_instance", None, raising=False)

    def _explode(*args, **kwargs):
        raise RuntimeError("clickhouse unreachable")

    monkeypatch.setattr(aam, "SetupTokenManager", _explode)

    with pytest.raises(RuntimeError, match="clickhouse unreachable"):
        get_setup_token_manager()


def test_no_dummy_setup_token_manager_remains():
    """
    The hardcoded-token dummy must be gone from the executable source.

    Checked against the compiled constants rather than the raw text, so the
    explanatory comments describing the old bug do not trip the assertion.
    """
    import dis

    code = aam.get_setup_token_manager.__code__
    constants = {c for c in code.co_consts if isinstance(c, str)}
    names = set(code.co_names)

    assert "test-token" not in constants, (
        "A hardcoded bootstrap token is a platform-takeover primitive."
    )
    assert "DummySetupTokenManager" not in constants
    assert "type" not in names, (
        "get_setup_token_manager() should not synthesise a stand-in class."
    )


def test_manager_is_cached_after_successful_construction(monkeypatch):
    monkeypatch.setattr(aam, "_setup_token_manager_instance", None, raising=False)
    built = []

    class _Fake:
        def __init__(self):
            built.append(1)

    monkeypatch.setattr(aam, "SetupTokenManager", _Fake)

    first = get_setup_token_manager()
    second = get_setup_token_manager()

    assert first is second
    assert len(built) == 1, "Manager should be constructed once and reused."


# ---------------------------------------------------------------------------
# Setup status must not be guessed
# ---------------------------------------------------------------------------


def _manager_without_db():
    """A SetupTokenManager with __init__ bypassed, so no database is needed."""
    mgr = SetupTokenManager.__new__(SetupTokenManager)
    mgr.setup_tokens = {}
    return mgr


class _FailingDB:
    class client:
        @staticmethod
        def query(*args, **kwargs):
            raise RuntimeError("clickhouse unreachable")


class _QueryResult:
    def __init__(self, rows):
        self.result_rows = rows


class _CountingClient:
    """Returns a super-admin count, mimicking the ClickHouse client surface."""

    def __init__(self, count):
        self._count = count

    def query(self, *args, **kwargs):
        return _QueryResult([[self._count]])


class _CountingDB:
    def __init__(self, count):
        self.client = _CountingClient(count)


def test_setup_status_error_is_raised_not_guessed():
    mgr = _manager_without_db()
    mgr.db = _FailingDB()
    # A used token in memory previously made this return True regardless.
    mgr.setup_tokens = {"t": {"used": True, "expires_at": None}}

    with pytest.raises(RuntimeError):
        mgr.has_setup_completed()


def test_setup_status_reports_true_when_super_admin_exists():
    mgr = _manager_without_db()
    mgr.db = _CountingDB(1)

    assert mgr.has_setup_completed() is True


def test_setup_status_reports_false_when_no_super_admin():
    mgr = _manager_without_db()
    mgr.db = _CountingDB(0)

    assert mgr.has_setup_completed() is False


# ---------------------------------------------------------------------------
# Token issuance and single use
# ---------------------------------------------------------------------------


def test_generated_token_is_not_predictable():
    mgr = _manager_without_db()

    first = mgr.generate_setup_token()["setup_token"]
    second = mgr.generate_setup_token()["setup_token"]

    assert first != second
    assert len(first) >= 32, "Bootstrap tokens must have real entropy."


def test_token_is_single_use():
    mgr = _manager_without_db()
    token = mgr.generate_setup_token()["setup_token"]

    assert mgr.validate_setup_token(token) is True
    assert mgr.validate_setup_token(token) is False, (
        "A consumed bootstrap token must not be reusable."
    )


def test_unknown_token_is_rejected():
    mgr = _manager_without_db()
    assert mgr.validate_setup_token("never-issued") is False


def test_expired_token_is_rejected():
    from datetime import datetime, timedelta

    mgr = _manager_without_db()
    token = mgr.generate_setup_token()["setup_token"]
    mgr.setup_tokens[token]["expires_at"] = datetime.utcnow() - timedelta(seconds=1)

    assert mgr.validate_setup_token(token) is False


def test_known_limitation_is_documented():
    """
    Tokens are still process-local. That is a real multi-replica limitation and
    must stay documented until ENH-021 adds persistence, rather than being
    quietly forgotten.
    """
    doc = (SetupTokenManager.__doc__ or "").lower()
    assert "limitation" in doc
    assert "memory" in doc or "in-process" in doc
