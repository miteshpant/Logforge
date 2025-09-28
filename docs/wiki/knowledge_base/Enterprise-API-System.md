# Logforge Enterprise API System

## Overview

The Enterprise API (`/v1/enterprise`) provides comprehensive enterprise-readiness features including advanced authentication, role-based access control (RBAC), multi-tenant management, compliance automation, enterprise integrations, and governance capabilities. This system enables large organizations to meet security, compliance, and operational requirements at scale.

## Architecture

**Location**: `/apps/api/routers/enterprise_api.py`  
**Service**: `EnterpriseService` (dependency injection)  
**Authentication**: Required for all endpoints (except `/health`)  
**Multi-Tenancy**: `X-Customer-ID` header required for all authenticated endpoints  
**Subscription**: Requires `enterprise.*` features in subscription  

## Endpoint Categories

The Enterprise API provides **22 endpoints** organized into 5 functional categories:

1. **Authentication & Authorization** (6 endpoints) - OIDC, API keys, MFA
2. **RBAC & Permissions** (4 endpoints) - Custom roles, user assignments
3. **Multi-Tenancy & Compliance** (6 endpoints) - Tenant management, audit logs
4. **Enterprise Integrations** (3 endpoints) - Third-party system integration
5. **Administration & Governance** (3 endpoints) - Billing, health, backup policies

## 1. Authentication & Authorization (6 endpoints)

### **POST /v1/enterprise/auth/oidc/configure** - Configure OIDC Provider
Configure enterprise-grade OIDC authentication providers.

**Request Model**: `OIDCConfigRequest`
```json
{
  "provider_name": "Corporate Auth0",
  "provider_type": "auth0",
  "client_id": "enterprise_client_123",
  "client_secret": "secret_encrypted_value",
  "domain": "company.auth0.com",
  "scopes": ["openid", "profile", "email", "groups"],
  "enabled": true
}
```

**Response**:
```json
{
  "provider_id": "uuid-generated",
  "status": "configured",
  "message": "OIDC provider successfully configured",
  "test_url": "https://company.auth0.com/authorize?client_id=enterprise_client_123...",
  "configuration_valid": true,
  "last_tested": "2024-01-01T12:00:00Z"
}
```

**Supported Provider Types**:
- **Auth0**: Enterprise identity platform
- **Keycloak**: Open-source identity management  
- **Azure AD**: Microsoft enterprise directory
- **Okta**: Enterprise identity service
- **Google Workspace**: Google enterprise SSO
- **SAML**: Generic SAML 2.0 providers

### **GET /v1/enterprise/auth/providers** - List Authentication Providers
List all configured authentication providers with status.

**Response**:
```json
{
  "providers": [
    {
      "provider_id": "uuid",
      "provider_name": "Corporate Auth0",
      "provider_type": "auth0",
      "status": "active",
      "enabled": true,
      "last_sync": "2024-01-01T12:00:00Z",
      "user_count": 1250
    }
  ],
  "total": 3,
  "enabled_count": 2
}
```

### **POST /v1/enterprise/auth/api-keys** - Generate API Key
Generate scoped API keys for service-to-service authentication.

**Request Model**: `APIKeyRequest`
```json
{
  "name": "Production Integration Key",
  "description": "API key for production SIEM integration",
  "permissions": ["logs:read", "alerts:read", "dashboards:read"],
  "expires_at": "2025-01-01T00:00:00Z",
  "rate_limit": 10000,
  "ip_whitelist": ["192.168.1.0/24", "10.0.0.0/8"]
}
```

**Response**:
```json
{
  "key_id": "uuid-generated",
  "api_key": "lf_enterprise_abc123def456...",
  "name": "Production Integration Key",
  "permissions": ["logs:read", "alerts:read", "dashboards:read"],
  "expires_at": "2025-01-01T00:00:00Z",
  "created_at": "2024-01-01T12:00:00Z",
  "warning": "Store this key securely. It will not be shown again."
}
```

