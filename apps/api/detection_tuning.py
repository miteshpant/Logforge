"""
Detection tuning (Phase 1): exclusions, throttling, and exclusion
suggestions from false-positive verdicts.

A tenant's tuning is a list of records:

    {"id", "rule_id" ('*' = every rule), "kind": "exclusion" | "throttle",
     "spec": {...}, "reason", ...}

* exclusion: {"conditions": {<Sigma selection>}, "expires_at"?: ISO time}.
  An alert whose event matches the conditions (same field syntax and
  modifiers as rules, `attrs` fallback included) is not raised.
* throttle: {"window": "10m", "group_by": [fields]}. At most one alert per
  rule and group per window.

Suppression only stops the alert: the match still feeds correlations, so
excluding a noisy base rule doesn't blind the sequences built on it.
"""

from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import structlog

from correlation import CorrelationRuleError, field_value, parse_timespan

logger = structlog.get_logger(__name__)

KINDS = ("exclusion", "throttle")
_FIELD = re.compile(r"^[A-Za-z0-9_@\-]+(\.[A-Za-z0-9_@\-]+)*$")
_MODIFIERS = {"contains", "startswith", "endswith", "all", "re", "regex", "gt", "gte", "lt", "lte"}
#: Fields that identify one event rather than describe a pattern, and
#: pipeline metadata every event carries; neither belongs in an exclusion.
_VOLATILE = {"ts", "timestamp", "ingested_at", "id", "event_id_internal", "trace_id", "span_id",
             "msg", "message", "attrs", "customer_id", "date", "hour",
             "host",  # alias of hostname
             "level", "log_level", "severity_num", "facility", "parser_version", "processing_version",
             "source_format", "status", "status_code"}


class TuningError(ValueError):
    """A tuning record that can't be applied, with the reason."""


