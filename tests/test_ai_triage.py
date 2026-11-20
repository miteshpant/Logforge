"""
Alert and case triage summaries (Phase 9).

* gather(): the evidence is fetched through the same read-only, permission-
  checked tools the assistant uses (the alert or case, the related activity of
  its entities, threat intelligence for its addresses); every item is a
  citation C1, C2, ...
* template(): the summary without AI. Every sentence is built from one
  evidence item and cites it, so it is cited by construction.
* write(): the model's summary, as sections of sentences. A sentence that
  cites nothing, or cites an id that wasn't issued, is dropped and reported;
  so no uncited claim reaches the analyst. If nothing usable is left, the
  template is used.
"""

import asyncio
import json
import re

import pytest
from ai import tools as tool_module
from ai.citations import check_citations
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.tools import ToolContext
from ai.triage import SECTIONS, Bundle, build_bundle, gather, template, write

ADMIN = [{"role": "tenant_admin", "tenant_id": "acme"}]
CTX = ToolContext(tenant_id="acme", user_id="u1", roles=ADMIN)

ALERT = {
    "id": "a-1", "rule_id": "ssh_brute_force", "title": "SSH brute force then success", "severity": "high",
    "status": "open", "created_at": "2026-11-20T02:13:00+00:00", "mitre_techniques": ["T1110.001"],
    "raw_log_data": {"normalized_log": {"src_ip": "45.155.205.233", "user": "root", "hostname": "bastion-01",
                                        "msg": "Accepted password for root from 45.155.205.233"}},
}
ACTIVITY = {"45.155.205.233": [{"service": "sshd", "level": "warn", "events": 15}],
            "root": [{"service": "sshd", "level": "info", "events": 3}],
            "bastion-01": []}
INTEL = {"45.155.205.233": [{"indicator_type": "ipv4", "value": "45.155.205.233", "threat_type": "bruteforce",
                             "confidence": 90, "source": "abuse-feed", "seen_7d": 15}]}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def data(monkeypatch):
    queries = []

    async def alert(alert_id, tenant):
        assert tenant == "acme"
        return dict(ALERT) if alert_id == "a-1" else None

    async def logql(body, tenant):
        queries.append(body)
        value = json.loads(re.search(r'"(?:[^"\\]|\\.)*"', body["query"]).group(0))
        return {"logs": ACTIVITY.get(value, []), "total_count": len(ACTIVITY.get(value, []))}

    async def indicators(value, tenant):
        return INTEL.get(value, [])

    async def case(case_id, tenant):
        return {"case": {"id": "c-9", "title": "bastion-01 compromise", "status": "investigating", "severity": "high",
                         "entities": {"src_ip": ["45.155.205.233"], "hostname": ["bastion-01"]}},
                "alerts": [{"id": "a-1", "title": "SSH brute force then success", "severity": "high",
                            "ts": "2026-11-20T02:13:00+00:00", "mitre_techniques": ["T1110.001"],
                            "entities": {"src_ip": ["45.155.205.233"]}},
                           {"id": "a-2", "title": "New local admin created", "severity": "critical",
                            "ts": "2026-11-20T02:20:00+00:00", "mitre_techniques": ["T1136"],
                            "entities": {"user": ["svc-backup"]}}],
                "timeline": [{"ts": "2026-11-20T02:30:00+00:00", "kind": "status", "actor": "dana",
                              "detail": "investigating"}]}

    monkeypatch.setattr(tool_module, "_alert", alert)
    monkeypatch.setattr(tool_module, "_logql", logql)
    monkeypatch.setattr(tool_module, "_indicators", indicators)
    monkeypatch.setattr(tool_module, "_case", case)
    return queries


def test_gathering_an_alert_collects_cited_evidence(data):
    bundle = run(gather("alert", "a-1", CTX))
    kinds = [e.kind for e in bundle.evidence]
    assert bundle.evidence[0].cid == "C1" and kinds[0] == "alert"
    assert kinds.count("query") == 3 and kinds.count("indicator") == 1
    assert bundle.entities == {"src_ip": ["45.155.205.233"], "user": ["root"], "hostname": ["bastion-01"]}
    assert [(t["id"], t["name"], t["tactic"]) for t in bundle.techniques] == \
        [("T1110.001", "Brute Force", "credential-access")]
    # related activity is looked up over the day before the alert, per entity
    assert all(q["since"] == "24h" for q in data) and len(data) == 3
    # by the fields that hold that kind of entity, and in the message
    assert data[0]["query"].startswith('| where src_ip = "45.155.205.233" or attrs.src_ip = ')
    assert 'msg contains "45.155.205.233"' in data[0]["query"]
    assert data[1]["query"].startswith('| where user_id = "root" or attrs.user = "root"')
    assert bundle.subject == {"kind": "alert", "id": "a-1", "title": "SSH brute force then success"}


