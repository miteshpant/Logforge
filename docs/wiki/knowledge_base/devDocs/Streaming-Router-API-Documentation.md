# Streaming Router API Documentation

## Overview

The Streaming Router provides real-time data streaming capabilities using Server-Sent Events (SSE) for metrics, traces, security events, alerts, usage data, and AI insights. This router enables real-time monitoring and live dashboard updates across the Logforge platform.

## Base Information

- **Router File**: `/apps/api/routers/streaming_api.py`
- **URL Prefix**: `/v1/stream`
- **Protocol**: Server-Sent Events (SSE)
- **Authentication**: Required via `X-Customer-ID` header
- **Content Type**: `text/event-stream`

## Data Validation Status

✅ **No Mock/Dummy Data Found** - All endpoints use real service integrations with live data streaming.

## API Endpoints

### Metrics Streaming

#### Stream Real-Time Metrics
```http
GET /v1/stream/metrics?metric_names=cpu_usage,memory_usage,disk_usage
```

**Description**: Stream real-time metrics data with 5-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Query Parameters**:
- `metric_names` (string): Comma-separated list of metric names (default: "cpu_usage,memory_usage,disk_usage")

**Response**: Server-Sent Events stream
```
event: metrics
data: [{"name": "cpu_usage", "value": 45.2, "timestamp": "2025-01-01T12:00:00Z"}, ...]

event: error  
data: {"message": "Metrics streaming error: ..."}
```

**Service Integration**: `ObservabilityService.get_metrics()`
- **Update Interval**: 5 seconds
- **Data Source**: Latest metrics from ClickHouse
- **Filter Logic**: Filters by requested metric names

---

### Traces Streaming

#### Stream Real-Time Traces
```http
GET /v1/stream/traces
```

**Description**: Stream real-time distributed tracing data with 10-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Response**: Server-Sent Events stream
```
event: traces
data: [{"trace_id": "abc123", "span_id": "def456", "operation": "http_request", ...}, ...]

event: error
data: {"message": "Traces streaming error: ..."}
```

**Service Integration**: `ObservabilityService.search_traces()`
- **Update Interval**: 10 seconds
- **Time Window**: Last 5 minutes
- **Limit**: 10 traces per update

---

### Security Events Streaming

#### Stream Real-Time Security Events
```http
GET /v1/stream/security
```

**Description**: Stream real-time security events and threat detections with 15-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Response**: Server-Sent Events stream
```
event: security_events
data: [{"event_id": "sec_001", "rule_id": "bf001", "severity": "high", "timestamp": "2025-01-01T12:00:00Z", ...}, ...]

event: error
data: {"message": "Security events streaming error: ..."}
```

**Service Integration**: `SecurityService.get_security_events()`
- **Update Interval**: 15 seconds
- **Time Window**: Last 5 minutes
- **Event Types**: Brute force, malware, privilege escalation, data exfiltration

---

### Alerts Streaming

#### Stream Real-Time Alerts
```http
GET /v1/stream/alerts
```

**Description**: Stream real-time alert notifications with 20-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Response**: Server-Sent Events stream
```
event: alerts
data: [{"alert_id": "alert_123", "rule_name": "High CPU Usage", "status": "triggered", "created_at": "2025-01-01T12:00:00Z", ...}, ...]

event: error
data: {"message": "Alerts streaming error: ..."}
```

**Service Integration**: `AlertService.get_alerts()`
- **Update Interval**: 20 seconds
- **Time Window**: Last 10 minutes
- **Alert Types**: Threshold, anomaly, pattern, frequency, absence, sequence

---

### Usage Data Streaming

#### Stream Real-Time Usage Data
```http
GET /v1/stream/usage
```

**Description**: Stream real-time usage and billing data with 30-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Response**: Server-Sent Events stream
```
event: usage
data: {"api_calls": 15420, "data_ingested_gb": 12.5, "storage_used_gb": 145.2, "cost_today": 25.80, ...}

event: error
data: {"message": "Usage streaming error: ..."}
```

**Service Integration**: `UsageService.get_usage_summary()`
- **Update Interval**: 30 seconds
- **Time Window**: Last 24 hours
- **Metrics**: API calls, data ingestion, storage usage, estimated costs

---

### AI Insights Streaming

#### Stream Real-Time AI Insights
```http
GET /v1/stream/ai-insights
```

**Description**: Stream real-time AI insights and anomaly detections with 45-second intervals

**Headers**: 
- `X-Customer-ID`: Required tenant identifier

