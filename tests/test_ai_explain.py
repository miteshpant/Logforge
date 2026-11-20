"""
"Explain this event" (Phase 9). An analyst picks an event in the Log
Explorer and asks what it is.

* gather(): the evidence: the event itself (C1); reference entries for what
  it is and what its fields mean (Windows and Sysmon event IDs, sshd and
  sudo lines, HTTP statuses, OCSF classes, common fields); the shipped
  detection rules it matches; threat intelligence for its addresses (read
  as the caller).
* template(): the explanation without AI, every sentence cited, with field
  meanings and follow-up queries that compile.
* write(): the model's explanation from the redacted evidence; sentences
  without a valid citation are dropped, queries that don't compile are
  dropped; field meanings always come from the reference.
"""

import asyncio
import json

import pytest
from ai import explain as explain_module
from ai import tools as tool_module
from ai.citations import check_citations
from ai.explain import gather, template, write
from ai.nl2query import compile_error
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.tools import ToolContext

CTX = ToolContext(tenant_id="acme", user_id="u1", roles=[{"role": "tenant_admin", "tenant_id": "acme"}])

WIN = {"ts": "2026-11-19T10:00:00+00:00", "service": "windows", "host": "WS-1", "level": "info",
       "msg": "An account failed to log on.", "attrs": {"event_id": 4625, "user": "bob", "src_ip": "203.0.113.9",
                                                       "logon_type": 3}}
SSH = {"ts": "2026-11-19T10:02:11+00:00", "service": "sshd", "host": "web-01", "level": "info",
       "msg": "Failed password for root from 203.0.113.50 port 40112 ssh2", "src_ip": "203.0.113.50",
       "user_id": "root", "attrs": {}}
HTTP = {"ts": "2026-11-19T10:05:00+00:00", "service": "checkout", "host": "web-2", "level": "error",
        "msg": "GET /api/orders 503", "status": 503, "attrs": {"path": "/api/orders", "duration_ms": 30012}}
RULE = {"id": "ssh_failed_root", "title": "Failed SSH login as root", "level": "medium",
        "tags": ["attack.credential_access", "attack.t1110.001"],
        "detection": {"selection": {"service": "sshd", "msg|contains": "Failed password for root"},
                      "condition": "selection"}}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def data(monkeypatch):
    async def indicators(value, tenant):
        if value == "203.0.113.50":
            return [{"indicator_type": "ipv4", "value": value, "threat_type": "bruteforce", "confidence": 80,
                     "source": "abuse-feed", "seen_7d": 40}]
        return []

    monkeypatch.setattr(tool_module, "_indicators", indicators)
    monkeypatch.setattr(explain_module, "library_rules", lambda: [RULE])


def sentences(out):
    return [s for section in out["sections"] for s in section["sentences"]]


def test_a_windows_failed_logon():
    bundle = run(gather(WIN, CTX))
    out = template(bundle)
    text = "\n".join(sentences(out))
    assert "failed Windows logon" in text and "4625" in text
    fields = {f["field"]: f for f in out["fields"]}
    assert "attrs.event_id" in fields and "attrs.logon_type" in fields and "attrs.src_ip" in fields
    assert fields["attrs.logon_type"]["meaning"].startswith("How the account logged on")
    assert not check_citations(text, {e.cid: e for e in bundle.evidence})["uncited"]


def test_an_ssh_failure_matching_a_rule_and_intel():
    bundle = run(gather(SSH, CTX))
    kinds = [e.kind for e in bundle.evidence]
    assert kinds[0] == "event" and "rule" in kinds and "indicator" in kinds and "reference" in kinds
    out = template(bundle)
    text = "\n".join(sentences(out))
    assert "failed SSH password login" in text and "Failed SSH login as root" in text
    assert "T1110.001" in text and "abuse-feed" in text
    assert not check_citations(text, {e.cid: e for e in bundle.evidence})["uncited"]


def test_an_http_server_error():
    out = template(run(gather(HTTP, CTX)))
    text = "\n".join(sentences(out))
    assert "server error" in text and "No shipped detection rule matches" in text


def test_follow_up_queries_compile_and_use_the_events_entities():
    out = template(run(gather(SSH, CTX)))
    queries = [q["query"] for q in out["queries"]]
    assert any('src_ip = "203.0.113.50"' in q for q in queries)
    assert any('user_id = "root"' in q for q in queries)
    assert all(compile_error(q) is None for q in queries), queries


def test_an_unknown_event_is_described_generically():
    out = template(run(gather({"service": "mystery", "msg": "zzz", "attrs": {}}, CTX)))
    assert "mystery" in sentences(out)[0]


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, text):
        self.text, self.sent = text, []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_the_model_explanation_keeps_cited_sentences_and_compiling_queries():
    bundle = run(gather(SSH, CTX))
    answer = {"what": ["A failed SSH password login for root from 203.0.113.50 [C1].", "Clearly an APT."],
              "significance": ["The address is a known brute-forcer [C99]."],
              "next_steps": ["Check for a later success from the same address [C1]."],
              "queries": [{"label": "Successes", "query": '| where src_ip = "203.0.113.50" and msg contains '
                                                          '"Accepted"'},
                          {"label": "Broken", "query": "| stats (((("}]}
    out = run(write(bundle, Scripted(json.dumps(answer)), redactor=Redactor([])))
    assert out["mode"] == "ai"
    assert sorted(out["dropped"]) == ["Clearly an APT.", "The address is a known brute-forcer [C99]."]
    assert [q["label"] for q in out["queries"]] == ["Successes"]
    assert out["fields"] == template(bundle)["fields"]


def test_the_event_is_redacted_before_it_is_sent():
    provider = Scripted(json.dumps({"what": ["x [C1]."]}))
    run(write(run(gather(WIN, CTX)), provider, redactor=Redactor(["user"])))
    assert "bob" not in provider.sent[0][-1].content


def test_an_unusable_answer_falls_back_to_the_template():
    out = run(write(run(gather(HTTP, CTX)), Scripted("no idea"), redactor=Redactor([])))
    assert out["mode"] == "template" and "model_answer_unusable" in out["flags"]


def test_windows_and_sysmon_ids_are_told_apart_by_channel_not_by_mention():
    from ai.explain import _kinds

    security = {"service": "windows", "msg": "", "attrs": {"event_id": 1102, "channel": "Security", "sysmon": "no"}}
    sysmon = {"service": "windows", "msg": "", "attrs": {"event_id": 1, "channel": "Microsoft-Windows-Sysmon/Operational"}}
    assert "audit log was cleared" in _kinds(security)[0][0]
    assert _kinds(sysmon)[0][0].startswith("Sysmon: a process was created")


def test_auditd_records():
    from ai.explain import _kinds

    event = {"service": "auditd", "msg": "type=USER_LOGIN msg=audit(1731999640.345:4105): pid=1", "attrs": {}}
    assert _kinds(event)[0][0].startswith("a user login (auditd)")
