# Data APIs

## Overview

The Data APIs provide comprehensive log ingestion, querying, and storage management capabilities. These APIs support multiple log formats, advanced querying with ClickHouse optimization, and automated storage lifecycle management.

**Base Paths**: `/v1/ingest`, `/v1/query`, `/v1/storage`, `/v1/export`  
**Total Endpoints**: 25+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)

## Log Ingestion APIs

### 1. Single Log Ingestion
```http
POST /v1/ingest/logs
```

**Description**: Ingest single log entry with automatic parsing

**Authentication**: Required

**Request Body**:
```json
{
  "timestamp": "2024-01-20T15:30:00Z",
  "level": "info",
  "message": "User login successful",
  "service": "auth-service",
  "source": "application",
  "metadata": {
    "user_id": "user_123",
    "ip_address": "192.168.1.100",
    "session_id": "sess_456"
  }
}
```

**Response** (200):
```json
{
  "message": "Log ingested successfully",
  "log_id": "log_789",
  "ingestion_time": "2024-01-20T15:30:01.234Z",
  "tenant_id": "tenant_456",
  "storage_location": "hot"
}
```

**Usage Example**:
```bash
curl -X POST "http://localhost:7080/v1/ingest/logs" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: tenant_456" \
  -H "Content-Type: application/json" \
  -d '{"level":"info","message":"User action completed","service":"web-app"}'
```

### 2. Batch Log Ingestion
```http
POST /v1/ingest/logs/batch
```

**Description**: Ingest multiple log entries in single request (up to 1000 logs)

**Authentication**: Required

**Request Body**:
```json
{
  "logs": [
    {
      "timestamp": "2024-01-20T15:30:00Z",
      "level": "info", 
      "message": "User login",
      "service": "auth-service"
    },
    {
      "timestamp": "2024-01-20T15:30:01Z",
      "level": "warn",
      "message": "Slow query detected",
      "service": "database"
    }
  ]
}
```

**Response** (200):
```json
{
  "message": "Batch ingestion completed",
  "ingested": 2,
  "failed": 0,
  "ingestion_time": "2024-01-20T15:30:02.456Z",
  "log_ids": ["log_790", "log_791"],
  "processing_time_ms": 45
}
```

### 3. Bulk Log Ingestion
```http
POST /v1/ingest/logs/bulk
```

**Description**: High-volume bulk ingestion from various sources

**Authentication**: Required

**Request Body**:
```json
{
  "source": "file_upload",
  "format": "json",
  "compression": "gzip",
  "data": "H4sIAAAAAAAAAKtWykvMTVWyUjJSUkorys9V..."
}
```

**Response** (200):
```json
{
  "message": "Bulk ingestion initiated",
  "batch_id": "batch_123",
  "estimated_logs": 10000,
  "status": "processing",
  "estimated_completion": "2024-01-20T15:35:00Z"
}
```

### 4. OpenTelemetry (OTLP) Ingestion
```http
POST /v1/ingest/otlp
```

**Description**: Ingest OpenTelemetry Protocol (OTLP) logs

**Authentication**: Required

**Request Body** (OTLP format):
```json
{
  "resourceLogs": [
    {
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "web-service"}},
          {"key": "service.version", "value": {"stringValue": "1.2.0"}}
        ]
      },
      "scopeLogs": [
        {
          "logRecords": [
            {
              "timeUnixNano": "1640995800000000000",
              "severityText": "INFO",
              "body": {"stringValue": "Request processed successfully"}
            }
          ]
        }
      ]
    }
  ]
}
```

**Response** (200):
```json
{
  "message": "OTLP logs ingested successfully",
  "logs_processed": 1,
  "ingestion_time": "2024-01-20T15:30:03.789Z"
}
```

### 5. Syslog Ingestion
```http
POST /v1/ingest/syslog
```

**Description**: Ingest syslog format logs (RFC 3164 and RFC 5424)

