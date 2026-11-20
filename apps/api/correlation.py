"""
Sigma correlation rules: model and streaming engine (Phase 1).

A correlation rule references base Sigma rules by `name` and aggregates their
matches per group over a time span, in the Sigma correlation format:

    title: Password spraying from one source
    id: lf-c-password-spray
    level: high
    tags: [attack.credential_access, attack.t1110.003]
    correlation:
      type: value_count          # event_count | value_count | value_sum
      rules: [lf-auth-failed]    #   | temporal | temporal_ordered
      group-by: [src_ip]
      timespan: 10m
      condition: {field: user, gte: 10}

* event_count: at least N base-rule matches in the window.
* value_count: at least N distinct values of `field` in the window.
* value_sum: the sum of numeric `field` reaches N (Logforge extension).
* temporal: every referenced rule matched within the window, in any order.
* temporal_ordered: the referenced rules matched in the listed order.

A temporal or temporal_ordered rule may name `until` rules (Logforge
extension): a match of one for a group abandons that group's partial
sequence, e.g. brute force then success `until: [password_reset]`.

Correlations over alerts (Logforge extension): the reserved reference
`alerts` (or `alerts:<severity>`) matches every alert another rule raises,
with `alert.rule_id`, `alert.severity`, `alert.technique` (the rule's first,
primary technique) and `alert.techniques` set on the event. One alert counts
once, however many techniques its rule is tagged with. "Three techniques on one host in an
hour" is a value_count of alert.technique grouped by host.

Only thresholds that can be decided while events arrive are accepted
(gt / gte / eq). "Fewer than N" is only known when a window closes, which a
streaming engine never observes.
"""

from __future__ import annotations

import re
from collections import OrderedDict, deque
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

TYPES = ("event_count", "value_count", "value_sum", "temporal", "temporal_ordered")
_THRESHOLD_TYPES = ("event_count", "value_count", "value_sum")
_OPERATORS = ("gt", "gte", "eq")
_TECHNIQUE = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)
_TIMESPAN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


ALERTS = "alerts"


def is_alert_reference(name: str) -> bool:
    return name == ALERTS or name.startswith(ALERTS + ":")


class CorrelationRuleError(ValueError):
    """A correlation rule that can't be evaluated, with the reason."""


def parse_timespan(text: Any) -> timedelta:
    match = _TIMESPAN.match(str(text or ""))
    if not match:
        raise CorrelationRuleError(f"invalid timespan {text!r} (use e.g. 30s, 5m, 2h, 1d)")
    value, unit = int(match.group(1)), match.group(2)
    if value <= 0:
        raise CorrelationRuleError(f"invalid timespan {text!r}")
    return timedelta(**{_UNITS[unit]: value})


