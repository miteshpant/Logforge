"""
Investigation copilot (Phase 10). From a case, an alert or an entity, the
copilot plans read-only searches, runs the ones the analyst approves,
builds a cited timeline, proposes where it started and what to search next.
Pinning and conclusions are the analyst's to approve (the UI calls the case
API); nothing here writes.

* plan(): one or two steps per entity, each a LogforgeQL query over a window
  around the anchor (the alert's time): what else an address touched, what
  happened on a host before the alert, what a user did.
* validate_steps(): steps coming back from the analyst (possibly edited)
  must compile, keep within bounds, and be at most 8.
* run(): runs the steps through the read-only tool as the caller; events
  become a timeline (each a citation); signals score them; the earliest
  strong signals are root-cause candidates; new entities in suspicious
  events become proposed pivots.
* write(): the model's hypotheses, root cause and next steps; uncited
  sentences, root causes that aren't fetched events, and queries that don't
  compile are dropped.
"""

import asyncio
import json

import pytest
from ai import copilot
from ai import explain as explain_module
from ai import tools as tool_module
from ai.citations import check_citations
from ai.nl2query import compile_error
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.tools import ToolContext

CTX = ToolContext(tenant_id="acme", user_id="u1", roles=[{"role": "tenant_admin", "tenant_id": "acme"}])
IP = "45.155.205.233"


def ev(ts, msg, **extra):
    return {"ts": f"2026-11-19T{ts}+00:00", "service": extra.pop("service", "sshd"), "host": "bastion-01",
            "level": "info", "msg": msg, **extra}


HOST_EVENTS = (
    [ev("02:00:00", "(root) CMD (/usr/local/bin/backup.sh)", service="CRON")]
    + [ev(f"02:10:{i:02d}", f"Failed password for root from {IP} port 5{i:04d} ssh2", src_ip=IP, user_id="root")
       for i in range(15)]
    + [ev("02:13:00", f"Accepted password for root from {IP} port 50122 ssh2", src_ip=IP, user_id="root"),
       ev("02:20:00", "new user: name=svc-backup, UID=1002, GID=1002, home=/home/svc-backup", service="useradd",
          user_id="root")]
)


