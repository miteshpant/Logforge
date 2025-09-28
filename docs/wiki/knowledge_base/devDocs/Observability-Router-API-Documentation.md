# Observability Router API Documentation

## Overview

The Observability Router provides comprehensive Application Performance Monitoring (APM) capabilities with OpenTelemetry trace and metrics ingestion. This router enables distributed tracing, service topology mapping, performance analytics, and real-time observability for microservices architectures.

## Architecture

```
Request → Observability Router → Observability Service → Observability DAO → ClickHouse
```

**Core Components:**
- **Router**: `/apps/api/routers/observability_api.py` - FastAPI endpoints with OpenTelemetry models
- **Service**: `/apps/api/services/observability_service.py` - Business logic for trace/metrics processing
- **DAO**: `/apps/api/dao/observability_dao.py` - Database operations for observability data
- **Engine**: `/apps/api/observability_engine.py` - Core observability data structures and enums
- **Database**: Multi-tenant ClickHouse tables (`traces_mt`, `metrics_mt`, `service_topology_mt`)

## API Endpoints

### Trace Ingestion

#### 1. Ingest Trace Spans
**Endpoint**: `POST /v1/observability/traces/ingest`

Ingest OpenTelemetry trace spans for distributed tracing.

**Headers:**
- `X-Customer-ID`: Customer identifier
- `Content-Type`: application/json

**Request Body:**
```json
{
  "spans": [
    {
      "trace_id": "1234567890abcdef1234567890abcdef",
      "span_id": "1234567890abcdef",
      "parent_span_id": "0987654321fedcba",
      "operation_name": "GET /api/users",
      "service_name": "user-service",
      "start_time": "2024-01-15T10:30:00Z",
      "end_time": "2024-01-15T10:30:01.250Z",
      "duration_ms": 1250,
      "kind": "server",
      "status": "ok",
      "status_message": "Request completed successfully",
      "attributes": {
        "http.method": "GET",
        "http.url": "https://api.example.com/users",
        "http.status_code": 200,
        "user.id": "user123"
      },
      "events": [
        {
          "name": "database_query",
          "timestamp": "2024-01-15T10:30:00.500Z",
          "attributes": {
            "db.statement": "SELECT * FROM users WHERE id = ?",
            "db.duration_ms": 45
          }
        }
      ],
      "links": [
        {
          "trace_id": "fedcba0987654321fedcba0987654321",
          "span_id": "fedcba0987654321",
          "attributes": {
            "link.type": "follows_from"
          }
        }
      ],
      "resource": {
        "service.name": "user-service",
        "service.version": "1.2.3",
        "host.name": "user-service-pod-123",
        "k8s.namespace": "production"
      }
    }
  ],
  "resource_spans": []
}
```

**Response:**
```json
{
  "message": "Traces ingested successfully",
  "spans_ingested": 1,
  "customer_id": "customer_123",
  "errors": []
}
```

**Implementation:**
```python
observability_service = ObservabilityService()

for span_req in request.spans:
    span_data = {
        'trace_id': span_req.trace_id,
        'span_id': span_req.span_id,
        'operation_name': span_req.operation_name,
        'service_name': span_req.service_name,
        'start_time': span_req.start_time.isoformat(),
        'end_time': span_req.end_time.isoformat() if span_req.end_time else None,
        'kind': span_req.kind.value,
        'status': span_req.status.value,
        'attributes': span_req.attributes
    }
    
    span_id = await observability_service.ingest_trace_span(span_data, customer_id)
```

### Metrics Ingestion

#### 2. Ingest Metrics
**Endpoint**: `POST /v1/observability/metrics/ingest`

Ingest time series metrics for performance monitoring.

