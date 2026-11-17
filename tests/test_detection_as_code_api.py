"""
Detection-as-code API (Phase 1).

  GET  /v1/security/rules/export[?include_defaults=true]   Sigma YAML
  POST /v1/security/rules/sync  {yaml, dry_run=true, prune=false,
                                 backtest_days=0, max_alerts_per_day?}

A dry run returns the plan; an apply writes it only if nothing was rejected,
then refreshes the tenant's rule cache.
"""

import json

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_detection_as_code import BASE, SPRAY, WEBSHELL, text

H = {"X-Customer-ID": "acme"}


@pytest.fixture
def api(monkeypatch):
    import routers.security_api as security_api
    from authn_authz_middleware import get_current_user

    state = {"existing": [], "reserved": [], "writes": [], "invalidated": [], "backtests": []}

    async def rows(tenant, include_defaults=False):
        state["rows_tenant"] = tenant
        return state["existing"], state["reserved"]

    class DB:
        async def execute_update(self, sql, params=None):
            state["writes"].append(" ".join(sql.split())[:40])
            return True

    async def invalidate(tenant):
        state["invalidated"].append(tenant)

    async def fake_backtest(db, rules, rule_id, tenant_id, start, end, **kwargs):
        state["backtests"].append((rule_id, (end - start).days))
        return {"alerts_total": 1000 if rule_id == "acme-webshell" else 2, "events_scanned": 10, "alerts": []}

    monkeypatch.setattr(security_api, "_dac_rows", rows)
    monkeypatch.setattr(security_api, "_rules_db", lambda: DB())
    monkeypatch.setattr(security_api, "_invalidate_rules", invalidate)
    monkeypatch.setattr(security_api, "run_backtest", fake_backtest)
    monkeypatch.setattr(security_api, "_backtest_db", lambda: DB())
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1"})()
    client = TestClient(app)
    client.state = state
    return client


def test_dry_run_returns_the_plan_and_writes_nothing(api):
    response = api.post("/v1/security/rules/sync", headers=H, json={"yaml": text(BASE, SPRAY, WEBSHELL)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok" and body["applied"] is None
    assert sorted(body["create"]) == ["acme-auth-failed", "acme-spray", "acme-webshell"]
    assert api.state["writes"] == [] and api.state["invalidated"] == []


def test_apply_writes_and_refreshes_the_rule_cache(api):
    response = api.post("/v1/security/rules/sync", headers=H,
                        json={"yaml": text(BASE, SPRAY, WEBSHELL), "dry_run": False})
    body = response.json()
    assert body["applied"] == {"created": 3, "updated": 0, "retired": 0}
    assert len(api.state["writes"]) == 3 and api.state["invalidated"] == ["acme"]


def test_rejected_sync_is_not_applied(api):
    broken = dict(WEBSHELL, level="nonsense")
    body = api.post("/v1/security/rules/sync", headers=H, json={"yaml": text(BASE, broken), "dry_run": False}).json()
    assert body["status"] == "rejected" and body["applied"] is None
    assert body["rejected"][0]["rule"] == "acme-webshell"
    assert api.state["writes"] == []


def test_backtest_gate(api):
    body = api.post("/v1/security/rules/sync", headers=H, json={
        "yaml": text(BASE, SPRAY, WEBSHELL), "backtest_days": 7, "max_alerts_per_day": 50}).json()
    assert body["status"] == "rejected"
    assert body["rejected"] == [{"rule": "acme-webshell",
                                 "reason": "backtest: 1000 alerts in 7 days (142.9/day > 50/day)"}]
    assert sorted(api.state["backtests"]) == [("acme-spray", 7), ("acme-webshell", 7)]


def test_bad_yaml_is_400(api):
    response = api.post("/v1/security/rules/sync", headers=H, json={"yaml": "title: [unclosed"})
    assert response.status_code == 400 and "invalid YAML" in response.json()["detail"]


def test_export_is_yaml_that_syncs_unchanged(api):
    from detection_as_code import plan_sync
    import asyncio

    created = asyncio.run(plan_sync("acme", text(BASE, SPRAY, WEBSHELL), []))["create"]
    api.state["existing"] = [dict(r, is_enabled=1) for r in created]
    response = api.get("/v1/security/rules/export", headers=H)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/yaml")
    documents = list(yaml.safe_load_all(response.text))
    assert sorted(d["id"] for d in documents) == ["acme-auth-failed", "acme-spray", "acme-webshell"]
    body = api.post("/v1/security/rules/sync", headers=H, json={"yaml": response.text}).json()
    assert sorted(body["unchanged"]) == ["acme-auth-failed", "acme-spray", "acme-webshell"]
    assert body["create"] == [] and body["update"] == []
