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
