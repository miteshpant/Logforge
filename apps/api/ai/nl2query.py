"""
Natural language -> LogforgeQL (Phase 9).

The answer is always a query the user sees, can edit and runs themselves;
nothing here reads log data except the field catalogue (names, types and a
few example values, redacted before they reach a model).

`translate` uses a model; `rule_based` is the deterministic fallback for when
AI is off. Both return a QueryDraft whose query has been compiled.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .providers import Message
from .redaction import Redactor

COLUMNS = ("ts", "service", "host", "level", "msg", "status", "src_ip", "user_id", "trace_id", "span_id")
MAX_FIELDS = 80

PROMPT = """You turn questions about logs into one LogforgeQL query. Answer with JSON only:
{"query": "<the query>", "explanation": "<one or two sentences on what the query does>"}

Each event has: ts, service, host, level (debug, info, warn, error), msg, status (HTTP status), src_ip,
user_id, trace_id, and attrs.* for anything else. Use only fields from the list below (or those columns).

A query is optional free text to search for, then pipeline stages separated by |:
  | last 15m                time window: 15m, 1h, 24h, 7d (put it first)
  | where <condition>       service = "auth", level = "error", status >= 500, msg contains "panic";
                            combine with and / or / not
  | stats count() as n by f1, f2   also sum(f), avg(f), dc(f), p95(f), values(f)
  | timechart span=5m count() by service
  | top limit=10 field      most common values
  | sort ts desc            or -field / field
  | head 100

Examples:
  Errors from the api service per host -> | where service = "api" and level = "error" | stats count() as n by host
  Lines mentioning "connection reset" in the last hour -> "connection reset" | last 1h
  Slowest endpoints -> | stats p95(attrs.duration_ms) as p95 by attrs.path | sort -p95 | head 10"""


@dataclass
class QueryDraft:
    query: str | None
    explanation: str
    valid: bool
    mode: str  # ai | rule_based
    error: str | None = None
    fields_used: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        return asdict(self)


# -- validation ----------------------------------------------------------------------

def compile_error(query: str) -> str | None:
    """None if the query compiles, else the compiler's message."""
    import logql
    import logql_pipeline as lp

    try:
        logql.compile_to_request_payload(query)
        return None
    except Exception:  # noqa: BLE001 - fall through to the pipeline compiler
        pass
    end = datetime.now(timezone.utc)
    try:
        lp.compile_pipeline(query, customer_id="nl2query-check", start=end - timedelta(hours=1), end=end)
        return None
    except Exception as e:  # noqa: BLE001 - any failure is "doesn't compile"
        return str(e) or type(e).__name__


_FIELD = re.compile(r"(?<![\w\".])((?:attrs|ocsf)\.[A-Za-z0-9_.\-]+|ts|service|host|level|msg|status|src_ip|"
                    r"user_id|trace_id|span_id)(?![\w(])")


def fields_in(query: str) -> list[str]:
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', query)  # ignore quoted values
    seen: list[str] = []
    for name in _FIELD.findall(text):
        if name not in seen:
            seen.append(name)
    return seen


def _known(catalogue: dict[str, Any] | None) -> set:
    names = {f["name"] for f in (catalogue or {}).get("fields", [])}
    return names | set(COLUMNS)


# -- the model path -------------------------------------------------------------------

def catalogue_prompt(catalogue: dict[str, Any] | None, redactor: Redactor) -> str:
    lines = []
    for f in (catalogue or {}).get("fields", [])[:MAX_FIELDS]:
        examples = [str(e["value"]) for e in f.get("examples", [])[:3]]
        examples, _ = redactor.redact({f["name"]: examples})
        shown = examples[f["name"]]
        if shown == "[redacted]":
            lines.append(f"- {f['name']} ({f.get('type', '?')}): [examples redacted]")
        else:
            lines.append(f"- {f['name']} ({f.get('type', '?')}): {', '.join(str(x)[:60] for x in shown)}")
    return "Fields in this tenant's logs, with example values:\n" + ("\n".join(lines) or "- (none sampled)")


def json_object(text: str) -> dict[str, Any] | None:
    """The JSON object in a model's answer: fenced, bare, or among prose."""
    body = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, re.DOTALL)
    if fenced:
        body = fenced.group(1)
    else:
        start, end = body.find("{"), body.rfind("}")
        if start >= 0 and end > start:
            body = body[start:end + 1]
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _parse(text: str) -> tuple[str | None, str]:
    data = json_object(text) or {}
    query, explanation = data.get("query"), data.get("explanation", "")
    return (query.strip() if isinstance(query, str) and query.strip() else None), str(explanation or "")


