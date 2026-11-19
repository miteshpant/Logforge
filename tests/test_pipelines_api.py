"""
Pipelines API (Phase 4), under /v1/pipelines (logs read / write):

  GET    ""                 the tenant's pipelines and the built-ins
  POST   ""                 create (validated; 409 if the id exists)
  GET    /{id}              one pipeline (tenant or built-in)
  PUT    /{id}              save a new version
  DELETE /{id}
  GET    /{id}/versions     history, newest first
  POST   /simulate          run sample events (objects or raw lines) through
                            an inline or saved pipeline; returns every step

Each change invalidates the tenant's routing cache.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline_store import PipelineRegistry

H = {"X-Customer-ID": "acme"}
NGINX = {"name": "nginx", "description": "nginx access logs", "routing": {"services": ["nginx"]},
         "processors": [{"grok": {"field": "msg", "patterns": ["%{COMBINEDAPACHELOG}"]}},
                        {"convert": {"field": "attrs.response", "type": "integer"}}]}
LINE = '203.0.113.9 - - [19/Nov/2026:10:00:00 +0000] "GET /login HTTP/1.1" 401 512 "-" "curl/8.4.0"'


class MemoryDAO:
    def __init__(self):
        self.rows = {}

    async def list(self, tenant_id):
        return [r[-1] for (t, _), r in sorted(self.rows.items()) if t == tenant_id and r[-1] is not None]

    async def get(self, tenant_id, pipeline_id):
        versions = self.rows.get((tenant_id, pipeline_id))
        return versions[-1] if versions else None

    async def versions(self, tenant_id, pipeline_id):
        return [r for r in reversed(self.rows.get((tenant_id, pipeline_id), [])) if r is not None]

    async def save(self, tenant_id, record, actor, now=None):
        versions = self.rows.setdefault((tenant_id, record.id), [])
        record.version, record.updated_by = len(versions) + 1, actor
        versions.append(record)
        return record

    async def delete(self, tenant_id, pipeline_id, actor, now=None):
        self.rows[(tenant_id, pipeline_id)].append(None)


@pytest.fixture
def api(monkeypatch):
    import routers.pipelines_api as pipelines_api
    from authn_authz_middleware import get_current_user
    from pipeline_store import PipelineRecord

    dao = MemoryDAO()
    builtin = PipelineRecord.from_dict({"name": "syslog", "builtin": True,
                                        "processors": [{"syslog": {"field": "msg"}}]})
    registry = PipelineRegistry(dao=dao, builtins={"syslog": builtin})
    invalidated = []
    original = registry.invalidate
    registry.invalidate = lambda tenant_id=None: (invalidated.append(tenant_id), original(tenant_id))
    monkeypatch.setattr(pipelines_api, "_registry", lambda: registry)
    app = FastAPI()
    app.include_router(pipelines_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.invalidated = invalidated
    return client


def test_create_list_get_update_versions_delete(api):
    created = api.post("/v1/pipelines", headers=H, json=NGINX)
    assert created.status_code == 201, created.text
    assert created.json()["id"] == "nginx" and created.json()["version"] == 1
    assert created.json()["updated_by"] == "dana@acme.example"
    assert api.post("/v1/pipelines", headers=H, json=NGINX).status_code == 409

    listed = api.get("/v1/pipelines", headers=H).json()
    assert [p["id"] for p in listed["pipelines"]] == ["nginx"]
    assert [p["id"] for p in listed["builtins"]] == ["syslog"] and listed["builtins"][0]["builtin"] is True

    updated = api.put("/v1/pipelines/nginx", headers=H, json={**NGINX, "enabled": False})
    assert updated.status_code == 200 and updated.json()["version"] == 2 and updated.json()["enabled"] is False
    assert [v["version"] for v in api.get("/v1/pipelines/nginx/versions", headers=H).json()["versions"]] == [2, 1]
    assert api.get("/v1/pipelines/syslog", headers=H).json()["builtin"] is True
    assert api.put("/v1/pipelines/missing", headers=H, json=NGINX).status_code == 404

    assert api.delete("/v1/pipelines/nginx", headers=H).status_code == 204
    assert api.get("/v1/pipelines/nginx", headers=H).status_code == 404
    assert api.invalidated == ["acme", "acme", "acme"]


def test_invalid_definitions_are_400_with_the_reason(api):
    bad = api.post("/v1/pipelines", headers=H, json={"name": "x", "processors": [{"grok": {"field": "msg",
                                                                                           "patterns": ["%{NOPE:a}"]}}]})
    assert bad.status_code == 400 and "unknown pattern %{NOPE}" in bad.json()["detail"]
    bad_if = api.post("/v1/pipelines", headers=H, json={"name": "x", "processors": [{"drop": {}, "if": "a ==="}]})
    assert bad_if.status_code == 400 and "processors[0].if" in bad_if.json()["detail"]
    renamed = api.put("/v1/pipelines/nginx", headers=H, json={**NGINX, "id": "other"})
    assert renamed.status_code in (400, 404)


def test_simulate_inline_and_saved(api):
    result = api.post("/v1/pipelines/simulate", headers=H, json={"pipeline": NGINX, "docs": [LINE, {"msg": "x"}]})
    assert result.status_code == 200, result.text
    first, second = result.json()["results"]
    assert first["status"] == "ok" and first["doc"]["attrs"]["response"] == 401
    assert first["doc"]["service"] == "sample" and [s["processor"] for s in first["steps"]] == ["grok", "convert"]
    assert second["status"] == "failed" and "grok" in second["error"]["message"]

    api.post("/v1/pipelines", headers=H, json=NGINX)
    saved = api.post("/v1/pipelines/simulate", headers=H, json={"pipeline_id": "nginx", "docs": [LINE]}).json()
    assert saved["results"][0]["status"] == "ok"
    assert api.post("/v1/pipelines/simulate", headers=H, json={"pipeline_id": "nope", "docs": [LINE]}).status_code == 404
    too_many = api.post("/v1/pipelines/simulate", headers=H, json={"pipeline": NGINX, "docs": [LINE] * 101})
    assert too_many.status_code == 422


def test_stats_per_pipeline_and_for_the_tenant(api, monkeypatch):
    import routers.pipelines_api as pipelines_api
    from pipeline_processors import ProcessorContext

    api.post("/v1/pipelines", headers=H, json=NGINX)
    registry = pipelines_api._registry()
    record = registry.dao.rows[("acme", "nginx")][-1]
    for line in [LINE, "garbage"]:
        record.pipeline.run({"msg": line, "attrs": {}}, ProcessorContext(), stats=registry.stats("acme", record))
    one = api.get("/v1/pipelines/nginx/stats", headers=H).json()
    assert one["versions"][0]["version"] == 1 and one["versions"][0]["events"] == {"in": 2, "ok": 1, "dropped": 0,
                                                                                  "failed": 1}
    assert [p["type"] for p in one["versions"][0]["processors"]] == ["grok", "convert"]
    summary = api.get("/v1/pipelines/stats", headers=H).json()
    assert summary["pipelines"]["nginx"]["events"]["failed"] == 1
    assert api.get("/v1/pipelines/none/stats", headers=H).json()["versions"] == []
