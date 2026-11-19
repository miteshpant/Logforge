"""
Ingest pipelines (Phase 4): an ordered list of processors, each optionally
guarded by `if`, with failure handling modelled on Elastic ingest pipelines.

    {"name": "nginx", "processors": [
        {"grok": {"field": "msg", "patterns": ["%{COMBINEDAPACHELOG}"]}},
        {"convert": {"field": "attrs.bytes", "type": "integer"}, "ignore_failure": true},
        {"drop": {}, "if": "attrs.request == '/healthz'"}],
     "on_failure": [{"set": {"field": "attrs.pipeline_error", "value": "{{_error.message}}"}}]}

When a processor fails:
1. `ignore_failure: true` -> carry on;
2. else its own `on_failure` steps run (with `_error` set), then carry on;
3. else the pipeline's `on_failure` runs and processing stops, the event is kept;
4. else the event fails, and the caller sends it to the dead-letter queue.

`drop` discards the event. Every run can record per-processor stats; a
traced run (simulation) returns the document after each step.
"""

import pytest

from pipeline_processors import ProcessorContext
from pipelines import MAX_PROCESSORS, Pipeline, PipelineError, PipelineStats, simulate

NGINX = ('203.0.113.9 - - [19/Nov/2026:10:00:00 +0000] "GET /login HTTP/1.1" 401 512 "-" "curl/8.4.0"')


def nginx_pipeline(**extra):
    return Pipeline.from_dict({"name": "nginx", "processors": [
        {"grok": {"field": "msg", "patterns": ["%{COMBINEDAPACHELOG}"]}, "tag": "parse"},
        {"date": {"field": "attrs.timestamp", "formats": ["HTTPDATE"]}},
        {"set": {"field": "level", "value": "warn"}, "if": "attrs.response >= 400"},
        {"drop": {}, "if": "attrs.request == '/healthz'"},
    ], **extra})


def test_runs_processors_in_order_with_conditions():
    result = nginx_pipeline().run({"msg": NGINX, "level": "info", "attrs": {}}, ProcessorContext())
    assert result.status == "ok"
    assert result.doc["attrs"]["clientip"] == "203.0.113.9" and result.doc["level"] == "warn"
    assert result.doc["ts"].isoformat() == "2026-11-19T10:00:00+00:00"


def test_drop():
    line = NGINX.replace("/login", "/healthz")
    assert nginx_pipeline().run({"msg": line, "attrs": {}}, ProcessorContext()).status == "dropped"


def test_unhandled_failure_fails_the_event_with_the_reason():
    result = nginx_pipeline().run({"msg": "garbage", "attrs": {}}, ProcessorContext())
    assert result.status == "failed"
    assert result.error == {"processor": "grok", "index": 0, "tag": "parse",
                            "message": "grok: no grok pattern matched msg"}


def test_ignore_failure_and_processor_on_failure():
    pipeline = Pipeline.from_dict({"name": "p", "processors": [
        {"convert": {"field": "attrs.n", "type": "integer"}, "ignore_failure": True},
        {"json": {"field": "msg"}, "on_failure": [
            {"set": {"field": "attrs.parse_error", "value": "{{_error.message}}"}}]},
        {"set": {"field": "attrs.after", "value": True}},
    ]})
    result = pipeline.run({"msg": "not json", "attrs": {"n": "x"}}, ProcessorContext())
    assert result.status == "ok" and result.doc["attrs"]["after"] is True
    assert result.doc["attrs"]["parse_error"].startswith("json: msg is not valid JSON")
    assert "_error" not in result.doc


def test_pipeline_on_failure_keeps_the_event_and_stops():
    pipeline = nginx_pipeline(on_failure=[{"set": {"field": "attrs.pipeline_error", "value": "{{_error.message}}"}},
                                          {"set": {"field": "attrs.failed_at", "value": "{{_error.processor}}"}}])
    result = pipeline.run({"msg": "garbage", "level": "info", "attrs": {}}, ProcessorContext())
    assert result.status == "ok" and result.doc["attrs"]["failed_at"] == "grok"
    assert "ts" not in result.doc  # later processors did not run


