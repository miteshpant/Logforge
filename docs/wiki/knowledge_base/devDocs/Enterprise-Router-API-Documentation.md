# Enterprise Router API Documentation

## Overview

The Enterprise Router provides 22 enterprise-grade endpoints for authentication, authorization, multi-tenancy, compliance, and integrations. This router enables enterprise customers to manage advanced features like OIDC authentication, RBAC permissions, tenant isolation, compliance reporting, and third-party integrations.

## Architecture

```
Request → Enterprise Router → Enterprise Service → Enterprise Engine → ClickHouse/External APIs
```

**Core Components:**
- **Router**: `/apps/api/routers/enterprise_api.py` - FastAPI endpoints with validation
- **Service**: `/apps/api/services/enterprise_service.py` - Business logic and orchestration (1400+ lines)
- **Engine**: `/apps/api/enterprise_engine.py` - Core enterprise functionality and testing
- **Database**: Multi-tenant ClickHouse tables for enterprise data

## API Endpoints

### Authentication & Authorization (6 endpoints)

#### 1. Configure OIDC Provider
**Endpoint**: `POST /v1/enterprise/auth/oidc/configure`

Configure OIDC authentication provider for enterprise SSO.

**Headers:**
- `X-Customer-ID`: Customer identifier
- `Content-Type`: application/json

**Request Body:**
```json
{
  "provider_name": "auth0-corporate",
  "provider_type": "auth0",
  "client_id": "abc123xyz789",
  "client_secret": "secret_key_here",
  "domain": "company.auth0.com",
  "scopes": ["openid", "profile", "email", "groups"],
  "enabled": true
}
```

**Response:**
```json
{
  "provider_id": "oidc_prov_123",
  "status": "configured",
  "discovery_url": "https://company.auth0.com/.well-known/openid_configuration",
  "client_id": "abc123xyz789",
  "enabled": true
}
```

**Implementation:**
```python
enterprise_service = EnterpriseService()
result = await enterprise_service.configure_oidc_provider(customer_id, request.model_dump())
```

#### 2. List Authentication Providers
**Endpoint**: `GET /v1/enterprise/auth/providers`

List all configured authentication providers for the customer.

**Response:**
```json
{
  "providers": [
    {
      "provider_id": "oidc_prov_123",
      "provider_name": "auth0-corporate",
      "provider_type": "auth0",
      "domain": "company.auth0.com",
      "enabled": true,
      "users_count": 150,
      "last_used": "2024-01-15T10:30:00Z"
    }
  ],
  "total_count": 1
}
```

#### 3. Generate API Key
**Endpoint**: `POST /v1/enterprise/auth/api-keys`

Generate scoped API key for service integration.

**Request Body:**
```json
{
  "name": "monitoring-service",
  "description": "API key for Grafana monitoring integration",
  "permissions": ["logs:read", "metrics:read", "dashboards:read"],
  "expires_at": "2024-12-31T23:59:59Z",
  "rate_limit": 1000,
  "ip_whitelist": ["10.0.1.0/24", "192.168.1.100"]
}
```