**Authentication**: Required

**Request Body** (raw syslog):
```
<34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick on /dev/pts/8
```

**Response** (200):
```json
{
  "message": "Syslog ingested successfully",
  "format": "RFC3164",
  "parsed_fields": {
    "facility": "security",
    "severity": "info",
    "timestamp": "2024-10-11T22:14:15Z",
    "hostname": "mymachine",
    "program": "su"
  }
}
```

### 6. Nginx Log Ingestion
```http
POST /v1/ingest/nginx
```

**Description**: Ingest Nginx access logs with automatic parsing

**Authentication**: Required

**Request Body** (raw Nginx log):
```
192.168.1.100 - - [20/Jan/2024:15:30:00 +0000] "GET /api/v1/logs HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
```

**Response** (200):
```json
{
  "message": "Nginx log ingested successfully",
  "parsed_fields": {
    "remote_addr": "192.168.1.100",
    "method": "GET",
    "uri": "/api/v1/logs",
    "status": 200,
    "bytes_sent": 1234,
    "user_agent": "Mozilla/5.0"
  }
}
```

### 7. Common Event Format (CEF) Ingestion
```http
POST /v1/ingest/cef
```

**Description**: Ingest Common Event Format (CEF) security logs

**Authentication**: Required

**Request Body** (CEF format):
```
CEF:0|Vendor|Product|Version|Signature|Name|Severity|src=192.168.1.100 dst=10.0.0.1 spt=12345 dpt=80
```

**Response** (200):
```json
{
  "message": "CEF log ingested successfully",
  "parsed_fields": {
    "vendor": "Vendor",
    "product": "Product", 
    "version": "Version",
    "signature_id": "Signature",
    "name": "Name",
    "severity": "High",
    "source_ip": "192.168.1.100",
    "destination_ip": "10.0.0.1"
  }
}
```

### 8. Structured JSON Ingestion
```http
POST /v1/ingest/structured
```

**Description**: Ingest structured JSON logs

**Authentication**: Required

**Request Body**:
```json
{
  "@timestamp": "2024-01-20T15:30:00Z",
  "log.level": "ERROR",
  "message": "Database connection failed",
  "service.name": "api-service",
  "error": {
    "type": "ConnectionError",
    "message": "Connection timeout after 30s"
  }
}
```

**Response** (200):
```json
{
  "message": "Structured log ingested successfully",
  "log_id": "log_792",
  "normalized_fields": 8,
  "indexed_fields": ["timestamp", "level", "service.name", "error.type"]
}
```

### 9. Plain Text Ingestion
```http
POST /v1/ingest/text
```

**Description**: Ingest plain text logs with basic parsing

**Authentication**: Required

**Request Body** (plain text):
```
2024-01-20 15:30:00 [ERROR] api-service: Failed to process request - timeout
```

**Response** (200):
```json
{
  "message": "Text log ingested successfully",
  "auto_parsed": true,
  "extracted_fields": {
    "timestamp": "2024-01-20T15:30:00Z",
    "level": "ERROR",
    "service": "api-service",
    "message": "Failed to process request - timeout"
  }
}
```

### 10. Auto-Detect Format Ingestion
```http
POST /v1/ingest
```

**Description**: Auto-detect log format and ingest appropriately

**Authentication**: Required

**Request Body** (any format):
```json
{
  "data": "2024-01-20T15:30:00Z INFO [web-service] Request completed successfully"
}
```

**Response** (200):
```json
{
  "message": "Log ingested with auto-detection",
  "detected_format": "structured_text",
  "confidence": 0.95,
  "log_id": "log_793"
}
```

## Query & Search APIs

### 11. Advanced Log Query
```http
POST /v1/query/advanced
```

**Description**: Advanced log querying with filters, aggregations, and analysis

**Authentication**: Required

