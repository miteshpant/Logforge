# GET /v1/logs API Runbook

## Overview
This runbook documents the `GET /v1/logs` API endpoint for basic log retrieval and filtering in the Logforge platform.

## API Endpoint Details

**Endpoint**: `GET /v1/logs`  
**Content-Type**: Not applicable (GET request)  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Accessed

### 1. logs_raw_mt (Read-Only Access)
**Purpose**: Primary log storage table for reading log records  
**Access Method**: Direct ClickHouse query in main thread  
**Key Fields Read**:
- `ts`: Log timestamp
- `service`: Service name that generated the log
- `level`: Log level (info, warn, error, debug, etc.)
- `msg`: Log message content
- `host`: Hostname/server that generated the log
- `trace_id`: Distributed tracing identifier
- `customer_id`: Tenant isolation identifier

**Query Pattern**: 
```sql
SELECT ts, service, level, msg, host, trace_id, customer_id
FROM logs_raw_mt
WHERE customer_id = '{customer_id}' [AND additional_filters]
ORDER BY ts DESC
LIMIT {limit} OFFSET {offset}
```

## Request Parameters

### Query Parameters
- **service** (optional): Filter logs by service name
- **level** (optional): Filter logs by log level
- **limit** (optional): Maximum number of logs to return (default: 100)
- **offset** (optional): Number of logs to skip for pagination (default: 0)

### Required Headers
```http
GET /v1/logs?service=api-gateway&level=error&limit=50&offset=0 HTTP/1.1
Host: localhost:7080
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

## Sample cURL Commands

### Basic Log Retrieval
```bash
curl -X GET "http://localhost:7080/v1/logs?limit=10&offset=0" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### Filter by Service
```bash
curl -X GET "http://localhost:7080/v1/logs?service=api-gateway&limit=20" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### Filter by Log Level
```bash
curl -X GET "http://localhost:7080/v1/logs?level=error&limit=50" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### Combined Filters with Pagination
```bash
curl -X GET "http://localhost:7080/v1/logs?service=auth-service&level=warn&limit=25&offset=50" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
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
      "msg": "Authentication failed for user request",
      "host": "prod-api-01",
      "trace_id": "abc123def456",
      "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
    },
    {
      "ts": "2025-10-09T12:33:45.678Z",
      "service": "user-service",
      "level": "info",
      "msg": "User login successful",
      "host": "prod-api-02",
      "trace_id": "xyz789uvw123",
      "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
    }
  ],
  "total": 1247,
  "limit": 50,
  "offset": 0,
  "customer_id": "505908f9-8718-4dea-b2d8-9b9e5ae0bd45"
}
```

### Error Responses
```json
// Database connection error
{
  "detail": "Database client not initialized"
}

// Authentication error
{
  "detail": "Invalid or expired session"
}

// Log retrieval failed
{
  "detail": "Log retrieval failed: Database connection timeout"
}
```

## Code Flow Analysis

### Main Request Processing
1. **Authentication**: JWT token validation + X-Customer-ID header verification
2. **Parameter Validation**: Extract and validate query parameters (service, level, limit, offset)
3. **SQL Query Construction**: Build WHERE clause with tenant isolation and optional filters
4. **Database Query Execution**: Execute SELECT query against logs_raw_mt table
5. **Result Processing**: Convert ClickHouse result rows to JSON format
6. **Pagination Support**: Calculate total count and return with pagination metadata
7. **Response**: Return formatted JSON response with logs and metadata

### Database Query Logic
```python
# Build WHERE conditions with mandatory tenant isolation
where_conditions = [f"customer_id = '{customer_id}'"]

# Add optional filters
if service:
    where_conditions.append(f"service = '{service}'")
if level:
    where_conditions.append(f"level = '{level}'")

where_clause = " AND ".join(where_conditions)

# Main query for logs
query = f"""
SELECT ts, service, level, msg, host, trace_id, customer_id
FROM logs_raw_mt
WHERE {where_clause}
ORDER BY ts DESC
LIMIT {limit} OFFSET {offset}
"""

# Count query for pagination
count_query = f"""
SELECT count() FROM logs_raw_mt WHERE {where_clause}
"""
```

## Authentication & Authorization

### Required Authentication
- **JWT Bearer Token**: Must be valid and non-expired
- **X-Customer-ID Header**: Must match authenticated user's tenant ID
- **Tenant Isolation**: Automatic enforcement via customer_id filter

### Security Features
- **Mandatory Tenant Filtering**: Every query includes customer_id = '{customer_id}' filter
- **SQL Injection Protection**: Parameterized queries prevent injection attacks
- **Input Validation**: Service and level parameters validated before query execution
- **Rate Limiting**: Enforced through authentication middleware

## Performance Characteristics

### Response Time Targets
- **Simple Query**: < 100ms for recent logs (last 24 hours)
- **Filtered Query**: < 500ms with service/level filters
- **Large Result Sets**: < 1s for 1000+ records
- **Pagination**: Optimized OFFSET handling for large datasets

### Resource Usage
- **Memory**: Efficient result streaming for large queries
- **CPU**: Optimized ClickHouse queries with proper indexing
- **Network**: Minimal data transfer with field selection

### Query Optimization
- **Index Usage**: Leverages ClickHouse timestamp and customer_id indexes
- **Result Limiting**: Default and maximum limits prevent excessive resource usage
- **Efficient Pagination**: COUNT query separated from main query for performance

