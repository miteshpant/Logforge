"""
Sigma detection -> ClickHouse prefilter for backtesting (Phase 1).

`compile_prefilter(detection)` returns a WHERE clause over `logs_raw_mt`
selecting a SUPERSET of the events the engine would match, plus its
parameters (%(pN)s placeholders; values are never inlined). The backtest
replays the selected events through the engine, so the SQL never decides a
match by itself; it only keeps the scan small.

Anything the SQL can't express exactly is widened, never narrowed:

* `not ...` becomes "no restriction" (dropping a negation only widens);
* regexes (Python and ClickHouse's RE2 differ), unknown modifiers and null
  values are unrestricted, and so is comparing `event_type` with a value the
  normalizer can guess from the message (login_failed, ...), which the stored
  row doesn't carry;
* if nothing restricts the rule, the result is (None, {}): scan the range.

Field lookup mirrors the engine and ingestion: a model column when it is
non-empty, otherwise the caller's value in the `attrs` JSON. Strings compare
case-insensitively with lowerUTF8, like the engine's str.lower.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any, Dict, List, Optional, Tuple

from sigma_condition import (And, Identifier, Not, Or, Quantifier, SigmaConditionError, parse_condition,
                             split_aggregation)

#: Rule field -> logs_raw_mt column (aliases as the ingestion normalizer
#: exposes them to rules).
COLUMNS = {
    "host": "host", "hostname": "host",
    "msg": "msg", "message": "msg",
    "service": "service",
    "level": "level", "log_level": "level",
    "src_ip": "src_ip",
    "user_id": "user_id",
    "trace_id": "trace_id",
    "span_id": "span_id",
    "status": "status", "status_code": "status",
}
NUMERIC_COLUMNS = {"status"}


def _guessable_event_types() -> set:
    """event_type values the ingestion normalizer derives from the message
    (config/field_mapping.yml event_type_patterns)."""
    try:
        from field_mapper import field_mapper

        return {str(k).lower() for k in field_mapper.value_mappings.get("event_type_patterns", {})}
    except Exception:
        return {"login_failed", "login_success", "process_creation", "file_creation", "network_connection"}


#: field -> values the normalizer may fill in, which the stored row lacks.
DERIVED_VALUES = {"event_type": _guessable_event_types()}

_FIELD_NAME = re.compile(r"^[A-Za-z0-9_@\-]+(\.[A-Za-z0-9_@\-]+)*$")
_NUMERIC_COMPARISON = re.compile(r"^\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_COMPARATORS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


class _Unrestricted(Exception):
    """This part can't narrow the scan."""


def _attr_expression(path: List[str]) -> str:
    keys = ", ".join(f"'{p}'" for p in path)
    return (f"if(JSONType(attrs, {keys}) = 'String', JSONExtractString(attrs, {keys}), "
            f"JSONExtractRaw(attrs, {keys}))")


def field_expression(field: str) -> str:
    """SQL for a rule field's value as a string ('' when absent)."""
    if not _FIELD_NAME.match(field):
        raise ValueError(f"unsupported field name {field!r}")
    parts = field.split(".")
    if parts[0] == "attrs" and len(parts) > 1:
        return _attr_expression(parts[1:])
    if len(parts) > 1:
        raise ValueError(f"nested field {field!r} outside attrs")
    column = COLUMNS.get(field)
    attr = _attr_expression([field])
    if column is None:
        return attr
    if column in NUMERIC_COLUMNS:
        return f"if({column} != 0, toString({column}), {attr})"
    return f"if({column} != '', toString({column}), {attr})"


