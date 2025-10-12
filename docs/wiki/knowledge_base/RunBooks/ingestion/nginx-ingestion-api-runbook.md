# Nginx Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/nginx` API endpoint for Nginx access log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/nginx`  
**Content-Type**: `text/plain`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The nginx ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual nginx log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from nginx access log timestamp
- `level`: "info" (default for access logs)
- `msg`: Full nginx access log line
- `service`: "nginx" (default service name)
- `host`: Extracted from nginx log or server name
- `src_ip`: Client IP address from access log
- `status`: HTTP status code (200, 404, 500, etc.)
- `raw_log`: Original nginx access log line
- `source_format`: "nginx"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.nginx"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records (always 1 for single log)
- `bytes_processed`: Total bytes from nginx log content
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
- `endpoint`: "/nginx"
- `source_format`: "nginx"
- `log_count`: Number of logs processed (always 1)
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: 1 (for successful requests)
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## Nginx Log Format Support

The nginx endpoint supports multiple nginx access log formats:

### Combined Log Format (Most Common)
```
192.168.1.100 - admin [08/Oct/2025:12:34:56 +0000] "GET /api/health HTTP/1.1" 200 45 "https://example.com/dashboard" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### Common Log Format
```
192.168.1.100 - admin [08/Oct/2025:12:34:56 +0000] "GET /api/health HTTP/1.1" 200 45
```

### JSON Log Format
```json
{"remote_addr":"192.168.1.100","time_local":"08/Oct/2025:12:34:56 +0000","method":"GET","uri":"/api/health","status":200,"body_bytes_sent":45}
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/nginx HTTP/1.1
Host: localhost:7080
Content-Type: text/plain
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### Combined Format
```bash
curl -X POST "http://localhost:7080/v1/ingest/nginx" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '192.168.1.100 - admin [08/Oct/2025:12:34:56 +0000] "GET /api/health HTTP/1.1" 200 45 "https://example.com/dashboard" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"'
```

#### JSON Format
```bash
curl -X POST "http://localhost:7080/v1/ingest/nginx" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{"remote_addr":"192.168.1.100","time_local":"08/Oct/2025:12:34:56 +0000","method":"GET","uri":"/api/health","status":200,"body_bytes_sent":45}'
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
// Invalid nginx format
{
  "detail": "No valid log records found in nginx data"
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
  "detail": "Nginx log parsing failed: Invalid access log format"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **Raw Data Extraction**: Read request body as UTF-8 text
3. **Nginx Parsing**: Parse using combined/common/JSON patterns
4. **Log Preparation**: Convert to LogEntry object with metadata
5. **Background Task Scheduling**: Queue tracking operations for background processing
6. **Fast Response**: Return 200 OK immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Nginx Parser Features

### Field Extraction
- **IP Address**: Client IP from remote_addr
- **Timestamp**: Parse nginx timestamp format to ISO
- **HTTP Method**: GET, POST, PUT, DELETE, etc.
- **URI**: Requested URL path
- **Status Code**: HTTP response status
- **Response Size**: Bytes sent to client
- **Referrer**: HTTP referrer header
- **User Agent**: Client browser/application

### Pattern Matching
1. **Combined Pattern**: Full access log with referrer and user agent
2. **Common Pattern**: Basic access log without referrer/user agent
3. **JSON Pattern**: Structured JSON nginx logs
4. **Fallback**: Treat entire input as message if no pattern matches

### Data Transformation
- **Timestamp**: Convert nginx timestamp to ISO format
- **Status Mapping**: Preserve HTTP status codes
- **IP Extraction**: Extract client IP for security analysis
- **User Agent Parsing**: Preserve user agent for analytics

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for high-volume nginx log ingestion

### Resource Usage
- **Memory**: Minimal - single log processing with immediate handoff
- **CPU**: Low main thread usage, background processing distributed
- **Database**: Optimized single log operations

## Error Handling

### Validation Errors
- Invalid nginx log format → 400 Bad Request
- Malformed timestamp → Fallback to current time
- Missing request data → 400 Bad Request

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
2. **Invalid Nginx Format**: Validate against standard nginx log formats
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Timestamp Parsing**: Check nginx timestamp format compatibility

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Validate Nginx Format**: Test with standard nginx access log
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## Nginx Log Examples

### Production Web Server
```
10.0.0.1 - - [08/Oct/2025:14:23:45 +0000] "GET /api/users/123 HTTP/1.1" 200 1024 "https://app.example.com/dashboard" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

### API Gateway Logs
```
192.168.1.100 - apikey [08/Oct/2025:14:23:45 +0000] "POST /v1/data/ingest HTTP/1.1" 201 256 "-" "curl/7.68.0"
```

### Load Balancer Logs
```
172.16.0.5 - - [08/Oct/2025:14:23:45 +0000] "GET /health HTTP/1.1" 200 2 "-" "ELB-HealthChecker/2.0"
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: All nginx fields validated before processing
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

### Nginx Security
- **IP Validation**: Ensure IP addresses are properly formatted
- **Content Sanitization**: Prevent log injection attacks
- **Size Limits**: Reasonable log line size limits to prevent DoS

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of nginx log content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient Parsing**: Single-pass parsing with minimal memory allocation
- **Background Processing**: No blocking operations affecting throughput
- **Single Log Operations**: Optimized for individual nginx log processing

## Integration Examples

### Nginx Configuration
```nginx
# Standard combined log format
log_format combined '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent"';

# Custom JSON format
log_format json_combined escape=json
  '{'
    '"time_local":"$time_local",'
    '"remote_addr":"$remote_addr",'
    '"remote_user":"$remote_user",'
    '"request":"$request",'
    '"status": "$status",'
    '"body_bytes_sent":"$body_bytes_sent",'
    '"request_time":"$request_time",'
    '"http_referrer":"$http_referer",'
    '"http_user_agent":"$http_user_agent"'
  '}';

access_log /var/log/nginx/access.log combined;
```

### Log Forwarding with Filebeat
```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/nginx/access.log
  fields:
    logtype: nginx
  
output.http:
  hosts: ["http://logforge-api.example.com:7080"]
  path: "/v1/ingest/nginx"
  headers:
    Authorization: "Bearer YOUR_TOKEN"
    X-Customer-ID: "YOUR_TENANT_ID"
    Content-Type: "text/plain"
```

### Real-time Streaming with rsyslog
```conf
# rsyslog configuration for nginx log forwarding
$ModLoad imfile
$InputFileName /var/log/nginx/access.log
$InputFileTag nginx-access:
$InputFileStateFile stat-nginx-access
$InputFileSeverity info
$InputFileFacility local0
$InputRunFileMonitor

*.* @@logforge-api.example.com:514
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team