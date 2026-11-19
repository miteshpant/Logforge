"""
Dashboards from queries (Phase 6).

A dashboard widget whose query_definition is {"logql": "<query>"} is a query
panel. It runs over the dashboard's time range with the dashboard's
variables bound as values (logql_pipeline binds every variable; nothing is
pasted into the query text), and its result is shaped for the widget type:

  metric / stat / gauge  {"value", "formatted_value", "label"}: the first
                         numeric value of the first row
  table                  {"columns", "rows"}
  *_chart                {"labels", "series": [{"name", "data"}]}: labels
                         from the first text or time column; a timechart
                         split by a field becomes one series per value

Every shape also carries the raw result under "result".

Variables (stored with the dashboard):

  {"name", "label"?, "type": "custom" | "query" | "text",
   "values"? (custom), "query"? (query: its first column gives the options),
   "default"?, "include_all"?}

"*" means All (logql_pipeline.ALL): a comparison with it is true for every
row.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import logql_pipeline as lp

logger = logging.getLogger(__name__)

ALL_TOKEN = "*"
MAX_VARIABLES = 20
MAX_OPTIONS = 500
CHART_TYPES = {"line_chart", "bar_chart", "area_chart", "pie_chart"}
STAT_TYPES = {"metric", "stat", "gauge"}
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class VariableError(ValueError):
    """Invalid variable definitions or values. The message is shown to the user."""


def validate_variables(defs: Any) -> List[Dict[str, Any]]:
    if defs is None:
        return []
    if not isinstance(defs, list) or len(defs) > MAX_VARIABLES:
        raise VariableError(f"variables must be a list (at most {MAX_VARIABLES})")
    out, seen = [], set()
    for raw in defs:
        if not isinstance(raw, dict):
            raise VariableError("each variable must be an object")
        name = raw.get("name")
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise VariableError(f"variable name {name!r} must be letters, digits and _")
        if name in seen:
            raise VariableError(f"variable {name} is defined twice")
        seen.add(name)
        kind = raw.get("type", "custom")
        if kind not in ("custom", "query", "text"):
            raise VariableError(f"variable {name}: type must be custom, query or text")
        include_all = bool(raw.get("include_all", False))
        var: Dict[str, Any] = {"name": name, "label": str(raw.get("label") or name)[:100], "type": kind,
                               "include_all": include_all}
        if kind == "custom":
            values = raw.get("values")
            if not isinstance(values, list) or not values or len(values) > MAX_OPTIONS or \
                    not all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in values):
                raise VariableError(f"variable {name}: values must be a non-empty list of values")
            var["values"] = [str(v) for v in values]
        if kind == "query":
            query = raw.get("query")
            if not isinstance(query, str) or not query.strip():
                raise VariableError(f"variable {name}: a query variable needs a query")
            var["query"] = query
        default = raw.get("default", ALL_TOKEN if include_all else (var.get("values") or [""])[0])
        default = "" if default is None else str(default)
        if default == ALL_TOKEN and not include_all:
            raise VariableError(f"variable {name}: default * (All) needs include_all")
        if kind == "custom" and default not in var["values"] and default != ALL_TOKEN:
            raise VariableError(f"variable {name}: default must be one of its values")
        var["default"] = default
        out.append(var)
    return out


def resolve(defs: List[Dict[str, Any]], requested: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """name -> value for the compiler (lp.ALL for All)."""
    requested = requested or {}
    values: Dict[str, Any] = {}
    for var in defs:
        name = var["name"]
        value = requested.get(name, var["default"])
        value = "" if value is None else str(value)
        if len(value) > 500:
            raise VariableError(f"{name} is too long")
        if value == ALL_TOKEN:
            if not var["include_all"]:
                raise VariableError(f"{name} does not offer All")
            values[name] = lp.ALL
            continue
        if var["type"] == "custom" and value not in var["values"]:
            raise VariableError(f"{name} must be one of {', '.join(var['values'])}")
        values[name] = value
    return values


async def _execute(query: str, tenant_id: str, start: datetime, end: datetime,
                   variables: Dict[str, Any]) -> Dict[str, Any]:
    from routers.query import execute_pipeline_text

    return await execute_pipeline_text(query, tenant_id, start, end, variables)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _label(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else ("" if value is None else str(value))


def shape(widget_type: str, result: Dict[str, Any]) -> Dict[str, Any]:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0]) if rows else [])
    raw = {"columns": columns, "rows": rows, "result_type": result.get("result_type"),
           "truncated": bool(result.get("truncated"))}
    if widget_type in STAT_TYPES:
        value, label = None, None
        if rows:
            for column in columns:
                if _is_number(rows[0].get(column)):
                    value, label = rows[0][column], column
                    break
        formatted = None if value is None else (f"{value:,}" if isinstance(value, int) else f"{value:,.2f}".rstrip("0")
                                                .rstrip("."))
        return {"value": value, "formatted_value": formatted, "label": label, "result": raw}
    if widget_type in CHART_TYPES:
        numeric = [c for c in columns if any(_is_number(r.get(c)) for r in rows)]
        text = [c for c in columns if c not in numeric]
        if not rows or not numeric:
            return {"labels": [], "series": [], "result": raw}
        label_col = "_time" if "_time" in columns else (text[0] if text else None)
        split = [c for c in text if c != label_col]
        labels: List[str] = []
        for r in rows:
            lab = _label(r.get(label_col)) if label_col else str(len(labels))
            if lab not in labels:
                labels.append(lab)
        if split and len(numeric) == 1:
            # long format (timechart ... by f): one series per value of f
            by, metric = split[0], numeric[0]
            names: List[str] = []
            points: Dict[tuple, float] = {}
            for r in rows:
                name = _label(r.get(by))
                if name not in names:
                    names.append(name)
                points[(name, _label(r.get(label_col)))] = r.get(metric) or 0
            series = [{"name": n, "data": [points.get((n, lab), 0) for lab in labels]} for n in names]
        else:
            by_label = {(_label(r.get(label_col)) if label_col else str(i)): r for i, r in enumerate(rows)}
            series = [{"name": c, "data": [(by_label[lab].get(c) or 0) for lab in labels]} for c in numeric]
        return {"labels": labels, "series": series, "result": raw}
    return {"columns": columns, "rows": rows, "result": raw}


async def panel_data(widget: Dict[str, Any], tenant_id: str, start: datetime, end: datetime,
                     variables: Dict[str, Any]) -> Dict[str, Any]:
    from fastapi import HTTPException

    query = (widget.get("query_definition") or {}).get("logql")
    try:
        result = await _execute(query, tenant_id, start, end, variables)
    except HTTPException as e:
        return {"error": str(e.detail)}
    except Exception as e:
        logger.error(f"Query panel {widget.get('id')} failed: {e}")
        return {"error": "The panel's query failed; see the API logs"}
    return shape(widget.get("type", "table"), result)


async def options(defs: List[Dict[str, Any]], tenant_id: str, start: datetime, end: datetime) -> Dict[str, List[str]]:
    """The values each variable offers ("*" first when it includes All)."""
    found: Dict[str, List[str]] = {}
    for var in defs:
        values: List[str] = []
        if var["type"] == "custom":
            values = list(var["values"])
        elif var["type"] == "query":
            try:
                result = await _execute(var["query"], tenant_id, start, end, {})
                column = (result.get("columns") or [None])[0]
                values = sorted({_label(r.get(column)) for r in result.get("rows") or []
                                 if r.get(column) not in (None, "")})[:MAX_OPTIONS]
            except Exception as e:
                logger.warning(f"Options query for variable {var['name']} failed: {e}")
        found[var["name"]] = ([ALL_TOKEN] if var["include_all"] else []) + values
    return found
