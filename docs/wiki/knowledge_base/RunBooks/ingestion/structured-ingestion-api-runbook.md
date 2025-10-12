# Structured JSON Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/structured` API endpoint for structured JSON log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/structured`  
**Content-Type**: `application/json`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The structured ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual structured log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: From `ts` field or current time
- `level`: Log level from request
- `msg`: Required message field
- `service`: Service name from request
- `host`: Hostname from request
- `trace_id`, `span_id`: Tracing information
- `attrs`: Additional custom attributes
- `raw_log`: Original JSON structure
- `source_format`: "json"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.structured"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records
- `bytes_processed`: Total bytes from JSON content
- `cost_calculated`: Using $0.50/GB from pricing.yml
- `rate_applied`: Applied pricing rate
- `billing_period`: Current billing cycle
- `recorded_at`: Timestamp of usage recording

### 3. tenant_quotas_mt (Quota Management)
**Purpose**: Updates tenant usage quotas and limits  
**Update Method**: Background task via `update_tenant_quota()`  
**Key Fields Updated**:
- `current_usage`: Incremented by bytes processed
- `last_updated`: Current timestamp
- Quota limit enforcement if exceeded

### 4. ingestion_stats_mt (Performance Monitoring)
**Purpose**: Tracks ingestion performance metrics  
**Update Method**: Background task via direct ClickHouse insert  
**Key Fields**:
- `customer_id`: Tenant isolation
- `endpoint`: "/structured"
- `source_format`: "json"
- `log_count`: Number of logs processed
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: Number of successful logs
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## JSON Schema & Validation

The structured endpoint accepts JSON that conforms to the LogEntry model:

### Required Fields
- **msg**: Log message (string, required)

### Optional Fields
- **ts**: Timestamp (ISO format, defaults to current time)
- **level**: Log level (trace, debug, info, warn, error, fatal)
- **service**: Service name (string, defaults to "unknown")
- **host**: Hostname (string)
- **trace_id**: Distributed trace ID (string)
- **span_id**: Span ID for tracing (string)
- **attrs**: Additional attributes (object)
- **status**: HTTP status or error code (integer)
- **src_ip**: Source IP address (string)

### Single Log Format
```json
{
  "ts": "2025-10-09T12:34:56.789Z",
  "level": "info",
  "service": "api-gateway",
  "host": "api-01",
  "msg": "Request processed successfully",
  "trace_id": "abc123",
  "span_id": "def456",
  "attrs": {
    "user_id": "user-789",
    "request_id": "req-123456",
    "environment": "production"
  },
  "status": 200,
  "src_ip": "192.168.1.100"
}
```

### Array of Logs Format
```json
[
  {
    "ts": "2025-10-09T12:34:56.789Z",
    "level": "info",
    "msg": "User login successful",
    "service": "auth-service",
    "user_id": "user-123"
  },
  {
    "ts": "2025-10-09T12:34:57.890Z",
    "level": "warn",
    "msg": "Rate limit approaching",
    "service": "api-gateway",
    "threshold": 90
  }
]
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/structured HTTP/1.1
Host: localhost:7080
Content-Type: application/json
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### Single Structured Log
```bash
curl -X POST "http://localhost:7080/v1/ingest/structured" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "ts": "2025-10-09T12:34:56.789Z",
    "level": "info",
    "service": "api-gateway",
    "host": "api-01",
    "msg": "Request processed successfully",
    "user_id": "user-789",
    "request_id": "req-123456",
    "environment": "production"
  }'
```

#### Multiple Structured Logs
```bash
curl -X POST "http://localhost:7080/v1/ingest/structured" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '[
    {
      "msg": "User authentication successful",
      "level": "info",
      "service": "auth-service",
      "user_id": "user-123"
    },
    {
      "msg": "Database query executed",
      "level": "debug",
      "service": "data-service",
      "query_time_ms": 45
    }
  ]'
```

#### Minimal Required Fields
```bash
curl -X POST "http://localhost:7080/v1/ingest/structured" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{"msg": "Simple log message with only required field"}'
```

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

### Error Responses
```json
// Missing required field (msg)
{
  "detail": "Structured data parsing failed: 1 validation error for LogEntry\nmsg\n  Field required [type=missing, input_value={'ts': '2025-10-09...', 'level': 'info'}, input_type=dict]"
}

