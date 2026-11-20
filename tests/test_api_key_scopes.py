"""
API key scopes (roadmap: "Enforce API key scopes"). A key is backed by a
service account with the tenant_admin role; the permissions it was created
with were recorded but never checked, so every key could do anything in its
tenant. Now a key with permissions can only do what they allow.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from api_key_scopes import allows  # noqa: E402


@pytest.mark.parametrize("key, required, ok", [
    (["logs:write"], "logs:write:tenant", True),       # ingest
    (["logs:write"], "logs:read:tenant", False),       # an ingest key can't read logs
    (["logs:read"], "logs:read:tenant", True),
    (["logs:read"], "settings:write:tenant", False),
    (["metrics:write"], "observability:write:tenant", True),   # metrics and traces live under observability
    (["traces:read"], "observability:read:tenant", True),
    (["security:read"], "security:write:tenant", False),
    (["ai:read", "ai:write"], "ai:write:tenant", True),
    (["logs:read"], "platform:admin:platform", False),
    (["logs:read"], "queries:write:tenant", True),     # running a search (POST /v1/query/...) reads logs
    (["logs:write"], "queries:write:tenant", False),
])
def test_a_key_can_do_only_what_its_permissions_allow(key, required, ok):
    assert allows(key, required) is ok


def test_a_key_without_permissions_keeps_full_access():
    # keys created before scopes were enforced listed none; they keep working
    assert allows([], "settings:write:tenant") is True


def test_the_middleware_checks_the_key():
    from authn_authz_middleware import api_key_denied

    class State:
        is_api_key_auth = True
        api_key_permissions = ["logs:write"]

    assert api_key_denied(State(), "logs:write:tenant") is None
    assert "logs:read" in api_key_denied(State(), "logs:read:tenant")

    class Session:
        pass

    assert api_key_denied(Session(), "settings:write:tenant") is None  # not an API key: roles decide
