# POST /v1/query/advanced API Runbook

## Overview
This runbook documents the `POST /v1/query/advanced` API endpoint for advanced log querying with filters, aggregations, time-series analysis, and real-time caching in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/query/advanced`  
**Content-Type**: `application/json`  
**Authentication**: Bearer token + X-Customer-ID header  
**Response Model**: QueryResponse with logs, aggregations, and metadata

## Database Tables Accessed

### 1. logs_raw_mt (Primary Read Access)
**Purpose**: Main log storage table for raw log data querying  
**Access Method**: ClickHouse SELECT queries with advanced filtering and aggregations  
**Key Fields Read**:
- `ts`: Log timestamp (DateTime64(3, 'UTC'))
- `service`: Service name that generated the log
- `level`: Log level (info, warn, error, debug, etc.)
- `msg`: Log message content
- `host`: Hostname/server that generated the log
- `trace_id`: Distributed tracing identifier
- `customer_id`: Tenant isolation identifier
- `*`: All available fields based on query configuration

**Query Pattern**: 
```sql
SELECT [fields] FROM logs_raw_mt 
WHERE customer_id = '{customer_id}' 
  AND ts BETWEEN '{start_time}' AND '{end_time}'
  [AND additional_filters]
[GROUP BY fields]
[ORDER BY sort_field sort_order]
LIMIT {limit} OFFSET {offset}
```

### 2. logs_normalized_mt (Optimized Read Access)
**Purpose**: Normalized log storage for complex queries and aggregations  
**Access Method**: Automatic table selection based on query complexity  
**Usage**: Selected for queries with heavy aggregations or complex filters  
**Schema**: Similar to logs_raw_mt but with optimized column types and indexing

### 3. query_cache_mt (Read/Write Access)
**Purpose**: Query result caching for performance optimization  
**Access Method**: Key-based lookup and TTL-based storage  
**Key Fields**:
- `id`: Unique cache entry identifier (UUID)
- `customer_id`: Tenant isolation for cached results
- `cache_key`: Hash-based key for query lookup
- `query_definition`: JSON serialized query parameters
- `result_data`: JSON serialized query results
- `created_at`: Cache entry creation timestamp
- `expires_at`: Cache expiration timestamp (5-minute TTL)

**Cache Pattern**:
```sql
-- Cache Lookup
SELECT result_data FROM query_cache_mt 
WHERE cache_key = '{hash}' AND customer_id = '{customer_id}' 
  AND expires_at > NOW()

-- Cache Insert  
INSERT INTO query_cache_mt (id, customer_id, cache_key, query_definition, result_data, created_at, expires_at)
VALUES ('{uuid}', '{customer_id}', '{hash}', '{query_json}', '{result_json}', NOW(), NOW() + 300)
```

## Request Format

### Required Headers
```http
POST /v1/query/advanced HTTP/1.1
Host: localhost:7080
Content-Type: application/json
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Request Body Schema (AdvancedQueryRequest)

#### Basic Time Range (Required)
```json
{
  "start_time": "2025-10-09T00:00:00Z",
  "end_time": "2025-10-09T23:59:59Z"
}
```

#### Complete Request Example
```json
{
  "start_time": "2025-10-09T00:00:00Z",
  "end_time": "2025-10-09T23:59:59Z",
  "filters": [
    {
      "field": "level",
      "operator": "eq",
      "value": "error"
    },
    {
      "field": "service",
      "operator": "in",
      "value": ["api-gateway", "auth-service"]
    }
  ],
  "text_search": "authentication failed",
  "aggregations": [
    {
      "type": "count",
      "field": "*",
      "alias": "error_count"
    },
    {
      "type": "unique",
      "field": "service",
      "alias": "affected_services"
    }
  ],
  "group_by": ["service", "level"],
  "time_series": true,
  "time_granularity": "hour",
  "sort_field": "ts",
  "sort_order": "desc",
  "limit": 1000,
  "offset": 0,
  "include_fields": ["ts", "level", "service", "msg", "host"],
  "exclude_fields": ["internal_debug_info"]
}
```

