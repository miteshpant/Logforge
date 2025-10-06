# Observability APIs

## Overview

The Observability APIs provide comprehensive monitoring capabilities including distributed tracing, metrics collection, application performance monitoring (APM), and service health tracking. These APIs enable DevOps and SRE teams to monitor, debug, and optimize distributed systems in real-time.

**Base Path**: `/v1/observability`  
**Total Endpoints**: 20+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)  
**Required Roles**: `devops_engineer`, `admin` or higher

## Core Observability Features

### 1. Observability Health Check
```http
GET /v1/observability/health
```

**Description**: Get observability system health and status

**Authentication**: Required

**Response** (200):
```json
{
  "status": "healthy",
  "components": {
    "trace_ingestion": {
      "status": "healthy",
      "traces_per_second": 1250,
      "queue_depth": 45,
      "processing_latency_ms": 12
    },
    "metrics_collection": {
      "status": "healthy",
      "metrics_per_second": 8500,
      "active_series": 125000,
      "storage_usage_gb": 45.6
    },
    "service_discovery": {
      "status": "healthy",
      "services_discovered": 85,
      "last_discovery": "2024-01-20T15:30:00Z"
    },
    "apm_analysis": {
      "status": "healthy",
      "analysis_lag_seconds": 8,
      "active_transactions": 2450
    }
  },
  "performance": {
    "trace_retention_days": 7,
    "metrics_retention_days": 90,
    "p99_query_latency_ms": 450
  }
}
```

## Distributed Tracing

### 2. Ingest Traces
```http
POST /v1/observability/traces/ingest
```

**Description**: Ingest distributed tracing data (OpenTelemetry format)

**Authentication**: Required

**Request Body** (OpenTelemetry format):
```json
{
  "resourceSpans": [
    {
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "api-service"}},
          {"key": "service.version", "value": {"stringValue": "1.2.0"}},
          {"key": "deployment.environment", "value": {"stringValue": "production"}}
        ]
      },
      "scopeSpans": [
        {
          "scope": {
            "name": "api-service-tracer",
            "version": "1.0.0"
          },
          "spans": [
            {
              "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
              "spanId": "00f067aa0ba902b7",
              "parentSpanId": "0020000000000001",
              "name": "GET /api/users",
              "kind": "SPAN_KIND_SERVER",
              "startTimeUnixNano": "1640995800000000000",
              "endTimeUnixNano": "1640995800250000000",
              "status": {"code": "STATUS_CODE_OK"},
              "attributes": [
                {"key": "http.method", "value": {"stringValue": "GET"}},
                {"key": "http.route", "value": {"stringValue": "/api/users"}},
                {"key": "http.status_code", "value": {"intValue": "200"}}
              ]
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
  "message": "Traces ingested successfully",
  "traces_processed": 1,
  "spans_processed": 1,
  "ingestion_time": "2024-01-20T15:30:01.234Z",
  "processing_time_ms": 15
}
```

### 3. Search Traces
```http
POST /v1/observability/traces/search
```

**Description**: Search and filter distributed traces

**Authentication**: Required

**Request Body**:
```json
{
  "time_range": {
    "start": "2024-01-20T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "filters": {
    "service_name": "api-service",
    "operation_name": "GET /api/users",
    "min_duration_ms": 100,
    "max_duration_ms": 5000,
    "status": "error",
    "tags": {
      "http.status_code": "500",
      "error": "true"
    }
  },
  "limit": 50,
  "sort": {
    "field": "duration",
    "direction": "desc"
  }
}
```

