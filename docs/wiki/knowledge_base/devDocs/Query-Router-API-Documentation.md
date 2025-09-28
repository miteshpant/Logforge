# Query Router API Documentation

## Overview

The Query Router provides advanced log querying capabilities with filtering, aggregations, time-series analysis, and saved query management. This router enables complex log analysis, data export, and performance-optimized query execution with caching and multi-tenant isolation.

## Architecture

```
Request → Query Router → Query Service → Query DAO → ClickHouse
                     ↓
                Query Engine → ClickHouse (direct for complex queries)
```

**Core Components:**
- **Router**: `/apps/api/routers/query.py` - FastAPI endpoints with query models
- **Service**: `/apps/api/services/query_service.py` - Business logic and validation
- **DAO**: `/apps/api/dao/query_dao.py` - Database operations for queries and caching
- **Engine**: `/apps/api/query_engine.py` - Advanced query execution engine
- **Database**: Multi-tenant ClickHouse tables (`logs_raw_mt`, `logs_normalized_mt`, `saved_queries_mt`, `query_cache_mt`)

## API Endpoints

### Advanced Query Operations

#### 1. Advanced Query
**Endpoint**: `POST /v1/query/advanced`

Execute advanced log queries with complex filtering, aggregations, and analysis.

**Headers:**
- `X-Customer-ID`: Customer identifier (via MiddlewareTenant)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    },
    {
      "field": "service",
      "operator": "contains",
      "value": "user"
    },
    {
      "field": "ts",
      "operator": "gte",
      "value": "2024-01-15T10:00:00Z"
    },
    {
      "field": "ts",
      "operator": "lte", 
      "value": "2024-01-15T11:00:00Z"
    }
  ],
  "aggregations": [
    {
      "type": "count",
      "field": "level",
      "group_by": ["service", "host"]
    },
    {
      "type": "avg",
      "field": "response_time",
      "group_by": ["service"]
    }
  ],
  "sort": [
    {
      "field": "ts",
      "direction": "desc"
    }
  ],
  "limit": 100,
  "offset": 0,
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z"
}
```

**Filter Operators:**
- `eq`: Equal to
- `ne`: Not equal to
- `gt`: Greater than
- `gte`: Greater than or equal to
- `lt`: Less than
- `lte`: Less than or equal to
- `contains`: Contains substring
- `starts_with`: Starts with prefix
- `ends_with`: Ends with suffix
- `regex`: Regular expression match
- `in`: In list of values
- `not_in`: Not in list of values

**Response:**
```json
{
  "logs": [
    {
      "ts": "2024-01-15T10:30:00Z",
      "level": "ERROR",
      "service": "user-service",
      "msg": "Database connection timeout",
      "host": "user-service-pod-123",
      "trace_id": "1234567890abcdef",
      "customer_id": "customer_123",
      "response_time": 5000
    },
    {
      "ts": "2024-01-15T10:29:45Z",
      "level": "ERROR", 
      "service": "user-api",
      "msg": "Authentication failed",
      "host": "user-api-pod-456",
      "trace_id": "fedcba0987654321",
      "customer_id": "customer_123",
      "response_time": 2500
    }
  ],
  "total_count": 2,
  "aggregations": {
    "count_by_service_host": [
      {
        "service": "user-service",
        "host": "user-service-pod-123",
        "count": 1
      },
      {
        "service": "user-api",
        "host": "user-api-pod-456", 
        "count": 1
      }
    ],
    "avg_response_time_by_service": [
      {
        "service": "user-service",
        "avg_response_time": 5000
      },
      {
        "service": "user-api",
        "avg_response_time": 2500
      }
    ]
  },
  "execution_time_ms": 245,
  "customer_id": "customer_123"
}
```

**Implementation:**
```python
query_service = QueryService()

# Check cache first
cached_result = await query_service.get_cached_result(query_dict, customer_id)
if cached_result:
    return QueryResponse(**cached_result)

# Execute advanced query
result = await query_engine.execute_query(query_request)

