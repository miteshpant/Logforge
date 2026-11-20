"""
Entities (Phase 11): read from entities_mt / entity_edges_mt (migration 026),
which materialized views keep from logs_raw_mt. The store's queries always
bind the tenant and every value; types are checked.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from entities import TYPES, EntityError, EntityStore, query_for

T = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)


class FakeDB:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    async def fetch_all(self, sql, params):
        self.calls.append((sql, params))
        return self.rows


def run(coro):
    return asyncio.run(coro)


def test_search_binds_the_tenant_type_and_text():
    db = FakeDB([{"entity_type": "user", "value": "bob", "first_seen": T, "last_seen": T, "events": 3}])
    out = run(EntityStore(db).search("acme", "user", q="bo'b"))
    assert out == [{"entity_type": "user", "value": "bob", "first_seen": T.isoformat(), "last_seen": T.isoformat(),
                    "events": 3}]
    sql, params = db.calls[0]
    assert "customer_id = %(tenant)s" in sql and params == {"tenant": "acme", "type": "user", "q": "bo'b",
                                                            "limit": 50, "offset": 0}
    assert "bo'b" not in sql
    with pytest.raises(EntityError):
        run(EntityStore(db).search("acme", "planet"))


def test_related_reads_both_directions_of_an_edge():
    db = FakeDB([])
    run(EntityStore(db).related("acme", "host", "web-1"))
    sql, params = db.calls[0]
    assert "a_type = %(type)s AND a = %(value)s" in sql and "b_type = %(type)s AND b = %(value)s" in sql
    assert params["tenant"] == "acme" and params["value"] == "web-1"


def test_get_and_query_for():
    db = FakeDB([])
    assert run(EntityStore(db).get("acme", "ip", "1.2.3.4")) is None
    assert query_for("ip", "1.2.3.4") == ('| where src_ip = "1.2.3.4" or attrs.src_ip = "1.2.3.4" or '
                                          'attrs.dst_ip = "1.2.3.4"')
    assert set(TYPES) == {"user", "host", "ip", "service", "cloud_account"}
    with pytest.raises(EntityError):
        query_for("user", "")


def test_entity_queries_compile():
    from ai.nl2query import compile_error

    for entity_type in TYPES:
        assert compile_error(query_for(entity_type, "x")) is None, entity_type


@pytest.fixture
def api(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.entities_api as module

    rows = {"search": [{"entity_type": "host", "value": "web-1", "first_seen": T, "last_seen": T, "events": 9}],
            "get": [{"entity_type": "host", "value": "web-1", "first_seen": T, "last_seen": T, "events": 9}],
            "related": [{"entity_type": "user", "value": "bob", "first_seen": T, "last_seen": T, "events": 4}]}

    class DB:
        async def fetch_all(self, sql, params):
            if "entity_edges_mt" in sql:
                return rows["related"]
            if params.get("value") == "web-1":
                return rows["get"]
            return rows["search"] if "value" not in params else []

    monkeypatch.setattr(module, "_store", lambda: EntityStore(DB()))
    from entity_risk import rank

    alerts = [{"id": "a1", "rule_id": "lsass_dump", "title": "lsass dump", "severity": "critical",
               "ts": T.isoformat(), "mitre_techniques": ["T1003.001"], "entities": {"hostname": ["web-1"]}}]

    async def ranking(tenant):
        from entity_risk import attribute

        return rank(alerts, T), attribute(alerts), []

    async def cases(tenant, value):
        return [{"id": "c1", "title": "web-1 compromise", "status": "new", "severity": "high"}]

    monkeypatch.setattr(module, "_ranking", ranking)
    monkeypatch.setattr(module, "_cases", cases)

    async def baseline(tenant, entity_type, value):
        return [{"kind": "hour", "label": "4 event(s) at 03:00 UTC", "severity": "medium", "ts": T.isoformat()}]

    monkeypatch.setattr(module, "_baseline", baseline)
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_the_entities_api(api):
    h = {"X-Customer-ID": "acme"}
    assert api.get("/v1/entities?type=host", headers=h).json()["entities"][0]["value"] == "web-1"
    body = api.get("/v1/entities/host/web-1", headers=h).json()
    assert body["entity"]["events"] == 9 and body["related"][0]["value"] == "bob"
    assert body["query"].startswith('| where host = "web-1"')
    assert api.get("/v1/entities/host/nope", headers=h).status_code == 404
    assert api.get("/v1/entities/planet/x", headers=h).status_code == 422
    assert api.get("/v1/entities?type=planet", headers=h).status_code == 422
    assert body["risk"]["score"] > 0 and body["rank"] == 1 and body["risk"]["factors"][0]["kind"] == "alert"
    assert body["alerts"][0]["id"] == "a1" and body["cases"][0]["id"] == "c1"
    assert body["anomalies"][0]["kind"] == "hour" and body["flags"] == []
    risk = api.get("/v1/entities/risk", headers=h).json()
    assert risk["entities"][0]["value"] == "web-1" and risk["window_days"] == 14