async def translate(question: str, provider, *, catalogue: dict[str, Any] | None = None,
                    redactor: Redactor | None = None, session=None, max_tokens: int = 1024) -> QueryDraft:
    """Ask the model for a query; compile it; give one repair round with the error.
    With `session` (ai.assistant.AISession) every call is audited and budgeted."""
    redactor = redactor or Redactor([])
    question, _ = redactor.redact(question)
    system = PROMPT + "\n\n" + catalogue_prompt(catalogue, redactor)
    messages = [Message(role="system", content=system), Message(role="user", content=question)]

    async def call(msgs):
        if session is not None:
            return await session.chat(msgs, max_tokens=max_tokens)
        return await provider.chat(msgs, [], max_tokens=max_tokens)

    error = "no answer"
    for attempt in range(2):
        result = await call(messages)
        query, explanation = _parse(result.text)
        if query is None:
            error = "the model's answer was not the JSON asked for"
            problem = "Your answer was not valid JSON with a 'query' field. Answer with the JSON only."
        else:
            error = compile_error(query)
            if error is None:
                used = fields_in(query)
                unknown = [f for f in used if f not in _known(catalogue)]
                return QueryDraft(query=query, explanation=explanation, valid=True, mode="ai", fields_used=used,
                                  unknown_fields=unknown)
            problem = f"That query did not compile: {error}. Fix it and answer with the JSON only."
        if attempt == 0:
            messages = messages + [Message(role="assistant", content=result.text),
                                   Message(role="user", content=problem)]
    return QueryDraft(query=None, explanation="", valid=False, mode="ai", error=error)


# -- the rule-based fallback -----------------------------------------------------------

_UNITS = {"minute": "m", "min": "m", "minutes": "m", "mins": "m", "hour": "h", "hours": "h", "hr": "h", "hrs": "h",
          "day": "d", "days": "d", "week": "w", "weeks": "w"}
_ALIASES = {"host": "host", "hosts": "host", "server": "host", "servers": "host", "machine": "host",
            "service": "service", "services": "service", "app": "service", "apps": "service",
            "level": "level", "levels": "level", "severity": "level", "status": "status", "status code": "status",
            "ip": "src_ip", "ips": "src_ip", "source ip": "src_ip", "source address": "src_ip", "address": "src_ip",
            "addresses": "src_ip", "client": "src_ip", "clients": "src_ip", "user": "user_id", "users": "user_id",
            "account": "user_id", "accounts": "user_id", "path": "path", "paths": "path", "url": "path",
            "urls": "path", "endpoint": "path", "endpoints": "path", "method": "method", "methods": "method"}
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _resolve(word: str, catalogue: dict[str, Any] | None) -> str | None:
    word = word.strip().lower()
    target = _ALIASES.get(word, word.rstrip("s"))
    names = [f["name"] for f in (catalogue or {}).get("fields", [])]
    if target in COLUMNS:
        return target
    for name in names:  # attrs.path, attrs.uri ...
        if name.split(".")[-1].lower() in (target, target + "s") and not name.startswith("ocsf."):
            return name
    if target == "path":
        for name in names:
            if name.split(".")[-1].lower() in ("uri", "url", "request_path", "route"):
                return name
    return None


def _values(catalogue: dict[str, Any] | None, field_name: str) -> list[str]:
    for f in (catalogue or {}).get("fields", []):
        if f["name"] == field_name:
            return [str(e["value"]) for e in f.get("examples", []) if isinstance(e.get("value"), str)]
    return []


def _q(value: str) -> str:
    return json.dumps(value)


