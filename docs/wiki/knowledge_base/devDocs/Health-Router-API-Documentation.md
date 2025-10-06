# Health Router API Documentation

## Overview

The Health Router provides system health monitoring and basic platform information endpoints. These endpoints are essential for monitoring service availability, diagnosing system issues, and providing platform metadata without requiring authentication.

## Base Information

- **Router File**: `/apps/api/routers/health.py`
- **Service Layer**: `/apps/api/services/health_service.py`
- **URL Prefix**: `/` (root level)
- **Authentication**: Not required (public endpoints)

## Data Validation Status

✅ **No Mock/Dummy Data Found** - All endpoints use real service connectivity tests and actual system metrics.

## API Endpoints

### System Health Monitoring

#### Basic Health Check
```http
GET /health
```

**Description**: Real health check endpoint with actual service connectivity tests

**Authentication**: None required

**Response Model**: `HealthResponse`
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "services": {
    "api": "healthy|degraded|unhealthy",
    "database": "healthy|degraded|unhealthy", 
    "clickhouse": "healthy|degraded|unhealthy",
    "storage": "healthy|degraded|unhealthy",
    "error": "Error message if applicable"
  }
}
```

**Service Integration**: `HealthService.get_overall_health()`
- **Test Coverage**: API, database, ClickHouse, storage connectivity
- **Status Levels**: healthy, degraded, unhealthy, unknown
- **Error Handling**: Graceful degradation on service failures

**Success Response (200)**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "services": {
    "api": "healthy",
    "database": "healthy",
    "clickhouse": "healthy", 
    "storage": "healthy"
  }
}
```

**Degraded Response (200)**:
```json
{
  "status": "unhealthy",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "services": {
    "api": "degraded",
    "database": "unknown",
    "clickhouse": "unknown",
    "storage": "unknown",
    "error": "Health service failed: Connection timeout"
  }
}
```

---

#### Detailed Health Check
```http
GET /health/detailed
```

**Description**: Detailed health check with comprehensive metrics and diagnostics

**Authentication**: None required

**Response**: Extended health information with detailed metrics
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00.000Z",
  "services": {
    "api": {
      "status": "healthy",
      "response_time_ms": 12,
      "uptime_seconds": 86400
    },
    "database": {
      "status": "healthy",
      "connection_pool": "8/10",
      "query_time_ms": 5
    },
    "clickhouse": {
      "status": "healthy", 
      "cluster_nodes": 3,
      "disk_usage_percent": 45,
      "memory_usage_mb": 2048
    },
    "storage": {
      "status": "healthy",
      "buckets_accessible": 4,
      "total_size_gb": 1024.5
    }
  },
  "metrics": {
    "requests_per_second": 150,
    "active_connections": 45,
    "error_rate_percent": 0.1
  }
}
```

**Service Integration**: `HealthService.get_detailed_health()`
- **Comprehensive Metrics**: Response times, resource usage, performance counters
- **Service Diagnostics**: Connection pools, cluster status, storage health
- **Real-time Data**: Current system performance and utilization

**Error Response (503)**:
```json
{
  "detail": "Health service unavailable: Service connection failed"
}
```

---

### Platform Information

#### Root Endpoint
```http
GET /
```

**Description**: Root endpoint with basic platform information and feature overview

**Authentication**: None required

**Response**: Platform metadata and feature list
```json
{
  "message": "Logforge API - Advanced observability and SIEM platform",
  "version": "1.0.0",
  "docs": "/docs",
  "features": [
    "Multi-format log ingestion",
    "Advanced query engine", 
    "Real-time dashboards",
    "Rule-based alerting",
    "Security analytics",
    "Distributed tracing",
    "Metrics collection"
  ]
}
```

**Use Cases**:
- Platform discovery and capabilities overview
- Version information for client compatibility
- Feature detection for UI/client configuration
- Basic connectivity testing

## Health Status Definitions

### Service Status Levels

| Status | Description | Criteria |
|--------|-------------|----------|
| `healthy` | Service fully operational | All connectivity tests pass, response times normal |
| `degraded` | Service operational with issues | Some tests fail, elevated response times |
| `unhealthy` | Service not operational | Most/all tests fail, service unavailable |
| `unknown` | Status cannot be determined | Health check itself failed |

### Service Components

#### API Service
- **Tests**: Internal service health, memory usage
- **Metrics**: Response time, uptime, active connections
- **Thresholds**: Response time < 100ms (healthy), < 500ms (degraded)

#### Database Service
- **Tests**: Connection establishment, query execution
- **Metrics**: Connection pool status, query response time
- **Thresholds**: Query time < 50ms (healthy), < 200ms (degraded)

#### ClickHouse Service
- **Tests**: Cluster connectivity, query execution
- **Metrics**: Node availability, disk usage, memory usage
- **Thresholds**: Disk < 80% (healthy), < 95% (degraded)

#### Storage Service
- **Tests**: Bucket accessibility, read/write operations
- **Metrics**: Available buckets, total storage size
- **Thresholds**: All buckets accessible (healthy)

## Monitoring Integration

### Load Balancer Health Checks
Configure load balancers to use `/health` endpoint:
```yaml
health_check:
  path: /health
  interval: 30s
  timeout: 5s
  healthy_threshold: 2
  unhealthy_threshold: 3
