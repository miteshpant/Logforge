"""
LogforgeQL pipeline commands (Phase 6): analytics, not just search.

    error | where status >= 500 or level = "fatal"
          | eval slow = if(attrs.duration_ms > 1000, "slow", "ok")
          | stats count() as n, p95(attrs.duration_ms) as p95 by service, slow
          | sort -n | head 10

The original LogforgeQL (logql.py) compiles to an AdvancedQueryRequest: one
filter list, one GROUP BY. That cannot express a pipeline, where each stage
works on the output of the one before (`stats ... | where n > 3 | stats ...`).
This module compiles such queries to ONE parameterised ClickHouse statement
in which every stage wraps the previous stage as a subquery.

Commands: where, eval, stats, eventstats, timechart, top, rare, sort, head
(limit), dedup, fields (table), rename, bin, rex, parse, json, last. Queries
the original language accepts keep using it (uses_pipeline()), so their
behaviour does not change.

SECURITY
--------
* The tenant and the time window are applied in the innermost SELECT, on the
  table itself; no stage can remove them (every later stage only reads the
  subquery).
* Every string a user types, and every variable value, is a bound parameter.
  Numbers are rendered from their parsed Python value.
* Field names resolve through the query engine's allow-list (columns, derived
  fields, attrs.<path>, ocsf.<path>) or through names a stage defined. Names
  a user introduces must be plain identifiers; generated names are checked
  against a fixed character set before they are quoted.
* Functions come from a fixed table; there is no way to name a ClickHouse
  function directly.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

import logql
from logql import LogQLSyntaxError
from query_engine import (
    DERIVED_FIELD_SQL,
    NUMERIC_FIELDS,
    QueryFieldError,
    complex_field_sql,
    is_complex_field,
    validate_field,
)


class PipelineError(LogQLSyntaxError):
    """A query that cannot be compiled. The message is shown to the user."""


MAX_ROWS = 10_000          # rows a query may return
DEFAULT_EVENT_ROWS = 100   # events returned when the query has no head
MAX_SERIES = 100           # timechart limit=
MAX_VALUES = 100           # values() / list() items per group
MAX_JOIN_ROWS = 50_000     # rows a join subsearch may return
DEFAULT_JOIN_ROWS = 10_000
MAX_JOIN_DEPTH = 2

# Column types the compiler tracks, so it can convert where ClickHouse needs it
# (attrs and ocsf values are text; comparing text with a number is an error).
NUM, STR, BOOL, TIME, NULL, LIST = "num", "str", "bool", "time", "null", "list"
ALL_TYPE = "all"


class _All:
    """A dashboard variable set to All: comparisons with it are true."""

    def __repr__(self) -> str:
        return "ALL"


ALL = _All()

LOG_COLUMNS = ("ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
               "user_id", "ingested_at", "severity_num", "facility", "parser_version", "customer_id")
EVENT_OUTPUT = ("ts", "host", "service", "level", "msg", "trace_id", "span_id", "attrs", "status", "src_ip",
                "user_id")
_TIME_COLUMNS = {"ts", "ingested_at", "date", "hour"}

STAGES = ("where", "eval", "stats", "eventstats", "timechart", "top", "rare", "sort", "head", "limit", "dedup",
          "fields", "table", "rename", "bin", "rex", "parse", "json", "lookup", "join", "last")

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*$")
_GENERATED_NAME_RE = re.compile(r"^[A-Za-z0-9_.()*]{1,128}$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SPAN_RE = re.compile(r"^(\d+)(s|m|h|d|w)$")
_UNITS = {"s": ("second", 1), "m": ("minute", 60), "h": ("hour", 3600), "d": ("day", 86400),
          "w": ("week", 604800)}
_AUTO_SPANS = ["1s", "5s", "10s", "30s", "1m", "5m", "10m", "15m", "30m", "1h", "3h", "6h", "12h", "1d", "7d"]
_OPTION_RE = re.compile(r"^\s*([a-z]+)\s*=\s*([^\s,]+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

@dataclass
class Tok:
    kind: str  # num, str, ident, var, op, end
    value: Any
    pos: int

    def is_kw(self, *words: str) -> bool:
        return self.kind == "ident" and str(self.value).lower() in words


_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![A-Za-z_]))
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')
  | (?P<var>\$[A-Za-z_][A-Za-z0-9_]*)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)
  | (?P<op>>=|<=|!=|==|=~|!~|[=<>+\-*/%(),\[\]])
""", re.VERBOSE)


def tokenize(text: str) -> List[Tok]:
    tokens, pos = [], 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if not match:
            raise PipelineError(f"Unexpected character {text[pos]!r} at position {pos + 1}: "
                                f"...{text[max(0, pos - 15):pos + 15]}...")
        kind = match.lastgroup
        raw = match.group()
        if kind == "num":
            tokens.append(Tok("num", float(raw) if any(c in raw for c in ".eE") else int(raw), pos))
        elif kind == "str":
            quote = raw[0]
            tokens.append(Tok("str", re.sub(r"\\([\\" + quote + r"])", r"\1", raw[1:-1]), pos))
        elif kind != "ws":
            tokens.append(Tok(kind, raw, pos))
        pos = match.end()
    tokens.append(Tok("end", None, len(text)))
    return tokens


# ---------------------------------------------------------------------------
# Compiled values and scopes
# ---------------------------------------------------------------------------

@dataclass
class Col:
    sql: str
    type: str
    literal: Any = None       # the Python value, for literals
    items: Optional[List["Col"]] = None  # for lists


def q(name: str) -> str:
    """Quote an output name. Only checked shapes ever get here."""
    if not (_FIELD_NAME_RE.match(name) or _GENERATED_NAME_RE.match(name)):
        raise PipelineError(f"{name!r} is not a valid name")
    return f"`{name}`"


@dataclass
class Scope:
    """What a stage can see: the SQL so far and the names it can use.

    `open` scopes are event scopes over the log table: every field the query
    engine knows resolves (lazily, as an expression over the raw columns),
    except names hidden by rename / fields -. Closed scopes (after stats,
    fields, ...) see exactly `cols`.
    """
    sql: str
    cols: Dict[str, Col]
    open: bool
    events: bool
    kind: str = "events"                  # events | table | timechart
    order: List[Tuple[str, str]] = field(default_factory=list)  # (sql, ASC|DESC)
    order_frozen: bool = False            # order applied inside, not re-applied
    real: set = field(default_factory=set)  # real output columns of `sql` (open scopes)
    hidden: set = field(default_factory=set)
    computed: List[str] = field(default_factory=list)
    limit: Optional[int] = None
    closed_by: str = ""


@dataclass
class CompiledQuery:
    sql: str
    params: Dict[str, Any]
    columns: List[str]
    result_type: str
    limit: int
    explicit_limit: bool


@dataclass
class LookupMeta:
    """What the compiler needs to know about a tenant's lookup table."""
    name: str
    version: int
    columns: List[str]
    key: str


