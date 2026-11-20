"""
Playbooks (Phase 13): definitions, validation, trigger matching, and the
run engine with approvals, against fake integrations.
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from integrations.actions import ActionResult  # noqa: E402
from playbooks import engine, model  # noqa: E402

BRUTE = """
name: Brute force response
trigger:
  on: alert
  when: alert.severity in ["high", "critical"] and alert.rule_id == "ssh_brute_force"
steps:
  - id: intel
    enrich: {indicator: "{{ alert.entities.src_ip.0 }}"}
  - id: notify
    action:
      integration: SOC Slack
      inputs: {text: "[{{ alert.severity | upper }}] {{ alert.title }} (intel: {{ steps.intel.output.verdict }})"}
  - id: ticket
    action:
      integration: Jira
      inputs: {summary: "{{ alert.title }}", description: "Source {{ alert.entities.src_ip.0 }}"}
    link_case: true
  - id: approve
    approval: {prompt: "Block {{ alert.entities.src_ip.0 }} at the firewall?", timeout: 4h}
  - id: block
    action:
      integration: Firewall
      inputs: {action: block_ip, target: "{{ alert.entities.src_ip.0 }}", reason: "{{ alert.title }}"}
"""

ALERT = {"id": "a1", "title": "SSH brute force from 203.0.113.9", "severity": "high", "rule_id": "ssh_brute_force",
         "entities": {"src_ip": ["203.0.113.9"]}}
INTEGRATIONS = {"SOC Slack": {"id": "i1", "kind": "slack", "config": {}, "secrets": {"webhook_url": "https://h"}},
                "Jira": {"id": "i2", "kind": "jira_issue", "config": {}, "secrets": {}},
                "Firewall": {"id": "i3", "kind": "containment_webhook", "config": {"url": "https://fw"},
                             "secrets": {}}}


# -- definitions -----------------------------------------------------------------

def test_a_playbook_parses_and_matches_its_trigger():
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    assert [s.id for s in pb.steps] == ["intel", "notify", "ticket", "approve", "block"]
    assert pb.matches("alert", {"alert": ALERT})
    assert not pb.matches("alert", {"alert": {**ALERT, "severity": "low"}})
    assert not pb.matches("case_created", {"alert": ALERT})


@pytest.mark.parametrize("change, message", [
    (lambda y: y.replace("  - id: approve\n    approval: {prompt: \"Block {{ alert.entities.src_ip.0 }} at the "
                         "firewall?\", timeout: 4h}\n", ""), "approval"),
    (lambda y: y.replace("integration: Firewall", "integration: Nope"), "Nope"),
    (lambda y: y.replace("on: alert", "on: tuesday"), "trigger"),
    (lambda y: y.replace('alert.rule_id == "ssh_brute_force"', 'alert.rule_id ==='), "when"),
    (lambda y: y.replace("enrich:", "teleport:"), "step"),
    (lambda y: y.replace("id: notify", "id: intel"), "unique"),
    (lambda y: y.replace("{{ alert.title }}\"}", "{{ alert.__class__ }}\"}", 1), "field path"),
])
def test_invalid_playbooks_are_explained(change, message):
    with pytest.raises(model.PlaybookError, match=message):
        model.parse(change(BRUTE), integrations=INTEGRATIONS)


def test_containment_needs_an_approval_before_it_not_after():
    yaml_text = BRUTE.replace(
        "  - id: approve\n    approval: {prompt: \"Block {{ alert.entities.src_ip.0 }} at the firewall?\", "
        "timeout: 4h}\n  - id: block", "  - id: block")
    yaml_text += "  - id: approve\n    approval: {prompt: late}\n"
    with pytest.raises(model.PlaybookError, match="approval"):
        model.parse(yaml_text, integrations=INTEGRATIONS)


# -- running ---------------------------------------------------------------------

class Fakes:
    def __init__(self):
        self.calls = []

    async def action(self, integration, inputs, ctx):
        self.calls.append((integration["kind"], inputs))
        if integration["kind"] == "jira_issue":
            return ActionResult(True, 201, {"ticket": "SEC-42", "url": "https://jira/browse/SEC-42",
                                            "system": "jira"})
        return ActionResult(True, 200)

    async def enrich(self, tenant_id, spec, ctx):
        return {"verdict": "malicious", "sources": ["abuse.ch"]}

    async def search(self, tenant_id, spec, ctx):
        return {"rows": [{"n": 3}]}


def _runner(fakes, links=None):
    def link(tenant, case_id, ticket):
        (links if links is not None else []).append((case_id, ticket))

    return engine.Runner(action=fakes.action, enrich=fakes.enrich, search=fakes.search, link_ticket=link,
                         integrations=lambda tenant: INTEGRATIONS)


def test_a_run_goes_up_to_the_approval_then_waits():
    fakes, links = Fakes(), []
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    run = asyncio.run(_runner(fakes, links).start("acme", pb, "alert", {"alert": ALERT, "case": {"id": "c1"}}))
    assert run.status == "waiting_approval"
    assert [s["status"] for s in run.steps] == ["done", "done", "done", "waiting", "pending"]
    assert fakes.calls[0] == ("slack", {"text": "[HIGH] SSH brute force from 203.0.113.9 (intel: malicious)"})
    assert run.steps[2]["output"]["ticket"] == "SEC-42"
    assert links == [("c1", {"ticket": "SEC-42", "url": "https://jira/browse/SEC-42", "system": "jira",
                             "integration": "i2"})]
    assert run.steps[3]["prompt"] == "Block 203.0.113.9 at the firewall?"
    assert not any(kind == "containment_webhook" for kind, _ in fakes.calls)  # nothing contained yet


def test_approval_runs_the_containment_and_records_who():
    fakes = Fakes()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    runner = _runner(fakes)
    run = asyncio.run(runner.start("acme", pb, "alert", {"alert": ALERT}))
    run = asyncio.run(runner.decide(run, pb, "approve", "approve", user="dana", note="confirmed attacker"))
    assert run.status == "succeeded"
    assert run.steps[3]["decision"] == {"by": "dana", "approved": True, "note": "confirmed attacker",
                                        "at": run.steps[3]["decision"]["at"]}
    assert fakes.calls[-1] == ("containment_webhook", {"action": "block_ip", "target": "203.0.113.9",
                                                       "reason": "SSH brute force from 203.0.113.9"})


def test_rejection_stops_the_run_before_containment():
    fakes = Fakes()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    runner = _runner(fakes)
    run = asyncio.run(runner.start("acme", pb, "alert", {"alert": ALERT}))
    run = asyncio.run(runner.decide(run, pb, "approve", "reject", user="dana"))
    assert run.status == "rejected"
    assert run.steps[4]["status"] == "skipped"
    assert not any(kind == "containment_webhook" for kind, _ in fakes.calls)


def test_an_expired_approval_does_not_run_the_containment():
    fakes = Fakes()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    runner = _runner(fakes)
    run = asyncio.run(runner.start("acme", pb, "alert", {"alert": ALERT}))
    run.steps[3]["deadline"] = "2000-01-01T00:00:00+00:00"
    assert runner.expire(run) is True and run.status == "expired"
    with pytest.raises(engine.RunError, match="not waiting"):
        asyncio.run(runner.decide(run, pb, "approve", "approve", user="dana"))


def test_a_failed_step_stops_the_run_unless_told_to_continue():
    class Failing(Fakes):
        async def action(self, integration, inputs, ctx):
            self.calls.append((integration["kind"], inputs))
            return ActionResult(False, 500, error="HTTP 500")

    fakes = Failing()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    run = asyncio.run(_runner(fakes).start("acme", pb, "alert", {"alert": ALERT}))
    assert run.status == "failed" and run.steps[1]["error"] == "HTTP 500"
    assert [s["status"] for s in run.steps][2:] == ["pending", "pending", "pending"]
    tolerant = model.parse(BRUTE.replace("  - id: notify\n", "  - id: notify\n    on_error: continue\n"),
                           integrations=INTEGRATIONS)
    run = asyncio.run(_runner(Failing()).start("acme", tolerant, "alert", {"alert": ALERT}))
    assert run.steps[1]["status"] == "failed" and run.steps[2]["status"] == "failed"  # ticket also fails (500)
    assert run.status == "failed"


def test_run_state_survives_a_round_trip():
    fakes = Fakes()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    run = asyncio.run(_runner(fakes).start("acme", pb, "alert", {"alert": ALERT}))
    again = engine.Run.from_dict(run.to_dict())
    assert again.to_dict() == run.to_dict()


def test_containment_is_refused_at_run_time_without_an_approval():
    # a definition stored before validation existed, or edited around it
    fakes = Fakes()
    pb = model.parse(BRUTE, integrations=INTEGRATIONS)
    pb.steps = [s for s in pb.steps if s.id != "approve"]
    run = asyncio.run(_runner(fakes).start("acme", pb, "alert", {"alert": ALERT}))
    assert run.status == "failed" and "approval" in run.steps[-1]["error"]
    assert not any(kind == "containment_webhook" for kind, _ in fakes.calls)