### Filter Operators
- **eq**: equals (`"level": "error"`)
- **ne**: not equals (`"level": "debug"`)
- **gt**: greater than (`"processing_time": 1000`)
- **gte**: greater than or equal
- **lt**: less than
- **lte**: less than or equal  
- **contains**: string contains (`"msg": "failed"`)
- **starts_with**: string starts with (`"service": "api-"`)
- **ends_with**: string ends with (`"host": "-prod"`)
- **regex**: regular expression match (`"msg": "\\d{3}-\\d{3}-\\d{4}"`)
- **in**: value in list (`"service": ["api", "web", "db"]`)
- **not_in**: value not in list

### Aggregation Types
- **count**: Count of records
- **sum**: Sum of numeric field values (handles both numeric and string fields)
- **avg**: Average of numeric field values (handles both numeric and string fields)
- **min**: Minimum value in field
- **max**: Maximum value in field
- **percentile**: Percentile calculation (specify percentile parameter)
- **unique**: Unique values in field (cardinality)
- **cardinality**: Distinct count of field values

#### Numeric Field Handling
The query engine automatically detects field types for optimal aggregation:
- **Numeric fields** (`severity_num`, `status`, `facility`): Direct aggregation without conversion
- **String fields**: Converted using `toFloat64OrZero()` for sum/avg operations
- **Mixed field queries**: Automatically handled based on field type detection

### Time Granularity Options
- **second**: 1-second buckets
- **minute**: 1-minute buckets  
- **hour**: 1-hour buckets (default)
- **day**: 1-day buckets
- **week**: 1-week buckets
- **month**: 1-month buckets

## Sample cURL Commands

### Basic Error Log Query
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T00:00:00Z",
    "end_time": "2025-10-09T23:59:59Z",
    "filters": [
      {
        "field": "level", 
        "operator": "eq", 
        "value": "error"
      }
    ],
    "limit": 100
  }'
```

### Advanced Query with Aggregations
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T00:00:00Z",
    "end_time": "2025-10-09T23:59:59Z",
    "filters": [
      {
        "field": "service",
        "operator": "in",
        "value": ["api-gateway", "auth-service"]
      }
    ],
    "aggregations": [
      {
        "type": "count",
        "field": "*",
        "alias": "total_logs"
      },
      {
        "type": "unique",
        "field": "level",
        "alias": "log_levels"
      }
    ],
    "group_by": ["service"],
    "time_series": true,
    "time_granularity": "hour"
  }'
```

### Text Search with Time Series
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T00:00:00Z", 
    "end_time": "2025-10-09T23:59:59Z",
    "text_search": "authentication failed",
    "time_series": true,
    "time_granularity": "minute",
    "aggregations": [
      {
        "type": "count",
        "field": "*", 
        "alias": "failures_per_minute"
      }
    ]
  }'
```

### Complex Multi-Filter Query
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T12:00:00Z",
    "end_time": "2025-10-09T13:00:00Z", 
    "filters": [
      {
        "field": "level",
        "operator": "in",
        "value": ["error", "warn"]
      },
      {
        "field": "msg",
        "operator": "contains", 
        "value": "timeout"
      },
      {
        "field": "service",
        "operator": "starts_with",
        "value": "api-"
      }
    ],
    "group_by": ["service", "level"],
    "sort_field": "ts",
    "sort_order": "desc",
    "limit": 500
  }'
```

## Response Format