**Request Body:**
```json
{
  "metrics": [
    {
      "metric_name": "http_requests_total",
      "metric_type": "counter",
      "value": 1547,
      "timestamp": "2024-01-15T10:30:00Z",
      "labels": {
        "method": "GET",
        "status": "200",
        "endpoint": "/api/users"
      },
      "service_name": "user-service",
      "resource": {
        "service.name": "user-service",
        "service.version": "1.2.3",
        "host.name": "user-service-pod-123"
      }
    },
    {
      "metric_name": "response_time_seconds",
      "metric_type": "histogram",
      "value": 0.125,
      "timestamp": "2024-01-15T10:30:00Z",
      "labels": {
        "method": "GET",
        "endpoint": "/api/users"
      },
      "service_name": "user-service",
      "resource": {
        "service.name": "user-service"
      }
    }
  ]
}
```

**Response:**
```json
{
  "message": "Metrics ingested successfully",
  "metrics_ingested": 2,
  "customer_id": "customer_123",
  "errors": []
}
```

### Trace Search & Analysis

#### 3. Search Traces
**Endpoint**: `POST /v1/observability/traces/search`

Search traces with advanced filtering capabilities.

**Request Body:**
```json
{
  "service_name": "user-service",
  "operation_name": "GET /api/users",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "min_duration_ms": 100,
  "max_duration_ms": 5000,
  "status": "error",
  "limit": 50,
  "offset": 0
}
```

**Response:**
```json
{
  "traces": [
    {
      "trace_id": "1234567890abcdef1234567890abcdef",
      "span_id": "1234567890abcdef",
      "operation_name": "GET /api/users",
      "service_name": "user-service",
      "start_time": "2024-01-15T10:30:00Z",
      "end_time": "2024-01-15T10:30:01.250Z",
      "duration_ms": 1250,
      "status": "error",
      "attributes": {
        "http.status_code": 500,
        "error.message": "Database connection timeout"
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0,
  "customer_id": "customer_123"
}
```

#### 4. Get Trace Details
**Endpoint**: `GET /v1/observability/traces/{trace_id}`

Get complete trace information with all spans.

**Path Parameters:**
- `trace_id`: Unique trace identifier

**Response:**
```json
{
  "trace_id": "1234567890abcdef1234567890abcdef",
  "trace": {
    "trace_id": "1234567890abcdef1234567890abcdef",
    "spans": [
      {
        "span_id": "1234567890abcdef",
        "operation_name": "GET /api/users",
        "service_name": "user-service",
        "start_time": "2024-01-15T10:30:00Z",
        "duration_ms": 1250,
        "status": "ok",
        "attributes": {
          "http.method": "GET",
          "http.status_code": 200
        }
      },
      {
        "span_id": "0987654321fedcba",
        "parent_span_id": "1234567890abcdef",
        "operation_name": "SELECT users",
        "service_name": "database",
        "start_time": "2024-01-15T10:30:00.100Z",
        "duration_ms": 45,
        "status": "ok"
      }
    ],
    "total_spans": 2,
    "duration_ms": 1250,
    "services": ["user-service", "database"],
    "status": "ok"
  },
  "customer_id": "customer_123"
}
```

### Service Topology & Dependencies

#### 5. Get Service Map
**Endpoint**: `GET /v1/observability/service-map`

Get service topology and dependency mapping.

**Query Parameters:**
- `time_range_hours`: Time range for analysis (default: 24)

**Response:**
```json
{
  "services": [
    {
      "service_name": "user-service",
      "service_type": "application",
      "dependencies": ["database", "auth-service"],
      "health_status": "healthy",
      "metadata": {
        "service.version": "1.2.3",
        "deployment.environment": "production"
      },
      "last_seen": "2024-01-15T10:30:00Z"
    },
    {
      "service_name": "database",
      "service_type": "datastore",
      "dependencies": [],
      "health_status": "healthy",
      "metadata": {
        "db.type": "postgresql",
        "db.version": "13.8"
      },
      "last_seen": "2024-01-15T10:29:45Z"
    }
  ],
  "time_range_hours": 24,
  "customer_id": "customer_123"
}
```

### Application Performance Monitoring (APM)

#### 6. Get APM Overview
**Endpoint**: `GET /v1/observability/apm/overview`

Get comprehensive APM overview for all services.

**Query Parameters:**
- `time_range_hours`: Time range for metrics (default: 24)

