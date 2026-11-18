"""
Indicator storage, the in-memory index and the feed runner (Phase 3).

* Feeds and indicators are per tenant (threat_feeds_mt, threat_indicators_mt,
  migration 018); a feed's API key is read from the environment variable it
  names, never stored.
* IndicatorIndex answers lookups from memory: exact values, and for domains
  the parent domains too (a.b.evil.example matches evil.example). Expired
  indicators don't match. Each tenant's set reloads after `ttl` seconds.
* run_feed fetches, parses (threat_feeds), applies the feed's confidence and
  TTL, upserts, records the run's status, and reports which indicators are
  new (for retro-hunting).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from threat_intel import Indicator
from threat_intel_store import (BUILTIN_FEEDS, FeedConfig, IndicatorIndex, ThreatIntelDAO, due_feeds, run_feed)

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
FIXTURES = Path(__file__).parent / "fixtures" / "threat_feeds"


def ind(value, kind="ip", expires=None, confidence=80, source="feodo"):
    return Indicator(value=value, indicator_type=kind, confidence=confidence, source=source, expires_at=expires)


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    async def fetch_all(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self.rows

    async def execute_update(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return True


def dao(rows=None):
    d = ThreatIntelDAO.__new__(ThreatIntelDAO)
    d.db = FakeDB(rows)
    return d


# --- DAO -----------------------------------------------------------------------

def test_upsert_writes_one_multi_row_insert_per_chunk():
    d = dao()
    asyncio.run(d.upsert_indicators("acme", [ind("203.0.113.1"), ind("evil.example", "domain")], feed_id="f1", now=T0))
    sql, params = d.db.calls[0]
    assert sql.startswith("INSERT INTO threat_indicators_mt") and len(d.db.calls) == 1
    assert params["tenant_id_0"] == "acme" and params["value_1"] == "evil.example" and params["feed_id_0"] == "f1"


def test_active_indicators_are_tenant_scoped_and_unexpired():
    d = dao([])
    asyncio.run(d.active_indicators("acme", now=T0))
    sql, params = d.db.calls[0]
    assert "FROM threat_indicators_mt FINAL" in sql and "tenant_id = %(tenant_id)s" in sql
    assert "deleted = 0" in sql and "(expires_at IS NULL OR expires_at > %(now)s)" in sql


def test_feed_configs_never_carry_secrets():
    feed = FeedConfig.from_dict({"name": "ThreatFox", "kind": "threatfox", "url": "https://threatfox-api.abuse.ch/api/v1/",
                                 "method": "POST", "body": {"query": "get_iocs", "days": 1},
                                 "auth_header": "Auth-Key", "secret_env": "ABUSECH_AUTH_KEY"})
    assert "secret" not in feed.to_row() or feed.to_row().get("secret_env") == "ABUSECH_AUTH_KEY"
    with pytest.raises(ValueError, match="environment variable"):
        FeedConfig.from_dict({"name": "x", "kind": "plain", "url": "https://x.example", "secret_env": "key with spaces"})
    with pytest.raises(ValueError, match="https"):
        FeedConfig.from_dict({"name": "x", "kind": "plain", "url": "ftp://x.example/list"})
    with pytest.raises(ValueError, match="kind"):
        FeedConfig.from_dict({"name": "x", "kind": "gopher", "url": "https://x.example"})


def test_builtin_feed_templates():
    names = {f["name"] for f in BUILTIN_FEEDS}
    assert {"abuse.ch Feodo Tracker", "abuse.ch URLhaus", "abuse.ch ThreatFox"} <= names
    for template in BUILTIN_FEEDS:
        FeedConfig.from_dict(template)  # all valid


# --- index -----------------------------------------------------------------------

def make_index(indicators_by_tenant):
    async def loader(tenant_id, now):
        return indicators_by_tenant.get(tenant_id, [])
    return IndicatorIndex(loader=loader, ttl_seconds=60)


def test_exact_and_parent_domain_lookups():
    index = make_index({"acme": [ind("203.0.113.1"), ind("evil.example", "domain"),
                                 ind("http://evil.example/gate.php", "url")]})
    lookup = lambda kind, value: asyncio.run(index.lookup("acme", kind, value, now=T0))  # noqa: E731
    assert lookup("ip", "203.0.113.1").value == "203.0.113.1"
    assert lookup("domain", "cdn.a.evil.example").value == "evil.example"
    assert lookup("domain", "notevil.example") is None
    assert lookup("url", "HTTP://EVIL.EXAMPLE/gate.php") is not None
    assert lookup("ip", "203.0.113.2") is None


def test_tenants_are_isolated():
    index = make_index({"acme": [ind("203.0.113.1")]})
    assert asyncio.run(index.lookup("other", "ip", "203.0.113.1", now=T0)) is None


def test_expired_indicators_do_not_match():
    index = make_index({"acme": [ind("203.0.113.1", expires=T0 - timedelta(seconds=1))]})
    assert asyncio.run(index.lookup("acme", "ip", "203.0.113.1", now=T0)) is None


def test_tenant_sets_reload_after_the_ttl():
    data = {"acme": [ind("203.0.113.1")]}
    index = make_index(data)
    assert asyncio.run(index.lookup("acme", "ip", "203.0.113.1", now=T0))
    data["acme"] = []
    assert asyncio.run(index.lookup("acme", "ip", "203.0.113.1", now=T0 + timedelta(seconds=30)))  # cached
    assert asyncio.run(index.lookup("acme", "ip", "203.0.113.1", now=T0 + timedelta(seconds=61))) is None
    index.invalidate("acme")


# --- runner ----------------------------------------------------------------------

class MemoryStore:
    def __init__(self, existing=()):
        self.keys = set(existing)
        self.upserts = []
        self.statuses = []

    async def existing_keys(self, tenant_id, keys):
        return {k for k in keys if k in self.keys}

    async def upsert_indicators(self, tenant_id, indicators, feed_id, now):
        self.upserts.append(list(indicators))
        self.keys |= {(i.indicator_type, i.normalized()) for i in indicators}

    async def record_run(self, tenant_id, feed, now, status, count, error):
        self.statuses.append((status, count, error))


def feodo_feed(**extra):
    return FeedConfig.from_dict({"id": "f1", "name": "Feodo", "kind": "feodo_json",
                                 "url": "https://feodotracker.abuse.ch/downloads/ipblocklist.json",
                                 "confidence": 90, "ttl_days": 7, **extra})


def test_run_feed_applies_confidence_and_ttl_and_reports_new_indicators(monkeypatch):
    payload = (FIXTURES / "feodo_ipblocklist.json").read_text()
    calls = []

    async def fetch(request):
        calls.append(request)
        return 200, payload

    store = MemoryStore(existing={("ip", "162.243.103.246")})
    result = asyncio.run(run_feed("acme", feodo_feed(), store, fetch=fetch, now=T0))
    assert result["status"] == "ok" and result["count"] == 5
    assert ("ip", "162.243.103.246") not in result["new"] and len(result["new"]) == 4
    stored = store.upserts[0]
    assert all(i.confidence == 90 and i.expires_at == T0 + timedelta(days=7) for i in stored)
    assert store.statuses == [("ok", 5, "")]
    assert calls[0]["method"] == "GET" and calls[0]["url"].startswith("https://feodotracker")


def test_run_feed_sends_the_auth_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("ABUSECH_AUTH_KEY", "k-123")
    seen = {}

    async def fetch(request):
        seen.update(request)
        return 200, (FIXTURES / "threatfox_iocs.json").read_text()

    feed = FeedConfig.from_dict({"id": "tf", "name": "ThreatFox", "kind": "threatfox", "method": "POST",
                                 "url": "https://threatfox-api.abuse.ch/api/v1/", "body": {"query": "get_iocs", "days": 1},
                                 "auth_header": "Auth-Key", "secret_env": "ABUSECH_AUTH_KEY"})
    result = asyncio.run(run_feed("acme", feed, MemoryStore(), fetch=fetch, now=T0))
    assert result["status"] == "ok" and seen["headers"]["Auth-Key"] == "k-123" and seen["json"]["query"] == "get_iocs"


def test_missing_secret_http_errors_and_bad_payloads_are_recorded(monkeypatch):
    monkeypatch.delenv("ABUSECH_AUTH_KEY", raising=False)
    feed = FeedConfig.from_dict({"id": "tf", "name": "ThreatFox", "kind": "threatfox", "url": "https://x.example/",
                                 "auth_header": "Auth-Key", "secret_env": "ABUSECH_AUTH_KEY"})
    store = MemoryStore()
    result = asyncio.run(run_feed("acme", feed, store, fetch=None, now=T0))
    assert result["status"] == "error" and "ABUSECH_AUTH_KEY is not set" in result["error"]

    async def gone(request):
        return 410, "<html>Gone</html>"

    result = asyncio.run(run_feed("acme", feodo_feed(), store, fetch=gone, now=T0))
    assert result["status"] == "error" and "HTTP 410" in result["error"]

    async def html(request):
        return 200, "<html>login</html>"

    result = asyncio.run(run_feed("acme", feodo_feed(), store, fetch=html, now=T0))
    assert result["status"] == "error" and "not valid JSON" in result["error"]
    assert [s[0] for s in store.statuses] == ["error", "error", "error"] and store.upserts == []


def test_due_feeds():
    fresh = feodo_feed(interval_minutes=60, last_run_at=(T0 - timedelta(minutes=10)).isoformat())
    stale = feodo_feed(id="f2", interval_minutes=60, last_run_at=(T0 - timedelta(minutes=61)).isoformat())
    never = feodo_feed(id="f3")
    off = feodo_feed(id="f4", enabled=False)
    assert [f.id for f in due_feeds([fresh, stale, never, off], T0)] == ["f2", "f3"]