### Success Response (200 OK)
```json
{
  "logs": [
    {
      "ts": "2025-10-09T12:34:56.789Z",
      "service": "api-gateway", 
      "level": "error",
      "msg": "Authentication timeout for user request",
      "host": "prod-api-01",
      "trace_id": "abc123def456",
      "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
    },
    {
      "ts": "2025-10-09T12:33:45.678Z",
      "service": "auth-service",
      "level": "warn", 
      "msg": "Slow authentication response detected",
      "host": "prod-auth-02",
      "trace_id": "xyz789uvw123",
      "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
    }
  ],
  "aggregations": {
    "total_logs": 1247,
    "log_levels": ["error", "warn", "info"],
    "time_series": [
      {
        "timestamp": "2025-10-09T12:00:00Z",
        "bucket": "2025-10-09 12:00:00",
        "failures_per_minute": 15
      },
      {
        "timestamp": "2025-10-09T12:01:00Z", 
        "bucket": "2025-10-09 12:01:00",
        "failures_per_minute": 23
      }
    ],
    "group_by_results": [
      {
        "service": "api-gateway",
        "level": "error", 
        "count": 45
      },
      {
        "service": "auth-service",
        "level": "warn",
        "count": 12
      }
    ]
  },
  "total_count": 1247,
  "execution_time_ms": 245.6,
  "has_more": true,
  "next_offset": 1000,
  "query_info": {
    "cache_hit": false,
    "table_used": "logs_raw_mt",
    "query_complexity": "medium",
    "optimization_applied": true
  },
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

### Cached Response (200 OK)
```json
{
  "logs": [...],
  "aggregations": {...},
  "total_count": 1247,
  "execution_time_ms": 12.3,
  "query_info": {
    "cache_hit": true,
    "cache_age_seconds": 45,
    "original_execution_time_ms": 245.6
  },
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

### Error Responses
```json
// Query engine not initialized
{
  "detail": "Query engine not initialized"
}

// Invalid time range
{
  "detail": "Advanced query failed: start_time must be before end_time"
}

// Authentication error
{
  "detail": "Invalid or expired session"
}

// Permission error
{
  "detail": "Insufficient permissions for /v1/query/advanced"
}

// Query execution error
{
  "detail": "Advanced query failed: Invalid field 'nonexistent_field' in filter"
}
```

## Code Flow Analysis

### Main Request Processing
1. **Authentication**: JWT token validation + X-Customer-ID header verification
2. **Request Validation**: Validate AdvancedQueryRequest model and required fields
3. **Tenant Isolation**: Automatically add customer_id filter to ensure multi-tenant security
4. **Cache Lookup**: Check query_cache_mt for existing results using query hash
5. **Cache Hit**: Return cached QueryResponse if valid cache entry found
6. **Query Execution**: Execute advanced query against logs_raw_mt or logs_normalized_mt
7. **Result Processing**: Process aggregations, time-series, and apply sorting/limiting
8. **Cache Storage**: Store result in query_cache_mt with 5-minute TTL
9. **Response**: Return QueryResponse with logs, aggregations, and execution metadata

### Query Engine Logic
```python
# Automatic tenant isolation enforcement
if not query_request.filters:
    query_request.filters = []
query_request.filters.append(QueryFilter(
    field="customer_id",
    operator=QueryOperator.EQ, 
    value=customer_id
))

# Cache key generation based on query parameters
query_dict = query_request.model_dump(mode='json')
cache_key = hashlib.md5(json.dumps(query_dict, sort_keys=True).encode()).hexdigest()

# Table selection optimization
table = query_engine._select_optimal_table(query_request)
# Returns 'logs_raw_mt' for simple queries, 'logs_normalized_mt' for complex aggregations

# Query result caching with TTL
await query_service.cache_query_result(
    query_data=query_dict,
    customer_id=customer_id,
    result=result.model_dump(mode='json'),
    ttl_seconds=300  # 5-minute cache TTL
)
```

### Cache Strategy
- **Cache Key**: MD5 hash of serialized query parameters + customer_id
- **TTL**: 5 minutes (300 seconds) for query results
- **Cache Hit Logic**: Exact query match within TTL window
- **Cache Storage**: JSON serialized query definition and results
- **Cache Invalidation**: Automatic expiration based on expires_at timestamp

## Authentication & Authorization

### Required Authentication
- **JWT Bearer Token**: Must be valid and non-expired
- **X-Customer-ID Header**: Must match authenticated user's tenant ID
- **Tenant Isolation**: Automatic enforcement via customer_id filter injection
- **Permission**: Requires `queries:write:tenant` permission for POST operations

### Security Features
- **Mandatory Tenant Filtering**: Every query includes `customer_id = '{customer_id}'` filter
- **SQL Injection Protection**: Parameterized queries and filter validation
- **Input Validation**: Pydantic model validation for all request parameters
- **Rate Limiting**: Enforced through authentication middleware
- **Cache Isolation**: Cached results are tenant-specific and cannot cross tenant boundaries

## Performance Characteristics

### Response Time Targets
- **Simple Query**: < 200ms for basic filters on recent data (last 24 hours)
- **Complex Aggregations**: < 1s for multi-field group by and aggregations
- **Time Series Queries**: < 2s for hourly buckets over 7-day periods
- **Cached Queries**: < 50ms for cache hits
- **Large Result Sets**: < 3s for 10,000+ records with aggregations

### Optimization Features
- **Intelligent Caching**: 5-minute TTL cache for identical queries
- **Table Selection**: Automatic selection between raw and normalized tables
- **Index Usage**: Leverages ClickHouse customer_id and timestamp indexes
- **Query Optimization**: Built-in query complexity analysis and optimization
- **Result Limiting**: Configurable limits with pagination support (max 10,000 per query)

### Resource Usage
- **Memory**: Efficient streaming for large aggregation results
- **CPU**: Optimized ClickHouse queries with proper indexing and filtering
- **Storage**: Compressed cache storage with automatic TTL cleanup
- **Network**: Minimal data transfer with field selection and compression

### Cache Performance
- **Cache Hit Rate**: ~70-80% for common dashboard and monitoring queries
- **Memory Usage**: JSON compressed storage, ~50% space reduction
- **Lookup Speed**: Sub-millisecond cache key lookups
- **Storage Overhead**: ~10MB cache storage per 1000 cached queries

## Error Handling

### Query Engine Errors
- **Initialization Failure**: 500 error with "Query engine not initialized"
- **Invalid Filters**: 500 error with specific field/operator validation details
- **Time Range Errors**: 500 error for invalid start_time/end_time combinations
- **Table Access Errors**: 500 error with database connection details

### Database Errors
- **Connection Failure**: 500 error with ClickHouse connection timeout details
- **Query Timeout**: 500 error with query execution timeout information
- **Invalid Query**: 500 error with SQL syntax or semantic error details
- **Resource Limits**: 500 error when query exceeds memory or time limits

### Authentication Errors
- **Invalid Token**: 401 Unauthorized response
- **Missing Headers**: 401 Unauthorized for missing Authorization or X-Customer-ID
- **Tenant Mismatch**: 403 Forbidden for unauthorized tenant access
- **Permission Denied**: 403 Forbidden for insufficient query permissions

### Validation Errors
- **Request Body**: 422 Unprocessable Entity for invalid JSON or missing required fields
- **Filter Validation**: 500 error for invalid operator/field combinations
- **Aggregation Errors**: 500 error for invalid aggregation type/field combinations
- **Limit Violations**: 400 error for limits exceeding maximum allowed values

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **Query Performance**: Response times for different query complexities
- **Cache Hit Rate**: Percentage of queries served from cache vs database
- **Database Load**: ClickHouse CPU and memory usage during complex queries
- **Error Rate**: Failed queries vs successful queries over time
- **Table Selection**: Usage patterns between raw and normalized tables

### Common Issues
1. **Slow Queries**: Large time ranges without proper filtering or indexing
2. **Cache Misses**: Slight variations in query parameters preventing cache hits
3. **Memory Exhaustion**: Very large aggregation queries without proper limits
4. **Authentication Failures**: Expired tokens or incorrect tenant IDs
5. **Time Zone Issues**: Incorrect timestamp formatting or timezone handling
6. **ClickHouse Type Errors**: `toFloat64OrZero()` errors on numeric fields
7. **Field Selection Errors**: "tuple index out of range" with `include_fields`
8. **Missing Column Errors**: Using non-existent fields in filters or aggregations

### Debugging Steps
1. **Check Authentication**: Verify JWT token validity and X-Customer-ID header
2. **Validate Request**: Ensure proper JSON format and required fields
3. **Test Query Complexity**: Start with simple queries and add complexity incrementally
4. **Monitor Cache Performance**: Check cache hit rates and query hash generation
5. **Analyze Query Execution**: Review ClickHouse query logs for slow operations
6. **Resource Monitoring**: Check server CPU/memory during high-load periods

### Specific Issue Troubleshooting

#### ClickHouse Type Conversion Errors
**Error**: `Illegal type UInt8 of first argument of function toFloat64OrZero`  
**Cause**: Trying to use `toFloat64OrZero()` on already numeric fields  
**Solution**: Use only existing database fields in aggregations:
- ✅ **Numeric fields**: `severity_num`, `status`, `facility` (use directly)
- ✅ **String fields**: `level`, `service`, `msg` (converted automatically)

#### Field Selection Issues  
**Error**: `tuple index out of range`  
**Cause**: Using `include_fields` with non-existent columns or field count mismatch  
**Solution**: Use only existing table fields in `include_fields`:
- ✅ **Available fields**: `ts`, `host`, `service`, `level`, `msg`, `trace_id`, `span_id`, `attrs`, `status`, `src_ip`, `user_id`, `customer_id`

#### Missing Column Errors
**Error**: `Missing columns: 'field_name' while processing query`  
**Cause**: Using fields that don't exist in logs_raw_mt table  
**Solution**: Replace with actual table fields:
- ❌ `response_time`, `event_type`, `revenue`, `region`, `user_agent`
- ✅ `severity_num`, `status`, `level`, `service`, `msg`, `trace_id`

### Performance Tuning
1. **Query Optimization**: Use appropriate filters to reduce data scan volume
2. **Time Range Limiting**: Avoid queries spanning more than 30 days without pagination
3. **Aggregation Efficiency**: Group by low-cardinality fields for better performance
4. **Cache Utilization**: Structure repeated queries to maximize cache hit rates
5. **Index Strategy**: Ensure customer_id and timestamp indexes are optimized

## Usage Examples

### Security Operations Center (SOC) Queries

#### Real-Time Threat Detection
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T12:00:00Z",
    "end_time": "2025-10-09T13:00:00Z",
    "filters": [
      {
        "field": "level",
        "operator": "in", 
        "value": ["error", "critical"]
      },
      {
        "field": "msg",
        "operator": "regex",
        "value": "(failed|denied|blocked|unauthorized)"
      }
    ],
    "aggregations": [
      {
        "type": "count",
        "field": "*",
        "alias": "security_events"
      },
      {
        "type": "unique", 
        "field": "src_ip",
        "alias": "unique_sources"
      }
    ],
    "group_by": ["service", "src_ip"],
    "time_series": true,
    "time_granularity": "minute"
  }'