def test_an_alert_the_caller_cannot_see_is_not_found(data):
    with pytest.raises(LookupError):
        run(gather("alert", "nope", CTX))


def test_gathering_needs_the_callers_permissions(data):
    viewer = ToolContext(tenant_id="acme", user_id="u2", roles=[{"role": "viewer", "tenant_id": "other"}])
    with pytest.raises(PermissionError):
        run(gather("alert", "a-1", viewer))


def test_the_template_cites_every_sentence(data):
    bundle = run(gather("alert", "a-1", CTX))
    out = template(bundle)
    assert out["mode"] == "template" and [s["key"] for s in out["sections"]] == [k for k, _ in SECTIONS]
    text = "\n".join(sent for s in out["sections"] for sent in s["sentences"])
    check = check_citations(text, {e.cid: e for e in bundle.evidence})
    assert not check["uncited"] and not check["unknown"]
    for fact in ("45.155.205.233", "root", "bastion-01", "T1110.001", "Brute Force", "abuse-feed"):
        assert fact in text, fact
    assert out["dropped"] == [] and out["citations"][0]["id"] == "C1"


def test_a_case_summary_covers_its_alerts(data):
    bundle = run(gather("case", "c-9", CTX))
    out = template(bundle)
    text = "\n".join(sent for s in out["sections"] for sent in s["sentences"])
    assert "New local admin created" in text and "svc-backup" in text and "T1136" in text
    assert not check_citations(text, {e.cid: e for e in bundle.evidence})["uncited"]
    assert bundle.subject["kind"] == "case"


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, text):
        self.text, self.sent = text, []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_the_model_summary_keeps_only_cited_sentences(data):
    bundle = run(gather("alert", "a-1", CTX))
    answer = {"what_happened": ["15 failed root logins came from 45.155.205.233 [C2] and then one succeeded [C1].",
                                "This is definitely an APT."],
              "attack": ["Brute force, credential access [C1]."],
              "entities": ["45.155.205.233 is on a feed [C99]."],
              "related": ["Nothing else touched bastion-01 [C4]."],
              "next_steps": ["Reset the root password on bastion-01 [C1]."]}
    provider = Scripted(f"```json\n{json.dumps(answer)}\n```")
    out = run(write(bundle, provider, redactor=Redactor([])))
    assert out["mode"] == "ai"
    assert sorted(out["dropped"]) == ["45.155.205.233 is on a feed [C99].", "This is definitely an APT."]
    text = "\n".join(sent for s in out["sections"] for sent in s["sentences"])
    assert "APT" not in text and not check_citations(text, {e.cid: e for e in bundle.evidence})["uncited"]
    # the evidence went to the model with its citation ids
    user = provider.sent[0][-1].content
    assert "[C1]" in user and "45.155.205.233" in user


def test_redaction_applies_to_the_evidence_sent(data, monkeypatch):
    bundle = run(gather("alert", "a-1", CTX))
    provider = Scripted(json.dumps({"what_happened": ["Login [C1]."]}))
    run(write(bundle, provider, redactor=Redactor(["src_ip"])))
    assert "45.155.205.233" not in provider.sent[0][-1].content


def test_an_unusable_model_answer_falls_back_to_the_template(data):
    bundle = run(gather("alert", "a-1", CTX))
    out = run(write(bundle, Scripted("I can't help with that."), redactor=Redactor([])))
    assert out["mode"] == "template" and "model_answer_unusable" in out["flags"]


def test_build_bundle_from_stored_tool_outputs():
    """The evaluation builds bundles from recorded tool outputs, without a database."""
    bundle = build_bundle("alert", "a-1", alert=ALERT, activity={"45.155.205.233": ACTIVITY["45.155.205.233"]},
                          intel=INTEL)
    assert isinstance(bundle, Bundle) and [e.cid for e in bundle.evidence] == ["C1", "C2", "C3"]
