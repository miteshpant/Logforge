"""
Running pipelines at ingest (Phase 4).

run_ingest_pipelines sits in smart ingestion, after metadata enrichment and
before normalisation, so a pipeline shapes the event before field mapping,
threat-intel matching, storage and detection see it.

* An event goes through the pipeline its shipper named (X-Logforge-Pipeline,
  carried as `logforge_pipeline` on the event) or the one routing selects.
* Kept events are stamped attrs.pipeline = {id, version}; `route` results go
  to attrs.route; dropped events are counted and removed.
* No event is silently lost: a failure (or a named pipeline that does not
  exist) puts the event's original, unprocessed form in the dead-letter
  queue with the reason. If the dead-letter queue itself cannot be written,
  the original event is stored anyway, marked with attrs.pipeline_error.
* With no pipeline for the tenant, events pass through untouched.
"""

import asyncio

import pytest

from ingest_pipeline_runner import run_ingest_pipelines
from pipeline_store import PipelineRecord, PipelineRegistry
from services.smart_ingestion_service import SmartIngestionService

NGINX = '203.0.113.9 - - [19/Nov/2026:10:00:00 +0000] "GET /login HTTP/1.1" 401 512 "-" "curl/8.4.0"'
PIPELINES = [
    {"name": "nginx", "routing": {"services": ["nginx"]}, "processors": [
        {"grok": {"field": "msg", "patterns": ["%{COMBINEDAPACHELOG}"]}},
        {"drop": {}, "if": "attrs.request == '/healthz'"},
        {"route": {"retention": "short"}, "if": "attrs.response < 400"}]},
    {"name": "manual", "processors": [{"set": {"field": "attrs.manual", "value": True}}]},
]


class DAO:
    def __init__(self, records):
        self.records = records

    async def list(self, tenant_id):
        return self.records if tenant_id == "acme" else []


class DLQ:
    def __init__(self, fail=False):
        self.entries, self.fail = [], fail

    async def add(self, tenant_id, entries):
        if self.fail:
            raise ConnectionError("clickhouse down")
        self.entries += [(tenant_id, e) for e in entries]


def registry(definitions=PIPELINES):
    return PipelineRegistry(dao=DAO([PipelineRecord.from_dict({**d, "version": 3}) for d in definitions]),
                            builtins={})


def event(msg, service="nginx", **extra):
    return {"service": service, "msg": msg, "level": "info", "attrs": {"source_format": "json"}, **extra}


def run(raw, reg=None, dlq=None, tenant="acme"):
    docs = [dict(r, attrs=dict(r.get("attrs") or {})) for r in raw]
    reg, dlq = reg or registry(), dlq if dlq is not None else DLQ()
    kept, summary = asyncio.run(run_ingest_pipelines(tenant, raw, docs, registry=reg, dlq=dlq))
    return kept, summary, dlq, reg


def test_routing_transforms_stamps_and_routes():
    kept, summary, dlq, _ = run([event(NGINX), event(NGINX.replace(" 401 ", " 200 "))])
    assert [d["attrs"]["response"] for d in kept] == [401, 200]
    assert kept[0]["attrs"]["pipeline"] == {"id": "nginx", "version": 3}
    assert "route" not in kept[0]["attrs"] and kept[1]["attrs"]["route"] == {"retention": "short"}
    assert summary == {"events": 2, "processed": 2, "dropped": 0, "failed": 0}
    assert dlq.entries == []


def test_drop_and_failure_go_where_they_should():
    raw = [event(NGINX.replace("/login", "/healthz")), event("not an access log"), event("other", service="app")]
    kept, summary, dlq, _ = run(raw)
    assert [d["msg"] for d in kept] == ["other"] and "pipeline" not in kept[0]["attrs"]
    assert summary == {"events": 3, "processed": 2, "dropped": 1, "failed": 1}
    (tenant, entry), = dlq.entries
    assert tenant == "acme" and entry["pipeline_id"] == "nginx" and entry["pipeline_version"] == 3
    assert entry["processor"] == "grok" and entry["error"] == "grok: no grok pattern matched msg"
    assert entry["event"] == raw[1]  # the original, before any processor ran


def test_the_shipper_can_name_a_pipeline():
    kept, _, dlq, _ = run([event("x", service="app", logforge_pipeline="manual"), event("y", service="app", logforge_pipeline="nope")])
    assert kept[0]["attrs"]["manual"] is True and "logforge_pipeline" not in kept[0]
    (_, entry), = dlq.entries
    assert entry["pipeline_id"] == "nope" and "not found" in entry["error"] and "logforge_pipeline" not in entry["event"]


def test_events_are_kept_when_the_dead_letter_queue_is_down():
    kept, summary, _, _ = run([event("not an access log")], dlq=DLQ(fail=True))
    assert len(kept) == 1 and kept[0]["msg"] == "not an access log"
    assert kept[0]["attrs"]["pipeline_error"] == {"pipeline": "nginx", "processor": "grok",
                                                  "error": "grok: no grok pattern matched msg"}
    assert summary["failed"] == 1


def test_no_pipelines_is_a_pass_through():
    raw = [event(NGINX)]
    kept, summary, dlq, _ = run(raw, tenant="globex")
    assert kept[0]["msg"] == NGINX and "pipeline" not in kept[0]["attrs"] and summary["processed"] == 0


def test_stats_are_recorded_per_pipeline_version():
    _, _, _, reg = run([event(NGINX), event("bad")])
    record = asyncio.run(reg.router("acme")).get("nginx")
    snapshot = reg.stats("acme", record).snapshot()
    assert snapshot["events"] == {"in": 2, "ok": 1, "dropped": 0, "failed": 1}


def test_smart_ingestion_runs_the_pipeline_before_normalisation(monkeypatch):
    import ingest_pipeline_runner

    dlq = DLQ()
    monkeypatch.setattr(ingest_pipeline_runner, "_registry", lambda: registry())
    monkeypatch.setattr(ingest_pipeline_runner, "_dlq", lambda: dlq)
    raw = [event(NGINX), event(NGINX.replace("/login", "/healthz")), event("bad")]
    result = asyncio.run(SmartIngestionService().process_logs_with_normalization(raw, "acme", "json"))
    assert len(result.log_entries) == 1 and len(result.normalized_data) == 1
    entry = result.log_entries[0]
    assert entry.attrs["clientip"] == "203.0.113.9" and entry.attrs["pipeline"]["id"] == "nginx"
    assert len(dlq.entries) == 1


@pytest.fixture(autouse=True)
def _no_publish(monkeypatch):
    import ingest_pipeline_runner

    async def nothing(*args, **kwargs):
        return None

    monkeypatch.setattr(ingest_pipeline_runner, "_publish_dead_letters", nothing)