def rule_based(question: str, catalogue: dict[str, Any] | None = None) -> QueryDraft:
    text = question.strip()
    low = text.lower()
    filters: list[str] = []
    said: list[str] = []
    window = None

    m = re.search(r"\b(?:last|past|previous)\s+(\d{1,4})\s*(minutes?|mins?|hours?|hrs?|days?|weeks?)\b", low)
    if m:
        n, unit = int(m.group(1)), _UNITS[m.group(2)]
        if unit == "w":
            n, unit = n * 7, "d"
        window = f"{n}{unit}"
    elif re.search(r"\b(?:last|past) (?:hour|hr)\b", low):
        window = "1h"
    elif re.search(r"\btoday\b|\blast day\b|\b24 hours\b", low):
        window = "24h"
    elif re.search(r"\b(?:this|last|past) week\b", low):
        window = "7d"
    if window:
        said.append(f"in the last {window}")

    phrase = re.search(r'"([^"]+)"', text)
    search = _q(phrase.group(1)) if phrase else None
    rest = low.replace(phrase.group(0).lower(), " ") if phrase else low

    if re.search(r"\b5\d\d\b|5xx|server errors?", rest):
        filters.append("status >= 500")
        said.append("with a server error (5xx)")
        rest = re.sub(r"\b5\d\d\b(?:\s+errors?)?|5xx(?:\s+errors?)?|server errors?", " ", rest)
    elif re.search(r"4xx|client errors?|not found|\b404s?\b", rest):
        filters.append("status >= 400 and status < 500")
        said.append("with a client error (4xx)")
        rest = re.sub(r"4xx(?:\s+errors?)?|client errors?|not found|\b404s?\b(?:\s+errors?)?", " ", rest)

    for service in sorted(_values(catalogue, "service"), key=len, reverse=True):
        if re.search(rf"(?<![\w.-]){re.escape(service.lower())}(?![\w.-])", rest):
            filters.insert(0, f"service = {_q(service)}")
            said.insert(0, f"from {service}")
            break
    # Any other value the catalogue has seen (a host, a user, a method ...)
    # becomes a filter on its field.
    taken = {f.split(" ", 1)[0] for f in filters}
    for f in (catalogue or {}).get("fields", []):
        name = f["name"]
        if name in taken or name in ("service", "level", "msg", "ts") or name.startswith("ocsf."):
            continue
        for value in _values(catalogue, name):
            if len(value) >= 3 and re.search(rf"(?<![\w.-]){re.escape(value.lower())}(?![\w.-])", rest):
                filters.append(f"{name} = {_q(value)}")
                said.append(f"where {name} is {value}")
                taken.add(name)
                rest = rest.replace(value.lower(), " ")
                break
    if re.search(r"\berrors?\b|\bfail(?:ed|ures?)?\b", rest):
        filters.append('level = "error"')
        said.append("at level error")
    elif re.search(r"\bwarn(?:ing|ings|s)?\b", rest):
        filters.append('level = "warn"')
        said.append("at level warn")
    ip = _IP.search(rest)
    if ip:
        filters.append(f"src_ip = {_q(ip.group(0))}")
        said.append(f"from {ip.group(0)}")

    group = None
    g = re.search(r"\b(?:per|by|for each|each|grouped by)\s+([a-z_ ]+?)(?=[?.,!]|$|\s+(?:in|over|during|for|from|last|past)\b)",
                  rest)
    if g:
        words = g.group(1).strip()
        if words:
            group = _resolve(words, catalogue) or next(
                (found for word in words.split() if (found := _resolve(word, catalogue))), None)
    top = re.search(r"\btop\s+(\d{1,3})\s+([a-z_ ]+?)(?=\s+(?:by|in|over|from|last|past)\b|[?.,!]|$)", rest)
    most = re.search(r"\bwhich\s+([a-z_ ]+?)\s+(?:\w+\s+){0,3}(?:the\s+)?most\b|\bmost common\s+([a-z_ ]+)", rest)
    trend = re.search(r"\bover time\b|\btrend\b|\bper (?:minute|hour|day)\b|\btimeline\b", rest)
    latest = re.search(r"\b(?:latest|last|most recent|recent)\s+(\d{1,4})\b"
                       r"(?!\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?)\b)", rest) or (
        re.search(r"\b(?:latest|most recent)\b", rest) and not window)
    count = re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", rest)

    stages: list[str] = []
    if window:
        stages.append(f"last {window}")
    if filters:
        stages.append("where " + " and ".join(filters))
    tail, how = None, ""
    if top:
        field_name = _resolve(top.group(2), catalogue)
        if field_name:
            tail, how = f"top limit={int(top.group(1))} {field_name}", f"the {top.group(1)} most common values of {field_name}"
    if tail is None and most:
        field_name = _resolve((most.group(1) or most.group(2) or "").strip(), catalogue)
        if field_name:
            tail, how = f"top limit=10 {field_name}", f"the 10 most common values of {field_name}"
    if tail is None and trend:
        tail = "timechart count()" + (f" by {group}" if group else "")
        how = "counted over time" + (f" per {group}" if group else "")
    if tail is None and group:
        tail, how = f"stats count() as count by {group}", f"counted per {group}"
    if tail is None and count:
        tail, how = "stats count() as count", "counted"
    if tail is None and latest:
        n = int(latest.group(1)) if hasattr(latest, "group") and latest.group(1) else 100
        tail, how = f"sort ts desc | head {n}", f"the latest {n}"
    if tail:
        stages.append(tail)

    if not stages and not search:
        return QueryDraft(query=None, valid=False, mode="rule_based",
                          explanation="The rule-based translator couldn't turn this question into a query. "
                                      "Try naming a service, a level, a time window or a field to group by.")
    query = (search + " | " if search else "| ") + " | ".join(stages) if stages else search
    error = compile_error(query)
    explanation = "Events" + (f" mentioning {search}" if search else "") + (
        " " + ", ".join(said) if said else "") + (f", {how}" if how else "") + "."
    return QueryDraft(query=query if error is None else None, explanation=explanation, valid=error is None,
                      mode="rule_based", error=error, fields_used=fields_in(query) if error is None else [])
