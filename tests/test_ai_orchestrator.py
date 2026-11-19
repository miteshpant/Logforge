"""
Orchestrator, citations and data controls (Phase 8).

* The model answers by calling tools; every item a tool returns gets a
  citation id (C1, C2, ...) that the model must put after the sentences
  that use it. An answer with an uncited sentence, or citing an id no tool
  returned, is flagged, never passed off as grounded.
* Before anything goes to a provider (the question and every tool result),
  configured field names and secret-looking values are redacted. The audit
  log records exactly what was sent.
* Tool errors (including permission denials) go back to the model as
  errors; the number of tool calls is capped.
"""

import asyncio
import json

import pytest
from ai import tools
from ai.citations import check_citations
from ai.orchestrator import ask
from ai.providers import ChatResult, ToolCall, Usage
from ai.redaction import Redactor
from ai.tools import Ref, ToolContext, ToolOutput

CTX = ToolContext(tenant_id="acme", user_id="u1", roles=[{"tenant_id": "acme", "role": "tenant_admin"}])


class ScriptedProvider:
    """Replies with the given results in order and records what it was sent."""

    name, kind, model, external = "scripted", "scripted", "scripted-1", True

    def __init__(self, *results):
        self.results, self.sent = list(results), []

    async def chat(self, messages, tools_, *, max_tokens=4096, model=None):
        self.sent.append([(m.role, m.content) for m in messages])
        return self.results.pop(0)


