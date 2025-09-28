# Query API System Documentation

## Overview

The Query API System provides comprehensive log querying, analysis, and data export capabilities for the Logforge platform. This system serves as the core M2 functionality, enabling advanced log searches, aggregations, time-series analysis, and saved query management with full multi-tenant isolation.

## Architecture

### Core Components
- **Query Router** (`/apps/api/routers/query.py`): 9 endpoints for comprehensive query operations
- **Query Engine** (`/apps/api/query_engine.py`): Advanced query processing and optimization
- **Query Service** (`/apps/api/services/query_service.py`): Business logic and caching
- **Query DAO** (`/apps/api/dao/query_dao.py`): Database access layer with ClickHouse optimization

### Key Features
- **Advanced Query Processing**: Complex filters, aggregations, and sorting
- **Time-Series Analysis**: Trend analysis with configurable intervals
- **Saved Query Management**: CRUD operations for reusable queries
- **Multi-Format Export**: JSON, CSV export capabilities
- **Query Validation**: Real-time query structure validation
- **Performance Optimization**: Result caching with 5-minute TTL
- **Multi-Tenant Isolation**: Complete tenant data separation

## API Endpoints

### 1. Advanced Query Operations

#### POST /v1/query/advanced
**Purpose**: Execute complex log queries with filters, aggregations, and analysis

**Authentication**: Bearer token + X-Customer-ID header
**Subscription**: Requires `queries.*` or `query.advanced` feature

**Request Body**:
```json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T23:59:59Z",
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    },
    {
      "field": "service",
      "operator": "contains", 
      "value": "api"
    }
  ],
  "text_search": "error",
  "sort_field": "ts",
  "sort_order": "desc",
  "limit": 100,
  "offset": 0,
  "aggregations": [
    {
      "field": "service",
      "type": "count"
    }
  ]
}
```

**Response**:
```json
{
  "logs": [
    {
      "ts": "2024-01-01T10:30:00Z",
      "level": "ERROR",
      "service": "api-service",
      "msg": "Database connection failed",
      "host": "api-server-1",
      "trace_id": "abc123",
      "customer_id": "tenant-uuid"
    }
  ],
  "total_count": 1247,
  "aggregations": {
    "service": {
      "api-service": 856,
      "auth-service": 391
    }
  },
  "execution_time_ms": 45,
  "customer_id": "tenant-uuid"
}
```

**Supported Filter Operators**:
- `eq`, `ne`: Exact match/not match
- `gt`, `gte`, `lt`, `lte`: Numeric comparisons
- `contains`, `starts_with`, `ends_with`: Text matching
- `regex`: Regular expression matching
- `in`, `not_in`: Array matching

#### POST /v1/query/aggregate
**Purpose**: Perform aggregation operations on log data with grouping

**Request Body**:
```json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T23:59:59Z",
  "group_by": ["service", "level"],
  "aggregations": [
    {
      "field": "service",
      "type": "count"
    }
  ],
  "filters": [
    {
      "field": "level",
      "operator": "in",
      "value": ["ERROR", "WARN"]
    }
  ]
}
```

**Response**:
```json
{
  "aggregations": {
    "service": {
      "api-service": 425,
      "auth-service": 189,
      "db-service": 78
    }
  },
  "group_by": ["service", "level"],
  "total_groups": 12,
  "execution_time_ms": 23,
  "customer_id": "tenant-uuid"
}
```

#### POST /v1/query/timeseries
**Purpose**: Time-series analysis for trends and pattern identification

**Request Body**:
```json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T23:59:59Z",
  "interval": "1h",
  "metrics": ["count"],
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    }
  ],
  "group_by": ["service"],
  "aggregations": [
    {
      "field": "*",
      "type": "count"
    }
  ],
  "granularity": "hour"
}
```

**Response**:
```json
{
  "buckets": [
    {
      "timestamp": "2024-01-01T10:00:00Z",
      "count": 45,
      "groups": {
        "api-service": 30,
        "auth-service": 15
      }
    },
    {
      "timestamp": "2024-01-01T11:00:00Z", 
      "count": 67,
      "groups": {
        "api-service": 42,
        "auth-service": 25
      }
    }
  ],
  "aggregations": {
    "total_events": 2845,
    "avg_per_hour": 118.5
  },
  "total_count": 2845,
  "execution_time_ms": 78,
  "customer_id": "tenant-uuid"
}
```

**Supported Intervals**: `1m`, `5m`, `15m`, `30m`, `1h`, `6h`, `12h`, `24h`