def run_(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def data(monkeypatch):
    return install_fakes(monkeypatch)


def install_fakes(monkeypatch):
    """The tool's data access, faked: the host and address events above."""
    queries = []

    async def logql(body, tenant):
        queries.append(body)
        q = body["query"]
        if "stats" in q and IP in q:
            return {"logs": [{"service": "sshd", "host": "bastion-01", "user_id": "root", "events": 16}],
                    "total_count": 1}
        if 'host = "bastion-01"' in q:
            return {"logs": list(reversed(HOST_EVENTS)), "total_count": len(HOST_EVENTS)}
        if IP in q:
            return {"logs": [e for e in HOST_EVENTS if e.get("src_ip") == IP], "total_count": 16}
        return {"logs": [], "total_count": 0}

    async def case(case_id, tenant):
        return {"case": {"id": "c-1", "title": "New admin on bastion-01", "status": "new", "severity": "high",
                         "entities": {"hostname": ["bastion-01"]}},
                "alerts": [{"id": "a-2", "title": "New local admin created", "severity": "high",
                            "ts": "2026-11-19T02:20:00+00:00", "mitre_techniques": ["T1136.001"],
                            "entities": {"hostname": ["bastion-01"], "user": ["svc-backup"]}}],
                "timeline": []}

    monkeypatch.setattr(tool_module, "_logql", logql)
    monkeypatch.setattr(tool_module, "_case", case)
    monkeypatch.setattr(explain_module, "library_rules", lambda: [])
    return queries


HOST = {"kind": "entity", "type": "hostname", "value": "bastion-01", "at": "2026-11-19T02:20:00+00:00"}


def test_a_case_gives_the_entities_and_the_anchor():
    context = run_(copilot.gather_context({"kind": "case", "id": "c-1"}, CTX))
    assert context.anchor.isoformat() == "2026-11-19T02:20:00+00:00"
    assert context.entities == {"hostname": ["bastion-01"], "user": ["svc-backup"]}
    assert [e.kind for e in context.bundle.evidence] == ["case", "alert"]


def test_the_plan_is_read_only_queries_around_the_anchor():
    context = run_(copilot.gather_context(HOST, CTX))
    steps = copilot.plan(context)
    assert [s.title for s in steps] == ["What happened on bastion-01 before the alert?"]
    step = steps[0]
    assert compile_error(step.query) is None and step.query.startswith('| where host = "bastion-01"')
    assert step.start == "2026-11-18T20:20:00+00:00" and step.end == "2026-11-19T02:25:00+00:00"
    ip_steps = copilot.plan(run_(copilot.gather_context({"kind": "entity", "type": "src_ip", "value": IP,
                                                        "at": "2026-11-19T02:20:00+00:00"}, CTX)))
    assert [s.title for s in ip_steps] == [f"What else did {IP} touch?", f"Events involving {IP}"]
    assert all(compile_error(s.query) is None for s in ip_steps)


def test_steps_from_the_analyst_are_checked():
    good = {"title": "mine", "query": '| where host = "x"', "start": "2026-11-19T00:00:00Z",
            "end": "2026-11-19T01:00:00Z"}
    assert copilot.validate_steps([good])[0].title == "mine"
    with pytest.raises(ValueError, match="compile"):
        copilot.validate_steps([{**good, "query": "| stats (((("}])
    with pytest.raises(ValueError, match="at most"):
        copilot.validate_steps([good] * 9)
    with pytest.raises(ValueError, match="window"):
        copilot.validate_steps([{**good, "end": "2026-11-18T00:00:00Z"}])


def test_running_builds_a_cited_timeline_and_finds_where_it_started(data):
    context = run_(copilot.gather_context(HOST, CTX))
    out = run_(copilot.run(context, copilot.plan(context), CTX))
    timeline = out["timeline"]
    assert [e["ts"] for e in timeline] == sorted(e["ts"] for e in timeline) and len(timeline) == 18
    # every step ran with its own window, as the caller
    assert data[0]["start_time"] == "2026-11-18T20:20:00+00:00"
    by_cid = {e["cid"]: e for e in timeline}
    root = by_cid[out["root_cause"][0]]
    assert root["msg"].startswith("Accepted password for root") and "after 15 failed logins" in root["signals"][0]
    assert by_cid[out["root_cause"][1]]["service"] == "useradd"
    # hypotheses cite the timeline, and nothing else
    text = "\n".join(out["hypotheses"])
    issued = {c["id"] for c in out["citations"]}
    assert not check_citations(text, {c: 1 for c in issued})["uncited"] and IP in text
    # the address seen in the suspicious events is a proposed pivot, not yet run
    assert [s["title"] for s in out["next_steps"]][:1] == [f"What else did {IP} touch?"]
    assert all(compile_error(s["query"]) is None for s in out["next_steps"])
    assert out["mode"] == "template" and out["steps"][0]["events"] == 18


def test_pivots_add_what_the_address_touched(data):
    context = run_(copilot.gather_context(HOST, CTX))
    first = run_(copilot.run(context, copilot.plan(context), CTX))
    steps = copilot.plan(context) + copilot.validate_steps(first["next_steps"][:1])
    second = run_(copilot.run(context, steps, CTX))
    assert len(second["steps"]) == 2 and second["steps"][1]["rows"][0]["events"] == 16
    assert IP not in [s.get("value") for s in second["next_steps"]]


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, text):
        self.text, self.sent = text, []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_the_model_cannot_cite_or_name_evidence_that_was_not_fetched():
    context = run_(copilot.gather_context(HOST, CTX))
    template = run_(copilot.run(context, copilot.plan(context), CTX))
    success = template["root_cause"][0]
    answer = {"hypotheses": [f"An attacker guessed root's password and logged in [{success}].",
                             "They then exfiltrated the database.", "They used Cobalt Strike [C999]."],
              "root_cause": [success, "C999"],
              "next_steps": [{"title": "Other hosts the address reached", "query": f'| where src_ip = "{IP}"'},
                             {"title": "broken", "query": "| stats (((("}]}
    provider = Scripted(json.dumps(answer))
    out = run_(copilot.write(template, context, provider, redactor=Redactor([])))
    assert out["mode"] == "ai" and out["hypotheses"] == [answer["hypotheses"][0]]
    assert sorted(out["dropped"]) == ["They then exfiltrated the database.", "They used Cobalt Strike [C999]."]
    assert out["root_cause"] == [success] and "fabricated_evidence_dropped" in out["flags"]
    assert [s["title"] for s in out["next_steps"]] == ["Other hosts the address reached"]
    assert out["timeline"] == template["timeline"]
    # the timeline went to the model with its citation ids
    assert success in provider.sent[0][-1].content


def test_an_unusable_answer_keeps_the_template():
    context = run_(copilot.gather_context(HOST, CTX))
    template = run_(copilot.run(context, copilot.plan(context), CTX))
    out = run_(copilot.write(template, context, Scripted("hmm"), redactor=Redactor([])))
    assert out["mode"] == "template" and "model_answer_unusable" in out["flags"]
    assert out["hypotheses"] == template["hypotheses"]