**API Key Features**:
- **Scoped Permissions**: Granular resource:action permissions
- **Rate Limiting**: Configurable requests per hour limits
- **IP Whitelisting**: Network-level access control
- **Expiration Dates**: Automatic key expiry for security
- **Audit Logging**: Complete API key usage tracking

### **GET /v1/enterprise/auth/api-keys** - List API Keys
List all API keys for the tenant with usage statistics.

**Response**:
```json
{
  "api_keys": [
    {
      "key_id": "uuid",
      "name": "Production Integration Key",
      "permissions": ["logs:read", "alerts:read"],
      "status": "active",
      "created_at": "2024-01-01T12:00:00Z",
      "expires_at": "2025-01-01T00:00:00Z",
      "last_used": "2024-01-01T11:45:00Z",
      "usage_stats": {
        "requests_last_hour": 245,
        "requests_last_day": 5890,
        "rate_limit": 10000
      }
    }
  ],
  "total": 5,
  "active_count": 4
}
```

### **DELETE /v1/enterprise/auth/api-keys/{key_id}** - Revoke API Key
Immediately revoke an API key for security.

**Response**:
```json
{
  "key_id": "uuid",
  "status": "revoked",
  "revoked_at": "2024-01-01T12:00:00Z",
  "message": "API key has been permanently revoked"
}
```

### **POST /v1/enterprise/auth/mfa/setup** - Setup Multi-Factor Authentication
Configure MFA for enhanced security.

**Request Model**: `MFASetupRequest`
```json
{
  "user_id": "user-uuid",
  "mfa_type": "totp",
  "backup_codes": true,
  "phone_number": "+1-555-0123"
}
```

**Response**:
```json
{
  "mfa_id": "uuid-generated",
  "mfa_type": "totp",
  "status": "configured",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "secret_key": "JBSWY3DPEHPK3PXP",
  "backup_codes": ["123456", "789012", "345678"],
  "setup_url": "otpauth://totp/Logforge:user@company.com?secret=JBSWY3DPEHPK3PXP"
}
```

**MFA Types Supported**:
- **TOTP**: Time-based one-time passwords (Google Authenticator, Authy)
- **SMS**: SMS-based verification codes
- **Hardware**: FIDO2/WebAuthn hardware keys
- **Push**: Mobile app push notifications

## 2. RBAC & Permissions (4 endpoints)

### **GET /v1/enterprise/rbac/roles** - List Roles
List all available roles and their permissions.

**Response**:
```json
{
  "platform_roles": [
    {
      "role_name": "super_admin",
      "description": "Full platform administration",
      "permissions": ["*"],
      "scope": "platform",
      "user_count": 3
    }
  ],
  "tenant_roles": [
    {
      "role_name": "tenant_admin",
      "description": "Full tenant administration",
      "permissions": ["tenant:*", "users:*", "logs:*"],
      "scope": "tenant",
      "user_count": 25
    }
  ],
  "custom_roles": [
    {
      "role_name": "security_analyst_custom",
      "description": "Custom security analyst role",
      "permissions": ["security:read", "alerts:write", "investigations:*"],
      "scope": "tenant",
      "created_by": "admin@company.com",
      "user_count": 8
    }
  ],
  "total_roles": 15
}
```

**Built-in Roles**:
- **Platform Roles**: `super_admin`, `admin`, `support_admin`, `billing_admin`
- **Tenant Roles**: `tenant_admin`, `security_analyst`, `devops_engineer`, `compliance_officer`, `viewer`

### **POST /v1/enterprise/rbac/roles** - Create Custom Role
Create custom roles with specific permissions.

**Request Model**: `CustomRoleRequest`
```json
{
  "name": "SOC_Analyst_L2",
  "description": "Level 2 Security Operations Center Analyst",
  "permissions": [
    "security:read", "security:write", 
    "alerts:read", "alerts:write", "alerts:ack",
    "investigations:read", "investigations:write",
    "dashboards:read", "reports:read"
  ],
  "inherits_from": "security_analyst"
}
```