@dataclass
class CorrelationRule:
    id: str
    title: str
    level: str
    type: str
    rules: List[str]
    group_by: List[str]
    timespan: timedelta
    operator: Optional[str] = None
    threshold: Optional[float] = None
    field: Optional[str] = None
    tags: List[str] = dc_field(default_factory=list)
    #: Name other correlations can reference this one by (chaining).
    name: Optional[str] = None
    #: Base rules whose match abandons a group's partial sequence.
    until: List[str] = dc_field(default_factory=list)

    @property
    def reads_alerts(self) -> bool:
        return any(is_alert_reference(r) for r in self.references)

    @property
    def references(self) -> List[str]:
        return list(self.rules) + list(self.until)

    @property
    def techniques(self) -> List[str]:
        return [m.group(1).upper() for m in (_TECHNIQUE.match(t) for t in self.tags) if m]

    def threshold_met(self, value: float) -> bool:
        if self.operator == "gt":
            return value > self.threshold
        if self.operator == "gte":
            return value >= self.threshold
        return value == self.threshold

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationRule":
        corr = data.get("correlation")
        if not isinstance(corr, dict):
            raise CorrelationRuleError("missing correlation block")
        ctype = corr.get("type")
        if ctype not in TYPES:
            raise CorrelationRuleError(f"unsupported correlation type {ctype!r}")
        rules = corr.get("rules") or []
        if isinstance(rules, str):
            rules = [rules]
        if not rules:
            raise CorrelationRuleError("correlation needs base rules")
        if ctype in ("temporal", "temporal_ordered") and len(rules) < 2:
            raise CorrelationRuleError(f"{ctype} needs at least two base rules")

        until = corr.get("until") or []
        if isinstance(until, str):
            until = [until]
        if until and ctype not in ("temporal", "temporal_ordered"):
            raise CorrelationRuleError("until is only for temporal and temporal_ordered correlations")
        if any(is_alert_reference(str(r)) for r in rules) and not all(is_alert_reference(str(r)) for r in rules):
            raise CorrelationRuleError("a correlation over alerts can only reference alerts")
        if set(map(str, until)) & set(map(str, rules)):
            raise CorrelationRuleError("a rule can't be both in rules and in until")

        group_by = corr.get("group-by") or []
        if isinstance(group_by, str):
            group_by = [group_by]

        operator = threshold = value_field = None
        if ctype in _THRESHOLD_TYPES:
            condition = corr.get("condition")
            if not isinstance(condition, dict):
                raise CorrelationRuleError(f"{ctype} needs a condition")
            value_field = condition.get("field")
            if ctype in ("value_count", "value_sum") and not value_field:
                raise CorrelationRuleError(f"{ctype} needs condition.field")
            ops = [k for k in condition if k != "field"]
            if len(ops) != 1 or ops[0] not in _OPERATORS:
                raise CorrelationRuleError(
                    "condition must be exactly one of gt, gte or eq (only gt, gte or eq can be "
                    "decided while events stream in)")
            operator = ops[0]
            try:
                threshold = float(condition[operator])
            except (TypeError, ValueError):
                raise CorrelationRuleError("condition threshold must be a number")
            if threshold <= 0:
                raise CorrelationRuleError("condition threshold must be positive")

        return cls(
            id=str(data.get("id") or data.get("name") or ""),
            title=str(data.get("title") or ""),
            level=str(data.get("level") or "medium"),
            type=ctype,
            rules=[str(r) for r in rules],
            group_by=[str(g) for g in group_by],
            timespan=parse_timespan(corr.get("timespan")),
            operator=operator,
            threshold=threshold,
            field=value_field,
            tags=[str(t) for t in data.get("tags") or []],
            name=str(data["name"]) if data.get("name") else None,
            until=[str(u) for u in until],
        )


# ---------------------------------------------------------------------------
# Streaming engine
# ---------------------------------------------------------------------------

#: value_sum can't be bounded by its threshold (many small values add up); it
#: keeps at most this many contributions per group. Dropping the oldest can
#: only under-count, never invent an alert.
MAX_SUM_ENTRIES = 1000
#: Timestamps kept per base rule for temporal correlations.
MAX_TEMPORAL_ENTRIES = 50
#: Sample events attached to an alert.
SAMPLE_EVENTS = 10


def field_value(event: Dict[str, Any], name: str) -> Any:
    """Top-level field, then `attrs` (where ingestion keeps caller fields)
    when the column is missing or empty; dotted names walk nested objects."""
    if "." in name:
        attrs = event.get("attrs") if isinstance(event.get("attrs"), dict) else None
        for root in (event, attrs):
            current: Any = root
            for part in name.split("."):
                if not isinstance(current, dict) or part not in current:
                    current = None
                    break
                current = current[part]
            if current not in (None, ""):
                return current
        if name.startswith("ocsf."):
            # Phase 5 common schema: today's fields mapped to OCSF at read time.
            from ocsf_schema import resolve

            return resolve(event, name[len("ocsf."):])
        return None
    value = event.get(name)
    if value not in (None, ""):
        return value
    # Ingestion fills model columns the caller didn't send with "": fall back
    # to the caller's value in attrs.
    attrs = event.get("attrs")
    if isinstance(attrs, dict) and attrs.get(name) not in (None, ""):
        return attrs[name]
    return value


@dataclass
class CorrelationAlert:
    rule: CorrelationRule
    tenant_id: str
    group: Dict[str, Any]
    value: float
    first_seen: datetime
    last_seen: datetime
    events: List[Dict[str, Any]]


