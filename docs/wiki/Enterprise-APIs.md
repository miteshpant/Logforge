# Enterprise APIs

## Overview

The Enterprise APIs provide advanced features for large-scale deployments including RBAC (Role-Based Access Control), compliance automation, enterprise integrations, audit logging, and advanced authentication. These APIs are designed for enterprise customers requiring enhanced security, governance, and operational capabilities.

**Base Paths**: `/v1/enterprise`, `/v1/alerts`  
**Total Endpoints**: 35+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)  
**Required Roles**: `admin`, `compliance_officer`, or higher

## Enterprise System Health

### 1. Enterprise Health Check
```http
GET /v1/enterprise/health
```

**Description**: Get enterprise system health and feature status

**Authentication**: Required (admin role)

**Response** (200):
```json
{
  "status": "healthy",
  "enterprise_features": {
    "rbac": {
      "status": "active",
      "roles_configured": 15,
      "permissions_mapped": 128,
      "last_sync": "2024-01-20T15:30:00Z"
    },
    "audit_logging": {
      "status": "active",
      "events_24h": 12500,
      "retention_days": 2555,
      "storage_usage_gb": 45.6
    },
    "compliance": {
      "status": "active",
      "frameworks": ["SOX", "GDPR", "HIPAA", "PCI-DSS"],
      "last_report": "2024-01-20T00:00:00Z",
      "violations_open": 0
    },
    "integrations": {
      "status": "active",
      "active_integrations": 8,
      "failed_integrations": 0,
      "last_health_check": "2024-01-20T15:25:00Z"
    }
  },
  "licensing": {
    "plan": "Enterprise",
    "users_licensed": 500,
    "users_active": 347,
    "features_enabled": ["RBAC", "Audit", "Compliance", "SSO", "API_Keys"],
    "expires_at": "2025-01-20T00:00:00Z"
  }
}
```

### 2. System Health (Infrastructure)
```http
GET /v1/enterprise/system/health
```

**Description**: Get detailed system infrastructure health

**Authentication**: Required (admin role)

**Response** (200):
```json
{
  "overall_status": "healthy",
  "components": {
    "api_servers": {
      "status": "healthy",
      "instances": 3,
      "healthy_instances": 3,
      "avg_cpu_percent": 35.2,
      "avg_memory_percent": 68.5,
      "requests_per_second": 450
    },
    "database": {
      "status": "healthy",
      "cluster_size": 3,
      "replication_lag_ms": 12,
      "connection_pool_usage": 45,
      "slow_queries_count": 2
    },
    "storage": {
      "status": "healthy",
      "total_capacity_tb": 10.0,
      "used_capacity_tb": 4.2,
      "usage_percent": 42.0,
      "backup_status": "current"
    },
    "message_queue": {
      "status": "healthy",
      "queue_depth": 1250,
      "throughput_messages_per_second": 2100,
      "consumer_lag_seconds": 8
    }
  },
  "performance_metrics": {
    "api_response_time_p95_ms": 450,
    "database_query_time_p95_ms": 25,
    "storage_read_latency_ms": 12,
    "storage_write_latency_ms": 18
  }
}
```

## Role-Based Access Control (RBAC)

### 3. List RBAC Roles
```http
GET /v1/enterprise/rbac/roles
```

**Description**: List all RBAC roles with permissions

**Authentication**: Required (admin role)

**Query Parameters**:
- `include_permissions` (boolean, default: true): Include permission details
- `tenant_specific` (boolean, default: false): Include tenant-specific roles

**Response** (200):
```json
{
  "roles": [
    {
      "id": "role_001",
      "name": "super_admin",
      "display_name": "Super Administrator",
      "description": "Full platform access with all permissions",
      "type": "platform",
      "is_system": true,
      "user_count": 3,
      "permissions": [
        "platform:*",
        "tenants:*",
        "users:*",
        "rbac:*",
        "system:*"
      ],
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "role_002",
      "name": "tenant_admin",
      "display_name": "Tenant Administrator",
      "description": "Full tenant administration access",
      "type": "tenant",
      "is_system": true,
      "user_count": 25,
      "permissions": [
        "tenant:admin",
        "users:write",
        "dashboards:*",
        "alerts:*",
        "logs:*"
      ],
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "role_003",
      "name": "security_analyst",
      "display_name": "Security Analyst",
      "description": "Security operations and analysis",
      "type": "tenant",
      "is_system": true,
      "user_count": 45,
      "permissions": [
        "security:*",
        "logs:read",
        "dashboards:security:*",
        "alerts:security:*",
        "threat_intel:read"
      ]
    }
  ],
  "total": 15,
  "system_roles": 8,
  "custom_roles": 7
}
```