**Response**:
```json
{
  "role_id": "uuid-generated",
  "role_name": "SOC_Analyst_L2",
  "status": "created",
  "effective_permissions": [
    "security:read", "security:write",
    "alerts:read", "alerts:write", "alerts:ack",
    "investigations:read", "investigations:write",
    "dashboards:read", "reports:read",
    "logs:read"
  ],
  "inherited_permissions": ["logs:read"],
  "created_at": "2024-01-01T12:00:00Z"
}
```

### **PUT /v1/enterprise/rbac/users/{user_id}/roles** - Assign User Roles
Assign multiple roles to a user with effective dates.

**Request Model**: `UserRoleAssignment`
```json
{
  "roles": ["SOC_Analyst_L2", "compliance_officer"],
  "effective_date": "2024-01-15T00:00:00Z"
}
```

**Response**:
```json
{
  "user_id": "user-uuid",
  "status": "assigned",
  "assigned_roles": [
    {
      "role_name": "SOC_Analyst_L2",
      "effective_date": "2024-01-15T00:00:00Z",
      "expires_at": null
    },
    {
      "role_name": "compliance_officer", 
      "effective_date": "2024-01-15T00:00:00Z",
      "expires_at": null
    }
  ],
  "effective_permissions": [...],
  "assigned_at": "2024-01-01T12:00:00Z"
}
```

### **GET /v1/enterprise/rbac/permissions** - Get User Permissions
Get effective permissions for the current user.

**Response**:
```json
{
  "user_id": "user-uuid",
  "user_email": "analyst@company.com",
  "effective_permissions": [
    "security:read", "security:write",
    "alerts:read", "alerts:write", "alerts:ack",
    "logs:read", "dashboards:read"
  ],
  "roles": [
    {
      "role_name": "SOC_Analyst_L2",
      "scope": "tenant",
      "assigned_date": "2024-01-15T00:00:00Z"
    }
  ],
  "scope": "tenant",
  "tenant_id": "tenant-uuid"
}
```

## 3. Multi-Tenancy & Compliance (6 endpoints)

### **GET /v1/enterprise/tenants** - List Enterprise Tenants
List all tenants managed by this enterprise customer.

**Response**:
```json
{
  "tenants": [
    {
      "tenant_id": "uuid",
      "name": "Production Environment", 
      "tier": "enterprise",
      "status": "active",
      "data_residency": "us-east-1",
      "compliance_requirements": ["SOX", "GDPR"],
      "created_at": "2024-01-01T00:00:00Z",
      "user_count": 125,
      "monthly_cost": 15420.50
    }
  ],
  "total": 8,
  "active_count": 7
}
```

### **POST /v1/enterprise/tenants** - Create Enterprise Tenant
Create new managed tenant with enterprise settings.

**Request Model**: `TenantRequest`
```json
{
  "tenant_id": "dev-environment-001",
  "name": "Development Environment",
  "tier": "enterprise",
  "data_residency": "us-west-2", 
  "compliance_requirements": ["SOX", "GDPR", "HIPAA"],
  "retention_policy": {
    "logs": 2555,
    "alerts": 1095,
    "audit_logs": 2555
  },
  "resource_limits": {
    "max_users": 50,
    "max_storage_gb": 1000,
    "max_ingestion_gb_per_day": 100
  }
}
```

**Response**:
```json
{
  "tenant_id": "uuid-generated",
  "status": "created",
  "message": "Enterprise tenant created successfully",
  "tier": "enterprise", 
  "quota_limits": {
    "storage_gb": 1000,
    "users": 50,
    "ingestion_gb_per_day": 100
  },
  "compliance_configuration": {
    "frameworks": ["SOX", "GDPR", "HIPAA"],
    "audit_enabled": true,
    "encryption_required": true
  }
}
```