**Response** (200):
```json
{
  "traces": [
    {
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "root_span": {
        "span_id": "00f067aa0ba902b7",
        "service_name": "api-service",
        "operation_name": "GET /api/users",
        "start_time": "2024-01-20T15:30:00Z",
        "duration_ms": 1250,
        "status": "error",
        "error_message": "Database connection timeout"
      },
      "span_count": 8,
      "service_count": 3,
      "services": ["api-service", "database-service", "auth-service"],
      "has_errors": true,
      "criticality": "high"
    }
  ],
  "total": 145,
  "page_info": {
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

### 4. Get Trace Details
```http
GET /v1/observability/traces/{trace_id}
```

**Description**: Get detailed trace information including all spans

**Authentication**: Required

**Path Parameters**:
- `trace_id` (string): Trace identifier

**Response** (200):
```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "duration_ms": 1250,
  "start_time": "2024-01-20T15:30:00Z",
  "end_time": "2024-01-20T15:30:01.250Z",
  "status": "error",
  "services": [
    {
      "name": "api-service",
      "span_count": 3,
      "duration_ms": 1250,
      "error_count": 1
    },
    {
      "name": "database-service", 
      "span_count": 3,
      "duration_ms": 1100,
      "error_count": 1
    },
    {
      "name": "auth-service",
      "span_count": 2,
      "duration_ms": 45,
      "error_count": 0
    }
  ],
  "spans": [
    {
      "span_id": "00f067aa0ba902b7",
      "parent_span_id": null,
      "service_name": "api-service",
      "operation_name": "GET /api/users",
      "start_time": "2024-01-20T15:30:00Z",
      "duration_ms": 1250,
      "status": "error",
      "tags": {
        "http.method": "GET",
        "http.route": "/api/users",
        "http.status_code": 500,
        "error": true,
        "error.message": "Database connection timeout"
      },
      "logs": [
        {
          "timestamp": "2024-01-20T15:30:01Z",
          "level": "error",
          "message": "Failed to execute query: connection timeout"
        }
      ]
    }
  ],
  "trace_tree": {
    "root": "00f067aa0ba902b7",
    "children": ["0020000000000002", "0020000000000003"]
  }
}
```

### 5. Real-time Trace Stream
```http
GET /v1/observability/traces/stream
```

**Description**: Real-time stream of incoming traces (WebSocket or Server-Sent Events)

**Authentication**: Required

**Query Parameters**:
- `service` (string, optional): Filter by service name
- `min_duration_ms` (integer, optional): Minimum duration filter
- `format` (string, default: "sse"): Stream format (sse, websocket)

**Response** (Server-Sent Events):
```
data: {"trace_id":"4bf92f3577b34da6a3ce929d0e0e4737","service":"api-service","duration_ms":450,"status":"ok","timestamp":"2024-01-20T15:31:00Z"}

data: {"trace_id":"4bf92f3577b34da6a3ce929d0e0e4738","service":"payment-service","duration_ms":2100,"status":"error","timestamp":"2024-01-20T15:31:05Z"}
```

## Metrics Collection & Querying

### 6. Ingest Metrics
```http
POST /v1/observability/metrics/ingest
```

**Description**: Ingest application and infrastructure metrics

**Authentication**: Required

**Request Body**:
```json
{
  "metrics": [
    {
      "name": "http_requests_total",
      "type": "counter",
      "value": 1250,
      "timestamp": "2024-01-20T15:30:00Z",
      "labels": {
        "service": "api-service",
        "method": "GET",
        "endpoint": "/api/users",
        "status_code": "200"
      }
    },
    {
      "name": "response_time_seconds",
      "type": "histogram",
      "value": 0.450,
      "timestamp": "2024-01-20T15:30:00Z",
      "labels": {
        "service": "api-service",
        "endpoint": "/api/users"
      },
      "buckets": {
        "0.1": 100,
        "0.5": 450,
        "1.0": 500,
        "5.0": 500
      }
    }
  ]
}
```

**Response** (200):
```json
{
  "message": "Metrics ingested successfully",
  "metrics_processed": 2,
  "data_points": 7,
  "ingestion_time": "2024-01-20T15:30:01.456Z"
}
```

### 7. Query Metrics
```http
POST /v1/observability/metrics/query
```

**Description**: Query metrics with PromQL-like syntax

**Authentication**: Required

**Request Body**:
```json
{
  "query": "rate(http_requests_total[5m])",
  "time_range": {
    "start": "2024-01-20T14:00:00Z",
    "end": "2024-01-20T15:00:00Z"
  },
  "step": "1m",
  "filters": {
    "service": "api-service"
  }
}
```

**Response** (200):
```json
{
  "query": "rate(http_requests_total[5m])",
  "result_type": "matrix",
  "data": [
    {
      "metric": {
        "service": "api-service",
        "method": "GET",
        "endpoint": "/api/users"
      },
      "values": [
        ["2024-01-20T14:00:00Z", "12.5"],
        ["2024-01-20T14:01:00Z", "13.2"],
        ["2024-01-20T14:02:00Z", "11.8"]
      ]
    }
  ],
  "execution_time_ms": 25
}
```

### 8. Metrics Stream
```http
GET /v1/observability/metrics/stream
```

**Description**: Real-time metrics stream

**Authentication**: Required

**Query Parameters**:
- `metrics` (string, optional): Comma-separated metric names
- `labels` (string, optional): Label filters
- `interval` (string, default: "10s"): Stream interval

**Response** (Server-Sent Events):
```
data: {"metric":"cpu_usage_percent","value":45.6,"labels":{"service":"api-service","instance":"web-01"},"timestamp":"2024-01-20T15:31:00Z"}

