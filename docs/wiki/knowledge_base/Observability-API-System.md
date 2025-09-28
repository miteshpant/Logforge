# Logforge Observability API System

## Overview

The Logforge Observability API provides comprehensive distributed tracing and metrics capabilities following OpenTelemetry standards. Built on FastAPI with multi-tenant architecture, the system supports trace ingestion, metrics collection, service mapping, APM analytics, and performance monitoring for modern microservices environments.

**Base URL**: `/v1/observability`  
**Authentication**: Bearer token required via `Authorization` header  
**Multi-tenant**: X-Customer-ID header required for tenant isolation

---

## Trace Management Endpoints

### 1. Trace Span Ingestion
**Endpoint**: `POST /v1/observability/traces/ingest`

Ingests OpenTelemetry trace spans with full support for distributed tracing standards and batch processing.

**Request Body**:
```json
{
  "spans": [
    {
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "span_id": "00f067aa0ba902b7",
      "parent_span_id": "00f067aa0ba902b6",
      "operation_name": "GET /api/users",
      "service_name": "user-service",
      "start_time": "2024-01-01T12:00:00.000Z",
      "end_time": "2024-01-01T12:00:00.145Z",
      "duration_ms": 145,
      "kind": "server",
      "status": "ok",
      "status_message": "Request completed successfully",
      "attributes": {
        "http.method": "GET",
        "http.url": "/api/users",
        "http.status_code": 200,
        "http.user_agent": "curl/7.68.0"
      },
      "events": [
        {
          "name": "cache.miss",
          "timestamp": "2024-01-01T12:00:00.050Z",
          "attributes": {
            "cache.key": "users_list",
            "cache.type": "redis"
          }
        }
      ],
      "links": [
        {
          "trace_id": "4bf92f3577b34da6a3ce929d0e0e4735",
          "span_id": "00f067aa0ba902b5",
          "relationship": "follows_from"
        }
      ],
      "resource": {
        "service.name": "user-service",
        "service.version": "1.2.3",
        "deployment.environment": "production"
      }
    }
  ],
  "resource_spans": []
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/observability/traces/ingest" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "spans": [
      {
        "trace_id": "abc123-def456-ghi789",
        "span_id": "span-001",
        "parent_span_id": null,
        "operation_name": "process_order",
        "service_name": "order-service",
        "start_time": "2024-01-01T12:00:00Z",
        "end_time": "2024-01-01T12:00:02Z",
        "kind": "server",
        "status": "ok",
        "attributes": {
          "order.id": "ORD-12345",
          "order.amount": 99.99
        },
        "events": [],
        "links": [],
        "resource": {
          "service.name": "order-service"
        }
      }
    ]
  }'
```

**Response Structure**:
```json
{
  "message": "Traces ingested successfully",
  "spans_ingested": 1,
  "customer_id": "tenant-uuid-123",
  "errors": []
}
```

**Span Attributes**:
- **Trace ID**: Unique identifier linking related spans across services
- **Span ID**: Unique identifier for this specific span
- **Parent Span ID**: Links to parent span for building trace trees
- **Operation Name**: Human-readable operation descriptor
- **Kind**: Span type (server, client, producer, consumer, internal, unspecified)
- **Status**: Execution status (ok, error, unset)
- **Attributes**: Key-value pairs for contextual information
- **Events**: Timeline events within the span execution
- **Links**: References to spans in other traces

### 2. Trace Search
**Endpoint**: `POST /v1/observability/traces/search`

Searches traces with advanced filtering capabilities for debugging and analysis.

**Request Body**:
```json
{
  "service_name": "user-service",
  "operation_name": "GET /api/users",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T23:59:59Z",
  "min_duration_ms": 100,
  "max_duration_ms": 5000,
  "status": "error",
  "limit": 50,
  "offset": 0
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/observability/traces/search" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "start_time": "2024-01-01T12:00:00Z",
    "end_time": "2024-01-01T13:00:00Z",
    "status": "error",
    "limit": 25
  }'
```