class Compiler:
    def __init__(self, customer_id: str, start: datetime, end: datetime, table: str,
                 variables: Optional[Dict[str, Any]], max_rows: int,
                 lookups: Optional[Dict[str, "LookupMeta"]] = None, lookup_table: str = "lookup_rows_mt"):
        if not _TABLE_RE.match(table) or not _TABLE_RE.match(lookup_table):
            raise PipelineError("invalid table")
        self.customer_id, self.start, self.end, self.table = customer_id, start, end, table
        self.variables = variables or {}
        self.max_rows = max_rows
        self.params: Dict[str, Any] = {}
        self.lookups = lookups or {}
        self.lookup_table = lookup_table
        self.join_depth = 0

    def lookup(self, name: str) -> "LookupMeta":
        meta = self.lookups.get(name)
        if meta is None:
            known = ", ".join(sorted(self.lookups)) or "none uploaded"
            raise PipelineError(f"Unknown lookup: {name}. Lookups: {known}")
        return meta

    def lookup_rows(self, meta: "LookupMeta") -> str:
        """The current version's rows of a tenant's lookup, as a subquery."""
        return (f"SELECT key, values FROM {self.lookup_table} WHERE tenant_id = {self.bind(self.customer_id)} "
                f"AND lookup = {self.bind(meta.name)} AND version = {int(meta.version)}")

    # -- binding ------------------------------------------------------------
    def bind(self, value: Any) -> str:
        key = f"p{len(self.params)}"
        self.params[key] = value
        return f"%({key})s"

    def bind_hint(self, _hint: str, value: Any) -> str:
        return self.bind(value)

    def literal(self, value: Any) -> Col:
        if value is None:
            return Col("NULL", NULL)
        if isinstance(value, bool):
            return Col("1" if value else "0", BOOL, literal=value)
        if isinstance(value, int):
            return Col(str(int(value)), NUM, literal=value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise PipelineError("numbers must be finite")
            return Col(repr(float(value)), NUM, literal=value)
        if isinstance(value, str):
            return Col(self.bind(value), STR, literal=value)
        if isinstance(value, (list, tuple)):
            items = [self.literal(v) for v in value]
            if any(i.type == LIST for i in items):
                raise PipelineError("lists cannot be nested")
            return Col("", LIST, items=items)
        raise PipelineError(f"unsupported value type: {type(value).__name__}")

    # -- the base relation ----------------------------------------------------
    def base(self, text_search: Optional[str]) -> Scope:
        where = [f"customer_id = {self.bind(self.customer_id)}", f"ts >= {self.bind(self.start)}",
                 f"ts <= {self.bind(self.end)}"]
        if text_search:
            where.append(f"msg LIKE {self.bind('%' + like_escape(text_search) + '%')}")
        sql = f"SELECT * FROM {self.table} WHERE {' AND '.join(where)}"
        return Scope(sql=sql, cols={}, open=True, events=True, real=set(LOG_COLUMNS))

    # -- field resolution -----------------------------------------------------
    def resolve(self, scope: Scope, name: str) -> Col:
        if name in scope.cols:
            return scope.cols[name]
        if scope.open and name not in scope.hidden:
            return self.base_field(name)
        available = ", ".join(scope.cols) or "none"
        after = f" after `{scope.closed_by}`" if scope.closed_by else ""
        raise PipelineError(f"{name} is not available{after}. Available: {available}")

    def base_field(self, name: str) -> Col:
        try:
            if is_complex_field(name):
                return Col(f"({complex_field_sql(validate_field(name), self.bind_hint)})", STR)
            validate_field(name)
        except QueryFieldError as e:
            raise PipelineError(str(e)) from None
        if name in DERIVED_FIELD_SQL:
            kind = TIME if name in _TIME_COLUMNS else NUM if name in NUMERIC_FIELDS else STR
            return Col(f"({DERIVED_FIELD_SQL[name]})", kind)
        kind = TIME if name in _TIME_COLUMNS else NUM if name in NUMERIC_FIELDS else STR
        return Col(name, kind)

    def variable(self, name: str) -> Col:
        key = name[1:]
        if key not in self.variables:
            raise PipelineError(f"Unknown variable: ${key}")
        if self.variables[key] is ALL:
            return Col("1", ALL_TYPE, literal=name)
        return self.literal(self.variables[key])


def like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

def _not_all(col: Col) -> None:
    if col.type == ALL_TYPE:
        raise PipelineError(f"{col.literal} is All here; All can only be compared with = or in")


def to_num(col: Col) -> str:
    _not_all(col)
    if col.type in (NUM, BOOL, NULL):
        return col.sql
    if col.type == STR:
        return f"toFloat64OrNull({col.sql})"
    if col.type == TIME:
        raise PipelineError("Arithmetic on a time is not supported; use a function such as hour(ts)")
    raise PipelineError("A list cannot be used here")


def to_str(col: Col) -> str:
    _not_all(col)
    if col.type == STR:
        return col.sql
    if col.type == LIST:
        raise PipelineError("A list cannot be used here")
    return f"toString({col.sql})"


def nonempty(col: Col) -> str:
    _not_all(col)
    if col.type == STR:
        return f"(isNotNull({col.sql}) AND {col.sql} != '')"
    return f"isNotNull({col.sql})"


def unify(cols: List[Col]) -> Tuple[List[str], str]:
    kinds = {c.type for c in cols if c.type != NULL}
    if len(kinds) <= 1:
        return [c.sql for c in cols], (kinds.pop() if kinds else NULL)
    if kinds <= {NUM, BOOL}:
        return [c.sql for c in cols], NUM
    return [c.sql if c.type in (STR, NULL) else to_str(c) for c in cols], STR


def check_regex(pattern: Any, where: str) -> None:
    if not isinstance(pattern, str):
        raise PipelineError(f"{where}: the pattern must be a quoted string")
    for regex, message in logql._UNSUPPORTED_RE:
        if regex.search(pattern):
            raise PipelineError(f"{where}: {message}")
    try:
        re.compile(pattern)
    except re.error as e:
        raise PipelineError(f"{where}: invalid regular expression: {e}") from None


# ---------------------------------------------------------------------------
# Functions available in eval / where
# ---------------------------------------------------------------------------

def _arity(name: str, args: List[Col], low: int, high: Optional[int] = None) -> None:
    high = low if high is None else high
    if not low <= len(args) <= high:
        want = str(low) if low == high else f"{low} to {high}" if high < 99 else f"at least {low}"
        raise PipelineError(f"{name} takes {want} argument{'s' if want != '1' else ''}")


def _int_literal(col: Col, what: str) -> int:
    if col.type != NUM or not isinstance(col.literal, int):
        raise PipelineError(f"{what} must be a whole number")
    return int(col.literal)


def _fn_if(c, args):
    _arity("if", args, 3)
    (a, b), kind = unify(args[1:])
    return Col(f"if({args[0].sql}, {a}, {b})", kind)


def _fn_case(c, args):
    if len(args) < 2:
        raise PipelineError("case takes condition, value pairs and an optional default")
    pairs = args if len(args) % 2 == 0 else args[:-1]
    default = args[-1] if len(args) % 2 else Col("NULL", NULL)
    values, kind = unify([pairs[i] for i in range(1, len(pairs), 2)] + [default])
    parts = []
    for i in range(0, len(pairs), 2):
        parts += [pairs[i].sql, values[i // 2]]
    return Col(f"multiIf({', '.join(parts)}, {values[-1]})", kind)


def _fn_coalesce(c, args):
    _arity("coalesce", args, 1, 99)
    values, kind = unify(args)
    values = [f"nullIf({v}, '')" if kind == STR else v for v in values]
    return Col(f"coalesce({', '.join(values)})", kind)


def _round(c, args):
    _arity("round", args, 1, 2)
    digits = _int_literal(args[1], "round's digits") if len(args) == 2 else 0
    return Col(f"round({to_num(args[0])}, {digits})", NUM)


def _substr(c, args):
    _arity("substr", args, 2, 3)
    parts = [to_str(args[0]), f"toInt64({to_num(args[1])})"]
    if len(args) == 3:
        parts.append(f"toInt64({to_num(args[2])})")
    return Col(f"substringUTF8({', '.join(parts)})", STR)


def _match(c, args):
    _arity("match", args, 2)
    check_regex(args[1].literal, "match")
    return Col(f"match({to_str(args[0])}, {args[1].sql})", BOOL)


def _replace(c, args):
    _arity("replace", args, 3)
    check_regex(args[1].literal, "replace")
    return Col(f"replaceRegexpAll({to_str(args[0])}, {args[1].sql}, {to_str(args[2])})", STR)


def _like(c, args):
    _arity("like", args, 2)
    return Col(f"({to_str(args[0])} LIKE {to_str(args[1])})", BOOL)


def _cidrmatch(c, args):
    _arity("cidrmatch", args, 2)
    if not isinstance(args[0].literal, str) or not re.match(r"^[0-9A-Fa-f:.]+/\d{1,3}$", args[0].literal):
        raise PipelineError('cidrmatch needs a quoted CIDR first, e.g. cidrmatch("10.0.0.0/8", src_ip)')
    ip = to_str(args[1])
    return Col(f"(isIPv4String({ip}) OR isIPv6String({ip})) AND isIPAddressInRange({ip}, {args[0].sql})", BOOL)


def _json_extract(c, args):
    _arity("json_extract", args, 2)
    if not isinstance(args[1].literal, str) or not args[1].literal:
        raise PipelineError('json_extract needs a quoted path, e.g. json_extract(msg, "user.name")')
    keys = ", ".join(c.bind(k) for k in args[1].literal.split(".") if k)
    return Col(f"JSONExtractString({to_str(args[0])}, {keys})", STR)


def _strftime(c, args):
    _arity("strftime", args, 2)
    if args[0].type != TIME or not isinstance(args[1].literal, str):
        raise PipelineError('strftime needs a time and a quoted format, e.g. strftime(ts, "%Y-%m-%d")')
    return Col(f"formatDateTime({args[0].sql}, {args[1].sql})", STR)


def _time_fn(sql_name: str, kind: str = NUM):
    def fn(c, args, _name=sql_name):
        _arity(_name, args, 1)
        if args[0].type != TIME:
            raise PipelineError("this function needs a time, such as ts")
        return Col(f"{_name}({args[0].sql})", kind)
    return fn


def _num_fn(sql_name: str, n: int = 1):
    def fn(c, args, _name=sql_name, _n=n):
        _arity(_name, args, _n)
        return Col(f"{_name}({', '.join(to_num(a) for a in args)})", NUM)
    return fn


def _str_fn(sql_name: str, kind: str = STR):
    def fn(c, args, _name=sql_name, _kind=kind):
        _arity(_name, args, 1)
        return Col(f"{_name}({to_str(args[0])})", _kind)
    return fn


def _inlookup(c, args):
    _arity("inlookup", args, 2)
    if not isinstance(args[0].literal, str):
        raise PipelineError('inlookup needs a quoted lookup name first, e.g. inlookup("blocklist", src_ip)')
    meta = c.lookup(args[0].literal)
    rows = c.lookup_rows(meta).replace("SELECT key, values", "SELECT key", 1)
    return Col(f"({to_str(args[1])} IN ({rows}))", BOOL)


FUNCTIONS: Dict[str, Callable[[Compiler, List[Col]], Col]] = {
    "inlookup": _inlookup,
    "if": _fn_if,
    "case": _fn_case,
    "coalesce": _fn_coalesce,
    "isnull": lambda c, a: (_arity("isnull", a, 1), Col(f"NOT {nonempty(a[0])}", BOOL))[1],
    "isnotnull": lambda c, a: (_arity("isnotnull", a, 1), Col(nonempty(a[0]), BOOL))[1],
    "lower": _str_fn("lowerUTF8"),
    "upper": _str_fn("upperUTF8"),
    "trim": _str_fn("trimBoth"),
    "len": _str_fn("lengthUTF8", NUM),
    "substr": _substr,
    "replace": _replace,
    "match": _match,
    "like": _like,
    "concat": lambda c, a: (_arity("concat", a, 1, 99),
                            Col(f"concat({', '.join(f'ifNull({to_str(x)}, {chr(39)}{chr(39)})' for x in a)})",
                                STR))[1],
    "tonumber": lambda c, a: (_arity("tonumber", a, 1), Col(f"toFloat64OrNull({to_str(a[0])})", NUM))[1],
    "tostring": lambda c, a: (_arity("tostring", a, 1), Col(to_str(a[0]), STR))[1],
    "round": _round,
    "floor": _num_fn("floor"),
    "ceil": _num_fn("ceil"),
    "abs": _num_fn("abs"),
    "sqrt": _num_fn("sqrt"),
    "ln": _num_fn("log"),
    "log10": _num_fn("log10"),
    "exp": _num_fn("exp"),
    "pow": _num_fn("pow", 2),
    "least": _num_fn("least", 2),
    "greatest": _num_fn("greatest", 2),
    "now": lambda c, a: (_arity("now", a, 0), Col("now64(3)", TIME))[1],
    "hour": _time_fn("toHour"),
    "minute": _time_fn("toMinute"),
    "dayofweek": _time_fn("toDayOfWeek"),
    "date": _time_fn("toDate", TIME),
    "strftime": _strftime,
    "cidrmatch": _cidrmatch,
    "json_extract": _json_extract,
}


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

_COMPARE_OPS = {"=": "=", "==": "=", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}


class Parser:
    """Recursive descent over tokens; compiles while it parses."""

    def __init__(self, compiler: Compiler, scope: Scope, tokens: List[Tok], stage: str):
        self.c, self.scope, self.toks, self.i, self.stage = compiler, scope, tokens, 0, stage

    # -- token helpers --------------------------------------------------------
    def peek(self, ahead: int = 0) -> Tok:
        return self.toks[min(self.i + ahead, len(self.toks) - 1)]

    def next(self) -> Tok:
        tok = self.peek()
        self.i += 1
        return tok

    def at_op(self, *ops: str) -> bool:
        tok = self.peek()
        return tok.kind == "op" and tok.value in ops

    def expect_op(self, op: str) -> None:
        tok = self.next()
        if tok.kind != "op" or tok.value != op:
            self.fail(tok, f"expected {op!r}")

    def done(self) -> bool:
        return self.peek().kind == "end"

    def fail(self, tok: Tok, what: str):
        if tok.kind == "end":
            raise PipelineError(f"`{self.stage}`: unexpected end of the expression ({what})")
        raise PipelineError(f"`{self.stage}`: {what}, got {tok.value!r} at position {tok.pos + 1}")

    def name(self, what: str = "a name") -> str:
        tok = self.next()
        if tok.kind != "ident":
            self.fail(tok, f"expected {what}")
        return tok.value

    # -- grammar ----------------------------------------------------------------
    def expr(self) -> Col:
        return self.or_()

    def or_(self) -> Col:
        left = self.and_()
        while self.peek().is_kw("or"):
            self.next()
            right = self.and_()
            left = Col(f"({left.sql} OR {right.sql})", BOOL)
        return left

    def and_(self) -> Col:
        left = self.not_()
        while self.peek().is_kw("and"):
            self.next()
            right = self.not_()
            left = Col(f"({left.sql} AND {right.sql})", BOOL)
        return left

    def not_(self) -> Col:
        if self.peek().is_kw("not"):
            self.next()
            inner = self.not_()
            return Col(f"(NOT {inner.sql})", BOOL)
        return self.comparison()

    def comparison(self) -> Col:
        left = self.additive()
        tok = self.peek()
        if tok.kind == "op" and tok.value in _COMPARE_OPS:
            self.next()
            return compare(left, _COMPARE_OPS[tok.value], self.additive())
        if tok.kind == "op" and tok.value in ("=~", "!~"):
            self.next()
            pattern = self.additive()
            check_regex(pattern.literal, f"`{tok.value}`")
            sql = f"match({to_str(left)}, {pattern.sql})"
            return Col(sql if tok.value == "=~" else f"(NOT {sql})", BOOL)
        negate = False
        if tok.is_kw("not") and self.peek(1).is_kw("in", "contains", "startswith", "endswith", "like"):
            self.next()
            negate, tok = True, self.peek()
        if tok.is_kw("in"):
            self.next()
            result = self.membership(left, self.additive())
        elif tok.is_kw("contains", "startswith", "endswith", "like"):
            self.next()
            result = self.text_match(left, tok.value.lower(), self.additive())
        elif tok.is_kw("is"):
            self.next()
            negate_null = False
            if self.peek().is_kw("not"):
                self.next()
                negate_null = True
            if not self.next().is_kw("null"):
                self.fail(self.toks[self.i - 1], "expected null after is")
            return Col(nonempty(left) if negate_null else f"(NOT {nonempty(left)})", BOOL)
        else:
            if negate:
                self.fail(tok, "expected in, contains, startswith, endswith or like after not")
            return left
        return Col(f"(NOT {result.sql})", BOOL) if negate else result

    def membership(self, left: Col, values: Col) -> Col:
        if values.type == ALL_TYPE:
            return Col("1", BOOL)
        items = values.items if values.type == LIST else [values]
        if not items:
            return Col("0", BOOL)
        if left.type == STR and all(i.type == NUM for i in items):
            lhs, rendered = to_num(left), [i.sql for i in items]
        elif left.type == NUM and any(i.type == STR for i in items):
            lhs, rendered = left.sql, [to_num(i) for i in items]
        else:
            lhs, rendered = left.sql, [i.sql for i in items]
        return Col(f"({lhs} IN ({', '.join(rendered)}))", BOOL)

    def text_match(self, left: Col, how: str, right: Col) -> Col:
        subject = to_str(left)
        if how == "like":
            return Col(f"({subject} LIKE {to_str(right)})", BOOL)
        if isinstance(right.literal, str):
            text = like_escape(right.literal)
            pattern = {"contains": f"%{text}%", "startswith": f"{text}%", "endswith": f"%{text}"}[how]
            return Col(f"({subject} LIKE {self.c.bind(pattern)})", BOOL)
        func = {"contains": "position({0}, {1}) > 0", "startswith": "startsWith({0}, {1})",
                "endswith": "endsWith({0}, {1})"}[how]
        return Col(f"({func.format(subject, to_str(right))})", BOOL)

    def additive(self) -> Col:
        left = self.multiplicative()
        while self.at_op("+", "-"):
            op = self.next().value
            right = self.multiplicative()
            left = Col(f"({to_num(left)} {op} {to_num(right)})", NUM)
        return left

    def multiplicative(self) -> Col:
        left = self.unary()
        while self.at_op("*", "/", "%"):
            op = self.next().value
            right = self.unary()
            if op == "%":
                left = Col(f"modulo({to_num(left)}, {to_num(right)})", NUM)
            else:
                left = Col(f"({to_num(left)} {op} {to_num(right)})", NUM)
        return left

    def unary(self) -> Col:
        if self.at_op("-"):
            self.next()
            inner = self.unary()
            if inner.type == NUM and isinstance(inner.literal, (int, float)):
                return self.c.literal(-inner.literal)
            return Col(f"(-{to_num(inner)})", NUM)
        return self.primary()

    def primary(self) -> Col:
        tok = self.next()
        if tok.kind == "num":
            return self.c.literal(tok.value)
        if tok.kind == "str":
            return self.c.literal(tok.value)
        if tok.kind == "var":
            return self.c.variable(tok.value)
        if tok.kind == "op" and tok.value == "(":
            inner = self.expr()
            self.expect_op(")")
            return inner
        if tok.kind == "op" and tok.value == "[":
            items = []
            while not self.at_op("]"):
                item = self.unary()
                if item.literal is None and item.type != NULL:
                    self.fail(tok, "list items must be values")
                items.append(item)
                if not self.at_op("]"):
                    self.expect_op(",")
            self.next()
            return Col("", LIST, items=items)
        if tok.kind == "ident":
            word = tok.value.lower()
            if word in ("true", "false"):
                return self.c.literal(word == "true")
            if word == "null":
                return Col("NULL", NULL)
            if self.at_op("("):
                return self.call(tok)
            return self.c.resolve(self.scope, tok.value)
        self.fail(tok, "expected a value, a field or a function")

    def call(self, tok: Tok) -> Col:
        name = tok.value.lower()
        func = FUNCTIONS.get(name)
        if func is None:
            raise PipelineError(f"Unknown function: {tok.value}. Available: {', '.join(sorted(FUNCTIONS))}")
        self.expect_op("(")
        args: List[Col] = []
        while not self.at_op(")"):
            args.append(self.expr())
            if not self.at_op(")"):
                self.expect_op(",")
        self.next()
        return func(self.c, args)


def compare(left: Col, op: str, right: Col) -> Col:
    if ALL_TYPE in (left.type, right.type):
        if op not in ("=", "!="):
            _not_all(left if left.type == ALL_TYPE else right)
        return Col("1" if op == "=" else "0", BOOL)
    if right.type == NULL or left.type == NULL:
        other = left if right.type == NULL else right
        if op not in ("=", "!="):
            raise PipelineError("null can only be compared with = or !=; use isnull()")
        return Col(f"(NOT {nonempty(other)})" if op == "=" else nonempty(other), BOOL)
    kinds = {left.type, right.type}
    if LIST in kinds:
        raise PipelineError("Use `in` to compare with a list")
    if TIME in kinds and STR in kinds:
        text = right if right.type == STR else left
        parsed = f"parseDateTime64BestEffortOrNull({text.sql}, 3, 'UTC')"
        lhs, rhs = (left.sql, parsed) if right is text else (parsed, right.sql)
    elif TIME in kinds and kinds & {NUM, BOOL}:
        raise PipelineError("A time can only be compared with a time or a quoted date")
    elif STR in kinds and kinds & {NUM, BOOL}:
        lhs, rhs = to_num(left), to_num(right)
    else:
        lhs, rhs = left.sql, right.sql
    return Col(f"({lhs} {op} {rhs})", BOOL)


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def _options(body: str, allowed: Tuple[str, ...], stage: str) -> Tuple[Dict[str, str], str]:
    options = {}
    while True:
        match = _OPTION_RE.match(body)
        if not match or match.group(1).lower() not in allowed:
            if match and match.group(1).lower() not in allowed and "=" in body.split()[0]:
                raise PipelineError(f"`{stage}`: unknown option {match.group(1)!r}; options: {', '.join(allowed)}")
            return options, body
        options[match.group(1).lower()] = match.group(2)
        body = body[match.end():]


def _span(text: str, stage: str) -> Tuple[str, int]:
    match = _SPAN_RE.match(text or "")
    if not match or int(match.group(1)) <= 0 or int(match.group(1)) > 100_000:
        raise PipelineError(f"`{stage}`: span must look like 30s, 5m, 1h, 1d or 1w, got {text!r}")
    unit, seconds = _UNITS[match.group(2)]
    return f"INTERVAL {int(match.group(1))} {unit}", int(match.group(1)) * seconds


def _positive(text: str, what: str, maximum: int) -> int:
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise PipelineError(f"{what} must be a whole number, got {text!r}") from None
    if value <= 0:
        raise PipelineError(f"{what} must be positive")
    if value > maximum:
        raise PipelineError(f"{what} can be at most {maximum}")
    return value


def _field_list(parser: Parser, stage: str, allow_sign: bool = False) -> Tuple[List[str], str]:
    sign = ""
    if allow_sign and parser.at_op("-", "+"):
        sign = parser.next().value
    names = []
    while not parser.done():
        names.append(parser.name("a field name"))
        if not parser.done():
            parser.expect_op(",")
    if not names:
        raise PipelineError(f"`{stage}` needs a field")
    return names, sign


class Pipeline:
    def __init__(self, compiler: Compiler):
        self.c = compiler

    # -- generic transforms ------------------------------------------------------
    def add_column(self, scope: Scope, name: str, col: Col) -> Scope:
        quoted = q(name)
        if scope.open:
            if name in scope.real:
                sql = f"SELECT * REPLACE ({col.sql} AS {quoted}) FROM ({scope.sql})"
            else:
                sql = f"SELECT *, {col.sql} AS {quoted} FROM ({scope.sql})"
            computed = [n for n in scope.computed if n != name] + [name]
            cols = dict(scope.cols)
            cols[name] = Col(quoted, col.type)
            return Scope(**{**scope.__dict__, "sql": sql, "cols": cols, "real": scope.real | {name},
                            "hidden": scope.hidden - {name}, "computed": computed})
        items, replaced = [], False
        for existing, c in scope.cols.items():
            if existing == name:
                items.append(f"{col.sql} AS {quoted}")
                replaced = True
            else:
                items.append(f"{c.sql} AS {q(existing)}")
        if not replaced:
            items.append(f"{col.sql} AS {quoted}")
        cols = {n: Col(q(n), c.type) for n, c in scope.cols.items()}
        cols[name] = Col(quoted, col.type)
        return Scope(**{**scope.__dict__, "sql": f"SELECT {', '.join(items)} FROM ({scope.sql})", "cols": cols})

    def visible(self, scope: Scope) -> List[str]:
        if scope.open:
            return [n for n in EVENT_OUTPUT if n not in scope.hidden and n not in scope.computed] + scope.computed
        return list(scope.cols)

    def close(self, scope: Scope, names: List[str], renames: Dict[str, str], stage: str) -> Scope:
        """Select exactly `names` (each output as renames.get(name, name))."""
        resolved = [(name, renames.get(name, name), self.c.resolve(scope, name)) for name in names]
        outputs = [out for _, out, _ in resolved]
        if len(set(outputs)) != len(outputs):
            raise PipelineError(f"`{stage}`: a field appears twice")
        order = scope.order
        if not order and scope.events and not scope.order_frozen:
            ts = scope.cols.get("ts") or (self.c.base_field("ts") if scope.open and "ts" not in scope.hidden
                                          else None)
            order = [(ts.sql, "DESC")] if ts else []
        mapping = {col.sql: q(out) for _, out, col in resolved}
        new_order, inner = [], scope.sql
        frozen = scope.order_frozen
        if order and all(sql in mapping for sql, _ in order):
            new_order = [(mapping[sql], d) for sql, d in order]
        elif order:
            inner = f"{scope.sql} ORDER BY {', '.join(f'{s} {d}' for s, d in order)}"
            frozen = True
        select = ", ".join(f"{col.sql} AS {q(out)}" for _, out, col in resolved)
        return Scope(sql=f"SELECT {select} FROM ({inner})",
                     cols={out: Col(q(out), col.type) for _, out, col in resolved},
                     open=False, events=scope.events, kind=scope.kind, order=new_order, order_frozen=frozen,
                     limit=scope.limit, closed_by=stage)

    def order_clause(self, scope: Scope) -> str:
        if scope.order_frozen and not scope.order:
            return ""
        order = scope.order
        if not order and scope.events:
            try:
                order = [(self.c.resolve(scope, "ts").sql, "DESC")]
            except PipelineError:
                order = []
        return f" ORDER BY {', '.join(f'{s} {d}' for s, d in order)}" if order else ""

    # -- where / eval ------------------------------------------------------------
    def where(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "where")
        if parser.done():
            raise PipelineError("`where` needs a condition")
        cond = parser.expr()
        if not parser.done():
            parser.fail(parser.peek(), "expected and / or or the end of the condition")
        return Scope(**{**scope.__dict__, "sql": f"SELECT * FROM ({scope.sql}) WHERE {cond.sql}"})

    def eval(self, scope: Scope, body: str) -> Scope:
        tokens = tokenize(body)
        parser = Parser(self.c, scope, tokens, "eval")
        if parser.done():
            raise PipelineError("`eval` needs name = expression")
        while not parser.done():
            name_tok = parser.next()
            if name_tok.kind != "ident" or not parser.at_op("="):
                raise PipelineError("`eval` expects name = expression, e.g. eval kb = bytes / 1024")
            name = name_tok.value
            if not _NAME_RE.match(name):
                raise PipelineError(f"`eval`: {name!r} is not a valid name (letters, digits and _)")
            parser.next()
            parser.scope = scope
            col = parser.expr()
            if col.type == LIST:
                raise PipelineError("`eval`: a list cannot be a field value")
            _not_all(col)
            scope = self.add_column(scope, name, col)
            if not parser.done():
                parser.expect_op(",")
        return scope

    # -- aggregations --------------------------------------------------------------
    def aggregations(self, parser: Parser, stage: str) -> List[Tuple[str, Col]]:
        aggs: List[Tuple[str, Col]] = []
        while not parser.done() and not parser.peek().is_kw("by"):
            func_tok = parser.next()
            if func_tok.kind != "ident":
                parser.fail(func_tok, "expected an aggregation such as count() or avg(field)")
            func = func_tok.value.lower()
            args: List[Col] = []
            arg_text: List[str] = []
            if parser.at_op("("):
                parser.next()
                start = parser.i
                if parser.at_op("*") and parser.peek(1).kind == "op" and parser.peek(1).value == ")":
                    parser.next()
                while not parser.at_op(")"):
                    args.append(parser.expr())
                    if not parser.at_op(")"):
                        parser.expect_op(",")
                arg_toks = parser.toks[start:parser.i]
                parser.next()
                arg_text = [str(t.value) for t in arg_toks]
            col = aggregate(self.c, func, args, stage)
            alias = None
            if parser.peek().is_kw("as"):
                parser.next()
                alias = parser.name("a name after as")
                if not _NAME_RE.match(alias):
                    raise PipelineError(f"`{stage}`: {alias!r} is not a valid name")
            if alias is None:
                alias = default_name(func, arg_text, args)
                if alias is None:
                    raise PipelineError(f"`{stage}`: name {func}(...) with `as`, e.g. {func}(...) as value")
            if any(alias == existing for existing, _ in aggs):
                raise PipelineError(f"`{stage}`: {alias!r} is used twice")
            aggs.append((alias, col))
            if not parser.done() and not parser.peek().is_kw("by"):
                parser.expect_op(",")
        if not aggs:
            raise PipelineError(f"`{stage}` needs an aggregation, e.g. {stage} count() by service")
        return aggs

    def by_fields(self, parser: Parser, scope: Scope, stage: str) -> List[Tuple[str, Col]]:
        if not parser.peek().is_kw("by"):
            return []
        parser.next()
        names, _ = _field_list(parser, stage)
        return [(name, self.c.resolve(scope, name)) for name in names]

    def stats(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "stats")
        aggs = self.aggregations(parser, "stats")
        by = self.by_fields(parser, scope, "stats")
        names = [n for n, _ in by] + [n for n, _ in aggs]
        if len(set(names)) != len(names):
            raise PipelineError("`stats`: a name is used twice")
        select = ", ".join([f"{c.sql} AS {q(n)}" for n, c in by] + [f"{c.sql} AS {q(n)}" for n, c in aggs])
        group = f" GROUP BY {', '.join(q(n) for n, _ in by)}" if by else ""
        cols = {n: Col(q(n), c.type) for n, c in by + aggs}
        return Scope(sql=f"SELECT {select} FROM ({scope.sql}){group}", cols=cols, open=False, events=False,
                     kind="table", order=[(q(n), "ASC") for n, _ in by], limit=None, closed_by="stats")

    def eventstats(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "eventstats")
        aggs = self.aggregations(parser, "eventstats")
        by = self.by_fields(parser, scope, "eventstats")
        window = f"OVER (PARTITION BY {', '.join(c.sql for _, c in by)})" if by else "OVER ()"
        for name, col in aggs:
            scope = self.add_column(scope, name, Col(f"{col.sql} {window}", col.type))
        return scope

    def timechart(self, scope: Scope, body: str) -> Scope:
        options, body = _options(body, ("span", "limit"), "timechart")
        if "span" in options:
            interval, _ = _span(options["span"], "timechart")
        else:
            interval = auto_interval(self.c.start, self.c.end)
        limit = _positive(options.get("limit", "10"), "timechart limit", MAX_SERIES) \
            if options.get("limit") != "0" else 0
        ts = self.c.resolve(scope, "ts")
        if ts.type != TIME:
            raise PipelineError("`timechart` needs events with a ts")
        parser = Parser(self.c, scope, tokenize(body), "timechart")
        aggs = self.aggregations(parser, "timechart")
        by = self.by_fields(parser, scope, "timechart")
        if len(by) > 1:
            raise PipelineError("`timechart` splits by one field at most")
        bucket = f"toStartOfInterval(toDateTime({ts.sql}, 'UTC'), {interval})"
        select = [f"{bucket} AS `_time`"]
        cols = {"_time": Col("`_time`", TIME)}
        group = ["`_time`"]
        if by:
            name, col = by[0]
            series = to_str(col)
            if limit:
                top = (f"SELECT {series} AS k FROM ({scope.sql}) GROUP BY k ORDER BY count() DESC, k "
                       f"LIMIT {limit}")
                series = f"if({series} IN ({top}), {series}, 'OTHER')"
            select.append(f"{series} AS {q(name)}")
            cols[name] = Col(q(name), STR)
            group.append(q(name))
        for name, col in aggs:
            if name in cols:
                raise PipelineError(f"`timechart`: {name!r} is used twice")
            select.append(f"{col.sql} AS {q(name)}")
            cols[name] = Col(q(name), col.type)
        sql = f"SELECT {', '.join(select)} FROM ({scope.sql}) GROUP BY {', '.join(group)}"
        order = [("`_time`", "ASC")] + ([(q(by[0][0]), "ASC")] if by else [])
        frozen = False
        if not by:
            start = f"toStartOfInterval(toDateTime({self.c.bind(self.c.start)}, 'UTC'), {interval})"
            end = f"toDateTime({self.c.bind(self.c.end)}, 'UTC')"
            sql += f" ORDER BY `_time` ASC WITH FILL FROM {start} TO {end} STEP {interval}"
            order, frozen = [], True
        return Scope(sql=sql, cols=cols, open=False, events=False, kind="timechart", order=order,
                     order_frozen=frozen, closed_by="timechart")

    def top(self, scope: Scope, body: str, rare: bool = False) -> Scope:
        stage = "rare" if rare else "top"
        options, body = _options(body, ("limit",), stage)
        limit = _positive(options.get("limit", "10"), f"{stage} limit", MAX_ROWS)
        parser = Parser(self.c, scope, tokenize(body), stage)
        names = []
        while not parser.done() and not parser.peek().is_kw("by"):
            names.append(parser.name("a field name"))
            if not parser.done() and not parser.peek().is_kw("by"):
                parser.expect_op(",")
        if not names:
            raise PipelineError(f"`{stage}` needs a field, e.g. {stage} src_ip")
        fields = [(n, self.c.resolve(scope, n)) for n in names]
        by = self.by_fields(parser, scope, stage)
        all_names = [n for n, _ in by] + names
        if len(set(all_names)) != len(all_names) or {"count", "percent"} & set(all_names):
            raise PipelineError(f"`{stage}`: a field is used twice")
        partition = f"PARTITION BY {', '.join(q(n) for n, _ in by)}" if by else ""
        select = [f"{c.sql} AS {q(n)}" for n, c in by + fields]
        select += ["count() AS `count`", f"100 * count() / sum(count()) OVER ({partition}) AS `percent`"]
        direction = "ASC" if rare else "DESC"
        order = [(q(n), "ASC") for n, _ in by] + [("`count`", direction)] + [(q(n), "ASC") for n in names]
        order_sql = ", ".join(f"{s} {d}" for s, d in order)
        limit_sql = f"LIMIT {limit} BY {', '.join(q(n) for n, _ in by)}" if by else f"LIMIT {limit}"
        sql = (f"SELECT {', '.join(select)} FROM ({scope.sql}) GROUP BY {', '.join(q(n) for n in all_names)} "
               f"ORDER BY {order_sql} {limit_sql}")
        cols = {n: Col(q(n), c.type) for n, c in by + fields}
        cols.update({"count": Col("`count`", NUM), "percent": Col("`percent`", NUM)})
        return Scope(sql=sql, cols=cols, open=False, events=False, kind="table", order=order, closed_by=stage)

    # -- row stages ------------------------------------------------------------------
    def sort(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "sort")
        count = None
        if parser.peek().kind == "num":
            count = _positive(str(parser.next().value), "sort's count", self.c.max_rows)
        order = []
        while not parser.done():
            direction = "ASC"
            if parser.at_op("-", "+"):
                direction = "DESC" if parser.next().value == "-" else "ASC"
            name = parser.name("a field to sort by")
            if parser.peek().is_kw("asc", "desc"):
                direction = parser.next().value.upper()
            order.append((self.c.resolve(scope, name).sql, direction))
            if not parser.done():
                parser.expect_op(",")
        if not order:
            raise PipelineError("`sort` needs a field, e.g. sort -count")
        scope = Scope(**{**scope.__dict__, "order": order, "order_frozen": False})
        return self.head(scope, str(count)) if count else scope

    def head(self, scope: Scope, body: str) -> Scope:
        body = body.strip() or "10"
        n = _positive(body, "head", self.c.max_rows)
        sql = f"SELECT * FROM ({scope.sql}){self.order_clause(scope)} LIMIT {n}"
        limit = n if scope.limit is None else min(n, scope.limit)
        return Scope(**{**scope.__dict__, "sql": sql, "limit": limit})

    def dedup(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "dedup")
        keep = 1
        if parser.peek().kind == "num":
            keep = _positive(str(parser.next().value), "dedup's count", self.c.max_rows)
        names, _ = _field_list(parser, "dedup")
        cols = [self.c.resolve(scope, n) for n in names]
        present = " AND ".join(nonempty(c) for c in cols)
        sql = (f"SELECT * FROM ({scope.sql}) WHERE {present}{self.order_clause(scope)} "
               f"LIMIT {keep} BY {', '.join(c.sql for c in cols)}")
        return Scope(**{**scope.__dict__, "sql": sql})

    def fields(self, scope: Scope, body: str, stage: str = "fields") -> Scope:
        parser = Parser(self.c, scope, tokenize(body), stage)
        names, sign = _field_list(parser, stage, allow_sign=True)
        for name in names:
            self.c.resolve(scope, name)  # unknown names fail here
        if sign == "-":
            if scope.open:
                return Scope(**{**scope.__dict__, "hidden": scope.hidden | set(names),
                                "computed": [n for n in scope.computed if n not in names]})
            keep = [n for n in scope.cols if n not in names]
            return self.close(scope, keep, {}, stage)
        return self.close(scope, names, {}, stage)

    def rename(self, scope: Scope, body: str) -> Scope:
        parser = Parser(self.c, scope, tokenize(body), "rename")
        pairs = []
        while not parser.done():
            old = parser.name("a field to rename")
            if not parser.next().is_kw("as"):
                raise PipelineError("`rename` expects: rename old as new")
            new = parser.name("a new name")
            if not _NAME_RE.match(new):
                raise PipelineError(f"`rename`: {new!r} is not a valid name")
            pairs.append((old, new))
            if not parser.done():
                parser.expect_op(",")
        if not pairs:
            raise PipelineError("`rename` expects: rename old as new")
        for old, new in pairs:
            col = self.c.resolve(scope, old)
            if scope.open:
                scope = self.add_column(scope, new, col)
                scope = Scope(**{**scope.__dict__, "hidden": scope.hidden | {old},
                                 "computed": [n for n in scope.computed if n != old]})
                scope.cols.pop(old, None)
            else:
                order = [(q(new) if s == q(old) else s, d) for s, d in scope.order]
                scope = self.close(scope, list(scope.cols), {old: new}, "rename")
                scope.order = order if all(s in [c.sql for c in scope.cols.values()] for s, _ in order) \
                    else scope.order
        return scope

    def bin(self, scope: Scope, body: str) -> Scope:
        options, body = _options(body, ("span",), "bin")
        parser = Parser(self.c, scope, tokenize(body), "bin")
        name = parser.name("a field to bin")
        target = name
        if parser.peek().is_kw("as"):
            parser.next()
            target = parser.name("a name after as")
            if not _NAME_RE.match(target):
                raise PipelineError(f"`bin`: {target!r} is not a valid name")
        if not parser.done():
            parser.fail(parser.peek(), "expected the end of bin")
        col = self.c.resolve(scope, name)
        if col.type == TIME:
            interval = _span(options["span"], "bin")[0] if "span" in options else \
                auto_interval(self.c.start, self.c.end)
            binned = Col(f"toStartOfInterval(toDateTime({col.sql}, 'UTC'), {interval})", TIME)
        else:
            if "span" not in options:
                raise PipelineError("`bin` needs span= for a number, e.g. bin span=100 bytes")
            try:
                width = float(options["span"])
            except ValueError:
                raise PipelineError(f"`bin`: span must be a number for {name}") from None
            if not math.isfinite(width) or width <= 0:
                raise PipelineError("`bin`: span must be positive")
            width_sql = repr(width) if width != int(width) else str(int(width))
            binned = Col(f"(floor({to_num(col)} / {width_sql}) * {width_sql})", NUM)
        if scope.open or target in scope.cols or not scope.cols:
            return self.add_column(scope, target, binned)
        return self.add_column(scope, target, binned)

    # -- extraction (shared with the original language) ---------------------------------
    def extraction(self, scope: Scope, keyword: str, body: str) -> Scope:
        source = "msg"
        match = logql._FIELD_OPTION_RE.match(body)
        if match:
            source = match.group("field")
            body = body[match.end():]
        source_col = self.c.resolve(scope, source)
        holder = logql.ParsedQuery()
        try:
            {"rex": logql._parse_rex, "parse": logql._parse_parse, "json": logql._parse_json}[keyword](body, holder)
        except LogQLSyntaxError as e:
            raise PipelineError(str(e)) from None
        except QueryFieldError as e:
            raise PipelineError(str(e)) from None
        text = to_str(source_col)
        for extraction in holder.extractions:
            if extraction["kind"] == "regex":
                sql = f"extractGroups({text}, {self.c.bind(extraction['pattern'])})[{int(extraction['group'])}]"
            else:
                keys = ", ".join(self.c.bind(k) for k in extraction["path"])
                sql = f"JSONExtractString({text}, {keys})"
            scope = self.add_column(scope, extraction["name"], Col(sql, STR))
        return scope


    # -- lookups and joins -------------------------------------------------------------
    def lookup(self, scope: Scope, body: str) -> Scope:
        """lookup <name> <field> [as <key column>] [output col [as alias], ...]"""
        parser = Parser(self.c, scope, tokenize(body), "lookup")
        if parser.done():
            raise PipelineError("`lookup` needs a lookup and a field, e.g. lookup users user_id")
        meta = self.c.lookup(parser.name("a lookup name"))
        if parser.done():
            raise PipelineError("`lookup` needs a field to match, e.g. lookup users user_id")
        field_name = parser.name("a field to match")
        if parser.peek().is_kw("as"):
            parser.next()
            key = parser.name("the lookup's key column")
            if key != meta.key:
                raise PipelineError(f"`lookup`: {meta.name} is keyed by {meta.key}, not {key}")
        outputs: List[Tuple[str, str]] = []
        if parser.peek().is_kw("output", "outputnew"):
            parser.next()
            while not parser.done():
                column = parser.name("a lookup column")
                alias = column
                if parser.peek().is_kw("as"):
                    parser.next()
                    alias = parser.name("a name after as")
                outputs.append((column, alias))
                if not parser.done():
                    parser.expect_op(",")
        elif not parser.done():
            parser.fail(parser.peek(), "expected output or the end of lookup")
        if not outputs:
            outputs = [(c, c) for c in meta.columns if c != meta.key]
        for column, alias in outputs:
            if column not in meta.columns or column == meta.key:
                raise PipelineError(f"`lookup`: {meta.name} has no column {column} "
                                    f"(columns: {', '.join(c for c in meta.columns if c != meta.key)})")
            if not _NAME_RE.match(alias):
                raise PipelineError(f"`lookup`: {alias!r} is not a valid name")
        key = Col(f"toString({self.c.resolve(scope, field_name).sql})", STR)
        scope = self.add_column(scope, "__lk", key)
        visible = self.visible(scope)
        joined = (f"FROM ({scope.sql}) AS l ANY LEFT JOIN ({self.c.lookup_rows(meta)}) AS r "
                  f"ON l.`__lk` = r.key")
        values = [(alias, Col(f"if(r.key = '', NULL, r.values[{self.c.bind(column)}])", STR))
                  for column, alias in outputs]
        if scope.open:
            kept = [n for n in scope.real if n != "__lk"]
            select = [f"l.{q(n)} AS {q(n)}" for n in sorted(kept) if n not in {a for a, _ in values}]
            select += [f"{c.sql} AS {q(a)}" for a, c in values]
            computed = [n for n in scope.computed if n != "__lk" and n not in {a for a, _ in values}]
            cols = {n: c for n, c in scope.cols.items() if n != "__lk"}
            for alias, c in values:
                cols[alias] = Col(q(alias), STR)
            return Scope(**{**scope.__dict__, "sql": f"SELECT {', '.join(select)} {joined}", "cols": cols,
                            "real": (set(kept) | {a for a, _ in values}), "computed": computed + [a for a, _ in values],
                            "hidden": scope.hidden - {a for a, _ in values}})
        names = [n for n in visible if n != "__lk" and n not in {a for a, _ in values}]
        select = [f"l.{q(n)} AS {q(n)}" for n in names] + [f"{c.sql} AS {q(a)}" for a, c in values]
        cols = {n: Col(q(n), scope.cols[n].type) for n in names}
        cols.update({a: Col(q(a), STR) for a, _ in values})
        order = [(s, d) for s, d in scope.order if s in {q(n) for n in names}]
        return Scope(**{**scope.__dict__, "sql": f"SELECT {', '.join(select)} {joined}", "cols": cols,
                        "order": order})

    def join(self, scope: Scope, body: str) -> Scope:
        """join [type=inner|left] [max=N] key[, key] [ subsearch ]"""
        options, body = _options(body, ("type", "max"), "join")
        how = options.get("type", "inner").lower()
        if how not in ("inner", "left"):
            raise PipelineError("`join`: type must be inner or left")
        max_rows = _positive(options.get("max", str(DEFAULT_JOIN_ROWS)), "join max", MAX_JOIN_ROWS)
        head, subsearch = _subsearch(body)
        parser = Parser(self.c, scope, tokenize(head), "join")
        keys, _ = _field_list(parser, "join")
        if self.c.join_depth >= MAX_JOIN_DEPTH:
            raise PipelineError(f"`join`: subsearches can be nested at most {MAX_JOIN_DEPTH} deep")
        self.c.join_depth += 1
        try:
            right_pipeline, right_scope, _ = run_stages(self.c, subsearch)
        finally:
            self.c.join_depth -= 1
        right_columns = right_pipeline.visible(right_scope)
        for key in keys:
            if key not in right_columns:
                raise PipelineError(f"`join`: {key} is not in the subsearch's results "
                                    f"({', '.join(right_columns)})")
        left_names = set(self.visible(scope)) | set(scope.cols)
        extra = [n for n in right_columns if n not in keys]
        clash = [n for n in extra if n in left_names]
        if clash:
            raise PipelineError(f"`join`: both sides have {', '.join(clash)}; rename one side first")
        right_sql, _ = final_select(right_pipeline, right_scope, max_rows)
        right_keys = ", ".join(f"toString({q(k)}) AS {q(k)}" for k in keys)
        right_rest = "".join(f", {q(n)}" for n in extra)
        # One right row per key, then a plain join: ClickHouse's ANY INNER JOIN
        # also keeps only one LEFT row per key, which dropped events.
        right = (f"SELECT {right_keys}{right_rest} FROM ({right_sql}) "
                 f"LIMIT 1 BY {', '.join(q(k) for k in keys)}")
        for key in keys:
            scope = self.add_column(scope, key, Col(to_str(self.c.resolve(scope, key)), STR))
        on = " AND ".join(f"l.{q(k)} = r.{q(k)}" for k in keys)
        joined = f"FROM ({scope.sql}) AS l {how.upper()} JOIN ({right}) AS r ON {on}"
        right_types = {n: (right_scope.cols[n].type if n in right_scope.cols else
                           right_pipeline.c.resolve(right_scope, n).type) for n in extra}
        if scope.open:
            select = ["l.*"] + [f"r.{q(n)} AS {q(n)}" for n in extra]
            cols = dict(scope.cols)
            cols.update({n: Col(q(n), right_types[n]) for n in extra})
            return Scope(**{**scope.__dict__, "sql": f"SELECT {', '.join(select)} {joined}", "cols": cols,
                            "real": scope.real | set(extra), "computed": scope.computed + extra})
        names = list(scope.cols)
        select = [f"l.{q(n)} AS {q(n)}" for n in names] + [f"r.{q(n)} AS {q(n)}" for n in extra]
        cols = {n: Col(q(n), scope.cols[n].type) for n in names}
        cols.update({n: Col(q(n), right_types[n]) for n in extra})
        return Scope(**{**scope.__dict__, "sql": f"SELECT {', '.join(select)} {joined}", "cols": cols})


def _subsearch(body: str) -> Tuple[str, str]:
    """Split `key, key [ subsearch ]` at the first [ outside quotes."""
    quote, depth, start = None, 0, None
    for i, char in enumerate(body):
        if quote:
            if char == "\\":
                continue
            if char == quote and body[i - 1] != "\\":
                quote = None
            continue
        if char in "\"'":
            quote = char
        elif char == "[":
            if depth == 0 and start is None:
                start = i
            depth += 1
        elif char == "]":
            depth -= 1
    stripped = body.rstrip()
    if start is None or not stripped.endswith("]") or depth != 0:
        raise PipelineError("`join` needs a subsearch in brackets, e.g. join user_id [ | stats count() by user_id ]")
    inner = stripped[start + 1:-1].strip()
    if not inner:
        raise PipelineError("`join`: the subsearch is empty")
    return body[:start], inner


def default_name(func: str, arg_text: List[str], args: List[Col]) -> Optional[str]:
    if func in ("count", "c") and not args:
        return "count"
    if len(arg_text) == 1 and _FIELD_NAME_RE.match(arg_text[0]):
        return f"{func}({arg_text[0]})"
    if func in ("percentile", "perc") and len(arg_text) == 3 and _FIELD_NAME_RE.match(arg_text[0]):
        return f"p{arg_text[2]}({arg_text[0]})"
    return None


_PERCENTILE_RE = re.compile(r"^(?:p|perc)(\d{1,2})$")


def aggregate(c: Compiler, func: str, args: List[Col], stage: str) -> Col:
    def one() -> Col:
        if len(args) != 1:
            raise PipelineError(f"`{stage}`: {func} needs a field, e.g. {func}(bytes)")
        return args[0]

    if func in ("count", "c"):
        if not args:
            return Col("count()", NUM)
        return Col(f"countIf({nonempty(one())})", NUM)
    if func in ("dc", "distinct_count"):
        x = one()
        return Col(f"uniqExactIf({x.sql}, {nonempty(x)})", NUM)
    if func == "estdc":
        x = one()
        return Col(f"uniqIf({x.sql}, {nonempty(x)})", NUM)
    if func in ("sum", "avg", "mean", "stdev", "var"):
        sql = {"sum": "sum", "avg": "avg", "mean": "avg", "stdev": "stddevSamp", "var": "varSamp"}[func]
        return Col(f"{sql}({to_num(one())})", NUM)
    if func in ("min", "max"):
        x = one()
        if x.type == TIME:
            return Col(f"{func}({x.sql})", TIME)
        return Col(f"{func}({to_num(x)})", NUM)
    if func == "median":
        return Col(f"quantile(0.5)({to_num(one())})", NUM)
    match = _PERCENTILE_RE.match(func)
    if match:
        level = int(match.group(1))
        if not 1 <= level <= 99:
            raise PipelineError(f"`{stage}`: percentiles go from p1 to p99")
        return Col(f"quantile({level / 100})({to_num(one())})", NUM)
    if func in ("percentile", "perc"):
        if len(args) != 2 or not isinstance(args[1].literal, (int, float)) or not 0 < args[1].literal < 100:
            raise PipelineError(f"`{stage}`: percentile(field, N) takes N between 0 and 100")
        return Col(f"quantile({float(args[1].literal) / 100})({to_num(args[0])})", NUM)
    if func == "values":
        x = one()
        return Col(f"arraySort(groupUniqArrayIf({MAX_VALUES})({to_str(x)}, {nonempty(x)}))", LIST)
    if func == "list":
        x = one()
        return Col(f"groupArrayIf({MAX_VALUES})({to_str(x)}, {nonempty(x)})", LIST)
    if func in ("earliest", "latest"):
        x = one()
        return Col(f"{'argMin' if func == 'earliest' else 'argMax'}({x.sql}, ts)", x.type)
    if func == "sum" and not args:
        raise PipelineError(f"`{stage}`: sum needs a field")
    raise PipelineError(f"`{stage}`: unknown aggregation {func!r}. Available: count, dc, estdc, sum, avg, min, "
                        f"max, median, p1..p99, percentile, stdev, var, values, list, earliest, latest")


def auto_interval(start: datetime, end: datetime) -> str:
    """A span giving at most ~50 buckets over the window."""
    seconds = max(1.0, (end - start).total_seconds())
    for span in _AUTO_SPANS:
        interval, width = _span(span, "timechart")
        if seconds / width <= 50:
            return interval
    return _span(_AUTO_SPANS[-1], "timechart")[0]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _split(query: str) -> Tuple[Optional[str], List[str]]:
    if query is None or not query.strip():
        raise PipelineError("Query is empty")
    stages = logql._split_top_level(query, "|")
    text = None
    if stages:
        first = stages[0].strip()
        word = first.split()[0].lower() if first else ""
        if first == "*":
            stages = stages[1:]
        elif first and word not in STAGES and not query.lstrip().startswith("|"):
            text, stages = first, stages[1:]
            if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
                text = re.sub(r"\\([\\" + text[0] + r"])", r"\1", text[1:-1])  # "a phrase" searches a phrase
    return text, stages


_QUOTED_RE = re.compile(r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'""")


def uses_pipeline(query: str) -> bool:
    """True when the query needs this compiler: the original LogforgeQL
    cannot parse it. Queries it can parse keep its exact behaviour."""
    try:
        text, stages = _split(query)
    except PipelineError:
        return False
    v1 = ("where", "stats", "sort", "limit", "last", "rex", "parse", "json")
    keywords = [stage.split()[0].lower() for stage in stages if stage.strip()]
    if any(k not in v1 for k in keywords):
        return True
    # The original compiler is not a pipeline: it applies every filter before
    # the aggregation, so `stats ... | where n > 3` silently filtered the
    # events instead. Stages after stats need this compiler.
    if "stats" in keywords and any(k in ("where", "rex", "parse", "json")
                                   for k in keywords[keywords.index("stats") + 1:]):
        return True
    # $variables are values here; the original compiler searched for "$name".
    unquoted = _QUOTED_RE.sub("", query)
    if re.search(r"\$[A-Za-z_]", unquoted):
        return True
    try:
        logql.parse(query)
        return False
    except Exception:
        return True


def requested_seconds(query: str) -> Optional[int]:
    """The window a `| last <duration>` stage asks for, if any."""
    try:
        _, stages = _split(query)
    except PipelineError:
        return None
    seconds = None
    for stage in stages:
        words = stage.split()
        if words and words[0].lower() == "last" and len(words) == 2:
            match = logql._DURATION_RE.match(words[1])
            if match:
                seconds = int(match.group("count")) * logql._DURATION_SECONDS[match.group("unit").lower()]
    return seconds


def run_stages(compiler: Compiler, query: str) -> Tuple["Pipeline", Scope, bool]:
    text, stages = _split(query)
    pipeline = Pipeline(compiler)
    scope = compiler.base(text)
    explicit_limit = False
    for stage in stages:
        stage = stage.strip()
        if not stage:
            continue
        keyword = stage.split()[0].lower()
        body = stage[len(keyword):].strip()
        if keyword not in STAGES:
            raise PipelineError(f"Unknown stage: {stage.split()[0]!r}. Supported: {', '.join(STAGES)}")
        if keyword == "last":
            if logql._DURATION_RE.match(body) is None:
                raise PipelineError(f"`last` requires a duration like 15m, 24h or 7d, got {body!r}")
            continue  # applied to the window by the caller (requested_seconds)
        if keyword == "where":
            scope = pipeline.where(scope, body)
        elif keyword == "eval":
            scope = pipeline.eval(scope, body)
        elif keyword == "stats":
            scope = pipeline.stats(scope, body)
        elif keyword == "eventstats":
            scope = pipeline.eventstats(scope, body)
        elif keyword == "timechart":
            scope = pipeline.timechart(scope, body)
        elif keyword in ("top", "rare"):
            scope = pipeline.top(scope, body, rare=keyword == "rare")
        elif keyword == "sort":
            scope = pipeline.sort(scope, body)
            explicit_limit = explicit_limit or scope.limit is not None
        elif keyword in ("head", "limit"):
            if keyword == "limit" and not body:
                raise PipelineError("`limit` requires an integer")
            scope = pipeline.head(scope, body)
            explicit_limit = True
        elif keyword == "dedup":
            scope = pipeline.dedup(scope, body)
        elif keyword in ("fields", "table"):
            scope = pipeline.fields(scope, body, keyword)
        elif keyword == "rename":
            scope = pipeline.rename(scope, body)
        elif keyword == "bin":
            scope = pipeline.bin(scope, body)
        elif keyword in ("rex", "parse", "json"):
            scope = pipeline.extraction(scope, keyword, body)
        elif keyword == "lookup":
            scope = pipeline.lookup(scope, body)
        elif keyword == "join":
            scope = pipeline.join(scope, body)
    return pipeline, scope, explicit_limit


def final_select(pipeline: "Pipeline", scope: Scope, limit: int) -> Tuple[str, List[str]]:
    columns = pipeline.visible(scope)
    if scope.open:
        select = ", ".join(f"{pipeline.c.resolve(scope, n).sql} AS {q(n)}" for n in columns)
    else:
        select = ", ".join(q(n) for n in columns)
    return f"SELECT {select} FROM ({scope.sql}){pipeline.order_clause(scope)} LIMIT {int(limit)}", columns


def compile_pipeline(query: str, customer_id: str, start: datetime, end: datetime, table: str = "logs_raw_mt",
                     variables: Optional[Dict[str, Any]] = None, max_rows: int = MAX_ROWS,
                     lookups: Optional[Dict[str, LookupMeta]] = None,
                     lookup_table: str = "lookup_rows_mt") -> CompiledQuery:
    if not customer_id:
        raise PipelineError("a tenant is required")
    compiler = Compiler(customer_id, start, end, table, variables, max_rows, lookups, lookup_table)
    pipeline, scope, explicit_limit = run_stages(compiler, query)
    limit = scope.limit if scope.limit is not None else (DEFAULT_EVENT_ROWS if scope.events else max_rows)
    sql, columns = final_select(pipeline, scope, limit)
    return CompiledQuery(sql=sql, params=compiler.params, columns=columns, result_type=scope.kind,
                         limit=int(limit), explicit_limit=explicit_limit)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (str, int, bool, date)) or value is None:
        return value
    return str(value)


def execute(client, compiled: CompiledQuery, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    import json as _json

    result = client.query(compiled.sql, parameters=compiled.params, settings=settings or {})
    names = list(result.column_names)
    rows = []
    for raw in result.result_rows:
        row = {name: _clean(value) for name, value in zip(names, raw)}
        if compiled.result_type == "events" and isinstance(row.get("attrs"), str):
            try:
                row["attrs"] = _json.loads(row["attrs"]) if row["attrs"] else {}
            except ValueError:
                pass
        rows.append(row)
    return {"rows": rows, "columns": names, "result_type": compiled.result_type,
            "truncated": len(rows) >= compiled.limit and not compiled.explicit_limit}