**Response:**
```json
{
  "overview": {
    "total_services": 5,
    "healthy_services": 4,
    "degraded_services": 1,
    "unhealthy_services": 0,
    "total_requests": 15420,
    "total_errors": 156,
    "error_rate": 1.01,
    "avg_response_time": 245.7,
    "services": [
      {
        "service_name": "user-service",
        "request_rate": 12.5,
        "error_rate": 1.2,
        "avg_response_time": 245.7,
        "p95_response_time": 850.3,
        "p99_response_time": 1250.8,
        "throughput": 750.0,
        "error_count": 18,
        "total_requests": 1500,
        "time_window": "24h"
      }
    ]
  },
  "time_range_hours": 24,
  "customer_id": "customer_123"
}
```

#### 7. Get Service APM Metrics
**Endpoint**: `GET /v1/observability/apm/{service_name}`

Get detailed APM metrics for a specific service.

**Path Parameters:**
- `service_name`: Service name to analyze

**Query Parameters:**
- `time_range_hours`: Time range for metrics (default: 1)

**Response:**
```json
{
  "service_name": "user-service",
  "metrics": {
    "service_name": "user-service",
    "request_rate": 12.5,
    "error_rate": 1.2,
    "avg_response_time": 245.7,
    "p95_response_time": 850.3,
    "p99_response_time": 1250.8,
    "throughput": 750.0,
    "error_count": 18,
    "total_requests": 1500,
    "time_window": "1h"
  },
  "time_range_hours": 1,
  "customer_id": "customer_123"
}
```

#### 8. Get Service Health
**Endpoint**: `GET /v1/observability/service/{service_name}/health`

Get detailed health status for a service.

**Response:**
```json
{
  "service_name": "user-service",
  "health": {
    "service_name": "user-service",
    "health_status": "healthy",
    "metrics": {
      "request_rate": 12.5,
      "error_rate": 1.2,
      "avg_response_time": 245.7,
      "p95_response_time": 850.3,
      "total_requests": 1500,
      "time_window": "1h"
    },
    "recommendations": [
      "Service appears healthy. Continue monitoring."
    ],
    "last_updated": "2024-01-15T10:30:00Z"
  },
  "customer_id": "customer_123"
}
```

### Analytics & Insights

#### 9. Get Trace Analytics
**Endpoint**: `GET /v1/observability/analytics`

Get comprehensive trace analytics and insights.

**Query Parameters:**
- `time_range_hours`: Time range for analysis (default: 24)

**Response:**
```json
{
  "analytics": {
    "total_traces": 8547,
    "unique_traces": 7892,
    "unique_services": 12,
    "avg_duration": 425.7,
    "p50_duration": 245.3,
    "p95_duration": 1250.8,
    "p99_duration": 2450.5,
    "error_rate": 2.1,
    "error_count": 179,
    "time_window_hours": 24,
    "insights": [
      {
        "type": "warning",
        "message": "Average response time is 426ms, consider optimization"
      }
    ]
  },
  "time_range_hours": 24,
  "customer_id": "customer_123"
}
```

#### 10. Get Performance Trends
**Endpoint**: `GET /v1/observability/trends`

Get performance trends over time.

**Query Parameters:**
- `days`: Number of days for trend analysis (default: 7)

**Response:**
```json
{
  "trends": {
    "time_period": "7 days",
    "daily_metrics": [
      {
        "date": "2024-01-15",
        "total_traces": 8547,
        "avg_duration": 425.7,
        "error_rate": 2.1,
        "unique_services": 12
      },
      {
        "date": "2024-01-14",
        "total_traces": 7892,
        "avg_duration": 467.3,
        "error_rate": 2.8,
        "unique_services": 11
      }
    ],
    "trends": {
      "traces_trend": {
        "direction": "increasing",
        "percentage": 8.3
      },
      "performance_trend": {
        "direction": "increasing",
        "percentage": 8.9
      },
      "error_trend": {
        "direction": "decreasing",
        "percentage": 25.0
      },
      "services_trend": {
        "direction": "increasing",
        "percentage": 9.1
      }
    }
  },
  "days": 7,
  "customer_id": "customer_123"
}
```