### 4. Create RBAC Role
```http
POST /v1/enterprise/rbac/roles
```

**Description**: Create custom RBAC role

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "name": "compliance_auditor",
  "display_name": "Compliance Auditor",
  "description": "Read-only access for compliance auditing",
  "type": "tenant",
  "permissions": [
    "audit_logs:read",
    "compliance:read",
    "reports:read",
    "logs:read",
    "users:read"
  ],
  "restrictions": {
    "time_based": {
      "allowed_hours": "09:00-17:00",
      "timezone": "America/New_York"
    },
    "ip_whitelist": ["192.168.1.0/24", "10.0.0.0/8"]
  }
}
```

**Response** (201):
```json
{
  "id": "role_016",
  "name": "compliance_auditor",
  "display_name": "Compliance Auditor",
  "created_at": "2024-01-20T17:00:00Z",
  "permissions_count": 5,
  "message": "RBAC role created successfully"
}
```

### 5. List User Permissions
```http
GET /v1/enterprise/rbac/permissions
```

**Description**: List all available permissions in the system

**Authentication**: Required (admin role)

**Query Parameters**:
- `category` (string, optional): Filter by permission category
- `resource` (string, optional): Filter by resource type

**Response** (200):
```json
{
  "permissions": [
    {
      "permission": "logs:read",
      "category": "data",
      "resource": "logs",
      "action": "read",
      "description": "Read access to log data",
      "requires_tenant_context": true
    },
    {
      "permission": "users:write",
      "category": "user_management",
      "resource": "users",
      "action": "write",
      "description": "Create and modify users",
      "requires_tenant_context": true
    },
    {
      "permission": "platform:admin",
      "category": "platform",
      "resource": "platform",
      "action": "admin",
      "description": "Platform administration access",
      "requires_tenant_context": false
    }
  ],
  "categories": [
    {"name": "data", "permission_count": 25},
    {"name": "user_management", "permission_count": 15},
    {"name": "security", "permission_count": 20},
    {"name": "platform", "permission_count": 10}
  ]
}
```

### 6. Assign User Roles
```http
POST /v1/enterprise/rbac/users/{user_id}/roles
```

**Description**: Assign RBAC roles to user

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "roles": ["security_analyst", "compliance_auditor"],
  "effective_date": "2024-01-21T00:00:00Z",
  "expires_at": "2024-12-31T23:59:59Z",
  "justification": "Assigned for Q1 security audit project"
}
```

**Response** (200):
```json
{
  "user_id": "user_123",
  "roles_assigned": ["security_analyst", "compliance_auditor"],
  "effective_permissions": [
    "security:read", "security:analyze", "audit_logs:read",
    "compliance:read", "logs:read", "reports:read"
  ],
  "assigned_at": "2024-01-20T17:15:00Z",
  "expires_at": "2024-12-31T23:59:59Z"
}
```

## Authentication & SSO

### 7. List Authentication Providers
```http
GET /v1/enterprise/auth/providers
```

**Description**: List configured authentication providers

**Authentication**: Required (admin role)

**Response** (200):
```json
{
  "providers": [
    {
      "id": "oidc_001",
      "type": "oidc",
      "name": "Corporate Azure AD",
      "enabled": true,
      "default": true,
      "configuration": {
        "issuer": "https://login.microsoftonline.com/tenant-id/v2.0",
        "client_id": "app-client-id",
        "scopes": ["openid", "profile", "email"],
        "user_mapping": {
          "email": "email",
          "first_name": "given_name",
          "last_name": "family_name"
        }
      },
      "statistics": {
        "users_count": 347,
        "last_login": "2024-01-20T16:45:00Z",
        "success_rate_24h": 0.998
      }
    },
    {
      "id": "local_001",
      "type": "local",
      "name": "Local Authentication",
      "enabled": true,
      "default": false,
      "statistics": {
        "users_count": 25,
        "last_login": "2024-01-20T15:30:00Z",
        "success_rate_24h": 1.0
      }
    }
  ],
  "mfa_enforcement": {
    "enabled": true,
    "required_roles": ["admin", "super_admin"],
    "optional_roles": ["analyst"]
  }
}
```

