# Advanced Query API Guide

## Overview

The Logforge Advanced Query API provides powerful capabilities for searching, filtering, and analyzing log data across your infrastructure. This comprehensive guide will help you leverage the full potential of the query system to gain insights from your observability data.

## API Endpoints

### Primary Query Endpoints

1. **Advanced Query** - `POST /v1/query/advanced`
   - Complex queries with filters, aggregations, and time-series analysis
   - Full-featured querying with grouping, field selection, and sorting

2. **Aggregate Query** - `POST /v1/query/aggregate`
   - Focused on aggregation operations with grouping
   - Optimized for statistical analysis and metrics

3. **Time Series Query** - `POST /v1/query/timeseries`
   - Time-based analysis with buckets and intervals
   - Perfect for trend analysis and temporal patterns

4. **Basic Logs** - `GET /v1/logs`
   - Simple log retrieval with basic filters
   - M0 compatibility endpoint for straightforward queries

## Authentication

All query endpoints require:
- **Authorization Header**: `Bearer <your_jwt_token>`
- **Customer ID Header**: `X-Customer-ID: <your_customer_id>`

Multi-tenant isolation is automatically enforced - you can only query data belonging to your organization.

## Advanced Query Structure

### Basic Request Format

```json
{
  "filters": [],
  "aggregations": [],
  "group_by": [],
  "order_by": [],
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z",
  "limit": 100,
  "offset": 0,
  "include_fields": [],
  "exclude_fields": [],
  "time_zone": "UTC"
}
```

### Field Descriptions

- **filters**: Array of filter conditions to narrow down results
- **aggregations**: Statistical operations to perform on the data
- **group_by**: Fields to group results by (for statistical analysis)
- **order_by**: Sorting configuration for results
- **start_time/end_time**: Time range for the query (ISO 8601 format)
- **limit/offset**: Pagination controls (max limit: 10,000)
- **include_fields/exclude_fields**: Control which fields are returned
- **time_zone**: Timezone for time-based operations (default: UTC)

## Filter Operations

### Available Filter Operators

| Operator | Description | Example Use Case |
|----------|-------------|------------------|
| `eq` | Equals | Exact service name matching |
| `ne` | Not equals | Exclude specific log levels |
| `gt` | Greater than | Response times above threshold |
| `gte` | Greater than or equal | Include boundary values |
| `lt` | Less than | Small file sizes |
| `lte` | Less than or equal | Include boundary values |
| `contains` | String contains | Error messages containing keywords |
| `starts_with` | String starts with | URLs with specific prefixes |
| `ends_with` | String ends with | File extensions |
| `regex` | Regular expression | Complex pattern matching |
| `in` | Value in list | Multiple service names |
| `not_in` | Value not in list | Exclude multiple values |

### Filter Examples

#### Basic String Filtering
```json
{
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "api-gateway"
    }
  ]
}
```

#### Multiple Conditions
```json
{
  "filters": [
    {
      "field": "level",
      "operator": "in",
      "value": ["ERROR", "CRITICAL"]
    },
    {
      "field": "msg",
      "operator": "contains", 
      "value": "database"
    }
  ]
}
```

#### Numeric Range Filtering
```json
{
  "filters": [
    {
      "field": "response_time",
      "operator": "gte",
      "value": 1000
    },
    {
      "field": "response_time",
      "operator": "lt",
      "value": 5000
    }
  ]
}
```

#### Regular Expression Filtering
```json
{
  "filters": [
    {
      "field": "msg",
      "operator": "regex",
      "value": "^Error: \\w+ failed with code (4|5)\\d{2}"
    }
  ]
}
```

## Aggregation Operations

### Available Aggregation Types

| Type | Description | Use Case |
|------|-------------|----------|
| `count` | Count of records | Event frequency |
| `sum` | Sum of numeric values | Total bytes transferred |
| `avg` | Average of numeric values | Mean response time |
| `min` | Minimum value | Fastest response |
| `max` | Maximum value | Slowest response |
| `percentile` | Percentile calculation | P95 response times |
| `unique` | Unique value count | Distinct user count |
| `cardinality` | Estimated unique count | High-cardinality metrics |

### Aggregation Examples

#### Basic Count Aggregation
```json
{
  "aggregations": [
    {
      "type": "count",
      "field": "*",
      "alias": "total_events"
    }
  ]
}
```

#### Statistical Analysis
```json
{
  "aggregations": [
    {
      "type": "avg",
      "field": "response_time",
      "alias": "avg_response_time"
    },
    {
      "type": "percentile",
      "field": "response_time", 
      "percentile": 95,
      "alias": "p95_response_time"
    }
  ]
}
```