### 2. Saved Query Management

#### GET /v1/query/saved
**Purpose**: List saved queries with optional filtering

**Query Parameters**:
- `created_by`: Filter by creator (optional)
- `query_type`: Filter by query type (optional)  
- `limit`: Maximum results (default: 50)

**Response**:
```json
{
  "saved_queries": [
    {
      "query_id": "query-uuid-1",
      "name": "Daily Error Analysis",
      "description": "Analyze daily error patterns across all services",
      "query_definition": {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T23:59:59Z",
        "filters": [
          {
            "field": "level",
            "operator": "eq", 
            "value": "ERROR"
          }
        ]
      },
      "query_type": "advanced",
      "created_by": "john.doe@company.com",
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T14:30:00Z",
      "tags": ["errors", "daily-analysis"],
      "customer_id": "tenant-uuid"
    }
  ],
  "total": 15,
  "customer_id": "tenant-uuid"
}
```

#### POST /v1/query/saved
**Purpose**: Save a query for future reuse

**Request Body**:
```json
{
  "name": "Weekly Performance Report",
  "description": "Weekly performance analysis for all services",
  "query_definition": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-07T23:59:59Z",
    "filters": [
      {
        "field": "level",
        "operator": "eq",
        "value": "ERROR"
      }
    ],
    "aggregations": [
      {
        "field": "service",
        "type": "count"
      }
    ]
  },
  "query_type": "advanced",
  "created_by": "analyst@company.com",
  "tags": ["performance", "weekly"]
}
```

**Response**:
```json
{
  "status": "saved",
  "query_id": "query-uuid-new",
  "message": "Query saved successfully",
  "created_at": "2024-01-01T15:45:00Z"
}
```

#### GET /v1/query/saved/{query_id}
**Purpose**: Retrieve specific saved query details

**Response**:
```json
{
  "query_id": "query-uuid-1",
  "name": "Daily Error Analysis", 
  "description": "Analyze daily error patterns across all services",
  "query_definition": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T23:59:59Z",
    "filters": [
      {
        "field": "level",
        "operator": "eq",
        "value": "ERROR"
      }
    ]
  },
  "query_type": "advanced",
  "created_by": "john.doe@company.com",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T14:30:00Z",
  "tags": ["errors", "daily-analysis"],
  "customer_id": "tenant-uuid"
}
```

#### PUT /v1/query/saved/{query_id}
**Purpose**: Update existing saved query

**Request Body**:
```json
{
  "name": "Updated Daily Error Analysis",
  "description": "Enhanced daily error analysis with service breakdown",
  "tags": ["errors", "daily-analysis", "service-breakdown"]
}
```

**Response**:
```json
{
  "status": "updated",
  "query_id": "query-uuid-1",
  "message": "Query updated successfully",
  "updated_at": "2024-01-01T16:20:00Z"
}
```

#### DELETE /v1/query/saved/{query_id}
**Purpose**: Remove saved query

**Response**:
```json
{
  "status": "deleted",
  "query_id": "query-uuid-1", 
  "message": "Query deleted successfully"
}
```

### 3. Query Validation & Export

#### POST /v1/query/validate
**Purpose**: Validate query structure and parameters before execution

**Request Body**:
```json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z",
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "ERROR"
    }
  ],
  "aggregations": [
    {
      "field": "service",
      "type": "count"
    }
  ]
}
```

**Response (Valid)**:
```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "estimated_cost": {
    "rows_scanned": 1500000,
    "processing_time": "2.3s",
    "resource_usage": "moderate"
  }
}
```

**Response (Invalid)**:
```json
{
  "valid": false,
  "errors": [
    "End time must be after start time",
    "Filter field 'unknown_field' is not supported"
  ],
  "warnings": [
    "Large time range may result in slow query performance"
  ],
  "suggestions": [
    "Consider adding more specific filters",
    "Use smaller time windows for better performance"
  ]
}
```

#### POST /v1/export
**Purpose**: Export query results in various formats

**Authentication**: Bearer token + X-Customer-ID header
**Subscription**: Requires `export.*` or `export.basic` feature

**Request Body**:
```json
{
  "query": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T23:59:59Z",
    "filters": [
      {
        "field": "level",
        "operator": "eq",
        "value": "ERROR"
      }
    ],
    "limit": 1000
  },
  "format": "csv"
}
```

