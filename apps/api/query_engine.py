"""
Advanced Query Engine for Logforge M7
Supports complex querying, filtering, aggregation, and time-series analysis
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
from enum import Enum
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


@dataclass
class QueryFilter:
    """Individual query filter"""
    field: str
    operator: QueryOperator
    value: Union[str, int, float, List[Any]]
    
    def to_clickhouse_condition(self) -> str:
        """Convert filter to ClickHouse WHERE condition"""
        field_name = self.field
        
        # Handle nested JSON fields in attrs/raw_data
        if '.' in field_name and field_name.startswith('attrs.'):
            json_field = field_name.replace('attrs.', '')
            field_name = f"JSONExtractString(raw_data, '{json_field}')"
        elif '.' in field_name and field_name.startswith('raw_data.'):
            json_field = field_name.replace('raw_data.', '')
            field_name = f"JSONExtractString(raw_data, '{json_field}')"
        
        if self.operator == QueryOperator.EQ:
            if isinstance(self.value, str):
                return f"{field_name} = '{self.value}'"
            return f"{field_name} = {self.value}"
            
        elif self.operator == QueryOperator.NE:
            if isinstance(self.value, str):
                return f"{field_name} != '{self.value}'"
            return f"{field_name} != {self.value}"
            
        elif self.operator == QueryOperator.GT:
            return f"{field_name} > {self.value}"
            
        elif self.operator == QueryOperator.GTE:
            return f"{field_name} >= {self.value}"
            
        elif self.operator == QueryOperator.LT:
            return f"{field_name} < {self.value}"
            
        elif self.operator == QueryOperator.LTE:
            return f"{field_name} <= {self.value}"
            
        elif self.operator == QueryOperator.CONTAINS:
            return f"{field_name} LIKE '%{self.value}%'"
            
        elif self.operator == QueryOperator.STARTS_WITH:
            return f"{field_name} LIKE '{self.value}%'"
            
        elif self.operator == QueryOperator.ENDS_WITH:
            return f"{field_name} LIKE '%{self.value}'"
            
        elif self.operator == QueryOperator.REGEX:
            return f"match({field_name}, '{self.value}')"
            
        elif self.operator == QueryOperator.IN:
            if isinstance(self.value, list):
                values = [f"'{v}'" if isinstance(v, str) else str(v) for v in self.value]
                return f"{field_name} IN ({', '.join(values)})"
            return f"{field_name} = '{self.value}'"
            
        elif self.operator == QueryOperator.NOT_IN:
            if isinstance(self.value, list):
                values = [f"'{v}'" if isinstance(v, str) else str(v) for v in self.value]
                return f"{field_name} NOT IN ({', '.join(values)})"
            return f"{field_name} != '{self.value}'"
        
        return f"{field_name} = '{self.value}'"


@dataclass
class QueryAggregation:
    """Query aggregation specification"""
    type: AggregationType
    field: str
    alias: Optional[str] = None
    percentile_value: Optional[float] = None  # For percentile aggregations
    
    def to_clickhouse_select(self) -> str:
        """Convert to ClickHouse SELECT clause"""
        field_name = self.field
        alias = self.alias or f"{self.type.value}_{self.field.replace('*', 'all')}"
        
        # Handle nested JSON fields
        if '.' in field_name and field_name.startswith('attrs.'):
            json_field = field_name.replace('attrs.', '')
            field_name = f"JSONExtractString(attrs, '{json_field}')"
        
        if self.type == AggregationType.COUNT:
            if field_name == "*":
                return f"count() AS {alias}"
            return f"count({field_name}) AS {alias}"
            
        elif self.type == AggregationType.SUM:
            return f"sum(toFloat64OrZero({field_name})) AS {alias}"
            
        elif self.type == AggregationType.AVG:
            return f"avg(toFloat64OrZero({field_name})) AS {alias}"
            
        elif self.type == AggregationType.MIN:
            return f"min({field_name}) AS {alias}"
            
        elif self.type == AggregationType.MAX:
            return f"max({field_name}) AS {alias}"
            
        elif self.type == AggregationType.PERCENTILE:
            percentile = self.percentile_value or 0.95
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
        
        try:
            # Determine which table to use
            table = self._select_optimal_table(query)
            
            # Build the SQL query
            sql_query = self._build_sql_query(query, table)
            
            # Debug logging for alert queries
            logger.info(f"Executing SQL: {sql_query}")
            
            # Execute query
            result = self.client.query(sql_query)
            rows = result.result_rows
            
            # Process results
            if query.aggregations:
                # Handle aggregation results
                response = self._process_aggregation_results(rows, query)
            else:
                # Handle log results
                response = self._process_log_results(rows, query)
            
            # Add execution metadata
            execution_time = (time.time() - start_time) * 1000
            response.execution_time_ms = execution_time
            response.query_info = {
                "sql_query": sql_query,
                "table_used": table,
                "total_rows_scanned": len(rows)
            }
            
            return response
            
        except Exception as e:
            # Return error response
            return QueryResponse(
                logs=[],
                total_count=0,
                execution_time_ms=(time.time() - start_time) * 1000,
                query_info={"error": str(e)}
            )
    
    def _select_optimal_table(self, query: AdvancedQueryRequest) -> str:
        """Select the optimal table for the query"""
        # Check if this is a multi-tenant query (has customer_id filter)
        has_customer_filter = any(f.field == "customer_id" for f in query.filters)
        
        # Use normalized table if we need aggregations or complex filtering
        if query.aggregations or query.time_series or query.group_by:
            # For multi-tenant, use raw table for now until materialized view is fixed
            if has_customer_filter:
                return self.base_table  # Already has _mt suffix
            return self.normalized_table
        
        # Check if we need fields only available in normalized table
        normalized_fields = {'extracted_user_id', 'extracted_ip', 'http_method', 
                           'http_uri', 'http_status', 'http_response_time_ms', 
                           'error_code', 'is_error', 'is_slow'}
        
        for filter_obj in query.filters:
            if filter_obj.field in normalized_fields:
                return self.normalized_table
        
        if query.include_fields:
            if any(field in normalized_fields for field in query.include_fields):
                return self.normalized_table
        
        # Default to raw table for simple queries
        return self.base_table
    
    def _build_sql_query(self, query: AdvancedQueryRequest, table: str) -> str:
        """Build ClickHouse SQL query"""
        # SELECT clause
        if query.aggregations:
            select_parts = []
            
            # Add group by fields
            for field in query.group_by:
                select_parts.append(field)
            
            # Add time series grouping
            if query.time_series:
                time_func = self._get_time_function(query.time_granularity)
                select_parts.append(f"{time_func}(ts) AS time_bucket")
            
            # Add aggregations
            for agg in query.aggregations:
                select_parts.append(agg.to_clickhouse_select())
            
            # Ensure we have at least one SELECT element
            if not select_parts:
                select_parts.append("1")  # Fallback
            
            select_clause = ", ".join(select_parts)
        else:
            # Regular log query
            if query.include_fields:
                select_clause = ", ".join(query.include_fields)
            else:
                select_clause = "*"
        
        # FROM clause
        from_clause = f"FROM {table}"
        
        # WHERE clause
        where_conditions = []
        
        # Time range
        where_conditions.append(f"ts >= '{query.start_time.isoformat()}'")
        where_conditions.append(f"ts <= '{query.end_time.isoformat()}'")
        
        # Filters
        for filter_obj in query.filters:
            where_conditions.append(filter_obj.to_clickhouse_condition())
        
        # Text search
        if query.text_search:
            where_conditions.append(f"msg LIKE '%{query.text_search}%'")
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}"
        
        # GROUP BY clause
        group_by_clause = ""
        if query.aggregations:
            group_parts = []
            
            for field in query.group_by:
                group_parts.append(field)
            
            if query.time_series:
                group_parts.append("time_bucket")
            
            if group_parts:
                group_by_clause = f"GROUP BY {', '.join(group_parts)}"
        
        # ORDER BY clause
        if query.aggregations and query.time_series:
            order_by_clause = f"ORDER BY time_bucket {query.sort_order.value}"
        elif query.aggregations:
            # For aggregations without time series, order by first aggregation or group by field
            if query.group_by:
                order_by_clause = f"ORDER BY {query.group_by[0]} {query.sort_order.value}"
            elif query.aggregations:
                # Use first aggregation alias (match the one generated in to_clickhouse_select)
                first_agg = query.aggregations[0]
                first_agg_alias = first_agg.alias or f"{first_agg.type.value}_{first_agg.field.replace('*', 'all')}"
                order_by_clause = f"ORDER BY {first_agg_alias} {query.sort_order.value}"
            else:
                order_by_clause = ""
        else:
            order_by_clause = f"ORDER BY {query.sort_field} {query.sort_order.value}"
        
        # LIMIT clause
        limit_clause = f"LIMIT {query.offset}, {query.limit}"
        
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
            # This assumes the row matches the table schema
            log_dict = {
                'ts': row[0],
                'host': row[1],
                'service': row[2],
                'level': row[3],
                'msg': row[4],
                'trace_id': row[5],
                'span_id': row[6],
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
            else:
                # For non-time-series, just use the first row
                if not aggregations:
                    aggregations = row_data
        
        if query.time_series:
            aggregations['time_series'] = time_series_data
        
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
        import os
        
        # Get connection details from environment variables
        host = 'clickhouse'
        port = 8123
        username = os.getenv('CLICKHOUSE_USER', 'logforge')
        password = os.getenv('CLICKHOUSE_PASSWORD', 'logforge123')
        database = os.getenv('CLICKHOUSE_DATABASE', 'logforge')
        
        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database
        )
        _query_engine_instance = AdvancedQueryEngine(client)
    return _query_engine_instance