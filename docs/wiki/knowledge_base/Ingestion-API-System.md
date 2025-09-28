# Logforge Ingestion API System

## Overview

The Logforge Ingestion API provides comprehensive log ingestion capabilities supporting multiple formats, protocols, and processing methods. Built on FastAPI with background task processing and multi-tenant architecture, the system handles high-throughput log ingestion with format auto-detection, validation, and real-time processing.

**Base URL**: `/v1/ingest`  
**Authentication**: Bearer token required via `Authorization` header  
**Multi-tenant**: X-Customer-ID header required for tenant isolation

---

## Structured Log Ingestion Endpoints

### 1. Single Log Entry Ingestion
**Endpoint**: `POST /v1/ingest/logs`

Ingests a single structured log entry using the LogEntry model with full validation and background processing.

**Request Body**:
```json
{
  "msg": "User login successful",
  "level": "info",
  "service": "auth-service", 
  "ts": "2024-01-01T12:00:00Z",
  "host": "web-server-01",
  "attrs": {
    "user_id": "12345",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/logs" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "msg": "API request processed",
    "level": "info",
    "service": "api-gateway",
    "ts": "2024-01-01T12:00:00Z",
    "host": "gateway-01",
    "attrs": {
      "endpoint": "/v1/users",
      "method": "GET",
      "response_time_ms": 145,
      "status_code": 200
    }
  }'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 log",
  "log_id": "log-1704110400-1234",
  "processed_count": 1
}
```

**Performance Metrics**:
- Processing time tracking for performance monitoring
- Byte size calculation for billing and storage optimization
- Background task queuing for high-throughput processing

### 2. Batch Log Ingestion
**Endpoint**: `POST /v1/ingest/logs/batch`

Ingests multiple structured log entries in a single request for improved throughput and reduced API overhead.

**Request Body**:
```json
{
  "logs": [
    {
      "msg": "Database connection established",
      "level": "info",
      "service": "db-service",
      "ts": "2024-01-01T12:00:00Z",
      "host": "db-primary",
      "attrs": {
        "connection_id": "conn-123",
        "database": "app_prod"
      }
    },
    {
      "msg": "Query executed successfully",
      "level": "debug",
      "service": "db-service", 
      "ts": "2024-01-01T12:00:01Z",
      "host": "db-primary",
      "attrs": {
        "query_time_ms": 45,
        "rows_affected": 1
      }
    }
  ]
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/logs/batch" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "msg": "User session started",
        "level": "info",
        "service": "session-manager",
        "ts": "2024-01-01T12:00:00Z",
        "host": "session-01"
      },
      {
        "msg": "Cache miss occurred",
        "level": "warn", 
        "service": "cache-service",
        "ts": "2024-01-01T12:00:01Z",
        "host": "cache-01"
      }
    ]
  }'
```

**Response Structure**:
```json
{
  "status": "accepted",
  "message": "Successfully ingested 2 logs",
  "processed_count": 2,
  "error_count": 0
}
```

### 3. Bulk Data Ingestion
**Endpoint**: `POST /v1/ingest/logs/bulk`

Handles bulk log ingestion from various data sources with flexible data structure support and error tolerance.

**Request Body**:
```json
{
  "logs": [
    {
      "msg": "Application started",
      "level": "info",
      "service": "app-service",
      "ts": "2024-01-01T12:00:00Z"
    },
    {
      "msg": "Configuration loaded",
      "level": "info", 
      "service": "app-service",
      "ts": "2024-01-01T12:00:01Z"
    }
  ]
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/logs/bulk" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {"msg": "System health check", "level": "info", "service": "monitor"},
      {"msg": "Memory usage: 45%", "level": "debug", "service": "monitor"},
      {"msg": "CPU usage: 78%", "level": "warn", "service": "monitor"}
    ]
  }'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 3 logs",
  "processed_count": 3,
  "error_count": 0
}
```

### 4. Structured JSON Ingestion
**Endpoint**: `POST /v1/ingest/structured`

Ingests structured JSON data with support for both single objects and arrays, with flexible schema handling.

