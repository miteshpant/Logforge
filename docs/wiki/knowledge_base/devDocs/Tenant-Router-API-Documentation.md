# Tenant Router API Documentation

## Overview

The Tenant Router provides comprehensive tenant lifecycle management for the Logforge platform, including tenant CRUD operations, storage configuration, usage tracking, compliance management, and health monitoring. This router handles all tenant-related operations with real database integration and no mock data.

## Base Information

- **Router File**: `/apps/api/routers/tenant_api.py`
- **Service Layer**: `/apps/api/services/tenant_service.py`
- **Data Layer**: `/apps/api/dao/tenant_dao.py`
- **URL Prefix**: `/v1/tenants`
- **Authentication**: Required for all endpoints (implicit through middleware)
- **Multi-Tenant**: All operations respect tenant isolation via database constraints

## Data Validation Status

✅ **No Mock/Dummy Data Found** - All endpoints use real database operations with ClickHouse integration. Fixed hardcoded values:
- **Storage Connection Latency**: Replaced hardcoded 45ms with real latency measurement via database query
- **Uptime Percentage**: Replaced hardcoded percentages (99.9%, 95.0%, 85.0%) with calculated values based on actual health check results

## API Endpoints

### Tenant CRUD Operations

#### Create Tenant
```http
POST /v1/tenants
```

**Description**: Create a new tenant with automatic UUID generation and default configuration setup

**Request Body**: `TenantCreate`
```json
{
  "name": "Acme Corporation",
  "type": "enterprise",
  "primary_contact_name": "John Smith",
  "primary_contact_email": "john.smith@acme.com",
  "industry": "Technology"
}
```

**Response**: `TenantResponse` (201 Created)
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Acme Corporation",
  "type": "enterprise",
  "status": "active",
  "primary_contact_name": "John Smith",
  "primary_contact_email": "john.smith@acme.com",
  "industry": "Technology",
  "created_at": "2025-09-27T14:30:00Z",
  "updated_at": "2025-09-27T14:30:00Z"
}
```

**Automatic Setup**: Creates default quotas, configurations, and subscription based on tenant type

#### List Tenants
```http
GET /v1/tenants?page=1&page_size=50&status=active&type=enterprise
```

**Description**: List tenants with pagination and filtering support

**Query Parameters**:
- `page`: Page number (default: 1, min: 1)
- `page_size`: Items per page (default: 50, min: 1, max: 100)
- `status`: Filter by tenant status (active, inactive, pending, suspended)
- `type`: Filter by tenant type (enterprise, smb, startup, etc.)

**Response**: `TenantListResponse`
```json
{
  "tenants": [
    {
      "tenant_id": "string",
      "name": "string",
      "type": "enterprise",
      "status": "active",
      "primary_contact_name": "string",
      "primary_contact_email": "string",
      "industry": "string",
      "created_at": "2025-09-27T14:30:00Z",
      "updated_at": "2025-09-27T14:30:00Z"
    }
  ],
  "total_count": 100,
  "page": 1,
  "page_size": 50,
  "total_pages": 2
}
```

#### Get Tenant Statistics
```http
GET /v1/tenants/stats
```

**Description**: Get lightweight tenant statistics for dashboard (performance optimized)

**Response**:
```json
{
  "total_tenants": 1247,
  "active_tenants": 1180,
  "inactive_tenants": 45,
  "pending_tenants": 15,
  "suspended_tenants": 7,
  "calculated_at": "2025-09-27T14:30:00Z"
}
```

#### Get Tenant Details
```http
GET /v1/tenants/{tenant_id}
```

**Description**: Retrieve detailed information for a specific tenant

**Response**: `TenantResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Acme Corporation",
  "type": "enterprise",
  "status": "active",
  "primary_contact_name": "John Smith",
  "primary_contact_email": "john.smith@acme.com",
  "industry": "Technology",
  "created_at": "2025-09-27T14:30:00Z",
  "updated_at": "2025-09-27T14:30:00Z"
}
```

**Error Handling**: Returns 404 for non-existent or inactive tenants

#### Update Tenant
```http
PUT /v1/tenants/{tenant_id}
```

**Description**: Update tenant information with automatic domain extraction

**Request Body**: `TenantUpdate`
```json
{
  "name": "Acme Corporation Ltd",
  "primary_contact_name": "Jane Smith",
  "primary_contact_email": "jane.smith@acme.com",
  "industry": "Financial Services",
  "type": "enterprise"
}
```

**Response**: `TenantResponse`

#### Decommission Tenant
```http
DELETE /v1/tenants/{tenant_id}?reason=contract_ended&data_retention=backup&backup_required=true
```

**Description**: Securely decommission tenant with data handling options

**Query Parameters**:
- `reason`: Decommissioning reason (default: "")
- `data_retention`: Data retention strategy (default: "backup")
- `backup_required`: Require backup before deletion (default: true)

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "decommissioned",
  "reason": "contract_ended",
  "data_retention": "backup",
  "backup_required": true,
  "decommissioned_at": "2025-09-27T14:30:00Z",
  "message": "Tenant successfully decommissioned"
}
```

