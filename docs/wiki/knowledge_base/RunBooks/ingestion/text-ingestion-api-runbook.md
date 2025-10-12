# Text Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/text` API endpoint for plain text log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/text`  
**Content-Type**: `text/plain`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The text ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual text log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from text log or current time
- `level`: Extracted from log text or "info" default
- `msg`: Extracted message content
- `service`: Extracted service name or "unknown"
- `host`: Extracted hostname or default
- `attrs`: Additional extracted attributes
- `raw_log`: Original text log message
- `source_format`: "text"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.text"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records (always 1 for single log)
- `bytes_processed`: Total bytes from text message content
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
- `endpoint`: "/text"
- `source_format`: "text"
- `log_count`: Number of logs processed (always 1)
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: 1 (for successful requests)
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## Text Log Format Support

The text endpoint supports multiple plain text log patterns with intelligent pattern matching:

### Timestamp-Level-Message Pattern
```
2025-10-08 12:34:56.789 INFO Application started successfully on port 8080
2025-10-08T12:34:56.789Z ERROR Database connection failed: timeout after 30s
```

### Level-Timestamp-Message Pattern
```
INFO 2025-10-08 12:34:56.789 User authentication successful
ERROR 2025-10-08T12:34:56.789Z Failed to process request: invalid input
```

### Java Exception Pattern
```
2025-10-08 12:34:56.789 ERROR [main] com.example.Service - Database error occurred
java.sql.SQLException: Connection timeout
    at java.sql.DriverManager.getConnection(DriverManager.java:689)
    at com.example.Database.connect(Database.java:45)
```

### Generic Text (Fallback)
```
Application startup completed
User john.doe logged in successfully
Processing batch job #12345
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/text HTTP/1.1
Host: localhost:7080
Content-Type: text/plain
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### Structured Text Log
```bash
curl -X POST "http://localhost:7080/v1/ingest/text" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '2025-10-08 12:34:56 INFO Application started successfully on port 8080'
```

#### Simple Text Message
```bash
curl -X POST "http://localhost:7080/v1/ingest/text" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d 'User authentication successful for user@example.com'
```

#### Java Exception Log
```bash
curl -X POST "http://localhost:7080/v1/ingest/text" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '2025-10-08 12:34:56.789 ERROR [worker-thread-1] com.example.Service - Database connection failed'
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
// Invalid text data
{
  "detail": "No valid log records found in text data"
}

// Authentication error
{
  "detail": "Invalid or expired session"
}

// Missing tenant header
{
  "detail": "X-Customer-ID header is required"
}

