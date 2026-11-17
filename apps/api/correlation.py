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

Only thresholds that can be decided while events arrive are accepted
(gt / gte / eq). "Fewer than N" is only known when a window closes, which a
streaming engine never observes.
"""

from __future__ import annotations

import re
from collections import OrderedDict, deque
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

TYPES = ("event_count", "value_count", "value_sum", "temporal", "temporal_ordered")
_THRESHOLD_TYPES = ("event_count", "value_count", "value_sum")
_OPERATORS = ("gt", "gte", "eq")
_TECHNIQUE = re.compile(r"^attack\.(t\d{4}(?:\.\d{3})?)$", re.IGNORECASE)
_TIMESPAN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


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
        )