### Storage Management

#### Configure Storage Backend
```http
POST /v1/tenants/{tenant_id}/storage/configure
```

**Description**: Configure storage backend settings for tenant

**Request Body**: `StorageConfig`
```json
{
  "backend_type": "s3",
  "config": {
    "bucket": "logforge-tenant-logs",
    "region": "us-east-1",
    "access_key": "AKIAIOSFODNN7EXAMPLE"
  },
  "compression_enabled": true,
  "encryption_enabled": true
}
```

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "storage_backend": "s3",
  "configuration": {
    "backend_type": "s3",
    "config": {},
    "compression_enabled": true,
    "encryption_enabled": true
  },
  "status": "configured",
  "configured_at": "2025-09-27T14:30:00Z"
}
```

#### Test Storage Connection
```http
POST /v1/tenants/{tenant_id}/storage/test-connection
```

**Description**: Test storage connectivity with real latency measurement

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "connection_status": "success",
  "latency_ms": 67,
  "test_timestamp": "2025-09-27T14:30:00Z",
  "backend_health": "healthy"
}
```

**Health Determination**:
- `latency_ms < 100`: "healthy"
- `100 <= latency_ms < 1000`: "degraded"
- `latency_ms >= 1000`: "unhealthy"

#### Get Storage Status
```http
GET /v1/tenants/{tenant_id}/storage/status
```

**Description**: Get storage status and usage statistics from storage service

**Response**: `StorageStatusResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "storage_backend": "clickhouse",
  "total_size_bytes": 1073741824,
  "hot_storage_bytes": 536870912,
  "warm_storage_bytes": 268435456,
  "cold_storage_bytes": 268435456,
  "health_status": "healthy",
  "connection_status": "connected",
  "last_backup": "2025-09-27T14:30:00Z"
}
```

### Usage & Billing

#### Get Tenant Usage
```http
GET /v1/tenants/{tenant_id}/usage
```

**Description**: Get tenant usage statistics and billing data from usage service

**Response**: `TenantUsageResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "current_period": "2025-09",
  "data_ingested_bytes": 5368709120,
  "queries_executed": 2450,
  "alerts_triggered": 12,
  "storage_used_bytes": 1073741824,
  "cost_breakdown": {
    "ingestion": 25.50,
    "storage": 15.75,
    "queries": 8.25,
    "alerts": 2.00,
    "total": 51.50
  }
}
```

#### Get Tenant Quotas
```http
GET /v1/tenants/{tenant_id}/quotas
```

**Description**: Retrieve tenant quotas and limits from database

**Response**: `TenantQuotas`
```json
{
  "max_data_ingestion_gb_per_day": 100,
  "max_queries_per_hour": 10000,
  "max_storage_gb": 500,
  "max_alerts": 50,
  "max_users": 25
}
```

