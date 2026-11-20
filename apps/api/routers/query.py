"""
Advanced query API endpoints - M2 core functionality
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from models import QueryResponse
from query_engine import (
    AdvancedQueryEngine,
    AdvancedQueryRequest,
    AggregationType,
    QueryAggregation,
    QueryFieldError,
    QueryFilter,
    QueryOperator,
)
from storage_config import get_customer_id
from tenant_dependencies import MiddlewareTenant
from services.query_service import QueryService
from error_handling import internal_error

router = APIRouter(prefix="/v1")

# Global instances (will be injected)
query_engine = None
clickhouse_client = None

# ENH-033/ENH-010: `QueryService()` opens a database connection in its
# constructor, so building it here connected during `import routers.query` --
# making this router, and the request-building logic in it, untestable without
# live infrastructure. Built on first use instead.
_query_service_instance: Optional[QueryService] = None


def get_query_service() -> QueryService:
    """Get the shared QueryService, constructing it on first use."""
    global _query_service_instance
    if _query_service_instance is None:
        _query_service_instance = QueryService()
    return _query_service_instance


def __getattr__(name: str):
    """Preserve the module-level `query_service` name (PEP 562)."""
    if name == "query_service":
        return get_query_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def setup_dependencies(qe, client):
    """Setup dependencies from main app"""
    global query_engine, clickhouse_client
    query_engine = qe
    clickhouse_client = client

# ---------------------------------------------------------------------------
# LF-017 / LF-022: shared default time window.
#
# Endpoints must NEVER run unbounded over the log tables: without a `ts`
# predicate ClickHouse reads every monthly partition for the tenant before
# applying LIMIT. When the caller supplies no range, default to the last hour
# (the Loki/Datadog convention), and reject windows wider than
# LOGFORGE_MAX_QUERY_WINDOW_DAYS (default 31) with a clear 400 instead of a
# slow success. The effective window is echoed in every response so the UI
# can display "showing last 1 hour".
# ---------------------------------------------------------------------------

DEFAULT_QUERY_WINDOW = timedelta(hours=1)

_RELATIVE_RANGE_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$")
_RELATIVE_UNITS = {
    "s": timedelta(seconds=1),
    "m": timedelta(minutes=1),
    "h": timedelta(hours=1),
    "d": timedelta(days=1),
    "w": timedelta(weeks=1),
}


def _max_query_window() -> timedelta:
    return timedelta(days=int(os.getenv("LOGFORGE_MAX_QUERY_WINDOW_DAYS", "31")))


def _coerce_datetime(value: Any, field_name: str) -> datetime:
    """Parse a datetime from a datetime or ISO-8601 string; always tz-aware UTC."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {field_name}: {value!r} is not an ISO-8601 datetime",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}: expected an ISO-8601 datetime",
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_since(value: str) -> timedelta:
    """Parse a relative range like '15m', '24h', '7d' (LF-022)."""
    match = _RELATIVE_RANGE_RE.match(value or "")
    if not match:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid 'since' value {value!r}. "
                "Expected <number><unit> with unit one of s, m, h, d, w (e.g. '15m', '24h', '7d')."
            ),
        )
    return int(match.group(1)) * _RELATIVE_UNITS[match.group(2)]


def logql_window(payload: Dict[str, Any], request_body: Dict[str, Any],
                 max_window: Optional[timedelta] = None) -> Tuple[datetime, datetime]:
    """The window a LogforgeQL query scans. An explicit range in the request
    body wins; otherwise the query's own `| last <duration>`; otherwise the
    last hour (LF-022). Every path goes through the max-window guard."""
    if any(request_body.get(k) is not None for k in ("start_time", "end_time", "since")):
        return resolve_time_window(start_time=request_body.get("start_time"), end_time=request_body.get("end_time"),
                                   since=request_body.get("since"), max_window=max_window)
    return resolve_time_window(start_time=payload.get("start_time"), end_time=payload.get("end_time"),
                               max_window=max_window)