#### Grouped Aggregations
```json
{
  "group_by": ["service", "level"],
  "aggregations": [
    {
      "type": "count",
      "field": "*",
      "alias": "event_count"
    },
    {
      "type": "unique",
      "field": "host",
      "alias": "unique_hosts"
    }
  ]
}
```

## Time Series Analysis

### Time Series Request Format
```json
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z",
  "interval": "1h",
  "granularity": "hour",
  "metrics": ["response_time", "error_rate"],
  "aggregations": [
    {
      "type": "avg",
      "field": "response_time",
      "alias": "avg_response_time"
    }
  ]
}
```

### Available Intervals
- **Seconds**: `1s`, `5s`, `10s`, `30s`
- **Minutes**: `1m`, `5m`, `15m`, `30m`
- **Hours**: `1h`, `6h`, `12h`
- **Days**: `1d`, `7d`

### Granularity Options
- `second`, `minute`, `hour`, `day`, `week`, `month`

## Practical Query Examples

### 1. Error Monitoring
```json
{
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
      "type": "count",
      "field": "*",
      "alias": "error_count"
    }
  ],
  "order_by": [
    {
      "field": "error_count",
      "direction": "desc"
    }
  ],
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z"
}
```

### 2. Performance Analysis
```json
{
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "api-gateway"
    },
    {
      "field": "response_time",
      "operator": "gte",
      "value": 100
    }
  ],
  "aggregations": [
    {
      "type": "avg",
      "field": "response_time",
      "alias": "avg_response_time"
    },
    {
      "type": "percentile",
      "field": "response_time",
      "percentile": 95,
      "alias": "p95_response_time"
    },
    {
      "type": "max",
      "field": "response_time", 
      "alias": "max_response_time"
    }
  ],
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z"
}
```

### 3. Security Analysis
```json
{
  "filters": [
    {
      "field": "msg",
      "operator": "regex",
      "value": "(failed|denied|unauthorized|forbidden)"
    },
    {
      "field": "level",
      "operator": "in",
      "value": ["WARN", "ERROR"]
    }
  ],
  "group_by": ["source_ip", "service"],
  "aggregations": [
    {
      "type": "count",
      "field": "*",
      "alias": "security_events"
    }
  ],
  "order_by": [
    {
      "field": "security_events",
      "direction": "desc"
    }
  ],
  "limit": 50
}
```

### 4. Business Intelligence
```json
{
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "payment-processor"
    },
    {
      "field": "status",
      "operator": "eq",
      "value": "success"
    }
  ],
  "group_by": ["payment_method"],
  "aggregations": [
    {
      "type": "sum",
      "field": "amount",
      "alias": "total_revenue"
    },
    {
      "type": "count",
      "field": "*",
      "alias": "transaction_count"
    },
    {
      "type": "avg",
      "field": "amount",
      "alias": "avg_transaction_value"
    }
  ]
}
```

### 5. Infrastructure Monitoring
```json
{
  "filters": [
    {
      "field": "metric_name",
      "operator": "in",
      "value": ["cpu_usage", "memory_usage", "disk_usage"]
    }
  ],
  "group_by": ["host", "metric_name"],
  "aggregations": [
    {
      "type": "avg",
      "field": "metric_value",
      "alias": "avg_value"
    },
    {
      "type": "max",
      "field": "metric_value",
      "alias": "peak_value"
    }
  ],
  "order_by": [
    {
      "field": "avg_value",
      "direction": "desc"
    }
  ]
}
```

## Field Selection

### Including Specific Fields
```json
{
  "include_fields": ["ts", "service", "level", "msg", "response_time"],
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "api-gateway"
    }
  ]
}
```

### Excluding Fields
```json
{
  "exclude_fields": ["raw_log", "internal_metadata", "debug_info"],
  "filters": [
    {
      "field": "level",
      "operator": "ne",
      "value": "DEBUG"
    }
  ]
}
```

## Sorting and Pagination

### Sorting Results
```json
{
  "order_by": [
    {
      "field": "ts",
      "direction": "desc"
    },
    {
      "field": "response_time",
      "direction": "asc"
    }
  ]
}
```

### Pagination
```json
{
  "limit": 100,
  "offset": 200
}
```

**Note**: Maximum limit is 10,000 records per request. For larger datasets, use pagination.

## Query Performance Optimization

### Best Practices

1. **Use Time Ranges**: Always specify reasonable start_time and end_time
2. **Limit Results**: Use appropriate limit values to avoid large response payloads
3. **Index-Friendly Filters**: Use indexed fields (service, level, host) in filters
4. **Selective Fields**: Use include_fields to fetch only necessary data
5. **Cache Awareness**: Identical queries are cached for 5 minutes

