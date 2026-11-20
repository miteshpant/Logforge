"""Playbook branches and parallel steps: a step's `if` (the condition language,
over the alert and earlier steps' outputs) skips it when false; adjacent steps
in one `parallel` group run at the same time. Approvals and containment stay
sequential, and a skipped approval doesn't count as approved."""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from playbooks import engine, model  # noqa: E402
from test_playbooks import ALERT, INTEGRATIONS, Fakes, _runner  # noqa: E402

BRANCHING = """
name: Branching response
trigger: {on: alert}
steps:
  - id: intel
    enrich: {indicator: "{{ alert.entities.src_ip.0 }}"}
  - id: page
    if: steps.intel.output.verdict == "malicious"
    action: {integration: SOC Slack, inputs: {text: "malicious {{ alert.title }}"}}
  - id: fyi
    if: steps.intel.output.verdict != "malicious"
    action: {integration: SOC Slack, inputs: {text: "fyi {{ alert.title }}"}}
"""

PARALLEL = """
name: Parallel lookups
trigger: {on: alert}
steps:
  - id: intel
    parallel: lookups
    enrich: {indicator: "{{ alert.entities.src_ip.0 }}"}
  - id: history
    parallel: lookups
    search: {query: "| where src_ip = \\"{{ alert.entities.src_ip.0 }}\\" | stats count()"}
  - id: notify
    action: {integration: SOC Slack, inputs: {text: "{{ steps.intel.output.verdict }} / {{ steps.history.output.rows.0.n }}"}}
"""


def test_if_takes_one_branch_and_skips_the_other():
    fakes = Fakes()
    run = asyncio.run(_runner(fakes).start("acme", model.parse(BRANCHING, integrations=INTEGRATIONS), "alert",
                                           {"alert": ALERT}))
    assert run.status == "succeeded"
    assert [s["status"] for s in run.steps] == ["done", "done", "skipped"]
    assert fakes.calls == [("slack", {"text": "malicious " + ALERT["title"]})]


def test_a_parallel_group_runs_concurrently():
    class Slow(Fakes):
        async def enrich(self, tenant_id, spec, ctx):
            await asyncio.sleep(0.3)
            return {"verdict": "malicious"}

        async def search(self, tenant_id, spec, ctx):
            await asyncio.sleep(0.3)
            return {"rows": [{"n": 3}]}

    fakes = Slow()
    started = time.monotonic()
    run = asyncio.run(_runner(fakes).start("acme", model.parse(PARALLEL, integrations=INTEGRATIONS), "alert",
                                           {"alert": ALERT}))
    assert time.monotonic() - started < 0.55  # both lookups at once, not one after the other
    assert run.status == "succeeded"
    assert fakes.calls == [("slack", {"text": "malicious / 3"})]


@pytest.mark.parametrize("text, message", [
    (BRANCHING.replace('if: steps.intel.output.verdict == "malicious"', "if: verdict ==="), "if"),
    ("""
name: x
trigger: {on: alert}
steps:
  - id: a
    parallel: g
    approval: {prompt: "ok?"}
""", "parallel"),
    ("""
name: x
trigger: {on: alert}
steps:
  - id: a
    parallel: g
    enrich: {indicator: x}
  - id: b
    search: {query: "| stats count()"}
  - id: c
    parallel: g
    enrich: {indicator: y}
""", "adjacent"),
])
def test_invalid_branching_is_explained(text, message):
    with pytest.raises(model.PlaybookError, match=message):
        model.parse(text, integrations=INTEGRATIONS)


def test_a_skipped_approval_does_not_allow_containment():
    text = """
name: Contain if bad
trigger: {on: alert}
steps:
  - id: approve
    if: alert.severity == "critical"
    approval: {prompt: "Block?"}
  - id: block
    action: {integration: Firewall, inputs: {action: block_ip, target: x}}
"""
    fakes = Fakes()
    run = asyncio.run(_runner(fakes).start("acme", model.parse(text, integrations=INTEGRATIONS), "alert",
                                           {"alert": ALERT}))  # severity high: approval skipped
    assert run.steps[0]["status"] == "skipped" and run.steps[1]["status"] == "failed"
    assert "approved approval" in run.steps[1]["error"]
    assert not any(kind == "containment_webhook" for kind, _ in fakes.calls)