**Response Structure**:
```json
{
  "traces": [
    {
      "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
      "spans": [
        {
          "span_id": "00f067aa0ba902b7",
          "operation_name": "process_payment",
          "service_name": "payment-service",
          "start_time": "2024-01-01T12:15:00Z",
          "duration_ms": 2340,
          "status": "error",
          "attributes": {
            "payment.id": "PAY-67890",
            "error.message": "Payment gateway timeout"
          }
        }
      ]
    }
  ],
  "total": 1,
  "limit": 25,
  "offset": 0,
  "customer_id": "tenant-uuid-123"
}
```

### 3. Trace Details
**Endpoint**: `GET /v1/observability/traces/{trace_id}`

Retrieves complete trace information with all spans and relationships.

**Path Parameters**:
- `trace_id`: Trace identifier

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/traces/4bf92f3577b34da6a3ce929d0e0e4736" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "trace": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "total_spans": 15,
    "root_span": {
      "span_id": "00f067aa0ba902b7",
      "operation_name": "handle_request",
      "service_name": "api-gateway",
      "duration_ms": 1205
    },
    "spans": [
      {
        "span_id": "00f067aa0ba902b7",
        "parent_span_id": null,
        "operation_name": "handle_request",
        "service_name": "api-gateway",
        "start_time": "2024-01-01T12:00:00Z",
        "end_time": "2024-01-01T12:00:01.205Z",
        "duration_ms": 1205,
        "status": "ok",
        "attributes": {
          "http.method": "POST",
          "http.path": "/api/orders"
        }
      }
    ],
    "services": ["api-gateway", "order-service", "payment-service", "inventory-service"],
    "duration_ms": 1205,
    "status": "ok"
  },
  "customer_id": "tenant-uuid-123"
}
```

---

## Metrics Management Endpoints

### 4. Metrics Ingestion
**Endpoint**: `POST /v1/observability/metrics/ingest`

Ingests time-series metrics with support for multiple metric types and labeling.

**Request Body**:
```json
{
  "metrics": [
    {
      "metric_name": "http_requests_total",
      "metric_type": "counter",
      "value": 1542,
      "timestamp": "2024-01-01T12:00:00Z",
      "labels": {
        "method": "GET",
        "status": "200",
        "endpoint": "/api/users",
        "service": "user-service"
      },
      "service_name": "user-service",
      "resource": {
        "service.name": "user-service",
        "service.version": "1.2.3"
      }
    },
    {
      "metric_name": "response_time_seconds",
      "metric_type": "histogram",
      "value": 0.145,
      "timestamp": "2024-01-01T12:00:00Z",
      "labels": {
        "method": "GET",
        "endpoint": "/api/users"
      },
      "service_name": "user-service",
      "resource": {
        "service.name": "user-service"
      }
    },
    {
      "metric_name": "memory_usage_bytes",
      "metric_type": "gauge",
      "value": 524288000,
      "timestamp": "2024-01-01T12:00:00Z",
      "labels": {
        "instance": "user-service-1"
      },
      "service_name": "user-service",
      "resource": {
        "service.name": "user-service"
      }
    }
  ]
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/observability/metrics/ingest" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [
      {
        "metric_name": "cpu_usage_percent",
        "metric_type": "gauge",
        "value": 75.5,
        "timestamp": "2024-01-01T12:00:00Z",
        "labels": {
          "service": "api-service",
          "instance": "api-01"
        },
        "service_name": "api-service",
        "resource": {
          "service.name": "api-service"
        }
      }
    ]
  }'
