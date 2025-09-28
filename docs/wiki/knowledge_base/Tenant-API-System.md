# Logforge Tenant API System

## Overview

The Tenant API (`/v1/tenants`) provides comprehensive multi-tenant lifecycle management for the Logforge platform. This system handles tenant onboarding, configuration, storage management, usage tracking, compliance, and decommissioning with full enterprise-grade capabilities.

## Architecture

**Location**: `/apps/api/routers/tenant_api.py`  
**Service**: `tenant_service` (dependency injection)  
**Authentication**: Platform admin or tenant admin roles required  
**Multi-Tenancy**: Full tenant isolation with UUID-based identification  

## Core Endpoints

### 1. Tenant Lifecycle Management

#### **POST /v1/tenants** - Create Tenant
Creates a new tenant with UUID generation and database persistence.

**Request Model**: `TenantCreate`
```json
{
  "name": "Organization Name",
  "type": "enterprise|smb|startup|non_profit|government|education|healthcare|financial",
  "primary_contact_name": "Contact Name",
  "primary_contact_email": "contact@example.com",
  "address": "Organization Address",
  "industry": "Industry Sector",
  "company_size": 100,
  "website": "https://example.com",
  "notes": "Additional notes"
}
```

**Response**: `TenantResponse` (201 Created)
```json
{
  "tenant_id": "uuid-generated",
  "name": "Organization Name",
  "type": "enterprise",
  "status": "active",
  "primary_contact_name": "Contact Name",
  "primary_contact_email": "contact@example.com",
  "industry": "Industry Sector",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Key Features**:
- Automatic UUID generation for tenant_id
- Email validation for primary contact
- Support for 8 organization types
- Comprehensive metadata capture
- Audit trail creation

#### **GET /v1/tenants** - List Tenants
List tenants with pagination and filtering capabilities.

**Query Parameters**:
- `page`: Page number (default: 1, min: 1)
- `page_size`: Items per page (default: 50, max: 100)
- `status`: Filter by TenantStatus (active, inactive, suspended)
- `type`: Filter by TenantType

**Response**: `TenantListResponse`
```json
{
  "tenants": [...],
  "total_count": 150,
  "page": 1,
  "page_size": 50,
  "total_pages": 3
}
```

#### **GET /v1/tenants/stats** - Tenant Statistics
Performance-optimized lightweight statistics for dashboards.

**Response**:
```json
{
  "total_tenants": 1247,
  "active_tenants": 1195,
  "total_revenue": 127450.00,
  "total_data_tb": 15.2
}
```

**Performance**: Optimized for admin dashboards (250x data reduction vs full tenant list)

#### **GET /v1/tenants/{tenant_id}** - Get Tenant
Retrieve detailed tenant information by UUID.

**Security**: Returns 404 for inactive/decommissioned tenants (security through obscurity)

#### **PUT /v1/tenants/{tenant_id}** - Update Tenant
Update tenant information with partial updates supported.

**Request Model**: `TenantUpdate` (all fields optional)

#### **DELETE /v1/tenants/{tenant_id}** - Decommission Tenant
Securely decommission tenant with data retention options.

**Query Parameters**:
- `reason`: Decommissioning reason (required for audit)
- `data_retention`: Strategy (backup, archive, purge)
- `backup_required`: Require backup before deletion (default: true)

**Response**:
```json
{
  "tenant_id": "uuid",
  "status": "decommissioned",
  "decommission_date": "2024-01-01T00:00:00Z",
  "backup_location": "s3://backups/tenant-uuid/",
  "data_retention": "backup",
  "reason": "Contract expired"
}
```

### 2. Storage Management

#### **POST /v1/tenants/{tenant_id}/storage/configure** - Configure Storage
Configure multi-cloud storage backend for tenant data.

**Request Model**: `StorageConfig`
```json
{
  "backend_type": "s3|gcs|azure|minio|clickhouse",
  "region": "us-east-1",
  "bucket_name": "tenant-logs-bucket",
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "encrypted",
  "encryption_enabled": true,
  "lifecycle_policy": {
    "hot_retention_days": 30,
    "warm_retention_days": 90,
    "cold_retention_days": 365
  }
}
```

**Supported Backends**:
- **AWS S3**: Full S3 API compatibility with lifecycle management
- **Google Cloud Storage**: Native GCS integration
- **Azure Blob Storage**: Azure-native storage with compliance
- **MinIO**: Self-hosted S3-compatible storage
- **ClickHouse**: High-performance columnar storage

#### **POST /v1/tenants/{tenant_id}/storage/test-connection** - Test Storage
Validate storage connectivity and credentials.

**Response**:
```json
{
  "connection_status": "success",
  "latency_ms": 45,
  "read_test": "passed",
  "write_test": "passed",
  "encryption_test": "passed",
  "tested_at": "2024-01-01T00:00:00Z"
}
```

#### **GET /v1/tenants/{tenant_id}/storage/status** - Storage Status
Get comprehensive storage utilization and health.

**Response Model**: `StorageStatusResponse`
```json
{
  "backend_type": "s3",
  "region": "us-east-1",
  "total_size_gb": 1024.5,
  "used_size_gb": 512.3,
  "available_size_gb": 512.2,
  "compression_ratio": 3.2,
  "encryption_status": "enabled",
  "lifecycle_policy_active": true,
  "last_backup": "2024-01-01T00:00:00Z",
  "health_status": "healthy"
}
```

### 3. Usage & Billing Management

#### **GET /v1/tenants/{tenant_id}/usage** - Usage Statistics
Comprehensive tenant usage analytics for billing and monitoring.

**Response Model**: `TenantUsageResponse`
```json
{
  "tenant_id": "uuid",
  "billing_period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "usage_summary": {
    "data_ingested_gb": 245.7,
    "queries_executed": 15420,
    "alerts_triggered": 87,
    "api_calls": 125430,
    "storage_used_gb": 512.3,
    "bandwidth_gb": 89.2
  },
  "cost_breakdown": {
    "ingestion_cost": 49.14,
    "storage_cost": 25.62,
    "query_cost": 77.10,
    "bandwidth_cost": 4.46,
    "total_cost": 156.32
  },
  "feature_usage": {
    "security_events": 1250,
    "compliance_reports": 4,
    "integrations_active": 3,
    "users_active": 25
  },
  "currency": "USD"
}
```

#### **GET /v1/tenants/{tenant_id}/quotas** - Get Quotas
Retrieve tenant resource quotas and limits.

**Response Model**: `TenantQuotas`
```json
{
  "max_data_ingestion_gb_per_day": 100,
  "max_queries_per_hour": 1000,
  "max_storage_gb": 2000,
  "max_alerts": 50,
  "max_users": 25,
  "current_usage": {
    "data_ingestion_gb_today": 45.2,
    "queries_last_hour": 234,
    "storage_used_gb": 512.3,
    "active_alerts": 12,
    "active_users": 18
  }
}
```

#### **PUT /v1/tenants/{tenant_id}/quotas** - Update Quotas
Update tenant resource quotas (admin operation).

### 4. Configuration & Compliance

#### **GET /v1/tenants/{tenant_id}/config** - Get Configuration
Retrieve tenant configuration settings.

**Response Model**: `TenantConfig`
```json
{
  "tenant_id": "uuid",
  "timezone": "UTC",
  "log_retention_days": 90,
  "encryption_enabled": true,
  "notification_settings": {
    "email_alerts": true,
    "slack_integration": true,
    "webhook_url": "https://hooks.example.com/webhook"
  },
  "security_settings": {
    "mfa_required": true,
    "session_timeout_hours": 8,
    "ip_whitelist": ["192.168.1.0/24"]
  },
  "ui_preferences": {
    "dashboard_refresh_interval": 30,
    "default_log_format": "json",
    "timezone_display": "local"
  }
}
```

#### **PUT /v1/tenants/{tenant_id}/config** - Update Configuration
Update tenant configuration with validation.

#### **GET /v1/tenants/{tenant_id}/compliance** - Compliance Status
Get compliance framework status and reports.

**Response**:
```json
{
  "compliance_frameworks": ["SOX", "GDPR", "HIPAA"],
  "compliance_scores": {
    "SOX": 95.2,
    "GDPR": 89.7,
    "HIPAA": 92.1
  },
  "audit_readiness": true,
  "last_compliance_check": "2024-01-01T00:00:00Z",
  "findings": [
    {
      "framework": "GDPR",
      "severity": "medium",
      "finding": "Data retention period exceeds recommended 24 months",
      "remediation": "Review and update data retention policy"
    }
  ],
  "certifications": ["SOC2", "ISO27001"],
  "next_audit_date": "2024-06-01T00:00:00Z"
}
```

#### **POST /v1/tenants/{tenant_id}/legal-hold** - Create Legal Hold
Implement legal hold for data preservation.

**Request Model**: `LegalHoldRequest`
```json
{
  "case_name": "Case ABC-2024",
  "description": "Litigation hold order",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-12-31T23:59:59Z",
  "contact_person": "Legal Counsel",
  "contact_email": "legal@example.com",
  "data_types": ["logs", "emails", "documents"],
  "justification": "Court order dated 2024-01-01"
}
```

**Response**:
```json
{
  "hold_id": "uuid",
  "status": "active",
  "preservation_start": "2024-01-01T00:00:00Z",
  "scope": {
    "data_types": ["logs", "emails", "documents"],
    "date_range": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-12-31T23:59:59Z"
    }
  },
  "custodian": "Legal Counsel",
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 5. Health & Monitoring