### **PUT /v1/enterprise/tenants/{tenant_id}/settings** - Update Tenant Settings
Update enterprise tenant configuration.

**Request Model**: `TenantSettingsUpdate`
```json
{
  "data_residency": "eu-central-1",
  "compliance_requirements": ["GDPR", "ISO27001"],
  "retention_policy": {
    "logs": 2190,
    "audit_logs": 3650
  },
  "security_settings": {
    "mfa_required": true,
    "session_timeout": 4,
    "ip_whitelist_required": true
  }
}
```

**Response**:
```json
{
  "tenant_id": "uuid",
  "status": "updated",
  "message": "Tenant settings updated successfully",
  "updated_settings": {
    "data_residency": "eu-central-1",
    "compliance_requirements": ["GDPR", "ISO27001"],
    "security_settings": {
      "mfa_required": true,
      "session_timeout": 4
    }
  },
  "compliance_impact": {
    "new_requirements": ["ISO27001"],
    "certification_required": true
  }
}
```

### **GET /v1/enterprise/compliance/reports** - Generate Compliance Report
Generate automated compliance reports for various frameworks.

**Query Parameters**:
- `compliance_framework`: Framework name (SOX, GDPR, HIPAA, PCI-DSS, ISO27001)
- `period_start`: Report period start (ISO datetime)
- `period_end`: Report period end (ISO datetime)
- `sections`: Report sections to include

**Response**:
```json
{
  "report": {
    "report_id": "uuid-generated",
    "framework": "SOX",
    "period": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-31T23:59:59Z"
    },
    "compliance_score": 94.2,
    "sections": {
      "access_controls": {
        "score": 96.5,
        "status": "compliant",
        "findings": 2,
        "critical_issues": 0
      },
      "audit_trail": {
        "score": 98.1,
        "status": "compliant", 
        "coverage": "100%",
        "retention_compliant": true
      },
      "data_integrity": {
        "score": 88.7,
        "status": "mostly_compliant",
        "findings": 5,
        "critical_issues": 1
      }
    },
    "findings": [
      {
        "finding_id": "F001",
        "severity": "medium",
        "control": "AC-2.4",
        "description": "Some user accounts lack proper approval workflow",
        "recommendation": "Implement formal user approval process"
      }
    ],
    "recommendations": [
      "Implement automated user provisioning workflow",
      "Enable additional audit logging for financial data access",
      "Review and update data classification policies"
    ],
    "certification_status": "ready",
    "next_audit_date": "2024-06-01T00:00:00Z"
  },
  "status": "completed",
  "message": "SOX compliance report generated successfully"
}
```

**Supported Compliance Frameworks**:
- **SOX**: Sarbanes-Oxley Act financial compliance
- **GDPR**: European data protection regulation  
- **HIPAA**: Healthcare information privacy
- **PCI-DSS**: Payment card industry security
- **ISO27001**: Information security management
- **FedRAMP**: Federal cloud security requirements

### **POST /v1/enterprise/compliance/legal-hold** - Create Legal Hold
Create legal hold for data preservation.

**Request Model**: `LegalHoldRequest`
```json
{
  "case_id": "LITIGATION-2024-001",
  "custodian": "legal-team@company.com",
  "reason": "Patent litigation discovery order",
  "date_range": {
    "start": "2023-01-01T00:00:00Z",
    "end": "2024-12-31T23:59:59Z"
  },
  "scope": {
    "data_types": ["logs", "emails", "documents", "audit_records"],
    "users": ["john.doe@company.com", "jane.smith@company.com"],
    "systems": ["production", "staging"],
    "search_terms": ["patent", "invention", "IP"]
  }
}
```