### 8. Configure OIDC Provider
```http
POST /v1/enterprise/auth/oidc/configure
```

**Description**: Configure OpenID Connect authentication provider

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "name": "Corporate Okta",
  "issuer": "https://company.okta.com",
  "client_id": "okta_client_id",
  "client_secret": "okta_client_secret",
  "scopes": ["openid", "profile", "email", "groups"],
  "user_mapping": {
    "email": "email",
    "first_name": "given_name",
    "last_name": "family_name",
    "groups": "groups"
  },
  "role_mapping": {
    "Logforge_Admins": "tenant_admin",
    "Logforge_Analysts": "security_analyst",
    "Logforge_Users": "user"
  },
  "enabled": true,
  "auto_provision_users": true
}
```

**Response** (200):
```json
{
  "provider_id": "oidc_002",
  "name": "Corporate Okta",
  "status": "configured",
  "test_url": "https://api.logforge.com/v1/auth/oidc/test/oidc_002",
  "callback_url": "https://api.logforge.com/v1/auth/oidc/callback/oidc_002",
  "created_at": "2024-01-20T17:30:00Z"
}
```

### 9. Setup MFA
```http
POST /v1/enterprise/auth/mfa/setup
```

**Description**: Configure multi-factor authentication

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "enforcement_policy": "required_for_admins",
  "allowed_methods": ["totp", "sms", "email"],
  "backup_codes": {
    "enabled": true,
    "count": 10
  },
  "grace_period_days": 7,
  "session_timeout_hours": 8
}
```

**Response** (200):
```json
{
  "policy_id": "mfa_policy_001",
  "enforcement_policy": "required_for_admins",
  "affected_users": 28,
  "rollout_date": "2024-01-27T00:00:00Z",
  "message": "MFA policy configured successfully"
}
```

## API Key Management

### 10. List API Keys
```http
GET /v1/enterprise/auth/api-keys
```

**Description**: List API keys for current tenant

**Authentication**: Required

**Query Parameters**:
- `include_revoked` (boolean, default: false): Include revoked keys
- `created_by` (string, optional): Filter by creator

**Response** (200):
```json
{
  "api_keys": [
    {
      "id": "key_001",
      "name": "Production Integration",
      "prefix": "lf_prod_",
      "permissions": ["logs:write", "metrics:write"],
      "created_by": "user_123",
      "created_at": "2024-01-15T10:00:00Z",
      "last_used": "2024-01-20T16:45:00Z",
      "usage_stats": {
        "requests_24h": 12500,
        "requests_total": 1250000
      },
      "expires_at": "2025-01-15T10:00:00Z",
      "status": "active"
    },
    {
      "id": "key_002",
      "name": "Dev Environment",
      "prefix": "lf_dev_",
      "permissions": ["logs:read", "dashboards:read"],
      "created_by": "user_456",
      "created_at": "2024-01-10T14:30:00Z",
      "last_used": "2024-01-19T11:20:00Z",
      "expires_at": "2024-07-10T14:30:00Z",
      "status": "active"
    }
  ],
  "total": 8,
  "active": 6,
  "expired": 1,
  "revoked": 1
}
```

### 11. Create API Key
```http
POST /v1/enterprise/auth/api-keys
```

**Description**: Create new API key

**Authentication**: Required

**Request Body**:
```json
{
  "name": "CI/CD Pipeline",
  "description": "API key for automated log ingestion from CI/CD",
  "permissions": ["logs:write", "metrics:write"],
  "rate_limit": {
    "requests_per_minute": 1000,
    "burst_limit": 2000
  },
  "ip_restrictions": ["10.0.0.0/8", "192.168.1.0/24"],
  "expires_at": "2025-01-20T00:00:00Z"
}
```