class _Compiler:
    def __init__(self, start: int):
        self.params: Dict[str, Any] = {}
        self.counter = start

    def param(self, value: Any) -> str:
        name = f"p{self.counter}"
        self.counter += 1
        self.params[name] = value
        return f"%({name})s"

    # -- values ----------------------------------------------------------
    def value_clause(self, expr: str, operator: str, value: Any) -> str:
        if value is None or isinstance(value, (dict, list)):
            raise _Unrestricted
        if operator in ("eq", ""):
            match = _NUMERIC_COMPARISON.match(str(value))
            if match:
                return f"toFloat64OrNull({expr}) {match.group(1)} {self.param(float(match.group(2)))}"
            return f"lowerUTF8({expr}) = lowerUTF8({self.param(str(value))})"
        if operator == "contains":
            return f"positionCaseInsensitiveUTF8({expr}, {self.param(str(value))}) > 0"
        if operator == "startswith":
            return f"startsWith(lowerUTF8({expr}), lowerUTF8({self.param(str(value))}))"
        if operator == "endswith":
            return f"endsWith(lowerUTF8({expr}), lowerUTF8({self.param(str(value))}))"
        if operator in _COMPARATORS:
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise _Unrestricted
            return f"toFloat64OrNull({expr}) {_COMPARATORS[operator]} {self.param(number)}"
        raise _Unrestricted  # re/regex and anything unknown

    def field_clause(self, key: str, value: Any) -> Optional[str]:
        field, *modifiers = key.split("|")
        require_all = "all" in modifiers
        modifiers = [m for m in modifiers if m != "all"]
        if len(modifiers) > 1:
            return None
        operator = modifiers[0] if modifiers else "eq"
        try:
            expr = field_expression(field)
        except ValueError:
            return None
        values = value if isinstance(value, list) else [value]
        if not values:
            return None
        derived = DERIVED_VALUES.get(field, set())
        clauses = []
        for item in values:
            try:
                if str(item).lower() in derived:
                    raise _Unrestricted
                clauses.append(self.value_clause(expr, operator, item))
            except _Unrestricted:
                if not require_all:
                    return None  # one unrestricted alternative -> the OR is unrestricted
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return "(" + (" AND " if require_all else " OR ").join(clauses) + ")"

    def block(self, block: Any) -> Optional[str]:
        if not isinstance(block, dict) or not block:
            return None
        clauses = [c for c in (self.field_clause(k, v) for k, v in block.items()) if c]
        return "(" + " AND ".join(clauses) + ")" if clauses else None

    # -- condition -------------------------------------------------------
    def node(self, node: Any, blocks: Dict[str, Any]) -> Optional[str]:
        if isinstance(node, Identifier):
            return self.block(blocks.get(node.name))
        if isinstance(node, Not):
            return None
        if isinstance(node, And):
            left, right = self.node(node.left, blocks), self.node(node.right, blocks)
            if left and right:
                return f"({left} AND {right})"
            return left or right
        if isinstance(node, Or):
            left = self.node(node.left, blocks)
            if left is None:
                return None
            right = self.node(node.right, blocks)
            return f"({left} OR {right})" if right else None
        if isinstance(node, Quantifier):
            names = list(blocks) if node.pattern == "them" else [
                n for n in blocks if fnmatch.fnmatchcase(n, node.pattern)]
            parts = [self.node(Identifier(n), blocks) for n in names]
            if not parts:
                return None
            if node.mode == "all":
                kept = [p for p in parts if p]
                return "(" + " AND ".join(kept) + ")" if kept else None
            if any(p is None for p in parts):
                return None
            return "(" + " OR ".join(parts) + ")"
        return None


def compile_prefilter(detection: Dict[str, Any], start: int = 0) -> Tuple[Optional[str], Dict[str, Any]]:
    """(WHERE clause or None, params) selecting a superset of the events the
    detection matches. `start` offsets parameter names, to combine rules."""
    if not isinstance(detection, dict):
        return None, {}
    condition = detection.get("condition", "selection")
    if not isinstance(condition, str):
        return None, {}
    head, aggregation = split_aggregation(condition)
    if aggregation is None:
        count = re.match(r"\s*count\s*\(\s*([A-Za-z0-9_]*)\s*\)", condition)
        if count:
            head = count.group(1) or "selection"
    blocks = {k: v for k, v in detection.items() if k != "condition" and isinstance(v, dict)}
    try:
        tree = parse_condition(head)
    except SigmaConditionError:
        return None, {}
    compiler = _Compiler(start)
    sql = compiler.node(tree, blocks)
    if not sql:
        return None, {}
    used = {k: v for k, v in compiler.params.items() if f"%({k})s" in sql}
    return sql, used