def resolve_time_window(
    start_time: Any = None,
    end_time: Any = None,
    since: Optional[str] = None,
    max_window: Optional[timedelta] = None,
) -> Tuple[datetime, datetime]:
    """
    Resolve the effective [start, end] query window.

    * Missing end -> now.
    * Missing start -> end - since (when given) else end - 1h.
    * start >= end, or a window wider than the configured maximum -> 400.
    """
    now = datetime.now(timezone.utc)
    end = _coerce_datetime(end_time, "end_time") if end_time is not None else now
    if start_time is not None:
        start = _coerce_datetime(start_time, "start_time")
    elif since is not None:
        start = end - _parse_since(since)
    else:
        start = end - DEFAULT_QUERY_WINDOW

    if start >= end:
        raise HTTPException(
            status_code=400, detail="start_time must be before end_time"
        )

    limit_name = "LOGFORGE_MAX_ARCHIVE_WINDOW_DAYS" if max_window else "LOGFORGE_MAX_QUERY_WINDOW_DAYS"
    max_window = max_window or _max_query_window()
    if end - start > max_window:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested time range of {(end - start).days} days exceeds the "
                f"maximum of {max_window.days} days "
                f"({limit_name}). Narrow the range."
            ),
        )
    return start, end


def _time_range_payload(start: datetime, end: datetime) -> Dict[str, str]:
    """The effective window, echoed in responses (LF-017/LF-022)."""
    return {"start_time": start.isoformat(), "end_time": end.isoformat()}


# Define TimeseriesQueryRequest model here since it's query-specific
class TimeseriesQueryRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    interval: str = "1h"  # 1m, 5m, 15m, 30m, 1h, 6h, 12h, 24h
    metrics: List[str] = []  # Optional, can be derived from aggregations
    filters: List[Dict[str, Any]] = []
    group_by: List[str] = []
    aggregations: List[Dict[str, Any]] = []  # For M2 compatibility
    granularity: str = "hour"  # For M2 compatibility


