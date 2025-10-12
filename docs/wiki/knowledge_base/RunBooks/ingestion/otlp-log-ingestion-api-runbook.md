# OTLP Log Ingestion API Runbook

## Overview
This runbook documents the `/v1/ingest/otlp` API endpoint for OpenTelemetry Protocol (OTLP) log ingestion in the Logforge platform.

## API Endpoint Details

**Endpoint**: `POST /v1/ingest/otlp`  
**Content-Type**: `application/json`  
**Authentication**: Bearer token + X-Customer-ID header  

## Database Tables Updated

The OTLP ingestion endpoint updates **4 key database tables** in a non-blocking architecture:

### 1. logs_raw_mt (Primary Storage)
**Purpose**: Stores the actual OTLP log records  
**Update Method**: Bulk insert in main thread  
**Key Fields**:
- `customer_id`: Tenant isolation
- `timestamp`: Parsed from OTLP `time_unix_nano`
- `level`: Converted from OTLP `severity_text`
- `msg`: OTLP log record `body`
- `service`: Extracted from resource attributes `service.name`
- `host`: Extracted from resource attributes `host.name`
- `trace_id`, `span_id`: OTLP tracing context
- `raw_log`: Original OTLP structure (JSON)
- `source_format`: "otlp"

### 2. usage_records_mt (Billing & Usage Tracking)
**Purpose**: Records API usage for billing calculations  
**Update Method**: Background task via `track_usage_with_cost_calculation()`  
**Key Fields**:
- `customer_id`: Tenant isolation
- `feature_name`: "ingestion.otlp"
- `usage_type`: "monthly_ingestion"
- `quantity`: Number of log records
- `bytes_processed`: Total bytes from OTLP message content
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
- `endpoint`: "/otlp"
- `source_format`: "otlp"
- `log_count`: Number of logs processed
- `bytes_processed`: Total bytes ingested
- `processing_time_ms`: API processing time
- `success_count`: Successful log count
- `error_count`: 0 (for successful requests)
- `timestamp`: Processing timestamp

## OTLP Data Structure

The OTLP endpoint accepts OpenTelemetry Protocol logs with this structure:

```json
{
  "resource_logs": [
    {
      "resource": {
        "attributes": [
          {"key": "service.name", "value": "otlp-service"},
          {"key": "host.name", "value": "host-01"},
          {"key": "deployment.environment", "value": "production"}
        ]
      },
      "scope_logs": [
        {
          "scope": {
            "name": "instrumentation-library",
            "version": "1.0.0"
          },
          "log_records": [
            {
              "time_unix_nano": 1633024496789000000,
              "severity_number": 9,
              "severity_text": "INFO",
              "body": "Application started successfully",
              "attributes": [
                {"key": "http.method", "value": "POST"},
                {"key": "http.status_code", "value": 200}
              ],
              "trace_id": "0102030405060708090a0b0c0d0e0f10",
              "span_id": "0102030405060708"
            }
          ]
        }
      ]
    }
  ]
}
```

## Authentication & Request Format

### Required Headers
```http
POST /v1/ingest/otlp HTTP/1.1
Host: localhost:7080
Content-Type: application/json
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45
```

### Sample cURL Command
```bash
curl -X POST "http://localhost:7080/v1/ingest/otlp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Customer-ID: $TENANT_ID" \
  -d '{
    "resource_logs": [
      {
        "resource": {
          "attributes": [
            {"key": "service.name", "value": "otlp-test-service"},
            {"key": "host.name", "value": "otlp-test-host"}
          ]
        },
        "scope_logs": [
          {
            "scope": {"name": "test-instrumentation", "version": "1.0.0"},
            "log_records": [
              {
                "time_unix_nano": 1633024496789000000,
                "severity_number": 9,
                "severity_text": "INFO",
                "body": "OTLP test log entry",
                "trace_id": "0102030405060708090a0b0c0d0e0f10",
                "span_id": "0102030405060708"
              }
            ]
          }
        ]
      }
    ]
  }'
```