**JSON Export Response**:
```json
{
  "data": [
    {
      "ts": "2024-01-01T10:30:00Z",
      "level": "ERROR", 
      "service": "api-service",
      "message": "Database connection failed",
      "host": "api-server-1"
    }
  ],
  "format": "json",
  "count": 245,
  "customer_id": "tenant-uuid"
}
```

**CSV Export Response**:
```json
{
  "data": "timestamp,level,service,message,host\n2024-01-01T10:30:00Z,ERROR,api-service,Database connection failed,api-server-1\n2024-01-01T10:31:15Z,ERROR,auth-service,Token validation failed,auth-server-2\n",
  "format": "csv",
  "count": 245,
  "customer_id": "tenant-uuid"
}
```

**Supported Export Formats**: `json`, `csv`

### 4. Basic Log Retrieval (M0 Compatibility)

#### GET /v1/logs
**Purpose**: Simple log retrieval with basic filtering

**Query Parameters**:
- `service`: Filter by service name (optional)
- `level`: Filter by log level (optional)
- `limit`: Maximum results (default: 100)
- `offset`: Skip results for pagination (default: 0)

**Response**:
```json
{
  "logs": [
    {
      "ts": "2024-01-01T10:30:00Z",
      "service": "api-service",
      "level": "ERROR",
      "msg": "Database connection failed",
      "host": "api-server-1",
      "trace_id": "abc123",
      "customer_id": "tenant-uuid"
    }
  ],
  "total": 1247,
  "limit": 100,
  "offset": 0,
  "customer_id": "tenant-uuid"
}
```

## Performance & Optimization

### Query Performance
- **Typical Response Times**: < 1.5s for 24h window on 200M rows
- **ClickHouse Optimization**: Materialized views and pre-aggregated data
- **Index Usage**: Optimized for timestamp and customer_id filtering
- **Memory Management**: Streaming results for large datasets

### Caching Strategy
- **Result Caching**: 5-minute TTL for expensive queries
- **Query Plan Caching**: Optimized execution plans cached per customer
- **Cache Invalidation**: Automatic invalidation on data updates
- **Memory Limits**: Configurable cache size limits per tenant

### Resource Management
- **Query Timeouts**: 30s execution timeout for safety
- **Resource Limits**: CPU and memory limits per query
- **Priority Queues**: Interactive vs batch query prioritization
- **Rate Limiting**: Per-tenant query rate limits

## Multi-Tenancy & Security

### Data Isolation
- **Tenant Filtering**: Automatic `customer_id` injection in all queries
- **Row-Level Security**: Database-level tenant isolation
- **Cross-Tenant Protection**: Middleware validation prevents access breaches
- **Audit Logging**: Complete query audit trail per tenant

### Authentication & Authorization
- **Bearer Tokens**: JWT-based authentication required
- **Header Validation**: `X-Customer-ID` header mandatory
- **Role-Based Access**: Different access levels (admin, analyst, viewer)
- **Feature Gates**: Subscription-based feature access control

