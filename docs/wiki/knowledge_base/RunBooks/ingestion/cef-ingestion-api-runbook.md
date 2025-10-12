# CEF Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/cef` API endpoint for Common Event Format (CEF) log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/cef`  
**Content-Type**: `text/plain`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The CEF ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual CEF log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from CEF timestamp or current time
- `level`: Mapped from CEF severity (0-10 scale)
- `msg`: CEF message field
- `service`: CEF device vendor + product
- `host`: CEF device hostname or IP
- `src_ip`: Source IP from CEF extensions
- `status`: Mapped from CEF outcome field
- `raw_log`: Original CEF message
- `source_format`: "cef"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.cef"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records (always 1 for single log)
- `bytes_processed`: Total bytes from CEF message content
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
- `endpoint`: "/cef"
- `source_format`: "cef"
- `log_count`: Number of logs processed (always 1)
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: 1 (for successful requests)
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## CEF Format Support

The CEF endpoint supports the standard Common Event Format (CEF) specification:

### CEF Header Format
```
CEF:Version|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|Extension
```

### Example CEF Messages

#### Security Event
```
CEF:0|Logforge|Security|1.0|100|User Login Attempt|5|src=192.168.1.100 suser=testuser dhost=auth-server act=login outcome=success
```

#### Network Event
```
CEF:0|Cisco|ASA|9.8|106023|Firewall Deny|3|src=10.0.0.1 dst=192.168.1.100 spt=443 dpt=80 proto=TCP
```

#### Application Event
```
CEF:0|Microsoft|Windows|10|4625|Failed Logon|7|src=192.168.1.50 suser=admin dhost=DC01 outcome=failure
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/cef HTTP/1.1
Host: localhost:7080
Content-Type: text/plain
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Commands

#### Security Event
```bash
curl -X POST "http://localhost:7080/v1/ingest/cef" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d 'CEF:0|Logforge|Security|1.0|100|User Login Attempt|5|src=192.168.1.100 suser=testuser dhost=auth-server act=login outcome=success'
```

#### Firewall Event
```bash
curl -X POST "http://localhost:7080/v1/ingest/cef" \
  -H "Content-Type: text/plain" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d 'CEF:0|Palo Alto|NGFW|10.1|TRAFFIC|Traffic Denied|6|src=10.1.1.100 dst=8.8.8.8 spt=12345 dpt=53 proto=UDP act=denied'
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
// Invalid CEF format
{
  "detail": "No valid log records found in CEF data"
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
  "detail": "CEF parsing failed: Invalid CEF header format"
}
```

## Code Flow Analysis

### Main Request Processing (Sub-50ms)
1. **Authentication**: JWT token validation + tenant ID verification
2. **Raw Data Extraction**: Read request body as UTF-8 text
3. **CEF Parsing**: Parse CEF header and extensions
4. **Log Preparation**: Convert to LogEntry object with metadata
5. **Background Task Scheduling**: Queue tracking operations for background processing
6. **Fast Response**: Return 200 OK immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## CEF Parser Features

### Header Parsing
- **Version**: CEF format version (usually 0)
- **Device Vendor**: Security device manufacturer
- **Device Product**: Product name/model
- **Device Version**: Software/firmware version
- **Signature ID**: Event type identifier
- **Event Name**: Human-readable event description
- **Severity**: Numeric severity (0-10 scale)

### Extension Fields
- **src**: Source IP address
- **dst**: Destination IP address
- **spt**: Source port
- **dpt**: Destination port
- **suser**: Source user
- **duser**: Destination user
- **act**: Action taken
- **outcome**: Event outcome (success/failure)
- **msg**: Additional message text

### Severity Mapping
| CEF Severity | Log Level | Description |
|--------------|-----------|-------------|
| 0-2 | debug | Low priority events |
| 3-4 | info | Informational events |
| 5-6 | warn | Warning events |
| 7-8 | error | Error events |
| 9-10 | fatal | Critical/fatal events |

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Optimized for high-volume CEF log ingestion

### Resource Usage
- **Memory**: Minimal - single log processing with immediate handoff
- **CPU**: Low main thread usage, background processing distributed
- **Database**: Optimized single log operations

## Error Handling

### Validation Errors
- Invalid CEF header format → 400 Bad Request
- Missing required CEF fields → Fallback to defaults
- Malformed extensions → Parse available fields

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
2. **Invalid CEF Format**: Validate against CEF specification
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Extension Parsing**: Check CEF extension field formatting

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Validate CEF Format**: Test with standard CEF message
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## CEF Log Examples

### Authentication Events
```
CEF:0|Microsoft|Active Directory|2019|4624|Successful Logon|4|src=192.168.1.100 suser=john.doe dhost=DC01 act=logon outcome=success
CEF:0|Microsoft|Active Directory|2019|4625|Failed Logon|7|src=192.168.1.50 suser=admin dhost=DC01 act=logon outcome=failure
```

### Network Security Events
```
CEF:0|Cisco|ASA|9.8|106023|Firewall Deny|6|src=10.0.0.1 dst=192.168.1.100 spt=443 dpt=80 proto=TCP act=denied
CEF:0|Palo Alto|NGFW|10.1|THREAT|Malware Detected|9|src=192.168.1.50 dst=8.8.8.8 act=blocked fname=malware.exe
```

### Application Security Events
```
CEF:0|OWASP|ModSecurity|3.0|950001|SQL Injection|8|src=192.168.1.200 request=/login.php?id=1' OR 1=1-- act=blocked
CEF:0|F5|BIG-IP|15.1|XSS|Cross-Site Scripting|7|src=10.1.1.50 request=/search?q=<script>alert(1)</script> act=blocked
```

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: All CEF fields validated before processing
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

### CEF Security
- **Field Validation**: Ensure CEF fields are properly formatted
- **Content Sanitization**: Prevent log injection attacks
- **Size Limits**: Reasonable message size limits to prevent DoS

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of CEF message content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient Parsing**: Single-pass parsing with minimal memory allocation
- **Background Processing**: No blocking operations affecting throughput
- **Single Log Operations**: Optimized for individual CEF message processing

## Integration Examples

### Syslog to CEF Forwarding
```bash
# rsyslog configuration for CEF log forwarding
$ModLoad imfile
$InputFileName /var/log/security/cef.log
$InputFileTag cef-security:
$InputFileStateFile stat-cef-security
$InputFileSeverity info
$InputFileFacility local1
$InputRunFileMonitor