def tool_turn(*calls):
    return ChatResult(text="", tool_calls=[ToolCall(id=f"t{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)],
                      stop_reason="tool_use", usage=Usage(100, 10), model="scripted-1")


def answer(text, stop="end"):
    return ChatResult(text=text, tool_calls=[], stop_reason=stop, usage=Usage(150, 30), model="scripted-1")


@pytest.fixture
def fake_query(monkeypatch):
    async def run_query(ctx, args):
        rows = [{"ts": "2026-11-19T10:00:01", "service": "sshd", "host": "web-1", "msg": "Failed password for root",
                 "attrs": {"password": "hunter2", "auth_failure": "yes"}, "ref": 1},
                {"ts": "2026-11-19T10:00:05", "service": "sshd", "host": "web-1",
                 "msg": "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789 leaked", "ref": 2}]
        return ToolOutput(data={"ref": 0, "rows": rows, "total_count": 2},
                          refs=[Ref("query", args["query"], "/observability/logs?q=x"),
                                Ref("event", "sshd 10:00:01", "/observability/logs?q=a"),
                                Ref("event", "sshd 10:00:05", "/observability/logs?q=b")])

    monkeypatch.setitem(tools.TOOLS, "run_query", tools.Tool(
        "run_query", "q", tools.TOOLS["run_query"].input_schema, ("POST", "/v1/query/logql"), run_query))


def run(coro):
    return asyncio.run(coro)


def test_a_grounded_answer_with_citations(fake_query):
    audit = []
    provider = ScriptedProvider(tool_turn(("run_query", {"query": 'service = "sshd"'})),
                                answer("There were 2 failed SSH logins on web-1 [C1]. The first was for root [C2]."))

    async def record(kind, content, usage=None):
        audit.append((kind, content))

    result = run(ask("How many failed SSH logins? my password is hunter2", provider=provider, ctx=CTX,
                     redactor=Redactor(["password"]), audit=record))
    assert result.grounded and result.flags == []
    assert [c["id"] for c in result.citations] == ["C1", "C2"]
    assert result.citations[0]["kind"] == "query" and result.citations[1]["link"] == "/observability/logs?q=a"
    assert result.provider == {"name": "scripted", "model": "scripted-1", "external": True, "label": "scripted"}
    assert result.usage == {"input_tokens": 250, "output_tokens": 40}
    assert result.tool_calls == [{"name": "run_query", "arguments": {"query": 'service = "sshd"'}, "ok": True}]

    # the tool result went to the model with citation ids, and redacted
    second_call = provider.sent[1]
    tool_message = next(c for r, c in second_call if r == "tool")
    payload = json.loads(tool_message)
    assert payload["cite"] == "C1" and payload["rows"][0]["cite"] == "C2" and "ref" not in payload
    assert payload["rows"][0]["attrs"]["password"] == "[redacted]"
    assert "ghp_" not in tool_message and "hunter2" not in tool_message
    # ... and so did the question (a secret-looking value in free text)
    question = next(c for r, c in provider.sent[0] if r == "user")
    assert "hunter2" not in question
    # the audit log holds what was sent, not the originals
    assert [k for k, _ in audit] == ["prompt", "response", "tool_call", "tool_result", "response"]
    assert all("hunter2" not in json.dumps(c) for _, c in audit)


def test_uncited_and_invented_citations_are_flagged(fake_query):
    provider = ScriptedProvider(tool_turn(("run_query", {"query": "x"})),
                                answer("Two failed logins [C1]. The attacker is in Russia. See also [C9]."))
    result = run(ask("q", provider=provider, ctx=CTX, redactor=Redactor([])))
    assert not result.grounded
    assert set(result.flags) == {"uncited_sentences", "unknown_citations"}
    assert result.uncited == ["The attacker is in Russia."]
    assert result.unknown_citations == ["C9"]
    assert [c["id"] for c in result.citations] == ["C1"]


def test_an_answer_with_no_tool_use_is_flagged_as_ungrounded():
    result = run(ask("hello?", provider=ScriptedProvider(answer("Hi! I can help with your logs.")), ctx=CTX,
                     redactor=Redactor([])))
    assert result.flags == ["no_citations"] and not result.grounded


def test_tool_errors_go_back_to_the_model(monkeypatch):
    provider = ScriptedProvider(tool_turn(("run_query", {"query": "x"})),
                                answer("I can't run queries for you."))
    viewer = ToolContext(tenant_id="acme", user_id="u2", roles=[{"tenant_id": "acme", "role": "security_analyst"}])
    result = run(ask("q", provider=provider, ctx=viewer, redactor=Redactor([])))
    tool_message = next(c for r, c in provider.sent[1] if r == "tool")
    assert "not permitted" in tool_message
    assert result.tool_calls[0]["ok"] is False and "not permitted" in result.tool_calls[0]["error"]


def test_tool_calls_are_capped(fake_query):
    loop = [tool_turn(("run_query", {"query": f"q{i}"})) for i in range(5)]
    provider = ScriptedProvider(*loop)
    result = run(ask("q", provider=provider, ctx=CTX, redactor=Redactor([]), max_tool_calls=3))
    assert len(result.tool_calls) == 3 and "tool_limit" in result.flags
    assert len(provider.sent) == 4  # three rounds of tools, then one last turn


def test_refusals_and_budget_stops(fake_query):
    refused = run(ask("q", provider=ScriptedProvider(answer("", stop="refusal")), ctx=CTX, redactor=Redactor([])))
    assert "refused" in refused.flags and not refused.grounded

    class Stop(Exception):
        pass

    calls = []

    async def budget():
        calls.append(1)
        if len(calls) > 1:
            raise Stop("monthly token budget used up")

    with pytest.raises(Stop):
        run(ask("q", provider=ScriptedProvider(tool_turn(("run_query", {"query": "a"})), answer("x")),
                ctx=CTX, redactor=Redactor([]), before_call=budget))


# -- citations and redaction on their own ------------------------------------------------

def test_citation_checking():
    issued = {"C1": {}, "C2": {}}
    report = check_citations("Failed logins rose [C1]. Most came from one address [C1][C2].", issued)
    assert report == {"used": ["C1", "C2"], "unknown": [], "uncited": []}
    report = check_citations("Answer:\n- 3 hosts [C2]\n- nothing else", issued)
    assert report["uncited"] == ["- nothing else"]


def test_redaction():
    r = Redactor(["password", "attrs.user_email"])
    doc = {"msg": "login with Authorization: Bearer abcdefghijklmnop1234567890 ok",
           "attrs": {"db_password": "x", "user_email": "a@b.c", "nested": {"Password": "y"}, "ok": "fine"},
           "key": "AKIAIOSFODNN7EXAMPLE", "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123def456"}
    out, count = r.redact(doc)
    assert out["attrs"]["db_password"] == out["attrs"]["nested"]["Password"] == "[redacted]"
    assert out["attrs"]["user_email"] == "[redacted]" and out["attrs"]["ok"] == "fine"
    assert "abcdefghijklmnop1234567890" not in out["msg"] and out["msg"].startswith("login with Authorization")
    assert out["key"] == "[redacted]" and out["jwt"] == "[redacted]"
    assert count == 6
    text, n = r.redact("password=hunter2 and api_key: sk-live-0123456789abcdef0123")
    assert "hunter2" not in text and "sk-live" not in text and n == 2


def test_unexpected_tool_failures_become_generic_tool_errors(monkeypatch):
    async def broken(ctx, args):
        raise RuntimeError("clickhouse://admin:s3cret@db/ connection refused")

    monkeypatch.setitem(tools.TOOLS, "get_alert", tools.Tool(
        "get_alert", "a", tools.TOOLS["get_alert"].input_schema, ("GET", "/v1/security/events/{id}"), broken))
    provider = ScriptedProvider(tool_turn(("get_alert", {"alert_id": "a"})), answer("Could not fetch it."))
    result = run(ask("q", provider=provider, ctx=CTX, redactor=Redactor([])))
    sent = next(c for r, c in provider.sent[1] if r == "tool")
    assert "internal error" in sent and "s3cret" not in sent
    assert result.tool_calls[0] == {"name": "get_alert", "arguments": {"alert_id": "a"}, "ok": False,
                                    "error": "get_alert failed with an internal error"}


# -- gaps found by the Phase 8 security review ---------------------------------------

def test_redaction_catches_more_secret_forms():
    r = Redactor([])
    for text, secret in [
        ('{"password": "hunter2", "user": "bob"}', "hunter2"),
        ("GET /cb?access_token=abc123def456ghi789 HTTP/1.1", "abc123def456ghi789"),
        ("auth_token=zzz111yyy222xxx333", "zzz111yyy222xxx333"),
        ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
        ("Cookie: session=7f3a9c2e1b8d4f60", "7f3a9c2e1b8d4f60"),
        ("connecting to mysql://root:Sup3rS3cret@db:3306/app", "Sup3rS3cret"),
        ("aws_secret_access_key=wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY", "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY"),
        ("token glpat-AbCdEfGhIjKlMnOpQrSt", "glpat-AbCdEfGhIjKlMnOpQrSt"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7bq9" + "A" * 3000, "MIIEowIBAAKCAQEA7bq9"),
    ]:
        out, n = r.redact(text)
        assert secret not in out and n >= 1, (text, out)


def test_redaction_field_names_match_word_segments_and_paths_at_any_depth():
    r = Redactor(["password", "secret", "session", "credentials", "attrs.user_email"])
    doc = {"rows": [{"attrs": {"password_hash": "x1", "secret_key": "x2", "sessionid": "x3", "credentials": "x4",
                               "user_email": "a@b.c", "passenger": "keep"}}]}
    out, _ = r.redact(doc)
    attrs = out["rows"][0]["attrs"]
    assert attrs["passenger"] == "keep"
    assert all(attrs[k] == "[redacted]" for k in ("password_hash", "secret_key", "sessionid", "credentials",
                                                  "user_email"))


def test_long_values_are_redacted_before_they_are_cut(monkeypatch):
    key = "-----BEGIN PRIVATE KEY-----\n" + "Q" * 3000 + "\n-----END PRIVATE KEY-----"

    async def run_query(ctx, args):
        return ToolOutput(data={"ref": 0, "rows": [{"msg": key, "note": "x" * 5000, "ref": 0}]},
                          refs=[Ref("query", "q", "/observability/logs?q=x")])

    monkeypatch.setitem(tools.TOOLS, "run_query", tools.Tool(
        "run_query", "q", tools.TOOLS["run_query"].input_schema, ("POST", "/v1/query/logql"), run_query))
    provider = ScriptedProvider(tool_turn(("run_query", {"query": "x"})), answer("ok [C1]."))
    run(ask("q", provider=provider, ctx=CTX, redactor=Redactor([])))
    sent = next(c for r, c in provider.sent[1] if r == "tool")
    assert "QQQQ" not in sent and "[redacted]" in sent
    note = json.loads(sent)["rows"][0]["note"]   # long values are still cut, after redaction
    assert note == "x" * 2000 + "…"


def test_tool_errors_are_redacted_and_over_limit_calls_are_audited(monkeypatch):
    async def failing(ctx, args):
        raise tools.ToolError("query failed near 'password=hunter2'")

    monkeypatch.setitem(tools.TOOLS, "run_query", tools.Tool(
        "run_query", "q", tools.TOOLS["run_query"].input_schema, ("POST", "/v1/query/logql"), failing))
    audit = []

    async def record(kind, content, usage=None):
        audit.append((kind, content))

    provider = ScriptedProvider(tool_turn(("run_query", {"query": "a"}), ("run_query", {"query": "b"})),
                                answer("done"))
    run(ask("q", provider=provider, ctx=CTX, redactor=Redactor([]), audit=record, max_tool_calls=1))
    assert "hunter2" not in json.dumps(audit) and "hunter2" not in json.dumps(provider.sent)
    kinds = [k for k, _ in audit]
    assert kinds.count("tool_call") == 2 and kinds.count("tool_result") == 2