## Response Format

### Success Response (202 Accepted)
```json
{
  "status": "accepted",
  "message": "Successfully accepted 1 OTLP logs for processing",
  "processed_count": 1,
  "error_count": 0
}
```

### Error Responses
```json
// Invalid OTLP format
{
  "detail": "No valid log records found in OTLP data"
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
2. **OTLP Parsing**: Parse OTLP structure using dedicated parser
3. **Log Preparation**: Convert OTLP records to LogEntry objects
4. **Background Task Scheduling**: Queue tracking operations for background processing
5. **Fast Response**: Return 202 Accepted immediately

### Background Processing (Non-blocking)
1. **Log Storage**: Bulk insert to `logs_raw_mt` table
2. **Usage Tracking**: Record usage metrics with cost calculation
3. **Quota Updates**: Update tenant quota counters
4. **Performance Metrics**: Store ingestion performance data

## Performance Characteristics

### Response Time Targets
- **API Response**: < 50ms (sub-50ms achieved)
- **Database Operations**: Non-blocking background processing
- **Throughput**: Designed for high-volume OTLP ingestion

### Resource Usage
- **Memory**: Minimal - immediate processing handoff to background
- **CPU**: Low main thread usage, background processing distributed
- **Database**: Optimized bulk operations, minimal locking

## OTLP Parser Features

### Supported OTLP Elements
- **Resource Logs**: Complete OTLP resource_logs structure
- **Resource Attributes**: Service name, host name, environment, etc.
- **Scope Logs**: Instrumentation library information
- **Log Records**: Full log record structure with attributes
- **Tracing Context**: Trace ID and Span ID extraction
- **Severity Mapping**: OTLP severity numbers to standard log levels

### Data Transformation
- **Timestamp**: Convert `time_unix_nano` to ISO format
- **Severity**: Map OTLP severity numbers to log levels
- **Attributes**: Flatten OTLP attributes to key-value pairs
- **Resource Context**: Extract service and host from resource attributes
- **Tracing**: Preserve trace_id and span_id for correlation

## Error Handling

### Validation Errors
- Invalid OTLP structure → 400 Bad Request
- Missing required fields → 400 Bad Request
- Empty log records → 400 Bad Request

### Processing Errors
- Parser exceptions → 500 Internal Server Error
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
2. **Invalid OTLP Format**: Validate against OpenTelemetry specification
3. **Tenant Isolation**: Ensure X-Customer-ID header is correct
4. **Performance Issues**: Monitor background task queue depth

### Debugging Steps
1. **Check Authentication**: Verify JWT token and tenant ID
2. **Validate OTLP Structure**: Test with minimal OTLP payload
3. **Monitor Background Tasks**: Check ingestion_stats_mt for processing metrics
4. **Database Verification**: Query logs_raw_mt for stored records

## Security Considerations

### Authentication
- **JWT Tokens**: Must be valid and non-expired
- **Tenant Isolation**: Strict enforcement via X-Customer-ID header
- **Rate Limiting**: Quota-based enforcement

### Data Protection
- **Input Validation**: All OTLP fields validated before processing
- **SQL Injection**: Parameterized queries prevent injection attacks
- **Data Encryption**: TLS for data in transit, encryption at rest for sensitive data

## Cost Model

### Billing Calculation
- **Rate**: $0.50 per GB ingested (from pricing.yml)
- **Measurement**: Total bytes of OTLP message content
- **Tracking**: Real-time usage recording in usage_records_mt
- **Aggregation**: Monthly billing cycles with detailed usage breakdown

### Cost Optimization
- **Efficient Parsing**: Minimal memory allocation during processing
- **Background Processing**: No blocking operations affecting throughput
- **Bulk Operations**: Optimized database insertions reduce processing costs

---

**Last Updated**: October 2025  
**API Version**: v1  
**Maintainer**: Logforge Engineering Team