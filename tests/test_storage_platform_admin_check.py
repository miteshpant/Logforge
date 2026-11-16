"""
The storage router's platform-admin checks must work for real platform admins.

They read ``request.state.user_id`` (the auth middleware sets
``request.state.user``), called ``UserService.get_user_roles`` (no such method)
and matched on ``role_name`` (the column is ``role``). Every caller got
403 "User context not found", platform admins included.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _request(user_id):
    user = SimpleNamespace(id=user_id) if user_id else None
    return SimpleNamespace(state=SimpleNamespace(user=user))


def _user_service(roles):
    svc = MagicMock()
    svc.get_user_tenant_roles = AsyncMock(return_value=roles)
    return svc


@pytest.mark.asyncio
async def test_platform_admin_gets_infrastructure_health():
    from routers import storage

    svc = _user_service([{"tenant_id": "platform", "role": "super_admin"}])
    storage_service = MagicMock()
    storage_service.get_infrastructure_health = AsyncMock(return_value={"clickhouse": "ok"})
    with patch("authn_authz_middleware.get_user_service", return_value=svc), \
         patch.object(storage, "get_storage_service", return_value=storage_service):
        out = await storage.get_infrastructure_health(_request("admin-1"), customer_id="t1")

    assert out["accessed_by"] == "admin-1"
    assert out["infrastructure_health"] == {"clickhouse": "ok"}
    svc.get_user_tenant_roles.assert_awaited_once_with("admin-1", "platform")


@pytest.mark.asyncio
async def test_tenant_user_is_refused_with_admin_message():
    from routers import storage

    svc = _user_service([{"tenant_id": "t1", "role": "tenant_admin"}])
    with patch("authn_authz_middleware.get_user_service", return_value=svc):
        with pytest.raises(HTTPException) as exc:
            await storage.get_infrastructure_health(_request("user-1"), customer_id="t1")

    assert exc.value.status_code == 403
    assert "Platform admin access required" in exc.value.detail


@pytest.mark.asyncio
async def test_unauthenticated_request_has_no_user_context():
    from routers import storage

    with pytest.raises(HTTPException) as exc:
        await storage.get_infrastructure_health(_request(None), customer_id="t1")
    assert exc.value.detail == "User context not found"


def test_audit_user_id_comes_from_the_user_object():
    from routers import storage

    assert storage._request_user_id(_request("u-9")) == "u-9"
    assert storage._request_user_id(_request(None)) is None


@pytest.mark.asyncio
async def test_platform_admin_can_sync_all_quotas():
    """Regression: the handler referenced user_id after the guard stopped assigning it."""
    import sys
    import types

    from routers import storage

    svc = _user_service([{"tenant_id": "platform", "role": "super_admin"}])
    sync = types.SimpleNamespace(trigger_manual_sync=AsyncMock(return_value={"tenants": 3}))
    fake_module = types.SimpleNamespace(storage_quota_sync_service=sync)
    with patch("authn_authz_middleware.get_user_service", return_value=svc), \
         patch.dict(sys.modules, {"services.storage_quota_sync_service": fake_module}):
        out = await storage.trigger_all_storage_quota_sync(_request("admin-1"), requesting_customer="platform")

    assert out["user_id"] == "admin-1"
    assert out["sync_result"] == {"tenants": 3}