### Metrics Query & Analysis

#### 11. Query Metrics
**Endpoint**: `POST /v1/observability/metrics/query`

Query time series metrics with aggregation.

**Request Body:**
```json
{
  "metric_name": "http_requests_total",
  "service_name": "user-service",
  "start_time": "2024-01-15T10:00:00Z",
  "end_time": "2024-01-15T11:00:00Z",
  "labels": {
    "method": "GET",
    "status": "200"
  },
  "aggregation": "avg",
  "granularity": "1m"
}
```

**Response:**
```json
{
  "metrics": {
    "http_requests_total": [
      {
        "timestamp": "2024-01-15T10:00:00Z",
        "value": 245.7
      },
      {
        "timestamp": "2024-01-15T10:01:00Z",
        "value": 267.3
      }
    ]
  },
  "aggregation": "avg",
  "granularity": "1m",
  "customer_id": "customer_123"
}
```

### Health Check

#### 12. Observability Health Check
**Endpoint**: `GET /v1/observability/health`

Health check for observability service.

**Response:**
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

## Data Models

### Span Kinds
- `unspecified`: Default span kind
- `internal`: Internal operation span
- `server`: Server-side request span
- `client`: Client-side request span
- `producer`: Producer span (e.g., message queue)
- `consumer`: Consumer span (e.g., message queue)

### Span Status
- `unset`: Status not set
- `ok`: Successful operation
- `error`: Operation failed

### Metric Types
- `counter`: Monotonically increasing counter
- `gauge`: Value that can go up and down
- `histogram`: Distribution of values
- `summary`: Summary with quantiles

## Authentication & Headers

All observability endpoints require authentication:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id>
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `202`: Accepted (for ingestion endpoints)
- `400`: Bad request (validation error)
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Resource not found
- `422`: Unprocessable entity
- `500`: Internal server error

**Error Response Format:**
```json
{
  "error": {
    "code": "TRACE_NOT_FOUND",
    "message": "Trace not found",
    "details": {
      "trace_id": "1234567890abcdef1234567890abcdef"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Code Integration

### Service Layer Integration

```python
from services.observability_service import ObservabilityService

# Initialize service
observability_service = ObservabilityService()

# Ingest trace span
span_data = {
    'trace_id': '1234567890abcdef1234567890abcdef',
    'span_id': '1234567890abcdef',
    'operation_name': 'GET /api/users',
    'service_name': 'user-service',
    'start_time': datetime.utcnow().isoformat(),
    'end_time': (datetime.utcnow() + timedelta(milliseconds=250)).isoformat(),
    'kind': 'server',
    'status': 'ok',
    'attributes': {'http.method': 'GET', 'http.status_code': 200}
}
span_id = await observability_service.ingest_trace_span(span_data, customer_id)

# Ingest metric
metric_data = {
    'name': 'http_requests_total',
    'type': 'counter',
    'value': 1,
    'timestamp': datetime.utcnow().isoformat(),
    'attributes': {'method': 'GET', 'status': '200'}
}
metric_id = await observability_service.ingest_metric(metric_data, customer_id)

# Get APM metrics
apm_metrics = await observability_service.get_service_apm_metrics(
    'user-service', customer_id, hours=24
)

# Search traces
filters = {
    'service_name': 'user-service',
    'start_time': datetime.utcnow() - timedelta(hours=1),
    'end_time': datetime.utcnow(),
    'min_duration_ms': 100
}
traces = await observability_service.search_traces(customer_id, filters, limit=50)
```

### Database Schema

**Key Observability Tables:**
- `traces_mt`: OpenTelemetry trace spans with attributes, events, links
- `metrics_mt`: Time series metrics with labels and resource attributes
- `service_topology_mt`: Service dependency mapping and health status
- `service_dependencies_mt`: Service-to-service dependency analytics

**Trace Schema:**
```sql
CREATE TABLE traces_mt (
    id String,
    trace_id String,
    span_id String,
    parent_span_id Nullable(String),
    operation_name String,
    service_name String,
    start_time DateTime64(9),
    end_time Nullable(DateTime64(9)),
    duration_ms UInt64,
    kind String,
    status String,
    status_message Nullable(String),
    attributes String,  -- JSON
    events String,     -- JSON
    links String,      -- JSON
    resource String,   -- JSON
    customer_id String,
    ingested_at DateTime64(9)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_time)