# Cache the result (5 minutes TTL)
await query_service.cache_query_result(
    query_data=query_dict,
    customer_id=customer_id, 
    result=result.model_dump(),
    ttl_seconds=300
)
```

#### 2. Aggregate Query
**Endpoint**: `POST /v1/query/aggregate`

Perform aggregations on log data with grouping and calculations.

**Request Body:**
```json
{
  "filters": [
    {
      "field": "level",
      "operator": "in",
      "value": ["ERROR", "WARN"]
    },
    {
      "field": "ts",
      "operator": "gte",
      "value": "2024-01-15T00:00:00Z"
    }
  ],
  "group_by": ["service", "level"],
  "aggregations": [
    {
      "type": "count",
      "field": "*"
    },
    {
      "type": "avg",
      "field": "response_time"
    },
    {
      "type": "max",
      "field": "response_time"
    }
  ]
}
```

**Response:**
```json
{
  "aggregations": {
    "groups": [
      {
        "service": "user-service",
        "level": "ERROR",
        "count": 156,
        "avg_response_time": 4250.7,
        "max_response_time": 8750
      },
      {
        "service": "user-service", 
        "level": "WARN",
        "count": 89,
        "avg_response_time": 2150.3,
        "max_response_time": 3500
      },
      {
        "service": "auth-service",
        "level": "ERROR",
        "count": 42,
        "avg_response_time": 1850.5,
        "max_response_time": 4200
      }
    ]
  },
  "group_by": ["service", "level"],
  "total_groups": 3,
  "execution_time_ms": 125,
  "customer_id": "customer_123"
}
```

#### 3. Time-Series Query
**Endpoint**: `POST /v1/query/timeseries`

Perform time-series analysis for trends and patterns over time.

**Request Body:**
```json
{
  "start_time": "2024-01-15T00:00:00Z",
  "end_time": "2024-01-15T23:59:59Z",
  "interval": "1h",
  "metrics": ["count", "avg_response_time"],
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "user-service"
    }
  ],
  "group_by": ["level"],
  "aggregations": [
    {
      "type": "count",
      "field": "*"
    },
    {
      "type": "avg",
      "field": "response_time"
    }
  ],
  "granularity": "hour"
}
```

**Response:**
```json
{
  "buckets": [
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "level": "INFO",
      "count": 1250,
      "avg_response_time": 145.7
    },
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "level": "ERROR",
      "count": 15,
      "avg_response_time": 4250.3
    },
    {
      "timestamp": "2024-01-15T01:00:00Z",
      "level": "INFO", 
      "count": 1180,
      "avg_response_time": 167.2
    },
    {
      "timestamp": "2024-01-15T01:00:00Z",
      "level": "ERROR",
      "count": 8,
      "avg_response_time": 3890.5
    }
  ],
  "aggregations": {
    "time_series": [
      {
        "timestamp": "2024-01-15T00:00:00Z",
        "total_count": 1265,
        "avg_response_time": 195.4
      },
      {
        "timestamp": "2024-01-15T01:00:00Z",
        "total_count": 1188,
        "avg_response_time": 183.7
      }
    ]
  },
  "total_count": 2453,
  "execution_time_ms": 387,
  "customer_id": "customer_123"
}
```

### Saved Query Management

#### 4. List Saved Queries
**Endpoint**: `GET /v1/query/saved`

List saved queries for the customer with filtering and pagination.

**Query Parameters:**
- `created_by`: Filter by creator (optional)
- `query_type`: Filter by query type (optional)
- `limit`: Maximum number of queries to return (default: 50, max: 100)

**Example:**
```
GET /v1/query/saved?created_by=admin&query_type=advanced&limit=25
```

**Response:**
```json
{
  "saved_queries": [
    {
      "id": "query_123",
      "customer_id": "customer_123",
      "name": "Error Analysis Dashboard",
      "description": "Hourly error analysis for user services",
      "query_definition": {
        "filters": [
          {
            "field": "level",
            "operator": "eq",
            "value": "ERROR"
          }
        ],
        "aggregations": [
          {
            "type": "count",
            "field": "*",
            "group_by": ["service", "host"]
          }
        ]
      },
      "query_type": "advanced",
      "created_by": "admin",
      "tags": ["errors", "monitoring", "dashboard"],
      "is_public": false,
      "created_at": "2024-01-10T09:00:00Z",
      "updated_at": "2024-01-12T14:30:00Z",
      "status": "active"
    }
  ],
  "count": 1,
  "customer_id": "customer_123",
  "filters": {
    "created_by": "admin",
    "query_type": "advanced",
    "limit": 25
  }
}
```

#### 5. Save Query
**Endpoint**: `POST /v1/query/saved`

Save a query for future use with validation.

**Request Body:**
```json
{
  "name": "Performance Monitoring Query",
  "description": "Monitors response times and error rates",
  "query_definition": {
    "filters": [
      {
        "field": "service",
        "operator": "in",
        "value": ["user-service", "auth-service"]
      }
    ],
    "aggregations": [
      {
        "type": "avg",
        "field": "response_time",
        "group_by": ["service"]
      },
      {
        "type": "count",
        "field": "level",
        "group_by": ["level"]
      }
    ],
    "start_time": "2024-01-15T00:00:00Z",
    "end_time": "2024-01-15T23:59:59Z"
  },
  "query_type": "advanced",
  "tags": ["performance", "monitoring"],
  "is_public": false,
  "created_by": "analyst"
}
```

**Response:**
```json
{
  "status": "saved",
  "query_id": "query_456",
  "message": "Query saved successfully",
  "customer_id": "customer_123"
}
```

#### 6. Get Saved Query
**Endpoint**: `GET /v1/query/saved/{query_id}`

Retrieve a specific saved query by ID.

**Path Parameters:**
- `query_id`: Unique query identifier

**Response:**
```json
{
  "id": "query_456",
  "customer_id": "customer_123",
  "name": "Performance Monitoring Query",
  "description": "Monitors response times and error rates",
  "query_definition": {
    "filters": [
      {
        "field": "service", 
        "operator": "in",
        "value": ["user-service", "auth-service"]
      }
    ],
    "aggregations": [
      {
        "type": "avg",
        "field": "response_time",
        "group_by": ["service"]
      }
    ]
  },
  "query_type": "advanced",
  "created_by": "analyst",
  "tags": ["performance", "monitoring"],
  "is_public": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "status": "active"
}
```

#### 7. Update Saved Query
**Endpoint**: `PUT /v1/query/saved/{query_id}`

Update a specific saved query with validation.

**Request Body:**
```json
{
  "name": "Enhanced Performance Monitoring",
  "description": "Updated monitoring with additional metrics",
  "query_definition": {
    "filters": [
      {
        "field": "service",
        "operator": "in", 
        "value": ["user-service", "auth-service", "payment-service"]
      }
    ],
    "aggregations": [
      {
        "type": "avg",
        "field": "response_time",
        "group_by": ["service"]
      },
      {
        "type": "percentile",
        "field": "response_time",
        "percentile": 95,
        "group_by": ["service"]
      }
    ]
  },
  "tags": ["performance", "monitoring", "p95"]
}
```

**Response:**
```json
{
  "status": "updated",
  "query_id": "query_456",
  "message": "Query updated successfully",
  "customer_id": "customer_123"
}
```

#### 8. Delete Saved Query
**Endpoint**: `DELETE /v1/query/saved/{query_id}`

Delete (deactivate) a specific saved query.

**Response:**
```json
{
  "status": "deleted",
  "query_id": "query_456",
  "message": "Query deleted successfully",
  "customer_id": "customer_123"
}
```

### Query Validation & Export

#### 9. Validate Query
**Endpoint**: `POST /v1/query/validate`

Validate query structure and parameters before execution.

**Request Body:**
```json
{
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    },
    {
      "field": "ts",
      "operator": "gte",
      "value": "2024-01-15T10:00:00Z"
    },
    {
      "field": "ts",
      "operator": "lte",
      "value": "2024-01-15T09:00:00Z"
    }
  ],
  "aggregations": [
    {
      "type": "count",
      "field": "*"
    }
  ]
}
```

**Response:**
```json
{
  "valid": false,
  "errors": [
    "Start time must be before end time"
  ],
  "warnings": []
}
```

**Valid Query Response:**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Large time range may impact performance"
  ]
}
```