**Response** (201):
```json
{
  "id": "key_009",
  "name": "CI/CD Pipeline",
  "api_key": "lf_prod_abc123def456ghi789...",
  "prefix": "lf_prod_abc123",
  "permissions": ["logs:write", "metrics:write"],
  "rate_limit": {
    "requests_per_minute": 1000,
    "burst_limit": 2000
  },
  "created_at": "2024-01-20T18:00:00Z",
  "expires_at": "2025-01-20T00:00:00Z",
  "warning": "API key will only be shown once. Store it securely."
}
```

### 12. Revoke API Key
```http
DELETE /v1/enterprise/auth/api-keys/{key_id}
```

**Description**: Revoke API key

**Authentication**: Required

**Path Parameters**:
- `key_id` (string): API key identifier

**Response** (200):
```json
{
  "message": "API key revoked successfully",
  "key_id": "key_009",
  "revoked_at": "2024-01-20T18:15:00Z",
  "impact": {
    "active_sessions": 0,
    "last_used": "2024-01-20T17:30:00Z"
  }
}
```

## Audit Logging

### 13. List Audit Logs
```http
GET /v1/enterprise/audit-logs
```

**Description**: List enterprise audit logs

**Authentication**: Required (admin or compliance_officer role)

**Query Parameters**:
- `user_id` (string, optional): Filter by user
- `action` (string, optional): Filter by action type
- `resource` (string, optional): Filter by resource type
- `start_time` (string, optional): Start time filter
- `end_time` (string, optional): End time filter
- `limit` (integer, default: 100): Maximum logs to return
- `offset` (integer, default: 0): Number of logs to skip

**Response** (200):
```json
{
  "audit_logs": [
    {
      "id": "audit_001",
      "timestamp": "2024-01-20T17:45:00Z",
      "user_id": "user_123",
      "user_email": "admin@company.com",
      "action": "user:create",
      "resource": "users",
      "resource_id": "user_789",
      "tenant_id": "tenant_456",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      "result": "success",
      "details": {
        "user_email": "newuser@company.com",
        "roles_assigned": ["user"],
        "invitation_sent": true
      },
      "risk_score": 2
    },
    {
      "id": "audit_002",
      "timestamp": "2024-01-20T17:30:00Z",
      "user_id": "user_456",
      "user_email": "analyst@company.com",
      "action": "dashboard:share",
      "resource": "dashboards",
      "resource_id": "dash_001",
      "tenant_id": "tenant_456",
      "ip_address": "192.168.1.101",
      "result": "success",
      "details": {
        "shared_with": "user_789",
        "permissions": ["view"],
        "expires_at": "2024-02-20T00:00:00Z"
      },
      "risk_score": 1
    }
  ],
  "total": 12500,
  "summary": {
    "actions_24h": 1250,
    "users_active_24h": 47,
    "high_risk_events": 3,
    "failed_actions": 15
  }
}
```

## Compliance Management

### 14. Generate Compliance Reports
```http
GET /v1/enterprise/compliance/reports
```

**Description**: Generate compliance reports for various frameworks

**Authentication**: Required (compliance_officer or admin role)

**Query Parameters**:
- `framework` (string): Compliance framework (SOX, GDPR, HIPAA, PCI-DSS)
- `period` (string): Reporting period (monthly, quarterly, yearly)
- `start_date` (string): Report start date
- `end_date` (string): Report end date

**Response** (200):
```json
{
  "report_id": "comp_report_001",
  "framework": "SOX",
  "period": "quarterly",
  "report_date": "2024-01-20T18:00:00Z",
  "period_covered": {
    "start": "2023-10-01T00:00:00Z",
    "end": "2023-12-31T23:59:59Z"
  },
  "compliance_status": "compliant",
  "summary": {
    "total_controls": 45,
    "controls_passed": 43,
    "controls_failed": 0,
    "controls_pending": 2,
    "compliance_score": 95.6
  },
  "controls": [
    {
      "control_id": "SOX.AC.01",
      "name": "User Access Management",
      "status": "passed",
      "description": "Proper user access controls and regular reviews",
      "evidence": [
        "User access reviews completed monthly",
        "Privileged access monitored and logged",
        "Inactive accounts disabled within 30 days"
      ],
      "last_tested": "2023-12-15T00:00:00Z"
    },
    {
      "control_id": "SOX.AU.01",
      "name": "Audit Logging",
      "status": "passed",
      "description": "Comprehensive audit logging of all system activities",
      "evidence": [
        "All user actions logged and retained",
        "Log integrity protected with checksums",
        "Audit logs reviewed weekly by security team"
      ],
      "last_tested": "2023-12-20T00:00:00Z"
    }
  ],
  "recommendations": [
    "Implement automated compliance monitoring for real-time alerts",
    "Consider additional controls for data encryption at rest"
  ],
  "download_url": "/enterprise/compliance/reports/comp_report_001/download"
}
```