```

#### Performance Monitoring Dashboard
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-09T00:00:00Z",
    "end_time": "2025-10-09T23:59:59Z",
    "filters": [
      {
        "field": "severity_num",
        "operator": "gte",
        "value": 3
      },
      {
        "field": "service",
        "operator": "ne",
        "value": "health-check"
      }
    ],
    "aggregations": [
      {
        "type": "avg",
        "field": "severity_num", 
        "alias": "avg_severity"
      },
      {
        "type": "max",
        "field": "severity_num",
        "alias": "max_severity"
      },
      {
        "type": "count",
        "field": "*",
        "alias": "high_severity_events"
      }
    ],
    "group_by": ["service"],
    "time_series": true,
    "time_granularity": "hour"
  }'
```

### Business Intelligence Queries

#### User Activity Analysis
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "start_time": "2025-10-01T00:00:00Z",
    "end_time": "2025-10-31T23:59:59Z",
    "filters": [
      {
        "field": "event_type",
        "operator": "in",
        "value": ["login", "logout", "page_view", "transaction"]
      }
    ],
    "aggregations": [
      {
        "type": "count",
        "field": "*",
        "alias": "total_events"
      },
      {
        "type": "unique",
        "field": "user_id", 
        "alias": "active_users"
      }
    ],
    "group_by": ["event_type"],
    "time_series": true,
    "time_granularity": "day"
  }'
