"""
Advanced Query Engine for Logforge M7
Supports complex querying, filtering, aggregation, and time-series analysis
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
from enum import Enum
import os
import re
import json
import clickhouse_connect
import structlog
from dataclasses import dataclass
from models import QueryResponse

logger = structlog.get_logger(__name__)


class QueryOperator(str, Enum):
    """Supported query operators"""
    EQ = "eq"          # equals
    NE = "ne"          # not equals
    GT = "gt"          # greater than
    GTE = "gte"        # greater than or equal
    LT = "lt"          # less than
    LTE = "lte"        # less than or equal
    CONTAINS = "contains"    # string contains
    STARTS_WITH = "starts_with"  # string starts with
    ENDS_WITH = "ends_with"    # string ends with
    REGEX = "regex"    # regex match
    IN = "in"          # value in list
    NOT_IN = "not_in"  # value not in list


class AggregationType(str, Enum):
    """Supported aggregation types"""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    PERCENTILE = "percentile"
    UNIQUE = "unique"
    CARDINALITY = "cardinality"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


class TimeGranularity(str, Enum):
    """Time series granularity options"""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class QueryFieldError(ValueError):
    """Raised when a query references an identifier that is not allow-listed."""


# ---------------------------------------------------------------------------
# Identifier allow-list (ENH-002)
# ---------------------------------------------------------------------------
#
# ClickHouse binds VALUES as parameters, but IDENTIFIERS (column names, ORDER BY
# targets) cannot be bound -- they are part of the statement's grammar. So every
# identifier that reaches SQL must be validated against a fixed allow-list
# derived from the real schema, and anything unknown is rejected outright.
#
# Source of truth: infra/docker/clickhouse/init_simple.sql
#   logs_raw_mt        -> line 181
#   logs_normalized_mt -> line 207
ALLOWED_QUERY_FIELDS = frozenset({
    # Shared across logs_raw_mt and logs_normalized_mt
    "ts", "host", "service", "level", "msg", "trace_id", "span_id",
    "status", "src_ip", "user_id", "ingested_at", "severity_num",
    "facility", "customer_id",
    # logs_raw_mt only
    "attrs", "parser_version",
    # logs_normalized_mt only
    "date", "hour",
    # Derived fields, computed from `attrs` at query time (DERIVED_FIELD_SQL)
    "extracted_user_id", "extracted_ip", "http_method", "http_uri",
    "http_status", "http_response_time_ms", "error_code", "is_error", "is_slow",
})

# Derived fields. These are the computed columns of the legacy single-tenant
# `logs_normalized` table (infra/docker/clickhouse/init_simple.sql). The
# multi-tenant tables the engine queries never gained them, so they used to pass
# the allow-list and then fail inside ClickHouse ("Missing columns"), surfacing
# as a 500. They are now computed at query time from logs_raw_mt's `attrs` JSON
# with the same extraction rules (plus `latency_ms`, a common alias), so they
# work for every tenant. Expressions are constants -- no caller input.
#
# Note: logs_raw_mt.attrs holds the whole ingested log envelope, with the
# caller's own attributes nested under "attrs". Keys are therefore looked up at
# the top level first, then under "attrs".
def _json_has(key: str) -> str:
    return f"(JSONHas(attrs, '{key}') OR JSONHas(attrs, 'attrs', '{key}'))"


def _json_uint(key: str) -> str:
    return (f"if(JSONHas(attrs, '{key}'), JSONExtractUInt(attrs, '{key}'), "
            f"JSONExtractUInt(attrs, 'attrs', '{key}'))")


def _json_str(key: str) -> str:
    return (f"if(JSONHas(attrs, '{key}'), JSONExtractString(attrs, '{key}'), "
            f"JSONExtractString(attrs, 'attrs', '{key}'))")


_HTTP_STATUS_SQL = (
    f"if({_json_has('status')}, {_json_uint('status')}, "
    f"if({_json_has('statusCode')}, {_json_uint('statusCode')}, status))"
)
_HTTP_RESPONSE_TIME_SQL = (
    f"if({_json_has('duration_ms')}, {_json_uint('duration_ms')}, "
    f"if({_json_has('responseTime')}, {_json_uint('responseTime')}, "
    f"{_json_uint('latency_ms')}))"
)
DERIVED_FIELD_SQL = {
    "date": "toDate(ts)",
    "hour": "toStartOfHour(ts)",
    "extracted_user_id": (
        f"coalesce(nullIf({_json_str('user_id')}, ''), "
        f"nullIf({_json_str('userId')}, ''), user_id)"
    ),
    "extracted_ip": (
        f"coalesce(nullIf({_json_str('ip')}, ''), "
        f"nullIf({_json_str('clientIP')}, ''), src_ip)"
    ),
    "http_method": f"upper({_json_str('method')})",
    "http_uri": _json_str("uri"),
    "http_status": _HTTP_STATUS_SQL,
    "http_response_time_ms": _HTTP_RESPONSE_TIME_SQL,
    "error_code": _json_str("error_code"),
    "is_error": (
        f"multiIf(lower(level) IN ('error', 'critical', 'fatal'), 1, "
        f"({_HTTP_STATUS_SQL}) >= 400, 1, 0)"
    ),
    "is_slow": f"if(({_HTTP_RESPONSE_TIME_SQL}) > 1000, 1, 0)",
}

# Fields aggregated directly; anything else goes through toFloat64OrZero()
# (which only accepts strings, so numeric expressions must be listed here).
NUMERIC_FIELDS = frozenset({
    "severity_num", "status", "facility",
    "http_status", "http_response_time_ms", "is_error", "is_slow",
})


def field_sql(field: str) -> str:
    """SQL for an allow-listed field: the column itself, or a derived field's
    expression (parenthesised)."""
    field = validate_identifier(field)
    expr = DERIVED_FIELD_SQL.get(field)
    return f"({expr})" if expr else field


# Aggregation aliases are generated internally, so they follow a known-safe
# shape. Anything else is rejected.
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# JSON path prefixes that may address keys inside a JSON column.
_JSON_FIELD_PREFIXES = ("attrs.", "raw_data.")


def validate_identifier(field: str) -> str:
    """
    Validate a bare column identifier against the schema allow-list.

    Raises:
        QueryFieldError: if the identifier is unknown. Rejecting is deliberate --
        silently dropping an unknown filter would widen the result set and could
        leak rows the caller never intended to match.
    """
    if field in ALLOWED_QUERY_FIELDS:
        return field
    raise QueryFieldError(
        f"Unknown query field: {field!r}. "
        f"Allowed fields: {', '.join(sorted(ALLOWED_QUERY_FIELDS))}"
    )


@dataclass
class QueryFilter:
    """Individual query filter"""
    field: str
    operator: QueryOperator
    value: Union[str, int, float, List[Any]]

    def to_clickhouse_condition(self, params: Dict[str, Any], param_prefix: str) -> str:
        """
        Render this filter as a ClickHouse condition using BOUND PARAMETERS.

        ENH-002: this previously interpolated `self.value` straight into SQL, so
        a value such as ``x' OR customer_id != '`` could neutralise the
        tenant-isolation predicate appended by the router and expose other
        tenants' data. Values are now bound; only allow-listed identifiers are
        emitted as SQL text.

        Args:
            params: mutable dict that receives the bound parameter values.
            param_prefix: unique prefix so parameters never collide.

        Returns:
            A condition string containing only placeholders for values.
        """
        field_name = self._render_field_reference(params, param_prefix)

        def bind(value: Any, suffix: str = "") -> str:
            key = f"{param_prefix}{suffix}"
            params[key] = value
            return f"%({key})s"

        op = self.operator

        if op == QueryOperator.EQ:
            return f"{field_name} = {bind(self.value)}"
        if op == QueryOperator.NE:
            return f"{field_name} != {bind(self.value)}"
        if op == QueryOperator.GT:
            return f"{field_name} > {bind(self.value)}"
        if op == QueryOperator.GTE:
            return f"{field_name} >= {bind(self.value)}"
        if op == QueryOperator.LT:
            return f"{field_name} < {bind(self.value)}"
        if op == QueryOperator.LTE:
            return f"{field_name} <= {bind(self.value)}"

        # LIKE wildcards are applied to the BOUND VALUE, not to the SQL text, so
        # a '%' inside user input stays literal data rather than becoming syntax.
        if op == QueryOperator.CONTAINS:
            return f"{field_name} LIKE {bind(f'%{self.value}%')}"
        if op == QueryOperator.STARTS_WITH:
            return f"{field_name} LIKE {bind(f'{self.value}%')}"
        if op == QueryOperator.ENDS_WITH:
            return f"{field_name} LIKE {bind(f'%{self.value}')}"

        if op == QueryOperator.REGEX:
            return f"match({field_name}, {bind(self.value)})"

        if op in (QueryOperator.IN, QueryOperator.NOT_IN):
            keyword = "IN" if op == QueryOperator.IN else "NOT IN"
            if isinstance(self.value, list):
                if not self.value:
                    # An empty IN () is a syntax error in ClickHouse. Emit a
                    # constant instead: `IN ()` matches nothing, `NOT IN ()`
                    # matches everything.
                    return "0" if op == QueryOperator.IN else "1"
                placeholders = [
                    bind(item, f"_{index}") for index, item in enumerate(self.value)
                ]
                return f"{field_name} {keyword} ({', '.join(placeholders)})"
            return (
                f"{field_name} = {bind(self.value)}"
                if op == QueryOperator.IN
                else f"{field_name} != {bind(self.value)}"
            )

        raise QueryFieldError(f"Unsupported operator: {op}")

    def _render_field_reference(self, params: Dict[str, Any], param_prefix: str) -> str:
        """
        Render the left-hand side of the condition.

        Bare columns are allow-listed. JSON paths keep working, but the KEY is
        bound as a parameter so it cannot terminate the JSONExtractString call.
        """
        field = self.field

        for prefix in _JSON_FIELD_PREFIXES:
            if field.startswith(prefix):
                json_key = field[len(prefix):]
                if not json_key:
                    raise QueryFieldError(f"Empty JSON key in field: {field!r}")
                key_param = f"{param_prefix}_jsonkey"
                params[key_param] = json_key
                if prefix == "attrs.":
                    # Caller attributes are nested under "attrs" in the stored
                    # envelope; fall back to that level (see _json_has).
                    return (
                        f"if(JSONHas(attrs, %({key_param})s), "
                        f"JSONExtractString(attrs, %({key_param})s), "
                        f"JSONExtractString(attrs, 'attrs', %({key_param})s))"
                    )
                return f"JSONExtractString(raw_data, %({key_param})s)"

        return field_sql(field)


@dataclass
class QueryAggregation:
    """Query aggregation specification"""
    type: AggregationType
    field: str
    alias: Optional[str] = None
    percentile_value: Optional[float] = None  # For percentile aggregations
    
    def to_clickhouse_select(self) -> str:
        """
        Convert to a ClickHouse SELECT clause.

        ENH-002: both the aggregated field and the alias land in SQL text, so
        both are validated. `count(*)` is the one permitted non-column form.
        """
        field_name = self.field
        alias = self.alias or f"{self.type.value}_{self.field.replace('*', 'all')}"

        if not _SAFE_IDENTIFIER_RE.match(alias):
            raise QueryFieldError(f"Invalid aggregation alias: {alias!r}")

        # Handle nested JSON fields. The key is embedded in SQL here (there is no
        # parameter dict on this path), so it is restricted to a safe shape
        # rather than quoted -- quoting is what fails under adversarial input.
        if field_name.startswith('attrs.'):
            json_field = field_name[len('attrs.'):]
            if not _SAFE_IDENTIFIER_RE.match(json_field):
                raise QueryFieldError(
                    f"Invalid JSON key in aggregation field: {field_name!r}"
                )
            field_name = _json_str(json_field)
        elif field_name != "*":
            field_name = field_sql(field_name)
        numeric = self.field in NUMERIC_FIELDS

        if self.type == AggregationType.COUNT:
            if field_name == "*":
                return f"count() AS {alias}"
            return f"count({field_name}) AS {alias}"
            
        elif self.type == AggregationType.SUM:
            # Use direct aggregation for known numeric fields, toFloat64OrZero for string fields
            if numeric:
                return f"sum({field_name}) AS {alias}"
            return f"sum(toFloat64OrZero({field_name})) AS {alias}"
            
        elif self.type == AggregationType.AVG:
            # Use direct aggregation for known numeric fields, toFloat64OrZero for string fields
            if numeric:
                return f"avg({field_name}) AS {alias}"
            return f"avg(toFloat64OrZero({field_name})) AS {alias}"
            
        elif self.type == AggregationType.MIN:
            return f"min({field_name}) AS {alias}"
            
        elif self.type == AggregationType.MAX:
            return f"max({field_name}) AS {alias}"
            
        elif self.type == AggregationType.PERCENTILE:
            percentile = self.percentile_value or 0.95
            # Use direct aggregation for known numeric fields, toFloat64OrZero for string fields
            if numeric:
                return f"quantile({percentile})({field_name}) AS {alias}"
            return f"quantile({percentile})(toFloat64OrZero({field_name})) AS {alias}"
            
        elif self.type == AggregationType.UNIQUE:
            return f"uniq({field_name}) AS {alias}"
            
        elif self.type == AggregationType.CARDINALITY:
            return f"uniqHLL12({field_name}) AS {alias}"
        
        return f"count() AS {alias}"


class AdvancedQueryRequest(BaseModel):
    """Advanced query request model"""
    
    # Basic query parameters
    start_time: datetime = Field(..., description="Query start time")
    end_time: datetime = Field(..., description="Query end time")
    
    # Filtering
    filters: List[QueryFilter] = Field(default=[], description="Query filters")
    text_search: Optional[str] = Field(None, description="Full-text search in message field")
    
    # Aggregation
    aggregations: List[QueryAggregation] = Field(default=[], description="Aggregation specifications")
    group_by: List[str] = Field(default=[], description="Group by fields")
    
    # Time series
    time_series: Optional[bool] = Field(False, description="Enable time series grouping")
    time_granularity: Optional[TimeGranularity] = Field(TimeGranularity.HOUR, description="Time bucket size")
    
    # Sorting and limiting
    sort_field: str = Field("ts", description="Sort field")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")
    limit: int = Field(1000, description="Maximum results", ge=1, le=10000)
    offset: int = Field(0, description="Result offset", ge=0)
    
    # Result format
    include_fields: Optional[List[str]] = Field(None, description="Fields to include in results")
    exclude_fields: Optional[List[str]] = Field(None, description="Fields to exclude from results")
    
    # Performance options
    timeout_seconds: int = Field(30, description="Query timeout", ge=1, le=300)
    
    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v




class SavedQuery(BaseModel):
    """Saved query model"""
    id: Optional[str] = None
    name: str = Field(..., description="Query name")
    description: Optional[str] = None
    query: AdvancedQueryRequest
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    tags: List[str] = Field(default=[])
    is_public: bool = Field(False, description="Public query visible to all users")


class AdvancedQueryEngine:
    """Advanced query engine for ClickHouse"""
    
    def __init__(self, clickhouse_client):
        self.client = clickhouse_client
        self.base_table = "logs_raw_mt"
        self.normalized_table = "logs_normalized_mt"
    
    async def execute_query(self, query: AdvancedQueryRequest) -> QueryResponse:
        """Execute advanced query and return results"""
        import time
        start_time = time.time()
        
        # Determine which table to use
        table = self._select_optimal_table(query)

        # Build the SQL query. `params` receives every bound value; the returned
        # SQL contains placeholders only (ENH-002).
        params: Dict[str, Any] = {}
        sql_query = self._build_sql_query(query, table, params)

        logger.debug("Executing query", table=table, param_count=len(params))

        # ENH-017: cost guards. Without these, one tenant's unfiltered
        # wide-time-range query scans their entire partition set and degrades
        # the cluster for everyone -- a noisy-neighbour failure. `timeout_seconds`
        # was declared on the request model but never passed to the client, so
        # the documented timeout did nothing.
        settings = self._build_query_settings(query)

        # Values are bound by the driver -- never formatted into the statement.
        result = self.client.query(sql_query, parameters=params, settings=settings)
        rows = result.result_rows

        # Process results
        if query.aggregations:
            response = self._process_aggregation_results(rows, query)
        else:
            response = self._process_log_results(rows, query)

        # Add execution metadata.
        #
        # NOTE: the rendered SQL is deliberately NOT echoed back to callers.
        # It previously leaked the full statement (including other tenants'
        # filter structure) into API responses.
        execution_time = (time.time() - start_time) * 1000
        response.execution_time_ms = execution_time
        response.query_info = {
            "table_used": table,
            "rows_returned": len(rows)
        }

        return response
    
    # ENH-017: default per-query resource budget. Deliberately generous enough
    # for real analytical queries but low enough that a single request cannot
    # monopolise the cluster. Tunable per deployment via the environment, and
    # per subscription tier once tiering is wired in.
    DEFAULT_MAX_BYTES_TO_READ = 50 * 1024 * 1024 * 1024  # 50 GiB
    DEFAULT_MAX_RESULT_ROWS = 100_000

    def _build_query_settings(self, query: AdvancedQueryRequest) -> Dict[str, Any]:
        """
        Build ClickHouse execution settings that bound the cost of a query.

        `*_overflow_mode='throw'` is deliberate: a query that exceeds its budget
        must FAIL, not silently return a truncated result. Returning partial
        data as though it were complete would make dashboards and alerts lie --
        exactly the fabricated-success pattern this project forbids.
        """
        max_bytes = int(
            os.getenv("LOGFORGE_QUERY_MAX_BYTES", self.DEFAULT_MAX_BYTES_TO_READ)
        )
        max_rows = int(
            os.getenv("LOGFORGE_QUERY_MAX_RESULT_ROWS", self.DEFAULT_MAX_RESULT_ROWS)
        )

        return {
            # Honour the timeout the caller actually asked for.
            "max_execution_time": int(query.timeout_seconds),
            "timeout_overflow_mode": "throw",
            "max_bytes_to_read": max_bytes,
            "read_overflow_mode": "throw",
            "max_result_rows": max_rows,
            "result_overflow_mode": "throw",
        }

    def _select_optimal_table(self, query: AdvancedQueryRequest) -> str:
        """Select the optimal table for the query"""
        # Derived fields are computed from logs_raw_mt's `attrs`, which the
        # normalized table doesn't have.
        if self._uses_derived_fields(query):
            return self.base_table

        # Check if this is a multi-tenant query (has customer_id filter)
        has_customer_filter = any(f.field == "customer_id" for f in query.filters)
        
        # Use normalized table if we need aggregations or complex filtering
        if query.aggregations or query.time_series or query.group_by:
            # For multi-tenant, use raw table for now until materialized view is fixed
            if has_customer_filter:
                return self.base_table  # Already has _mt suffix
            return self.normalized_table
        
        # Default to raw table for simple queries
        return self.base_table

    @staticmethod
    def _uses_derived_fields(query: "AdvancedQueryRequest") -> bool:
        referenced = (
            [f.field for f in query.filters]
            + [a.field for a in query.aggregations]
            + list(query.group_by)
            + list(query.include_fields or [])
            + [query.sort_field]
        )
        return any(f in DERIVED_FIELD_SQL for f in referenced)
    
    def _build_sql_query(
        self,
        query: AdvancedQueryRequest,
        table: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a ClickHouse SQL query.

        ENH-002: all VALUES are bound into `params` as placeholders; only
        allow-listed IDENTIFIERS are emitted as SQL text. `table` is chosen
        internally by `_select_optimal_table` and is never caller-supplied.
        """
        if params is None:
            params = {}

        # Validate every caller-supplied identifier up front so a bad request
        # fails cleanly before any SQL is assembled.
        group_by_fields = [validate_identifier(f) for f in query.group_by]

        # SELECT clause. Derived group-by fields are selected under their own
        # name, so GROUP BY / ORDER BY can refer to the alias.
        if query.aggregations:
            select_parts = [
                f"{field_sql(f)} AS {f}" if f in DERIVED_FIELD_SQL else f
                for f in group_by_fields
            ]

            # Add time series grouping
            if query.time_series:
                time_func = self._get_time_function(query.time_granularity)
                select_parts.append(f"{time_func}(ts) AS time_bucket")

            # Add aggregations
            for agg in query.aggregations:
                select_parts.append(agg.to_clickhouse_select())

            # Ensure we have at least one SELECT element
            if not select_parts:
                select_parts.append("1")

            select_clause = ", ".join(select_parts)
        else:
            # Regular log query
            if query.include_fields:
                select_clause = ", ".join(
                    f"{field_sql(f)} AS {f}" if f in DERIVED_FIELD_SQL else validate_identifier(f)
                    for f in query.include_fields
                )
            else:
                select_clause = "*"

        # FROM clause -- `table` is engine-selected, not caller-supplied.
        from_clause = f"FROM {table}"

        # WHERE clause
        where_conditions = []

        # Time range -- bound, not formatted.
        params["_start_time"] = query.start_time
        params["_end_time"] = query.end_time
        where_conditions.append("ts >= %(_start_time)s")
        where_conditions.append("ts <= %(_end_time)s")

        # Filters -- each gets a unique parameter prefix so keys never collide.
        for index, filter_obj in enumerate(query.filters):
            where_conditions.append(
                filter_obj.to_clickhouse_condition(params, f"_f{index}")
            )

        # Text search -- wildcards applied to the bound value, so a '%' in user
        # input stays literal instead of becoming a wildcard.
        if query.text_search:
            params["_text_search"] = f"%{query.text_search}%"
            where_conditions.append("msg LIKE %(_text_search)s")

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        # GROUP BY clause
        group_by_clause = ""
        if query.aggregations:
            group_parts = list(group_by_fields)

            if query.time_series:
                group_parts.append("time_bucket")

            if group_parts:
                group_by_clause = f"GROUP BY {', '.join(group_parts)}"

        # ORDER BY clause
        sort_direction = query.sort_order.value.upper()
        if sort_direction not in ("ASC", "DESC"):
            raise QueryFieldError(f"Invalid sort order: {query.sort_order}")

        if query.aggregations and query.time_series:
            order_by_clause = f"ORDER BY time_bucket {sort_direction}"
        elif query.aggregations:
            if group_by_fields:
                order_by_clause = f"ORDER BY {group_by_fields[0]} {sort_direction}"
            else:
                # Aggregation aliases are generated internally; still shape-check
                # them so a hand-crafted alias cannot inject SQL.
                first_agg = query.aggregations[0]
                first_agg_alias = first_agg.alias or (
                    f"{first_agg.type.value}_{first_agg.field.replace('*', 'all')}"
                )
                if not _SAFE_IDENTIFIER_RE.match(first_agg_alias):
                    raise QueryFieldError(
                        f"Invalid aggregation alias: {first_agg_alias!r}"
                    )
                order_by_clause = f"ORDER BY {first_agg_alias} {sort_direction}"
        else:
            order_by_clause = (
                f"ORDER BY {field_sql(query.sort_field)} {sort_direction}"
            )

        # LIMIT clause -- coerced to int, so no string can reach the statement.
        # Pydantic already bounds these (limit 1..10000, offset >= 0).
        limit_clause = f"LIMIT {int(query.offset)}, {int(query.limit)}"

        # Assemble query
        query_parts = [
            f"SELECT {select_clause}",
            from_clause,
            where_clause
        ]

        if group_by_clause:
            query_parts.append(group_by_clause)

        query_parts.extend([
            order_by_clause,
            limit_clause
        ])

        return " ".join(query_parts)
    
    def _get_time_function(self, granularity: TimeGranularity) -> str:
        """Get ClickHouse time function for granularity"""
        if granularity == TimeGranularity.SECOND:
            return "toStartOfMinute"  # ClickHouse doesn't have second precision
        elif granularity == TimeGranularity.MINUTE:
            return "toStartOfMinute"
        elif granularity == TimeGranularity.HOUR:
            return "toStartOfHour"
        elif granularity == TimeGranularity.DAY:
            return "toStartOfDay"
        elif granularity == TimeGranularity.WEEK:
            return "toMonday"
        elif granularity == TimeGranularity.MONTH:
            return "toStartOfMonth"
        else:
            return "toStartOfHour"
    
    def _process_log_results(self, rows: List, query: AdvancedQueryRequest) -> QueryResponse:
        """Process regular log query results"""
        logs = []
        
        for row in rows:
            # Convert row to dictionary
            if query.include_fields:
                # When include_fields is specified, map columns to the requested fields
                log_dict = {}
                for i, field in enumerate(query.include_fields):
                    if i < len(row):
                        log_dict[field] = row[i]
            else:
                # Default full table schema mapping
                log_dict = {
                    'ts': row[0] if len(row) > 0 else None,
                    'host': row[1] if len(row) > 1 else None,
                    'service': row[2] if len(row) > 2 else None,
                    'level': row[3] if len(row) > 3 else None,
                    'msg': row[4] if len(row) > 4 else None,
                    'trace_id': row[5] if len(row) > 5 else None,
                    'span_id': row[6] if len(row) > 6 else None,
                    'attrs': json.loads(row[7]) if len(row) > 7 and row[7] else {},
                    'status': row[8] if len(row) > 8 else None,
                    'src_ip': row[9] if len(row) > 9 else None,
                    'user_id': row[10] if len(row) > 10 else None
                }
            
            # Apply field filtering
            if query.exclude_fields:
                for field in query.exclude_fields:
                    log_dict.pop(field, None)
            
            logs.append(log_dict)
        
        return QueryResponse(
            logs=logs,
            total_count=len(logs),
            execution_time_ms=0,
            has_more=len(logs) == query.limit,
            next_offset=query.offset + query.limit if len(logs) == query.limit else None
        )
    
    def _process_aggregation_results(self, rows: List, query: AdvancedQueryRequest) -> QueryResponse:
        """Process aggregation query results"""
        aggregations = {}
        time_series_data = []
        grouped_data = []
        
        for row in rows:
            row_data = {}
            col_idx = 0
            
            # Process group by fields
            for field in query.group_by:
                row_data[field] = row[col_idx]
                col_idx += 1
            
            # Process time bucket if time series
            if query.time_series:
                row_data['time'] = row[col_idx]
                col_idx += 1
            
            # Process aggregation results
            for agg in query.aggregations:
                alias = agg.alias or f"{agg.type.value}_{agg.field.replace('*', 'all')}"
                row_data[alias] = row[col_idx]
                col_idx += 1
            
            if query.time_series:
                time_series_data.append(row_data)
            elif query.group_by:
                # For group_by queries, collect all rows
                grouped_data.append(row_data)
            else:
                # For simple aggregations without group_by, just use the first row
                if not aggregations:
                    aggregations = row_data
        
        if query.time_series:
            aggregations['time_series'] = time_series_data
        elif query.group_by:
            # Return grouped data as logs since each row represents a group
            return QueryResponse(
                logs=grouped_data,
                aggregations={},
                total_count=len(grouped_data)
            )
        
        return QueryResponse(
            logs=[],
            aggregations=aggregations,
            total_count=len(time_series_data) if query.time_series else 1
        )


# Global query engine instance
_query_engine_instance = None

def get_query_engine():
    """Get the global query engine instance"""
    global _query_engine_instance
    if _query_engine_instance is None:
        import clickhouse_connect

        from app_config import clickhouse_settings

        # Host and port used to be hard-coded (clickhouse:8123), ignoring
        # CLICKHOUSE_HOST/PORT -- so a locally run API queried a host that
        # didn't exist.
        client = clickhouse_connect.get_client(**clickhouse_settings())
        _query_engine_instance = AdvancedQueryEngine(client)
    return _query_engine_instance