class _GroupState:
    """State for one (tenant, rule, group)."""

    def __init__(self, rule: CorrelationRule):
        self.rule = rule
        self.newest: Optional[datetime] = None
        if rule.type == "event_count":
            needed = int(rule.threshold) + (1 if rule.operator == "gt" else 0)
            self.entries: Deque[Tuple[datetime, Dict[str, Any]]] = deque(maxlen=max(needed, 1))
        elif rule.type == "value_sum":
            self.entries = deque(maxlen=MAX_SUM_ENTRIES)
        self.values: "OrderedDict[Any, datetime]" = OrderedDict()
        self.per_rule: Dict[str, Deque[datetime]] = {}
        self.sample: Deque[Dict[str, Any]] = deque(maxlen=SAMPLE_EVENTS)

    def size(self) -> int:
        if self.rule.type in ("event_count", "value_sum"):
            return len(self.entries)
        if self.rule.type == "value_count":
            return len(self.values)
        return max((len(d) for d in self.per_rule.values()), default=0)

    def _horizon(self) -> datetime:
        return self.newest - self.rule.timespan

    def add(self, event: Dict[str, Any], matched: Set[str], ts: datetime) -> Optional[Tuple[float, datetime]]:
        """Record the event; return (value, first_seen) if the rule fires."""
        if self.newest is None or ts > self.newest:
            self.newest = ts
        if ts < self._horizon():
            return None  # late event, outside the window
        self.sample.append(event)
        rtype = self.rule.type

        if rtype == "event_count":
            self.entries.append((ts, event))
            in_window = [t for t, _ in self.entries if t >= self._horizon()]
            if in_window and self.rule.threshold_met(len(in_window)):
                return float(len(in_window)), min(in_window)
            return None

        if rtype == "value_sum":
            try:
                amount = float(field_value(event, self.rule.field))
            except (TypeError, ValueError):
                return None
            self.entries.append((ts, amount))
            while self.entries and self.entries[0][0] < self._horizon():
                self.entries.popleft()
            total = sum(a for _, a in self.entries)
            if self.rule.threshold_met(total):
                return total, self.entries[0][0]
            return None

        if rtype == "value_count":
            value = field_value(event, self.rule.field)
            if value is None:
                return None
            self.values[value] = ts
            self.values.move_to_end(value)
            for stale in [v for v, t in self.values.items() if t < self._horizon()]:
                del self.values[stale]
            needed = int(self.rule.threshold) + (1 if self.rule.operator == "gt" else 0)
            while len(self.values) > max(needed, 1):
                self.values.popitem(last=False)
            if self.rule.threshold_met(len(self.values)):
                return float(len(self.values)), min(self.values.values())
            return None

        # temporal / temporal_ordered
        for name in matched:
            self.per_rule.setdefault(name, deque(maxlen=MAX_TEMPORAL_ENTRIES)).append(ts)
        horizon = self._horizon()
        for times in self.per_rule.values():
            while times and times[0] < horizon:
                times.popleft()
        if rtype == "temporal":
            if all(self.per_rule.get(r) for r in self.rule.rules):
                return float(len(self.rule.rules)), min(min(self.per_rule[r]) for r in self.rule.rules)
            return None
        return self._ordered_chain()

    def _ordered_chain(self) -> Optional[Tuple[float, datetime]]:
        first, *rest = self.rule.rules
        for start in sorted(self.per_rule.get(first, ())):
            previous = start
            for name in rest:
                later = [t for t in self.per_rule.get(name, ()) if t >= previous]
                if not later:
                    break
                previous = min(later)
            else:
                if previous - start <= self.rule.timespan:
                    return float(len(self.rule.rules)), start
        return None

    def reset(self) -> None:
        if hasattr(self, "entries"):
            self.entries.clear()
        self.values.clear()
        self.per_rule.clear()
        self.sample.clear()