**Response**:
```json
{
  "hold_id": "uuid-generated",
  "status": "created",
  "message": "Legal hold created and activated",
  "preservation_start": "2024-01-01T12:00:00Z",
  "scope": {
    "estimated_data_volume_gb": 245.7,
    "estimated_cost_per_month": 892.45,
    "affected_systems": ["production", "staging"],
    "affected_users": 2
  },
  "custodian_notifications": {
    "sent_to": ["legal-team@company.com"],
    "notification_date": "2024-01-01T12:00:00Z"
  },
  "compliance_status": "active"
}
```

### **GET /v1/enterprise/audit-logs** - Retrieve Audit Logs
Get comprehensive audit logs with advanced filtering.

**Query Parameters**:
- `start_time`: Filter start time (ISO datetime)
- `end_time`: Filter end time (ISO datetime)
- `user_id`: Filter by specific user
- `action_types`: Filter by action types (array)

**Response**:
```json
{
  "audit_logs": [
    {
      "log_id": "uuid",
      "timestamp": "2024-01-01T12:00:00Z",
      "user_id": "user-uuid",
      "user_email": "admin@company.com",
      "action_type": "user_create",
      "resource": "user:jane.doe@company.com",
      "details": {
        "target_user": "jane.doe@company.com",
        "assigned_roles": ["security_analyst"],
        "tenant_id": "tenant-uuid"
      },
      "ip_address": "192.168.1.100",
      "user_agent": "Logforge-Admin-UI/1.0",
      "result": "success",
      "compliance_tags": ["SOX", "GDPR"]
    }
  ],
  "total": 15420,
  "filtered_count": 234,
  "filters": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-01T23:59:59Z",
    "action_types": ["user_create", "user_delete"]
  },
  "retrieved_at": "2024-01-01T12:00:00Z"
}
```

**Audited Actions**:
- User management (create, update, delete, role changes)
- Authentication events (login, logout, MFA setup)
- Data access (query execution, log viewing, export)
- Configuration changes (tenant settings, integrations)
- Security events (API key creation, permission changes)

## 4. Enterprise Integrations (3 endpoints)

### **GET /v1/enterprise/integrations** - List Integrations
List available and configured enterprise integrations.

**Response**:
```json
{
  "configured_integrations": [
    {
      "integration_id": "uuid",
      "type": "slack",
      "name": "Corporate Slack",
      "status": "active",
      "health": "healthy",
      "configured_at": "2024-01-01T00:00:00Z",
      "last_used": "2024-01-01T11:45:00Z"
    }
  ],
  "available_integrations": [
    {
      "type": "servicenow",
      "name": "ServiceNow",
      "description": "ITSM and incident management",
      "features": ["incident_creation", "ticket_updates", "workflow_automation"],
      "status": "available"
    },
    {
      "type": "jira",
      "name": "Atlassian Jira",
      "description": "Issue tracking and project management",
      "features": ["issue_creation", "status_updates", "comment_sync"],
      "status": "available"
    }
  ],
  "total_configured": 3,
  "enabled_count": 2
}
```

**Supported Integrations**:
- **Slack**: Team communication and alerting
- **Microsoft Teams**: Enterprise communication platform
- **ServiceNow**: ITSM and incident management
- **Jira**: Issue tracking and project management
- **Splunk**: SIEM and log analysis integration
- **Elasticsearch**: Search and analytics platform
- **Webhook**: Generic HTTP webhook integration

### **POST /v1/enterprise/integrations/{integration_type}/configure** - Configure Integration
Configure enterprise integration with specific settings.

**Slack Integration Example**:
```json
{
  "name": "Production Alerts Channel",
  "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
  "channel": "#security-alerts",
  "bot_token": "xoxb-000000000000-000000000000-XXXXXXXXXXXXXXXXXXXXXXXX",
  "enabled": true,
  "notification_types": ["critical_alerts", "security_events", "compliance_violations"]
}
```