#### **GET /v1/tenants/{tenant_id}/health** - Tenant Health
Comprehensive tenant health diagnostics.

**Response Model**: `TenantHealthResponse`
```json
{
  "tenant_id": "uuid",
  "overall_status": "healthy",
  "components": {
    "storage": {
      "status": "healthy",
      "latency_ms": 45,
      "error_rate": 0.01
    },
    "ingestion": {
      "status": "healthy",
      "throughput_eps": 1250,
      "queue_depth": 45
    },
    "queries": {
      "status": "warning",
      "avg_response_time_ms": 1800,
      "slow_query_count": 12
    },
    "alerts": {
      "status": "healthy",
      "active_rules": 25,
      "triggered_last_hour": 3
    }
  },
  "resource_utilization": {
    "cpu_usage_percent": 65.2,
    "memory_usage_percent": 78.4,
    "storage_usage_percent": 45.8,
    "network_usage_mbps": 125.6
  },
  "sla_compliance": {
    "uptime_percentage": 99.97,
    "availability_target": 99.9,
    "performance_target": 95.0,
    "performance_actual": 97.3
  },
  "last_health_check": "2024-01-01T00:00:00Z"
}
```

#### **GET /v1/tenants/{tenant_id}/metrics** - Performance Metrics
Detailed performance analytics and KPIs.

