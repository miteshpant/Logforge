"""A tenant id in the path has to be the caller's own tenant (platform roles excepted),
and every member can read their own tenant's profile, which the UI loads at sign-in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from authn_authz_middleware import check_permission, get_endpoint_permission, tenant_path_denied  # noqa: E402

A, B = "tenant-a", "tenant-b"
admin_a = [{"tenant_id": A, "role": "tenant_admin"}]
viewer_a = [{"tenant_id": A, "role": "viewer"}]
platform = [{"tenant_id": "platform", "role": "super_admin"}]


def test_another_tenant_in_the_path_is_refused():
    assert tenant_path_denied(f"/v1/tenants/{B}", A, admin_a)
    assert tenant_path_denied(f"/v1/tenants/{B}/usage", A, admin_a)


def test_own_tenant_and_non_tenant_paths_pass():
    assert tenant_path_denied(f"/v1/tenants/{A}", A, admin_a) is None
    assert tenant_path_denied(f"/v1/tenants/{A}/usage", A, admin_a) is None
    assert tenant_path_denied("/v1/tenants/stats", A, admin_a) is None
    assert tenant_path_denied("/v1/logs/search", A, admin_a) is None


def test_platform_roles_reach_any_tenant():
    assert tenant_path_denied(f"/v1/tenants/{B}", A, platform) is None


def test_every_member_reads_their_own_tenant_profile():
    perm = get_endpoint_permission(f"/v1/tenants/{A}", "GET")
    for role in ("viewer", "security_analyst", "devops_engineer", "compliance_officer", "tenant_admin"):
        assert check_permission([{"tenant_id": A, "role": role}], perm, A), role


def test_every_member_reads_their_plan():
    perm = get_endpoint_permission(f"/v1/tenants/{A}/subscription", "GET")
    assert check_permission(viewer_a, perm, A)
    assert not check_permission(viewer_a, get_endpoint_permission(f"/v1/tenants/{A}/subscription", "PUT"), A)


def test_sub_resources_and_writes_still_need_tenant_rights():
    assert not check_permission(viewer_a, get_endpoint_permission(f"/v1/tenants/{A}/usage", "GET"), A)
    assert not check_permission(viewer_a, get_endpoint_permission(f"/v1/tenants/{A}", "PUT"), A)
