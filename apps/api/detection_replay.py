"""
Replay a timeline of events through the detection runtime.

Used by the rule fixture gate, the detection eval harness and the backtest
endpoint, so all three judge rules exactly as the live path does:

* single-event rules match per event (the engine's selection evaluator and
  condition grammar);
* count() rules run as windowed event_count correlations;
* Sigma correlation rules consume base-rule matches (by `name` or id), and
  base rules with `generate: false` don't alert on their own.

Each replay uses a fresh CorrelationStore, so it never touches live state.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from correlation import CorrelationStore, parse_timespan

#: Default start of an expanded timeline, and spacing between plain events.
TIMELINE_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
DEFAULT_SPACING = timedelta(seconds=1)


@dataclass
class ReplayAlert:
    rule_id: str
    ts: datetime
    group: Dict[str, Any] = field(default_factory=dict)
    value: Optional[float] = None
    techniques: List[str] = field(default_factory=list)
    event: Dict[str, Any] = field(default_factory=dict)


def expand_timeline(entries: Iterable[Any], start: datetime = TIMELINE_START) -> List[Dict[str, Any]]:
    """Fixture/scenario entries -> timestamped event copies.

    * a plain event comes 1s after the previous one;
    * {repeat: N, event: {...}, every: "10s"} repeats it (default every 1s);
    * {at: "5m", event: {...}} places it at an offset from the start.
    Events that already carry `ts` keep it.
    """
    events: List[Dict[str, Any]] = []
    cursor: Optional[datetime] = None
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if "event" in entry and isinstance(entry["event"], dict):
            template = entry["event"]
            repeat = int(entry.get("repeat", 1))
            every = parse_timespan(entry["every"]) if entry.get("every") else DEFAULT_SPACING
            first = start + parse_timespan(entry["at"]) if entry.get("at") else None
        else:
            template, repeat, every, first = entry, 1, DEFAULT_SPACING, None
        for i in range(repeat):
            if first is not None:
                when = first + every * i
            else:
                when = start if cursor is None else cursor + (DEFAULT_SPACING if i == 0 else every)
            event = copy.deepcopy(template)
            event.setdefault("ts", when.isoformat())
            events.append(event)
            cursor = when
    return events


def _matcher():
    from sigma_engine import SigmaConditionEvaluator

    return SigmaConditionEvaluator()


def detection_matches(evaluator, detection: Dict[str, Any], event: Dict[str, Any]) -> bool:
    """A detection block against one event, with the engine's evaluator and
    condition grammar."""
    from sigma_condition import SigmaConditionError, evaluate_condition

    blocks = {name: block for name, block in detection.items()
              if name != "condition" and isinstance(block, dict)}
    if not blocks:
        return False
    results = {name: evaluator.evaluate_selection(event, block)[0] for name, block in blocks.items()}
    try:
        return evaluate_condition(detection.get("condition", "selection"), results)
    except SigmaConditionError:
        return False


def _techniques(rule: Dict[str, Any]) -> List[str]:
    from correlation import _TECHNIQUE

    if rule.get("attack_techniques"):
        return list(rule["attack_techniques"])
    return [m.group(1).upper() for m in (_TECHNIQUE.match(str(t)) for t in rule.get("tags") or []) if m]


def replay(rules: List[Dict[str, Any]], events: List[Dict[str, Any]],
           store: Optional[CorrelationStore] = None, tenant_id: str = "replay") -> List[ReplayAlert]:
    """Run `events` (sorted by their own time) through `rules`; return every
    alert the runtime would raise, in order."""
    from sigma_engine import CountCondition, _count_rule_name, _event_time, compile_correlation_rules

    evaluator = _matcher()
    store = store or CorrelationStore()

    correlation_dicts, count_rules, simple_rules = [], [], []
    for rule in rules:
        if rule.get("correlation"):
            correlation_dicts.append(rule)
            continue
        condition = CountCondition.parse(str((rule.get("detection") or {}).get("condition", "")))
        if condition:
            count_rules.append((rule, condition))
        else:
            simple_rules.append(rule)
    compiled, meta = compile_correlation_rules(correlation_dicts, count_rules)

    alerts: List[ReplayAlert] = []
    for event in sorted(events, key=_event_time):
        ts = _event_time(event)
        matched = set()
        for rule in simple_rules:
            if not detection_matches(evaluator, rule.get("detection") or {}, event):
                continue
            matched.add(str(rule.get("id")))
            if rule.get("name"):
                matched.add(str(rule["name"]))
            if rule.get("generate") is not False:
                alerts.append(ReplayAlert(str(rule.get("id")), ts, techniques=_techniques(rule), event=event))
        for rule, _ in count_rules:
            selection = (rule.get("detection") or {}).get("selection") or {}
            if selection and evaluator.evaluate_selection(event, selection)[0]:
                matched.add(_count_rule_name(rule))
        if compiled and matched:
            for alert in store.process(tenant_id, compiled, event, matched, ts):
                source = meta.get(alert.rule.id, {})
                alerts.append(ReplayAlert(alert.rule.id, ts, group=alert.group, value=alert.value,
                                          techniques=_techniques(source) or alert.rule.techniques,
                                          event=event))
    return alerts
