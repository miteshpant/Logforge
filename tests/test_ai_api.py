"""
AI API (Phase 8), under /v1/ai:

  GET  /status     is AI on for this tenant, which provider, is it external
  GET  /settings   the tenant's AI settings            (tenant admin)
  PUT  /settings   opt in or out, choose a provider, add redacted fields,
                   lower budgets                        (tenant admin)
  POST /ask        a grounded answer with citations; with AI off, the
                   rule-based answer (mode: rule_based) and why
  GET  /usage      tokens and requests this month against the budget
  GET  /audit      prompts, tool calls and responses   (tenant admin)

AI is used only when the deployment enables it, lists the provider, and the
tenant has opted in. Each request is audited and counted against the
tenant's monthly token budget and per-minute rate limit.
"""

import pytest
from ai import assistant
from ai.providers import AIConfig, ProviderError, ProviderSettings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_ai_orchestrator import ScriptedProvider, answer

ACME = {"X-Customer-ID": "acme"}
GLOBEX = {"X-Customer-ID": "globex"}
CLAUDE = ProviderSettings(name="claude", kind="anthropic", model="claude-opus-5-5", api_key_env="K",
                          external=True, label="Claude (Anthropic)")
LOCAL = ProviderSettings(name="local", kind="ollama", model="llama3.1", base_url="http://o:11434", external=False)


class MemorySettings:
    def __init__(self):
        self.rows = {}

    async def get(self, tenant_id):
        return self.rows.get(tenant_id)

    async def save(self, tenant_id, settings, actor):
        self.rows[tenant_id] = settings


class MemoryAudit:
    def __init__(self):
        self.rows = []

    async def record(self, rows):
        self.rows.extend(rows)

    async def list(self, tenant_id, request_id=None, limit=200):
        rows = [r for r in self.rows if r["tenant_id"] == tenant_id and (not request_id or r["request_id"] == request_id)]
        return rows[-limit:]

    async def usage(self, tenant_id, since):
        rows = [r for r in self.rows if r["tenant_id"] == tenant_id]
        return {"tokens": sum(r["input_tokens"] + r["output_tokens"] for r in rows),
                "requests": len({r["request_id"] for r in rows})}


@pytest.fixture
def api(monkeypatch):
    import routers.ai_assistant_api as module

    state = {"config": AIConfig(enabled=True, providers={"claude": CLAUDE, "local": LOCAL},
                                monthly_token_budget=10_000, requests_per_minute=5),
             "provider": None, "fallbacks": []}
    settings, audit = MemorySettings(), MemoryAudit()
    monkeypatch.setattr(assistant, "load_config", lambda: state["config"])
    monkeypatch.setattr(assistant, "_settings_store", lambda: settings)
    monkeypatch.setattr(assistant, "_audit_store", lambda: audit)
    monkeypatch.setattr(assistant, "_build_provider", lambda p: state["provider"])

    async def fallback(question, tenant_id):
        state["fallbacks"].append((question, tenant_id))
        return {"text": "There were 12 errors in the last hour.", "generated_sql": "SELECT ...", "suggestions": []}

    monkeypatch.setattr(assistant, "_rule_based", fallback)
    assistant.reset_rate_limits()

    app = FastAPI()

    @app.middleware("http")
    async def roles(request, call_next):  # what the auth middleware leaves on the request
        tenant = request.headers.get("X-Customer-ID", "")
        role = request.headers.get("X-Test-Role", "tenant_admin")
        request.state.roles = [{"tenant_id": tenant, "role": role}]
        request.state.user = type("U", (), {"id": f"user-{role}", "email": f"{role}@x.example"})()
        request.state.tenant_id = tenant
        return await call_next(request)

    app.include_router(module.router)
    client = TestClient(app)
    client.state, client.settings, client.audit = state, settings, audit
    return client