// Invalid JSON format
{
  "detail": "Structured data parsing failed: Invalid JSON format"
}

// Authentication error
{
  "detail": "Invalid or expired session"
}

// Missing tenant header
{
  "detail": "X-Customer-ID header is required"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **JSON Parsing**: Parse request body as JSON
3. **Schema Validation**: Validate against LogEntry model using Pydantic
4. **Log Preparation**: Convert to LogEntry objects with metadata
5. **Background Task Scheduling**: Queue tracking operations for background processing
6. **Fast Response**: Return 200 OK immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Structured Data Features

### Flexible Schema
- **Required Fields**: Only `msg` field is mandatory
- **Optional Fields**: All other fields have sensible defaults
- **Custom Attributes**: Support for arbitrary additional fields
- **Type Validation**: Pydantic model ensures type safety

### Data Normalization
- **Timestamp Handling**: Automatic parsing of various timestamp formats
- **Level Normalization**: Case-insensitive log level handling
- **Service Detection**: Automatic service name extraction
- **Attribute Flattening**: Complex nested objects supported

### Batch Processing
- **Single or Array**: Accepts both single objects and arrays
- **Mixed Schemas**: Each log in array can have different fields
- **Efficient Processing**: Optimized for bulk ingestion
- **Error Isolation**: Individual log failures don't affect batch

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for high-volume structured log ingestion

### Resource Usage
- **Memory**: Efficient JSON parsing with streaming support
- **CPU**: Low main thread usage, background processing distributed
- **Database**: Optimized bulk operations for arrays

## Error Handling

### Validation Errors
- Missing required `msg` field → 400 Bad Request with detailed error
- Invalid JSON syntax → 400 Bad Request
- Type validation failures → 400 Bad Request with field details

### Processing Errors
- Pydantic validation exceptions → 400 Bad Request with specific error
- Database errors → Background error logging
- Quota exceeded → Quota enforcement (non-blocking)

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **ingestion_stats_mt**: Processing times, success/error rates
- **usage_records_mt**: Usage volumes and cost calculations
- **tenant_quotas_mt**: Quota utilization per tenant
- **logs_raw_mt**: Actual log storage and retrieval
- **Schema Validation**: Field usage patterns and validation errors

### Common Issues
1. **Authentication Failures**: Check Bearer token validity
2. **Schema Validation**: Ensure `msg` field is present
3. **JSON Format**: Validate JSON syntax before sending
4. **Tenant Isolation**: Ensure X-Customer-ID header is correct

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Validate JSON Schema**: Test with minimal required fields
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## Structured Log Examples

### Application Monitoring
```json
{
  "ts": "2025-10-09T14:23:45.123Z",
  "level": "info",
  "service": "user-service",
  "host": "app-01",
  "msg": "User registration completed",
  "user_id": "user-12345",
  "email": "user@example.com",
  "registration_source": "web",
  "processing_time_ms": 150
}
```

### API Request Logging
```json
{
  "ts": "2025-10-09T14:23:46.456Z",
  "level": "info",
  "service": "api-gateway",
  "host": "gateway-02",
  "msg": "API request processed",
  "method": "POST",
  "path": "/api/v1/users",
  "status": 201,
  "response_time_ms": 45,
  "user_agent": "curl/7.68.0",
  "src_ip": "192.168.1.100"
}
```

### Error Tracking
```json
{
  "ts": "2025-10-09T14:23:47.789Z",
  "level": "error",
  "service": "payment-service",
  "host": "pay-01",
  "msg": "Payment processing failed",
  "error_code": "INSUFFICIENT_FUNDS",
  "transaction_id": "txn-67890",
  "amount": 99.99,
  "currency": "USD",
  "user_id": "user-12345"
}
```

### Batch Processing Example
```json
[
  {
    "msg": "Batch job started",
    "level": "info",
    "service": "batch-processor",
    "job_id": "job-001",
    "records_to_process": 10000
  },
  {
    "msg": "Processing record",
    "level": "debug",
    "service": "batch-processor",
    "job_id": "job-001",
    "record_id": "rec-001"
  },
  {
    "msg": "Batch job completed",
    "level": "info",
    "service": "batch-processor",
    "job_id": "job-001",
    "records_processed": 10000,
    "duration_seconds": 120
  }
]
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: Pydantic model ensures type safety
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

### JSON Security
- **Schema Validation**: Prevents malformed data injection
- **Size Limits**: Reasonable payload size limits to prevent DoS
- **Field Sanitization**: Automatic handling of special characters

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of JSON content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient JSON Processing**: Streaming JSON parser for large payloads
- **Background Processing**: No blocking operations affecting throughput
- **Bulk Operations**: Optimized for array ingestion

## Integration Examples

### JavaScript/Node.js
```javascript
const axios = require('axios');

async function sendStructuredLog(logData) {
    try {
        const response = await axios.post(
            'http://localhost:7080/v1/ingest/structured',
            logData,
            {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${process.env.AUTH_TOKEN}`,
                    'X-Customer-ID': process.env.TENANT_ID
                }
            }
        );
        console.log('Log sent successfully:', response.data);
    } catch (error) {
        console.error('Failed to send log:', error.response?.data || error.message);
    }
}

// Usage
sendStructuredLog({
    msg: 'User action completed',
    level: 'info',
    service: 'web-app',
    user_id: 'user-123',
    action: 'profile_update'
});
```

### Python Application
```python
import requests
import json
from datetime import datetime

class StructuredLogger:
    def __init__(self, api_url, auth_token, tenant_id, service_name):
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
        self.service_name = service_name
    
    def log(self, message, level='info', **kwargs):
        log_data = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'service': self.service_name,
            'msg': message,
            **kwargs
        }
        
        try:
            response = requests.post(self.api_url, json=log_data, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send log: {e}")

# Usage
logger = StructuredLogger(
    'http://localhost:7080/v1/ingest/structured',
    'your-auth-token',
    'your-tenant-id',
    'python-app'
)

logger.log('Application started', level='info', port=8080)
logger.log('Database connected', level='info', db_name='production')
logger.log('User authenticated', level='info', user_id='user-123')
```

### Go Application
```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type LogEntry struct {
    Timestamp string                 `json:"ts"`
    Level     string                 `json:"level"`
    Service   string                 `json:"service"`
    Message   string                 `json:"msg"`
    Attrs     map[string]interface{} `json:"attrs,omitempty"`
}

type StructuredLogger struct {
    apiURL      string
    authToken   string
    tenantID    string
    serviceName string
    client      *http.Client
}

func NewStructuredLogger(apiURL, authToken, tenantID, serviceName string) *StructuredLogger {
    return &StructuredLogger{
        apiURL:      apiURL,
        authToken:   authToken,
        tenantID:    tenantID,
        serviceName: serviceName,
        client:      &http.Client{Timeout: 10 * time.Second},
    }
}

func (sl *StructuredLogger) Log(message, level string, attrs map[string]interface{}) error {
    logEntry := LogEntry{
        Timestamp: time.Now().UTC().Format("2006-01-02T15:04:05.000Z"),
        Level:     level,
        Service:   sl.serviceName,
        Message:   message,
        Attrs:     attrs,
    }
    
    jsonData, err := json.Marshal(logEntry)
    if err != nil {
        return err
    }
    
    req, err := http.NewRequest("POST", sl.apiURL, bytes.NewBuffer(jsonData))
    if err != nil {
        return err
    }
    
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer "+sl.authToken)
    req.Header.Set("X-Customer-ID", sl.tenantID)
    
    resp, err := sl.client.Do(req)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("failed to send log: status %d", resp.StatusCode)
    }
    
    return nil
}

// Usage
func main() {
    logger := NewStructuredLogger(
        "http://localhost:7080/v1/ingest/structured",
        "your-auth-token",
        "your-tenant-id",
        "go-app",
    )
    
    logger.Log("Application started", "info", map[string]interface{}{
        "port": 8080,
        "environment": "production",
    })
}
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team