#### Update Tenant Quotas
```http
PUT /v1/tenants/{tenant_id}/quotas
```

**Description**: Update tenant quotas and limits

**Request Body**: `TenantQuotas`
```json
{
  "max_data_ingestion_gb_per_day": 200,
  "max_queries_per_hour": 20000,
  "max_storage_gb": 1000,
  "max_alerts": 100,
  "max_users": 50
}
```

**Response**: `TenantQuotas` (updated values)

### Configuration & Compliance

#### Get Tenant Configuration
```http
GET /v1/tenants/{tenant_id}/config
```

**Description**: Retrieve tenant configuration from database with JSON parsing

**Response**: `TenantConfig`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timezone": "UTC",
  "log_retention_days": 90,
  "encryption_enabled": true,
  "notification_settings": {
    "email_enabled": true,
    "slack_enabled": false
  },
  "custom_branding": {
    "logo_url": "https://example.com/logo.png",
    "primary_color": "#007bff"
  },
  "alert_settings": {
    "email_enabled": true,
    "slack_enabled": true,
    "webhook_enabled": false
  },
  "integration_settings": {
    "slack_webhook": "https://hooks.slack.com/..."
  },
  "security_settings": {
    "mfa_required": true,
    "session_timeout": 3600
  },
  "ui_preferences": {
    "theme": "dark",
    "dashboard_layout": "grid"
  }
}
```

#### Update Tenant Configuration
```http
PUT /v1/tenants/{tenant_id}/config
```

**Description**: Update tenant configuration with nested JSON field support

**Request Body**: `TenantConfig`
```json
{
  "timezone": "America/New_York",
  "log_retention_days": 180,
  "encryption_enabled": true,
  "alert_settings": {
    "email_enabled": true,
    "slack_enabled": true,
    "pagerduty_enabled": true
  }
}
```

**Response**: `TenantConfig` (updated configuration)

#### Get Compliance Status
```http
GET /v1/tenants/{tenant_id}/compliance
```

**Description**: Get compliance status and reports using real database data

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "compliance_status": "compliant",
  "last_audit": "2025-09-01T00:00:00Z",
  "requirements": ["SOX", "GDPR", "PCI-DSS"],
  "reports": [
    {
      "type": "sox",
      "status": "completed",
      "generated_at": "2025-09-01T00:00:00Z"
    }
  ],
  "legal_holds": 2,
  "retention_policies": 3
}
```

#### Create Legal Hold
```http
POST /v1/tenants/{tenant_id}/legal-hold
```

**Description**: Create legal hold for data preservation with database persistence

**Request Body**: `LegalHoldRequest`
```json
{
  "case_id": "CASE-2025-001",
  "custodian": "legal@acme.com",
  "reason": "Litigation hold for contract dispute",
  "date_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2025-12-31T23:59:59Z"
  },
  "scope": {
    "data_types": ["logs", "emails", "documents"],
    "departments": ["sales", "legal"]
  }
}
```

**Response**:
```json
{
  "hold_id": "hold-uuid",
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "case_id": "CASE-2025-001",
  "custodian": "legal@acme.com",
  "reason": "Litigation hold for contract dispute",
  "date_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2025-12-31T23:59:59Z"
  },
  "scope": {
    "data_types": ["logs", "emails", "documents"],
    "departments": ["sales", "legal"]
  },
  "status": "active",
  "created_at": "2025-09-27T14:30:00Z"
}
```

### Health & Monitoring

#### Get Tenant Health
```http
GET /v1/tenants/{tenant_id}/health
```

**Description**: Get comprehensive tenant health status with real system checks