**Response**:
```json
{
  "integration_id": "uuid-generated",
  "status": "configured",
  "message": "Slack integration configured successfully",
  "health_check": {
    "connection": "successful",
    "authentication": "valid",
    "webhook_test": "passed",
    "channel_access": "confirmed"
  },
  "configuration": {
    "channel": "#security-alerts",
    "notification_types": ["critical_alerts", "security_events"],
    "rate_limit": "100/hour"
  }
}
```

### **GET /v1/enterprise/integrations/{integration_type}/status** - Integration Health
Check integration health and connectivity status.

**Response**:
```json
{
  "integration_type": "slack",
  "health_status": "healthy",
  "last_check": "2024-01-01T12:00:00Z",
  "check_details": {
    "connectivity": {
      "status": "healthy",
      "response_time_ms": 245,
      "last_successful": "2024-01-01T12:00:00Z"
    },
    "authentication": {
      "status": "healthy", 
      "token_valid": true,
      "expires_at": "2025-01-01T00:00:00Z"
    },
    "rate_limiting": {
      "status": "healthy",
      "current_usage": "45/100",
      "reset_at": "2024-01-01T13:00:00Z"
    }
  },
  "configuration_valid": true,
  "recent_activity": {
    "messages_sent_24h": 127,
    "errors_24h": 0,
    "last_message": "2024-01-01T11:45:00Z"
  }
}
```

## 5. Administration & Governance (3 endpoints)

### **GET /v1/enterprise/usage/billing** - Usage & Billing Analytics
Get comprehensive usage and billing analytics.

**Query Parameters**:
- `period_start`: Billing period start (ISO datetime)
- `period_end`: Billing period end (ISO datetime)  
- `breakdown`: Cost breakdown categories (array)

