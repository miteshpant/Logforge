"""
LogforgeQL -- a pipe-oriented text query language (ENH-028).

The only query interface was a JSON filter DSL, which is unusable for
interactive hunting. Analysts expect SPL / KQL / LogQL; requiring them to
hand-write JSON is a real barrier to adoption for experienced SOC teams.

Grammar
-------
    query    := selector? ("|" stage)*
    selector := free-text search terms
    stage    := where <expr>
              | stats <agg>(<field>) [by <field>, ...]
              | sort <field> [asc|desc]
              | limit <n>
              | last <duration>          (e.g. `last 15m`, `last 24h`, `last 7d`)
    expr     := comparison (("and"|"or") comparison)*
    comparison := field <op> value
    op       := = != > >= < <= =~ !~ contains startswith endswith in
    duration := <n>(s|m|h|d|w)

Examples
--------
    error timeout | where level = "error" | limit 100
    * | where service = "api" | stats count() by level
    | where service = "api" and http_status >= 500 | stats count() by service
    | where msg contains "panic" | sort ts desc | limit 50
    | last 15m | where level = "error"

SECURITY
--------
This compiles to an `AdvancedQueryRequest`, which is executed by the
parameterised builder from ENH-002. It **never** produces SQL text. That is the
whole point of targeting the request model: the language cannot become a new
injection surface, and it inherits the identifier allow-list for free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from query_engine import (
    AggregationType,
    QueryAggregation,
    QueryFilter,
    QueryOperator,
    SortOrder,
    validate_identifier,
)


class LogQLSyntaxError(ValueError):
    """Raised when a query cannot be parsed."""


# Text operator -> QueryOperator. `=~`/`!~` follow LogQL's regex spelling.
_OPERATORS: Dict[str, QueryOperator] = {
    "=": QueryOperator.EQ,
    "==": QueryOperator.EQ,
    "!=": QueryOperator.NE,
    ">": QueryOperator.GT,
    ">=": QueryOperator.GTE,
    "<": QueryOperator.LT,
    "<=": QueryOperator.LTE,
    "=~": QueryOperator.REGEX,
    "contains": QueryOperator.CONTAINS,
    "startswith": QueryOperator.STARTS_WITH,
    "endswith": QueryOperator.ENDS_WITH,
    "in": QueryOperator.IN,
    "not_in": QueryOperator.NOT_IN,
}

_AGGREGATIONS: Dict[str, AggregationType] = {
    "count": AggregationType.COUNT,
    "sum": AggregationType.SUM,
    "avg": AggregationType.AVG,
    "min": AggregationType.MIN,
    "max": AggregationType.MAX,
    "unique": AggregationType.UNIQUE,
    "cardinality": AggregationType.CARDINALITY,
}

# Longest-first so `>=` is matched before `>`.
_OPERATOR_PATTERN = "|".join(
    re.escape(op) for op in sorted(_OPERATORS, key=len, reverse=True)
    if not op.isalpha()
)
_WORD_OPERATORS = [op for op in _OPERATORS if op.isalpha()]

_COMPARISON_RE = re.compile(
    rf"""^\s*
        (?P<field>[A-Za-z_][A-Za-z0-9_.]*)\s*
        (?P<op>{_OPERATOR_PATTERN}|{"|".join(_WORD_OPERATORS)})\s*
        (?P<value>.+?)
    \s*$""",
    re.VERBOSE | re.IGNORECASE,
)

_STATS_RE = re.compile(
    r"^\s*(?P<func>[a-z]+)\s*\(\s*(?P<field>[A-Za-z_*][A-Za-z0-9_.]*)?\s*\)\s*$",
    re.IGNORECASE,
)

# `last <n><unit>` relative time window (LF-022).
_DURATION_RE = re.compile(r"^(?P<count>\d+)\s*(?P<unit>[smhdw])$", re.IGNORECASE)

_DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}

# Guard against absurd windows; the router applies its own max-window guard on
# top of this (LF-017/LF-022), so this only rejects the clearly unreasonable.
_MAX_LAST_SECONDS = 90 * 86400  # 90 days


@dataclass
class ParsedQuery:
    """The intermediate form produced by the parser."""

    text_search: Optional[str] = None
    filters: List[QueryFilter] = field(default_factory=list)
    aggregations: List[QueryAggregation] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    sort_field: Optional[str] = None
    sort_order: SortOrder = SortOrder.DESC
    limit: Optional[int] = None
    last_seconds: Optional[int] = None


def _parse_value(raw: str) -> Any:
    """
    Convert a literal to a Python value.

    Quoted strings stay strings; bare numbers become numbers; bracketed lists
    become lists (for `in`). Values are BOUND downstream, so nothing here needs
    to escape anything -- and nothing here should try to.
    """
    text = raw.strip()

    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]

    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(part) for part in _split_top_level(inner, ",")]

    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass

    return text


def _split_top_level(text: str, delimiter: str) -> List[str]:
    """Split on a delimiter, ignoring occurrences inside quotes or brackets."""
    parts, current, depth = [], [], 0
    quote: Optional[str] = None

    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue

        if char in "\"'":
            quote = char
            current.append(char)
            continue

        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)

        if char == delimiter and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current))

    return [p.strip() for p in parts if p.strip()]


def _split_conditions(expression: str) -> List[Tuple[str, str]]:
    """
    Split a `where` expression into (joiner, condition) pairs.

    Splitting is QUOTE-AWARE: `service = "a or b"` is one condition, not two.
    A naive regex split treats the `or` inside the string literal as an
    operator, which would reject a perfectly valid query -- or worse, silently
    change its meaning.

    Only `and` is supported between conditions, because the underlying request
    model ANDs its filters. `or` is rejected explicitly rather than silently
    mis-evaluated: returning wrong results is worse than an error message.
    """
    conditions: List[Tuple[str, str]] = []
    current: List[str] = []
    joiner = "and"
    quote: Optional[str] = None
    index = 0

    while index < len(expression):
        char = expression[index]

        if quote:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue

        if char in "\"'":
            quote = char
            current.append(char)
            index += 1
            continue

        # Only match a keyword at a word boundary, outside quotes.
        remainder = expression[index:]
        match = re.match(r"\s+(and|or)\s+", remainder, re.IGNORECASE)
        if match:
            conditions.append((joiner, "".join(current).strip()))
            joiner = match.group(1).lower()
            current = []
            index += match.end()
            continue

        current.append(char)
        index += 1

    if current:
        conditions.append((joiner, "".join(current).strip()))

    return [(j, c) for j, c in conditions if c]


def _parse_comparison(condition: str) -> QueryFilter:
    match = _COMPARISON_RE.match(condition)
    if not match:
        raise LogQLSyntaxError(
            f"Cannot parse condition: {condition!r}. "
            "Expected `field <operator> value`."
        )

    field_name = match.group("field")
    operator_text = match.group("op").lower()
    value = _parse_value(match.group("value"))

    operator = _OPERATORS.get(operator_text)
    if operator is None:
        raise LogQLSyntaxError(f"Unknown operator: {operator_text!r}")

    if operator == QueryOperator.IN and not isinstance(value, list):
        value = [value]

    # Validate the identifier here so the error names the offending field,
    # rather than surfacing later from the SQL builder.
    if not field_name.startswith(("attrs.", "raw_data.")):
        validate_identifier(field_name)

    return QueryFilter(field=field_name, operator=operator, value=value)


def _parse_stats(stage: str, parsed: ParsedQuery) -> None:
    """Parse `stats count() by service, level`."""
    body = stage[len("stats"):].strip()
    if not body:
        raise LogQLSyntaxError("`stats` requires an aggregation, e.g. `stats count()`")

    group_by: List[str] = []
    by_match = re.search(r"\s+by\s+", body, re.IGNORECASE)
    if by_match:
        # `re.split` with a capture-free pattern returns 2 parts, not 3 --
        # unpacking three names raised "not enough values to unpack".
        by_clause = body[by_match.end():]
        body = body[: by_match.start()]
        group_by = [
            validate_identifier(f) for f in _split_top_level(by_clause, ",")
        ]

    for expression in _split_top_level(body, ","):
        match = _STATS_RE.match(expression)
        if not match:
            raise LogQLSyntaxError(
                f"Cannot parse aggregation: {expression!r}. Expected e.g. `count()`."
            )

        func = match.group("func").lower()
        agg_field = match.group("field") or "*"

        aggregation = _AGGREGATIONS.get(func)
        if aggregation is None:
            raise LogQLSyntaxError(
                f"Unknown aggregation {func!r}. "
                f"Supported: {', '.join(sorted(_AGGREGATIONS))}"
            )

        if agg_field != "*" and not agg_field.startswith("attrs."):
            validate_identifier(agg_field)

        parsed.aggregations.append(
            QueryAggregation(type=aggregation, field=agg_field)
        )

    parsed.group_by = group_by


def parse(query: str) -> ParsedQuery:
    """
    Parse a LogforgeQL query.

    Raises:
        LogQLSyntaxError: with a message naming the offending stage. Query
        errors are user errors and must be explained, not swallowed.
    """
    if query is None:
        raise LogQLSyntaxError("Query is empty")

    stages = _split_top_level(query, "|")
    if not stages:
        raise LogQLSyntaxError("Query is empty")

    parsed = ParsedQuery()

    # A leading stage without a keyword is free-text search.
    #
    # A stage that merely LOOKS like a keyword must not be accepted as one:
    # `| frobnicate service` in leading position was silently swallowed as free
    # text, so a typo'd stage name returned unfiltered results instead of an
    # error. Only the first stage may be free text, and only when it does not
    # begin with a recognised stage keyword.
    first = stages[0].strip()
    keywords = ("where", "stats", "sort", "limit", "last")
    first_word = first.split()[0].lower() if first else ""

    if first == "*":
        # `*` is the conventional match-all selector (SPL/KQL); it was searched
        # for literally, so `* | where ...` silently returned nothing.
        stages = stages[1:]
    elif first and first_word not in keywords:
        parsed.text_search = first
        stages = stages[1:]
    elif not first:
        stages = stages[1:]

    for stage in stages:
        stage = stage.strip()
        if not stage:
            continue

        lowered = stage.lower()

        if lowered.startswith("where"):
            expression = stage[len("where"):].strip()
            if not expression:
                raise LogQLSyntaxError("`where` requires a condition")

            for joiner, condition in _split_conditions(expression):
                if joiner == "or":
                    raise LogQLSyntaxError(
                        "`or` is not supported between conditions yet. "
                        "Use a regex (`field =~ \"a|b\"`) or `in [a, b]`."
                    )
                parsed.filters.append(_parse_comparison(condition))

        elif lowered.startswith("stats"):
            _parse_stats(stage, parsed)

        elif lowered.startswith("sort"):
            body = stage[len("sort"):].strip()
            if not body:
                raise LogQLSyntaxError("`sort` requires a field")
            parts = body.split()
            parsed.sort_field = validate_identifier(parts[0])
            if len(parts) > 1:
                direction = parts[1].lower()
                if direction not in ("asc", "desc"):
                    raise LogQLSyntaxError(
                        f"Sort direction must be asc or desc, got {parts[1]!r}"
                    )
                parsed.sort_order = (
                    SortOrder.ASC if direction == "asc" else SortOrder.DESC
                )

        elif lowered.startswith("limit"):
            body = stage[len("limit"):].strip()
            try:
                parsed.limit = int(body)
            except ValueError:
                raise LogQLSyntaxError(f"`limit` requires an integer, got {body!r}")
            if parsed.limit <= 0:
                raise LogQLSyntaxError("`limit` must be positive")

        elif lowered.startswith("last"):
            body = stage[len("last"):].strip()
            match = _DURATION_RE.match(body)
            if not match:
                raise LogQLSyntaxError(
                    f"`last` requires a duration like `15m`, `24h` or `7d`, "
                    f"got {body!r}. Units: s, m, h, d, w."
                )
            seconds = int(match.group("count")) * _DURATION_SECONDS[
                match.group("unit").lower()
            ]
            if seconds <= 0:
                raise LogQLSyntaxError("`last` duration must be positive")
            if seconds > _MAX_LAST_SECONDS:
                raise LogQLSyntaxError(
                    "`last` window is too wide (maximum 90d). "
                    "Narrow the range to keep the scan bounded."
                )
            parsed.last_seconds = seconds

        else:
            raise LogQLSyntaxError(
                f"Unknown stage: {stage.split()[0]!r}. "
                f"Supported: {', '.join(keywords)}"
            )

    return parsed


def compile_to_request_payload(query: str) -> Dict[str, Any]:
    """
    Compile a query into a payload for `routers.query.build_query_request()`.

    Returning a payload (rather than an `AdvancedQueryRequest`) keeps the
    tenant-isolation filter as the router's responsibility: the language cannot
    accidentally construct a request that skips it.
    """
    parsed = parse(query)

    payload: Dict[str, Any] = {
        "filters": [
            {"field": f.field, "operator": f.operator.value, "value": f.value}
            for f in parsed.filters
        ]
    }

    if parsed.text_search:
        payload["text_search"] = parsed.text_search

    if parsed.aggregations:
        payload["aggregations"] = [
            {"type": a.type.value, "field": a.field} for a in parsed.aggregations
        ]

    if parsed.group_by:
        payload["group_by"] = parsed.group_by

    if parsed.sort_field:
        payload["sort_field"] = parsed.sort_field

    payload["sort_order"] = parsed.sort_order.value

    if parsed.limit is not None:
        payload["limit"] = parsed.limit

    if parsed.last_seconds is not None:
        # Resolve the relative window at compile time. The router only
        # overwrites these when the request body carries an explicit range, so
        # `| last 15m` works even for callers that send no range at all.
        end_time = datetime.now(timezone.utc)
        payload["start_time"] = (
            end_time - timedelta(seconds=parsed.last_seconds)
        ).isoformat()
        payload["end_time"] = end_time.isoformat()

    return payload