**Request Body (Single Object)**:
```json
{
  "msg": "Order processed successfully",
  "level": "info",
  "service": "order-service",
  "ts": "2024-01-01T12:00:00Z",
  "attrs": {
    "order_id": "ORD-12345",
    "customer_id": "CUST-67890",
    "total_amount": 99.99,
    "payment_method": "credit_card"
  }
}
```

**Request Body (Array)**:
```json
[
  {
    "msg": "Payment validated",
    "level": "info",
    "service": "payment-service"
  },
  {
    "msg": "Inventory updated",
    "level": "info", 
    "service": "inventory-service"
  }
]
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/structured" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "msg": "Email notification sent",
    "level": "info",
    "service": "notification-service",
    "ts": "2024-01-01T12:00:00Z",
    "attrs": {
      "recipient": "user@example.com",
      "template": "welcome_email",
      "delivery_status": "delivered"
    }
  }'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

---

## Protocol-Specific Ingestion Endpoints

### 5. OpenTelemetry (OTLP) Ingestion
**Endpoint**: `POST /v1/ingest/otlp`

Ingests logs using the OpenTelemetry Protocol (OTLP) format for distributed tracing and observability integration.

**Request Body (OTLP Format)**:
```json
{
  "resource_logs": [
    {
      "resource": {
        "attributes": [
          {
            "key": "service.name",
            "value": {"string_value": "payment-service"}
          },
          {
            "key": "service.version", 
            "value": {"string_value": "1.2.3"}
          }
        ]
      },
      "scope_logs": [
        {
          "log_records": [
            {
              "time_unix_nano": 1704110400000000000,
              "severity_number": 9,
              "severity_text": "INFO",
              "body": {"string_value": "Payment processed successfully"},
              "attributes": [
                {
                  "key": "payment.id",
                  "value": {"string_value": "PAY-12345"}
                },
                {
                  "key": "payment.amount",
                  "value": {"double_value": 99.99}
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/otlp" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d @otlp_logs.json
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1,
  "error_count": 0
}
```

### 6. Syslog Format Ingestion
**Endpoint**: `POST /v1/ingest/syslog`

Ingests logs in standard syslog formats (RFC 3164 and RFC 5424) commonly used by network devices and Unix systems.

**Request Body (RFC 5424 Format)**:
```
<14>1 2024-01-01T12:00:00.000Z web-server-01 nginx 1234 - [timeQuality tzKnown="1" isSynced="1"][meta sequenceId="1"] User request processed successfully
```

**Request Body (RFC 3164 Format)**:
```
<134>Jan 01 12:00:00 web-server-01 sshd[1234]: Accepted password for admin from 192.168.1.100 port 22
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/syslog" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: text/plain" \
  -d '<14>1 2024-01-01T12:00:00.000Z api-server nginx 1234 - [meta sequenceId="1"] GET /api/users 200 OK'
```

**Response Structure**:
```json
{
  "status": "success", 
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

**Syslog Parsing Features**:
- Automatic facility and severity extraction from priority values
- Timestamp normalization to ISO 8601 format
- Hostname and process name extraction
- Structured data parsing for RFC 5424 format

### 7. Nginx Access Log Ingestion
**Endpoint**: `POST /v1/ingest/nginx`

Specialized ingestion for Nginx access logs with automatic field parsing and HTTP request analysis.

**Request Body (Common Log Format)**:
```
192.168.1.100 - admin [01/Jan/2024:12:00:00 +0000] "GET /api/users HTTP/1.1" 200 1024 "https://example.com" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

**Request Body (Combined Log Format)**:
```
10.0.0.1 - - [01/Jan/2024:12:00:00 +0000] "POST /api/orders HTTP/1.1" 201 512 "-" "curl/7.68.0" "0.145"
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/nginx" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: text/plain" \
  -d '192.168.1.50 - api-user [01/Jan/2024:12:00:00 +0000] "GET /v1/health HTTP/1.1" 200 156 "-" "health-check/1.0"'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

**Nginx Log Parsing Features**:
- IP address and user identification extraction
- HTTP method, path, and status code parsing
- Response size and timing analysis
- User agent and referrer information extraction
- Custom log format support

### 8. Common Event Format (CEF) Ingestion  
**Endpoint**: `POST /v1/ingest/cef`

Ingests logs in Common Event Format (CEF), widely used by security information and event management (SIEM) systems.

**Request Body (CEF Format)**:
```
CEF:0|Security|IDS|1.0|100|Attempted intrusion|High|src=192.168.1.100 dst=10.0.0.1 spt=1234 dpt=80 act=blocked
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/cef" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: text/plain" \
  -d 'CEF:0|Firewall|ASA|9.0|106001|Inbound TCP connection denied|Low|src=203.0.113.1 dst=10.0.0.1 spt=12345 dpt=443'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs", 
  "processed_count": 1
}
```

**CEF Parsing Features**:
- Header parsing (version, vendor, product, version, signature ID, name, severity)
- Extension field parsing with key-value pairs
- Security event categorization
- Severity level normalization

### 9. Plain Text Log Ingestion
**Endpoint**: `POST /v1/ingest/text`

Ingests plain text logs with basic parsing to extract timestamps, log levels, and message content.

**Request Body**:
```
2024-01-01 12:00:00 INFO [auth-service] User authentication successful for user: admin
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest/text" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: text/plain" \
  -d '2024-01-01 12:00:00 ERROR [database] Connection timeout after 30 seconds'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs",
  "processed_count": 1
}
```

**Text Parsing Features**:
- Timestamp extraction and normalization
- Log level detection (INFO, WARN, ERROR, DEBUG, etc.)
- Service/component identification from brackets
- Message content extraction

---

## Format Auto-Detection Endpoint

### 10. Auto-Detection Ingestion
**Endpoint**: `POST /v1/ingest`

Intelligent format detection and ingestion based on content-type headers and content analysis.

**Supported Auto-Detection**:
- **JSON**: `application/json` content-type or valid JSON structure
- **OTLP**: JSON with `resource_logs` field
- **CEF**: Text starting with `CEF:` prefix
- **Syslog**: Text with syslog priority format `<priority>`
- **Nginx**: Text with common/combined log format patterns
- **Text**: Plain text with basic log structure

**Request Example (JSON Auto-Detection)**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "msg": "Auto-detected JSON log entry",
    "level": "info",
    "service": "auto-service"
  }'
```

**Request Example (Text Auto-Detection)**:
```bash
curl -X POST "https://api.logforge.com/v1/ingest" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: text/plain" \
  -d '2024-01-01 12:00:00 INFO Auto-detected plain text log message'
```

**Response Structure**:
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs - detected format: json",
  "processed_count": 1
}
```

**Detection Logic**:
1. **Content-Type Analysis**: Examines HTTP Content-Type header
2. **Structure Analysis**: Analyzes content structure and patterns
3. **Format Patterns**: Matches against known format signatures
4. **Fallback Strategy**: Defaults to text parsing if no pattern matches

---

## Data Models and Validation

### LogEntry Model

The core data structure for all ingested logs:

```json
{
  "msg": "string (required) - The main log message",
  "level": "string (optional) - Log level (info, warn, error, debug, trace)",
  "service": "string (optional) - Service or component name", 
  "ts": "string (optional) - ISO 8601 timestamp",
  "host": "string (optional) - Hostname or server identifier",
  "attrs": "object (optional) - Additional structured attributes",
  "ingested_at": "datetime (auto-generated) - Ingestion timestamp",
  "customer_id": "string (auto-assigned) - Tenant identifier"
}
```

### BatchLogEntry Model

Container for multiple log entries:

```json
{
  "logs": [
    {
      "msg": "Log message 1",
      "level": "info",
      "service": "service-1"
    },
    {
      "msg": "Log message 2", 
      "level": "warn",
      "service": "service-2"
    }
  ]
}
```

### Response Models

**IngestResponse** (Single Log):
```json
{
  "status": "success|error",
  "message": "string - Human readable message",
  "log_id": "string (optional) - Generated log identifier",
  "processed_count": "integer - Number of logs processed"
}
```

**BatchIngestResponse** (Multiple Logs):
```json
{
  "status": "success|accepted|error",
  "message": "string - Processing summary",
  "processed_count": "integer - Successfully processed logs",
  "error_count": "integer - Failed log processing count"
}
```

---

## Authentication & Authorization

### Required Headers
All ingestion endpoints require:
- `Authorization: Bearer <jwt-token>`
- `X-Customer-ID: <tenant-uuid>` (for multi-tenant isolation)

### Permission Requirements
- **Log Ingestion**: Requires `ingestion.*` subscription feature
- **Data Storage**: Requires `storage.*` subscription feature
- **Query Access**: May require `queries.*` for validation features

### Subscription Features
The Ingestion API requires the following subscription features:
- `ingestion.*` - Core log ingestion functionality
- `queries.*` - Query validation and processing
- `storage.*` - Data storage and retention
- `alerts.*` - Alert triggering from ingested data

---

## Performance and Scalability

### Background Processing
All ingestion endpoints use FastAPI BackgroundTasks for:
- **Asynchronous Processing**: Non-blocking request handling
- **Batch Optimization**: Efficient database insertions
- **Error Resilience**: Retry mechanisms for failed operations
- **Resource Management**: Memory and connection pooling

### Throughput Optimization
- **Batch Ingestion**: Recommended for high-volume scenarios
- **Connection Pooling**: Efficient database resource utilization
- **Parallel Processing**: Concurrent log processing capabilities
- **Compression**: Automatic data compression for storage efficiency

### Performance Metrics
- **Processing Time**: Sub-second response times for most requests
- **Throughput**: 50K+ events per second per node capability
- **Memory Usage**: Optimized for large batch processing
- **Storage Efficiency**: 3-6x compression ratios achieved

---

## Error Handling

### Validation Errors

**422 - Unprocessable Entity**:
```json
{
  "detail": [
    {
      "loc": ["msg"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**400 - Bad Request**:
```json
{
  "detail": "Missing 'logs' field in request"
}
```

### Processing Errors

**400 - Format Parsing Error**:
```json
{
  "detail": "Syslog parsing failed: Invalid priority format"
}
```

**500 - Server Error**:
```json
{
  "detail": "Ingestion failed: Database connection timeout"
}
```

### Authentication Errors

**401 - Unauthorized**:
```json
{
  "detail": "Not authenticated"
}
```

**403 - Subscription Required**:
```json
{
  "error": "subscription_not_found",
  "message": "No subscription found",
  "required_feature": "ingestion.*",
  "current_subscription": [],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade"
}
```

---

## Usage Tracking and Billing

### Automatic Metrics
- **Log Count**: Number of logs processed per request
- **Data Volume**: Byte size of ingested data
- **Processing Time**: Request processing duration
- **Error Rates**: Failed ingestion attempt tracking

### Tenant Usage Tracking
```json
{
  "tenant_id": "uuid",
  "feature": "log_ingestion", 
  "usage_count": 1000,
  "bytes_processed": 1048576,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Billing Integration
- **Real-time Usage**: Immediate usage tracking for billing
- **Feature Attribution**: Usage mapped to subscription features
- **Cost Calculation**: Based on log volume and processing complexity
- **Usage Analytics**: Detailed reporting for cost optimization

---

## Integration Examples

### High-Throughput Application Logging
```javascript
// Batch logging for high-performance applications
const batchLogs = async (logs) => {
  const response = await fetch('/v1/ingest/logs/batch', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + token,
      'X-Customer-ID': tenantId,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ logs })
  });
  return response.json();
};

// Usage
const logs = [
  {msg: 'Request started', level: 'info', service: 'api'},
  {msg: 'Database query executed', level: 'debug', service: 'db'},
  {msg: 'Response sent', level: 'info', service: 'api'}
];
await batchLogs(logs);
```

### Infrastructure Log Forwarding
```bash
# Nginx log forwarding with tail and curl
tail -F /var/log/nginx/access.log | while read line; do
  curl -X POST "https://api.logforge.com/v1/ingest/nginx" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Customer-ID: $TENANT_ID" \
    -H "Content-Type: text/plain" \
    -d "$line"
done
```

### Microservice Structured Logging
```python
import requests
import json
from datetime import datetime

class LogforgeHandler:
    def __init__(self, token, tenant_id, service_name):
        self.token = token
        self.tenant_id = tenant_id
        self.service_name = service_name
        self.base_url = "https://api.logforge.com/v1/ingest"
    
    def log(self, message, level="info", **attrs):
        log_entry = {
            "msg": message,
            "level": level,
            "service": self.service_name,
            "ts": datetime.utcnow().isoformat() + "Z",
            "attrs": attrs
        }
        
        response = requests.post(
            f"{self.base_url}/structured",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Customer-ID": self.tenant_id,
                "Content-Type": "application/json"
            },
            json=log_entry
        )
        return response.json()

# Usage
logger = LogforgeHandler(token, tenant_id, "payment-service")
logger.log("Payment processed", level="info", payment_id="PAY-123", amount=99.99)
```

### OpenTelemetry Integration
```javascript
// OTLP log export to Logforge
const otlpLogs = {
  resource_logs: [{
    resource: {
      attributes: [
        {key: "service.name", value: {string_value: "user-service"}},
        {key: "service.version", value: {string_value: "1.0.0"}}
      ]
    },
    scope_logs: [{
      log_records: [{
        time_unix_nano: Date.now() * 1000000,
        severity_number: 9, // INFO
        severity_text: "INFO",
        body: {string_value: "User created successfully"},
        attributes: [
          {key: "user.id", value: {string_value: "user-123"}},
          {key: "operation", value: {string_value: "create_user"}}
        ]
      }]
    }]
  }]
};

fetch('/v1/ingest/otlp', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token,
    'X-Customer-ID': tenantId,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(otlpLogs)
});
```

---

## Best Practices

### Ingestion Optimization
1. **Use Batch Ingestion**: For high-volume scenarios, prefer `/logs/batch` over single log ingestion
2. **Structured Data**: Use structured attributes for better queryability
3. **Consistent Timestamps**: Always include ISO 8601 timestamps
4. **Service Identification**: Include service names for better log organization

### Error Handling
1. **Retry Logic**: Implement exponential backoff for failed requests
2. **Validation**: Validate log structure before sending
3. **Error Monitoring**: Monitor ingestion error rates
4. **Fallback Strategy**: Have backup ingestion methods for critical logs

### Performance Guidelines
1. **Batch Size**: Optimal batch size is 100-1000 logs per request
2. **Concurrent Requests**: Limit concurrent ingestion requests to 10-20
3. **Data Size**: Keep individual log messages under 64KB
4. **Rate Limiting**: Respect API rate limits (varies by subscription tier)

### Security Considerations
1. **Token Security**: Secure storage and rotation of Bearer tokens
2. **Data Sanitization**: Remove sensitive data before ingestion
3. **Tenant Isolation**: Always include correct X-Customer-ID header
4. **Network Security**: Use HTTPS for all ingestion requests

---

## API Reference Summary

| Endpoint | Method | Format | Purpose | Auth Required |
|----------|--------|---------|---------|---------------|
| `/v1/ingest/logs` | POST | JSON | Single structured log | ✓ |
| `/v1/ingest/logs/batch` | POST | JSON | Multiple structured logs | ✓ |
| `/v1/ingest/logs/bulk` | POST | JSON | Bulk data ingestion | ✓ |
| `/v1/ingest/structured` | POST | JSON | Structured JSON logs | ✓ |
| `/v1/ingest/otlp` | POST | OTLP | OpenTelemetry logs | ✓ |
| `/v1/ingest/syslog` | POST | Syslog | RFC 3164/5424 logs | ✓ |
| `/v1/ingest/nginx` | POST | Text | Nginx access logs | ✓ |
| `/v1/ingest/cef` | POST | CEF | Common Event Format | ✓ |
| `/v1/ingest/text` | POST | Text | Plain text logs | ✓ |
| `/v1/ingest` | POST | Auto | Format auto-detection | ✓ |

**Total Endpoints**: 9  
**Supported Formats**: 7 distinct log formats  
**Processing Model**: Asynchronous background processing  
**Multi-tenant**: Complete tenant isolation enforced