// Parsing error
{
  "detail": "Text parsing failed: Empty message content"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **Raw Data Extraction**: Read request body as UTF-8 text
3. **Text Parsing**: Apply pattern matching to extract fields
4. **Log Preparation**: Convert to LogEntry object with metadata
5. **Background Task Scheduling**: Queue tracking operations for background processing
6. **Fast Response**: Return 200 OK immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Text Parser Features

### Pattern Matching Engine
The text parser uses regex patterns to extract structured data from unstructured text:

#### Pattern 1: Timestamp-Level-Message
```regex
(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+
(?P<level>\w+)\s+(?P<message>.*)
```

#### Pattern 2: Level-Timestamp-Message
```regex
(?P<level>\w+)\s+(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+
(?P<message>.*)
```

#### Pattern 3: Java Exception
```regex
(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+
(?P<level>\w+)\s+\[(?P<thread>[^\]]+)\]\s+(?P<logger>\S+)\s+-\s+(?P<message>.*)
```

### Field Extraction
- **Timestamp**: Parse various timestamp formats to ISO
- **Log Level**: Extract and normalize log levels
- **Message**: Core message content
- **Thread**: Thread name (for Java logs)
- **Logger**: Logger class name (for Java logs)
- **Pattern**: Which pattern was matched

### Fallback Processing
If no patterns match, the parser:
1. Uses current timestamp
2. Sets level to "info"
3. Uses entire input as message
4. Marks pattern as "fallback"

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for high-volume text log ingestion

### Resource Usage
- **Memory**: Minimal - single log processing with immediate handoff
- **CPU**: Low main thread usage, regex processing distributed
- **Database**: Optimized single log operations

## Error Handling

### Validation Errors
- Empty text input → 400 Bad Request
- Invalid encoding → UTF-8 decode error
- Zero-length message → 400 Bad Request

### Processing Errors
- Regex exceptions → Fallback processing
- Database errors → Background error logging
- Quota exceeded → Quota enforcement (non-blocking)

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **ingestion_stats_mt**: Processing times, success/error rates
- **usage_records_mt**: Usage volumes and cost calculations
- **tenant_quotas_mt**: Quota utilization per tenant
- **logs_raw_mt**: Actual log storage and retrieval
- **Pattern Distribution**: Which patterns are matching most frequently

### Common Issues
1. **Authentication Failures**: Check Bearer token validity
2. **Pattern Matching**: Check if text follows supported patterns
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Timestamp Parsing**: Verify timestamp format compatibility

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Test Pattern Matching**: Use sample text with known patterns
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## Text Log Examples

### Application Logs
```
2025-10-08 14:23:45.123 INFO Application server started on port 8080
2025-10-08 14:23:46.456 WARN Configuration file not found, using defaults
2025-10-08 14:23:47.789 ERROR Failed to connect to database: connection timeout
```

### Web Server Logs
```
INFO 2025-10-08T14:23:45.123Z Request processed successfully in 45ms
WARN 2025-10-08T14:23:46.456Z Slow query detected: 2.5s response time
ERROR 2025-10-08T14:23:47.789Z Authentication failed for user: invalid credentials
```

### Java Application Logs
```
2025-10-08 14:23:45.123 ERROR [worker-pool-1] com.example.UserService - User authentication failed
2025-10-08 14:23:46.456 INFO [main] com.example.Application - Starting application context
2025-10-08 14:23:47.789 DEBUG [http-nio-8080-exec-1] com.example.Controller - Processing request
```

### Simple Text Messages
```
User john.doe logged in successfully
Payment processed for order #12345
System maintenance scheduled for 2AM
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: Text content validated before processing
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

### Text Security
- **Content Sanitization**: Prevent log injection attacks
- **Size Limits**: Reasonable message size limits to prevent DoS
- **Pattern Validation**: Ensure extracted fields are properly formatted

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of text message content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient Parsing**: Single-pass regex processing
- **Background Processing**: No blocking operations affecting throughput
- **Single Log Operations**: Optimized for individual text message processing

## Integration Examples

### Application Logging
```python
import requests
import logging

class LogforgeHandler(logging.Handler):
    def __init__(self, api_url, auth_token, tenant_id):
        super().__init__()
        self.api_url = api_url
        self.headers = {
            'Content-Type': 'text/plain',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            requests.post(self.api_url, data=log_entry, headers=self.headers)
        except Exception:
            pass  # Don't let logging errors crash the application

# Usage
logger = logging.getLogger('myapp')
handler = LogforgeHandler(
    'http://localhost:7080/v1/ingest/text',
    'your-auth-token',
    'your-tenant-id'
)
logger.addHandler(handler)
logger.info('Application started successfully')
```

### Log File Forwarding with tail
```bash
#!/bin/bash
# Simple log forwarding script

AUTH_TOKEN="your-auth-token"
TENANT_ID="your-tenant-id"
API_URL="http://localhost:7080/v1/ingest/text"

tail -F /var/log/application.log | while read line; do
    curl -s -X POST "$API_URL" \
        -H "Content-Type: text/plain" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "X-Customer-ID: $TENANT_ID" \
        -d "$line"
done
```

### Systemd Journal Integration
```bash
# Forward systemd journal to Logforge
journalctl -f -u myservice.service --output=short-iso | \
while read line; do
    curl -s -X POST "http://localhost:7080/v1/ingest/text" \
        -H "Content-Type: text/plain" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "X-Customer-ID: $TENANT_ID" \
        -d "$line"
done
```

### Docker Container Logs
```bash
# Forward Docker container logs
docker logs -f container_name 2>&1 | \
while read line; do
    curl -s -X POST "http://localhost:7080/v1/ingest/text" \
        -H "Content-Type: text/plain" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "X-Customer-ID: $TENANT_ID" \
        -d "$line"
done
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team