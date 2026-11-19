"""
Field catalogue (Phase 5): what fields a tenant's logs have.

build_catalogue() summarises a sample of recent rows: every top-level column
that has a value, every attrs path (flattened: attrs.http.status), and every
common-schema field (ocsf.*) that resolves for the sampled events, each with
type, presence, cardinality (exact up to a cap), example values and the
services it appears in.

top_values_sql() builds the exact top-values query for one field, with the
field rendered by the query engine (keys bound, never SQL text).
"""

from __future__ import annotations

import ipaddress
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

COLUMNS = ("service", "host", "level", "status", "src_ip", "user_id", "trace_id")
INTERNAL = {"attrs.source_format", "attrs.processing_version"}  # added by ingest, not by the sender
MAX_DEPTH = 6


def _flatten(value: Any, prefix: str, out: Dict[str, Any], depth: int = 0) -> None:
    if isinstance(value, dict) and depth < MAX_DEPTH:
        for key, inner in value.items():
            _flatten(inner, f"{prefix}.{key}", out, depth + 1)
    else:
        out[prefix] = value


def _type_of(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, datetime):
        return "timestamp"
    text = str(value)
    try:
        ipaddress.ip_address(text)
        return "ip"
    except ValueError:
        return "string"


def _hashable(value: Any) -> Any:
    return json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list)) else value


def _event(row: Dict[str, Any]) -> Dict[str, Any]:
    attrs = row.get("attrs")
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs or "{}")
        except ValueError:
            attrs = {}
    return {**row, "attrs": attrs if isinstance(attrs, dict) else {}}


def build_catalogue(rows: Iterable[Dict[str, Any]], max_distinct: int = 500, examples: int = 5) -> Dict[str, Any]:
    import ocsf_schema

    present: Counter = Counter()
    values: Dict[str, Counter] = defaultdict(Counter)
    types: Dict[str, Counter] = defaultdict(Counter)
    services: Dict[str, Counter] = defaultdict(Counter)
    capped: Dict[str, bool] = {}
    total = 0
    for raw in rows:
        total += 1
        event = _event(raw)
        service = str(event.get("service") or "")
        fields: Dict[str, Any] = {}
        for column in COLUMNS:
            if event.get(column) not in (None, "", 0) or (column == "status" and event.get(column)):
                fields[column] = event[column]
        _flatten(event["attrs"], "attrs", fields)
        fields.pop("attrs", None)  # an empty attrs object
        for name in INTERNAL:
            fields.pop(name, None)
        for entry in ocsf_schema.MAPPING:
            value = ocsf_schema.resolve(event, entry["ocsf"])
            if value not in (None, ""):
                fields[f"ocsf.{entry['ocsf']}"] = value
        for name, value in fields.items():
            if value in (None, ""):
                continue
            present[name] += 1
            types[name][_type_of(value)] += 1
            services[name][service] += 1
            key = _hashable(value)
            if key in values[name] or len(values[name]) < max_distinct:
                values[name][key] += 1
            else:
                capped[name] = True
    catalogue = []
    for name, count in present.items():
        counter = values[name]
        catalogue.append({
            "name": name,
            "type": types[name].most_common(1)[0][0],
            "schema": name.startswith("ocsf."),
            "present": count,
            "presence_pct": round(100.0 * count / total, 1) if total else 0.0,
            "cardinality": len(counter),
            "cardinality_capped": capped.get(name, False),
            "examples": [{"value": v, "count": c} for v, c in counter.most_common(examples)],
            "services": [s for s, _ in services[name].most_common(5) if s],
        })
    catalogue.sort(key=lambda f: (f["schema"], -f["present"], f["name"]))
    return {"sampled_events": total, "fields": catalogue}


def top_values_sql(tenant_id: str, field: str, start: datetime, end: datetime, service: Optional[str] = None,
                   limit: int = 10) -> Tuple[str, Dict[str, Any]]:
    """Exact top values of one field (and the total/distinct query)."""
    from query_engine import _EXTRACTED, _FIELD_PARAMS, field_sql

    params: Dict[str, Any] = {"tenant_id": tenant_id, "start": start, "end": end, "limit": int(limit)}
    token, extracted = _FIELD_PARAMS.set(params), _EXTRACTED.set({})
    try:
        expr = field_sql(field)
    finally:
        _EXTRACTED.reset(extracted)
        _FIELD_PARAMS.reset(token)
    where = "customer_id = %(tenant_id)s AND ts >= %(start)s AND ts <= %(end)s"
    if service:
        where += " AND service = %(service)s"
        params["service"] = service
    sql = (f"SELECT toString({expr}) AS value, count() AS count FROM logs_raw_mt WHERE {where} "
           f"AND isNotNull({expr}) AND toString({expr}) != '' GROUP BY value ORDER BY count DESC LIMIT %(limit)s")
    return sql, params


def totals_sql(tenant_id: str, field: str, start: datetime, end: datetime, service: Optional[str] = None
               ) -> Tuple[str, Dict[str, Any]]:
    sql, params = top_values_sql(tenant_id, field, start, end, service)
    expr_sql = sql[len("SELECT toString("):sql.index(") AS value")]
    where = sql[sql.index(" WHERE ") + len(" WHERE "):sql.index(" GROUP BY")]
    return (f"SELECT count() AS total, uniq(toString({expr_sql})) AS distinct FROM logs_raw_mt WHERE {where}", params)