### Subscription Requirements
| **Endpoint** | **Required Feature** | **Subscription Tier** |
|--------------|---------------------|----------------------|
| `/query/advanced` | `queries.*` or `query.advanced` | Professional+ |
| `/query/aggregate` | `queries.*` or `query.aggregation` | Professional+ |
| `/query/timeseries` | `queries.*` or `query.timeseries` | Professional+ |
| `/query/saved/*` | `queries.*` or `query.saved` | Starter+ |
| `/query/validate` | `queries.*` or `query.validation` | Starter+ |
| `/export` | `export.*` or `export.basic` | Professional+ |
| `/logs` | `ingestion.*` or `query.basic` | All Tiers |

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid query structure: missing required field 'start_time'"
}
```

#### 403 Forbidden - Subscription
```json
{
  "error": "feature_not_subscribed",
  "message": "Feature 'export.basic' not included in subscription",
  "required_feature": "export.basic",
  "current_subscription": ["queries.*", "ingestion.*"],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade"
}
```

#### 403 Forbidden - Tenant Access
```json
{
  "detail": "No access to tenant: tenant-uuid"
}
```

#### 404 Not Found
```json
{
  "detail": "Query not found"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "start_time"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

#### 500 Server Error
```json
{
  "detail": "Query execution failed: database connection timeout"
}
```

## Integration Examples

### Advanced Log Analysis
```python
import httpx
import json

async def analyze_errors_by_service():
    headers = {
        "Authorization": "Bearer your-jwt-token",
        "X-Customer-ID": "your-tenant-id",
        "Content-Type": "application/json"
    }
    
    query = {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T23:59:59Z",
        "filters": [
            {
                "field": "level",
                "operator": "eq",
                "value": "ERROR"
            }
        ],
        "aggregations": [
            {
                "field": "service",
                "type": "count"
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.logforge.com/v1/query/advanced",
            headers=headers,
            json=query
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Found {result['total_count']} errors")
            print("Errors by service:", result['aggregations']['service'])
        else:
            print(f"Query failed: {response.text}")
```

### Time-Series Dashboard
```python
async def get_hourly_error_trends():
    query = {
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T23:59:59Z",
        "interval": "1h",
        "filters": [
            {
                "field": "level",
                "operator": "in",
                "value": ["ERROR", "WARN"]
            }
        ],
        "group_by": ["level"],
        "aggregations": [
            {
                "field": "*",
                "type": "count"
            }
        ]
    }
    
    response = await client.post("/v1/query/timeseries", json=query)
    buckets = response.json()["buckets"]
    
    # Process for dashboard visualization
    for bucket in buckets:
        print(f"Hour {bucket['timestamp']}: {bucket['count']} events")
```

### Saved Query Management
```python
async def create_and_manage_saved_query():
    # Save a frequently-used query
    save_request = {
        "name": "Daily Security Events",
        "description": "Security-related log analysis",
        "query_definition": {
            "start_time": "2024-01-01T00:00:00Z", 
            "end_time": "2024-01-01T23:59:59Z",
            "filters": [
                {
                    "field": "service",
                    "operator": "eq",
                    "value": "security-service"
                }
            ]
        },
        "query_type": "advanced",
        "tags": ["security", "daily"]
    }
    
    # Save the query
    save_response = await client.post("/v1/query/saved", json=save_request)
    query_id = save_response.json()["query_id"]
    
    # Later, retrieve and execute
    saved_query = await client.get(f"/v1/query/saved/{query_id}")
    
    # Execute the saved query
    results = await client.post(
        "/v1/query/advanced",
        json=saved_query.json()["query_definition"]
    )
```

## Best Practices

### Query Optimization
1. **Use Specific Time Ranges**: Avoid overly broad time windows
2. **Add Selective Filters**: Filter early to reduce data processing
3. **Limit Result Sets**: Use appropriate `limit` values for UI pagination
4. **Cache Frequently-Used Queries**: Save complex queries for reuse
5. **Monitor Query Performance**: Use execution times to identify slow queries

### Multi-Tenant Considerations
1. **Always Include Tenant Headers**: `X-Customer-ID` is mandatory
2. **Validate Permissions**: Check subscription features before query execution
3. **Handle Cross-Tenant Errors**: Properly handle 403 responses
4. **Implement Rate Limiting**: Prevent query abuse with client-side limits
5. **Audit Query Usage**: Log all query executions for billing and monitoring

### Error Handling
1. **Validate Before Execution**: Use `/query/validate` for complex queries
2. **Implement Retries**: Handle transient failures with exponential backoff
3. **Graceful Degradation**: Provide fallback options for failed queries
4. **User-Friendly Messages**: Convert technical errors to user-readable messages
5. **Monitor Error Rates**: Track query success/failure metrics

### Export Best Practices
1. **Limit Export Size**: Use pagination for large datasets
2. **Choose Appropriate Format**: JSON for structured data, CSV for analytics
3. **Handle Large Exports**: Consider streaming or background processing
4. **Validate Export Permissions**: Check subscription limits before export
5. **Optimize for Download**: Compress large export files when possible

## Integration with Other Systems

### Dashboard Integration
- **Real-Time Updates**: WebSocket support for live dashboard updates
- **Widget Queries**: Optimized queries for dashboard widgets
- **Caching Strategy**: Aggressive caching for dashboard performance
- **Auto-Refresh**: Configurable auto-refresh intervals

### Alerting Integration  
- **Query-Based Alerts**: Use saved queries as alert conditions
- **Threshold Monitoring**: Aggregate queries for threshold-based alerts
- **Pattern Detection**: Complex pattern matching with query filters
- **Historical Comparison**: Time-series queries for trend-based alerts

### External Tools
- **BI Tool Integration**: Export APIs for business intelligence tools
- **SIEM Integration**: Query APIs for security information management
- **DevOps Integration**: Automated queries for operational monitoring
- **API Gateway**: RESTful APIs for third-party tool integration

This comprehensive query system provides the foundation for advanced log analysis, enabling customers to extract valuable insights from their log data with enterprise-grade performance, security, and multi-tenancy support.