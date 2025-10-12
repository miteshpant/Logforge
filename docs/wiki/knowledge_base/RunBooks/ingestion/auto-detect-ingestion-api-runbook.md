# Auto-Detect Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest` API endpoint for automatic format detection and log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest`  
**Content-Type**: `application/json` or `text/plain`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The auto-detect ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from detected format or current time
- `level`: Extracted based on detected format
- `msg`: Message content from detected format
- `service`: Service name from detected format
- `host`: Hostname from detected format
- `trace_id`, `span_id`: Tracing information (if available)
- `raw_log`: Original log content
- `source_format`: Detected format (json, otlp, syslog, nginx, cef, text)

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.auto_detect"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records
- `bytes_processed`: Total bytes from log content
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
- `endpoint`: "/ingest"
- `source_format`: Detected format
- `log_count`: Number of logs processed
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: Number of successful logs
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## Format Detection Logic

The auto-detect endpoint uses intelligent format detection based on content type and content analysis:

### JSON Content Detection (`application/json`)
```
Content-Type: application/json
```

#### OTLP Format Detection
```json
{
  "resource_logs": [
    // OpenTelemetry Protocol structure
  ]
}
```
**Detection**: Presence of `resource_logs` key → **OTLP format**

#### Regular JSON Format
```json
{
  "msg": "Log message",
  "level": "info",
  "service": "api-gateway"
}
```
**Detection**: Standard JSON without OTLP structure → **JSON format**

### Text Content Detection (`text/plain` or other)

#### CEF Format Detection
```
CEF:0|Vendor|Product|Version|ID|Name|Severity|Extensions
```
**Detection**: Starts with `<` AND contains `CEF:` → **CEF format**

#### Syslog Format Detection
```
<134>Oct  8 12:34:56 hostname program: message
```
**Detection**: Starts with `<` (priority) → **Syslog format**

#### Nginx Format Detection
```
192.168.1.100 - admin [08/Oct/2025:12:34:56 +0000] "GET /api HTTP/1.1" 200 45
```
**Detection**: Contains ` - ` AND `[` patterns → **Nginx format**

#### Text Format Detection
```
2025-10-08 12:34:56 INFO Application started
```
**Detection**: All other text content → **Text format**

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest HTTP/1.1
Host: localhost:7080
Content-Type: application/json | text/plain
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### JSON Auto-Detection
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "service": "auto-detect-service",
    "msg": "Auto-detect ingestion test",
    "ts": "2025-10-09T12:34:56.789Z",
    "level": "info",
    "host": "auto-detect-host"
  }'
```

#### OTLP Auto-Detection
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "resource_logs": [
      {
        "resource": {
          "attributes": [
            {"key": "service.name", "value": "otlp-service"}
          ]
        },
        "scope_logs": [
          {
            "log_records": [
              {
                "time_unix_nano": 1633024496789000000,
                "severity_text": "INFO",
                "body": "OTLP log detected automatically"
              }
            ]
          }
        ]
      }
    ]
  }'
```

#### Syslog Auto-Detection
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '<134>Oct  9 12:34:56 auto-detect-host syslog-test: Syslog format detected automatically'
```

#### CEF Auto-Detection
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d 'CEF:0|AutoDetect|Security|1.0|100|Test Event|5|src=192.168.1.100 act=test'
```

#### Text Auto-Detection
```bash
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '2025-10-09 12:34:56 INFO Text format detected and processed automatically'
```

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Successfully ingested 1 logs - detected format: json",
  "processed_count": 1
}
```

### Format Detection Examples
```json
// JSON format detected
{
  "status": "success",
  "message": "Successfully ingested 1 logs - detected format: json",
  "processed_count": 1
}

// OTLP format detected
{
  "status": "success", 
  "message": "Successfully ingested 3 logs - detected format: otlp",
  "processed_count": 3
}

// Syslog format detected
{
  "status": "success",
  "message": "Successfully ingested 1 logs - detected format: syslog", 
  "processed_count": 1
}
```

### Error Responses
```json
// No valid data found
{
  "detail": "No valid log records found in auto-detected data"
}

// Invalid JSON format
{
  "detail": "Invalid JSON format"
}

// Authentication error
{
  "detail": "Invalid or expired session"
}

