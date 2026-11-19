"""
Packs API (Phase 7), under /v1/packs (read: logs:read; change: settings:write,
the tenant-admin permission, since a pack writes pipelines, rules, searches
and dashboards at once):

  GET    ""                 the catalogue, each pack with the installed version
  GET    /{id}              a pack's contents and the tenant's install
  POST   /{id}/plan         what installing or upgrading would change
  POST   /{id}/install      install or upgrade (keeps local changes; ?force=true overwrites)
  DELETE /{id}              remove what the pack installed (keeps local changes)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_pack_manager import MemoryAdapter
from test_source_packs import PACK, write

H = {"X-Customer-ID": "acme"}


class MemoryStore:
    def __init__(self):
        self.rows = {}

    async def list(self, tenant_id):
        return [m for (t, _), m in sorted(self.rows.items()) if t == tenant_id and m is not None]

    async def get(self, tenant_id, pack_id):
        return self.rows.get((tenant_id, pack_id))

    async def save(self, tenant_id, manifest, removed=False):
        self.rows[(tenant_id, manifest.pack_id)] = None if removed else manifest


@pytest.fixture
def api(tmp_path, monkeypatch):
    import routers.packs_api as packs_api
    from authn_authz_middleware import get_current_user

    write(tmp_path / "catalogue" / "demo", PACK)
    adapters = {k: MemoryAdapter(k) for k in ("pipeline", "rule", "search", "dashboard", "lookup")}
    store = MemoryStore()
    monkeypatch.setenv("SOURCE_PACKS_DIR", str(tmp_path / "catalogue"))
    packs_api.reset_catalogue()
    monkeypatch.setattr(packs_api, "_adapters", lambda: adapters)
    monkeypatch.setattr(packs_api, "_store", lambda: store)
    app = FastAPI()
    app.include_router(packs_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.adapters, client.store, client.catalogue = adapters, store, tmp_path / "catalogue"
    return client


def test_catalogue_and_detail(api):
    packs = api.get("/v1/packs", headers=H).json()
    assert packs["errors"] == {}
    entry = packs["packs"][0]
    assert entry["id"] == "demo" and entry["version"] == "1.2.0" and entry["installed_version"] is None
    assert entry["contents"]["rules"] == 1
    detail = api.get("/v1/packs/demo", headers=H).json()
    assert detail["rules"][0]["id"] == "demo-login-failed" and detail["installed"] is None
    assert api.get("/v1/packs/nope", headers=H).status_code == 404


def test_plan_install_upgrade_remove(api):
    plan = api.post("/v1/packs/demo/plan", headers=H).json()
    assert plan["counts"]["create"] == 5 and plan["from_version"] is None
    assert api.adapters["pipeline"].store == {}  # a plan changes nothing

    installed = api.post("/v1/packs/demo/install", headers=H).json()
    assert installed["installed"]["version"] == "1.2.0" and len(installed["installed"]["objects"]) == 5
    assert api.get("/v1/packs", headers=H).json()["packs"][0]["installed_version"] == "1.2.0"

    # the tenant edits the dashboard; a new pack version changes the pipeline
    api.adapters["dashboard"].store[("acme", "Demo overview")]["description"] = "ours"
    (api.catalogue / "demo" / "pack.yml").write_text(
        (api.catalogue / "demo" / "pack.yml").read_text().replace("version: 1.2.0", "version: 1.3.0"))
    path = api.catalogue / "demo" / "pipelines" / "demo-app.yml"
    path.write_text(path.read_text().replace("Parse demo lines", "Parse demo lines, v1.3"))
    entry = api.get("/v1/packs", headers=H).json()["packs"][0]
    assert entry["version"] == "1.3.0" and entry["installed_version"] == "1.2.0" and entry["update_available"]
    plan = api.post("/v1/packs/demo/plan", headers=H).json()
    assert [a["key"] for a in plan["actions"]["update"]] == ["pipeline:demo-app"]
    assert [a["key"] for a in plan["actions"]["keep_local"]] == ["dashboard:Demo overview"]
    api.post("/v1/packs/demo/install", headers=H)
    assert api.adapters["dashboard"].store[("acme", "Demo overview")]["description"] == "ours"

    removed = api.delete("/v1/packs/demo", headers=H).json()
    assert removed["kept"] == ["dashboard:Demo overview"] and len(removed["removed"]) == 4
    assert api.get("/v1/packs/demo", headers=H).json()["installed"] is None


def test_broken_packs_are_listed_with_the_reason_and_cannot_be_installed(api):
    write(api.catalogue / "broken", {"pack.yml": "id: broken\nname: Broken\nversion: x\n"})
    from routers.packs_api import reset_catalogue
    reset_catalogue()
    listed = api.get("/v1/packs", headers=H).json()
    assert "version" in listed["errors"]["broken"]
    assert api.post("/v1/packs/broken/install", headers=H).status_code == 404
