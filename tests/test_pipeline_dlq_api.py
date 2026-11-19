"""
Dead-letter queue API (Phase 4), under /v1/pipelines/dlq:

  GET  /dlq?pipeline_id=&status=pending   entries (original event, pipeline,
                                          processor, error) and counts
  POST /dlq/replay  {"ids": [...]} or {"pipeline_id": "..."}
                    sends the original events through ingest again, with
                    their pipeline (normally after it was fixed); the
                    entries become `replayed`; failures land in the queue
                    again with the new reason
  POST /dlq/discard {"ids": [...]}
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

H = {"X-Customer-ID": "acme"}


def entry(i, pipeline="nginx"):
    return {"id": f"d{i}", "pipeline_id": pipeline, "pipeline_version": 2, "processor": "grok", "processor_index": 0,
            "tag": "", "error": "grok: no grok pattern matched msg", "status": "pending",
            "failed_at": datetime(2026, 11, 19, 9, i, tzinfo=timezone.utc).isoformat(),
            "event": {"service": "nginx", "msg": f"line {i}", "level": "info", "attrs": {"source_format": "json"}}}


class FakeDLQ:
    def __init__(self):
        self.entries = {e["id"]: e for e in [entry(1), entry(2), entry(3, pipeline="other")]}
        self.resolved = []

    async def list(self, tenant_id, pipeline_id=None, status="pending", limit=100, offset=0):
        rows = [e for e in self.entries.values() if (not pipeline_id or e["pipeline_id"] == pipeline_id)
                and (not status or e["status"] == status)]
        return rows[offset:offset + limit], len(rows)

    async def get_many(self, tenant_id, ids):
        return [self.entries[i] for i in ids if i in self.entries]

    async def counts(self, tenant_id):
        return {"nginx": {"pending": 2, "replayed": 0, "discarded": 0}}

    async def resolve_pending_again(self, tenant_id, entries):
        for e in entries:
            self.entries[e["id"]]["status"] = "pending"

    async def resolve(self, tenant_id, entries, status, actor, now=None):
        for e in entries:
            self.entries[e["id"]]["status"] = status
        self.resolved.append((status, sorted(e["id"] for e in entries), actor))


@pytest.fixture
def api(monkeypatch):
    import routers.pipelines_api as pipelines_api
    from authn_authz_middleware import get_current_user

    dlq, submitted = FakeDLQ(), []
    monkeypatch.setattr(pipelines_api, "_dlq", lambda: dlq)
    monkeypatch.setattr(pipelines_api, "_resubmit", lambda tenant, logs: submitted.append((tenant, logs)))
    app = FastAPI()
    app.include_router(pipelines_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.dlq, client.submitted = dlq, submitted
    return client


def test_list_entries_and_counts(api):
    body = api.get("/v1/pipelines/dlq?pipeline_id=nginx", headers=H).json()
    assert body["total"] == 2 and [e["id"] for e in body["entries"]] == ["d1", "d2"]
    assert body["entries"][0]["event"]["msg"] == "line 1" and body["counts"]["nginx"]["pending"] == 2


def test_replay_by_ids_and_by_pipeline(api):
    result = api.post("/v1/pipelines/dlq/replay", headers=H, json={"ids": ["d1"]}).json()
    assert result == {"replayed": 1}
    (tenant, logs), = api.submitted
    assert tenant == "acme" and logs[0].msg == "line 1"
    assert logs[0].model_dump()["logforge_pipeline"] == "nginx"  # forced through the fixed pipeline
    assert api.dlq.resolved == [("replayed", ["d1"], "dana@acme.example")]

    again = api.post("/v1/pipelines/dlq/replay", headers=H, json={"pipeline_id": "nginx"}).json()
    assert again == {"replayed": 1}  # d1 is no longer pending
    assert api.post("/v1/pipelines/dlq/replay", headers=H, json={}).status_code == 400


def test_discard(api):
    assert api.post("/v1/pipelines/dlq/discard", headers=H, json={"ids": ["d3", "zzz"]}).json() == {"discarded": 1}
    assert api.dlq.entries["d3"]["status"] == "discarded"
    assert api.submitted == []


def test_a_replay_that_cannot_be_submitted_stays_pending(api, monkeypatch):
    import routers.pipelines_api as pipelines_api

    def broken(tenant, logs):
        raise RuntimeError("ingest queue full")

    monkeypatch.setattr(pipelines_api, "_resubmit", broken)
    with pytest.raises(RuntimeError):
        api.post("/v1/pipelines/dlq/replay", headers=H, json={"ids": ["d1"]})
    assert api.dlq.entries["d1"]["status"] == "pending"