**Response**: `TenantHealthResponse`
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "overall_health": "healthy",
  "service_status": {
    "database": "healthy",
    "storage": "healthy",
    "ingestion": "degraded",
    "query_engine": "healthy",
    "alerts": "healthy"
  },
  "storage_health": "healthy",
  "ingestion_health": "degraded",
  "query_health": "healthy",
  "alert_health": "healthy",
  "active_alerts": 3,
  "last_check": "2025-09-27T14:30:00Z",
  "uptime_percentage": 96.0,
  "issues": [
    "No recent log ingestion activity (24h)"
  ]
}
```

**Health Check Details**:
- **Database**: Connection test via `SELECT 1`
- **Storage**: Tenant data access verification
- **Ingestion**: Recent log activity check (24h)
- **Query Engine**: Query performance test with latency measurement
- **Alerts**: Alert system accessibility check

**Uptime Calculation**: Based on actual health check results (Healthy=100%, Degraded=70%, Unhealthy=0%)

#### Get Tenant Metrics
```http
GET /v1/tenants/{tenant_id}/metrics
```

**Description**: Get tenant performance metrics and analytics using real database queries

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "performance_metrics": {
    "avg_query_time_ms": 125.5,
    "ingestion_rate_eps": 85.2,
    "query_success_rate": 99.2,
    "storage_efficiency": 3.2
  },
  "usage_metrics": {
    "total_logs": 1500000,
    "logs_per_day": 7350,
    "weekly_average": 7200,
    "active_alerts": 12,
    "total_alert_rules": 25
  },
  "error_rates": {
    "ingestion_errors": 0.45,
    "query_errors": 0.60,
    "storage_errors": 0.30,
    "total_error_rate": 1.5
  },
  "response_times": {
    "avg_ingestion_time_ms": 37.5,
    "avg_query_time_ms": 125.0,
    "p95_query_time_ms": 312.5,
    "p99_query_time_ms": 625.0
  },
  "resource_utilization": {
    "cpu_usage_percent": 38.4,
    "memory_usage_percent": 55.8,
    "disk_usage_percent": 22.0,
    "network_usage_mbps": 12.4
  },
  "quotas": {
    "monthly_ingestion": {
      "limit": 1000000,
      "used": 750000,
      "percentage": 75.0
    },
    "storage_gb": {
      "limit": 500,
      "used": 320,
      "percentage": 64.0
    }
  },
  "time_range": {
    "start": "2025-09-20T14:30:00Z",
    "end": "2025-09-27T14:30:00Z"
  }
}
```

**Metrics Calculation**:
- **Real Database Queries**: Log counts, alert statistics, quota usage
- **Calculated Performance**: Based on actual data volume and tenant activity
- **Storage Efficiency**: Real compression ratio from StorageDAO

#### Get Tenant Alerts
```http
GET /v1/tenants/{tenant_id}/alerts
```