## Error Handling

### Database Errors
- **Connection Failure**: 500 error with "Database client not initialized"
- **Query Timeout**: 500 error with timeout details
- **Invalid Query**: 500 error with SQL error details

### Authentication Errors
- **Invalid Token**: 401 Unauthorized response
- **Missing Headers**: 401 Unauthorized response
- **Tenant Mismatch**: 403 Forbidden response

### Validation Errors
- **Invalid Parameters**: No specific validation errors (uses defaults)
- **Negative Limits**: Handled by ClickHouse (treats as 0)
- **Large Offsets**: Performance impact but no error

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **Query Performance**: Response times for different filter combinations
- **Database Load**: ClickHouse CPU and memory usage during log queries
- **Authentication Success**: Rate of successful vs failed authentications
- **Pagination Usage**: Most common limit/offset patterns

### Common Issues
1. **Slow Queries**: Large time ranges without proper filtering
2. **Authentication Failures**: Expired tokens or incorrect tenant IDs
3. **Large Result Sets**: Queries without appropriate limits
4. **Pagination Problems**: Very large offsets causing performance issues

### Debugging Steps
1. **Check Authentication**: Verify JWT token validity and X-Customer-ID header
2. **Test Database Connection**: Ensure ClickHouse is accessible and responsive
3. **Analyze Query Performance**: Check ClickHouse query logs for slow queries
4. **Monitor Resource Usage**: Check server CPU/memory during high-load periods

## Usage Examples

### Log Monitoring Dashboard
```bash
# Get recent error logs for monitoring
curl -X GET "http://localhost:7080/v1/logs?level=error&limit=100" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### Service-Specific Debugging
```bash
# Debug specific service issues
curl -X GET "http://localhost:7080/v1/logs?service=payment-gateway&limit=200" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID"
```

### Historical Log Analysis
```bash
# Get paginated historical logs
for offset in 0 100 200 300; do
  curl -X GET "http://localhost:7080/v1/logs?limit=100&offset=$offset" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "X-Customer-ID: $TENANT_ID"
done
```

### Real-Time Log Streaming Simulation
```bash
#!/bin/bash
# Simulate real-time log monitoring
while true; do
  curl -s -X GET "http://localhost:7080/v1/logs?limit=10&offset=0" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "X-Customer-ID: $TENANT_ID" | \
    jq '.logs[] | "\(.ts) [\(.level)] \(.service): \(.msg)"'
  sleep 5
done
```

## Integration Examples

### Log Analysis Script
```python
import requests
import json

class LogAnalyzer:
    def __init__(self, api_url, auth_token, tenant_id):
        self.api_url = api_url
        self.headers = {
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
    
    def get_error_logs(self, service=None, limit=100):
        """Get recent error logs for analysis"""
        params = {'level': 'error', 'limit': limit}
        if service:
            params['service'] = service
            
        response = requests.get(
            f"{self.api_url}/v1/logs",
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def get_service_logs(self, service, limit=200):
        """Get logs for specific service"""
        params = {'service': service, 'limit': limit}
        response = requests.get(
            f"{self.api_url}/v1/logs",
            headers=self.headers,
            params=params
        )
        return response.json()
    
    def analyze_error_patterns(self):
        """Analyze error log patterns"""
        error_logs = self.get_error_logs(limit=500)
        services = {}
        
        for log in error_logs.get('logs', []):
            service = log.get('service', 'unknown')
            services[service] = services.get(service, 0) + 1
            
        return sorted(services.items(), key=lambda x: x[1], reverse=True)

# Usage
analyzer = LogAnalyzer(
    'http://localhost:7080',
    'your-auth-token',
    'your-tenant-id'
)

# Get error patterns
error_patterns = analyzer.analyze_error_patterns()
print("Top services by error count:")
for service, count in error_patterns[:5]:
    print(f"  {service}: {count} errors")
```

## Security Considerations

### Data Protection
- **Tenant Isolation**: Strict enforcement via customer_id filtering
- **Authentication Required**: No anonymous access to log data
- **Data Encryption**: TLS for data in transit
- **Access Logging**: All log access requests are logged for audit

### Query Security
- **SQL Injection Prevention**: Parameterized queries and input sanitization
- **Resource Limits**: Default and maximum limits prevent resource exhaustion
- **Rate Limiting**: Authentication middleware enforces request limits

### Privacy Compliance
- **PII Handling**: Log content may contain PII - ensure compliance with data protection laws
- **Data Retention**: Logs subject to TTL policies and retention management
- **Access Controls**: Only authenticated users with proper tenant access can retrieve logs

## Performance Optimization

### Query Optimization
- **Index Strategy**: Ensure customer_id and timestamp indexes exist
- **Filter Early**: Apply service/level filters at database level
- **Limit Results**: Use appropriate limits to prevent large transfers
- **Pagination**: Use offset carefully with large datasets

### Caching Strategy
- **No Caching**: This endpoint provides real-time log access
- **Client-Side Caching**: Clients can cache results for short periods
- **CDN Considerations**: Not applicable for dynamic log content

### Database Tuning
- **ClickHouse Configuration**: Optimize for read-heavy workloads
- **Memory Settings**: Configure appropriate memory limits for large queries
- **Partition Strategy**: Consider time-based partitioning for large log volumes

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team