def test_failure_inside_on_failure_fails_the_event():
    pipeline = Pipeline.from_dict({"name": "p", "processors": [{"json": {"field": "msg"}}],
                                   "on_failure": [{"fail": {"message": "giving up"}}]})
    result = pipeline.run({"msg": "x", "attrs": {}}, ProcessorContext())
    assert result.status == "failed" and result.error["message"] == "giving up"


def test_a_bad_condition_at_run_time_is_a_failure_not_a_crash():
    pipeline = Pipeline.from_dict({"name": "p", "processors": [
        {"set": {"field": "attrs.x", "value": 1}, "if": "len(msg * 1000000) > 1"}]})
    result = pipeline.run({"msg": "abc", "attrs": {}}, ProcessorContext())
    assert result.status == "failed" and "too large" in result.error["message"]


def test_stats_per_processor():
    stats = PipelineStats()
    pipeline = nginx_pipeline()
    for line in [NGINX, NGINX.replace("/login", "/healthz"), "garbage"]:
        pipeline.run({"msg": line, "level": "info", "attrs": {}}, ProcessorContext(), stats=stats)
    snapshot = stats.snapshot()
    assert snapshot["events"] == {"in": 3, "ok": 1, "dropped": 1, "failed": 1}
    grok, date, set_level, drop = snapshot["processors"]
    assert (grok["type"], grok["count"], grok["failed"]) == ("grok", 3, 1)
    assert date["count"] == 2 and set_level["count"] == 2 and set_level["skipped"] == 0
    assert drop["count"] == 2 and drop["skipped"] == 1 and drop["dropped"] == 1
    assert grok["time_us"] >= 0


def test_validation():
    with pytest.raises(PipelineError, match="exactly one processor"):
        Pipeline.from_dict({"name": "p", "processors": [{"set": {"field": "a", "value": 1}, "drop": {}}]})
    with pytest.raises(PipelineError, match=r"processors\[0\]: unknown processor"):
        Pipeline.from_dict({"name": "p", "processors": [{"teleport": {}}]})
    with pytest.raises(PipelineError, match=r"processors\[0\].if: syntax error"):
        Pipeline.from_dict({"name": "p", "processors": [{"drop": {}, "if": "a ==="}]})
    with pytest.raises(PipelineError, match="name"):
        Pipeline.from_dict({"processors": []})
    with pytest.raises(PipelineError, match="at most"):
        Pipeline.from_dict({"name": "p", "processors": [{"drop": {}}] * (MAX_PROCESSORS + 1)})
    with pytest.raises(PipelineError, match="on_failure"):
        Pipeline.from_dict({"name": "p", "processors": [
            {"drop": {}, "on_failure": [{"set": {"field": "a", "value": 1}, "on_failure": [{"drop": {}}]}]}]})
    assert Pipeline.from_dict(nginx_pipeline().to_dict()).to_dict() == nginx_pipeline().to_dict()


def test_simulate_returns_each_step():
    docs = [{"msg": NGINX, "level": "info", "attrs": {}}, {"msg": "garbage", "attrs": {}}]
    results = simulate(nginx_pipeline(), docs, ProcessorContext())
    first, second = results
    assert first["status"] == "ok" and [s["processor"] for s in first["steps"]] == ["grok", "date", "set", "drop"]
    assert first["steps"][0]["doc"]["attrs"]["verb"] == "GET" and first["steps"][3]["status"] == "skipped"
    assert first["steps"][1]["doc"]["ts"] == "2026-11-19T10:00:00+00:00"  # JSON-ready
    assert second["status"] == "failed" and second["steps"][0]["status"] == "error"
    assert second["error"]["message"] == "grok: no grok pattern matched msg"
    assert docs[0]["attrs"] == {}  # the inputs are not changed