*.* @@logforge-api.example.com:514
```

### Splunk Universal Forwarder
```conf
[monitor:///var/log/security/cef.log]
disabled = false
sourcetype = cef
index = security

[tcpout:logforge]
server = logforge-api.example.com:7080
```

### Python CEF Generation
```python
import requests
from datetime import datetime

def send_cef_event(vendor, product, event_id, name, severity, **extensions):
    cef_header = f"CEF:0|{vendor}|{product}|1.0|{event_id}|{name}|{severity}"
    cef_extensions = "|".join([f"{k}={v}" for k, v in extensions.items()])
    cef_message = f"{cef_header}|{cef_extensions}"
    
    headers = {
        'Content-Type': 'text/plain',
        'Authorization': f'Bearer {AUTH_TOKEN}',
        'X-Customer-ID': TENANT_ID
    }
    
    response = requests.post(
        'http://localhost:7080/v1/ingest/cef',
        data=cef_message,
        headers=headers
    )
    return response

# Example usage
send_cef_event(
    vendor="MyApp",
    product="WebServer",
    event_id="1001", 
    name="Login Success",
    severity=4,
    src="192.168.1.100",
    suser="john.doe",
    act="login",
    outcome="success"
)
```

### Security Device Integration
```bash
# Example: Palo Alto Networks firewall syslog config
set deviceconfig system syslog-certificate logforge-cert
set shared log-settings syslog logforge server logforge-api.example.com
set shared log-settings syslog logforge port 514
set shared log-settings syslog logforge format CEF
set shared log-settings syslog logforge facility LOG_USER
```

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team