**Request Body**:
```json
{
  "query": {
    "time_range": {
      "start": "2024-01-20T00:00:00Z",
      "end": "2024-01-20T23:59:59Z"
    },
    "filters": [
      {
        "field": "level",
        "operator": "eq",
        "value": "error"
      },
      {
        "field": "service",
        "operator": "in", 
        "value": ["api-service", "auth-service"]
      }
    ],
    "search": "database connection",
    "limit": 100,
    "offset": 0,
    "sort": [
      {
        "field": "timestamp",
        "direction": "desc"
      }
    ]
  },
  "aggregations": [
    {
      "name": "errors_by_service",
      "type": "terms",
      "field": "service",
      "size": 10
    }
  ]
}
```

**Response** (200):
```json
{
  "hits": {
    "total": 245,
    "max_score": 1.0,
    "logs": [
      {
        "_id": "log_794",
        "_score": 1.0,
        "_source": {
          "timestamp": "2024-01-20T15:30:00Z",
          "level": "error",
          "service": "api-service",
          "message": "Database connection timeout",
          "metadata": {
            "duration_ms": 30000,
            "retry_count": 3
          }
        }
      }
    ]
  },
  "aggregations": {
    "errors_by_service": {
      "buckets": [
        {"key": "api-service", "doc_count": 150},
        {"key": "auth-service", "doc_count": 95}
      ]
    }
  },
  "took": 25,
  "timed_out": false
}
```

### 12. Simple Log Retrieval
```http
GET /v1/logs
```

**Description**: Simple log retrieval for basic queries (M0 compatibility)

**Authentication**: Required

**Query Parameters**:
- `service` (string, optional): Filter by service name
- `level` (string, optional): Filter by log level
- `limit` (integer, default: 100): Maximum logs to return
- `offset` (integer, default: 0): Number of logs to skip

**Response** (200):
```json
{
  "logs": [
    {
      "id": "log_795",
      "timestamp": "2024-01-20T15:30:00Z",
      "level": "info",
      "service": "web-service",
      "message": "Request processed"
    }
  ],
  "total": 1000,
  "limit": 100,
  "offset": 0
}
```

**Usage Example**:
```bash
curl -X GET "http://localhost:7080/v1/logs?service=api-service&level=error&limit=50" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: tenant_456"
```

### 13. Aggregate Query
```http
POST /v1/query/aggregate
```

**Description**: Aggregate log data with grouping and calculations

**Authentication**: Required

**Request Body**:
```json
{
  "time_range": {
    "start": "2024-01-20T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "group_by": ["service", "level"],
  "metrics": [
    {
      "name": "count",
      "type": "count"
    },
    {
      "name": "avg_response_time",
      "type": "avg",
      "field": "response_time"
    }
  ],
  "filters": [
    {
      "field": "status_code",
      "operator": "gte",
      "value": 400
    }
  ]
}
```

**Response** (200):
```json
{
  "buckets": [
    {
      "key": {"service": "api-service", "level": "error"},
      "doc_count": 45,
      "avg_response_time": {"value": 1250.5}
    },
    {
      "key": {"service": "web-service", "level": "warn"},
      "doc_count": 23,
      "avg_response_time": {"value": 890.2}
    }
  ],
  "total_buckets": 8
}
```

### 14. Time Series Query
```http
POST /v1/query/timeseries
```

**Description**: Time-series analysis for trends and patterns

**Authentication**: Required

**Request Body**:
```json
{
  "time_range": {
    "start": "2024-01-20T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "interval": "1h",
  "metrics": [
    {
      "name": "log_count",
      "type": "count"
    },
    {
      "name": "error_rate",
      "type": "rate",
      "filter": {"level": "error"}
    }
  ],
  "group_by": ["service"]
}
```

**Response** (200):
```json
{
  "series": [
    {
      "name": "api-service",
      "data": [
        {
          "timestamp": "2024-01-20T00:00:00Z",
          "log_count": 1250,
          "error_rate": 0.05
        },
        {
          "timestamp": "2024-01-20T01:00:00Z", 
          "log_count": 1180,
          "error_rate": 0.03
        }
      ]
    }
  ],
  "interval": "1h",
  "total_points": 24
}
```