```

**Response Structure**:
```json
{
  "message": "Metrics ingested successfully",
  "metrics_ingested": 1,
  "customer_id": "tenant-uuid-123",
  "errors": []
}
```

**Metric Types**:
- **Counter**: Monotonically increasing values (e.g., request counts)
- **Gauge**: Point-in-time values that can go up or down (e.g., memory usage)
- **Histogram**: Distribution of values with buckets (e.g., response times)
- **Summary**: Similar to histogram but with quantiles (e.g., latency percentiles)

### 5. Metrics Query
**Endpoint**: `POST /v1/observability/metrics/query`

Queries time-series metrics with aggregation and time-range filtering.

**Request Body**:
```json
{
  "metric_name": "http_requests_total",
  "service_name": "user-service",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-01T23:59:59Z",
  "labels": {
    "method": "GET",
    "status": "200"
  },
  "aggregation": "sum",
  "granularity": "5m"
}
```

**Request Example**:
```bash
curl -X POST "https://api.logforge.com/v1/observability/metrics/query" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "metric_name": "response_time_seconds",
    "service_name": "api-service",
    "start_time": "2024-01-01T12:00:00Z",
    "end_time": "2024-01-01T13:00:00Z",
    "aggregation": "avg",
    "granularity": "1m"
  }'
```

**Response Structure**:
```json
{
  "metrics": {
    "response_time_seconds": [
      {
        "timestamp": "2024-01-01T12:00:00Z",
        "value": 0.145
      },
      {
        "timestamp": "2024-01-01T12:01:00Z",
        "value": 0.132
      },
      {
        "timestamp": "2024-01-01T12:02:00Z",
        "value": 0.156
      }
    ]
  },
  "aggregation": "avg",
  "granularity": "1m",
  "customer_id": "tenant-uuid-123"
}
```

**Query Parameters**:
- **Aggregation Functions**: sum, avg, min, max, count, rate
- **Granularity Options**: 30s, 1m, 5m, 15m, 1h, 6h, 1d
- **Label Filtering**: Exact match on label key-value pairs

---

## Service Topology & APM Endpoints

### 6. Service Map
**Endpoint**: `GET /v1/observability/service-map`

Retrieves service topology and dependency mapping for microservices architecture visualization.

**Query Parameters**:
- `time_range_hours` (optional): Time window for analysis (default: 24)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/service-map?time_range_hours=12" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "services": [
    {
      "name": "api-gateway",
      "type": "gateway",
      "health_status": "healthy",
      "request_rate": 1250.5,
      "error_rate": 0.02,
      "avg_response_time": 145.3,
      "dependencies": [
        {
          "service": "user-service",
          "calls_per_minute": 320,
          "avg_latency_ms": 85,
          "error_rate": 0.01
        },
        {
          "service": "order-service", 
          "calls_per_minute": 180,
          "avg_latency_ms": 125,
          "error_rate": 0.03
        }
      ]
    },
    {
      "name": "user-service",
      "type": "service",
      "health_status": "healthy",
      "request_rate": 320.0,
      "error_rate": 0.01,
      "avg_response_time": 85.2,
      "dependencies": [
        {
          "service": "database",
          "calls_per_minute": 280,
          "avg_latency_ms": 15,
          "error_rate": 0.001
        }
      ]
    }
  ],
  "time_range_hours": 12,
  "customer_id": "tenant-uuid-123"
}
```

### 7. APM Overview
**Endpoint**: `GET /v1/observability/apm/overview`

Provides comprehensive Application Performance Monitoring overview across all services.

