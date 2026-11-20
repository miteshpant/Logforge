"""
Case reports (Phase 10): an incident summary for management, or a
post-incident review, generated from the case and its timeline, every
sentence citing the case, an alert or a timeline entry.

* gather(): the case through the read-only tool, as the caller: the case,
  its alerts and its timeline entries (comments, status changes, pinned
  evidence that wasn't taken back, assignments) are the citations.
* template(): computed facts only: what was detected and when, the
  entities, severity and status, response times (to acknowledge, contain,
  resolve), what the analysts recorded and pinned.
* write(): the model's report from the same evidence; uncited sentences are
  dropped.
* markdown(): the report as Markdown, citations listed as sources.
"""

import asyncio
import json

import pytest
from ai import tools as tool_module
from ai.case_report import AUDIENCES, gather, markdown, template, write
from ai.citations import check_citations
from ai.providers import ChatResult, Usage
from ai.redaction import Redactor
from ai.tools import ToolContext

CTX = ToolContext(tenant_id="acme", user_id="u1", roles=[{"role": "tenant_admin", "tenant_id": "acme"}])

CASE = {
    "case": {"id": "c-7", "title": "bastion-01 compromise", "status": "resolved", "severity": "critical",
             "assignee": "dana", "entities": {"src_ip": ["45.155.205.233"], "hostname": ["bastion-01"]},
             "created_at": "2026-11-19T02:14:00+00:00", "acknowledged_at": "2026-11-19T02:30:00+00:00",
             "contained_at": "2026-11-19T03:10:00+00:00", "resolved_at": "2026-11-19T09:00:00+00:00",
             "close_reason": "Root password reset, attacker key removed"},
    "alerts": [{"id": "a-1", "title": "SSH brute force then success", "severity": "high",
                "ts": "2026-11-19T02:13:00+00:00", "mitre_techniques": ["T1110.001"],
                "entities": {"src_ip": ["45.155.205.233"], "user": ["root"]}},
               {"id": "a-2", "title": "New local admin created", "severity": "critical",
                "ts": "2026-11-19T02:20:00+00:00", "mitre_techniques": ["T1136.001"],
                "entities": {"user": ["svc-backup"]}}],
    "timeline": [
        {"id": "t1", "ts": "2026-11-19T02:14:00+00:00", "actor": "system", "kind": "created", "data": {}},
        {"id": "t2", "ts": "2026-11-19T02:30:00+00:00", "actor": "dana", "kind": "status_changed",
         "data": {"from": "new", "to": "investigating"}},
        {"id": "t3", "ts": "2026-11-19T02:41:00+00:00", "actor": "dana", "kind": "evidence_pinned",
         "data": {"kind": "search", "ref": 'src_ip = "45.155.205.233"', "title": "Logins from the attacker"}},
        {"id": "t4", "ts": "2026-11-19T02:50:00+00:00", "actor": "dana", "kind": "comment",
         "data": {"text": "Root's password was guessed; svc-backup created right after."}},
        {"id": "t5", "ts": "2026-11-19T02:55:00+00:00", "actor": "dana", "kind": "evidence_pinned",
         "data": {"kind": "event", "ref": "x", "title": "Wrong pin"}},
        {"id": "t6", "ts": "2026-11-19T02:56:00+00:00", "actor": "dana", "kind": "evidence_unpinned",
         "data": {"evidence_id": "t5"}},
        {"id": "t7", "ts": "2026-11-19T03:10:00+00:00", "actor": "dana", "kind": "status_changed",
         "data": {"from": "investigating", "to": "contained"}},
        {"id": "t8", "ts": "2026-11-19T09:00:00+00:00", "actor": "dana", "kind": "status_changed",
         "data": {"from": "contained", "to": "resolved", "reason": "Root password reset, attacker key removed"}},
    ],
}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def data(monkeypatch):
    install_fakes(monkeypatch)


def install_fakes(monkeypatch):
    async def case(case_id, tenant):
        from ai.tools import ToolError

        if case_id != "c-7":
            raise ToolError("case nope not found")
        return json.loads(json.dumps(CASE))

    monkeypatch.setattr(tool_module, "_case", case)


def text_of(report):
    return "\n".join(s for section in report["sections"] for s in section["sentences"])


@pytest.mark.parametrize("audience", AUDIENCES)
def test_the_template_report_cites_every_sentence(audience):
    bundle = run(gather("c-7", CTX))
    report = template(bundle, audience)
    text = text_of(report)
    check = check_citations(text, {e.cid: e for e in bundle.evidence})
    assert not check["uncited"] and not check["unknown"] and report["mode"] == "template"
    assert report["audience"] == audience and report["title"].startswith("bastion-01 compromise")


def test_the_review_has_response_times_and_what_was_recorded():
    report = template(run(gather("c-7", CTX)), "review")
    text = text_of(report)
    assert "16 minutes to acknowledge" in text and "56 minutes to contain" in text and "6 hours 46 minutes to resolve" in text
    assert "Root's password was guessed" in text and "Logins from the attacker" in text
    assert "Wrong pin" not in text  # taken back
    assert "T1110.001" in text and "SSH brute force then success" in text
    assert [s["key"] for s in report["sections"]] == ["detection", "response", "findings", "actions"]


def test_the_management_summary_is_short_and_plain():
    report = template(run(gather("c-7", CTX)), "management")
    text = text_of(report)
    assert [s["key"] for s in report["sections"]] == ["summary", "impact", "status"]
    assert "critical" in text and "resolved" in text and "bastion-01" in text
    assert "Root password reset, attacker key removed" in text


def test_markdown_lists_the_sources():
    report = template(run(gather("c-7", CTX)), "management")
    md = markdown(report)
    assert md.startswith("# bastion-01 compromise") and "## Sources" in md and "[C1]" in md


def test_a_missing_case():
    with pytest.raises(LookupError):
        run(gather("nope", CTX))


class Scripted:
    name, model, external = "s", "s-1", False

    def __init__(self, text):
        self.text, self.sent = text, []

    async def chat(self, messages, tools, *, max_tokens=4096, model=None):
        self.sent.append(messages)
        return ChatResult(text=self.text, tool_calls=[], stop_reason="end", usage=Usage(10, 5), model="s-1")


def test_the_model_report_keeps_only_cited_sentences():
    bundle = run(gather("c-7", CTX))
    answer = {"summary": ["An attacker guessed root's password on bastion-01 [C2].", "No data was lost."],
              "impact": ["One account was created [C3]."], "status": ["Resolved [C1]."]}
    provider = Scripted(json.dumps(answer))
    out = run(write(bundle, "management", provider, redactor=Redactor([])))
    assert out["mode"] == "ai" and out["dropped"] == ["No data was lost."]
    assert "Wrong pin" not in provider.sent[0][-1].content