### 15. Query Validation
```http
POST /v1/query/validate
```

**Description**: Validate query structure and parameters before execution

**Authentication**: Required

**Request Body**:
```json
{
  "query": {
    "time_range": {
      "start": "2024-01-20T00:00:00Z",
      "end": "2024-01-20T23:59:59Z"
    },
    "filters": [
      {
        "field": "nonexistent_field",
        "operator": "eq",
        "value": "test"
      }
    ]
  }
}
```

**Response** (200):
```json
{
  "valid": false,
  "errors": [
    {
      "field": "filters[0].field",
      "message": "Field 'nonexistent_field' does not exist",
      "suggestion": "Available fields: timestamp, level, service, message"
    }
  ],
  "estimated_cost": null,
  "estimated_results": null
}
```

## Saved Queries

### 16. List Saved Queries
```http
GET /v1/query/saved
```

**Description**: List saved queries for the customer

**Authentication**: Required

**Query Parameters**:
- `created_by` (string, optional): Filter by creator
- `query_type` (string, optional): Filter by query type
- `limit` (integer, default: 50): Maximum queries to return

**Response** (200):
```json
{
  "queries": [
    {
      "id": "query_123",
      "name": "Daily Error Analysis",
      "description": "Error logs analysis for last 24 hours",
      "query": {...},
      "created_by": "user_456",
      "created_at": "2024-01-15T10:30:00Z",
      "last_executed": "2024-01-20T14:25:00Z",
      "execution_count": 45
    }
  ],
  "total": 12,
  "limit": 50
}
```

### 17. Save Query
```http
POST /v1/query/saved
```

