"""
Grounded root cause analysis (Phase 10). The statistical RCA engine's
result is the input; every finding becomes a citation, one read-only search
corroborates the root cause, and the analysis is cited: by template without
AI ("statistical"), by the model with a provider ("ai"), uncited sentences
dropped. apply() puts it into the RCA response, keeping the statistical
originals when the model's replace them.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from ai import rca
from ai import tools as tool_module
from ai.citations import check_citations
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.tools import ToolContext
from services.rca_engine import RCAResult, RootCause, TimelineEvent

T = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
CTX = ToolContext(tenant_id="acme", user_id="u1", roles=[{"role": "tenant_admin", "tenant_id": "acme"}])


def result():
    spike = TimelineEvent(T, "error_spike", "payments", "Error rate 40x baseline", 0.9, {"errors": 400})
    alert = TimelineEvent(T.replace(minute=4), "alert_triggered", "checkout", "Checkout latency p95 > 2s", 0.7, {})
    root = RootCause("error_spike", 0.75, "Error spike in payments: Error rate 40x baseline", [spike], "payments", T)
    factor = RootCause("contributing_factor", 0.7, "Checkout latency p95 > 2s", [alert], "checkout", alert.timestamp)
    return RCAResult("rca_1", "inc-9", root, [factor], [spike, alert], {"estimated_cost": 1200},
                     [{"priority": "immediate", "action": "Investigate error logs for payments"}],
                     [{"id": "inc-2", "title": "payments outage"}], 0.75, 12)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def logs(monkeypatch):
    calls = []

    async def logql(body, tenant):
        calls.append(body)
        return {"logs": [{"host": "pay-1", "msg": "connection pool exhausted", "errors": 380},
                         {"host": "pay-2", "msg": "timeout calling bank", "errors": 20}], "total_count": 2}

    monkeypatch.setattr(tool_module, "_logql", logql)
    return calls


def test_the_statistical_analysis_is_cited_and_corroborated(logs):
    bundle = rca.bundle_from(result())
    run(rca.corroborate(bundle, result(), CTX))
    assert logs[0]["start_time"] == "2026-11-19T09:45:00+00:00" and 'service = "payments"' in logs[0]["query"]
    out = rca.template(bundle, result())
    text = "\n".join(s for section in out["sections"] for s in section["sentences"])
    assert out["mode"] == "statistical"
    assert not check_citations(text, {e.cid: e for e in bundle.evidence})["uncited"]
    assert "400 error(s)" in text and "connection pool exhausted" in text and "75% confidence" in text
    assert "Checkout latency p95 > 2s" in text and "1 similar incident(s)" in text


def test_uncorroborated_picks_say_so(monkeypatch):
    async def empty(body, tenant):
        return {"logs": [], "total_count": 0}

    monkeypatch.setattr(tool_module, "_logql", empty)
    bundle = rca.bundle_from(result())
    run(rca.corroborate(bundle, result(), CTX))
    text = "\n".join(rca.template(bundle, result())["sections"][0]["sentences"])
    assert "not corroborated" in text


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, text):
        self.text, self.sent = text, []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_the_model_analysis_replaces_the_heuristic_text_and_keeps_the_statistics(logs):
    bundle = rca.bundle_from(result())
    run(rca.corroborate(bundle, result(), CTX))
    answer = {"root_cause": ["The payments connection pool ran out [C5][C1].", "A bad deploy did it."],
              "contributing": ["Checkout timed out waiting on payments [C2]."],
              "recommendations": ["Raise the pool size and add a circuit breaker [C5]."]}
    out = run(rca.write(bundle, result(), Scripted(json.dumps(answer)), redactor=Redactor([])))
    assert out["mode"] == "ai" and out["dropped"] == ["A bad deploy did it."]
    response = {"root_cause": {"type": "error_spike", "description": "Error spike in payments"},
                "recommendations": [{"action": "Investigate error logs for payments"}]}
    rca.apply(response, out)
    assert response["root_cause"]["description"] == "The payments connection pool ran out [C5][C1]."
    assert response["recommendations"][0]["action"].startswith("Raise the pool size")
    assert response["statistical"]["root_cause"]["description"] == "Error spike in payments"
    assert response["analysis"]["citations"][0]["id"] == "C1"


def test_without_ai_the_response_keeps_its_statistical_text(logs):
    bundle = rca.bundle_from(result())
    analysis = rca.template(bundle, result())
    response = rca.apply({"root_cause": {"description": "Error spike in payments"}}, analysis)
    assert response["root_cause"]["description"] == "Error spike in payments" and "statistical" not in response
    assert response["analysis"]["mode"] == "statistical"


@pytest.fixture
def rca_client(monkeypatch, logs):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import routers.ai_api as module
    from ai import assistant

    class Engine:
        async def analyze_incident(self, incident, customer_id):
            return result()

    monkeypatch.setattr(module, "get_rca_engine", lambda: Engine())

    @asynccontextmanager
    async def ai_off(**kwargs):
        raise assistant.AIUnavailable("tenant_off")
        yield  # pragma: no cover

    monkeypatch.setattr(assistant, "ai_session", ai_off)

    app = FastAPI()

    @app.middleware("http")
    async def roles(request, call_next):
        request.state.roles = [{"tenant_id": "acme", "role": "tenant_admin"}]
        return await call_next(request)

    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: type("U", (), {"id": "u1"})()
    return TestClient(app)


def test_the_rca_route_returns_the_cited_analysis_beside_the_statistics(rca_client):
    client = rca_client
    r = client.post("/v1/ai/analyze-incident", headers={"X-Customer-ID": "acme"},
                    json={"incident": {"id": "inc-9", "service": "payments"}})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["root_cause"]["description"] == "Error spike in payments: Error rate 40x baseline"
    assert body["analysis"]["mode"] == "statistical" and body["analysis"]["citations"]
    assert "connection pool exhausted" in body["analysis"]["sections"][0]["sentences"][1]