```

## Integration Examples

### Log Analysis Script
```python
import requests
import json
from datetime import datetime, timedelta

class LogAnalyzer:
    def __init__(self, api_url, auth_token, tenant_id):
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
    
    def query_error_trends(self, hours_back=24):
        """Analyze error trends over specified time period"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        query = {
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z", 
            "filters": [
                {
                    "field": "level",
                    "operator": "eq",
                    "value": "error"
                }
            ],
            "aggregations": [
                {
                    "type": "count",
                    "field": "*",
                    "alias": "error_count"
                }
            ],
            "group_by": ["service"],
            "time_series": True,
            "time_granularity": "hour"
        }
        
        response = requests.post(
            f"{self.api_url}/v1/query/advanced",
            headers=self.headers,
            json=query
        )
        return response.json()
    
    def detect_anomalies(self, service_name, threshold=1000):
        """Detect performance anomalies for specific service"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=6)
        
        query = {
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "filters": [
                {
                    "field": "service",
                    "operator": "eq", 
                    "value": service_name
                },
                {
                    "field": "response_time",
                    "operator": "gt",
                    "value": threshold
                }
            ],
            "aggregations": [
                {
                    "type": "count",
                    "field": "*",
                    "alias": "slow_requests"
                },
                {
                    "type": "avg", 
                    "field": "response_time",
                    "alias": "avg_response_time"
                }
            ],
            "time_series": True,
            "time_granularity": "minute",
            "limit": 5000
        }
        
        response = requests.post(
            f"{self.api_url}/v1/query/advanced",
            headers=self.headers,
            json=query
        )
        return response.json()