**Response:**
```json
{
  "key_id": "api_key_456",
  "api_key": "lf_ak_abc123...",
  "name": "monitoring-service",
  "permissions": ["logs:read", "metrics:read", "dashboards:read"],
  "rate_limit": 1000,
  "expires_at": "2024-12-31T23:59:59Z",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 4. List API Keys
**Endpoint**: `GET /v1/enterprise/auth/api-keys`

List all API keys for the tenant.

**Response:**
```json
{
  "api_keys": [
    {
      "key_id": "api_key_456",
      "name": "monitoring-service",
      "permissions": ["logs:read", "metrics:read"],
      "rate_limit": 1000,
      "expires_at": "2024-12-31T23:59:59Z",
      "last_used": "2024-01-15T09:45:00Z",
      "usage_count": 1547,
      "status": "active"
    }
  ],
  "total_count": 1
}
```

#### 5. Revoke API Key
**Endpoint**: `DELETE /v1/enterprise/auth/api-keys/{key_id}`

Revoke an active API key.

**Path Parameters:**
- `key_id`: API key identifier

**Response:**
```json
{
  "key_id": "api_key_456",
  "status": "revoked",
  "revoked_at": "2024-01-15T10:30:00Z"
}
```

#### 6. Setup Multi-Factor Authentication
**Endpoint**: `POST /v1/enterprise/auth/mfa/setup`

Setup Multi-Factor Authentication for a user.

**Request Body:**
```json
{
  "user_id": "user_123",
  "mfa_type": "totp",
  "backup_codes": true,
  "phone_number": "+1-555-123-4567"
}
```

**Response:**
```json
{
  "mfa_id": "mfa_789",
  "user_id": "user_123",
  "mfa_type": "totp",
  "secret_key": "JBSWY3DPEHPK3PXP",
  "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "backup_codes": ["12345678", "87654321", "11223344"],
  "status": "pending_verification"
}
```

### RBAC & Permissions (4 endpoints)

#### 7. List Roles
**Endpoint**: `GET /v1/enterprise/rbac/roles`

List all available roles and permissions.

**Response:**
```json
{
  "platform_roles": [
    {
      "role_name": "super_admin",
      "description": "Full platform administration",
      "permissions": ["*:*:*"],
      "user_count": 2
    }
  ],
  "tenant_roles": [
    {
      "role_name": "tenant_admin",
      "description": "Full tenant administration",
      "permissions": ["tenant:*:*", "users:*:own_tenant"],
      "user_count": 15
    },
    {
      "role_name": "security_analyst",
      "description": "Security operations and analysis",
      "permissions": ["logs:read:*", "alerts:*:*", "security:*:*"],
      "user_count": 25
    }
  ]
}
```

#### 8. Create Custom Role
**Endpoint**: `POST /v1/enterprise/rbac/roles`

Create custom role with specific permissions.

**Request Body:**
```json
{
  "name": "compliance_officer",
  "description": "Compliance reporting and audit access",
  "permissions": [
    "compliance:read:*",
    "audit:read:*",
    "reports:create:compliance",
    "legal_hold:*:*"
  ],
  "inherits_from": "viewer"
}
```

**Response:**
```json
{
  "role_id": "role_comp_123",
  "name": "compliance_officer",
  "description": "Compliance reporting and audit access",
  "permissions": [
    "compliance:read:*",
    "audit:read:*",
    "reports:create:compliance",
    "legal_hold:*:*",
    "logs:read:*"
  ],
  "inherits_from": "viewer",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### 9. Assign User Roles
**Endpoint**: `PUT /v1/enterprise/rbac/users/{user_id}/roles`

Assign roles to a user.

**Path Parameters:**
- `user_id`: User identifier

**Request Body:**
```json
{
  "roles": ["security_analyst", "compliance_officer"],
  "effective_date": "2024-01-15T00:00:00Z"
}
```

**Response:**
```json
{
  "user_id": "user_123",
  "assigned_roles": [
    {
      "role_name": "security_analyst",
      "assigned_at": "2024-01-15T10:30:00Z",
      "effective_date": "2024-01-15T00:00:00Z"
    },
    {
      "role_name": "compliance_officer", 
      "assigned_at": "2024-01-15T10:30:00Z",
      "effective_date": "2024-01-15T00:00:00Z"
    }
  ],
  "effective_permissions": [
    "logs:read:*",
    "alerts:*:*",
    "security:*:*",
    "compliance:read:*",
    "audit:read:*"
  ]
}
```

#### 10. Get User Permissions
**Endpoint**: `GET /v1/enterprise/rbac/permissions`

Get effective permissions for current user.

**Response:**
```json
{
  "user_id": "user_123",
  "tenant_id": "tenant_456",
  "roles": ["security_analyst", "compliance_officer"],
  "permissions": [
    {
      "resource": "logs",
      "actions": ["read"],
      "scope": "*"
    },
    {
      "resource": "alerts",
      "actions": ["create", "read", "update", "delete"],
      "scope": "*"
    },
    {
      "resource": "security",
      "actions": ["*"],
      "scope": "*"
    }
  ],
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### Multi-Tenancy & Compliance (6 endpoints)

#### 11. List Tenants
**Endpoint**: `GET /v1/enterprise/tenants`

List all customer tenants.

**Response:**
```json
{
  "tenants": [
    {
      "tenant_id": "tenant_123",
      "name": "Acme Corporation",
      "tier": "enterprise",
      "data_residency": "us-east-1",
      "compliance_requirements": ["SOX", "PCI-DSS"],
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "user_count": 150,
      "storage_used_gb": 1024.5
    }
  ],
  "total_count": 1
}
```

#### 12. Create Tenant
**Endpoint**: `POST /v1/enterprise/tenants`

Create new customer tenant.

**Request Body:**
```json
{
  "tenant_id": "tenant_newco",
  "name": "NewCo Enterprises",
  "tier": "professional", 
  "data_residency": "eu-west-1",
  "compliance_requirements": ["GDPR", "ISO27001"],
  "retention_policy": {
    "hot_data_days": 30,
    "warm_data_days": 90,
    "cold_data_days": 365
  },
  "resource_limits": {
    "max_users": 100,
    "max_storage_gb": 500,
    "max_api_calls_per_hour": 10000
  }
}
```

**Response:**
```json
{
  "tenant_id": "tenant_newco",
  "name": "NewCo Enterprises",
  "tier": "professional",
  "data_residency": "eu-west-1",
  "compliance_requirements": ["GDPR", "ISO27001"],
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "admin_user_id": "user_admin_456",
  "setup_completed": false
}
```

#### 13. Update Tenant Settings
**Endpoint**: `PUT /v1/enterprise/tenants/{tenant_id}/settings`

Update tenant configuration and settings.

**Path Parameters:**
- `tenant_id`: Tenant identifier

**Request Body:**
```json
{
  "data_residency": "eu-central-1",
  "compliance_requirements": ["GDPR", "ISO27001", "SOC2"],
  "retention_policy": {
    "hot_data_days": 60,
    "warm_data_days": 180,
    "cold_data_days": 2555
  },
  "security_settings": {
    "mfa_required": true,
    "session_timeout_minutes": 480,
    "password_policy": "enterprise"
  }
}
```

**Response:**
```json
{
  "tenant_id": "tenant_newco",
  "updated_settings": {
    "data_residency": {
      "old": "eu-west-1",
      "new": "eu-central-1"
    },
    "compliance_requirements": {
      "added": ["SOC2"],
      "removed": []
    },
    "retention_policy": {
      "updated": true
    }
  },
  "updated_at": "2024-01-15T10:30:00Z",
  "migration_required": true
}
```

#### 14. Generate Compliance Report
**Endpoint**: `GET /v1/enterprise/compliance/reports`

Generate automated compliance report.

**Query Parameters:**
- `compliance_framework`: SOX, GDPR, PCI-DSS, HIPAA, etc.
- `period_start`: Report period start (ISO datetime)
- `period_end`: Report period end (ISO datetime)
- `sections[]`: Report sections to include

**Example:**
```
GET /v1/enterprise/compliance/reports?compliance_framework=SOX&period_start=2024-01-01T00:00:00Z&period_end=2024-01-31T23:59:59Z&sections=access_controls&sections=audit_trail
```

**Response:**
```json
{
  "report_id": "comp_report_789",
  "compliance_framework": "SOX",
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "sections": {
    "access_controls": {
      "status": "compliant",
      "findings": [],
      "metrics": {
        "privileged_access_reviews": 4,
        "access_violations": 0,
        "mfa_coverage": "100%"
      }
    },
    "audit_trail": {
      "status": "compliant", 
      "findings": [],
      "metrics": {
        "audit_events_captured": 15750,
        "data_integrity_checks": 31,
        "retention_compliance": "100%"
      }
    }
  },
  "overall_status": "compliant",
  "generated_at": "2024-01-15T10:30:00Z"
}
```

#### 15. Create Legal Hold
**Endpoint**: `POST /v1/enterprise/compliance/legal-hold`

Create legal hold for data preservation.

**Request Body:**
```json
{
  "case_id": "legal_case_2024_001",
  "custodian": "legal@company.com",
  "reason": "Employment litigation discovery",
  "date_range": {
    "start": "2023-06-01T00:00:00Z",
    "end": "2024-01-15T23:59:59Z"
  },
  "scope": {
    "user_ids": ["user_123", "user_456"],
    "data_types": ["logs", "emails", "audit_trails"],
    "keywords": ["confidential", "termination", "performance"]
  }
}
```

**Response:**
```json
{
  "legal_hold_id": "lh_789",
  "case_id": "legal_case_2024_001",
  "status": "active",
  "custodian": "legal@company.com", 
  "scope": {
    "estimated_records": 45000,
    "estimated_size_gb": 2.3,
    "affected_users": 2
  },
  "preservation_started": "2024-01-15T10:30:00Z",
  "expiration_date": null
}
```

#### 16. Get Audit Logs
**Endpoint**: `GET /v1/enterprise/audit-logs`

Retrieve audit logs with filtering.

**Query Parameters:**
- `start_time`: Start time filter (ISO datetime)
- `end_time`: End time filter (ISO datetime)
- `user_id`: User ID filter
- `action_types[]`: Action type filters

**Example:**
```
GET /v1/enterprise/audit-logs?start_time=2024-01-15T00:00:00Z&user_id=user_123&action_types=login&action_types=data_access
```

**Response:**
```json
{
  "audit_events": [
    {
      "event_id": "audit_001",
      "timestamp": "2024-01-15T10:30:00Z",
      "user_id": "user_123",
      "action_type": "login",
      "resource": "auth_system",
      "details": {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0...",
        "mfa_used": true,
        "success": true
      },
      "risk_level": "low"
    },
    {
      "event_id": "audit_002", 
      "timestamp": "2024-01-15T10:31:00Z",
      "user_id": "user_123",
      "action_type": "data_access",
      "resource": "sensitive_logs",
      "details": {
        "query": "SELECT * FROM logs WHERE level='ERROR'",
        "records_accessed": 150,
        "data_classification": "confidential"
      },
      "risk_level": "medium"
    }
  ],
  "total_count": 2,
  "filtered_count": 2
}
```

### Enterprise Integration (3 endpoints)

#### 17. List Integrations
**Endpoint**: `GET /v1/enterprise/integrations`

List all available enterprise integrations.

**Response:**
```json
{
  "integrations": [
    {
      "integration_type": "slack",
      "name": "Slack Notifications",
      "status": "active",
      "configured": true,
      "last_used": "2024-01-15T09:45:00Z",
      "health_status": "healthy",
      "configuration": {
        "webhook_url": "https://hooks.slack.com/...",
        "channel": "#security-alerts",
        "notification_types": ["security_alerts", "compliance_reports"]
      }
    },
    {
      "integration_type": "servicenow",
      "name": "ServiceNow ITSM",
      "status": "active", 
      "configured": true,
      "last_used": "2024-01-15T08:30:00Z",
      "health_status": "healthy"
    }
  ],
  "available_integrations": [
    "slack", "servicenow", "jira", "pagerduty", "teams", "webhook"
  ]
}
```

#### 18. Configure Integration
**Endpoint**: `POST /v1/enterprise/integrations/{integration_type}/configure`

Configure enterprise integration.

**Path Parameters:**
- `integration_type`: Type of integration (slack, servicenow, jira, etc.)

**Request Body (Slack example):**
```json
{
  "enabled": true,
  "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
  "channel": "#security-alerts",
  "bot_token": "xoxb-000000000000-000000000000-XXXXXXXXXXXXXXXXXXXXXXXX",
  "notification_types": ["security_alerts", "compliance_reports", "system_alerts"]
}
```

**Response:**
```json
{
  "integration_type": "slack",
  "status": "configured",
  "configuration": {
    "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
    "channel": "#security-alerts",
    "notification_types": ["security_alerts", "compliance_reports", "system_alerts"]
  },
  "test_message_sent": true,
  "configured_at": "2024-01-15T10:30:00Z"
}
```

#### 19. Get Integration Health
**Endpoint**: `GET /v1/enterprise/integrations/{integration_type}/status`

Check integration health and connectivity.

**Path Parameters:**
- `integration_type`: Type of integration

**Response:**
```json
{
  "integration_type": "slack",
  "health_status": "healthy",
  "last_check": "2024-01-15T10:30:00Z",
  "connectivity": {
    "status": "connected",
    "response_time_ms": 245,
    "last_successful_message": "2024-01-15T09:45:00Z"
  },
  "metrics": {
    "messages_sent_24h": 15,
    "success_rate": "100%",
    "average_response_time_ms": 220
  },
  "issues": []
}
```

### Administration & Governance (3 endpoints)

#### 20. Get Usage Billing
**Endpoint**: `GET /v1/enterprise/usage/billing`

Get billing metrics and usage analytics.

**Query Parameters:**
- `period_start`: Billing period start (ISO datetime)
- `period_end`: Billing period end (ISO datetime)
- `breakdown[]`: Cost breakdown categories

**Example:**
```
GET /v1/enterprise/usage/billing?period_start=2024-01-01T00:00:00Z&period_end=2024-01-31T23:59:59Z&breakdown=storage&breakdown=ingestion&breakdown=queries
```

**Response:**
```json
{
  "billing_period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "total_cost": 12450.75,
  "currency": "USD",
  "breakdown": {
    "storage": {
      "cost": 5200.00,
      "usage": {
        "hot_storage_gb": 2048,
        "warm_storage_gb": 4096,
        "cold_storage_gb": 8192
      }
    },
    "ingestion": {
      "cost": 3750.25,
      "usage": {
        "events_ingested": 15750000,
        "gb_ingested": 1250.5
      }
    },
    "queries": {
      "cost": 2100.50,
      "usage": {
        "query_count": 45000,
        "compute_hours": 125.5
      }
    },
    "alerts": {
      "cost": 1400.00,
      "usage": {
        "alert_evaluations": 2500000,
        "notifications_sent": 850
      }
    }
  },
  "cost_trends": {
    "vs_previous_month": "+12.5%",
    "projected_next_month": 13200.00
  }
}
```

#### 21. Get Enterprise System Health
**Endpoint**: `GET /v1/enterprise/system/health`

Get enterprise system health and diagnostics.

**Response:**
```json
{
  "overall_health": "healthy",
  "last_check": "2024-01-15T10:30:00Z",
  "components": {
    "authentication": {
      "status": "healthy",
      "response_time_ms": 45,
      "success_rate": "99.95%",
      "active_sessions": 150
    },
    "authorization": {
      "status": "healthy",
      "response_time_ms": 12,
      "cache_hit_rate": "98.5%"
    },
    "integrations": {
      "status": "degraded",
      "healthy_count": 5,
      "total_count": 6,
      "failing": ["pagerduty"]
    },
    "compliance": {
      "status": "healthy",
      "audit_backlog": 0,
      "retention_compliance": "100%"
    }
  },
  "performance_metrics": {
    "api_response_time_p95_ms": 850,
    "throughput_requests_per_second": 1250,
    "error_rate": "0.05%"
  },
  "resource_usage": {
    "cpu_utilization": "45%",
    "memory_utilization": "62%",
    "storage_utilization": "78%"
  }
}
```

#### 22. Configure Backup Policy
**Endpoint**: `POST /v1/enterprise/backup/configure`

Configure backup and disaster recovery policies.

**Request Body:**
```json
{
  "policy_name": "enterprise_backup_policy",
  "schedule": "daily",
  "retention_days": 90,
  "storage_location": "s3://backup-bucket/enterprise-backups",
  "encryption": true,
  "compression": true,
  "components": [
    "user_data",
    "configuration",
    "audit_logs",
    "security_events",
    "compliance_data"
  ],
  "disaster_recovery": {
    "rpo_hours": 4,
    "rto_hours": 2,
    "cross_region_replication": true,
    "automated_testing": true
  }
}
```

**Response:**
```json
{
  "policy_id": "backup_policy_789",
  "policy_name": "enterprise_backup_policy",
  "status": "active",
  "schedule": "daily",
  "next_backup": "2024-01-16T02:00:00Z",
  "retention_days": 90,
  "estimated_backup_size_gb": 45.2,
  "disaster_recovery": {
    "rpo_hours": 4,
    "rto_hours": 2,
    "cross_region_replication": true,
    "last_dr_test": "2024-01-01T12:00:00Z",
    "dr_test_result": "successful"
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Enterprise Metrics

#### 23. Get Enterprise Metrics
**Endpoint**: `GET /v1/enterprise/metrics`

Get enterprise-wide metrics and KPIs.

**Response:**
```json
{
  "metrics": {
    "authentication": {
      "total_users": 1247,
      "active_sessions": 156,
      "mfa_adoption_rate": "85%",
      "sso_usage_rate": "78%"
    },
    "authorization": {
      "total_roles": 15,
      "custom_roles": 8,
      "permission_violations_24h": 2
    },
    "compliance": {
      "frameworks_enabled": ["SOX", "GDPR", "PCI-DSS"],
      "compliance_score": "98%",
      "audit_events_24h": 15750,
      "legal_holds_active": 2
    },
    "integrations": {
      "total_integrations": 6,
      "healthy_integrations": 5,
      "messages_sent_24h": 145,
      "integration_uptime": "99.5%"
    },
    "tenants": {
      "total_tenants": 45,
      "enterprise_tier": 12,
      "professional_tier": 28,
      "starter_tier": 5
    }
  },
  "generated_at": "2024-01-15T10:30:00Z"
}
```

### Health Check

#### Enterprise Health Check
**Endpoint**: `GET /v1/enterprise/health`

Enterprise module health check.

**Response:**
```json
{
  "status": "healthy",
  "module": "enterprise",
  "version": "1.0.0",
  "features": [
    "authentication",
    "authorization", 
    "rbac",
    "multi_tenancy",
    "compliance",
    "integrations",
    "governance"
  ],
  "endpoints_count": 22,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Authentication & Headers

All enterprise endpoints require authentication via Bearer token and customer identification:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id>
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `201`: Created successfully
- `400`: Bad request (validation error)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Resource not found
- `409`: Conflict (resource already exists)
- `422`: Unprocessable entity (validation failed)
- `500`: Internal server error

**Error Response Format:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid OIDC configuration",
    "details": {
      "field": "client_secret",
      "reason": "Client secret is required for confidential clients"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Code Integration

### Service Layer Integration

```python
from services.enterprise_service import EnterpriseService

# Initialize service
enterprise_service = EnterpriseService()

# Configure OIDC provider
oidc_config = {
    "provider_name": "auth0-corporate",
    "provider_type": "auth0", 
    "client_id": "abc123",
    "domain": "company.auth0.com"
}
result = await enterprise_service.configure_oidc_provider(customer_id, oidc_config)

# Generate API key
api_key_request = {
    "name": "monitoring-service",
    "permissions": ["logs:read", "metrics:read"],
    "rate_limit": 1000
}
api_key = await enterprise_service.generate_api_key(customer_id, api_key_request)

# Create compliance report
report = await enterprise_service.generate_compliance_report(
    customer_id, 
    "SOX", 
    start_date, 
    end_date, 
    ["access_controls", "audit_trail"]
)
```

### Database Schema

**Key Enterprise Tables:**
- `enterprise_providers_mt`: OIDC provider configurations
- `enterprise_api_keys_mt`: API key management  
- `enterprise_roles_mt`: Custom role definitions
- `enterprise_user_roles_mt`: User role assignments
- `enterprise_audit_logs_mt`: Audit trail events
- `enterprise_legal_holds_mt`: Legal hold records
- `enterprise_integrations_mt`: Integration configurations
- `enterprise_backup_policies_mt`: Backup and DR policies

## Performance Characteristics

- **Authentication Response Time**: < 100ms (includes OIDC validation)
- **RBAC Permission Check**: < 10ms (cached permissions)
- **Compliance Report Generation**: < 30s (for 1M audit events)
- **API Key Operations**: < 50ms
- **Integration Health Checks**: < 5s (parallel execution)
- **Audit Log Queries**: < 2s (for 24h window)

## Security Considerations

- **OIDC Secrets**: Encrypted at rest using AES-256
- **API Keys**: Hashed using bcrypt with 12 rounds
- **Audit Integrity**: Immutable audit logs with cryptographic signatures
- **Multi-Tenant Isolation**: Complete data separation via tenant_id
- **Rate Limiting**: Per-tenant and per-API-key rate limits
- **Permission Validation**: Real-time permission checks on every request

## Enterprise Integration Examples

### Slack Integration
```python
# Configure Slack
slack_config = {
    "enabled": True,
    "webhook_url": "https://hooks.slack.com/...",
    "channel": "#security-alerts",
    "notification_types": ["security_alerts", "compliance_reports"]
}
await enterprise_service.configure_integration(customer_id, "slack", slack_config)

# Send test notification
health = await enterprise_service.get_integration_health(customer_id, "slack")
```

### RBAC Management
```python
# Create custom role
role_config = {
    "name": "compliance_officer",
    "description": "Compliance and audit access",
    "permissions": ["compliance:*:*", "audit:read:*"],
    "inherits_from": "viewer"
}
role = await enterprise_service.create_custom_role(customer_id, role_config)

# Assign role to user
await enterprise_service.assign_user_roles(customer_id, user_id, ["compliance_officer"])
```

### Compliance Automation
```python
# Generate SOX compliance report
report = await enterprise_service.generate_compliance_report(
    customer_id,
    "SOX",
    datetime(2024, 1, 1),
    datetime(2024, 1, 31),
    ["access_controls", "audit_trail", "data_integrity"]
)

# Create legal hold
legal_hold = {
    "case_id": "case_2024_001",
    "custodian": "legal@company.com",
    "reason": "Employment litigation",
    "date_range": {"start": "2023-06-01", "end": "2024-01-15"},
    "scope": {"user_ids": ["user_123"], "data_types": ["logs", "audit_trails"]}
}
hold = await enterprise_service.create_legal_hold(customer_id, legal_hold)
```

## Best Practices

1. **Authentication**: Always use OIDC for enterprise customers
2. **API Keys**: Scope API keys to minimum required permissions
3. **Role Management**: Use role inheritance to simplify permission management
4. **Audit Logging**: Enable comprehensive audit logging for compliance
5. **Integration Health**: Monitor integration health proactively
6. **Backup Testing**: Regularly test disaster recovery procedures
7. **Permission Reviews**: Conduct quarterly permission audits
8. **Compliance Monitoring**: Automate compliance report generation

## Related Documentation

- [Authentication & Authorization Guide](./Auth-Router-API-Documentation.md)
- [Multi-Tenant Architecture](../../../wiki/Multi-Tenant-Architecture.md)
- [Compliance Framework Guide](../../../wiki/Compliance-Framework-Guide.md)
- [Enterprise Integration Setup](../../../wiki/Enterprise-Integration-Setup.md)