### 15. Legal Hold Management
```http
POST /v1/enterprise/compliance/legal-hold
```

**Description**: Create legal hold for data preservation

**Authentication**: Required (compliance_officer or admin role)

**Request Body**:
```json
{
  "case_name": "Litigation Case 2024-001",
  "description": "Data preservation for pending litigation",
  "custodians": ["user_123", "user_456", "user_789"],
  "data_types": ["logs", "emails", "documents"],
  "date_range": {
    "start": "2023-01-01T00:00:00Z",
    "end": "2024-01-20T23:59:59Z"
  },
  "search_terms": ["project_alpha", "confidential", "contract"],
  "retention_policy": "indefinite",
  "notify_custodians": true
}
```

**Response** (201):
```json
{
  "hold_id": "legal_hold_001",
  "case_name": "Litigation Case 2024-001",
  "status": "active",
  "created_at": "2024-01-20T18:30:00Z",
  "data_preserved": {
    "log_entries": 125000,
    "documents": 1500,
    "emails": 2500,
    "size_gb": 15.6
  },
  "custodians_notified": 3,
  "estimated_cost_monthly": 150.00
}
```

## Enterprise Integrations

### 16. List Enterprise Integrations
```http
GET /v1/enterprise/integrations
```

**Description**: List configured enterprise integrations

**Authentication**: Required (admin role)

**Response** (200):
```json
{
  "integrations": [
    {
      "id": "int_001",
      "type": "slack",
      "name": "Security Team Slack",
      "status": "active",
      "configuration": {
        "webhook_url": "https://hooks.slack.com/services/...",
        "channels": ["#security-alerts", "#incidents"],
        "notification_types": ["security_events", "system_alerts"]
      },
      "health": {
        "last_check": "2024-01-20T17:45:00Z",
        "success_rate_24h": 0.998,
        "avg_latency_ms": 145
      },
      "usage": {
        "messages_sent_24h": 125,
        "errors_24h": 2
      }
    },
    {
      "id": "int_002",
      "type": "servicenow",
      "name": "Corporate ServiceNow",
      "status": "active",
      "configuration": {
        "instance_url": "https://company.service-now.com",
        "table": "incident",
        "auto_assign": true
      },
      "health": {
        "last_check": "2024-01-20T17:40:00Z",
        "success_rate_24h": 1.0,
        "avg_latency_ms": 850
      }
    }
  ],
  "available_types": [
    "slack", "servicenow", "jira", "pagerduty", "webhook", 
    "splunk", "elasticsearch", "prometheus"
  ]
}
```

### 17. Configure Integration
```http
POST /v1/enterprise/integrations/{integration_type}/configure
```

**Description**: Configure specific integration type

**Authentication**: Required (admin role)

**Path Parameters**:
- `integration_type` (string): Integration type (slack, servicenow, etc.)

**Request Body** (Slack example):
```json
{
  "name": "DevOps Team Slack",
  "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
  "channels": ["#devops-alerts", "#system-health"],
  "notification_types": ["system_alerts", "performance_alerts"],
  "filters": {
    "severity": ["high", "critical"],
    "services": ["api-service", "database"]
  },
  "rate_limit": {
    "max_per_hour": 100,
    "burst_limit": 10
  }
}
```

**Response** (201):
```json
{
  "integration_id": "int_008",
  "type": "slack",
  "name": "DevOps Team Slack",
  "status": "active",
  "test_message_sent": true,
  "created_at": "2024-01-20T19:00:00Z"
}
```

### 18. Integration Health Status
```http
GET /v1/enterprise/integrations/{integration_type}/status
```

**Description**: Get health status for specific integration type

**Authentication**: Required (admin role)

**Path Parameters**:
- `integration_type` (string): Integration type

