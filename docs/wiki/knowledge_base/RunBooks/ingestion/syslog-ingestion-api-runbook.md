# Syslog Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/syslog` API endpoint for syslog format log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/syslog`  
**Content-Type**: `text/plain`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The syslog ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual syslog log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from syslog timestamp with year added for RFC 3164
- `level`: Converted from syslog severity number
- `msg`: Syslog message content
- `service`: Extracted from syslog program field
- `host`: Extracted from syslog hostname field
- `severity_num`: Syslog severity number (0-7)
- `facility`: Syslog facility number
- `raw_log`: Original syslog message
- `source_format`: "syslog"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.syslog"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records (always 1 for single log)
- `bytes_processed`: Total bytes from syslog message content
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
- `endpoint`: "/syslog"
- `source_format`: "syslog"
- `log_count`: Number of logs processed (always 1)
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: 1 (for successful requests)
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## Syslog Format Support

The syslog endpoint supports multiple syslog standards:

### RFC 5424 (Modern Syslog)
```
<165>1 2025-10-08T12:34:56.789Z web-server.example.com app-name 1234 ID47 [exampleSDID@32473 iut="3" eventSource="Application"] Application started successfully
```

### RFC 3164 (Traditional BSD Syslog)
```
<134>Oct  8 12:34:56 syslog-test-host logforge-test: Syslog ingestion test - RFC 3164 format log entry
```

### Simple Syslog Format
```
Oct  8 12:34:56 hostname program[pid]: Log message content
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/syslog HTTP/1.1
Host: localhost:7080
Content-Type: text/plain
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### RFC 3164 Format
```bash
curl -X POST "http://localhost:7080/v1/ingest/syslog" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '<134>Oct  8 12:34:56 syslog-test-host logforge-test: Syslog ingestion test - RFC 3164 format log entry with priority 134, facility local0, severity info'
```

#### RFC 5424 Format
```bash
curl -X POST "http://localhost:7080/v1/ingest/syslog" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '<165>1 2025-10-08T12:34:56.789Z web-server app-name 1234 ID47 [meta sequenceId="123"] Application started successfully'
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
// Invalid syslog format
{
  "detail": "No valid log records found in syslog data"
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
  "detail": "Syslog parsing failed: Invalid priority value"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **Raw Data Extraction**: Read request body as UTF-8 text
3. **Syslog Parsing**: Parse using RFC 5424/3164/simple patterns
4. **Log Preparation**: Convert to LogEntry object with metadata
5. **Background Task Scheduling**: Queue tracking operations for background processing
6. **Fast Response**: Return 200 OK immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Syslog Parser Features

### Priority Parsing
- **Facility Extraction**: `facility = priority >> 3`
- **Severity Extraction**: `severity = priority & 0x07`
- **Level Mapping**: Severity numbers to standard log levels

| Severity | Number | Log Level |
|----------|--------|-----------|
| Emergency | 0 | fatal |
| Alert | 1 | fatal |
| Critical | 2 | fatal |
| Error | 3 | error |
| Warning | 4 | warn |
| Notice | 5 | info |
| Info | 6 | info |
| Debug | 7 | debug |

### Timestamp Handling
- **RFC 5424**: Full ISO format with timezone
- **RFC 3164**: Month day time format (year added automatically)
- **Normalization**: All timestamps converted to UTC ISO format

### Pattern Matching
1. **RFC 5424 Pattern**: `<priority>version timestamp hostname program procid msgid structured_data message`
2. **RFC 3164 Pattern**: `<priority>timestamp hostname program[pid]: message`
3. **Simple Pattern**: `timestamp hostname program[pid]: message`
4. **Fallback**: Treat entire input as message if no pattern matches

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for high-volume syslog ingestion

### Resource Usage
- **Memory**: Minimal - single log processing with immediate handoff
- **CPU**: Low main thread usage, background processing distributed
- **Database**: Optimized single log operations

## Error Handling

### Validation Errors
- Invalid syslog priority → 400 Bad Request
- Malformed timestamp → Fallback to current time
- Missing message content → 400 Bad Request

### Processing Errors
- Parser exceptions → 400 Bad Request with specific error
- Database errors → Background error logging
- Quota exceeded → Quota enforcement (non-blocking)

## Monitoring & Troubleshooting

### Key Metrics to Monitor
- **ingestion_stats_mt**: Processing times, success/error rates
- **usage_records_mt**: Usage volumes and cost calculations
- **tenant_quotas_mt**: Quota utilization per tenant
- **logs_raw_mt**: Actual log storage and retrieval

### Common Issues
1. **Authentication Failures**: Check Bearer token validity
2. **Invalid Syslog Format**: Validate against RFC 3164/5424 standards
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Priority Parsing**: Check priority value is valid (0-191)

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Validate Syslog Format**: Test with minimal syslog payload
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## Syslog Format Examples

### Production Web Server (RFC 3164)
```
<134>Oct  8 14:23:45 web-01 nginx: 192.168.1.100 - - [08/Oct/2025:14:23:45 +0000] "GET /api/health HTTP/1.1" 200 45
```

### Security Event (RFC 5424)
```
<133>1 2025-10-08T14:23:45.123Z firewall-01 iptables 1234 DENY [meta severity="high"] DROP: IN=eth0 OUT= SRC=192.168.1.100 DST=10.0.0.1
```

### Application Log (Simple Format)
```
Oct  8 14:23:45 app-server myapp[5678]: User login successful for user@example.com
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: All syslog fields validated before processing
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

### Syslog Security
- **Priority Validation**: Ensure priority values are within valid range (0-191)
- **Content Sanitization**: Prevent log injection attacks
- **Size Limits**: Reasonable message size limits to prevent DoS

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of syslog message content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient Parsing**: Single-pass parsing with minimal memory allocation
- **Background Processing**: No blocking operations affecting throughput
- **Single Log Operations**: Optimized for individual syslog message processing

## Integration Examples

### Syslog Forwarder Configuration
```bash
# rsyslog configuration to forward to Logforge
*.* @@logforge-api.example.com:514
```

### Docker Container Syslog
```bash
docker run --log-driver syslog --log-opt syslog-address=tcp://localhost:514 myapp
```

### Python Syslog Client
```python
import socket
import time

def send_syslog(message, priority=134):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    timestamp = time.strftime("%b %d %H:%M:%S", time.localtime())
    syslog_msg = f"<{priority}>{timestamp} myhost myapp: {message}"
    sock.sendto(syslog_msg.encode(), ('localhost', 514))
    sock.close()
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team