**Response**:
```json
{
  "tenant_id": "uuid",
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-01T23:59:59Z"
  },
  "ingestion_metrics": {
    "events_per_second": 1250,
    "peak_eps": 2500,
    "total_events": 108000,
    "error_rate": 0.001,
    "avg_latency_ms": 25
  },
  "query_metrics": {
    "queries_per_hour": 450,
    "avg_response_time_ms": 850,
    "p95_response_time_ms": 2100,
    "success_rate": 99.8,
    "cache_hit_rate": 65.2
  },
  "storage_metrics": {
    "compression_ratio": 3.2,
    "read_iops": 1500,
    "write_iops": 800,
    "avg_read_latency_ms": 15,
    "avg_write_latency_ms": 8
  },
  "alert_metrics": {
    "rules_evaluated_per_minute": 2500,
    "alerts_triggered": 87,
    "false_positive_rate": 2.1,
    "avg_detection_time_seconds": 45
  }
}
```

#### **GET /v1/tenants/{tenant_id}/alerts** - Alert Configuration
Tenant-specific alert configuration and status.

**Response**:
```json
{
  "tenant_id": "uuid",
  "alert_configuration": {
    "enabled": true,
    "notification_channels": ["email", "slack", "webhook"],
    "escalation_policies": [
      {
        "severity": "critical",
        "escalation_delay_minutes": 5,
        "notification_methods": ["email", "sms", "call"]
      },
      {
        "severity": "warning",
        "escalation_delay_minutes": 30,
        "notification_methods": ["email"]
      }
    ]
  },
  "active_alerts": {
    "critical": 0,
    "warning": 3,
    "info": 12
  },
  "alert_history": {
    "last_24_hours": 15,
    "last_week": 87,
    "last_month": 342
  },
  "alert_rules": {
    "total_rules": 25,
    "enabled_rules": 23,
    "disabled_rules": 2,
    "rule_types": {
      "threshold": 15,
      "anomaly": 6,
      "pattern": 4
    }
  }
}
```

### 6. Utility Operations

#### **GET /v1/tenants/{tenant_id}/validate** - Tenant Validation
Validate tenant UUID format and existence.

**Response**:
```json
{
  "tenant_id": "uuid",
  "valid": true,
  "exists": true,
  "validated_at": "2024-01-01T12:00:00Z"
}
```

## Data Models

### Core Models

**TenantType Enum**:
```python
ENTERPRISE = "enterprise"      # Large enterprise customers
SMB = "smb"                   # Small/medium business
STARTUP = "startup"           # Startup companies
NON_PROFIT = "non_profit"     # Non-profit organizations
GOVERNMENT = "government"     # Government agencies
EDUCATION = "education"       # Educational institutions
HEALTHCARE = "healthcare"     # Healthcare organizations
FINANCIAL = "financial"       # Financial services
```

**TenantStatus Enum**:
```python
ACTIVE = "active"             # Fully operational
INACTIVE = "inactive"         # Temporarily disabled
SUSPENDED = "suspended"       # Suspended for violation
DECOMMISSIONED = "decommissioned"  # Permanently removed
```

### Request/Response Models