ORDER BY (customer_id, service_name, start_time)
```

## Performance Characteristics

- **Trace Ingestion**: > 50,000 spans/second per node
- **Metrics Ingestion**: > 100,000 metrics/second per node
- **Trace Search**: < 2s for 24h window on 10M spans
- **APM Metrics**: < 500ms for service-level aggregations
- **Service Map**: < 1s for complete topology (100+ services)
- **Analytics**: < 3s for 7-day trend analysis

## OpenTelemetry Integration

### Automatic Instrumentation
```python
# Python OpenTelemetry integration
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure exporter to Logforge
otlp_exporter = OTLPSpanExporter(
    endpoint="http://localhost:7080/v1/observability/traces/ingest",
    headers={"X-Customer-ID": "customer_123"}
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Create spans
with tracer.start_as_current_span("user_service_request") as span:
    span.set_attribute("http.method", "GET")
    span.set_attribute("http.url", "/api/users")
    # Your application code here
    span.set_attribute("http.status_code", 200)
```

### Manual Instrumentation
```python
import requests
import json
from datetime import datetime

# Manual span ingestion
span_data = {
    "spans": [{
        "trace_id": "1234567890abcdef1234567890abcdef",
        "span_id": "1234567890abcdef", 
        "operation_name": "database_query",
        "service_name": "user-service",
        "start_time": datetime.utcnow().isoformat() + "Z",
        "end_time": datetime.utcnow().isoformat() + "Z",
        "kind": "internal",
        "status": "ok",
        "attributes": {
            "db.statement": "SELECT * FROM users",
            "db.duration_ms": 45
        }
    }]
}

response = requests.post(
    "http://localhost:7080/v1/observability/traces/ingest",
    headers={
        "Content-Type": "application/json",
        "X-Customer-ID": "customer_123"
    },
    json=span_data
)
```

## APM Health Scoring

### Health Status Rules
- **Healthy**: Error rate < 5% AND average response time < 2s
- **Degraded**: Error rate 5-10% OR average response time 2-5s
- **Unhealthy**: Error rate > 10% OR average response time > 5s

### Recommendations Engine
- High error rate → "Investigate recent deployments and error patterns"
- High response time → "Check for performance bottlenecks"
- High traffic → "Ensure adequate scaling and resources"
- Healthy status → "Service appears healthy. Continue monitoring"

## Security Considerations

- **Multi-Tenant Isolation**: Complete data separation via `customer_id`
- **Attribute Sanitization**: PII detection and redaction in span attributes
- **Rate Limiting**: Per-tenant ingestion rate limits
- **Data Retention**: Configurable trace and metrics retention policies
- **Access Control**: RBAC for observability data access

## Best Practices

1. **Span Naming**: Use consistent operation naming (e.g., "HTTP GET /api/users")
2. **Attribute Standards**: Follow OpenTelemetry semantic conventions
3. **Sampling**: Implement intelligent sampling to manage data volume
4. **Error Tracking**: Always set span status for error conditions
5. **Resource Attributes**: Include service metadata for topology mapping
6. **Correlation**: Use trace context propagation across service boundaries
7. **Performance**: Batch span and metrics ingestion for efficiency

## Related Documentation

- [OpenTelemetry Specification](https://opentelemetry.io/docs/reference/specification/)
- [APM Best Practices](../../../wiki/APM-Best-Practices.md)
- [Service Topology Mapping](../../../wiki/Service-Topology-Mapping.md)
- [Distributed Tracing Guide](../../../wiki/Distributed-Tracing-Guide.md)