"""
POST /v1/security/rules/{rule_id}/backtest (Phase 1).

Runs a rule over the tenant's stored logs (default: the last 7 days) and
returns what it would have alerted on. Unknown rules are 404, bad ranges
400; the rule set is the tenant's rules plus the platform defaults.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.security_api as security_api
from authn_authz_middleware import get_current_user


class _User:
    id = "u1"


@pytest.fixture
def client(monkeypatch):
    calls = {}

    async def rules_for(tenant):
        calls["tenant"] = tenant
        return [{"id": "bf", "title": "Brute force", "detection": {"selection": {"x": "1"}, "condition": "selection"}}]

    async def fake_run(db, rules, rule_id, tenant_id, start, end, **kwargs):
        calls.update(rule_id=rule_id, start=start, end=end, kwargs=kwargs, rules=rules)
        from backtest import run_backtest as real
        return await real(_EmptyDB(), rules, rule_id, tenant_id, start, end, **kwargs)

    monkeypatch.setattr(security_api, "_backtest_rules", rules_for)
    monkeypatch.setattr(security_api, "_backtest_db", lambda: _EmptyDB())
    monkeypatch.setattr(security_api, "run_backtest", fake_run)
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[get_current_user] = lambda: _User()
    test_client = TestClient(app)
    test_client.calls = calls
    return test_client


class _EmptyDB:
    async def fetch_all(self, sql, params=None):
        return []


HEADERS = {"X-Customer-ID": "t1"}


def test_backtest_defaults_to_the_last_seven_days(client):
    response = client.post("/v1/security/rules/bf/backtest", json={}, headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule_id"] == "bf" and body["alerts_total"] == 0
    assert client.calls["tenant"] == "t1"
    span = client.calls["end"] - client.calls["start"]
    assert span == timedelta(days=7)
    assert abs(client.calls["end"] - datetime.now(timezone.utc)) < timedelta(minutes=1)


def test_explicit_range_and_limits(client):
    response = client.post("/v1/security/rules/bf/backtest", headers=HEADERS, json={
        "start": "2026-11-01T00:00:00Z", "end": "2026-11-02T00:00:00Z", "max_events": 1000, "sample_limit": 5})
    assert response.status_code == 200, response.text
    assert client.calls["kwargs"] == {"max_events": 1000, "sample_limit": 5}


def test_unknown_rule_is_404(client):
    response = client.post("/v1/security/rules/nope/backtest", json={}, headers=HEADERS)
    assert response.status_code == 404


def test_bad_range_is_400(client):
    response = client.post("/v1/security/rules/bf/backtest", headers=HEADERS, json={
        "start": "2026-11-02T00:00:00Z", "end": "2026-11-01T00:00:00Z"})
    assert response.status_code == 400
    assert "end must be after start" in response.json()["detail"]


def test_limits_are_bounded(client):
    response = client.post("/v1/security/rules/bf/backtest", headers=HEADERS, json={"max_events": 10**9})
    assert response.status_code == 422
