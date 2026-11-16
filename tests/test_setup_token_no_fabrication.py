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


class _TokenTableClient:
    """In-memory stand-in for platform_setup_tokens_mt.

    Implements just the three statements SetupTokenManager issues, keyed on
    the bound token_hash parameter, and records every statement.
    """

    def __init__(self):
        self.rows = {}  # token_hash -> {"expired": bool, "used": bool}
        self.statements = []

    def command(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        token_hash = parameters["token_hash"]
        if sql.lstrip().startswith("INSERT"):
            self.rows[token_hash] = {"expired": False, "used": False}
        elif "UPDATE used_at" in sql and token_hash in self.rows:
            self.rows[token_hash]["used"] = True

    def query(self, sql, parameters=None):
        self.statements.append((sql, parameters))
        row = self.rows.get(parameters["token_hash"])
        valid = bool(row) and not row["used"] and not row["expired"]
        return _QueryResult([[1 if valid else 0]])


class _TokenTableDB:
    def __init__(self):
        self.client = _TokenTableClient()


def _manager_without_db():
    """A SetupTokenManager with __init__ bypassed and an in-memory token table."""
    mgr = SetupTokenManager.__new__(SetupTokenManager)
    mgr.db = _TokenTableDB()
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
    mgr = _manager_without_db()
    token = mgr.generate_setup_token()["setup_token"]
    mgr.db.client.rows[SetupTokenManager._hash(token)]["expired"] = True

    assert mgr.validate_setup_token(token) is False


def test_tokens_are_persisted_as_hashes_not_plaintext():
    mgr = _manager_without_db()
    token = mgr.generate_setup_token()["setup_token"]

    assert list(mgr.db.client.rows) == [SetupTokenManager._hash(token)]
    for sql, params in mgr.db.client.statements:
        assert token not in sql and token not in str(params), (
            "The plaintext bootstrap token must never reach the database."
        )


def test_token_issued_by_one_instance_validates_on_another():
    """Restarts and other replicas share the table, not process memory."""
    issuer = _manager_without_db()
    token = issuer.generate_setup_token()["setup_token"]

    other = SetupTokenManager.__new__(SetupTokenManager)
    other.db = issuer.db  # same table, different process
    assert not hasattr(other, "setup_tokens")
    assert other.validate_setup_token(token) is True
    assert issuer.validate_setup_token(token) is False


def test_consumption_waits_for_the_mutation():
    mgr = _manager_without_db()
    token = mgr.generate_setup_token()["setup_token"]
    mgr.validate_setup_token(token)

    update = [sql for sql, _ in mgr.db.client.statements if "UPDATE used_at" in sql]
    assert update and "mutations_sync = 2" in update[0]