class CorrelationStore:
    """Streaming state for all tenants' correlation rules, bounded in size."""

    def __init__(self, max_groups: int = 100_000):
        self.max_groups = max_groups
        self.evictions = 0
        self._groups: "OrderedDict[Tuple[Any, ...], _GroupState]" = OrderedDict()

    def group_count(self) -> int:
        return len(self._groups)

    def max_entries_per_group(self) -> int:
        return max((g.size() for g in self._groups.values()), default=0)

    def process(self, tenant_id: str, rules: Iterable[CorrelationRule], event: Dict[str, Any],
                matched: Set[str], ts: datetime) -> List[CorrelationAlert]:
        alerts: List[CorrelationAlert] = []
        if not matched:
            return alerts
        # A firing correlation counts as a match of its id/name for the rules
        # after it, so correlations can chain (callers order rules so that
        # referenced correlations come first).
        matched = set(matched)
        for rule in rules:
            hits = matched.intersection(rule.rules)
            aborts = rule.until and matched.intersection(rule.until)
            if not hits and not aborts:
                continue
            group = {f: field_value(event, f) for f in rule.group_by}
            key = (tenant_id, rule.id, tuple(str(group[f]) for f in rule.group_by))
            if aborts:
                # The sequence is abandoned for this group: drop its progress,
                # this event included.
                if key in self._groups:
                    self._groups[key].reset()
                continue
            state = self._groups.get(key)
            if state is None or state.rule is not rule and state.rule != rule:
                state = _GroupState(rule)
                self._groups[key] = state
            self._groups.move_to_end(key)
            fired = state.add(event, hits, ts)
            if fired:
                value, first_seen = fired
                alerts.append(CorrelationAlert(
                    rule=rule, tenant_id=tenant_id, group=group, value=value,
                    first_seen=first_seen, last_seen=state.newest, events=list(state.sample)))
                state.reset()
                matched.add(rule.id)
                if rule.name:
                    matched.add(rule.name)
            while len(self._groups) > self.max_groups:
                self._groups.popitem(last=False)
                self.evictions += 1
        return alerts


def feed_alert(store: CorrelationStore, tenant_id: str, rules: Iterable[CorrelationRule],
               event: Dict[str, Any], ts: datetime, rule_id: str, severity: str,
               techniques: Iterable[str]) -> List[CorrelationAlert]:
    """Feed an alert raised by `rule_id` to the correlations over alerts.
    Alerts of those correlations aren't fed back (no loops)."""
    # An alert without the group's fields (no host on the event) can't be
    # put with others: grouping all of them under "None" would correlate
    # unrelated alerts.
    readers = [r for r in rules if r.reads_alerts
               and all(field_value(event, f) not in (None, "") for f in r.group_by)]
    if not readers:
        return []
    names = {ALERTS, f"{ALERTS}:{str(severity or 'medium').lower()}"}
    techniques = list(techniques)
    alert_event = dict(event, alert={"rule_id": rule_id, "severity": severity,
                                     "technique": techniques[0] if techniques else None,
                                     "techniques": techniques})
    return store.process(tenant_id, readers, alert_event, names, ts)


def order_for_chaining(rules: List[CorrelationRule]) -> List[CorrelationRule]:
    """Order rules so a correlation comes after any correlation it references.
    Rules in a reference cycle are dropped (they could never fire)."""
    labels = {}
    for r in rules:
        labels[r.id] = r
        if r.name:
            labels[r.name] = r
    ordered: List[CorrelationRule] = []
    placed: Set[str] = set()
    pending = list(rules)
    while pending:
        progress = False
        for r in list(pending):
            deps = {labels[ref].id for ref in r.references if ref in labels and labels[ref] is not r}
            if deps <= placed:
                ordered.append(r)
                placed.add(r.id)
                pending.remove(r)
                progress = True
        if not progress:
            break
    return ordered


_store: Optional[CorrelationStore] = None


def get_correlation_store() -> CorrelationStore:
    """The process-wide store (group cap from CORRELATION_MAX_GROUPS)."""
    global _store
    if _store is None:
        import os

        _store = CorrelationStore(max_groups=int(os.getenv("CORRELATION_MAX_GROUPS", "100000")))
    return _store
