"""
Cases API (Phase 2), under /v1/security/cases so it shares the security
permissions and subscription feature:

  GET    /v1/security/cases                    list (status, assignee, severity, q, paging)
  POST   /v1/security/cases                    create (from alerts, with evidence)
  POST   /v1/security/cases/bulk               assign / status / tags for many cases
  GET    /v1/security/cases/{id}               case + alerts + timeline
  PATCH  /v1/security/cases/{id}               title, description, severity
  POST   /v1/security/cases/{id}/assign|comments|status|tags|evidence|alerts|merge|split

Case errors are 400, unknown cases 404; the actor is the signed-in user.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_case_service import FakeAlerts, MemoryDAO, T0, stored_alert

H = {"X-Customer-ID": "acme"}


@pytest.fixture
def client(monkeypatch):
    import routers.cases_api as cases_api
    from authn_authz_middleware import get_current_user
    from services.case_service import CaseService

    service = CaseService(dao=MemoryDAO(), alerts=FakeAlerts([stored_alert("a1"), stored_alert("a2", severity="low")]),
                          clock=lambda: T0)

    monkeypatch.setattr(cases_api, "_case_service", lambda: service)
    app = FastAPI()
    app.include_router(cases_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    c = TestClient(app)
    c.service = service
    return c


def create(client, **body):
    body.setdefault("title", "Brute force on bastion")
    response = client.post("/v1/security/cases", headers=H, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_from_alerts_with_evidence(client):
    case = create(client, alert_ids=["a1"], evidence=[{"kind": "search", "ref": "src_ip:203.0.113.9"}])
    assert case["severity"] == "high" and case["alert_ids"] == ["a1"] and case["created_by"] == "dana@acme.example"
    detail = client.get(f"/v1/security/cases/{case['id']}", headers=H).json()
    assert [e["kind"] for e in detail["timeline"]] == ["created", "alert_attached", "evidence_pinned"]
    assert detail["alerts"][0]["entities"]["src_ip"] == ["203.0.113.9"]


def test_full_analyst_flow(client):
    case_id = create(client)["id"]
    base = f"/v1/security/cases/{case_id}"
    assert client.post(f"{base}/assign", headers=H, json={"assignee": "bob"}).json()["assignee"] == "bob"
    assert client.post(f"{base}/comments", headers=H, json={"text": "@bob on it"}).status_code == 200
    assert client.post(f"{base}/tags", headers=H, json={"add": ["ssh"]}).json()["tags"] == ["ssh"]
    assert client.post(f"{base}/alerts", headers=H, json={"alert_ids": ["a2"]}).json()["alert_ids"] == ["a2"]
    assert client.patch(base, headers=H, json={"severity": "critical"}).json()["severity"] == "critical"
    assert client.post(f"{base}/status", headers=H, json={"status": "investigating"}).json()["status"] == "investigating"
    closed = client.post(f"{base}/status", headers=H, json={"status": "resolved", "reason": "blocked source"}).json()
    assert closed["status"] == "resolved" and closed["close_reason"] == "blocked source"
    kinds = [e["kind"] for e in client.get(base, headers=H).json()["timeline"]]
    assert kinds == ["created", "assigned", "comment", "tags_changed", "alert_attached", "updated",
                     "status_changed", "status_changed"]
    assert client.service.alerts.verdicts == [("a2", "resolved", "dana@acme.example", "blocked source")]


def test_errors(client):
    case_id = create(client)["id"]
    bad = client.post(f"/v1/security/cases/{case_id}/status", headers=H, json={"status": "resolved"})
    assert bad.status_code == 400 and "reason" in bad.json()["detail"]
    assert client.get("/v1/security/cases/nope", headers=H).status_code == 404
    assert client.get(f"/v1/security/cases/{case_id}", headers={"X-Customer-ID": "other"}).status_code == 404
    assert client.post("/v1/security/cases", headers=H, json={"title": " "}).status_code == 400


def test_merge_split_and_bulk(client):
    one = create(client, alert_ids=["a1"])["id"]
    two = create(client, alert_ids=["a2"])["id"]
    merged = client.post(f"/v1/security/cases/{one}/merge", headers=H, json={"source_ids": [two]}).json()
    assert merged["alert_ids"] == ["a1", "a2"]
    split = client.post(f"/v1/security/cases/{one}/split", headers=H, json={"alert_ids": ["a2"], "title": "Low"}).json()
    assert split["case"]["alert_ids"] == ["a1"] and split["new_case"]["title"] == "Low"
    result = client.post("/v1/security/cases/bulk", headers=H, json={
        "case_ids": [one, split["new_case"]["id"]], "action": "assign", "assignee": "carol"}).json()
    assert len(result["updated"]) == 2 and result["errors"] == {}


def test_list_filters(client, monkeypatch):
    calls = {}

    async def fake_list(tenant_id, **kwargs):
        calls.update(kwargs, tenant=tenant_id)
        return [], 0

    client.service.dao.list = fake_list
    body = client.get("/v1/security/cases?status=new&status=investigating&assignee=bob&q=brute&limit=10&offset=20",
                      headers=H).json()
    assert body == {"cases": [], "total": 0, "limit": 10, "offset": 20}
    assert calls["status"] == ["new", "investigating"] and calls["assignee"] == "bob" and calls["tenant"] == "acme"