def opt_in(api, headers=ACME, **extra):
    r = api.put("/v1/ai/settings", headers=headers, json={"enabled": True, "provider": "claude", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_ai_is_off_until_the_tenant_opts_in(api):
    status = api.get("/v1/ai/status", headers=ACME).json()
    assert status["active"] is False and status["reason_code"] == "tenant_off"
    assert [p["name"] for p in status["providers"]] == ["claude", "local"]
    r = api.post("/v1/ai/ask", headers=ACME, json={"question": "how many errors?"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "rule_based" and body["reason_code"] == "tenant_off"
    assert body["text"] == "There were 12 errors in the last hour."
    assert api.state["fallbacks"] == [("how many errors?", "acme")]
    assert api.audit.rows == []


def test_the_deployment_switch_overrides_tenants(api):
    opt_in(api)
    api.state["config"] = AIConfig(enabled=False, providers={"claude": CLAUDE})
    body = api.post("/v1/ai/ask", headers=ACME, json={"question": "q"}).json()
    assert body["mode"] == "rule_based" and body["reason_code"] == "global_off"
    assert api.get("/v1/ai/status", headers=ACME).json()["reason_code"] == "global_off"
    # a provider removed from the deployment turns AI off for tenants that chose it
    api.state["config"] = AIConfig(enabled=True, providers={"local": LOCAL})
    assert api.post("/v1/ai/ask", headers=ACME, json={"question": "q"}).json()["reason_code"] == "provider_missing"


def test_settings_are_validated_and_tenant_admin_only(api):
    assert api.put("/v1/ai/settings", headers=ACME, json={"enabled": True, "provider": "nope"}).status_code == 400
    assert api.put("/v1/ai/settings", headers=ACME, json={"enabled": True}).status_code == 400  # which provider?
    r = api.put("/v1/ai/settings", headers=ACME, json={"enabled": True, "provider": "local",
                                                       "redact_fields": ["attrs.customer_email"],
                                                       "monthly_token_budget": 50_000})
    saved = r.json()
    # a tenant may lower the deployment's budget, never raise it
    assert saved["effective"]["monthly_token_budget"] == 10_000
    assert saved["settings"]["redact_fields"] == ["attrs.customer_email"]
    assert api.get("/v1/ai/settings", headers=ACME).json()["settings"]["provider"] == "local"
    analyst = {**ACME, "X-Test-Role": "security_analyst"}
    assert api.put("/v1/ai/settings", headers=analyst, json={"enabled": False}).status_code == 403
    assert api.get("/v1/ai/audit", headers=analyst).status_code == 403
    assert api.get("/v1/ai/status", headers=analyst).status_code == 200


def test_ask_answers_with_citations_audits_and_counts(api):
    opt_in(api, redact_fields=["attrs.customer_email"])
    api.state["provider"] = ScriptedProvider(answer("I need to look at the logs to answer that."))
    api.state["provider"].name, api.state["provider"].external = "claude", True
    r = api.post("/v1/ai/ask", headers=ACME, json={"question": "hi, my token=abc123def456 is it ok?"})
    body = r.json()
    assert r.status_code == 200 and body["mode"] == "ai"
    assert body["provider"] == {"name": "claude", "model": "scripted-1", "external": True,
                                "label": "Claude (Anthropic)"}
    assert body["flags"] == ["no_citations"] and body["grounded"] is False
    rid = body["request_id"]
    audit = api.get(f"/v1/ai/audit?request_id={rid}", headers=ACME).json()["entries"]
    assert [e["kind"] for e in audit] == ["prompt", "response"]
    assert all(e["user_id"] == "user-tenant_admin" and e["provider"] == "claude" for e in audit)
    assert "abc123def456" not in str(audit)
    usage = api.get("/v1/ai/usage", headers=ACME).json()
    assert usage["tokens"] == 180 and usage["requests"] == 1 and usage["monthly_token_budget"] == 10_000
    # nothing leaks across tenants
    assert api.get("/v1/ai/audit", headers=GLOBEX).json()["entries"] == []
    assert api.get("/v1/ai/usage", headers=GLOBEX).json()["tokens"] == 0


def test_budget_and_rate_limit(api):
    opt_in(api)
    api.audit.rows.append({"tenant_id": "acme", "request_id": "old", "input_tokens": 9_000, "output_tokens": 1_000})
    api.state["provider"] = ScriptedProvider(answer("x"))
    r = api.post("/v1/ai/ask", headers=ACME, json={"question": "q"})
    assert r.status_code == 429 and "budget" in r.json()["detail"]
    api.audit.rows.clear()
    api.state["provider"] = ScriptedProvider(*[answer("ok [C1]") for _ in range(10)])
    codes = [api.post("/v1/ai/ask", headers=ACME, json={"question": "q"}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_provider_failures_are_reported_and_audited(api):
    opt_in(api)

    class Failing:
        name, model, external = "claude", "claude-opus-5-5", True

        async def chat(self, *a, **k):
            raise ProviderError("claude: Anthropic returned HTTP 529 (OverloadedError)", status=529, retryable=True)

    api.state["provider"] = Failing()
    r = api.post("/v1/ai/ask", headers=ACME, json={"question": "q"})
    assert r.status_code == 502 and "529" in r.json()["detail"]
    kinds = [e["kind"] for e in api.audit.rows]
    assert kinds == ["prompt", "error"]


def test_questions_are_bounded(api):
    assert api.post("/v1/ai/ask", headers=ACME, json={"question": ""}).status_code == 422
    assert api.post("/v1/ai/ask", headers=ACME, json={"question": "x" * 5000}).status_code == 422


def test_the_rule_based_fallback_needs_what_v1_ai_query_needs(api):
    """Security review, Phase 8: the old NLQ processor checks no per-intent
    permissions, so with AI off only callers allowed to use /v1/ai/query
    (ai:write) get its answer; others get the reason and no data."""
    analyst = {**ACME, "X-Test-Role": "security_analyst"}
    body = api.post("/v1/ai/ask", headers=analyst, json={"question": "any security events?"}).json()
    assert body["mode"] == "off" and body["reason_code"] == "tenant_off" and body["text"] == ""
    assert api.state["fallbacks"] == []
    admin = api.post("/v1/ai/ask", headers=ACME, json={"question": "any security events?"}).json()
    assert admin["mode"] == "rule_based" and api.state["fallbacks"] == [("any security events?", "acme")]


def test_usage_is_written_before_each_model_call_and_requests_are_capped(api, monkeypatch):
    """Security review, Phase 8: usage written only at the end let concurrent
    requests overshoot the budget. Each model call now flushes the request's
    audit rows and re-reads usage first, and one request has a token cap."""
    from ai.providers import AIConfig
    from test_ai_orchestrator import tool_turn

    opt_in(api)
    seen = []

    class Watching(ScriptedProvider):
        async def chat(self, messages, tools_, **kw):
            seen.append(len(api.audit.rows))
            return await super().chat(messages, tools_, **kw)

    monkeypatch.setattr("ai.tools._logql", _fake_logql)
    api.state["provider"] = Watching(tool_turn(("run_query", {"query": "error"})), answer("done [C1]."))
    assert api.post("/v1/ai/ask", headers=ACME, json={"question": "q"}).status_code == 200
    assert seen[0] >= 1 and seen[1] > seen[0]  # the first call's rows were stored before the second call

    api.state["config"] = AIConfig(enabled=True, providers={"claude": CLAUDE}, monthly_token_budget=10_000_000,
                                   requests_per_minute=50, max_request_tokens=100)
    api.state["provider"] = ScriptedProvider(tool_turn(("run_query", {"query": "error"})), answer("done [C1]."))
    r = api.post("/v1/ai/ask", headers=ACME, json={"question": "q"})
    assert r.status_code == 429 and "per request" in r.json()["detail"]


async def _fake_logql(body, customer_id):
    return {"logs": [{"service": "api", "n": 1}], "total_count": 1}


# -- Phase 9: natural language -> LogforgeQL ----------------------------------------

@pytest.fixture
def catalogue(monkeypatch):
    import routers.ai_assistant_api as module
    from test_ai_nl2query import CATALOGUE

    seen = []

    async def fake(tenant_id):
        seen.append(tenant_id)
        return CATALOGUE

    monkeypatch.setattr(module, "_catalogue", fake)
    return seen


def test_nl2query_falls_back_to_rules_when_ai_is_off(api, catalogue):
    r = api.post("/v1/ai/nl2query", headers=ACME, json={"question": "How many errors did checkout log, per host?"})
    body = r.json()
    assert r.status_code == 200 and body["mode"] == "rule_based" and body["reason_code"] == "tenant_off"
    assert body["query"] == '| where service = "checkout" and level = "error" | stats count() as count by host'
    assert body["valid"] and body["explanation"] and catalogue == ["acme"]
    assert api.audit.rows == []
    # anyone who may ask may get a draft: it reads only the field catalogue
    analyst = {**ACME, "X-Test-Role": "security_analyst"}
    assert api.post("/v1/ai/nl2query", headers=analyst, json={"question": "errors per host"}).status_code == 200


def test_nl2query_with_ai_is_audited_and_returns_the_models_query(api, catalogue):
    import json as _json

    opt_in(api)
    api.state["provider"] = ScriptedProvider(answer(_json.dumps(
        {"query": '| where level = "error" | stats count() as n by service', "explanation": "Errors per service."})))
    api.state["provider"].name = "claude"
    body = api.post("/v1/ai/nl2query", headers=ACME, json={"question": "errors per service"}).json()
    assert body["mode"] == "ai" and body["valid"] and body["query"].endswith("by service")
    assert body["provider"]["label"] == "Claude (Anthropic)" and body["request_id"]
    kinds = [e["kind"] for e in api.get(f"/v1/ai/audit?request_id={body['request_id']}", headers=ACME).json()["entries"]]
    assert kinds == ["prompt", "response"]
    assert all(e["feature"] == "nl2query" for e in api.audit.rows)


# -- Phase 9: alert and case triage -------------------------------------------------

@pytest.fixture
def triage_data(monkeypatch):
    from test_ai_triage import install_fakes

    return install_fakes(monkeypatch)


def test_triage_without_ai_is_the_cited_template(api, triage_data):
    r = api.post("/v1/ai/triage", headers=ACME, json={"kind": "alert", "id": "a-1"})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["mode"] == "template" and body["reason_code"] == "tenant_off" and body["provider"] is None
    assert [s["key"] for s in body["sections"]][0] == "what_happened" and body["citations"][0]["id"] == "C1"
    assert api.audit.rows == []
    analyst = {**ACME, "X-Test-Role": "security_analyst"}
    assert api.post("/v1/ai/triage", headers=analyst, json={"kind": "case", "id": "c-9"}).status_code == 200


def test_triage_with_ai_is_audited_and_drops_uncited_sentences(api, triage_data):
    import json as _json

    opt_in(api)
    api.state["provider"] = ScriptedProvider(answer(_json.dumps(
        {"what_happened": ["Root logged in after 15 failures [C1].", "Probably a nation state."]})))
    api.state["provider"].name = "claude"
    body = api.post("/v1/ai/triage", headers=ACME, json={"kind": "alert", "id": "a-1"}).json()
    assert body["mode"] == "ai" and body["dropped"] == ["Probably a nation state."]
    assert body["sections"][0]["sentences"] == ["Root logged in after 15 failures [C1]."]
    assert body["request_id"] and all(e["feature"] == "triage" for e in api.audit.rows)


def test_triage_errors(api, triage_data):
    assert api.post("/v1/ai/triage", headers=ACME, json={"kind": "alert", "id": "nope"}).status_code == 404
    assert api.post("/v1/ai/triage", headers=ACME, json={"kind": "rule", "id": "a-1"}).status_code == 422
    viewer = {**ACME, "X-Test-Role": "viewer"}
    assert api.post("/v1/ai/triage", headers=viewer, json={"kind": "alert", "id": "a-1"}).status_code == 403


# -- Phase 9: pipeline drafts from sample logs ----------------------------------------

def test_pipeline_draft_without_ai_is_the_heuristic(api):
    from test_ai_pipeline_draft import KV_LINES

    r = api.post("/v1/ai/pipeline-draft", headers=ACME, json={"samples": KV_LINES, "service": "fw"})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["mode"] == "heuristic" and body["reason_code"] == "tenant_off"
    assert body["report"]["parsed"] == 2 and body["pipeline"]["processors"][0] == {"kv": {"field": "msg",
                                                                                          "target": "attrs"}}
    # drafting is for people who may edit pipelines
    analyst = {**ACME, "X-Test-Role": "viewer"}
    assert api.post("/v1/ai/pipeline-draft", headers=analyst, json={"samples": KV_LINES}).status_code == 403


def test_pipeline_draft_with_ai_is_audited(api):
    import json as _json

    opt_in(api)
    regex = {"regex": {"field": "msg", "patterns": [r"^(?P<who>\w+) did (?P<what>\w+)$"]}}
    api.state["provider"] = ScriptedProvider(answer(_json.dumps({"pipeline": {"processors": [regex]},
                                                                 "explanation": "who did what"})))
    api.state["provider"].name = "claude"
    body = api.post("/v1/ai/pipeline-draft", headers=ACME,
                    json={"samples": ["alice did login", "bob did logout"]}).json()
    assert body["mode"] == "ai" and body["report"]["parsed"] == 2 and body["request_id"]
    assert all(e["feature"] == "pipeline_draft" for e in api.audit.rows)


def test_pipeline_draft_samples_are_bounded(api):
    assert api.post("/v1/ai/pipeline-draft", headers=ACME, json={"samples": []}).status_code == 422
    assert api.post("/v1/ai/pipeline-draft", headers=ACME, json={"samples": ["x"] * 51}).status_code == 422


# -- Phase 9: explain this event --------------------------------------------------------

@pytest.fixture
def no_library(monkeypatch):
    from ai import explain

    monkeypatch.setattr(explain, "library_rules", lambda: [])


def test_explain_without_ai_is_the_template(api, no_library):
    from test_ai_explain import HTTP

    r = api.post("/v1/ai/explain", headers=ACME, json={"event": HTTP})
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["mode"] == "template" and body["reason_code"] == "tenant_off"
    assert "server error" in body["sections"][0]["sentences"][0] and body["queries"] and body["fields"]
    viewer = {**ACME, "X-Test-Role": "viewer"}
    assert api.post("/v1/ai/explain", headers=viewer, json={"event": HTTP}).status_code == 403


def test_explain_with_ai_is_audited(api, no_library):
    import json as _json

    from test_ai_explain import HTTP

    opt_in(api)
    api.state["provider"] = ScriptedProvider(answer(_json.dumps({"what": ["A request failed with 503 [C1]."]})))
    api.state["provider"].name = "claude"
    body = api.post("/v1/ai/explain", headers=ACME, json={"event": HTTP}).json()
    assert body["mode"] == "ai" and body["sections"][0]["sentences"] == ["A request failed with 503 [C1]."]
    assert all(e["feature"] == "explain" for e in api.audit.rows)


def test_explain_bounds_the_event(api, no_library):
    assert api.post("/v1/ai/explain", headers=ACME, json={"event": {"msg": "x" * 40_000}}).status_code == 422
    assert api.post("/v1/ai/explain", headers=ACME, json={"event": "text"}).status_code == 422


# -- Phase 10: investigation copilot -------------------------------------------------------

@pytest.fixture
def copilot_data(monkeypatch):
    from test_ai_copilot import install_fakes

    return install_fakes(monkeypatch)


def test_copilot_plans_then_runs_what_the_analyst_approves(api, copilot_data):
    from test_ai_copilot import HOST

    plan = api.post("/v1/ai/copilot/plan", headers=ACME, json={"subject": HOST})
    assert plan.status_code == 200, plan.text
    steps = plan.json()["steps"]
    assert steps[0]["title"] == "What happened on bastion-01 before the alert?" and plan.json()["anchor"]
    # nothing ran yet: planning only
    assert copilot_data == []
    run = api.post("/v1/ai/copilot/run", headers=ACME, json={"subject": HOST, "steps": steps})
    body = run.json()
    assert run.status_code == 200, run.text
    assert body["mode"] == "template" and body["reason_code"] == "tenant_off" and len(body["timeline"]) == 18
    assert body["root_cause"] and api.audit.rows == []


def test_copilot_with_ai_is_audited(api, copilot_data):
    import json as _json

    from test_ai_copilot import HOST

    opt_in(api)
    steps = api.post("/v1/ai/copilot/plan", headers=ACME, json={"subject": HOST}).json()["steps"]
    api.state["provider"] = ScriptedProvider(answer(_json.dumps({"hypotheses": ["Root logged in [C2]."],
                                                                 "root_cause": ["C2"]})))
    api.state["provider"].name = "claude"
    body = api.post("/v1/ai/copilot/run", headers=ACME, json={"subject": HOST, "steps": steps}).json()
    assert body["mode"] == "ai" and body["hypotheses"] == ["Root logged in [C2]."] and body["request_id"]
    assert all(e["feature"] == "copilot" for e in api.audit.rows)


def test_copilot_refuses_bad_steps_and_subjects(api, copilot_data):
    from test_ai_copilot import HOST

    bad = [{"title": "x", "query": "| stats ((((", "start": "2026-11-19T00:00:00Z", "end": "2026-11-19T01:00:00Z"}]
    r = api.post("/v1/ai/copilot/run", headers=ACME, json={"subject": HOST, "steps": bad})
    assert r.status_code == 422 and "compile" in r.json()["detail"]
    assert api.post("/v1/ai/copilot/plan", headers=ACME,
                    json={"subject": {"kind": "entity", "type": "planet", "value": "x"}}).status_code == 422
    assert api.post("/v1/ai/copilot/plan", headers=ACME,
                    json={"subject": {"kind": "case", "id": "c-1"}}).status_code == 200
    viewer = {**ACME, "X-Test-Role": "viewer"}
    assert api.post("/v1/ai/copilot/plan", headers=viewer, json={"subject": HOST}).status_code == 403