# Usage
analyzer = LogAnalyzer(
    'http://localhost:7080',
    'your-auth-token',
    'your-tenant-id'
)

# Analyze error trends
error_trends = analyzer.query_error_trends(hours_back=24)
print(f"Total errors in last 24h: {error_trends['aggregations']['error_count']}")

# Detect performance anomalies
anomalies = analyzer.detect_anomalies('api-gateway', threshold=2000)
print(f"Slow requests detected: {anomalies['aggregations']['slow_requests']}")
```

### Dashboard Integration
```javascript
// React/TypeScript dashboard integration
interface AdvancedQueryRequest {
  start_time: string;
  end_time: string;
  filters?: QueryFilter[];
  aggregations?: Aggregation[];
  group_by?: string[];
  time_series?: boolean;
  time_granularity?: 'minute' | 'hour' | 'day';
  limit?: number;
}

class LogforgeClient {
  constructor(private apiUrl: string, private authToken: string, private tenantId: string) {}
  
  async executeAdvancedQuery(query: AdvancedQueryRequest): Promise<QueryResponse> {
    const response = await fetch(`${this.apiUrl}/v1/query/advanced`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.authToken}`,
        'X-Customer-ID': this.tenantId
      },
      body: JSON.stringify(query)
    });
    
    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }
    
    return response.json();
  }
  
  async getServiceErrorRates(timeRange: { start: Date, end: Date }) {
    return this.executeAdvancedQuery({
      start_time: timeRange.start.toISOString(),
      end_time: timeRange.end.toISOString(),
      filters: [
        { field: 'level', operator: 'eq', value: 'error' }
      ],
      aggregations: [
        { type: 'count', field: '*', alias: 'error_count' }
      ],
      group_by: ['service'],
      time_series: true,
      time_granularity: 'hour'
    });
  }
}
```

## Security Considerations

### Data Protection
- **Tenant Isolation**: Strict enforcement via automatic customer_id filtering
- **Authentication Required**: No anonymous access to log data
- **Data Encryption**: TLS for data in transit, encrypted storage at rest
- **Access Logging**: All query requests logged for audit and compliance

### Query Security  
- **SQL Injection Prevention**: Parameterized queries and input sanitization
- **Resource Limits**: Maximum query complexity and result size limits
- **Rate Limiting**: Authentication middleware enforces request limits per tenant
- **Permission Enforcement**: Role-based access control for query operations

### Cache Security
- **Cache Isolation**: Tenant-specific cache keys prevent cross-tenant data access
- **TTL Management**: Automatic cache expiration prevents stale data exposure
- **Secure Storage**: Cached data encrypted and access-controlled
- **Cache Invalidation**: Immediate invalidation for sensitive operations

### Privacy Compliance
- **PII Handling**: Query results may contain PII - ensure compliance with data protection laws
- **Data Retention**: Cached results subject to TTL and retention policies
- **Access Controls**: Only authenticated users with proper permissions can access cached data
- **Audit Trail**: Complete logging of all query activities for compliance reporting

## Performance Optimization

### Query Optimization Strategies
- **Filter Early**: Apply filters at database level to reduce data transfer
- **Index Usage**: Leverage customer_id and timestamp indexes for optimal performance
- **Aggregation Efficiency**: Use appropriate aggregation types and group by low-cardinality fields
- **Time Range Limits**: Reasonable time ranges to prevent excessive resource usage

### Caching Strategies
- **Smart Cache Keys**: Hash generation includes all relevant query parameters
- **TTL Optimization**: 5-minute TTL balances freshness with performance
- **Cache Hit Optimization**: Structure repeated queries to maximize cache utilization
- **Memory Management**: Automatic cleanup of expired cache entries

### Database Tuning
- **ClickHouse Configuration**: Optimized for read-heavy analytical workloads
- **Memory Settings**: Appropriate memory limits for large aggregation queries
- **Partition Strategy**: Time-based partitioning for efficient query execution
- **Compression**: Optimized compression for storage efficiency and query speed

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team