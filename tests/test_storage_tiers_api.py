"""Storage tiers API (Phase 12), with TierManager on a fake ClickHouse client."""

import os
import sys
from datetime import date

import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "apps", "api"), os.path.dirname(__file__)]

from test_tier_manager import FakeClient, FakeObjects  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.storage_tiers_api as module
    import storage_tiers as st
    import tier_manager as tm

    client = FakeClient(stored=[("acme", "logs", 14, 730)], manifest={("acme", "logs"): {date(2026, 10, 1): 9}},
                        days={("acme", "logs"): {}, ("other", "logs"): {date(2020, 1, 1): 3}})
    monkeypatch.setattr(module, "_manager", lambda: tm.TierManager(client, FakeObjects(), st.load_config()))
    app = FastAPI()
    app.include_router(module.router)
    test = TestClient(app, headers={"X-Customer-ID": "acme"})
    test.fake = client
    return test


def test_get_tiers_shows_the_tenants_policy_and_archives(api):
    out = api.get("/v1/storage/tiers").json()
    logs = next(t for t in out["data_types"] if t["data_type"] == "logs")
    assert (logs["searchable_days"], logs["archive_days"], logs["custom"]) == (14, 730, True)
    assert logs["archived_days"] == 1 and logs["archived_rows"] == 9
    security = next(t for t in out["data_types"] if t["data_type"] == "security")
    assert security["custom"] is False
    assert out["tiers"]["hot"]["days"] >= 1
    assert out["limits"]["max_searchable_days"] >= 30


def test_set_policy_validates(api):
    assert api.put("/v1/storage/tiers/policies/logs", json={"searchable_days": 30, "archive_days": 10}).status_code == 422
    assert api.put("/v1/storage/tiers/policies/blobs", json={"searchable_days": 30}).status_code == 422
    assert api.put("/v1/storage/tiers/policies/logs", json={"searchable_days": 0}).status_code == 422
    ok = api.put("/v1/storage/tiers/policies/traces", json={"searchable_days": 7, "archive_days": 0})
    assert ok.status_code == 200 and ok.json()["policy"]["searchable_days"] == 7
    inserted = [p for s, p in api.fake.statements if s.startswith("INSERT INTO tenant_retention_mt")]
    assert inserted[-1]["tenant"] == "acme"


def test_run_now_touches_only_the_callers_tenant(api):
    out = api.post("/v1/storage/tiers/run").json()
    assert out["errors"] == []
    deletes = [p for s, p in api.fake.statements if s.startswith("ALTER TABLE logs_raw_mt DELETE")]
    assert deletes == []  # "other" has old data, but isn't the caller


def test_the_middleware_maps_tiers_to_storage_permissions():
    from authn_authz_middleware import ROLE_PERMISSIONS, UserRole, get_endpoint_permission

    assert get_endpoint_permission("/v1/storage/tiers", "GET") == "storage:read:tenant"
    assert get_endpoint_permission("/v1/storage/tiers/policies/logs", "PUT") == "storage:write:tenant"
    assert "storage:*:tenant" in ROLE_PERMISSIONS[UserRole.TENANT_ADMIN]
    assert not any(p.startswith("storage:") for p in ROLE_PERMISSIONS[UserRole.SECURITY_ANALYST])