def _parse_time(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise TuningError(f"expires_at is not an ISO timestamp: {value!r}")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _spec(record: Dict[str, Any]) -> Dict[str, Any]:
    spec = record.get("spec") or {}
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except ValueError:
            raise TuningError("spec is not valid JSON")
    if not isinstance(spec, dict):
        raise TuningError("spec must be an object")
    return spec


def validate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Check a tuning record; returns its parsed spec or raises TuningError."""
    if not str(record.get("rule_id") or "").strip():
        raise TuningError("rule_id is required ('*' for every rule)")
    kind = record.get("kind")
    if kind not in KINDS:
        raise TuningError(f"unsupported kind {kind!r} (use exclusion or throttle)")
    spec = _spec(record)
    if kind == "exclusion":
        conditions = spec.get("conditions")
        if not isinstance(conditions, dict) or not conditions:
            raise TuningError("an exclusion needs conditions (field: value, Sigma selection syntax)")
        for key in conditions:
            name, *modifiers = str(key).split("|")
            if not _FIELD.match(name):
                raise TuningError(f"unsupported field name {name!r}")
            unknown = [m for m in modifiers if m not in _MODIFIERS]
            if unknown:
                raise TuningError(f"unsupported modifier {unknown[0]!r}")
        _parse_time(spec.get("expires_at"))
    else:
        try:
            parse_timespan(spec.get("window"))
        except CorrelationRuleError as e:
            raise TuningError(str(e))
        group_by = spec.get("group_by", [])
        if not isinstance(group_by, list) or not all(isinstance(g, str) and _FIELD.match(g) for g in group_by):
            raise TuningError("group_by must be a list of field names")
    return spec


@dataclass
class Exclusion:
    id: str
    rule_id: str
    conditions: Dict[str, Any]
    expires_at: Optional[datetime] = None


@dataclass
class Throttle:
    id: str
    rule_id: str
    window: timedelta
    group_by: List[str] = field(default_factory=list)


class TuningSet:
    """One tenant's tuning, ready to apply."""

    def __init__(self, exclusions: List[Exclusion], throttles: List[Throttle]):
        self.exclusions = exclusions
        self.throttles = {t.rule_id: t for t in throttles}
        self._evaluator = None

    @classmethod
    def from_records(cls, records: Iterable[Dict[str, Any]]) -> "TuningSet":
        exclusions, throttles = [], []
        for record in records or []:
            try:
                spec = validate_record(record)
            except TuningError as e:
                logger.warning(f"Skipping tuning record {record.get('id')}: {e}")
                continue
            rule_id = str(record["rule_id"])
            if record["kind"] == "exclusion":
                exclusions.append(Exclusion(str(record.get("id")), rule_id, spec["conditions"],
                                            _parse_time(spec.get("expires_at"))))
            else:
                throttles.append(Throttle(str(record.get("id")), rule_id, parse_timespan(spec["window"]),
                                          list(spec.get("group_by") or [])))
        return cls(exclusions, throttles)

    def __bool__(self) -> bool:
        return bool(self.exclusions or self.throttles)

    def exclusion_for(self, rule_id: str, event: Dict[str, Any], now: datetime) -> Optional[str]:
        """Id of the exclusion that suppresses this alert, if any."""
        if not self.exclusions:
            return None
        if self._evaluator is None:
            from sigma_engine import SigmaConditionEvaluator

            self._evaluator = SigmaConditionEvaluator()
        for exclusion in self.exclusions:
            if exclusion.rule_id not in ("*", rule_id):
                continue
            if exclusion.expires_at is not None and now >= exclusion.expires_at:
                continue
            if self._evaluator.evaluate_selection(event, exclusion.conditions)[0]:
                return exclusion.id
        return None

    def throttle_for(self, rule_id: str) -> Optional[Throttle]:
        return self.throttles.get(rule_id) or self.throttles.get("*")


class Throttler:
    """Last-alert times per (tenant, rule, group), bounded with LRU eviction."""

    def __init__(self, max_keys: int = 100_000):
        self.max_keys = max_keys
        self._last: "OrderedDict[Tuple[Any, ...], datetime]" = OrderedDict()

    def size(self) -> int:
        return len(self._last)

    def allow(self, tenant_id: str, rule_id: str, throttle: Optional[Throttle], event: Dict[str, Any],
              group: Dict[str, Any], ts: datetime) -> bool:
        if throttle is None:
            return True
        values = tuple(str(group[f]) if f in group else str(field_value(event, f)) for f in throttle.group_by)
        key = (tenant_id, rule_id, values)
        last = self._last.get(key)
        if last is not None and ts - last < throttle.window:
            return False
        self._last[key] = ts
        self._last.move_to_end(key)
        while len(self._last) > self.max_keys:
            self._last.popitem(last=False)
        return True


def _flatten(event: Dict[str, Any]) -> Dict[str, str]:
    """Scalar fields of an event, attrs merged in (as rules see them)."""
    flat: Dict[str, str] = {}
    attrs = event.get("attrs") if isinstance(event.get("attrs"), dict) else {}
    # attrs first, then non-empty columns on top: a filled column wins, as in
    # the engine's field lookup.
    for source in (attrs, event):
        for key, value in source.items():
            if key in _VOLATILE or isinstance(value, (dict, list)) or value in (None, ""):
                continue
            flat[key] = str(value)
    return flat


def suggest_exclusion(false_positives: List[Dict[str, Any]], others: List[Dict[str, Any]],
                      min_false_positives: int = 3, min_support: float = 0.8) -> Dict[str, Any]:
    """Propose exclusion conditions from events analysts marked false
    positive: the field values present in at least `min_support` of them.
    `would_also_suppress` counts the rule's other detections that the
    exclusion would hide too."""
    result: Dict[str, Any] = {"conditions": None, "false_positives": len(false_positives),
                              "detections_checked": len(others), "would_also_suppress": 0, "support": {}}
    if len(false_positives) < min_false_positives:
        result["reason"] = f"needs at least {min_false_positives} false positives"
        return result
    flats = [_flatten(e) for e in false_positives]
    counts: Counter = Counter(pair for flat in flats for pair in flat.items())
    conditions: Dict[str, str] = {}
    for (name, value), count in counts.most_common():
        support = count / len(flats)
        if support >= min_support and name not in conditions:
            conditions[name] = value
            result["support"][name] = round(support, 3)
    if not conditions:
        result["reason"] = "the false positives share no field value"
        return result
    result["conditions"] = dict(sorted(conditions.items()))
    result["would_also_suppress"] = sum(
        1 for e in others if all(_flatten(e).get(k, "").lower() == v.lower() for k, v in conditions.items()))
    return result
