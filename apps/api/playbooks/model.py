"""
Playbook definitions (Phase 13).

    name: Brute force response
    trigger:
      on: alert                      # alert | case_created | case_updated
      when: alert.severity in ["high", "critical"] and alert.rule_id == "ssh_brute_force"
    steps:
      - id: intel
        enrich: {indicator: "{{ alert.entities.src_ip.0 }}"}
      - id: notify
        action: {integration: SOC Slack, inputs: {text: "{{ alert.title }}"}}
      - id: ticket
        action: {integration: Jira, inputs: {summary: "{{ alert.title }}"}}
        link_case: true              # the ticket follows the case (and closes it)
      - id: search
        search: {query: '| where src_ip = "{{ alert.entities.src_ip.0 }}" | stats count()', since: 24h}
      - id: approve
        approval: {prompt: "Block {{ alert.entities.src_ip.0 }}?", timeout: 4h}
      - id: block
        action: {integration: Firewall, inputs: {action: block_ip, target: "{{ alert.entities.src_ip.0 }}"}}

`when` is the ingest pipelines' condition language over the run context
(alert, case). Step fields are templates (integrations/templates.py) that
also see earlier steps: `{{ steps.intel.output.verdict }}`.

A containment step (an action through a containment integration) must have
an approval step between it and the start, or the previous containment
step: nothing outside Logforge is changed without a person agreeing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

import yaml

from integrations import actions, templates

TRIGGERS = ("alert", "case_created", "case_updated")
STEP_TYPES = ("enrich", "action", "search", "approval")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_DURATION = re.compile(r"^(\d+)\s*([mhd])$")
DEFAULT_APPROVERS = ["tenant_admin", "security_analyst"]


class PlaybookError(ValueError):
    pass


def duration(text: Any, default: str = "24h") -> timedelta:
    m = _DURATION.match(str(text or default).strip())
    if not m:
        raise PlaybookError(f"timeout must look like 30m, 4h or 2d, not {text!r}")
    n, unit = int(m.group(1)), m.group(2)
    return {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]


@dataclass
class Step:
    id: str
    type: str
    spec: Dict[str, Any]
    on_error: str = "stop"
    link_case: bool = False
    containment: bool = False


@dataclass
class Playbook:
    name: str
    trigger_on: str
    when: str
    steps: List[Step]
    description: str = ""
    _cond: Optional[Callable[[Dict[str, Any]], bool]] = field(default=None, repr=False)

    def matches(self, event: str, ctx: Dict[str, Any]) -> bool:
        if event != self.trigger_on:
            return False
        if self._cond is None:
            return True
        try:
            return bool(self._cond(ctx))
        except Exception:
            return False


def parse(text: str, integrations: Optional[Dict[str, Dict[str, Any]]] = None) -> Playbook:
    """Parse and validate. `integrations` (name -> integration) checks the names steps use."""
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise PlaybookError(f"not YAML: {e}") from None
    if not isinstance(doc, dict):
        raise PlaybookError("a playbook is a mapping with name, trigger and steps")
    name = str(doc.get("name") or "").strip()
    if not name:
        raise PlaybookError("name is required")
    trigger = doc.get("trigger") or {}
    if isinstance(trigger, dict) and True in trigger and "on" not in trigger:
        trigger = {**trigger, "on": trigger.pop(True)}  # YAML 1.1 reads the key `on` as true
    if not isinstance(trigger, dict) or trigger.get("on") not in TRIGGERS:
        raise PlaybookError(f"trigger.on must be one of {', '.join(TRIGGERS)}")
    when = str(trigger.get("when") or "").strip()
    cond = None
    if when:
        from pipeline_conditions import ConditionError, compile_condition

        try:
            cond = compile_condition(when)
        except ConditionError as e:
            raise PlaybookError(f"trigger.when: {e}") from None
    raw_steps = doc.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise PlaybookError("steps must be a non-empty list")
    steps: List[Step] = []
    seen = set()
    approved_since_containment = False
    for i, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise PlaybookError(f"step {i + 1} must be a mapping")
        sid = str(raw.get("id") or f"step_{i + 1}")
        if not _ID.match(sid):
            raise PlaybookError(f"step id {sid!r}: lowercase letters, digits and _")
        if sid in seen:
            raise PlaybookError(f"step ids must be unique ({sid!r} repeats)")
        seen.add(sid)
        kinds = [t for t in STEP_TYPES if t in raw]
        if len(kinds) != 1:
            raise PlaybookError(f"step {sid!r} needs exactly one step type ({', '.join(STEP_TYPES)})")
        stype = kinds[0]
        spec = raw[stype] or {}
        if not isinstance(spec, dict):
            raise PlaybookError(f"step {sid!r}: {stype} takes a mapping")
        try:
            templates.check(spec)
        except templates.TemplateError as e:
            raise PlaybookError(f"step {sid!r}: {e}") from None
        on_error = raw.get("on_error", "stop")
        if on_error not in ("stop", "continue"):
            raise PlaybookError(f"step {sid!r}: on_error is stop or continue")
        containment = False
        if stype == "action":
            ref = spec.get("integration")
            if not ref:
                raise PlaybookError(f"step {sid!r}: action.integration is required")
            if integrations is not None:
                integration = integrations.get(ref)
                if integration is None:
                    raise PlaybookError(f"step {sid!r}: no integration named {ref!r}")
                kind = actions.KINDS.get(integration["kind"])
                containment = bool(kind and kind.containment)
            if containment and not approved_since_containment:
                raise PlaybookError(f"step {sid!r} contains (changes a system outside Logforge): put an "
                                    "approval step before it")
            if containment:
                approved_since_containment = False
        elif stype == "approval":
            if not spec.get("prompt"):
                raise PlaybookError(f"step {sid!r}: approval.prompt is required")
            duration(spec.get("timeout"))
            approved_since_containment = True
        elif stype == "search" and not spec.get("query"):
            raise PlaybookError(f"step {sid!r}: search.query is required")
        elif stype == "enrich" and not (spec.get("indicator") or spec.get("entity")):
            raise PlaybookError(f"step {sid!r}: enrich needs an indicator or an entity")
        steps.append(Step(sid, stype, spec, on_error, bool(raw.get("link_case")), containment))
    return Playbook(name=name, trigger_on=trigger["on"], when=when, steps=steps,
                    description=str(doc.get("description") or ""), _cond=cond)