**Response** (200):
```json
{
  "integration_type": "slack",
  "overall_status": "healthy",
  "integrations": [
    {
      "id": "int_001",
      "name": "Security Team Slack",
      "status": "healthy",
      "last_successful": "2024-01-20T18:45:00Z",
      "last_error": null,
      "success_rate_24h": 0.998
    },
    {
      "id": "int_008",
      "name": "DevOps Team Slack",
      "status": "healthy",
      "last_successful": "2024-01-20T19:00:00Z",
      "last_error": null,
      "success_rate_24h": 1.0
    }
  ],
  "aggregate_metrics": {
    "total_messages_24h": 245,
    "successful_deliveries": 243,
    "failed_deliveries": 2,
    "avg_latency_ms": 156
  }
}
```

## Alert Management

### 19. List Alert Rules
```http
GET /v1/alerts/rules
```

**Description**: List alert rules for the customer

**Authentication**: Required

**Query Parameters**:
- `enabled` (boolean, optional): Filter by enabled status
- `severity` (string, optional): Filter by severity
- `category` (string, optional): Filter by category
- `limit` (integer, default: 100): Maximum rules to return
- `offset` (integer, default: 0): Number of rules to skip

**Response** (200):
```json
{
  "rules": [
    {
      "id": "alert_rule_001",
      "name": "High Error Rate",
      "description": "Alert when error rate exceeds 5% for 5 minutes",
      "category": "performance",
      "severity": "high",
      "enabled": true,
      "rule_type": "threshold",
      "condition": {
        "metric": "error_rate",
        "operator": "gt",
        "threshold": 0.05,
        "window": "5m",
        "evaluation_interval": "1m"
      },
      "query": {
        "filters": [
          {"field": "level", "operator": "eq", "value": "error"}
        ],
        "time_range": "5m",
        "aggregation": "rate"
      },
      "notifications": [
        {
          "type": "slack",
          "target": "#alerts",
          "template": "error_rate_alert"
        },
        {
          "type": "email",
          "target": "oncall@company.com"
        }
      ],
      "created_by": "user_123",
      "created_at": "2024-01-15T10:00:00Z",
      "last_triggered": "2024-01-20T16:30:00Z",
      "trigger_count_24h": 3
    }
  ],
  "total": 25,
  "enabled": 22,
  "disabled": 3,
  "by_severity": {
    "critical": 5,
    "high": 8,
    "medium": 10,
    "low": 2
  }
}
```

### 20. Create Alert Rule
```http
POST /v1/alerts/rules
```