**Response**: Server-Sent Events stream
```
event: ai_insights
data: [{"insight_id": "ai_001", "type": "anomaly", "confidence": 0.85, "description": "Unusual traffic pattern detected", ...}, ...]

event: error
data: {"message": "AI insights streaming error: ..."}
```

**Service Integration**: `AIService.get_anomaly_insights()`
- **Update Interval**: 45 seconds
- **Time Window**: Last 1 hour
- **Insight Types**: Anomalies, root cause analysis, predictive alerts

---

### Health Check

#### Streaming Service Health
```http
GET /v1/stream/health
```

**Description**: Health check for streaming service functionality

**Response**: JSON
```json
{
  "status": "healthy",
  "message": "Streaming service operational",
  "endpoints": [
    "/v1/stream/metrics",
    "/v1/stream/traces", 
    "/v1/stream/security",
    "/v1/stream/alerts",
    "/v1/stream/usage",
    "/v1/stream/ai-insights"
  ]
}
```

## SSE Message Format

All streaming endpoints use consistent Server-Sent Events formatting:

```
id: optional_event_id
event: event_type
data: {"json": "payload"}

```

**Event Types**:
- `metrics`: Real-time metrics data
- `traces`: Distributed tracing information
- `security_events`: Security alerts and detections
- `alerts`: System alerts and notifications
- `usage`: Usage and billing data
- `ai_insights`: AI-generated insights and anomalies
- `error`: Error messages and streaming failures

## Headers Configuration

All streaming responses include CORS and caching headers:

```
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Authorization, X-Customer-ID
Content-Type: text/event-stream
```

## Client Integration

### JavaScript Example
```javascript
const eventSource = new EventSource('/v1/stream/metrics?metric_names=cpu_usage,memory_usage', {
  headers: {
    'X-Customer-ID': 'tenant_123'
  }
});

eventSource.addEventListener('metrics', (event) => {
  const metrics = JSON.parse(event.data);
  updateDashboard(metrics);
});

eventSource.addEventListener('error', (event) => {
  const error = JSON.parse(event.data);
  console.error('Streaming error:', error.message);
});
```

### React Hook Example
```typescript
import { useEffect, useState } from 'react';

interface MetricData {
  name: string;
  value: number;
  timestamp: string;
}

const useMetricsStream = (tenantId: string, metricNames: string[]) => {
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(
      `/v1/stream/metrics?metric_names=${metricNames.join(',')}`,
      { 
        headers: { 'X-Customer-ID': tenantId } 
      }
    );

    eventSource.addEventListener('metrics', (event) => {
      setMetrics(JSON.parse(event.data));
      setError(null);
    });

    eventSource.addEventListener('error', (event) => {
      setError(JSON.parse(event.data).message);
    });

    return () => eventSource.close();
  }, [tenantId, metricNames]);

  return { metrics, error };
};
```

## Performance Characteristics

- **Connection Limit**: Unlimited concurrent connections per tenant
- **Latency**: Sub-second event delivery
- **Backpressure**: Automatic connection management for slow clients
- **Error Recovery**: Automatic reconnection on client-side failures
- **Memory Usage**: Streaming buffers cleared after each update

## Security Considerations

- **Authentication**: All endpoints require valid `X-Customer-ID` header
- **Tenant Isolation**: Data is automatically filtered by tenant context
- **Rate Limiting**: Implicit rate limiting via update intervals
- **CORS**: Configured for cross-origin access with proper headers

## Troubleshooting

### Common Issues

1. **Connection Drops**: Check network connectivity and implement reconnection logic
2. **Missing Data**: Verify `X-Customer-ID` header and tenant permissions
3. **High Latency**: Monitor update intervals and consider reducing frequency
4. **Memory Leaks**: Ensure EventSource connections are properly closed

### Monitoring

Monitor streaming health via:
- `/v1/stream/health` endpoint status
- Client connection counts in service logs
- Update frequency adherence in metrics
- Error rates in streaming responses

## Integration Points

### Real-Time Dashboards
- Security operations center (SOC) live updates
- Infrastructure monitoring dashboards  
- Business metrics real-time visualization
- Compliance monitoring dashboards

### Alert Systems
- Real-time alert delivery to UI components
- Push notifications for critical events
- Integration with external alerting systems
- Alert acknowledgment and status updates

### AI/ML Pipelines
- Anomaly detection result streaming
- Root cause analysis insights delivery
- Predictive alert notifications
- ML model confidence updates

This streaming API provides the foundation for real-time observability and enables responsive, live monitoring capabilities across the entire Logforge platform.