### Optimized Query Example
```json
{
  "filters": [
    {
      "field": "service",
      "operator": "eq",
      "value": "payment-api"
    },
    {
      "field": "level",
      "operator": "in",
      "value": ["ERROR", "WARN"]
    }
  ],
  "include_fields": ["ts", "service", "level", "msg", "trace_id"],
  "start_time": "2024-01-01T12:00:00Z",
  "end_time": "2024-01-01T13:00:00Z",
  "limit": 500,
  "order_by": [
    {
      "field": "ts",
      "direction": "desc"
    }
  ]
}
```

## Response Format

### Successful Response
```json
{
  "logs": [...],
  "total_count": 1250,
  "aggregations": {
    "avg_response_time": 234.5,
    "error_count": 15
  },
  "execution_time_ms": 145,
  "customer_id": "your-customer-id"
}
```

### Response Fields
- **logs**: Array of log records matching the query
- **total_count**: Total number of matching records
- **aggregations**: Results of aggregation operations
- **execution_time_ms**: Query execution time in milliseconds
- **customer_id**: Your organization identifier

## Error Handling

### Common Error Responses

#### Invalid Filter Operator
```json
{
  "detail": "Invalid operator 'invalid_op' for field 'service'"
}
```

#### Missing Time Range
```json
{
  "detail": "start_time and end_time are required for time-series queries"
}
```

#### Large Time Range Warning
```json
{
  "warning": "Large time range may impact performance",
  "suggestion": "Consider using smaller time windows or pagination"
}
```

## Query Caching

The system automatically caches query results for 5 minutes to improve performance:

- **Cache Key**: Generated from query parameters and customer_id
- **TTL**: 300 seconds (5 minutes)
- **Cache Hit**: Returns cached results with original execution_time_ms
- **Cache Miss**: Executes query and caches results

## Rate Limits and Quotas

- **Concurrent Queries**: Maximum 10 simultaneous queries per customer
- **Query Complexity**: Timeout after 30 seconds for complex queries
- **Daily Quota**: Varies by subscription tier
- **Result Size**: Maximum 10,000 records per query

## Integration Examples

### Python SDK Example
```python
import requests
import json

def query_logs(auth_token, customer_id, query_params):
    headers = {
        'Authorization': f'Bearer {auth_token}',
        'X-Customer-ID': customer_id,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(
        'http://localhost:7080/v1/query/advanced',
        headers=headers,
        json=query_params
    )
    
    return response.json()

# Example usage
query = {
    "filters": [
        {"field": "level", "operator": "eq", "value": "ERROR"}
    ],
    "limit": 100,
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z"
}

result = query_logs(auth_token, customer_id, query)
print(f"Found {result['total_count']} errors")
```

### cURL Example
```bash
curl -X POST "http://localhost:7080/v1/query/advanced" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "X-Customer-ID: YOUR_CUSTOMER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": [
      {
        "field": "service",
        "operator": "eq", 
        "value": "api-gateway"
      }
    ],
    "aggregations": [
      {
        "type": "count",
        "field": "*",
        "alias": "total_requests"
      }
    ],
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z"
  }'
```

## Advanced Use Cases

### Log Analysis Workflow
1. **Broad Search**: Start with simple filters to understand data volume
2. **Refinement**: Add more specific filters based on initial results
3. **Aggregation**: Use group_by and aggregations for pattern analysis
4. **Deep Dive**: Use include_fields to get detailed records for investigation

### Alerting Integration
Use aggregation queries to power alerting rules:
```json
{
  "filters": [
    {"field": "level", "operator": "eq", "value": "ERROR"}
  ],
  "aggregations": [
    {"type": "count", "field": "*", "alias": "error_count"}
  ],
  "start_time": "2024-01-01T12:00:00Z",
  "end_time": "2024-01-01T12:05:00Z"
}
```

### Dashboard Data
Create dashboard visualizations with time-series queries:
```json
{
  "interval": "5m",
  "aggregations": [
    {"type": "avg", "field": "response_time", "alias": "avg_response"},
    {"type": "count", "field": "*", "alias": "request_count"}
  ],
  "group_by": ["service"],
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T24:00:00Z"
}
```

## Troubleshooting

### Query Too Slow
- Reduce time range
- Add more specific filters
- Use field selection to limit data transfer
- Consider using aggregations instead of raw logs

### No Results Returned
- Verify time range includes expected data
- Check filter values for typos
- Ensure customer_id is correct
- Verify data exists in the specified time period

### Memory Issues
- Reduce limit parameter
- Use field exclusion for large text fields
- Implement pagination for large result sets

## Support

For additional help with queries:
- Check API logs for detailed error messages
- Use the query validation endpoint: `POST /v1/query/validate`
- Contact support with specific query examples
- Review the Postman collection for more examples

---

*This guide covers the core functionality of the Logforge Advanced Query API. For the latest updates and additional features, refer to the API documentation and release notes.*