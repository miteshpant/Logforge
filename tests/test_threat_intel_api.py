"""
Threat intelligence API (Phase 3), under /v1/security/intel:

  GET    /feeds                      the tenant's feeds + built-in templates
  POST   /feeds                      add a feed (or {"template": name})
  PATCH  /feeds/{id}                 enable/disable, interval, confidence, TTL
  DELETE /feeds/{id}
  POST   /feeds/{id}/run             fetch now; new indicators are retro-hunted
  GET    /indicators                 search (q, type) with "seen in your data" counts
  POST   /indicators                 add one by hand (retro-hunted too)
  DELETE /indicators/{type}/{value}

Secrets never appear: a feed shows only whether its key is configured.
"""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from threat_intel import Indicator

H = {"X-Customer-ID": "acme"}


class FakeDAO:
    def __init__(self):
        self.feeds = {}
        self.indicators = {}
        self.deleted = []

    async def list_feeds(self, tenant_id=None):
        return [(t, f) for (t, _), f in self.feeds.items() if tenant_id in (None, t)]

    async def save_feed(self, tenant_id, feed, deleted=False):
        if deleted:
            self.feeds.pop((tenant_id, feed.id), None)
        else:
            self.feeds[(tenant_id, feed.id)] = feed

    async def record_run(self, tenant_id, feed, now, status, count, error):
        feed.last_status, feed.last_count, feed.last_error = status, count, error

    async def existing_keys(self, tenant_id, keys):
        return {k for k in keys if (tenant_id, k) in self.indicators}

    async def upsert_indicators(self, tenant_id, indicators, feed_id, now):
        for i in indicators:
            self.indicators[(tenant_id, (i.indicator_type, i.normalized()))] = i

    async def delete_indicator(self, tenant_id, indicator_type, value, now):
        self.deleted.append((tenant_id, indicator_type, value))

    async def search_indicators(self, tenant_id, q="", indicator_type=None, limit=100, offset=0):
        rows = [{"indicator_type": i.indicator_type, "value": i.value, "threat_type": i.threat_type,
                 "confidence": i.confidence, "source": i.source, "tags": i.tags, "expires_at": None}
                for (t, _), i in self.indicators.items() if t == tenant_id and q in i.value]
        return rows, len(rows)

    async def seen_counts(self, tenant_id, keys, days=7):
        return {k: 3 for k in keys}


@pytest.fixture
def api(monkeypatch):
    import routers.threat_intel_api as intel_api
    from authn_authz_middleware import get_current_user

    dao = FakeDAO()
    hunts = []

    async def fetch(request):
        return 200, "203.0.113.50\n203.0.113.51\n"

    async def hunt(tenant_id, keys):
        hunts.append((tenant_id, sorted(keys)))

    monkeypatch.setattr(intel_api, "_dao", lambda: dao)
    monkeypatch.setattr(intel_api, "_fetch", lambda: fetch)
    monkeypatch.setattr(intel_api, "_retro_hunt", hunt)
    app = FastAPI()
    app.include_router(intel_api.router)
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "u1", "email": "dana@acme.example"})()
    client = TestClient(app)
    client.dao, client.hunts = dao, hunts
    return client


def test_feeds_from_templates_and_custom(api, monkeypatch):
    monkeypatch.delenv("ABUSECH_AUTH_KEY", raising=False)
    listed = api.get("/v1/security/intel/feeds", headers=H).json()
    assert listed["feeds"] == [] and any(t["name"] == "abuse.ch ThreatFox" for t in listed["templates"])
    threatfox = next(t for t in listed["templates"] if t["name"] == "abuse.ch ThreatFox")
    assert threatfox["secret_env"] == "ABUSECH_AUTH_KEY" and threatfox["secret_configured"] is False

    created = api.post("/v1/security/intel/feeds", headers=H, json={"template": "abuse.ch Feodo Tracker"})
    assert created.status_code == 201, created.text
    custom = api.post("/v1/security/intel/feeds", headers=H, json={
        "name": "Edge blocklist", "kind": "plain", "url": "https://lists.example/edge.txt", "confidence": 60})
    assert custom.status_code == 201
    bad = api.post("/v1/security/intel/feeds", headers=H, json={"name": "x", "kind": "plain", "url": "http://x"})
    assert bad.status_code == 400 and "https" in bad.json()["detail"]
    names = [f["name"] for f in api.get("/v1/security/intel/feeds", headers=H).json()["feeds"]]
    assert sorted(names) == ["Edge blocklist", "abuse.ch Feodo Tracker"]


def test_update_and_delete_a_feed(api):
    fid = api.post("/v1/security/intel/feeds", headers=H, json={"template": "abuse.ch Feodo Tracker"}).json()["id"]
    patched = api.patch(f"/v1/security/intel/feeds/{fid}", headers=H, json={"enabled": False, "interval_minutes": 30})
    assert patched.json()["enabled"] is False and patched.json()["interval_minutes"] == 30
    assert api.delete(f"/v1/security/intel/feeds/{fid}", headers=H).status_code == 204
    assert api.delete(f"/v1/security/intel/feeds/{fid}", headers=H).status_code == 404


def test_run_now_stores_indicators_and_retro_hunts_the_new_ones(api):
    fid = api.post("/v1/security/intel/feeds", headers=H, json={
        "name": "Edge", "kind": "plain", "url": "https://lists.example/edge.txt"}).json()["id"]
    result = api.post(f"/v1/security/intel/feeds/{fid}/run", headers=H).json()
    assert result["status"] == "ok" and result["count"] == 2 and len(result["new"]) == 2
    assert api.hunts == [("acme", [("ip", "203.0.113.50"), ("ip", "203.0.113.51")])]
    again = api.post(f"/v1/security/intel/feeds/{fid}/run", headers=H).json()
    assert again["new"] == [] and len(api.hunts) == 1  # nothing new, no hunt


def test_indicators_search_add_delete(api):
    added = api.post("/v1/security/intel/indicators", headers=H, json={
        "value": "hxxp://evil[.]example/x", "threat_type": "phishing", "confidence": 85, "tags": ["campaign-7"]})
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["value"] == "http://evil.example/x" and body["indicator_type"] == "url"
    assert api.hunts == [("acme", [("url", "http://evil.example/x")])]
    found = api.get("/v1/security/intel/indicators?q=evil", headers=H).json()
    assert found["total"] == 1 and found["indicators"][0]["seen_7d"] == 3
    bad = api.post("/v1/security/intel/indicators", headers=H, json={"value": "10.0.0.5"})
    assert bad.status_code == 400 and "not a usable indicator" in bad.json()["detail"]
    assert api.delete("/v1/security/intel/indicators/url/http%3A%2F%2Fevil.example%2Fx", headers=H).status_code == 204
    assert api.dao.deleted == [("acme", "url", "http://evil.example/x")]
