"""
Grounding tools (Phase 8): the only way a model sees tenant data.

Each tool is read-only and stands for one HTTP request a person could make
(`endpoint`). Before it runs, the caller's own roles are checked for the
permission that request needs, in the caller's tenant, with the same
functions the API middleware uses; so a model can never read more than the
person asking could. Tools return bounded results (MAX_ROWS rows, long text
cut) and `refs`: the events, alerts, cases, indicators and query results
the output contains, which the orchestrator turns into citations. Output
dicts mark what each part came from with `ref` (an index into `refs`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException

from .providers import ToolSpec

MAX_ROWS = 50
MAX_TEXT = 2000
SINCE = re.compile(r"^\d{1,4}[mhd]$")


class ToolError(Exception):
    """A tool call that could not run; its message goes back to the model."""


@dataclass
class ToolContext:
    tenant_id: str
    user_id: str
    roles: list[dict[str, Any]]


@dataclass
class Ref:
    kind: str  # query | event | alert | case | indicator
    label: str
    link: str
    key: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    data: dict[str, Any]
    refs: list[Ref]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    endpoint: tuple[str, str]  # the request this tool stands for: (method, path)
    run: Callable[[ToolContext, dict[str, Any]], Awaitable[ToolOutput]]

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, input_schema=self.input_schema)


# -- data access (patched in tests) ---------------------------------------------------

async def _logql(body: dict[str, Any], customer_id: str) -> dict[str, Any]:
    from routers.query import logql_query

    return await logql_query(body, customer_id)


async def _alert(alert_id: str, tenant_id: str) -> dict[str, Any] | None:
    from dao.security_dao import SecurityDAO

    return await SecurityDAO().get_security_event_by_id(alert_id, tenant_id)


async def _case(case_id: str, tenant_id: str) -> dict[str, Any]:
    from cases import CaseError
    from services.case_service import CaseNotFound, CaseService

    try:
        return await CaseService().details(tenant_id, case_id)
    except CaseNotFound:
        raise ToolError(f"case {case_id} not found") from None
    except CaseError as e:
        raise ToolError(str(e)) from None


async def _indicators(value: str, tenant_id: str) -> list[dict[str, Any]]:
    from threat_feeds import clean
    from threat_intel_store import ThreatIntelDAO

    cleaned = clean(value, None)
    if cleaned is None:
        raise ToolError(f"{value!r} is not an indicator (IP, domain, URL or hash)")
    kind, normal = cleaned
    dao = ThreatIntelDAO()
    rows, _ = await dao.search_indicators(tenant_id, q=normal, indicator_type=kind, limit=10, offset=0)
    rows = [r for r in rows if r.get("value") == normal]
    seen = await dao.seen_counts(tenant_id, [(r["indicator_type"], r["value"]) for r in rows])
    return [{**r, "seen_7d": seen.get((r["indicator_type"], r["value"]), 0)} for r in rows]


# -- helpers ----------------------------------------------------------------------

def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT] + "…"
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if k not in ("tenant_id", "customer_id")}
    if isinstance(value, list):
        return [_plain(v) for v in value[:MAX_ROWS]]
    return value


def _logs_link(query: str, since: str | None = None, start: str | None = None,
               end: str | None = None) -> str:
    params = {"q": query}
    if since:
        params["since"] = since
    if start:
        params["from"] = start
    if end:
        params["to"] = end
    return "/observability/logs?" + urlencode(params)


def _event_window(ts: str) -> tuple[str | None, str | None]:
    try:
        moment = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None, None
    return (moment - timedelta(seconds=1)).isoformat(), (moment + timedelta(seconds=1)).isoformat()


def _quote(value: Any) -> str:
    return json.dumps(str(value))


# -- the tools ---------------------------------------------------------------------

async def run_query(ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
    query, since = args["query"], args.get("since") or "1h"
    body = {"query": query, "since": since}
    try:
        result = await _logql(body, ctx.tenant_id)
    except HTTPException as e:
        raise ToolError(f"query failed: {e.detail}") from None
    rows = result.get("logs") or []
    refs = [Ref(kind="query", label=query if len(query) <= 120 else query[:117] + "…",
                link=_logs_link(query, since=since), key={"query": query, "since": since})]
    out_rows = []
    for row in rows[:MAX_ROWS]:
        row = _plain(row)
        if "ts" in row and "msg" in row:  # an event, not an aggregate row
            start, end = _event_window(row["ts"])
            narrowed = " and ".join(f"{f} = {_quote(row[f])}" for f in ("service", "host") if row.get(f))
            refs.append(Ref(kind="event", label=f"{row.get('service', '')} {row['ts']}".strip(),
                            link=_logs_link(f"| where {narrowed}" if narrowed else "*", start=start, end=end),
                            key={k: row.get(k) for k in ("ts", "service", "host")}))
            row = {**row, "ref": len(refs) - 1}
        out_rows.append(row)
    data = {"ref": 0, "rows": out_rows, "total_count": result.get("total_count", len(rows)),
            "truncated": len(rows) > MAX_ROWS or bool(result.get("truncated")),
            "time_range": result.get("time_range")}
    if result.get("columns"):
        data["columns"] = result["columns"]
    return ToolOutput(data=data, refs=refs)


async def get_alert(ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
    row = await _alert(args["alert_id"], ctx.tenant_id)
    if not row:
        raise ToolError(f"alert {args['alert_id']} not found")
    data = _plain(row)
    data["ref"] = 0
    return ToolOutput(data=data, refs=[Ref(kind="alert", label=str(row.get("title") or row.get("rule_id") or row["id"]),
                                           link=f"/security/events?alert={row['id']}", key={"id": row["id"]})])


async def get_case(ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
    details = await _case(args["case_id"], ctx.tenant_id)
    case = details.get("case") or {}
    case_id = case.get("id", args["case_id"])
    refs = [Ref(kind="case", label=str(case.get("title") or case_id), link=f"/security/cases/{case_id}",
                key={"id": case_id})]
    alerts = []
    for alert in (details.get("alerts") or [])[:MAX_ROWS]:
        alert = _plain(alert)
        if alert.get("id") and not alert.get("missing"):
            refs.append(Ref(kind="alert", label=str(alert.get("title") or alert["id"]),
                            link=f"/security/events?alert={alert['id']}", key={"id": alert["id"]}))
            alert = {**alert, "ref": len(refs) - 1}
        alerts.append(alert)
    return ToolOutput(data={"ref": 0, "case": _plain(case), "alerts": alerts,
                            "timeline": _plain((details.get("timeline") or [])[-MAX_ROWS:])}, refs=refs)


async def lookup_indicator(ctx: ToolContext, args: dict[str, Any]) -> ToolOutput:
    matches = await _indicators(args["value"], ctx.tenant_id)
    refs, out = [], []
    for match in matches[:MAX_ROWS]:
        match = _plain(match)
        refs.append(Ref(kind="indicator", label=f"{match.get('indicator_type')} {match.get('value')}",
                        link="/security/threat-intel?" + urlencode({"q": match.get("value", "")}),
                        key={"type": match.get("indicator_type"), "value": match.get("value")}))
        out.append({**match, "ref": len(refs) - 1})
    return ToolOutput(data={"value": args["value"], "matches": out,
                            "note": None if out else "not in this tenant's threat intelligence"}, refs=refs)


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("run_query",
         "Run a read-only LogforgeQL query over this tenant's logs and return up to 50 rows. Use pipeline stages "
         "(| where, | stats ... by, | timechart, | top, | sort, | head) to aggregate rather than reading raw events.",
         _schema({"query": {"type": "string", "description": "LogforgeQL, e.g. '| where service = \"sshd\" | "
                                                             "stats count() by src_ip | sort -count | head 10'"},
                  "since": {"type": "string", "description": "How far back: 15m, 24h, 7d (default 1h)"}},
                 ["query"]),
         ("POST", "/v1/query/logql"), run_query),
    Tool("get_alert", "Fetch one security alert (detection) by id: rule, severity, time and the event that raised it.",
         _schema({"alert_id": {"type": "string"}}, ["alert_id"]),
         ("GET", "/v1/security/events/{id}"), get_alert),
    Tool("get_case", "Fetch an investigation case by id: its status, its alerts and its timeline.",
         _schema({"case_id": {"type": "string"}}, ["case_id"]),
         ("GET", "/v1/security/cases/{id}"), get_case),
    Tool("lookup_indicator",
         "Look up an IP, domain, URL or file hash in this tenant's threat intelligence, with how often it was "
         "seen in the last 7 days.",
         _schema({"value": {"type": "string"}}, ["value"]),
         ("GET", "/v1/security/intel/indicators"), lookup_indicator),
]}


def tool_specs() -> list[ToolSpec]:
    return [t.spec() for t in TOOLS.values()]


def required_permission(tool: Tool) -> str:
    from authn_authz_middleware import get_endpoint_permission

    return get_endpoint_permission(tool.endpoint[1], tool.endpoint[0])


def _check_args(tool: Tool, args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolError(f"{tool.name}: arguments must be an object")
    props = tool.input_schema["properties"]
    unexpected = sorted(set(args) - set(props))
    if unexpected:
        raise ToolError(f"{tool.name}: unexpected argument(s) {', '.join(unexpected)}")
    for name in tool.input_schema["required"]:
        if not isinstance(args.get(name), str) or not args[name].strip():
            raise ToolError(f"{tool.name}: '{name}' is required")
    for name, value in args.items():
        if value is not None and not isinstance(value, str):
            raise ToolError(f"{tool.name}: '{name}' must be a string")
        if isinstance(value, str) and len(value) > 4000:
            raise ToolError(f"{tool.name}: '{name}' is too long")
    if tool.name == "run_query" and args.get("since") and not SINCE.match(args["since"]):
        raise ToolError("run_query: 'since' must look like 15m, 24h or 7d")
    return args


async def execute(name: str, args: Any, ctx: ToolContext) -> ToolOutput:
    from authn_authz_middleware import check_permission

    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"unknown tool {name!r}; available: {', '.join(TOOLS)}")
    args = _check_args(tool, args)
    permission = required_permission(tool)
    try:
        allowed = check_permission(ctx.roles, permission, ctx.tenant_id)
    except ValueError:
        allowed = False
    if not allowed:
        raise ToolError(f"{name}: not permitted (the person asking lacks {permission})")
    return await tool.run(ctx, args)