**Description**: Save query for future use

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Security Event Analysis",
  "description": "Query for analyzing security events",
  "query": {
    "filters": [
      {"field": "category", "operator": "eq", "value": "security"}
    ],
    "time_range": {"last": "24h"}
  },
  "tags": ["security", "monitoring"],
  "is_public": false
}
```

**Response** (200):
```json
{
  "id": "query_124",
  "name": "Security Event Analysis",
  "created_at": "2024-01-20T15:45:00Z",
  "message": "Query saved successfully"
}
```

### 18. Get Saved Query
```http
GET /v1/query/saved/{query_id}
```

**Description**: Retrieve specific saved query

**Authentication**: Required

**Path Parameters**:
- `query_id` (string): Query identifier

**Response** (200):
```json
{
  "id": "query_123",
  "name": "Daily Error Analysis",
  "description": "Error logs analysis for last 24 hours",
  "query": {
    "filters": [
      {"field": "level", "operator": "eq", "value": "error"}
    ],
    "time_range": {"last": "24h"}
  },
  "created_by": "user_456",
  "created_at": "2024-01-15T10:30:00Z",
  "tags": ["errors", "monitoring"]
}
```

### 19. Update Saved Query
```http
PUT /v1/query/saved/{query_id}
```

**Description**: Update existing saved query

**Authentication**: Required

**Path Parameters**:
- `query_id` (string): Query identifier

**Request Body**:
```json
{
  "name": "Updated Error Analysis",
  "description": "Enhanced error analysis with additional filters",
  "query": {
    "filters": [
      {"field": "level", "operator": "in", "value": ["error", "fatal"]}
    ]
  }
}
```

**Response** (200):
```json
{
  "id": "query_123",
  "message": "Query updated successfully",
  "updated_at": "2024-01-20T16:00:00Z"
}
```

### 20. Delete Saved Query
```http
DELETE /v1/query/saved/{query_id}
```

**Description**: Delete saved query

**Authentication**: Required

**Path Parameters**:
- `query_id` (string): Query identifier

**Response** (200):
```json
{
  "message": "Query deleted successfully",
  "query_id": "query_123"
}
```

## Data Export

### 21. Export Query Results
```http
POST /v1/export
```

**Description**: Export query results in various formats

**Authentication**: Required

**Request Body**:
```json
{
  "query": {
    "time_range": {
      "start": "2024-01-20T00:00:00Z",
      "end": "2024-01-20T23:59:59Z"
    },
    "filters": [
      {"field": "level", "operator": "eq", "value": "error"}
    ]
  },
  "format": "csv",
  "fields": ["timestamp", "level", "service", "message"],
  "compression": "gzip",
  "max_rows": 10000
}
```

**Response** (200):
```json
{
  "export_id": "export_123",
  "status": "completed",
  "download_url": "https://api.logforge.com/v1/exports/export_123/download",
  "format": "csv",
  "file_size": 2048576,
  "row_count": 8450,
  "expires_at": "2024-01-21T15:45:00Z"
}
```

**Supported Formats**:
- `json`: JSON Lines format
- `csv`: Comma-separated values
- `parquet`: Apache Parquet format
- `xlsx`: Excel spreadsheet

## Storage Management

### 22. Get Storage Health
```http
GET /v1/storage/health
```

**Description**: Get storage health for current tenant

**Authentication**: Required

**Response** (200):
```json
{
  "tenant_id": "tenant_456",
  "storage": {
    "hot": {
      "used_gb": 45.6,
      "total_gb": 100.0,
      "usage_percent": 45.6,
      "retention_days": 30
    },
    "warm": {
      "used_gb": 120.8,
      "total_gb": 500.0,
      "usage_percent": 24.2,
      "retention_days": 90
    },
    "cold": {
      "used_gb": 1024.5,
      "retention_days": 365
    }
  },
  "ingestion_rate": {
    "current_eps": 1250,
    "avg_24h_eps": 980,
    "peak_24h_eps": 2100
  },
  "health_status": "healthy"
}
```

### 23. Get Infrastructure Health (Admin)
```http
GET /v1/storage/health/infrastructure
```

**Description**: Get system-wide infrastructure health (Admin only)

**Authentication**: Required (admin role)

**Response** (200):
```json
{
  "clickhouse": {
    "status": "healthy",
    "cpu_usage": 35.2,
    "memory_usage": 67.8,
    "disk_usage": 45.6,
    "query_performance": {
      "avg_query_time_ms": 150,
      "slow_queries_count": 3
    }
  },
  "storage_backends": {
    "s3": {
      "status": "healthy",
      "latency_ms": 45,
      "error_rate": 0.001
    },
    "local": {
      "status": "healthy",
      "disk_usage": 78.5,
      "iops": 1250
    }
  },
  "message_queue": {
    "status": "healthy",
    "queue_depth": 1250,
    "throughput_eps": 2100
  }
}
```

### 24. Create Retention Policy
```http
POST /v1/storage/retention/{customer_id}
```

**Description**: Create retention policy for customer

**Authentication**: Required (admin role)

**Path Parameters**:
- `customer_id` (string): Customer identifier

**Request Body**:
```json
{
  "hot_retention_days": 30,
  "warm_retention_days": 90,
  "cold_retention_days": 365,
  "auto_archive": true,
  "compression_level": "standard",
  "compliance_tags": ["SOX", "GDPR"]
}
```

**Response** (200):
```json
{
  "policy_id": "policy_123",
  "customer_id": "customer_456",
  "hot_retention_days": 30,
  "warm_retention_days": 90,
  "cold_retention_days": 365,
  "created_at": "2024-01-20T16:15:00Z",
  "effective_date": "2024-01-21T00:00:00Z"
}
```

### 25. Trigger Storage Cleanup
```http
POST /v1/storage/cleanup
```

**Description**: Trigger manual cleanup based on TTL policies

**Authentication**: Required (admin role)

**Request Body** (optional):
```json
{
  "dry_run": true,
  "customer_id": "customer_456",
  "cleanup_type": "expired_logs"
}
```

**Response** (200):
```json
{
  "cleanup_id": "cleanup_123",
  "status": "initiated",
  "estimated_freed_gb": 12.5,
  "estimated_duration_minutes": 15,
  "affected_partitions": 5,
  "dry_run": true
}
```

### 26. Archive Old Data
```http
POST /v1/storage/archive/{customer_id}
```

**Description**: Archive old data to cold storage

**Authentication**: Required (admin role)

**Path Parameters**:
- `customer_id` (string): Customer identifier

**Response** (200):
```json
{
  "archive_job_id": "archive_123",
  "status": "initiated",
  "data_range": {
    "start": "2023-01-01T00:00:00Z",
    "end": "2023-12-31T23:59:59Z"
  },
  "estimated_size_gb": 450.7,
  "estimated_duration_hours": 6
}
```

## Performance Optimization

### Query Performance Tips

1. **Time Range Optimization**:
   - Use specific time ranges instead of open-ended queries
   - Prefer recent data (hot storage) for faster responses

2. **Field Selection**:
   - Only request needed fields in aggregations
   - Use indexed fields for filtering when possible

3. **Pagination**:
   - Use reasonable page sizes (100-1000 records)
   - Implement cursor-based pagination for large datasets

4. **Caching**:
   - Cache frequently-used saved queries
   - Use dashboard-level caching for repeated queries

### Ingestion Best Practices

1. **Batch Size**:
   - Use batch ingestion for >10 logs
   - Optimal batch size: 100-1000 logs

2. **Field Optimization**:
   - Use consistent field naming
   - Avoid deeply nested objects (>5 levels)

3. **Rate Limiting**:
   - Implement client-side rate limiting
   - Use async ingestion for high-volume scenarios

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_query` | Malformed query syntax |
| 400 | `invalid_time_range` | Invalid time range parameters |
| 413 | `payload_too_large` | Request body exceeds size limit |
| 422 | `validation_error` | Request validation failed |
| 429 | `rate_limit_exceeded` | Too many requests |
| 500 | `query_timeout` | Query execution timeout |

