"""
Path-based permissions: every mutating method needs the write permission.

Found while adding the pipelines API: PATCH fell through to the read
permission, so e.g. PATCH /v1/security/intel/feeds/{id} (enable/disable a
threat feed) was allowed with security:read.
"""

import pytest

from authn_authz_middleware import get_endpoint_permission


@pytest.mark.parametrize("path, read, write", [
    ("/v1/security/intel/feeds/f1", "security:read:tenant", "security:write:tenant"),
    ("/v1/alerts/rules/r1", "alerts:read:tenant", "alerts:write:tenant"),
    ("/v1/pipelines/nginx", "logs:read:tenant", "logs:write:tenant"),
    ("/v1/pipelines", "logs:read:tenant", "logs:write:tenant"),
    ("/v1/packs/linux/install", "logs:read:tenant", "settings:write:tenant"),
])
def test_mutating_methods_need_write(path, read, write):
    assert get_endpoint_permission(path, "GET") == read
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert get_endpoint_permission(path, method) == write, method


@pytest.mark.parametrize("method, path, permission", [
    ("GET", "/v1/ai/status", "ai:read:tenant"),
    ("GET", "/v1/ai/usage", "ai:read:tenant"),
    ("POST", "/v1/ai/ask", "ai:read:tenant"),          # read-only: the tools only read
    ("POST", "/v1/ai/nl2query", "ai:read:tenant"),     # drafts a query; reads only the field catalogue
    ("POST", "/v1/ai/pipeline-draft", "ai:read:tenant"),  # and logs:write, checked in the route
    ("POST", "/v1/ai/explain", "ai:read:tenant"),       # and logs:read, checked in the route
    ("POST", "/v1/ai/copilot/plan", "ai:read:tenant"),  # searches run as the caller
    ("POST", "/v1/ai/copilot/run", "ai:read:tenant"),
    ("DELETE", "/v1/security/cases/c1/evidence/e1", "security:write:tenant"),  # unpin
    ("POST", "/v1/ai/triage", "ai:read:tenant"),       # evidence is read with the caller's own permissions
    ("GET", "/v1/ai/settings", "settings:read:tenant"),  # tenant admin
    ("PUT", "/v1/ai/settings", "settings:write:tenant"),
    ("GET", "/v1/ai/audit", "settings:read:tenant"),
    ("POST", "/v1/ai/query", "ai:write:tenant"),        # the older AI routes are unchanged
])
def test_ai_assistant_permissions(method, path, permission):
    assert get_endpoint_permission(path, method) == permission


def test_who_may_ask_and_who_may_configure_ai():
    from authn_authz_middleware import check_permission

    def can(role, permission):
        return check_permission([{"tenant_id": "t", "role": role}], permission, "t")

    assert can("security_analyst", "ai:read:tenant") and can("devops_engineer", "ai:read:tenant")
    assert not can("viewer", "ai:read:tenant")
    assert can("tenant_admin", "settings:write:tenant") and not can("security_analyst", "settings:write:tenant")