#### 10. Export Query Results
**Endpoint**: `POST /v1/export`

Export query results in various formats (JSON, CSV, etc.).

**Request Body:**
```json
{
  "query": {
    "filters": [
      {
        "field": "level",
        "operator": "eq",
        "value": "ERROR"
      }
    ],
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "limit": 1000
  },
  "format": "csv"
}
```

**CSV Response:**
```json
{
  "data": "timestamp,level,service,message,host\n2024-01-15T10:30:00Z,ERROR,user-service,Database timeout,host-123\n2024-01-15T10:29:45Z,ERROR,auth-service,Auth failed,host-456\n",
  "format": "csv",
  "count": 2,
  "customer_id": "customer_123"
}
```

**JSON Response:**
```json
{
  "data": [
    {
      "ts": "2024-01-15T10:30:00Z",
      "level": "ERROR",
      "service": "user-service",
      "msg": "Database timeout",
      "host": "host-123"
    },
    {
      "ts": "2024-01-15T10:29:45Z",
      "level": "ERROR", 
      "service": "auth-service",
      "msg": "Auth failed",
      "host": "host-456"
    }
  ],
  "format": "json",
  "count": 2,
  "customer_id": "customer_123"
}
```

### Basic Log Retrieval

#### 11. Get Logs (M0 Compatibility)
**Endpoint**: `GET /v1/logs`