**Description**: Create new alert rule

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Database Connection Failures",
  "description": "Alert when database connections fail repeatedly",
  "category": "infrastructure",
  "severity": "critical",
  "enabled": true,
  "rule_type": "frequency",
  "condition": {
    "event_count": 10,
    "time_window": "5m",
    "evaluation_interval": "1m"
  },
  "query": {
    "filters": [
      {"field": "service", "operator": "eq", "value": "database"},
      {"field": "event_type", "operator": "eq", "value": "connection_failed"}
    ],
    "time_range": "5m"
  },
  "notifications": [
    {
      "type": "pagerduty",
      "target": "database_team",
      "priority": "high"
    },
    {
      "type": "slack",
      "target": "#database-alerts",
      "template": "db_connection_alert"
    }
  ],
  "tags": ["database", "critical_infrastructure"],
  "runbook_url": "https://wiki.company.com/database-troubleshooting"
}
```

**Response** (201):
```json
{
  "id": "alert_rule_026",
  "name": "Database Connection Failures",
  "status": "active",
  "enabled": true,
  "created_at": "2024-01-20T19:15:00Z",
  "next_evaluation": "2024-01-20T19:16:00Z",
  "message": "Alert rule created successfully"
}
```

### 21. List Active Alerts
```http
GET /v1/alerts
```

**Description**: List active alerts for the customer

**Authentication**: Required

**Query Parameters**:
- `status` (string, optional): Filter by status (firing, pending, resolved)
- `severity` (string, optional): Filter by severity
- `assigned_to` (string, optional): Filter by assignee
- `limit` (integer, default: 100): Maximum alerts to return
- `offset` (integer, default: 0): Number of alerts to skip

**Response** (200):
```json
{
  "alerts": [
    {
      "id": "alert_001",
      "rule_id": "alert_rule_001",
      "rule_name": "High Error Rate",
      "status": "firing",
      "severity": "high",
      "started_at": "2024-01-20T18:45:00Z",
      "last_updated": "2024-01-20T19:15:00Z",
      "summary": "Error rate is 8.5% (threshold: 5%)",
      "description": "API service error rate has exceeded threshold for 30 minutes",
      "labels": {
        "service": "api-service",
        "environment": "production",
        "severity": "high"
      },
      "annotations": {
        "runbook": "https://wiki.company.com/api-troubleshooting",
        "dashboard": "/dashboards/api-performance"
      },
      "assigned_to": "oncall_engineer",
      "notification_count": 5,
      "acknowledgments": []
    }
  ],
  "total": 15,
  "by_status": {
    "firing": 8,
    "pending": 3,
    "resolved": 4
  },
  "by_severity": {
    "critical": 2,
    "high": 6,
    "medium": 5,
    "low": 2
  }
}
```

### 22. Acknowledge Alert
```http
POST /v1/alerts/{alert_id}/acknowledge
```

**Description**: Acknowledge alert to stop notifications

**Authentication**: Required

**Path Parameters**:
- `alert_id` (string): Alert identifier

**Request Body**:
```json
{
  "comment": "Investigating root cause, implementing temporary fix",
  "timeout": "2h"
}
```

**Response** (200):
```json
{
  "alert_id": "alert_001",
  "status": "acknowledged",
  "acknowledged_by": "user_123",
  "acknowledged_at": "2024-01-20T19:30:00Z",
  "comment": "Investigating root cause, implementing temporary fix",
  "timeout_at": "2024-01-20T21:30:00Z"
}
```

### 23. Resolve Alert
```http
POST /v1/alerts/{alert_id}/resolve
```

**Description**: Manually resolve alert

**Authentication**: Required

**Path Parameters**:
- `alert_id` (string): Alert identifier

**Request Body**:
```json
{
  "resolution": "Fixed database connection pool configuration",
  "root_cause": "Connection pool size was too small for peak load",
  "actions_taken": [
    "Increased connection pool size from 20 to 50",
    "Added connection pool monitoring",
    "Updated alerting thresholds"
  ]
}
```

**Response** (200):
```json
{
  "alert_id": "alert_001",
  "status": "resolved",
  "resolved_by": "user_123",
  "resolved_at": "2024-01-20T19:45:00Z",
  "duration": "1h 0m",
  "resolution": "Fixed database connection pool configuration"
}
```

## Backup & Disaster Recovery

### 24. Configure Backup
```http
POST /v1/enterprise/backup/configure
```

**Description**: Configure enterprise backup policies

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "backup_type": "full",
  "schedule": {
    "frequency": "daily",
    "time": "02:00:00",
    "timezone": "UTC"
  },
  "retention": {
    "daily": 30,
    "weekly": 12,
    "monthly": 12,
    "yearly": 7
  },
  "storage": {
    "type": "s3",
    "bucket": "logforge-backups",
    "encryption": "AES256",
    "compression": true
  },
  "data_types": ["logs", "configs", "audit_logs", "user_data"],
  "notification": {
    "on_success": false,
    "on_failure": true,
    "email": "admin@company.com"
  }
}
```

**Response** (200):
```json
{
  "backup_policy_id": "backup_001",
  "status": "configured",
  "next_backup": "2024-01-21T02:00:00Z",
  "estimated_size_gb": 125.6,
  "estimated_duration_hours": 3,
  "created_at": "2024-01-20T20:00:00Z"
}
```

## Enterprise Metrics & Billing

### 25. Enterprise Metrics
```http
GET /v1/enterprise/metrics
```

**Description**: Get enterprise-level metrics and analytics

**Authentication**: Required (admin role)

**Query Parameters**:
- `period` (string, default: "30d"): Metrics period
- `breakdown` (string, optional): Breakdown by tenant, user, feature

