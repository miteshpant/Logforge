"""/v1/playbooks (Phase 13): definitions, approvals and who may give them."""

import os
import sys

import pytest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "apps", "api"), os.path.dirname(__file__)]

from test_playbooks import ALERT, BRUTE, INTEGRATIONS, Fakes, _runner  # noqa: E402


class MemoryStore:
    def __init__(self):
        self.playbooks, self.runs = {}, {}

    def list(self, tenant, enabled_only=False):
        return [p for (t, _), p in self.playbooks.items() if t == tenant and not p.get("deleted")]

    def get(self, tenant, pid):
        p = self.playbooks.get((tenant, pid))
        return p if p and not p.get("deleted") else None

    def save(self, tenant, name, definition, enabled, user, pid=None, deleted=False):
        pid = pid or f"pb{len(self.playbooks) + 1}"
        self.playbooks[(tenant, pid)] = {"id": pid, "name": name, "definition": definition, "enabled": enabled,
                                         "updated_by": user, "deleted": deleted}
        return self.playbooks[(tenant, pid)]

    def save_run(self, run):
        self.runs[(run.tenant_id, run.id)] = run

    def get_run(self, tenant, rid):
        return self.runs.get((tenant, rid))

    def list_runs(self, tenant, status=None, limit=100):
        return [r for (t, _), r in self.runs.items() if t == tenant and (not status or r.status == status)]


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.playbooks_api as module

    store, fakes = MemoryStore(), Fakes()
    roles = {"role": ["security_analyst"]}
    monkeypatch.setattr(module, "_store", lambda: store)
    monkeypatch.setattr(module, "_runner", lambda: _runner(fakes))
    monkeypatch.setattr(module, "_integrations", lambda tenant: INTEGRATIONS)

    async def fake_roles(request, tenant):
        return roles["role"]

    monkeypatch.setattr(module, "_roles", fake_roles)
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app, headers={"X-Customer-ID": "acme"})
    client.store, client.fakes, client.roles = store, fakes, roles
    return client


def test_create_validate_and_list(api):
    assert api.post("/v1/playbooks/validate", json={"definition": "name: x"}).json()["valid"] is False
    ok = api.post("/v1/playbooks/validate", json={"definition": BRUTE}).json()
    assert ok["valid"] and [s["containment"] for s in ok["steps"]] == [False, False, False, False, True]
    assert api.post("/v1/playbooks", json={"definition": BRUTE.replace("integration: Jira", "integration: Nope")}
                    ).status_code == 422
    made = api.post("/v1/playbooks", json={"definition": BRUTE})
    assert made.status_code == 201
    listed = api.get("/v1/playbooks").json()["playbooks"]
    assert listed[0]["name"] == "Brute force response" and listed[0]["trigger"] == "alert"


def test_approval_needs_an_approver_role_and_runs_the_containment(api):
    import asyncio

    from playbooks import model

    pid = api.post("/v1/playbooks", json={"definition": BRUTE}).json()["playbook"]["id"]
    run = asyncio.run(_runner(api.fakes).start("acme", model.parse(BRUTE), "alert", {"alert": ALERT},
                                               playbook_id=pid))
    api.store.save_run(run)
    waiting = api.get("/v1/playbooks/runs", params={"status": "waiting_approval"}).json()["runs"]
    assert [r["id"] for r in waiting] == [run.id]

    api.roles["role"] = ["viewer"]
    assert api.post(f"/v1/playbooks/runs/{run.id}/decision",
                    json={"step": "approve", "decision": "approve"}).status_code == 403
    api.roles["role"] = ["security_analyst"]
    out = api.post(f"/v1/playbooks/runs/{run.id}/decision", json={"step": "approve", "decision": "approve",
                                                                  "note": "known attacker"})
    assert out.status_code == 200 and out.json()["run"]["status"] == "succeeded"
    assert api.fakes.calls[-1][0] == "containment_webhook"
    # deciding again is a conflict, not a second containment
    again = api.post(f"/v1/playbooks/runs/{run.id}/decision", json={"step": "approve", "decision": "approve"})
    assert again.status_code == 409
    assert sum(1 for kind, _ in api.fakes.calls if kind == "containment_webhook") == 1


def test_permissions():
    from authn_authz_middleware import get_endpoint_permission

    assert get_endpoint_permission("/v1/playbooks", "POST") == "settings:write:tenant"
    assert get_endpoint_permission("/v1/playbooks/validate", "POST") == "security:read:tenant"
    assert get_endpoint_permission("/v1/playbooks/runs/r1/decision", "POST") == "security:write:tenant"
    assert get_endpoint_permission("/v1/playbooks/p1/run", "POST") == "security:write:tenant"
    assert get_endpoint_permission("/v1/playbooks/runs", "GET") == "security:read:tenant"