**Query Parameters**:
- `time_range_hours` (optional): Analysis time window (default: 24)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/apm/overview?time_range_hours=6" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "overview": {
    "total_services": 12,
    "healthy_services": 11,
    "warning_services": 1,
    "critical_services": 0,
    "total_requests": 1250000,
    "total_errors": 1250,
    "overall_error_rate": 0.001,
    "avg_response_time": 156.7,
    "p95_response_time": 420.1,
    "p99_response_time": 1250.0,
    "top_services": [
      {
        "name": "api-gateway",
        "requests": 450000,
        "errors": 900,
        "error_rate": 0.002,
        "avg_response_time": 145.3
      },
      {
        "name": "user-service",
        "requests": 320000,
        "errors": 160,
        "error_rate": 0.0005,
        "avg_response_time": 85.2
      }
    ],
    "performance_trends": {
      "requests_per_minute": [1200, 1250, 1180, 1320, 1290, 1235],
      "avg_response_time": [145, 152, 139, 158, 162, 147],
      "error_rate": [0.001, 0.0015, 0.0008, 0.002, 0.0018, 0.001]
    }
  },
  "time_range_hours": 6,
  "customer_id": "tenant-uuid-123"
}
```

### 8. Service-Specific APM Metrics
**Endpoint**: `GET /v1/observability/apm/{service_name}`

Retrieves detailed APM metrics for a specific service.

**Path Parameters**:
- `service_name`: Service identifier

**Query Parameters**:
- `time_range_hours` (optional): Analysis time window (default: 1)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/apm/user-service?time_range_hours=3" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "service_name": "user-service",
  "metrics": {
    "request_metrics": {
      "total_requests": 96000,
      "successful_requests": 95520,
      "failed_requests": 480,
      "error_rate": 0.005,
      "requests_per_minute": 533.3
    },
    "response_time_metrics": {
      "avg_response_time": 85.2,
      "p50_response_time": 75.0,
      "p90_response_time": 125.0,
      "p95_response_time": 185.0,
      "p99_response_time": 450.0,
      "max_response_time": 1200.0
    },
    "throughput_metrics": {
      "requests_per_second": 8.89,
      "bytes_per_second": 2048000,
      "operations_per_minute": 533
    },
    "error_metrics": {
      "error_count": 480,
      "error_rate": 0.005,
      "top_errors": [
        {
          "error_type": "ValidationError",
          "count": 320,
          "percentage": 66.7
        },
        {
          "error_type": "TimeoutError",
          "count": 160,
          "percentage": 33.3
        }
      ]
    },
    "dependency_metrics": [
      {
        "service": "database",
        "calls": 86400,
        "avg_latency": 15.2,
        "error_rate": 0.001
      }
    ]
  },
  "time_range_hours": 3,
  "customer_id": "tenant-uuid-123"
}
```

### 9. Service Health Status
**Endpoint**: `GET /v1/observability/service/{service_name}/health`

Retrieves detailed health status and diagnostics for a specific service.