**Response** (200):
```json
{
  "period": "30d",
  "summary": {
    "total_users": 347,
    "active_users": 312,
    "api_calls": 125000000,
    "data_ingested_gb": 1250.5,
    "data_stored_gb": 8500.2,
    "alerts_triggered": 1250,
    "compliance_score": 98.5
  },
  "usage_by_feature": {
    "log_ingestion": {
      "volume_gb": 1250.5,
      "requests": 85000000,
      "cost_usd": 1250.50
    },
    "log_queries": {
      "query_count": 25000000,
      "data_scanned_gb": 5500.0,
      "cost_usd": 550.00
    },
    "dashboards": {
      "views": 125000,
      "custom_dashboards": 45,
      "cost_usd": 125.00
    },
    "alerts": {
      "rules_active": 22,
      "notifications_sent": 2500,
      "cost_usd": 75.00
    }
  },
  "trends": {
    "user_growth_rate": 0.15,
    "usage_growth_rate": 0.28,
    "cost_efficiency_improvement": 0.12
  }
}
```

### 26. Billing Information
```http
GET /v1/enterprise/usage/billing
```

**Description**: Get billing information and usage costs

**Authentication**: Required (admin or billing_admin role)

**Query Parameters**:
- `billing_period` (string, optional): Specific billing period (YYYY-MM)

**Response** (200):
```json
{
  "billing_period": "2024-01",
  "billing_cycle": "monthly",
  "subscription": {
    "plan": "Enterprise",
    "tier": "Premium",
    "contract_start": "2024-01-01T00:00:00Z",
    "contract_end": "2024-12-31T23:59:59Z",
    "auto_renewal": true
  },
  "current_usage": {
    "period_start": "2024-01-01T00:00:00Z",
    "period_end": "2024-01-31T23:59:59Z",
    "base_cost_usd": 5000.00,
    "usage_costs": {
      "log_ingestion": 1250.50,
      "log_storage": 850.00,
      "query_processing": 550.00,
      "api_calls": 125.00,
      "user_seats": 2085.00
    },
    "total_cost_usd": 9860.50,
    "credits_applied": 500.00,
    "amount_due": 9360.50
  },
  "usage_limits": {
    "log_ingestion_gb": {
      "included": 1000,
      "used": 1250.5,
      "overage": 250.5,
      "overage_rate_per_gb": 5.00
    },
    "user_seats": {
      "included": 500,
      "used": 347,
      "remaining": 153
    }
  },
  "next_billing_date": "2024-02-01T00:00:00Z"
}
```

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_rbac_config` | RBAC configuration is invalid |
| 400 | `invalid_integration_config` | Integration configuration is invalid |
| 403 | `insufficient_enterprise_role` | User lacks required enterprise role |
| 404 | `role_not_found` | RBAC role does not exist |
| 404 | `integration_not_found` | Integration does not exist |
| 409 | `role_name_conflict` | Role name already exists |
| 409 | `integration_already_exists` | Integration already configured |

### Example Error Response
```json
{
  "detail": "RBAC role name already exists in tenant",
  "type": "role_name_conflict",
  "code": "RBAC_001",
  "context": {
    "role_name": "security_analyst",
    "existing_role_id": "role_003",
    "suggestion": "Use a different role name or update existing role"
  }
}
```

## Best Practices

### RBAC Management
1. **Principle of Least Privilege**: Grant minimum necessary permissions
2. **Regular Reviews**: Audit role assignments quarterly
3. **Role Separation**: Separate duties for sensitive operations
4. **Temporary Access**: Use time-limited role assignments
5. **Documentation**: Document role purposes and permissions

### Compliance
1. **Automated Monitoring**: Implement continuous compliance monitoring
2. **Regular Reporting**: Generate compliance reports monthly/quarterly
3. **Evidence Collection**: Maintain audit trails for all activities
4. **Policy Updates**: Keep policies current with regulatory changes
5. **Training**: Ensure staff understand compliance requirements

### Integration Management
1. **Health Monitoring**: Monitor integration health continuously
2. **Error Handling**: Implement retry logic and graceful degradation
3. **Rate Limiting**: Respect external service rate limits
4. **Security**: Use secure authentication for all integrations
5. **Documentation**: Maintain integration runbooks and troubleshooting guides

---

*See [User Management APIs](./User-Management-APIs.md) for basic user operations and [Security Analytics APIs](./Security-Analytics-APIs.md) for security-focused enterprise features.*