### Example Error Response
```json
{
  "detail": "Query timeout after 30 seconds",
  "type": "query_timeout",
  "code": "QUERY_001",
  "context": {
    "query_id": "query_temp_456",
    "execution_time_ms": 30000,
    "suggestion": "Reduce time range or add more specific filters"
  }
}
```

## Filter Operators

### Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `{"field": "level", "operator": "eq", "value": "error"}` |
| `ne` | Not equals | `{"field": "level", "operator": "ne", "value": "debug"}` |
| `gt` | Greater than | `{"field": "response_time", "operator": "gt", "value": 1000}` |
| `gte` | Greater than or equal | `{"field": "status_code", "operator": "gte", "value": 400}` |
| `lt` | Less than | `{"field": "response_time", "operator": "lt", "value": 500}` |
| `lte` | Less than or equal | `{"field": "status_code", "operator": "lte", "value": 299}` |
| `contains` | String contains | `{"field": "message", "operator": "contains", "value": "error"}` |
| `starts_with` | String starts with | `{"field": "service", "operator": "starts_with", "value": "api"}` |
| `ends_with` | String ends with | `{"field": "service", "operator": "ends_with", "value": "service"}` |
| `regex` | Regular expression | `{"field": "message", "operator": "regex", "value": "^ERROR.*"}` |
| `in` | Value in list | `{"field": "level", "operator": "in", "value": ["error", "fatal"]}` |
| `not_in` | Value not in list | `{"field": "level", "operator": "not_in", "value": ["debug", "trace"]}` |

---

*See [Dashboard APIs](./Dashboard-APIs.md) for data visualization and [Security Analytics APIs](./Security-Analytics-APIs.md) for security-focused querying.*