**Path Parameters**:
- `service_name`: Service identifier

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/service/payment-service/health" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "service_name": "payment-service",
  "health": {
    "status": "healthy",
    "last_seen": "2024-01-01T12:00:00Z",
    "uptime_percentage": 99.95,
    "health_checks": [
      {
        "name": "database_connection",
        "status": "healthy",
        "response_time_ms": 12,
        "last_check": "2024-01-01T12:00:00Z"
      },
      {
        "name": "external_api",
        "status": "healthy",
        "response_time_ms": 245,
        "last_check": "2024-01-01T12:00:00Z"
      }
    ],
    "recent_incidents": [
      {
        "timestamp": "2024-01-01T08:15:30Z",
        "type": "high_error_rate",
        "description": "Error rate spiked to 5% for 2 minutes",
        "resolved": true,
        "duration_minutes": 2
      }
    ],
    "performance_indicators": {
      "avg_response_time": 125.8,
      "error_rate": 0.002,
      "requests_per_minute": 180.5,
      "memory_usage_mb": 512,
      "cpu_usage_percent": 35.2
    }
  },
  "customer_id": "tenant-uuid-123"
}
```

---

## Analytics & Insights Endpoints

### 10. Trace Analytics
**Endpoint**: `GET /v1/observability/analytics`

Provides comprehensive trace analytics and insights across all services.

**Query Parameters**:
- `time_range_hours` (optional): Analysis time window (default: 24)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/analytics?time_range_hours=48" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "analytics": {
    "trace_statistics": {
      "total_traces": 45600,
      "successful_traces": 45144,
      "failed_traces": 456,
      "error_rate": 0.01,
      "avg_trace_duration": 245.7,
      "p95_trace_duration": 850.0
    },
    "service_analytics": [
      {
        "service": "api-gateway",
        "traces": 45600,
        "avg_duration": 145.3,
        "error_rate": 0.002,
        "bottleneck_score": 3.2
      },
      {
        "service": "user-service",
        "traces": 32000,
        "avg_duration": 85.2,
        "error_rate": 0.005,
        "bottleneck_score": 1.8
      }
    ],
    "operation_analytics": [
      {
        "operation": "GET /api/users",
        "count": 18500,
        "avg_duration": 85.2,
        "error_rate": 0.003
      },
      {
        "operation": "POST /api/orders",
        "count": 12000,
        "avg_duration": 245.8,
        "error_rate": 0.015
      }
    ],
    "error_analytics": {
      "top_errors": [
        {
          "error": "Payment gateway timeout",
          "count": 145,
          "services": ["payment-service"],
          "impact_score": 8.5
        }
      ]
    },
    "performance_insights": [
      {
        "type": "bottleneck",
        "service": "database",
        "description": "Database queries showing high latency",
        "recommendation": "Consider adding database connection pooling"
      },
      {
        "type": "optimization",
        "service": "user-service",
        "description": "Cache hit rate below optimal threshold",
        "recommendation": "Review caching strategy for user data"
      }
    ]
  },
  "time_range_hours": 48,
  "customer_id": "tenant-uuid-123"
}
```

### 11. Performance Trends
**Endpoint**: `GET /v1/observability/trends`

Analyzes performance trends and patterns over time for capacity planning and optimization.