All models include comprehensive field validation:
- **Email validation**: RFC-compliant email format checking
- **UUID validation**: Proper UUID v4 format for tenant IDs
- **Range validation**: Numeric fields with appropriate min/max limits
- **Enum validation**: Strict enum value checking
- **Length validation**: String fields with appropriate length limits

## Authentication & Authorization

### Required Permissions

| Operation | Required Role | Scope |
|-----------|---------------|-------|
| Create Tenant | `super_admin`, `admin` | Platform |
| List Tenants | `super_admin`, `admin`, `support_admin` | Platform |
| Get Tenant Stats | `super_admin`, `admin`, `billing_admin` | Platform |
| Get/Update Tenant | `super_admin`, `admin`, `tenant_admin` | Platform or Tenant |
| Decommission Tenant | `super_admin`, `admin` | Platform |
| Storage Operations | `super_admin`, `admin`, `tenant_admin` | Platform or Tenant |
| Usage/Billing | `super_admin`, `admin`, `billing_admin`, `tenant_admin` | Platform or Tenant |
| Configuration | `super_admin`, `admin`, `tenant_admin` | Platform or Tenant |
| Compliance | `super_admin`, `admin`, `compliance_officer` | Platform or Tenant |
| Health/Monitoring | `super_admin`, `admin`, `tenant_admin`, `devops_engineer` | Platform or Tenant |

### Multi-Tenant Isolation

- **Database Level**: All queries filtered by tenant_id
- **API Level**: X-Customer-ID header validation
- **Service Level**: Tenant context propagated through all operations
- **Storage Level**: Tenant-specific storage namespaces

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **201 Created**: Tenant successfully created
- **400 Bad Request**: Invalid request data or validation failure
- **404 Not Found**: Tenant not found or decommissioned
- **500 Internal Server Error**: Server-side processing error

### Error Response Format

```json
{
  "detail": "Descriptive error message",
  "error_code": "TENANT_NOT_FOUND",
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "uuid"
}
```

### Common Errors

- **TENANT_NOT_FOUND**: Tenant UUID not found in database
- **TENANT_INACTIVE**: Tenant exists but is decommissioned/inactive
- **STORAGE_CONNECTION_FAILED**: Storage backend connectivity issues
- **QUOTA_EXCEEDED**: Resource usage exceeds allocated quotas
- **VALIDATION_ERROR**: Request data validation failure
- **INSUFFICIENT_PERMISSIONS**: User lacks required permissions

## Performance Characteristics

- **Tenant Creation**: ~200-500ms (includes UUID generation and database persistence)
- **Tenant Listing**: ~50-200ms (pagination optimized)
- **Tenant Stats**: ~10-50ms (lightweight aggregation)
- **Storage Operations**: ~100-2000ms (depends on backend latency)
- **Usage Analytics**: ~200-1000ms (complex aggregations)
- **Health Checks**: ~50-200ms (cached metrics)

## Integration Points

### External Systems

- **Storage Backends**: S3, GCS, Azure, MinIO, ClickHouse
- **Notification Systems**: SMTP, Slack, Webhook, PagerDuty
- **Compliance Frameworks**: SOX, GDPR, HIPAA, PCI-DSS
- **Monitoring Systems**: Prometheus, Grafana, DataDog

### Internal Dependencies

- **Authentication System**: User roles and permissions
- **Subscription System**: Feature access and billing
- **Alert System**: Tenant-specific alerting rules
- **Usage Tracking**: API call and resource usage monitoring
- **Audit System**: Complete operation logging

## Security Features

1. **UUID-based Identification**: Prevents tenant ID enumeration attacks
2. **Role-based Access Control**: Granular permission system
3. **Data Encryption**: At-rest and in-transit encryption
4. **Audit Logging**: Complete operation tracking
5. **Legal Hold**: Data preservation for compliance
6. **Secure Decommissioning**: Safe tenant data removal
7. **IP Whitelisting**: Network-level access control
8. **MFA Integration**: Multi-factor authentication support

## Best Practices

### For Platform Administrators

1. **Always verify tenant UUID format** before operations
2. **Use pagination** for tenant listing operations
3. **Monitor storage costs** through usage analytics
4. **Implement proper backup strategies** before decommissioning
5. **Regular compliance audits** for all tenants
6. **Monitor resource utilization** to prevent quota violations

### For Tenant Administrators

1. **Configure appropriate retention policies** for cost optimization
2. **Set up proactive monitoring** through health endpoints
3. **Regularly review usage patterns** for optimization opportunities
4. **Implement proper alert escalation** policies
5. **Maintain compliance** with relevant frameworks
6. **Regular security audits** of configurations

The Tenant API provides the foundational multi-tenant infrastructure for the entire Logforge platform, enabling secure, scalable, and compliant tenant lifecycle management with comprehensive observability and control capabilities.