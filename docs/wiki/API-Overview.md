# Logforge API Overview

## Introduction

Logforge is an advanced, cost-effective observability + SIEM platform designed for enterprise security and operations teams. The API provides comprehensive access to log ingestion, querying, alerting, security analytics, and observability features.

- **API Version**: 0.1.0
- **Base URL**: `http://localhost:7080` (development) / `https://api.logforge.com` (production)
- **OpenAPI Version**: 3.1.0
- **Total Endpoints**: 194+ endpoints across 9 functional categories

## Architecture Overview

- **Storage**: ClickHouse (hot data), Multi-cloud (S3/GCS/Azure/MinIO) cold storage
- **Ingestion**: HTTP/OTLP (OpenTelemetry), Syslog, multi-format parsing
- **Message Queue**: Redpanda (dev) / Kafka (prod)
- **API**: FastAPI (Python) with comprehensive endpoint coverage
- **Multi-Tenant**: Complete tenant isolation with role-based access control

## Authentication

All API endpoints (except health checks) require authentication using:

### Bearer Token Authentication
```http
Authorization: Bearer <your-jwt-token>
```

### Multi-Tenant Header
```http
X-Customer-ID: <your-tenant-id>
```

### Authentication Flow
1. **Login**: `POST /v1/auth/login` - Get JWT token
2. **Session Management**: Token validation and refresh
3. **Logout**: `POST /v1/auth/logout` - Invalidate session

## API Categories

### 1. [Authentication APIs](./Authentication-APIs.md)
Authentication, session management, and API key operations
- **Endpoints**: 8+
- **Key Features**: JWT tokens, session management, API keys, MFA

### 2. [User Management APIs](./User-Management-APIs.md)
User CRUD operations, roles, and permissions
- **Endpoints**: 25+
- **Key Features**: User lifecycle, role-based access, bulk operations

### 3. [Data APIs](./Data-APIs.md)
Log ingestion, querying, and data export
- **Endpoints**: 25+
- **Key Features**: Multi-format ingestion, advanced querying, export capabilities

### 4. [Security Analytics APIs](./Security-Analytics-APIs.md)
SIEM capabilities, threat detection, and security analytics
- **Endpoints**: 15+
- **Key Features**: Sigma rules, threat intelligence, MITRE ATT&CK mapping

### 5. [Observability APIs](./Observability-APIs.md)
Metrics, traces, and APM functionality
- **Endpoints**: 20+
- **Key Features**: Distributed tracing, metrics collection, service mapping

### 6. [Dashboard APIs](./Dashboard-APIs.md)
Dashboard management and data visualization
- **Endpoints**: 12+
- **Key Features**: Custom dashboards, widgets, sharing capabilities

### 7. [Enterprise APIs](./Enterprise-APIs.md)
Enterprise features, compliance, and advanced administration
- **Endpoints**: 25+
- **Key Features**: RBAC, compliance reporting, enterprise integrations

### 8. [Tenant Management APIs](./Tenant-Management-APIs.md)
Multi-tenant management and configuration
- **Endpoints**: 30+
- **Key Features**: Tenant lifecycle, billing, usage tracking

### 9. [Alert APIs](./Alert-APIs.md)
Alert rules, notifications, and alert management
- **Endpoints**: 15+
- **Key Features**: Rule-based alerting, multi-channel notifications

## Common Request/Response Patterns

### Standard Headers
```http
Content-Type: application/json
Authorization: Bearer <token>
X-Customer-ID: <tenant-id>
```

### Error Response Format
```json
{
  "detail": "Error description",
  "type": "validation_error",
  "code": "INVALID_INPUT"
}
```

### Pagination
```json
{
  "items": [...],
  "total": 1000,
  "page": 1,
  "limit": 50,
  "has_more": true
}
```

### Timestamps
All timestamps use ISO 8601 format: `2024-01-15T10:30:00Z`

## Rate Limiting

- **Default**: 1000 requests/minute per tenant
- **Ingestion**: 10,000 requests/minute per tenant
- **Query**: 100 requests/minute per user

## Data Retention

- **Hot Storage**: 30 days (ClickHouse)
- **Cold Storage**: Configurable (90 days to 7 years)
- **Compliance**: SOX, GDPR, HIPAA, PCI-DSS support

## Performance Targets

- **Ingest**: ≥50,000 EPS per node
- **Query**: p50 < 1.5s for 24h window on 200M rows
- **Alert Latency**: <60s schedule-to-notify
- **API Response**: <500ms for most endpoints

## Getting Started

1. **Setup Authentication**: Get JWT token via login
2. **Verify Access**: Check health endpoints
3. **Ingest Data**: Start with `/v1/ingest/logs`
4. **Query Data**: Use `/v1/query/advanced`
5. **Create Dashboards**: Build visualizations
6. **Setup Alerts**: Configure monitoring rules

## SDK and Integration

- **Python SDK**: Available for all endpoints
- **REST API**: Full OpenAPI 3.1 specification
- **WebSocket**: Real-time streaming for dashboards
- **Webhooks**: Event notifications and integrations

## Support and Documentation

- **API Documentation**: Comprehensive endpoint documentation
- **Examples**: Request/response examples for all endpoints
- **Testing**: Built-in validation and testing endpoints
- **Monitoring**: Health checks and system status endpoints

---

*For detailed endpoint documentation, see the specific API category files linked above.*