data: {"metric":"memory_usage_bytes","value":2147483648,"labels":{"service":"api-service","instance":"web-01"},"timestamp":"2024-01-20T15:31:00Z"}
```

## Application Performance Monitoring (APM)

### 9. APM Overview
```http
GET /v1/observability/apm/overview
```

**Description**: Get application performance monitoring overview

**Authentication**: Required

**Query Parameters**:
- `time_range` (string, default: "1h"): Time range for analysis
- `environment` (string, optional): Filter by environment

**Response** (200):
```json
{
  "time_range": "1h",
  "summary": {
    "total_requests": 125000,
    "avg_response_time_ms": 285,
    "p95_response_time_ms": 850,
    "p99_response_time_ms": 1200,
    "error_rate": 0.025,
    "throughput_rps": 34.7
  },
  "services": [
    {
      "name": "api-service",
      "requests": 45000,
      "avg_response_time_ms": 220,
      "error_rate": 0.015,
      "apdex_score": 0.92,
      "health_status": "healthy"
    },
    {
      "name": "payment-service",
      "requests": 15000,
      "avg_response_time_ms": 450,
      "error_rate": 0.045,
      "apdex_score": 0.78,
      "health_status": "warning"
    }
  ],
  "slowest_endpoints": [
    {
      "service": "payment-service",
      "endpoint": "POST /payments/process",
      "avg_response_time_ms": 1250,
      "p95_response_time_ms": 2100,
      "request_count": 1250
    }
  ],
  "error_hotspots": [
    {
      "service": "api-service",
      "endpoint": "GET /api/users/{id}",
      "error_rate": 0.08,
      "error_count": 120,
      "top_error": "User not found"
    }
  ]
}
```

### 10. Service APM Details
```http
GET /v1/observability/apm/{service_name}
```

**Description**: Get detailed APM information for specific service

**Authentication**: Required

**Path Parameters**:
- `service_name` (string): Service name

**Query Parameters**:
- `time_range` (string, default: "1h"): Time range for analysis

**Response** (200):
```json
{
  "service_name": "api-service",
  "time_range": "1h",
  "overview": {
    "requests": 45000,
    "avg_response_time_ms": 220,
    "p50_response_time_ms": 180,
    "p95_response_time_ms": 450,
    "p99_response_time_ms": 680,
    "error_rate": 0.015,
    "apdex_score": 0.92,
    "throughput_rps": 12.5
  },
  "endpoints": [
    {
      "path": "GET /api/users",
      "requests": 15000,
      "avg_response_time_ms": 180,
      "error_rate": 0.008,
      "throughput_rps": 4.17
    },
    {
      "path": "POST /api/users",
      "requests": 5000,
      "avg_response_time_ms": 320,
      "error_rate": 0.025,
      "throughput_rps": 1.39
    }
  ],
  "dependencies": [
    {
      "service": "database-service",
      "call_count": 48000,
      "avg_response_time_ms": 45,
      "error_rate": 0.002,
      "dependency_type": "database"
    },
    {
      "service": "auth-service",
      "call_count": 25000,
      "avg_response_time_ms": 25,
      "error_rate": 0.001,
      "dependency_type": "service"
    }
  ],
  "time_series": {
    "response_time": [
      {"timestamp": "2024-01-20T14:00:00Z", "value": 210},
      {"timestamp": "2024-01-20T14:05:00Z", "value": 225},
      {"timestamp": "2024-01-20T14:10:00Z", "value": 195}
    ],
    "throughput": [
      {"timestamp": "2024-01-20T14:00:00Z", "value": 12.1},
      {"timestamp": "2024-01-20T14:05:00Z", "value": 13.8},
      {"timestamp": "2024-01-20T14:10:00Z", "value": 11.9}
    ],
    "error_rate": [
      {"timestamp": "2024-01-20T14:00:00Z", "value": 0.012},
      {"timestamp": "2024-01-20T14:05:00Z", "value": 0.018},
      {"timestamp": "2024-01-20T14:10:00Z", "value": 0.015}
    ]
  }
}
```

## Service Discovery & Mapping

### 11. Service Map
```http
GET /v1/observability/service-map
```

**Description**: Get service dependency map and topology

**Authentication**: Required

**Query Parameters**:
- `time_range` (string, default: "1h"): Time range for analysis
- `environment` (string, optional): Filter by environment
- `include_external` (boolean, default: true): Include external dependencies

**Response** (200):
```json
{
  "time_range": "1h",
  "services": [
    {
      "name": "api-gateway",
      "type": "service",
      "health": "healthy",
      "request_rate": 50.2,
      "error_rate": 0.01,
      "avg_latency_ms": 25,
      "position": {"x": 100, "y": 100}
    },
    {
      "name": "api-service",
      "type": "service", 
      "health": "healthy",
      "request_rate": 45.8,
      "error_rate": 0.015,
      "avg_latency_ms": 220,
      "position": {"x": 300, "y": 100}
    },
    {
      "name": "database",
      "type": "database",
      "health": "healthy",
      "request_rate": 48.0,
      "error_rate": 0.002,
      "avg_latency_ms": 45,
      "position": {"x": 500, "y": 200}
    }
  ],
  "connections": [
    {
      "source": "api-gateway",
      "target": "api-service",
      "request_rate": 45.8,
      "error_rate": 0.015,
      "avg_latency_ms": 220,
      "protocol": "http"
    },
    {
      "source": "api-service",
      "target": "database",
      "request_rate": 48.0,
      "error_rate": 0.002,
      "avg_latency_ms": 45,
      "protocol": "tcp"
    }
  ],
  "external_dependencies": [
    {
      "name": "external-payment-api",
      "type": "external_api",
      "health": "unknown",
      "request_rate": 2.1,
      "avg_latency_ms": 850
    }
  ]
}
```

### 12. Service Health Check
```http
GET /v1/observability/service/{service_name}/health
```

**Description**: Get detailed health information for specific service

**Authentication**: Required

**Path Parameters**:
- `service_name` (string): Service name

**Response** (200):
```json
{
  "service_name": "api-service",
  "health_status": "healthy",
  "last_updated": "2024-01-20T15:30:00Z",
  "metrics": {
    "uptime_seconds": 86400,
    "cpu_usage_percent": 45.2,
    "memory_usage_percent": 68.5,
    "disk_usage_percent": 23.1,
    "active_connections": 125,
    "request_rate_1m": 12.5,
    "error_rate_1m": 0.015
  },
  "health_checks": [
    {
      "name": "database_connectivity",
      "status": "passing",
      "last_check": "2024-01-20T15:29:45Z",
      "response_time_ms": 8
    },
    {
      "name": "external_api_connectivity",
      "status": "passing",
      "last_check": "2024-01-20T15:29:50Z",
      "response_time_ms": 125
    }
  ],
  "alerts": [
    {
      "level": "warning",
      "message": "Memory usage above 65%",
      "timestamp": "2024-01-20T15:25:00Z"
    }
  ],
  "dependencies": {
    "healthy": 3,
    "unhealthy": 0,
    "unknown": 1
  }
}
```

## Analytics & Trends

### 13. Observability Analytics
```http
GET /v1/observability/analytics
```

**Description**: Get observability analytics and insights

**Authentication**: Required

**Query Parameters**:
- `time_range` (string, default: "24h"): Time range for analysis
- `service` (string, optional): Focus on specific service
- `metric_type` (string, optional): Focus on specific metrics

**Response** (200):
```json
{
  "time_range": "24h",
  "insights": [
    {
      "type": "performance_degradation",
      "severity": "medium",
      "service": "payment-service",
      "description": "Response time increased by 35% compared to previous 24h",
      "recommendation": "Check database connection pool configuration",
      "impact_score": 0.7
    },
    {
      "type": "error_spike",
      "severity": "high",
      "service": "api-service",
      "description": "Error rate increased from 1.2% to 4.8% in last 2 hours",
      "recommendation": "Investigate recent deployment changes",
      "impact_score": 0.85
    }
  ],
  "performance_trends": {
    "response_time": {
      "trend": "increasing",
      "change_percent": 12.5,
      "significance": "medium"
    },
    "throughput": {
      "trend": "stable",
      "change_percent": -2.1,
      "significance": "low"
    },
    "error_rate": {
      "trend": "increasing",
      "change_percent": 45.8,
      "significance": "high"
    }
  },
  "anomalies": [
    {
      "metric": "cpu_usage",
      "service": "worker-service",
      "timestamp": "2024-01-20T14:30:00Z",
      "expected_value": 25.5,
      "actual_value": 78.2,
      "anomaly_score": 0.92
    }
  ],
  "capacity_forecasting": {
    "services_at_capacity": ["payment-service"],
    "estimated_time_to_capacity": "7 days",
    "scaling_recommendations": [
      {
        "service": "payment-service",
        "action": "scale_out",
        "recommended_instances": 3
      }
    ]
  }
}
```

### 14. Performance Trends
```http
GET /v1/observability/trends
```

**Description**: Get performance trends and forecasting

**Authentication**: Required

**Query Parameters**:
- `period` (string, default: "7d"): Analysis period
- `metrics` (string, optional): Comma-separated metric names
- `services` (string, optional): Comma-separated service names

**Response** (200):
```json
{
  "period": "7d",
  "trends": [
    {
      "service": "api-service",
      "metrics": {
        "response_time": {
          "current_avg": 220,
          "previous_avg": 195,
          "trend": "increasing",
          "change_percent": 12.8,
          "forecast_24h": 235
        },
        "throughput": {
          "current_avg": 12.5,
          "previous_avg": 11.8,
          "trend": "increasing",
          "change_percent": 5.9,
          "forecast_24h": 13.1
        },
        "error_rate": {
          "current_avg": 0.015,
          "previous_avg": 0.012,
          "trend": "increasing",
          "change_percent": 25.0,
          "forecast_24h": 0.018
        }
      }
    }
  ],
  "system_trends": {
    "overall_health": {
      "current_score": 0.87,
      "trend": "stable",
      "change_from_previous": -0.02
    },
    "capacity_utilization": {
      "current_percent": 68.5,
      "trend": "increasing",
      "estimated_full_capacity": "14 days"
    }
  }
}
```

## Configuration & Setup

### Trace Sampling Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `always_on` | Sample all traces | Development, debugging |
| `always_off` | Sample no traces | Disable tracing |
| `probabilistic` | Random sampling (0.0-1.0) | Production with volume control |
| `rate_limiting` | Rate-based sampling | Consistent trace volume |
| `parent_based` | Follow parent span decisions | Distributed sampling consistency |

### Metric Types

| Type | Description | Example |
|------|-------------|---------|
| `counter` | Monotonic increasing value | `http_requests_total` |
| `gauge` | Current value that can go up/down | `cpu_usage_percent` |
| `histogram` | Distribution of values | `response_time_seconds` |
| `summary` | Quantiles over time window | `request_duration_quantiles` |

### Service Health States

| State | Description | Criteria |
|-------|-------------|----------|
| `healthy` | Service operating normally | Error rate < 1%, latency within SLA |
| `warning` | Service degraded but functional | Error rate 1-5%, latency elevated |
| `critical` | Service severely impaired | Error rate > 5%, latency > 2x SLA |
| `unknown` | Health status unknown | No recent health check data |

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_trace_format` | Malformed trace data |
| 400 | `invalid_metric_query` | Invalid PromQL syntax |
| 404 | `trace_not_found` | Trace ID does not exist |
| 404 | `service_not_found` | Service not discovered |
| 413 | `trace_too_large` | Trace exceeds size limits |
| 422 | `validation_error` | Request validation failed |