Simple log retrieval endpoint for basic queries and M0 compatibility.

**Query Parameters:**
- `service`: Filter by service name (optional)
- `level`: Filter by log level (optional)
- `limit`: Maximum number of logs to return (default: 100)
- `offset`: Number of logs to skip (default: 0)

**Example:**
```
GET /v1/logs?service=user-service&level=ERROR&limit=50&offset=0
```

**Response:**
```json
{
  "logs": [
    {
      "ts": "2024-01-15T10:30:00Z",
      "service": "user-service",
      "level": "ERROR",
      "msg": "Database connection timeout",
      "host": "user-service-pod-123",
      "trace_id": "1234567890abcdef",
      "customer_id": "customer_123"
    },
    {
      "ts": "2024-01-15T10:29:45Z",
      "service": "user-service",
      "level": "ERROR",
      "msg": "Authentication failed",
      "host": "user-service-pod-456", 
      "trace_id": "fedcba0987654321",
      "customer_id": "customer_123"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0,
  "customer_id": "customer_123"
}
```

## Data Models

### Query Filter Model
```python
class QueryFilter(BaseModel):
    field: str = Field(..., description="Field name to filter on")
    operator: QueryOperator = Field(..., description="Filter operator")
    value: Union[str, int, float, List[Any]] = Field(..., description="Filter value(s)")
```

### Query Aggregation Model
```python
class QueryAggregation(BaseModel):
    type: str = Field(..., description="Aggregation type (count, avg, sum, max, min)")
    field: str = Field(..., description="Field to aggregate")
    group_by: List[str] = Field(default=[], description="Fields to group by")
    percentile: Optional[float] = Field(None, description="Percentile for percentile aggregations")
```

### Advanced Query Request Model
```python
class AdvancedQueryRequest(BaseModel):
    filters: List[QueryFilter] = Field(default=[], description="Query filters")
    aggregations: List[QueryAggregation] = Field(default=[], description="Aggregations to perform")
    sort: List[Dict[str, str]] = Field(default=[], description="Sort criteria")
    limit: int = Field(100, description="Maximum results to return")
    offset: int = Field(0, description="Number of results to skip")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
```

## Authentication & Headers

All query endpoints use the MiddlewareTenant dependency for authentication:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id> (automatically extracted by middleware)
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `400`: Bad request (validation error)
- `401`: Unauthorized
- `403`: Forbidden 
- `404`: Resource not found (saved query not found)
- `422`: Unprocessable entity (query validation failed)
- `500`: Internal server error (query execution failed)

**Error Response Format:**
```json
{
  "detail": "Advanced query failed: Invalid filter operator 'unknown_op'",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Performance Features

### Query Caching
- **Cache Duration**: 5 minutes (300 seconds) TTL
- **Cache Key**: MD5 hash of query data + customer_id
- **Cache Storage**: ClickHouse `query_cache_mt` table
- **Cache Hit Benefits**: ~100x faster response times for repeated queries

### Query Optimization
- **Multi-Tenant Isolation**: Automatic `customer_id` filter injection
- **Index Utilization**: Optimized for ClickHouse MergeTree indexes
- **Parallel Execution**: Concurrent filter and aggregation processing
- **Memory Management**: Streaming results for large datasets

## Code Integration

### Service Layer Integration

```python
from services.query_service import QueryService

# Initialize service
query_service = QueryService()

# Save a query
query_data = {
    'customer_id': 'customer_123',
    'name': 'Error Analysis',
    'description': 'Daily error rate analysis',
    'query_definition': {
        'filters': [
            {'field': 'level', 'operator': 'eq', 'value': 'ERROR'}
        ],
        'aggregations': [
            {'type': 'count', 'field': '*', 'group_by': ['service']}
        ]
    },
    'query_type': 'advanced',
    'tags': ['monitoring', 'errors'],
    'created_by': 'analyst'
}
result = await query_service.save_query(query_data)

