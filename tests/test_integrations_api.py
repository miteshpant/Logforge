"""
/v1/integrations (Phase 13): tenant admins configure integrations; secrets
are write-only and stored sealed.
"""

import json
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))


class Result:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Rows of integrations_mt, newest version wins (as ReplacingMergeTree FINAL)."""

    def __init__(self):
        self.rows = []

    def command(self, sql, parameters=None):
        assert sql.startswith("INSERT INTO integrations_mt")
        self.rows.append(dict(parameters))

    def query(self, sql, parameters=None):
        assert "FROM integrations_mt" in sql
        latest = {}
        for r in self.rows:
            latest[(r["tenant"], r["id"])] = r
        out = [r for (t, _), r in latest.items() if t == parameters["tenant"] and not r["deleted"]]
        if "id" in parameters:
            out = [r for r in out if r["id"] == parameters["id"]]
        return Result([(r["id"], r["name"], r["kind"], r["config"], r["secrets"], r["enabled"], r["user"], "2026-11-20")
                       for r in out])


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.integrations_api as module
    from integrations import secrets
    from integrations.store import IntegrationStore

    monkeypatch.setenv("LOGFORGE_SECRETS_KEY", secrets.new_key())
    monkeypatch.setenv("LOGFORGE_ALLOW_PRIVATE_INTEGRATIONS", "true")
    client = FakeClient()
    monkeypatch.setattr(module, "_store", lambda: IntegrationStore(client))
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={})

    monkeypatch.setattr(module, "_http", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    app = FastAPI()
    app.include_router(module.router)
    test = TestClient(app, headers={"X-Customer-ID": "acme"})
    test.fake, test.sent = client, sent
    return test


def test_kinds_are_listed(api):
    kinds = {k["kind"]: k for k in api.get("/v1/integrations/kinds").json()["kinds"]}
    assert kinds["jira_issue"]["secrets"] == ["api_token"] and kinds["jira_issue"]["ticket"] is True
    assert kinds["containment_webhook"]["containment"] is True


def test_secrets_are_write_only_and_sealed(api):
    out = api.post("/v1/integrations", json={"name": "SOC Slack", "kind": "slack", "config": {},
                                             "secrets": {"webhook_url": "https://hooks.slack.test/T/B/SECRET"}})
    assert out.status_code == 201, out.text
    created = out.json()["integration"]
    assert created["secrets_set"] == ["webhook_url"] and "SECRET" not in json.dumps(created)
    assert "SECRET" not in api.fake.rows[0]["secrets"]  # sealed at rest
    listed = api.get("/v1/integrations").json()["integrations"]
    assert [i["name"] for i in listed] == ["SOC Slack"] and "SECRET" not in json.dumps(listed)

    # an update without secrets keeps them; the test action uses them
    api.put(f"/v1/integrations/{created['id']}", json={"name": "SOC alerts", "kind": "slack", "config": {}})
    test = api.post(f"/v1/integrations/{created['id']}/test", json={"inputs": {"text": "test from {{ tenant.id }}"}})
    assert test.json()["result"]["ok"] is True
    assert str(api.sent[-1].url) == "https://hooks.slack.test/T/B/SECRET"
    assert json.loads(api.sent[-1].content) == {"text": "test from acme"}


def test_invalid_integrations_are_422s(api):
    assert api.post("/v1/integrations", json={"name": "x", "kind": "jira_issue", "config": {"base_url":
                    "https://j.test", "email": "a@b.c", "project": "SEC"}, "secrets": {}}).status_code == 422
    assert api.post("/v1/integrations", json={"name": "x", "kind": "fax", "config": {}}).status_code == 422
    assert api.post("/v1/integrations", json={"name": "", "kind": "slack", "config": {},
                                              "secrets": {"webhook_url": "https://h.test"}}).status_code == 422


def test_delete_and_tenant_isolation(api):
    made = api.post("/v1/integrations", json={"name": "Hook", "kind": "webhook", "config": {"url": "https://h.test"}})
    iid = made.json()["integration"]["id"]
    other = api.get("/v1/integrations", headers={"X-Customer-ID": "other"}).json()["integrations"]
    assert other == []
    assert api.get(f"/v1/integrations/{iid}", headers={"X-Customer-ID": "other"}).status_code == 404
    assert api.delete(f"/v1/integrations/{iid}").status_code == 200
    assert api.get("/v1/integrations").json()["integrations"] == []


def test_permissions():
    from authn_authz_middleware import get_endpoint_permission

    assert get_endpoint_permission("/v1/integrations", "GET") == "settings:read:tenant"
    assert get_endpoint_permission("/v1/integrations/x/test", "POST") == "settings:write:tenant"