### Example Error Response
```json
{
  "detail": "Invalid PromQL query syntax: unexpected token",
  "type": "invalid_metric_query",
  "code": "METRICS_001",
  "context": {
    "query": "rate(http_requests_total[5m",
    "position": 28,
    "suggestion": "Missing closing bracket in range selector"
  }
}
```

## Best Practices

### Tracing
1. **Sampling Strategy**: Use probabilistic sampling in production (1-10%)
2. **Span Naming**: Use consistent, descriptive span names
3. **Attribute Tags**: Add relevant business context as span attributes
4. **Error Handling**: Always record errors and exceptions in spans
5. **Propagation**: Ensure trace context propagation across service boundaries

### Metrics
1. **Naming Convention**: Use consistent metric naming (e.g., `service_operation_unit`)
2. **Labels**: Keep label cardinality low (< 1000 unique combinations)
3. **Aggregation**: Use appropriate metric types for different use cases
4. **Retention**: Configure appropriate retention periods for different metric types
5. **Collection Frequency**: Balance between granularity and storage costs

### APM
1. **SLA Definition**: Define clear service level agreements
2. **Alerting**: Set up alerts on key performance indicators
3. **Baseline**: Establish performance baselines for comparison
4. **Correlation**: Correlate metrics, traces, and logs for complete visibility
5. **Continuous Monitoring**: Implement automated performance regression detection

---

*See [Data APIs](./Data-APIs.md) for log correlation and [Dashboard APIs](./Dashboard-APIs.md) for observability visualization.*