def build_query_request(
    query_data: Dict[str, Any], customer_id: str
) -> AdvancedQueryRequest:
    """
    Build a validated `AdvancedQueryRequest` from a raw request dict, with the
    tenant-isolation filter applied.

    ENH-033: three endpoints passed raw dicts straight to
    `query_engine.execute_query()`, which expects an `AdvancedQueryRequest`.
    That raised `AttributeError: 'dict' object has no attribute 'filters'` and
    always had -- the failure was invisible because `execute_query` caught every
    exception and returned an empty result set, so clients saw a valid-looking
    "no data" response instead of an error.

    The tenant filter is appended HERE, after the caller's own filters, so it
    cannot be omitted by a caller-supplied payload.

    Raises:
        HTTPException(400): if the payload is not a valid query.
    """
    payload = dict(query_data or {})

    raw_filters = list(payload.get("filters") or [])
    # Tenant isolation is non-negotiable and always appended last.
    raw_filters.append(
        {"field": "customer_id", "operator": "eq", "value": customer_id}
    )

    try:
        filters = [
            f if isinstance(f, QueryFilter) else QueryFilter(
                field=f["field"],
                operator=QueryOperator(f["operator"]),
                value=f["value"],
            )
            for f in raw_filters
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid filter: {exc}")

    try:
        # `QueryAggregation` is a plain dataclass, so it does NOT validate its
        # own `type`. Coercing through the enum here means an unknown
        # aggregation is rejected with a 400 instead of silently degrading to
        # `count()` and returning a number the caller never asked for.
        aggregations = [
            a if isinstance(a, QueryAggregation) else QueryAggregation(
                type=AggregationType(a["type"]),
                field=a.get("field", "*"),
                alias=a.get("alias"),
                percentile_value=a.get("percentile_value"),
            )
            for a in (payload.get("aggregations") or [])
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid aggregation: {exc}")

    fields = {
        key: payload[key]
        for key in (
            "start_time", "end_time", "text_search", "group_by", "time_series",
            "time_granularity", "sort_field", "sort_order", "limit", "offset",
            "include_fields", "exclude_fields", "timeout_seconds", "extractions",
        )
        if key in payload and payload[key] is not None
    }

    try:
        return AdvancedQueryRequest(
            filters=filters, aggregations=aggregations, **fields
        )
    except Exception as exc:
        # Pydantic validation error -> 400, never a 500 and never a silent
        # empty result.
        raise HTTPException(status_code=400, detail=f"Invalid query: {exc}")


# Advanced Query Engine Endpoints (M2 Core)

@router.post("/query/advanced", response_model=QueryResponse)
async def advanced_query_logs(query_request: AdvancedQueryRequest, customer_id: str = MiddlewareTenant):
    """Advanced log querying with filters, aggregations, and analysis"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        # Add customer_id filter to ensure multi-tenant isolation
        if not query_request.filters:
            query_request.filters = []
        query_request.filters.append(QueryFilter(
            field="customer_id",
            operator=QueryOperator.EQ,
            value=customer_id
        ))
        
        # Check cache first
        query_dict = query_request.model_dump(mode='json')
        cached_result = await get_query_service().get_cached_result(query_dict, customer_id)
        
        if cached_result:
            # Return cached result as QueryResponse
            return QueryResponse(
                logs=cached_result.get('logs', []),
                total_count=cached_result.get('total_count', 0),
                aggregations=cached_result.get('aggregations', {}),
                execution_time_ms=cached_result.get('execution_time_ms', 0),
                customer_id=customer_id
            )
        
        # Execute advanced query
        result = await query_engine.execute_query(query_request)
        
        # Cache the result for future use (5 minutes TTL)
        await get_query_service().cache_query_result(
            query_data=query_dict,
            customer_id=customer_id,
            result=result.model_dump(mode='json'),
            ttl_seconds=300
        )
        
        # result is already a QueryResponse object, just return it
        result.customer_id = customer_id
        return result
        
    except HTTPException:
        raise
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Advanced query failed")

@router.post("/query/logql")
async def logql_query(
    request_body: Dict[str, Any], customer_id: str = MiddlewareTenant
):
    """
    Execute a LogforgeQL text query (ENH-028).

    Examples:
        {"query": "error | where service = \\"api\\" | limit 100"}
        {"query": "error | limit 50", "since": "24h"}
        {"query": "error", "start_time": "2026-08-15T00:00:00Z",
         "end_time": "2026-08-15T06:00:00Z"}

    LF-022: when no time range is supplied, the query runs over the last hour
    (the effective window is echoed back as `time_range`). A relative range
    can be given as `"since": "15m" | "24h" | "7d"`. Ranges wider than
    LOGFORGE_MAX_QUERY_WINDOW_DAYS (default 31) are rejected with a 400.

    The query compiles to an `AdvancedQueryRequest` and is executed by the
    parameterised builder, so it can never become an injection surface, and the
    tenant filter is applied by `build_query_request` exactly as for every other
    endpoint.
    """
    from logql import LogQLSyntaxError, compile_to_request_payload
    from logql_pipeline import uses_pipeline

    query_text = request_body.get("query")
    if not query_text or not isinstance(query_text, str):
        raise HTTPException(status_code=400, detail="A 'query' string is required")

    source = request_body.get("source", "events")
    if source == "archive":
        return await run_archive_query(query_text, request_body, customer_id)
    if source != "events":
        raise HTTPException(status_code=400, detail="source must be 'events' or 'archive'")
    if uses_pipeline(query_text):
        return await run_pipeline_query(query_text, request_body, customer_id)

    try:
        payload = compile_to_request_payload(query_text)
    except (LogQLSyntaxError, QueryFieldError) as exc:
        # A syntax error is a user error: explain it rather than returning a
        # confusing 500 or an empty result set.
        raise HTTPException(status_code=400, detail=str(exc))

    start, end = logql_window(payload, request_body)
    payload["start_time"] = start
    payload["end_time"] = end

    try:
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")

        query_request = build_query_request(payload, customer_id)
        result = await query_engine.execute_query(query_request)

        result.customer_id = customer_id
        response = result.model_dump(mode="json")
        # LF-022: echo the effective window so callers see what was scanned.
        response["time_range"] = _time_range_payload(start, end)
        return response

    except HTTPException:
        raise
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "LogQL query failed")


PIPELINE_QUERY_TIMEOUT_SECONDS = int(os.getenv("LOGFORGE_PIPELINE_QUERY_TIMEOUT_SECONDS", "30"))


def _check_variables(variables: Any) -> Dict[str, Any]:
    """Dashboard / caller variables: name -> string, number, bool or a list of them."""
    if variables is None:
        return {}
    if not isinstance(variables, dict) or len(variables) > 50:
        raise HTTPException(status_code=400, detail="'variables' must be an object (at most 50 entries)")
    scalar = (str, int, float, bool)
    for name, value in variables.items():
        if not isinstance(name, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$", name):
            raise HTTPException(status_code=400, detail=f"invalid variable name: {name!r}")
        ok = value is None or isinstance(value, scalar) or (
            isinstance(value, list) and len(value) <= 1000 and all(isinstance(v, scalar) for v in value))
        if not ok:
            raise HTTPException(status_code=400, detail=f"variable ${name} must be a value or a list of values")
    return variables


async def _lookup_metas(customer_id: str, query_text: str) -> Dict[str, Any]:
    """The tenant's lookup tables, loaded only when the query uses one."""
    if not re.search(r"\b(lookup|inlookup)\b", query_text, re.IGNORECASE):
        return {}
    import lookup_tables
    from logql_pipeline import LookupMeta

    try:
        tables = await lookup_tables.LookupDAO().list(customer_id)
    except Exception as e:
        raise internal_error(e, "Failed to load lookup tables")
    return {t.name: LookupMeta(name=t.name, version=t.version, columns=t.columns, key=t.key) for t in tables}


async def execute_pipeline_text(query_text: str, customer_id: str, start: datetime, end: datetime,
                                variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compile a pipeline query and run it: {"rows", "columns", "result_type", "truncated"}.

    The tenant is bound into the innermost SELECT by the compiler, so no stage
    can widen it. The statement runs read-only, with a time limit. Compile
    errors are 400s; database errors propagate (callers decide how to report).
    """
    import asyncio

    from logql_pipeline import PipelineError, compile_pipeline, execute

    import pattern_query

    try:
        patterns = pattern_query.split(query_text)
    except pattern_query.PatternQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if patterns:
        base, mode = patterns
        lookups = await _lookup_metas(customer_id, base)
        try:
            compile_pipeline(pattern_query.lines_query(base, 1), customer_id=customer_id, start=start, end=end,
                             lookups=lookups)
        except (PipelineError, QueryFieldError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        settings = {"readonly": 2, "max_execution_time": PIPELINE_QUERY_TIMEOUT_SECONDS,
                    "max_bytes_to_read": AdvancedQueryEngine.DEFAULT_MAX_BYTES_TO_READ}
        result = await asyncio.to_thread(pattern_query.run, query_engine.client, base, mode, customer_id, start, end,
                                         settings, lookups)
        return {**result, "estimated_rows": None, "rollup": False}

    lookups = await _lookup_metas(customer_id, query_text)
    try:
        compiled = compile_pipeline(query_text, customer_id=customer_id, start=start, end=end,
                                    variables=variables or {}, lookups=lookups)
    except (PipelineError, QueryFieldError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not query_engine:
        raise HTTPException(status_code=500, detail="Query engine not initialized")
    import query_cost

    estimated = await asyncio.to_thread(query_cost.estimate_rows, query_engine.client, compiled.sql, compiled.params)
    try:
        query_cost.check(estimated, await query_cost.tier_for(customer_id))
    except query_cost.QueryTooExpensive as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = {
        "readonly": 2,
        "max_execution_time": PIPELINE_QUERY_TIMEOUT_SECONDS,
        "max_bytes_to_read": AdvancedQueryEngine.DEFAULT_MAX_BYTES_TO_READ,
    }
    result = await asyncio.to_thread(execute, query_engine.client, compiled, settings)
    return {**result, "estimated_rows": estimated, "rollup": compiled.rollup}


async def validate_pipeline_text(query_text: str, customer_id: str,
                                 variables: Optional[Dict[str, Any]] = None) -> None:
    """Raise ValueError (the message is for the user) if the query does not compile."""
    from logql_pipeline import PipelineError, compile_pipeline

    import pattern_query

    try:
        patterns = pattern_query.split(query_text)
    except pattern_query.PatternQueryError as exc:
        raise ValueError(str(exc)) from None
    if patterns:
        query_text = pattern_query.lines_query(patterns[0], 1)
    lookups = await _lookup_metas(customer_id, query_text)
    end = datetime.now(timezone.utc)
    try:
        compile_pipeline(query_text, customer_id=customer_id, start=end - timedelta(hours=1), end=end,
                         lookups=lookups, variables=variables)
    except (PipelineError, QueryFieldError) as exc:
        raise ValueError(str(exc)) from None


async def run_pipeline_query(query_text: str, request_body: Dict[str, Any], customer_id: str,
                             variables: Any = None) -> Dict[str, Any]:
    """Phase 6: run a pipeline query for the /query/logql endpoint."""
    import time

    from logql_pipeline import requested_seconds

    seconds = requested_seconds(query_text)
    payload: Dict[str, Any] = {}
    if seconds:
        end = datetime.now(timezone.utc)
        payload = {"start_time": (end - timedelta(seconds=seconds)).isoformat(), "end_time": end.isoformat()}
    start, end = logql_window(payload, request_body)
    variables = _check_variables(request_body.get("variables") if variables is None else variables)

    began = time.time()
    try:
        result = await execute_pipeline_text(query_text, customer_id, start, end, variables)
    except HTTPException:
        raise
    except Exception as e:
        if "TIMEOUT_EXCEEDED" in str(e) or "Code: 159." in str(e):
            raise HTTPException(status_code=504, detail=(
                f"The query did not finish within {PIPELINE_QUERY_TIMEOUT_SECONDS} s. Narrow the time range, "
                "filter on service or level first, or count with stats count() by service / level / status "
                "(those read the hourly counts)."))
        raise internal_error(e, "LogQL query failed")
    return {
        "logs": result["rows"],
        "columns": result["columns"],
        "result_type": result["result_type"],
        "total_count": len(result["rows"]),
        "truncated": result["truncated"],
        "aggregations": {},
        "execution_time_ms": round((time.time() - began) * 1000, 2),
        "query_info": {"engine": "pipeline", "rows_returned": len(result["rows"]),
                       "estimated_rows": result.get("estimated_rows"), "hourly_counts": result.get("rollup", False)},
        "customer_id": customer_id,
        "time_range": _time_range_payload(start, end),
    }


async def run_archive_query(query_text: str, request_body: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
    """Phase 12: a pipeline query over the tenant's Parquet archives for the window."""
    import asyncio
    import time

    import data_scope

    # Archives are read with ClickHouse's s3() table function, which the scope's table
    # filters don't reach: compile_archive wraps the read in the scope's own filter.
    scope = data_scope.current()

    import archive_query
    import pattern_query
    from logql_pipeline import PipelineError, execute

    if pattern_query.split(query_text):
        raise HTTPException(status_code=400, detail="| patterns doesn't run on archives; rehydrate the days first")
    start, end = logql_window({}, request_body, max_window=timedelta(days=archive_query.MAX_WINDOW_DAYS))
    variables = _check_variables(request_body.get("variables"))
    from routers.storage_tiers_api import _manager

    mgr = _manager()
    archived = (await asyncio.to_thread(mgr.archived, "logs", customer_id)).get(customer_id, {})
    days = archive_query.days_in(archived, start, end)
    info = {"engine": "archive", "archived_days": len(days),
            "first_day": days[0].isoformat() if days else None, "last_day": days[-1].isoformat() if days else None}
    if not days:
        return {"logs": [], "columns": [], "result_type": "events", "total_count": 0, "truncated": False,
                "aggregations": {}, "execution_time_ms": 0.0, "query_info": info, "customer_id": customer_id,
                "time_range": _time_range_payload(start, end)}
    lookups = await _lookup_metas(customer_id, query_text)
    try:
        compiled = archive_query.compile_archive(query_text, customer_id, days, start, end, variables, lookups, scope=scope)
    except (PipelineError, QueryFieldError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = {"readonly": 2, "max_execution_time": PIPELINE_QUERY_TIMEOUT_SECONDS}
    began = time.time()
    try:
        result = await asyncio.to_thread(execute, mgr.client, compiled, settings)
    except Exception as e:
        if "TIMEOUT_EXCEEDED" in str(e) or "Code: 159." in str(e):
            raise HTTPException(status_code=504, detail=(
                f"The archive query did not finish within {PIPELINE_QUERY_TIMEOUT_SECONDS} s. Narrow the time "
                "range, or rehydrate the days and query them in ClickHouse."))
        raise internal_error(e, "Archive query failed")
    info["rows_returned"] = len(result["rows"])
    return {"logs": result["rows"], "columns": result["columns"], "result_type": result["result_type"],
            "total_count": len(result["rows"]), "truncated": result["truncated"], "aggregations": {},
            "execution_time_ms": round((time.time() - began) * 1000, 2), "query_info": info,
            "customer_id": customer_id, "time_range": _time_range_payload(start, end)}


@router.post("/query/estimate")
async def estimate_query(request_body: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Estimate what a LogforgeQL query would read, without running it.

    Same body as /query/logql. Returns the estimated rows, the tenant's plan
    limit, and whether the query reads the hourly counts.
    """
    import asyncio

    import query_cost
    from logql_pipeline import PipelineError, compile_pipeline, requested_seconds

    query_text = request_body.get("query")
    if not query_text or not isinstance(query_text, str):
        raise HTTPException(status_code=400, detail="A 'query' string is required")
    seconds = requested_seconds(query_text)
    payload: Dict[str, Any] = {}
    if seconds:
        end = datetime.now(timezone.utc)
        payload = {"start_time": (end - timedelta(seconds=seconds)).isoformat(), "end_time": end.isoformat()}
    start, end = logql_window(payload, request_body)
    variables = _check_variables(request_body.get("variables"))
    try:
        compiled = compile_pipeline(query_text, customer_id=customer_id, start=start, end=end, variables=variables,
                                    lookups=await _lookup_metas(customer_id, query_text))
    except (PipelineError, QueryFieldError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not query_engine:
        raise HTTPException(status_code=500, detail="Query engine not initialized")
    rows = await asyncio.to_thread(query_cost.estimate_rows, query_engine.client, compiled.sql, compiled.params)
    tier = await query_cost.tier_for(customer_id)
    limit = query_cost.load_limits().max_rows(tier)
    return {"estimated_rows": rows, "limit_rows": limit, "plan": tier or "default",
            "within_limit": rows is None or rows <= limit, "rollup": compiled.rollup,
            "time_range": _time_range_payload(start, end)}


@router.post("/query/aggregate")
async def aggregate_logs(query_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Aggregate log data with grouping and calculations"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        # ENH-033: build a validated request (tenant filter applied inside)
        # instead of handing a raw dict to the engine.
        query_request = build_query_request(query_data, customer_id)

        # Check cache first
        cached_result = await get_query_service().get_cached_result(query_data, customer_id)

        if cached_result:
            return {
                "results": cached_result.get('results', []),
                "aggregations": cached_result.get('aggregations', {}),
                "group_by": query_data.get("group_by", []),
                "total_groups": cached_result.get('total_count', 0),
                "execution_time_ms": cached_result.get('execution_time_ms', 0),
                "customer_id": customer_id
            }

        # Build aggregation query
        result = await query_engine.execute_query(query_request)
        
        # The grouped rows come back in `result.logs` (one row per group);
        # `result.aggregations` is only filled for ungrouped totals. Returning
        # just the latter reported total_groups=N with no data at all.
        result_dict = {
            "results": result.logs or [],
            "aggregations": result.aggregations or {},
            "total_count": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0
        }
        await get_query_service().cache_query_result(
            query_data=query_data,
            customer_id=customer_id,
            result=result_dict,
            ttl_seconds=300
        )
        
        return {
            "results": result.logs or [],
            "aggregations": result.aggregations or {},
            "group_by": query_data.get("group_by", []),
            "total_groups": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0,
            "customer_id": customer_id
        }
        
    except HTTPException:
        # ENH-033: preserve deliberate 4xx (e.g. an invalid query) instead of
        # relabelling it as a 500.
        raise
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Aggregation failed")

@router.post("/query/timeseries")
async def timeseries_query(query_request: TimeseriesQueryRequest, customer_id: str = MiddlewareTenant):
    """Time-series analysis endpoint for trends and patterns"""
    try:
        
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        query_data = query_request.model_dump()

        # Check cache first (cache key is built from the raw request shape)
        cached_result = await get_query_service().get_cached_result(query_data, customer_id)

        if cached_result:
            return {
                "buckets": cached_result.get('aggregations', {}).get("time_series", []),
                "aggregations": cached_result.get('aggregations', {}),
                "total_count": cached_result.get('total_count', 0),
                "execution_time_ms": cached_result.get('execution_time_ms', 0),
                "customer_id": customer_id
            }

        # ENH-033: translate the timeseries-specific request into a validated
        # AdvancedQueryRequest. `time_series`/`time_granularity` are what make
        # the engine emit time buckets; the previous raw dict carried
        # `granularity`/`interval`, which the engine never read.
        engine_payload = dict(query_data)
        engine_payload["time_series"] = True
        engine_payload["time_granularity"] = query_data.get("granularity") or "hour"
        # `interval`, `metrics` and `granularity` are not engine fields.
        for key in ("interval", "metrics", "granularity"):
            engine_payload.pop(key, None)

        engine_request = build_query_request(engine_payload, customer_id)

        # Execute time-series query
        result = await query_engine.execute_query(engine_request)
        
        # Cache the result
        result_dict = {
            "aggregations": result.aggregations or {},
            "total_count": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0
        }
        await get_query_service().cache_query_result(
            query_data=query_data,
            customer_id=customer_id,
            result=result_dict,
            ttl_seconds=300
        )
        
        return {
            "buckets": result.aggregations.get("time_series", []),
            "aggregations": result.aggregations or {},
            "total_count": result.total_count or 0,
            "execution_time_ms": result.execution_time_ms or 0,
            "customer_id": customer_id
        }
        
    except HTTPException:
        raise
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Timeseries query failed")

# Saved Query Management

@router.get("/query/saved")
async def list_saved_queries(
    created_by: str = Query(None, description="Filter by creator"),
    query_type: str = Query(None, description="Filter by query type"),
    limit: int = Query(50, description="Maximum number of queries to return"),
    customer_id: str = MiddlewareTenant
):
    """List saved queries for the customer"""
    try:
        result = await get_query_service().list_saved_queries(
            customer_id=customer_id,
            created_by=created_by,
            query_type=query_type,
            limit=limit
        )
        return result
        
    except Exception as e:
        raise internal_error(e, "Failed to list saved queries")

@router.post("/query/saved") 
async def save_query(query_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Save a query for future use"""
    try:
        # Add customer_id to query data
        query_data['customer_id'] = customer_id
        
        # Validate and save query
        result = await get_query_service().save_query(query_data)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to save query")

@router.get("/query/saved/{query_id}")
async def get_saved_query(query_id: str, customer_id: str = MiddlewareTenant):
    """Retrieve a specific saved query"""
    try:
        query_data = await get_query_service().get_saved_query(query_id, customer_id)
        
        if query_data:
            return query_data
        else:
            raise HTTPException(status_code=404, detail="Query not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(e, "Failed to retrieve query")

@router.put("/query/saved/{query_id}")
async def update_saved_query(query_id: str, update_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Update a specific saved query"""
    try:
        result = await get_query_service().update_saved_query(query_id, customer_id, update_data)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to update query")

@router.delete("/query/saved/{query_id}")
async def delete_saved_query(query_id: str, customer_id: str = MiddlewareTenant):
    """Delete a specific saved query"""
    try:
        result = await get_query_service().delete_saved_query(query_id, customer_id)
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Failed to delete query")

@router.post("/query/validate")
async def validate_query(query_data: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Validate query structure and parameters"""
    try:
        validation_result = await get_query_service().validate_query_structure(query_data)
        return validation_result
        
    except Exception as e:
        raise internal_error(e, "Query validation failed")

# Data Export Endpoints

@router.post("/export")
async def export_query_results(export_request: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Export query results in various formats (JSON, CSV, etc.)"""
    try:
        
        # Get query results first
        if not query_engine:
            raise HTTPException(status_code=500, detail="Query engine not initialized")
        
        raw_query = export_request.get("query", {})
        export_format = export_request.get("format", "json")

        # Handle string query (from log explorer search) vs dict query object.
        #
        # ENH-033: the free-text term was previously placed under a `search`
        # key, which the engine never reads -- so an export silently ignored the
        # user's search term. It maps to `text_search`.
        if isinstance(raw_query, str):
            query_data = {
                "text_search": raw_query,
                "filters": [],
                "start_time": export_request.get("start_time"),
                "end_time": export_request.get("end_time"),
            }
            # Include top-level filters from the request
            req_filters = export_request.get("filters", {})
            if isinstance(req_filters, dict):
                if req_filters.get("levels"):
                    query_data["filters"].append({
                        "field": "level",
                        "operator": "in",
                        "value": req_filters["levels"]
                    })
                if req_filters.get("service"):
                    query_data["filters"].append({
                        "field": "service",
                        "operator": "eq",
                        "value": req_filters["service"]
                    })
        else:
            query_data = raw_query if isinstance(raw_query, dict) else {}

        # ENH-033: validated request; tenant isolation applied inside.
        query_request = build_query_request(query_data, customer_id)

        # Execute query
        result = await query_engine.execute_query(query_request)
        
        # Format results based on requested format
        if export_format.lower() == "csv":
            # Convert to CSV format
            csv_data = "timestamp,level,service,message,host\n"
            for log in result.logs or []:
                csv_data += f"{log.get('ts')},{log.get('level')},{log.get('service')},{log.get('msg')},{log.get('host')}\n"
            
            return {
                "data": csv_data,
                "format": "csv",
                "count": result.total_count or 0,
                "customer_id": customer_id
            }
        else:
            # Default JSON format
            return {
                "data": result.logs or [],
                "format": "json", 
                "count": result.total_count or 0,
                "customer_id": customer_id
            }
            
    except HTTPException:
        raise
    except QueryFieldError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise internal_error(e, "Export failed")

# Basic log retrieval for M0 compatibility
# Keys ingestion adds to `attrs` for its own bookkeeping; not caller data.
_INTERNAL_ATTR_KEYS = frozenset({"source_format", "processing_version"})


def _caller_attrs(raw) -> dict:
    """Parse a stored `attrs` JSON string into the caller's attributes."""
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            return {}
    if not isinstance(parsed, dict):
        return {}
    return {k: v for k, v in parsed.items() if k not in _INTERNAL_ATTR_KEYS}


@router.get("/logs")
async def get_logs(
    service: str = Query(None, description="Filter by service name"),
    level: str = Query(None, description="Filter by log level"),
    start_time: Optional[datetime] = Query(None, description="Window start (ISO-8601). Defaults to end_time - 1h"),
    end_time: Optional[datetime] = Query(None, description="Window end (ISO-8601). Defaults to now"),
    limit: int = Query(100, ge=1, le=10000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    customer_id: str = MiddlewareTenant
):
    """
    Simple log retrieval endpoint for basic queries (M0 compatibility).

    ENH-003: `customer_id`, `service` and `level` were interpolated directly into
    the WHERE clause, so a crafted `service` value could terminate the predicate
    and neutralise the `customer_id` tenant-isolation filter, exposing other
    tenants' logs. All values are now bound as ClickHouse parameters, and
    limit/offset are integer-bounded by FastAPI before use.

    LF-017: the query is always bounded by a `ts` predicate. Without one,
    ClickHouse reads every monthly partition for the tenant before applying
    LIMIT -- a full-partition scan for what the UI presents as "recent logs".
    Omitted bounds default to the last hour; the effective window is returned
    as `time_range`; ranges wider than LOGFORGE_MAX_QUERY_WINDOW_DAYS
    (default 31) are rejected with a 400.
    """
    try:

        if not clickhouse_client:
            raise HTTPException(status_code=500, detail="Database client not initialized")

        # LF-017: resolve the bounded time window (defaults: last 1h).
        window_start, window_end = resolve_time_window(start_time, end_time)

        # Build the predicate with BOUND parameters only. `customer_id` comes
        # from the auth middleware, but is bound regardless -- defence in depth.
        where_conditions = [
            "customer_id = %(customer_id)s",
            "ts >= %(start_time)s",
            "ts <= %(end_time)s",
        ]
        params = {
            "customer_id": customer_id,
            "start_time": window_start,
            "end_time": window_end,
        }

        if service:
            where_conditions.append("service = %(service)s")
            params["service"] = service
        if level:
            where_conditions.append("level = %(level)s")
            params["level"] = level

        where_clause = " AND ".join(where_conditions)

        # limit/offset are ints validated by FastAPI (ge/le), so they cannot
        # carry SQL. int() makes that explicit and independent of the router.
        query = f"""
        SELECT ts, service, level, msg, host, trace_id, customer_id, span_id, attrs
        FROM logs_raw_mt
        WHERE {where_clause}
        ORDER BY ts DESC
        LIMIT {int(limit)} OFFSET {int(offset)}
        """

        # Off the event loop: a synchronous query here stalled every other request
        # for its whole duration (to_thread keeps the request's scope context).
        import asyncio

        result = await asyncio.to_thread(clickhouse_client.query, query, parameters=params)

        # Convert to expected format
        logs = []
        for row in result.result_rows:
            logs.append({
                "ts": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                "service": row[1],
                "level": row[2],
                "msg": row[3],
                "host": row[4],
                "trace_id": row[5],
                "customer_id": row[6],
                "span_id": row[7],
                "attrs": _caller_attrs(row[8]),
            })

        # Get total count for pagination (same bound predicate)
        count_query = f"""
        SELECT count() FROM logs_raw_mt WHERE {where_clause}
        """
        total_result = await asyncio.to_thread(clickhouse_client.query, count_query, parameters=params)
        total = total_result.result_rows[0][0] if total_result.result_rows else 0

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
            # LF-017: the window actually queried, so the UI can display
            # "showing last 1 hour" when it sent no explicit range.
            "time_range": _time_range_payload(window_start, window_end),
            "customer_id": customer_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise internal_error(e, "Log retrieval failed")