// Auto-detection failed
{
  "detail": "Auto-detection failed: Unable to determine log format"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **Content-Type Analysis**: Check HTTP Content-Type header
3. **Format Detection**: Apply detection logic based on content
4. **Parser Selection**: Route to appropriate format parser
5. **Log Preparation**: Convert to LogEntry objects with metadata
6. **Background Task Scheduling**: Queue tracking operations for background processing
7. **Fast Response**: Return 200 OK with detected format

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Auto-Detection Features

### Content-Type Based Detection
- **JSON Content**: `application/json` → JSON/OTLP detection
- **Text Content**: `text/plain` or others → Text-based format detection
- **Fallback**: Unknown content types treated as text

### Pattern-Based Detection
1. **JSON Analysis**: Check for OTLP-specific keys
2. **Text Analysis**: Apply regex patterns for format identification
3. **Priority Order**: CEF → Syslog → Nginx → Text (fallback)

### Format-Specific Processing
Each detected format uses its dedicated parser:
- **JSON**: LogEntry validation
- **OTLP**: OpenTelemetry Protocol parsing
- **Syslog**: RFC 3164/5424 parsing
- **CEF**: Common Event Format parsing
- **Nginx**: Access log parsing
- **Text**: Pattern-based text parsing

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Detection Overhead**: < 5ms additional processing
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for mixed format ingestion

### Resource Usage
- **Memory**: Minimal detection overhead
- **CPU**: Efficient pattern matching algorithms
- **Database**: Format-specific optimized operations

## Error Handling

### Detection Errors
- Unknown format → Fallback to text processing
- Invalid JSON → 400 Bad Request
- Empty content → 400 Bad Request

### Processing Errors
- Parser-specific errors → Format-specific error handling
- Database errors → Background error logging
- Quota exceeded → Quota enforcement (non-blocking)

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **ingestion_stats_mt**: Processing times, format distribution
- **usage_records_mt**: Usage volumes by detected format
- **tenant_quotas_mt**: Quota utilization per tenant
- **logs_raw_mt**: Actual log storage and retrieval
- **Format Detection**: Success rates by format type

### Format Distribution Analysis
Monitor which formats are being detected:
```sql
SELECT 
    source_format,
    COUNT(*) as log_count,
    AVG(processing_time_ms) as avg_processing_time
FROM ingestion_stats_mt 
WHERE endpoint = '/ingest'
    AND timestamp >= now() - INTERVAL 1 HOUR
GROUP BY source_format
ORDER BY log_count DESC;
```

### Common Issues
1. **Authentication Failures**: Check Bearer token validity
2. **Format Misdetection**: Verify content matches expected format
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Content-Type Issues**: Check HTTP headers are set correctly

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Test Detection Logic**: Send known format samples
3. **Monitor Background Tasks**: Check ingestion_stats_mt for metrics
4. **Analyze Format Distribution**: Review detection patterns

## Auto-Detection Examples

### Mixed Format Ingestion
```bash
# JSON format (Content-Type: application/json)
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{"msg": "JSON format detected", "level": "info"}'

# Syslog format (Content-Type: text/plain)  
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '<134>Oct  9 12:34:56 host app: Syslog format detected'

# Nginx format (Content-Type: text/plain)
curl -X POST "http://localhost:7080/v1/ingest" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '192.168.1.100 - - [09/Oct/2025:12:34:56 +0000] "GET / HTTP/1.1" 200 45'
```

### Response Format Detection
```json
// JSON detected
{"status": "success", "message": "Successfully ingested 1 logs - detected format: json", "processed_count": 1}

// Syslog detected  
{"status": "success", "message": "Successfully ingested 1 logs - detected format: syslog", "processed_count": 1}

// Nginx detected
{"status": "success", "message": "Successfully ingested 1 logs - detected format: nginx", "processed_count": 1}
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Format Validation**: Each format uses dedicated validation
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest

### Auto-Detection Security
- **Pattern Validation**: Ensure detected patterns are safe
- **Content Sanitization**: Format-specific sanitization applied
- **Size Limits**: Reasonable payload limits to prevent DoS

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of log content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with format breakdown

### Cost Optimization
- **Detection Efficiency**: Minimal overhead for format detection
- **Format-Specific Processing**: Optimized parsers for each format
- **Background Processing**: No blocking operations affecting throughput

## Integration Examples

### Multi-Format Log Forwarder
```python
import requests
import json

class AutoDetectLogger:
    def __init__(self, api_url, auth_token, tenant_id):
        self.api_url = api_url
        self.headers_json = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
        self.headers_text = {
            'Content-Type': 'text/plain',
            'Authorization': f'Bearer {auth_token}',
            'X-Customer-ID': tenant_id
        }
    
    def send_log(self, log_data):
        """Send log with automatic format detection"""
        if isinstance(log_data, (dict, list)):
            # JSON format
            response = requests.post(
                self.api_url, 
                json=log_data, 
                headers=self.headers_json
            )
        else:
            # Text format (syslog, nginx, cef, etc.)
            response = requests.post(
                self.api_url, 
                data=str(log_data), 
                headers=self.headers_text
            )
        
        return response.json()

# Usage examples
logger = AutoDetectLogger(
    'http://localhost:7080/v1/ingest',
    'your-auth-token', 
    'your-tenant-id'
)

# Send JSON log
logger.send_log({
    'msg': 'Application started',
    'level': 'info',
    'service': 'web-app'
})

# Send syslog
logger.send_log('<134>Oct  9 12:34:56 host app: Syslog message')

# Send nginx log
logger.send_log('192.168.1.100 - - [09/Oct/2025:12:34:56 +0000] "GET / HTTP/1.1" 200 45')
```

### Universal Log Collector
```bash
#!/bin/bash
# Universal log forwarder script

API_URL="http://localhost:7080/v1/ingest"
AUTH_TOKEN="your-auth-token"
TENANT_ID="your-tenant-id"

send_log() {
    local log_data="$1"
    local content_type="$2"
    
    curl -s -X POST "$API_URL" \
        -H "Content-Type: $content_type" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "X-Customer-ID: $TENANT_ID" \
        -d "$log_data"
}

# Monitor multiple log files with auto-detection
tail -F /var/log/nginx/access.log | while read line; do
    send_log "$line" "text/plain"
done &

tail -F /var/log/syslog | while read line; do  
    send_log "$line" "text/plain"
done &

tail -F /var/log/app/application.json | while read line; do
    send_log "$line" "application/json"  
done &

wait
```

### Kubernetes Log Collection
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush         1
        Log_Level     info

    [INPUT]
        Name              tail
        Path              /var/log/containers/*.log
        Parser            docker
        Tag               kube.*

    [OUTPUT]
        Name              http
        Match             *
        Host              logforge-api.example.com
        Port              7080
        URI               /v1/ingest
        Format            json
        Header            Authorization Bearer YOUR_TOKEN
        Header            X-Customer-ID YOUR_TENANT_ID
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team