**Query Parameters**:
- `days` (optional): Analysis period in days (default: 7)

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/trends?days=30" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: <tenant-id>"
```

**Response Structure**:
```json
{
  "trends": {
    "request_volume_trend": {
      "direction": "increasing",
      "change_percentage": 15.2,
      "daily_averages": [
        {"date": "2024-01-01", "requests": 1200000},
        {"date": "2024-01-02", "requests": 1250000},
        {"date": "2024-01-03", "requests": 1320000}
      ]
    },
    "response_time_trend": {
      "direction": "stable",
      "change_percentage": -2.1,
      "daily_averages": [
        {"date": "2024-01-01", "avg_ms": 152.5},
        {"date": "2024-01-02", "avg_ms": 148.2},
        {"date": "2024-01-03", "avg_ms": 149.8}
      ]
    },
    "error_rate_trend": {
      "direction": "decreasing",
      "change_percentage": -12.5,
      "daily_averages": [
        {"date": "2024-01-01", "error_rate": 0.0024},
        {"date": "2024-01-02", "error_rate": 0.0021},
        {"date": "2024-01-03", "error_rate": 0.0018}
      ]
    },
    "capacity_forecast": {
      "predicted_peak_day": "2024-01-15",
      "predicted_requests": 1850000,
      "capacity_utilization": 0.78,
      "scaling_recommendation": "Consider adding 2 more instances by 2024-01-10"
    },
    "anomaly_detection": [
      {
        "date": "2024-01-02",
        "type": "response_time_spike",
        "description": "Response time increased by 45% between 14:00-15:00",
        "severity": "medium"
      }
    ]
  },
  "days": 30,
  "customer_id": "tenant-uuid-123"
}
```

---

## Health Check Endpoint

### 12. Observability Health
**Endpoint**: `GET /v1/observability/health`

Health check endpoint for monitoring observability service status and capabilities.

**No Authentication Required**

**Request Example**:
```bash
curl -X GET "https://api.logforge.com/v1/observability/health"
```

**Response Structure**:
```json
{
  "status": "healthy",
  "message": "Observability service operational",
  "features": [
    "trace_ingestion",
    "metrics_ingestion", 
    "trace_search",
    "service_map",
    "apm_metrics",
    "apm_overview",
    "trace_analytics",
    "service_health",
    "performance_trends"
  ]
}
```

**Health Status Values**:
- `healthy`: All systems operational
- `degraded`: Some features experiencing issues
- `error`: Critical system failure

---

## Data Models

### Span Data Model

```json
{
  "trace_id": "string (required) - Unique trace identifier",
  "span_id": "string (required) - Unique span identifier", 
  "parent_span_id": "string (optional) - Parent span ID for building trace trees",
  "operation_name": "string (required) - Human-readable operation name",
  "service_name": "string (required) - Service generating the span",
  "start_time": "datetime (required) - Span start timestamp",
  "end_time": "datetime (optional) - Span end timestamp",
  "duration_ms": "integer (optional) - Span duration in milliseconds",
  "kind": "enum (server|client|producer|consumer|internal|unspecified)",
  "status": "enum (ok|error|unset)",
  "status_message": "string (optional) - Status description",
  "attributes": "object (optional) - Key-value span attributes",
  "events": "array (optional) - Timeline events during span execution",
  "links": "array (optional) - References to related spans",
  "resource": "object (optional) - Resource attributes (service info, etc.)"
}
```

### Metric Data Model

```json
{
  "metric_name": "string (required) - Metric name",
  "metric_type": "enum (counter|gauge|histogram|summary)",
  "value": "number (required) - Metric value",
  "timestamp": "datetime (required) - Measurement timestamp",
  "labels": "object (optional) - Key-value labels for filtering",
  "service_name": "string (required) - Service generating the metric",
  "resource": "object (optional) - Resource attributes"
}
```

### Query Models

**Trace Query**:
```json
{
  "service_name": "string (optional) - Filter by service",
  "operation_name": "string (optional) - Filter by operation", 
  "start_time": "datetime (optional) - Time range start",
  "end_time": "datetime (optional) - Time range end",
  "min_duration_ms": "integer (optional) - Minimum duration filter",
  "max_duration_ms": "integer (optional) - Maximum duration filter",
  "status": "enum (optional) - Status filter",
  "limit": "integer (default: 100) - Result limit",
  "offset": "integer (default: 0) - Result offset"
}
```

**Metric Query**:
```json
{
  "metric_name": "string (optional) - Metric name filter",
  "service_name": "string (optional) - Service filter",
  "start_time": "datetime (required) - Query start time",
  "end_time": "datetime (required) - Query end time",
  "labels": "object (optional) - Label filters",
  "aggregation": "string (default: avg) - Aggregation function",
  "granularity": "string (default: 1m) - Time granularity"
}
```

---

## Authentication & Authorization

### Required Headers
All observability endpoints (except health) require:
- `Authorization: Bearer <jwt-token>`
- `X-Customer-ID: <tenant-uuid>` (for multi-tenant isolation)

### Permission Requirements
- **Trace Operations**: Requires `observability.*` subscription feature
- **Metrics Operations**: Requires `observability.*` and `queries.*` features
- **Data Ingestion**: Requires `ingestion.*` subscription feature
- **Analytics Access**: Requires advanced observability permissions

### Subscription Features
The Observability API requires the following subscription features:
- `observability.*` - Core observability functionality
- `queries.*` - Query processing and analytics
- `ingestion.*` - Trace and metric ingestion
- `storage.*` - Data storage and retention
- `alerts.*` - Integration with alerting system

---

## Performance and Scalability

### Ingestion Performance
- **Trace Ingestion**: Support for 10,000+ spans per second per tenant
- **Metric Ingestion**: Support for 50,000+ data points per second per tenant
- **Batch Processing**: Optimized for bulk ingestion with error handling
- **Compression**: Automatic data compression for storage efficiency

### Query Performance
- **Trace Search**: Sub-second response times for most queries
- **Metrics Query**: Optimized time-series aggregations
- **Service Map**: Real-time topology updates with caching
- **Analytics**: Pre-computed insights for faster dashboard loading

### Scalability Features
- **Horizontal Scaling**: Auto-scaling based on ingestion volume
- **Data Partitioning**: Time-based and tenant-based partitioning
- **Retention Policies**: Configurable data retention for cost optimization
- **Sampling**: Intelligent trace sampling for high-volume environments

---

## Error Handling

### Ingestion Errors

**400 - Validation Error**:
```json
{
  "detail": "Invalid span data: trace_id is required"
}
```

**422 - Processing Error**:
```json
{
  "detail": [
    {
      "loc": ["spans", 0, "start_time"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Query Errors

**404 - Not Found**:
```json
{
  "detail": "Trace not found"
}
```

**500 - Server Error**:
```json
{
  "detail": "Failed to search traces: Database connection timeout"
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
  "required_feature": "observability.*",
  "current_subscription": [],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade"
}
```

---

## Integration Examples

### OpenTelemetry SDK Integration
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure OpenTelemetry to export to Logforge
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint="https://api.logforge.com/v1/observability/traces/ingest",
    headers={
        "Authorization": "Bearer YOUR_TOKEN",
        "X-Customer-ID": "your-tenant-id"
    }
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Create spans
with tracer.start_as_current_span("process_order") as span:
    span.set_attribute("order.id", "ORD-12345")
    span.set_attribute("order.amount", 99.99)
    
    # Your business logic here
    process_payment()
    update_inventory()
```

### Custom Metrics Publishing
```javascript
// Custom metrics publishing to Logforge
class LogforgeMetrics {
  constructor(token, tenantId) {
    this.token = token;
    this.tenantId = tenantId;
    this.baseUrl = 'https://api.logforge.com/v1/observability';
  }
  
  async publishMetrics(metrics) {
    const response = await fetch(`${this.baseUrl}/metrics/ingest`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'X-Customer-ID': this.tenantId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ metrics })
    });
    
    return response.json();
  }
  
  counter(name, value, labels = {}) {
    return {
      metric_name: name,
      metric_type: 'counter',
      value: value,
      timestamp: new Date().toISOString(),
      labels: labels,
      service_name: process.env.SERVICE_NAME || 'unknown',
      resource: {
        'service.name': process.env.SERVICE_NAME,
        'service.version': process.env.SERVICE_VERSION
      }
    };
  }
  
  gauge(name, value, labels = {}) {
    return {
      metric_name: name,
      metric_type: 'gauge',
      value: value,
      timestamp: new Date().toISOString(),
      labels: labels,
      service_name: process.env.SERVICE_NAME || 'unknown',
      resource: {
        'service.name': process.env.SERVICE_NAME
      }
    };
  }
}

// Usage
const metrics = new LogforgeMetrics(token, tenantId);

await metrics.publishMetrics([
  metrics.counter('http_requests_total', 1, { method: 'GET', status: '200' }),
  metrics.gauge('memory_usage_bytes', process.memoryUsage().rss)
]);
```

### Distributed Tracing Example
```bash
# Example: Distributed tracing across microservices

# 1. API Gateway creates root span
curl -X POST "https://api.logforge.com/v1/observability/traces/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT" \
  -d '{
    "spans": [{
      "trace_id": "abc123-def456-ghi789",
      "span_id": "root-span-001",
      "operation_name": "process_order_request",
      "service_name": "api-gateway",
      "start_time": "2024-01-01T12:00:00Z",
      "end_time": "2024-01-01T12:00:02.5Z",
      "kind": "server",
      "status": "ok",
      "attributes": {
        "http.method": "POST",
        "http.path": "/orders",
        "user.id": "user-123"
      }
    }]
  }'

