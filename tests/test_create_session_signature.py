"""
Tests for ENH-032 -- test helpers must match `UserService.create_session()`.

`services/user_service.py:427` declares

    create_session(self, user, ip_address, user_agent, tenant_id, user_role="user")

but three test helpers still called it with three positional arguments, raising

    TypeError: create_session() missing 1 required positional argument: 'tenant_id'

That broke four `test_tenant_router` tests before they reached their assertions.
Production callers (`routers/auth_api.py:77` and `:151`) were always correct, so
this was drift in the test layer only.

These tests pin the call contract so the helpers cannot silently fall behind
again.
"""

import ast
import inspect
from pathlib import Path

import pytest

from services.user_service import UserService

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER_FILES = [
    REPO_ROOT / "tests" / "routes_tests" / "base_test.py",
    REPO_ROOT / "tests" / "routes_tests" / "test_user_router.py",
    REPO_ROOT / "tests" / "routes_tests" / "test_usage_router.py",
]

REQUIRED_PARAMS = {"user", "ip_address", "user_agent", "tenant_id"}


def _create_session_calls(path):
    """Every `…create_session(...)` call node in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name == "create_session":
                yield node


def test_service_signature_is_the_expected_shape():
    """If the signature changes, this test is the first thing to update."""
    params = inspect.signature(UserService.create_session).parameters

    assert REQUIRED_PARAMS <= set(params), (
        f"create_session lost an expected parameter. Now: {list(params)}"
    )
    assert params["tenant_id"].default is inspect.Parameter.empty, (
        "tenant_id is required; helpers must pass it explicitly."
    )


@pytest.mark.parametrize("path", HELPER_FILES, ids=lambda p: p.name)
def test_helpers_supply_every_required_argument(path):
    calls = list(_create_session_calls(path))
    assert calls, f"Expected at least one create_session call in {path.name}"

    for call in calls:
        supplied = {kw.arg for kw in call.keywords if kw.arg}
        missing = REQUIRED_PARAMS - supplied

        assert not missing, (
            f"{path.name}:{call.lineno} calls create_session without {missing}. "
            "This is the ENH-032 regression."
        )


@pytest.mark.parametrize("path", HELPER_FILES, ids=lambda p: p.name)
def test_helpers_use_keyword_arguments(path):
    """
    Keyword arguments make a future signature change fail loudly at the call
    site instead of silently binding a value to the wrong parameter -- which is
    how this defect went unnoticed.
    """
    for call in _create_session_calls(path):
        assert not call.args, (
            f"{path.name}:{call.lineno} passes positional arguments to "
            "create_session; use keywords."
        )


def test_bound_call_matches_signature():
    """A representative helper-style call must actually bind."""
    sig = inspect.signature(UserService.create_session)

    sig.bind(
        None,
        user=object(),
        ip_address="127.0.0.1",
        user_agent="test-client",
        tenant_id="tenant-a",
        user_role="tenant_admin",
    )


def test_primary_granted_role_prefers_platform():
    """
    A platform admin's session must be scoped to 'platform', not to the
    throwaway test tenant, or it will not carry platform-level access.
    """
    from base_test import BaseTestSuite

    suite = BaseTestSuite.__new__(BaseTestSuite)
    suite.test_granted_roles = [
        {"role": "tenant_admin", "tenant_id": "test-tenant-1"},
        {"role": "super_admin", "tenant_id": "platform"},
    ]

    assert suite._primary_granted_role()["tenant_id"] == "platform"


def test_primary_granted_role_falls_back_to_tenant():
    from base_test import BaseTestSuite

    suite = BaseTestSuite.__new__(BaseTestSuite)
    suite.test_granted_roles = [
        {"role": "tenant_admin", "tenant_id": "test-tenant-1"}
    ]

    assert suite._primary_granted_role()["role"] == "tenant_admin"


def test_primary_granted_role_raises_without_roles():
    """
    An empty role list must be an obvious setup error, not a session with no
    role that produces confusing 403s later.
    """
    from base_test import BaseTestSuite

    suite = BaseTestSuite.__new__(BaseTestSuite)
    suite.test_granted_roles = []

    with pytest.raises(RuntimeError, match="No roles granted"):
        suite._primary_granted_role()