**Response**:
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "total_cost": 47589.32,
  "cost_breakdown": {
    "storage": {
      "amount": 12450.75,
      "percentage": 26.2,
      "details": {
        "hot_storage_gb": 2450,
        "warm_storage_gb": 5670,
        "cold_storage_gb": 12890
      }
    },
    "ingestion": {
      "amount": 18920.40,
      "percentage": 39.8,
      "details": {
        "events_processed": 125000000,
        "processing_cost": 15230.20,
        "parsing_cost": 3690.20
      }
    },
    "queries": {
      "amount": 9845.67,
      "percentage": 20.7,
      "details": {
        "query_count": 2450000,
        "compute_cost": 8234.50,
        "data_transfer_cost": 1611.17
      }
    },
    "alerts": {
      "amount": 6372.50,
      "percentage": 13.4,
      "details": {
        "alert_evaluations": 15600000,
        "notification_cost": 1245.75,
        "processing_cost": 5126.75
      }
    }
  },
  "usage_summary": {
    "total_data_ingested_gb": 15670,
    "total_queries": 2450000,
    "total_alerts_triggered": 8950,
    "average_daily_ingestion_gb": 505.5,
    "peak_ingestion_day": "2024-01-15",
    "peak_ingestion_gb": 892.3
  },
  "tenant_breakdown": [
    {
      "tenant_id": "uuid",
      "tenant_name": "Production",
      "cost": 35420.50,
      "percentage": 74.5,
      "usage": {
        "storage_gb": 18540,
        "queries": 1950000,
        "ingestion_gb": 12450
      }
    }
  ],
  "billing_details": {
    "currency": "USD",
    "billing_cycle": "monthly",
    "payment_method": "enterprise_contract",
    "discount_applied": 15.0,
    "taxes": 4758.93,
    "total_with_tax": 52348.25
  }
}
```

### **GET /v1/enterprise/system/health** - Enterprise System Health
Get comprehensive enterprise system health diagnostics.

**Response**:
```json
{
  "overall_status": "healthy",
  "uptime_percentage": 99.97,
  "health_check_timestamp": "2024-01-01T12:00:00Z",
  "components": {
    "authentication": {
      "status": "healthy",
      "oidc_providers": 3,
      "active_sessions": 1247,
      "failed_logins_24h": 12,
      "avg_response_time_ms": 85
    },
    "tenant_management": {
      "status": "healthy",
      "active_tenants": 8,
      "total_users": 2450,
      "tenant_isolation_tests": "passing",
      "cross_tenant_access_blocks": 0
    },
    "integrations": {
      "status": "warning",
      "active_integrations": 12,
      "healthy_integrations": 11,
      "failed_integrations": 1,
      "last_failure": "ServiceNow connection timeout"
    },
    "audit_logging": {
      "status": "healthy",
      "events_per_second": 450,
      "retention_compliance": "100%",
      "storage_utilization": "67.3%",
      "indexing_lag_seconds": 2.1
    }
  },
  "performance_metrics": {
    "avg_api_response_time_ms": 125,
    "p95_api_response_time_ms": 450,
    "throughput_requests_per_second": 2450,
    "error_rate_percentage": 0.02
  },
  "resource_utilization": {
    "cpu_usage_percentage": 72.4,
    "memory_usage_percentage": 68.9,
    "storage_usage_percentage": 45.2,
    "network_throughput_mbps": 1250
  }
}
```

### **POST /v1/enterprise/backup/configure** - Configure Backup Policy
Configure enterprise backup and disaster recovery policies.

**Request Model**: `BackupPolicyRequest`
```json
{
  "policy_name": "Enterprise Production Backup",
  "schedule": "daily",
  "retention_days": 2555,
  "storage_location": "s3://enterprise-backups/production/",
  "encryption": true,
  "compression": true,
  "components": [
    "tenant_configurations",
    "user_accounts_and_roles", 
    "audit_logs",
    "alert_rules",
    "dashboard_configurations",
    "integration_settings"
  ],
  "disaster_recovery": {
    "rto_hours": 4,
    "rpo_hours": 1,
    "backup_regions": ["us-east-1", "us-west-2", "eu-central-1"],
    "cross_region_replication": true,
    "automated_failover": true
  }
}
```

**Response**:
```json
{
  "policy": {
    "policy_id": "uuid-generated",
    "policy_name": "Enterprise Production Backup",
    "schedule": "daily at 02:00 UTC",
    "next_backup": "2024-01-02T02:00:00Z",
    "estimated_size_gb": 145.7,
    "estimated_cost_monthly": 892.45
  },
  "status": "configured",
  "message": "Backup policy configured successfully",
  "disaster_recovery": {
    "rto_target": "4 hours",
    "rpo_target": "1 hour", 
    "failover_regions": ["us-west-2", "eu-central-1"],
    "last_dr_test": "2023-12-15T10:00:00Z",
    "next_dr_test": "2024-03-15T10:00:00Z"
  },
  "compliance_impact": {
    "frameworks_supported": ["SOX", "GDPR", "HIPAA"],
    "retention_compliance": true,
    "encryption_compliance": true
  }
}
```

## 6. Enterprise Metrics & Health

### **GET /v1/enterprise/metrics** - Enterprise Metrics
Get enterprise-wide metrics and KPIs.

**Response**:
```json
{
  "operational_metrics": {
    "total_tenants": 8,
    "total_users": 2450,
    "total_data_tb": 47.2,
    "monthly_growth_percentage": 15.3,
    "system_uptime_percentage": 99.97
  },
  "security_metrics": {
    "failed_login_attempts_24h": 12,
    "mfa_adoption_percentage": 89.5,
    "api_key_usage_24h": 125000,
    "security_incidents_30d": 0,
    "compliance_score_average": 94.2
  },
  "performance_metrics": {
    "avg_query_response_time_ms": 850,
    "ingestion_rate_eps": 15420,
    "alert_evaluation_rate_per_minute": 125000,
    "api_throughput_rps": 2450,
    "error_rate_percentage": 0.02
  },
  "compliance_metrics": {
    "sox_compliance_score": 96.2,
    "gdpr_compliance_score": 92.1,
    "hipaa_compliance_score": 94.8,
    "audit_coverage_percentage": 100.0,
    "data_retention_compliance": true
  },
  "integration_metrics": {
    "active_integrations": 12,
    "integration_success_rate": 99.8,
    "notification_delivery_rate": 99.5,
    "webhook_success_rate": 98.9
  }
}
```

### **GET /v1/enterprise/health** - Enterprise Health Check
Simple health check endpoint (no authentication required).

**Response**:
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
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Authentication & Authorization

### Required Headers

**All authenticated endpoints require**:
- `Authorization: Bearer <jwt_token>` - Valid JWT token
- `X-Customer-ID: <tenant_id>` - Tenant context (UUID format)

### Permission Requirements

| Endpoint Category | Required Permissions | Role Examples |
|-------------------|---------------------|---------------|
| Auth Configuration | `enterprise.auth:admin` | `super_admin`, `admin` |
| RBAC Management | `enterprise.rbac:admin` | `super_admin`, `admin` |
| Tenant Management | `enterprise.tenants:admin` | `super_admin`, `admin` |
| Compliance | `enterprise.compliance:read/write` | `compliance_officer`, `admin` |
| Integrations | `enterprise.integrations:admin` | `admin`, `devops_engineer` |
| Governance | `enterprise.governance:read` | `admin`, `billing_admin` |

### Subscription Requirements

All endpoints require `enterprise.*` feature in tenant subscription:
```json
{
  "subscribed_features": [
    "enterprise.*",
    "ingestion.*", 
    "queries.*",
    "alerts.*",
    "security.*"
  ],
  "subscription_tier": "enterprise"
}
```

## Error Handling

### HTTP Status Codes

- **200 OK**: Successful operation
- **400 Bad Request**: Invalid request data
- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: Insufficient permissions or subscription
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server-side error

### Error Response Format

```json
{
  "error": "feature_not_subscribed",
  "message": "Enterprise RBAC features require enterprise subscription",
  "required_feature": "enterprise.rbac",
  "current_subscription": ["ingestion.*", "queries.*"],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Common Error Codes

- **subscription_not_found**: No active subscription
- **feature_not_subscribed**: Required enterprise feature not in subscription
- **invalid_tenant_uuid**: Tenant UUID format invalid
- **oidc_configuration_invalid**: OIDC provider configuration error
- **api_key_limit_exceeded**: Maximum API keys reached
- **role_permission_invalid**: Invalid permission specified
- **integration_connection_failed**: Integration connectivity error

## Security Features

1. **Advanced Authentication**: OIDC, SAML, MFA support
2. **Granular RBAC**: Custom roles with specific permissions
3. **API Key Management**: Scoped, time-limited service keys
4. **Audit Logging**: Complete operation tracking for compliance
5. **Multi-Tenant Isolation**: Strict data and access separation
6. **Compliance Automation**: Automated report generation
7. **Integration Security**: Secure external system connectivity
8. **Backup Encryption**: Encrypted backup and disaster recovery

## Best Practices

### For Enterprise Administrators

1. **Implement MFA** for all administrative accounts
2. **Use custom roles** for granular permission control
3. **Regular compliance audits** using automated reports
4. **Monitor integration health** proactively
5. **Configure proper backup policies** with DR testing
6. **Implement API key rotation** policies
7. **Review audit logs** regularly for security events

### For Security Teams

1. **Enable all compliance frameworks** relevant to organization
2. **Set up automated alerting** for security events
3. **Implement least-privilege access** with custom roles
4. **Regular security assessments** using enterprise metrics
5. **Maintain legal hold** procedures for litigation
6. **Monitor cross-tenant access** for isolation violations

The Enterprise API provides comprehensive enterprise-readiness capabilities enabling large organizations to deploy Logforge with confidence, meeting security, compliance, and operational requirements at scale.