# 2. Order service creates child span
curl -X POST "https://api.logforge.com/v1/observability/traces/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT" \
  -d '{
    "spans": [{
      "trace_id": "abc123-def456-ghi789",
      "span_id": "order-span-001",
      "parent_span_id": "root-span-001",
      "operation_name": "create_order",
      "service_name": "order-service",
      "start_time": "2024-01-01T12:00:00.1Z",
      "end_time": "2024-01-01T12:00:01.5Z",
      "kind": "internal",
      "status": "ok",
      "attributes": {
        "order.id": "ORD-789",
        "order.amount": 99.99
      }
    }]
  }'

# 3. Query the complete trace
curl -X GET "https://api.logforge.com/v1/observability/traces/abc123-def456-ghi789" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT"
```

### Service Health Monitoring
```bash
# Monitor service health across your architecture
for service in api-gateway user-service order-service payment-service; do
  echo "Checking health for $service..."
  curl -X GET "https://api.logforge.com/v1/observability/service/$service/health" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Customer-ID: $TENANT" \
    | jq '.health.status'
done

# Get overall APM overview
curl -X GET "https://api.logforge.com/v1/observability/apm/overview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: $TENANT" \
  | jq '.overview | {total_services, healthy_services, overall_error_rate}'
```

---

## Best Practices

### Trace Instrumentation
1. **Comprehensive Spans**: Instrument all major operations and external calls
2. **Meaningful Names**: Use descriptive operation names that indicate business intent
3. **Rich Attributes**: Include relevant context (user IDs, request parameters, etc.)
4. **Error Handling**: Always mark failed spans with error status and messages
5. **Sampling Strategy**: Implement intelligent sampling for high-volume services

### Metrics Collection
1. **Key Metrics**: Focus on RED metrics (Rate, Errors, Duration) and USE metrics (Utilization, Saturation, Errors)
2. **Label Cardinality**: Keep label cardinality reasonable to avoid performance issues
3. **Consistent Naming**: Use consistent metric naming conventions across services
4. **Time Synchronization**: Ensure accurate timestamps across all services
5. **Batch Processing**: Use batch ingestion for better performance

### Performance Optimization
1. **Query Optimization**: Use appropriate time ranges and filters for queries
2. **Data Retention**: Configure retention policies based on analysis needs
3. **Aggregation**: Pre-aggregate metrics where possible for faster dashboards
4. **Caching**: Leverage caching for frequently accessed service maps and analytics
5. **Resource Monitoring**: Monitor ingestion and query performance

### Security Considerations
1. **Sensitive Data**: Never include passwords, API keys, or PII in traces
2. **Tenant Isolation**: Always include correct X-Customer-ID headers
3. **Token Management**: Rotate authentication tokens regularly
4. **Network Security**: Use HTTPS for all API communications
5. **Access Control**: Implement proper RBAC for observability data access

---

## API Reference Summary

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/v1/observability/traces/ingest` | POST | Ingest trace spans | ✓ |
| `/v1/observability/metrics/ingest` | POST | Ingest metrics data | ✓ |
| `/v1/observability/traces/search` | POST | Search traces | ✓ |
| `/v1/observability/traces/{id}` | GET | Get trace details | ✓ |
| `/v1/observability/service-map` | GET | Service topology | ✓ |
| `/v1/observability/apm/overview` | GET | APM overview | ✓ |
| `/v1/observability/apm/{service}` | GET | Service APM metrics | ✓ |
| `/v1/observability/analytics` | GET | Trace analytics | ✓ |
| `/v1/observability/metrics/query` | POST | Query metrics | ✓ |
| `/v1/observability/service/{service}/health` | GET | Service health | ✓ |
| `/v1/observability/trends` | GET | Performance trends | ✓ |
| `/v1/observability/health` | GET | Health check | ✗ |

**Total Endpoints**: 12  
**OpenTelemetry Compatible**: Full OTLP support for traces and metrics  
**Multi-tenant**: Complete tenant isolation enforced  
**Real-time Processing**: Sub-second ingestion and query capabilities