# Get cached results
cached_result = await query_service.get_cached_result(query_dict, customer_id)

# List saved queries
queries = await query_service.list_saved_queries(
    customer_id='customer_123',
    query_type='advanced',
    limit=50
)

# Validate query structure
validation = await query_service.validate_query_structure(query_data)
```

### Direct Query Engine Usage

```python
from query_engine import AdvancedQueryRequest, QueryFilter, QueryOperator

# Build advanced query
query_request = AdvancedQueryRequest(
    filters=[
        QueryFilter(
            field="level",
            operator=QueryOperator.EQ,
            value="ERROR"
        ),
        QueryFilter(
            field="ts",
            operator=QueryOperator.GTE,
            value="2024-01-15T10:00:00Z"
        )
    ],
    aggregations=[
        {
            "type": "count",
            "field": "*",
            "group_by": ["service"]
        }
    ],
    limit=100
)

# Execute query
result = await query_engine.execute_query(query_request)
```

### Basic Query Example

```python
import requests

# Simple log retrieval
response = requests.get(
    "http://localhost:7080/v1/logs",
    headers={
        "Authorization": "Bearer <jwt_token>",
        "X-Customer-ID": "customer_123"
    },
    params={
        "service": "user-service",
        "level": "ERROR",
        "limit": 100
    }
)

logs = response.json()["logs"]
```

## Database Schema

**Key Query Tables:**
- `logs_raw_mt`: Raw log storage with multi-tenant isolation
- `logs_normalized_mt`: Normalized log data for complex queries
- `saved_queries_mt`: Saved query definitions and metadata
- `query_cache_mt`: Query result caching for performance

**Saved Queries Schema:**
```sql
CREATE TABLE saved_queries_mt (
    id String,
    customer_id String,
    name String,
    description String,
    query_definition String,  -- JSON
    query_type String,
    created_by String,
    tags String,             -- JSON Array
    is_public Boolean,
    created_at DateTime64(9),
    updated_at DateTime64(9),
    status String
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, updated_at)
```

**Query Cache Schema:**
```sql
CREATE TABLE query_cache_mt (
    id String,
    customer_id String,
    cache_key String,
    query_definition String,  -- JSON
    result_data String,      -- JSON
    created_at DateTime64(9),
    expires_at Float64       -- Unix timestamp
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, expires_at)
```

## Performance Characteristics

- **Simple Queries**: < 100ms for basic filters on indexed fields
- **Complex Aggregations**: < 2s for multi-dimensional grouping on 100M+ rows
- **Time-Series Queries**: < 5s for hourly bucketing over 30-day periods
- **Cache Hit Ratio**: > 80% for dashboard queries with 5-minute cache
- **Export Performance**: 10K+ records/second for CSV export
- **Saved Query Operations**: < 50ms for CRUD operations

## Query Optimization Tips

1. **Use Time Filters**: Always include time range filters for performance
2. **Index-Friendly Fields**: Filter on indexed fields (customer_id, ts, level, service)
3. **Limit Results**: Use appropriate limits for large datasets
4. **Cache Leverage**: Identical queries within 5 minutes use cached results
5. **Aggregation Order**: Group by high-cardinality fields first
6. **Export Batching**: Use pagination for large exports

## Security Considerations

- **Multi-Tenant Isolation**: Automatic customer_id filtering prevents cross-tenant data access
- **Query Validation**: Input sanitization and structure validation
- **Resource Limits**: Query timeout and result size limits
- **Audit Logging**: All query operations logged for compliance
- **Rate Limiting**: Per-tenant query rate limits

## Best Practices

1. **Query Design**: Design queries with appropriate time ranges and filters
2. **Caching Strategy**: Leverage caching for repeated dashboard queries
3. **Saved Queries**: Use saved queries for common analysis patterns
4. **Export Management**: Use appropriate formats and batch sizes for exports
5. **Performance Monitoring**: Monitor query execution times and optimize slow queries
6. **Error Handling**: Implement proper error handling for query failures

## Related Documentation

- [Query Engine Architecture](../../../wiki/Query-Engine-Architecture.md)
- [ClickHouse Optimization Guide](../../../wiki/ClickHouse-Optimization-Guide.md)
- [Multi-Tenant Query Isolation](../../../wiki/Multi-Tenant-Query-Isolation.md)
- [Advanced Query Examples](../../../wiki/Advanced-Query-Examples.md)