**Description**: Get tenant-specific alerts configuration using AlertDAO

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "active_alerts": 8,
  "alert_rules": {
    "total_rules": 25,
    "active_rules": 20,
    "disabled_rules": 5
  },
  "notification_channels": {
    "email": true,
    "slack": true,
    "webhook": false,
    "pagerduty": true
  },
  "escalation_policies": [
    {
      "policy_id": "policy-1",
      "name": "Critical Alert Escalation",
      "levels": ["team-lead", "manager", "director"]
    }
  ],
  "recent_alerts": [
    {
      "alert_id": "alert-1",
      "rule_name": "High Error Rate",
      "severity": "high",
      "triggered_at": "2025-09-27T14:25:00Z",
      "status": "triggered"
    }
  ],
  "last_updated": "2025-09-27T14:30:00Z"
}
```

### Utility Endpoints

#### Validate Tenant
```http
GET /v1/tenants/{tenant_id}/validate
```

**Description**: Validate tenant UUID format and database existence

**Response**:
```json
{
  "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "valid": true,
  "exists": true,
  "validated_at": "2025-09-27T14:30:00Z"
}
```

**Validation Process**:
1. **UUID Format Check**: Validates UUID format
2. **Database Existence**: Queries database for tenant record
3. **Status Verification**: Ensures tenant is accessible

## Database Tables

### Core Tables
- `tenants_mt` - Core tenant information
- `tenant_configs_mt` - Tenant configuration settings
- `tenant_quotas_mt` - Tenant quotas and limits
- `tenant_storage_configs_mt` - Storage backend configurations
- `legal_holds_mt` - Legal hold records

### Key Features

#### Real Database Operations
- **ClickHouse Integration**: All operations use ClickHouse database
- **Multi-Tenant Isolation**: Complete data separation via customer_id
- **ACID Compliance**: Transactional consistency for all operations
- **Read-After-Write Consistency**: Proper synchronization mechanisms

#### Comprehensive Health Monitoring
- **Real System Checks**: Database connectivity, storage access, query performance
- **Calculated Uptime**: Based on actual health check results
- **Performance Metrics**: Real data volume and latency measurements
- **Service Status Tracking**: Individual component health monitoring

#### Advanced Configuration Management
- **JSON Field Support**: Nested configuration with proper parsing
- **Type Validation**: String, number, boolean, and JSON config types
- **Hierarchical Settings**: Basic and nested configuration fields
- **Real-Time Updates**: Immediate configuration persistence

#### Storage Management
- **Multi-Backend Support**: S3, GCS, Azure, MinIO integration
- **Real Latency Testing**: Actual database query measurement
- **Health Assessment**: Dynamic health status based on performance
- **Usage Tracking**: Real storage consumption from StorageService

#### Compliance & Legal
- **Real Database Storage**: Legal holds stored in ClickHouse
- **Audit Trail**: Complete compliance activity tracking
- **Status Management**: Active/expired/cancelled legal hold states
- **Scope Definition**: Detailed data preservation parameters

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid tenant type: invalid_type"
}
```

#### 404 Not Found
```json
{
  "detail": "Tenant not found"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Database connection failed"
}
```

### Tenant Status Handling
- **Inactive Tenants**: Return 404 for decommissioned tenants
- **Validation Errors**: Proper error messages for invalid data
- **Database Errors**: Graceful handling of connection issues

## Testing

### Test Coverage
- **CRUD Operations**: Create, read, update, delete operations
- **Configuration Management**: Complex configuration updates
- **Health Monitoring**: Real system health checks
- **Storage Integration**: Backend connectivity testing
- **Compliance Features**: Legal hold management

### Database Integration
- **Real Queries**: All tests use actual ClickHouse operations
- **Multi-Tenant Validation**: Proper tenant isolation testing
- **Performance Testing**: Latency and throughput validation
- **Error Scenarios**: Database failure handling

## Implementation Notes

### No Mock Data Policy
- **Eliminated Hardcoded Values**: Real latency measurement for storage tests
- **Dynamic Uptime Calculation**: Based on actual health check results
- **Real Database Operations**: All endpoints use ClickHouse integration
- **Authentic Metrics**: Performance data from actual system measurements

### Performance Optimizations
- **Lazy Service Initialization**: Prevents startup database connections
- **Query Optimization**: Efficient ClickHouse queries with proper indexing
- **Connection Pooling**: Efficient database connection management
- **Caching Strategy**: Appropriate caching for configuration data

### Security Features
- **Multi-Tenant Isolation**: Complete data separation via customer_id
- **Input Validation**: Comprehensive request validation
- **Authentication Integration**: Seamless middleware integration
- **Audit Logging**: Complete activity tracking

### Default Configuration Setup
- **Automatic Provisioning**: Default quotas, configs, and subscriptions
- **Tier-Based Setup**: Configuration based on tenant type
- **Service Integration**: Automatic subscription service integration
- **Error Resilience**: Graceful handling of setup failures

This tenant router provides enterprise-grade tenant management with comprehensive lifecycle operations, real-time health monitoring, and robust compliance features, all backed by real database operations and no mock data.