```

### Kubernetes Probes
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

### External Monitoring
- **Prometheus**: Scrape `/health/detailed` for metrics collection
- **Nagios/Zabbix**: Monitor `/health` for status changes
- **Datadog/New Relic**: Health endpoint integration for APM

## Error Handling

### Health Service Failures
When `HealthService` itself fails:
- Returns degraded status with error details
- Provides fallback service status as "unknown"
- Includes error message in response
- Returns HTTP 200 (not 5xx) to avoid cascade failures

### Individual Service Failures
When specific services (DB, ClickHouse, etc.) fail:
- Overall status reflects worst individual status
- Failed services marked as "unhealthy" or "unknown"
- Healthy services continue reporting normally
- Detailed error information in service object

## Performance Characteristics

- **Response Time**: < 100ms for basic health check
- **Detailed Check**: < 500ms with full diagnostics
- **Concurrency**: Handles unlimited concurrent health checks
- **Caching**: No caching to ensure real-time status
- **Resource Usage**: Minimal CPU/memory impact

## Security Considerations

- **No Authentication**: Health endpoints are public by design
- **Information Disclosure**: Limited to operational status, no sensitive data
- **DDoS Protection**: Consider rate limiting in production
- **Network Security**: Ensure endpoints are accessible to monitoring systems

## Troubleshooting

### Common Issues

1. **False Positives**: Intermittent failures due to network latency
   - **Solution**: Increase health check timeouts
   - **Monitoring**: Track response time trends

2. **Cascade Failures**: Health endpoint becomes unavailable
   - **Solution**: Separate health service from main application
   - **Fallback**: Static health endpoint with minimal dependencies

3. **Resource Exhaustion**: Health checks consume excessive resources
   - **Solution**: Optimize health check queries
   - **Rate Limiting**: Implement endpoint-level rate limiting

### Debugging Steps

1. Check detailed health endpoint for specific service failures
2. Verify network connectivity to dependent services
3. Monitor resource usage during health check execution
4. Review service logs for health check errors
5. Test individual service connectivity manually

## Integration Examples

### Bash Health Check
```bash
#!/bin/bash
response=$(curl -s http://localhost:8080/health)
status=$(echo $response | jq -r '.status')

if [ "$status" == "healthy" ]; then
  echo "Service is healthy"
  exit 0
else
  echo "Service is $status"
  exit 1
fi
```

### Python Health Monitor
```python
import requests
import json
import time

def check_health():
    try:
        response = requests.get('http://localhost:8080/health', timeout=5)
        health_data = response.json()
        
        print(f"Overall Status: {health_data['status']}")
        for service, status in health_data['services'].items():
            print(f"  {service}: {status}")
            
        return health_data['status'] == 'healthy'
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Continuous monitoring
while True:
    if not check_health():
        # Alert or take corrective action
        pass
    time.sleep(30)
```

This health monitoring system provides comprehensive service observability and enables proactive issue detection across the Logforge platform infrastructure.