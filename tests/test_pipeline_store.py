"""
Pipeline storage and routing (Phase 4).

* Pipelines are stored per tenant and versioned: every save is a new row
  (ingest_pipelines_mt), the latest version wins, history is kept, and a
  delete is a tombstone version.
* Routing picks the pipeline for an event:
  1. a pipeline named by the shipper (X-Logforge-Pipeline header);
  2. otherwise the first enabled pipeline, by priority, whose routing
     matches: its `services` list contains the event's service, or its `if`
     condition is true;
  3. otherwise the tenant's default pipeline (routing.default), if any.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from pipeline_store import PipelineDAO, PipelineRecord, PipelineRegistry, PipelineRouter
from pipelines import PipelineError

T0 = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
SET = [{"set": {"field": "attrs.p", "value": "x"}}]


def record(name, **kwargs):
    return PipelineRecord.from_dict({"name": name, "processors": kwargs.pop("processors", SET), **kwargs})


def run(coro):
    return asyncio.run(coro)


class FakeDB:
    def __init__(self):
        self.rows = []

    async def execute_update(self, sql, params):
        assert sql.startswith("INSERT INTO ingest_pipelines_mt")
        self.rows.append(dict(params))

    async def fetch_all(self, sql, params=None):
        rows = [r for r in self.rows if r["tenant_id"] == params["tenant_id"]]
        if "pipeline_id" in params:
            rows = [r for r in rows if r["pipeline_id"] == params["pipeline_id"]]
        if "LIMIT 1 BY" in sql:
            latest = {}
            for r in rows:
                if r["pipeline_id"] not in latest or r["version"] > latest[r["pipeline_id"]]["version"]:
                    latest[r["pipeline_id"]] = r
            rows = list(latest.values())
        return sorted(rows, key=lambda r: -r["version"])


def test_record_validation():
    r = record("Nginx access", routing={"services": ["nginx"], "priority": 10})
    assert r.id == "nginx-access" and r.routing == {"services": ["nginx"], "if": "", "priority": 10, "default": False}
    with pytest.raises(PipelineError, match="routing.if"):
        record("x", routing={"if": "service =="})
    with pytest.raises(PipelineError, match="services"):
        record("x", routing={"services": "nginx"})
    with pytest.raises(PipelineError, match="unknown processor"):
        record("x", processors=[{"teleport": {}}])
    with pytest.raises(PipelineError, match="id"):
        PipelineRecord.from_dict({"name": "x", "id": "Bad Id!", "processors": SET})


def test_versions_latest_wins_and_delete_is_a_tombstone():
    dao = PipelineDAO(db=FakeDB())
    first = run(dao.save("acme", record("nginx"), actor="dana", now=T0))
    assert first.version == 1
    second = run(dao.save("acme", record("nginx", description="v2"), actor="dana", now=T0))
    assert second.version == 2
    run(dao.save("acme", record("other"), actor="dana", now=T0))
    assert [p.id for p in run(dao.list("acme"))] == ["nginx", "other"]
    assert run(dao.get("acme", "nginx")).description == "v2"
    assert [v.version for v in run(dao.versions("acme", "nginx"))] == [2, 1]
    run(dao.delete("acme", "nginx", actor="dana", now=T0))
    assert run(dao.get("acme", "nginx")) is None
    assert [p.id for p in run(dao.list("acme"))] == ["other"]
    assert run(dao.list("globex")) == []


def test_routing_order():
    router = PipelineRouter([
        record("catch-all", routing={"default": True}),
        record("nginx", routing={"services": ["nginx", "Ingress-Nginx"], "priority": 20}),
        record("errors", routing={"if": "level == 'error'", "priority": 10}),
        record("off", routing={"services": ["nginx"], "priority": 1}, enabled=False),
        record("manual"),  # no routing: only by header
    ])
    assert router.select({"service": "nginx", "level": "error"}).id == "errors"
    assert router.select({"service": "ingress-nginx", "level": "info"}).id == "nginx"
    assert router.select({"service": "billing", "level": "info"}).id == "catch-all"
    assert router.select({"service": "nginx"}, requested="manual").id == "manual"
    assert router.select({"service": "nginx"}, requested="off") is None  # disabled even when named
    assert PipelineRouter([record("x")]).select({"service": "x"}) is None


def test_registry_caches_per_tenant_and_invalidates():
    loads = []

    class DAO:
        async def list(self, tenant_id):
            loads.append(tenant_id)
            return [record("nginx", routing={"services": ["nginx"]})]

    registry = PipelineRegistry(dao=DAO(), ttl_seconds=60, builtins={})
    router = run(registry.router("acme"))
    assert router.select({"service": "nginx"}).id == "nginx"
    run(registry.router("acme"))
    assert loads == ["acme"]
    registry.invalidate("acme")
    run(registry.router("acme"))
    assert loads == ["acme", "acme"]


def test_builtins_are_selectable_by_name_and_shadowed_by_tenant_pipelines():
    builtin = record("syslog", description="built-in")
    registry = PipelineRegistry(dao=type("D", (), {"list": lambda self, t: _async([])})(), builtins={"syslog": builtin})
    assert run(registry.router("acme")).select({}, requested="syslog").description == "built-in"

    tenant = record("syslog", description="mine")
    registry = PipelineRegistry(dao=type("D", (), {"list": lambda self, t: _async([tenant])})(),
                                builtins={"syslog": builtin})
    assert run(registry.router("acme")).select({}, requested="syslog").description == "mine"


async def _async(value):
    return value


def test_registry_keeps_the_cached_router_when_storage_fails():
    calls = {"n": 0}

    class DAO:
        async def list(self, tenant_id):
            calls["n"] += 1
            if calls["n"] > 1:
                raise ConnectionError("down")
            return [record("nginx", routing={"services": ["nginx"]})]

    registry = PipelineRegistry(dao=DAO(), ttl_seconds=0, builtins={})
    run(registry.router("acme"))
    assert run(registry.router("acme")).select({"service": "nginx"}).id == "nginx"
    with pytest.raises(ConnectionError):
        run(PipelineRegistry(dao=DAO(), builtins={}).router("acme"))  # nothing cached yet
