# Tenant Management APIs

## Overview

The Tenant Management APIs provide comprehensive multi-tenant operations including tenant lifecycle management, subscription handling, usage tracking, billing, and compliance management. These APIs enable platform administrators to manage multiple customer tenants efficiently while maintaining strict data isolation.

**Base Paths**: `/v1/tenants`, `/v1/usage`  
**Total Endpoints**: 30+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)  
**Required Roles**: `admin`, `platform_admin`, or higher

## Core Tenant Operations

### 1. List Tenants
```http
GET /v1/tenants
```

**Description**: List all tenants (platform admin access)

**Authentication**: Required (platform admin)

**Query Parameters**:
- `status` (string, optional): Filter by status (active, suspended, trial)
- `subscription_tier` (string, optional): Filter by subscription tier
- `created_after` (string, optional): Filter by creation date
- `limit` (integer, default: 50): Maximum tenants to return
- `offset` (integer, default: 0): Number of tenants to skip

**Response** (200):
```json
{
  "tenants": [
    {
      "id": "tenant_001",
      "name": "acme_corp",
      "display_name": "ACME Corporation",
      "status": "active",
      "subscription_tier": "enterprise",
      "created_at": "2024-01-15T10:00:00Z",
      "admin_email": "admin@acme.com",
      "admin_user_id": "user_123",
      "user_count": 25,
      "storage_used_gb": 125.6,
      "monthly_cost_usd": 2500.00,
      "last_activity": "2024-01-20T18:45:00Z",
      "billing_status": "current",
      "compliance_frameworks": ["SOX", "GDPR"]
    },
    {
      "id": "tenant_002", 
      "name": "techstart_inc",
      "display_name": "TechStart Inc",
      "status": "active",
      "subscription_tier": "professional",
      "created_at": "2024-01-10T14:30:00Z",
      "admin_email": "admin@techstart.com",
      "admin_user_id": "user_456",
      "user_count": 8,
      "storage_used_gb": 45.2,
      "monthly_cost_usd": 800.00,
      "last_activity": "2024-01-20T16:20:00Z",
      "billing_status": "current"
    }
  ],
  "total": 127,
  "summary": {
    "active": 120,
    "suspended": 3,
    "trial": 4,
    "by_tier": {
      "enterprise": 25,
      "professional": 45,
      "starter": 50,
      "trial": 7
    }
  }
}
```

### 2. Create Tenant
```http
POST /v1/tenants
```

**Description**: Create new tenant with admin user

**Authentication**: Required (platform admin)

**Request Body**:
```json
{
  "name": "newcompany",
  "display_name": "New Company Ltd",
  "admin_email": "admin@newcompany.com",
  "admin_password": "SecurePassword123!",
  "subscription_tier": "professional",
  "billing_contact": {
    "name": "John Doe",
    "email": "billing@newcompany.com",
    "phone": "+1-555-123-4567"
  },
  "organization": {
    "industry": "technology",
    "size": "50-100",
    "country": "US",
    "timezone": "America/New_York"
  },
  "features": {
    "advanced_analytics": true,
    "custom_dashboards": true,
    "api_access": true,
    "sso": false
  },
  "compliance_requirements": ["GDPR"],
  "trial_period_days": 30
}
```

**Response** (201):
```json
{
  "id": "tenant_128",
  "name": "newcompany",
  "display_name": "New Company Ltd",
  "status": "active",
  "subscription_tier": "professional",
  "admin_user_id": "user_789",
  "created_at": "2024-01-20T19:00:00Z",
  "trial_expires_at": "2024-02-19T19:00:00Z",
  "onboarding": {
    "steps_completed": 1,
    "total_steps": 5,
    "next_step": "configure_data_sources"
  },
  "message": "Tenant created successfully"
}
```

### 3. Get Tenant Details
```http
GET /v1/tenants/{tenant_id}
```

**Description**: Get detailed tenant information

**Authentication**: Required (platform admin or tenant admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "id": "tenant_001",
  "name": "acme_corp",
  "display_name": "ACME Corporation",
  "status": "active",
  "subscription_tier": "enterprise",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-18T14:30:00Z",
  "admin_user_id": "user_123",
  "admin_email": "admin@acme.com",
  "organization": {
    "industry": "manufacturing",
    "size": "1000+",
    "country": "US",
    "timezone": "America/New_York",
    "address": {
      "street": "123 Main St",
      "city": "New York",
      "state": "NY",
      "postal_code": "10001"
    }
  },
  "billing": {
    "contact_email": "billing@acme.com",
    "payment_method": "credit_card",
    "billing_cycle": "monthly",
    "next_billing_date": "2024-02-01T00:00:00Z",
    "auto_pay": true
  },
  "usage_limits": {
    "users": {"limit": 100, "used": 25},
    "storage_gb": {"limit": 1000, "used": 125.6},
    "api_calls_monthly": {"limit": 10000000, "used": 2500000},
    "dashboards": {"limit": 50, "used": 12}
  },
  "features": {
    "advanced_analytics": true,
    "custom_dashboards": true,
    "api_access": true,
    "sso": true,
    "compliance_reporting": true,
    "priority_support": true
  },
  "compliance": {
    "frameworks": ["SOX", "GDPR"],
    "data_residency": "US",
    "retention_policy": "7_years",
    "encryption_at_rest": true
  },
  "settings": {
    "session_timeout_hours": 8,
    "password_policy": "strong",
    "mfa_required": true,
    "audit_logging": true,
    "data_export_allowed": true
  }
}
```

### 4. Update Tenant
```http
PUT /v1/tenants/{tenant_id}
```

**Description**: Update tenant configuration

**Authentication**: Required (platform admin or tenant admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Request Body**:
```json
{
  "display_name": "ACME Corporation LLC",
  "subscription_tier": "enterprise_plus",
  "features": {
    "advanced_analytics": true,
    "custom_dashboards": true,
    "api_access": true,
    "sso": true,
    "white_labeling": true
  },
  "usage_limits": {
    "users": 150,
    "storage_gb": 2000,
    "api_calls_monthly": 20000000
  },
  "settings": {
    "session_timeout_hours": 12,
    "mfa_required": false
  }
}
```

**Response** (200):
```json
{
  "id": "tenant_001",
  "display_name": "ACME Corporation LLC",
  "subscription_tier": "enterprise_plus",
  "updated_at": "2024-01-20T19:30:00Z",
  "changes": [
    "display_name updated",
    "subscription_tier upgraded",
    "white_labeling feature enabled",
    "user limit increased to 150",
    "session_timeout extended to 12 hours"
  ],
  "effective_date": "2024-02-01T00:00:00Z"
}
```

### 5. Delete Tenant
```http
DELETE /v1/tenants/{tenant_id}
```

**Description**: Initiate tenant deletion process

**Authentication**: Required (platform admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Query Parameters**:
- `force` (boolean, default: false): Skip grace period
- `backup_data` (boolean, default: true): Create backup before deletion

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "deletion_initiated": "2024-01-20T20:00:00Z",
  "grace_period_ends": "2024-01-27T20:00:00Z",
  "backup_created": true,
  "backup_id": "backup_tenant_001_20240120",
  "data_retention_days": 90,
  "message": "Tenant deletion initiated. Grace period: 7 days"
}
```

### 6. Get Tenant Stats (Lightweight)
```http
GET /v1/tenants/stats
```

**Description**: Get lightweight tenant statistics for admin dashboard

**Authentication**: Required (platform admin)

**Response** (200):
```json
{
  "total_tenants": 127,
  "active_tenants": 120,
  "trial_tenants": 4,
  "suspended_tenants": 3,
  "total_users": 2847,
  "total_storage_gb": 15670.5,
  "monthly_revenue_usd": 127450.00,
  "data_ingested_24h_gb": 125.6,
  "api_calls_24h": 12500000,
  "last_updated": "2024-01-20T20:00:00Z"
}
```

## Subscription Management

### 7. Get Tenant Subscription
```http
GET /v1/tenants/{tenant_id}/subscription
```

**Description**: Get tenant subscription details

**Authentication**: Required (platform admin or tenant admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "subscription": {
    "tier": "enterprise",
    "plan_name": "Enterprise Plus",
    "status": "active",
    "billing_cycle": "monthly",
    "price_per_month_usd": 2500.00,
    "started_at": "2024-01-15T10:00:00Z",
    "current_period_start": "2024-01-01T00:00:00Z",
    "current_period_end": "2024-01-31T23:59:59Z",
    "next_billing_date": "2024-02-01T00:00:00Z",
    "auto_renewal": true,
    "trial_period": false
  },
  "features": {
    "included": [
      "advanced_analytics", "custom_dashboards", "api_access", 
      "sso", "priority_support", "compliance_reporting"
    ],
    "add_ons": [
      {"name": "white_labeling", "price_monthly_usd": 500.00},
      {"name": "premium_support", "price_monthly_usd": 200.00}
    ]
  },
  "usage_limits": {
    "users": {"included": 100, "additional_per_user_usd": 25.00},
    "storage_gb": {"included": 1000, "additional_per_gb_usd": 2.00},
    "api_calls": {"included": 10000000, "additional_per_1k_usd": 0.10}
  },
  "billing_history": {
    "last_payment": {
      "date": "2024-01-01T00:00:00Z",
      "amount_usd": 2500.00,
      "status": "paid"
    },
    "payment_method": "credit_card_ending_1234"
  }
}
```

### 8. Update Subscription
```http
PUT /v1/tenants/{tenant_id}/subscription
```

**Description**: Update tenant subscription

**Authentication**: Required (platform admin or billing admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Request Body**:
```json
{
  "tier": "enterprise_plus",
  "billing_cycle": "annual",
  "add_ons": ["white_labeling", "premium_support"],
  "effective_date": "2024-02-01T00:00:00Z",
  "proration": true,
  "send_notification": true
}
```

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "subscription_updated": true,
  "old_tier": "enterprise",
  "new_tier": "enterprise_plus",
  "price_change_usd": 800.00,
  "effective_date": "2024-02-01T00:00:00Z",
  "proration_credit_usd": 416.67,
  "next_billing_amount_usd": 3300.00,
  "confirmation_sent": true
}
```

## Usage Tracking & Analytics

### 9. Get Current Usage
```http
GET /v1/usage/current/{tenant_id}
```

**Description**: Get current usage metrics for tenant

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "period": "current_month",
  "period_start": "2024-01-01T00:00:00Z",
  "period_end": "2024-01-31T23:59:59Z",
  "usage": {
    "users": {
      "active": 25,
      "limit": 100,
      "utilization_percent": 25.0
    },
    "storage": {
      "used_gb": 125.6,
      "limit_gb": 1000.0,
      "utilization_percent": 12.56,
      "growth_rate_monthly": 0.15
    },
    "api_calls": {
      "current_month": 2500000,
      "limit_monthly": 10000000,
      "utilization_percent": 25.0,
      "daily_average": 80645
    },
    "log_ingestion": {
      "volume_gb_month": 85.2,
      "events_count_month": 125000000,
      "avg_events_per_day": 4032258
    },
    "dashboards": {
      "total_created": 12,
      "limit": 50,
      "views_month": 8500
    },
    "alerts": {
      "rules_active": 15,
      "notifications_sent_month": 450
    }
  },
  "costs": {
    "base_subscription_usd": 2500.00,
    "overage_charges_usd": 0.00,
    "add_ons_usd": 700.00,
    "total_month_usd": 3200.00
  },
  "forecasts": {
    "end_of_month_storage_gb": 135.8,
    "end_of_month_api_calls": 2900000,
    "estimated_overage_cost_usd": 0.00
  }
}
```

### 10. Get Usage History
```http
GET /v1/usage/history/{tenant_id}
```

**Description**: Get historical usage data

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Query Parameters**:
- `period` (string, default: "6m"): History period (1m, 3m, 6m, 1y)
- `granularity` (string, default: "monthly"): Data granularity (daily, weekly, monthly)

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "period": "6m",
  "granularity": "monthly",
  "data_points": [
    {
      "period": "2023-08",
      "period_start": "2023-08-01T00:00:00Z",
      "period_end": "2023-08-31T23:59:59Z",
      "users": {"active": 18, "peak": 20},
      "storage_gb": 78.5,
      "api_calls": 1850000,
      "log_ingestion_gb": 65.2,
      "cost_usd": 2200.00
    },
    {
      "period": "2023-09",
      "period_start": "2023-09-01T00:00:00Z",
      "period_end": "2023-09-30T23:59:59Z",
      "users": {"active": 22, "peak": 24},
      "storage_gb": 95.8,
      "api_calls": 2100000,
      "log_ingestion_gb": 72.1,
      "cost_usd": 2350.00
    }
  ],
  "trends": {
    "user_growth_rate": 0.12,
    "storage_growth_rate": 0.18,
    "api_usage_growth_rate": 0.25,
    "cost_growth_rate": 0.15
  },
  "projections": {
    "next_month_users": 28,
    "next_month_storage_gb": 145.0,
    "next_month_cost_usd": 3400.00
  }
}
```

### 11. Real-time Usage
```http
GET /v1/usage/realtime/{tenant_id}
```

**Description**: Get real-time usage metrics

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "timestamp": "2024-01-20T20:15:00Z",
  "realtime_metrics": {
    "active_users_now": 8,
    "api_calls_per_minute": 125,
    "log_ingestion_eps": 850,
    "active_sessions": 12,
    "dashboard_views_active": 3,
    "alert_evaluations_per_minute": 45
  },
  "system_health": {
    "response_time_ms": 156,
    "error_rate_percent": 0.12,
    "queue_depth": 125,
    "cpu_usage_percent": 35.2,
    "memory_usage_percent": 68.5
  },
  "alerts": {
    "active_alerts": 2,
    "alerts_firing": 1,
    "last_alert": "2024-01-20T19:45:00Z"
  }
}
```

### 12. Export Usage Data
```http
GET /v1/usage/export/{tenant_id}
```

**Description**: Export usage data for billing or analysis

**Authentication**: Required (admin or billing role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Query Parameters**:
- `format` (string, default: "csv"): Export format (csv, json, xlsx)
- `period_start` (string): Start date (YYYY-MM-DD)
- `period_end` (string): End date (YYYY-MM-DD)
- `include_details` (boolean, default: false): Include detailed breakdowns

**Response** (200):
```json
{
  "export_id": "export_usage_001",
  "tenant_id": "tenant_001",
  "format": "csv",
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "status": "completed",
  "file_size_bytes": 2048576,
  "download_url": "/usage/exports/export_usage_001/download",
  "expires_at": "2024-01-27T20:15:00Z",
  "created_at": "2024-01-20T20:15:00Z"
}
```

## Billing Management

### 13. Generate Bill
```http
POST /v1/tenants/{tenant_id}/billing/generate
```

**Description**: Generate bill for specific period

**Authentication**: Required (billing admin)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Request Body**:
```json
{
  "billing_period": "2024-01",
  "include_usage_details": true,
  "send_to_customer": false,
  "apply_discounts": true
}
```

**Response** (200):
```json
{
  "bill_id": "bill_001",
  "tenant_id": "tenant_001",
  "billing_period": "2024-01",
  "generated_at": "2024-01-20T20:30:00Z",
  "bill_summary": {
    "subtotal_usd": 3200.00,
    "discounts_usd": 160.00,
    "taxes_usd": 304.00,
    "total_usd": 3344.00
  },
  "line_items": [
    {
      "description": "Enterprise Plan Base",
      "quantity": 1,
      "unit_price_usd": 2500.00,
      "total_usd": 2500.00
    },
    {
      "description": "White Labeling Add-on",
      "quantity": 1,
      "unit_price_usd": 500.00,
      "total_usd": 500.00
    },
    {
      "description": "Additional Storage (25.6 GB)",
      "quantity": 25.6,
      "unit_price_usd": 2.00,
      "total_usd": 51.20
    }
  ],
  "payment_due_date": "2024-02-15T00:00:00Z",
  "download_url": "/billing/bills/bill_001/download"
}
```

### 14. Billing History
```http
GET /v1/tenants/{tenant_id}/billing/history
```

**Description**: Get billing history for tenant

**Authentication**: Required (admin or billing role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Query Parameters**:
- `limit` (integer, default: 12): Number of bills to return
- `start_date` (string, optional): Start date filter

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "billing_history": [
    {
      "bill_id": "bill_001",
      "period": "2024-01",
      "amount_usd": 3344.00,
      "status": "paid",
      "due_date": "2024-02-15T00:00:00Z",
      "paid_date": "2024-02-10T14:30:00Z",
      "payment_method": "credit_card"
    },
    {
      "bill_id": "bill_002",
      "period": "2023-12",
      "amount_usd": 3200.00,
      "status": "paid",
      "due_date": "2024-01-15T00:00:00Z",
      "paid_date": "2024-01-12T16:45:00Z",
      "payment_method": "credit_card"
    }
  ],
  "summary": {
    "total_bills": 12,
    "total_paid_usd": 38400.00,
    "average_monthly_usd": 3200.00,
    "overdue_bills": 0,
    "next_bill_estimate_usd": 3400.00
  }
}
```

## Feature Management

### 15. Get Tenant Features
```http
GET /v1/tenants/{tenant_id}/features
```

**Description**: Get enabled features for tenant

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "subscription_tier": "enterprise",
  "features": {
    "core": {
      "log_ingestion": {"enabled": true, "limit": "unlimited"},
      "basic_dashboards": {"enabled": true, "limit": 10},
      "basic_alerts": {"enabled": true, "limit": 20},
      "user_management": {"enabled": true, "limit": 100}
    },
    "advanced": {
      "custom_dashboards": {"enabled": true, "limit": 50},
      "advanced_analytics": {"enabled": true},
      "api_access": {"enabled": true, "rate_limit": "10k/hour"},
      "data_export": {"enabled": true},
      "advanced_alerts": {"enabled": true, "limit": 100}
    },
    "enterprise": {
      "sso": {"enabled": true, "providers": ["oidc", "saml"]},
      "rbac": {"enabled": true, "custom_roles": true},
      "audit_logging": {"enabled": true, "retention_days": 2555},
      "compliance_reporting": {"enabled": true, "frameworks": ["SOX", "GDPR"]},
      "priority_support": {"enabled": true, "sla": "4h"}
    },
    "add_ons": {
      "white_labeling": {"enabled": true},
      "premium_support": {"enabled": true, "sla": "1h"},
      "data_residency": {"enabled": true, "regions": ["US"]},
      "extended_retention": {"enabled": true, "years": 7}
    }
  },
  "feature_usage": {
    "custom_dashboards": {"used": 12, "limit": 50},
    "api_calls_monthly": {"used": 2500000, "limit": 10000000},
    "advanced_alerts": {"used": 15, "limit": 100}
  }
}
```

### 16. Check Feature Access
```http
GET /v1/tenants/{tenant_id}/features/{feature_name}/access
```

**Description**: Check if tenant has access to specific feature

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier
- `feature_name` (string): Feature name

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "feature_name": "advanced_analytics",
  "has_access": true,
  "feature_details": {
    "enabled": true,
    "included_in_tier": true,
    "usage_limits": {
      "queries_per_hour": 1000,
      "data_retention_days": 90
    },
    "current_usage": {
      "queries_this_hour": 125,
      "data_stored_days": 45
    }
  },
  "expires_at": null,
  "restrictions": [],
  "upgrade_required": false
}
```

## Health & Monitoring

### 17. Get Tenant Health
```http
GET /v1/tenants/{tenant_id}/health
```

**Description**: Get health status for specific tenant

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "overall_health": "healthy",
  "last_updated": "2024-01-20T20:45:00Z",
  "components": {
    "data_ingestion": {
      "status": "healthy",
      "rate_eps": 850,
      "queue_depth": 45,
      "error_rate": 0.001
    },
    "query_performance": {
      "status": "healthy",
      "avg_response_time_ms": 156,
      "p95_response_time_ms": 450,
      "slow_queries_count": 2
    },
    "storage": {
      "status": "healthy",
      "used_gb": 125.6,
      "available_gb": 874.4,
      "utilization_percent": 12.56
    },
    "user_activity": {
      "status": "active",
      "active_users_24h": 18,
      "sessions_active": 8,
      "last_login": "2024-01-20T19:30:00Z"
    }
  },
  "alerts": {
    "active": 2,
    "critical": 0,
    "warnings": 2,
    "recent_alerts": [
      {
        "id": "alert_001",
        "severity": "warning",
        "message": "Storage usage above 10%",
        "timestamp": "2024-01-20T18:00:00Z"
      }
    ]
  },
  "performance_metrics": {
    "uptime_percent_30d": 99.95,
    "availability_sla": 99.9,
    "performance_score": 0.92
  }
}
```

### 18. Get Tenant Metrics
```http
GET /v1/tenants/{tenant_id}/metrics
```

**Description**: Get detailed metrics for tenant

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Query Parameters**:
- `period` (string, default: "24h"): Metrics period
- `metrics` (string, optional): Comma-separated metric names

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "period": "24h",
  "metrics": {
    "ingestion": {
      "events_count": 4500000,
      "volume_gb": 8.5,
      "rate_eps": 850,
      "peak_eps": 1250,
      "errors": 125
    },
    "queries": {
      "total_queries": 12500,
      "avg_response_time_ms": 156,
      "slow_queries": 25,
      "cached_queries": 8500,
      "cache_hit_rate": 0.68
    },
    "users": {
      "active_users": 18,
      "sessions": 45,
      "avg_session_duration_minutes": 125,
      "api_requests": 125000
    },
    "alerts": {
      "rules_evaluated": 125000,
      "alerts_triggered": 45,
      "notifications_sent": 67,
      "false_positives": 5
    },
    "dashboards": {
      "views": 450,
      "unique_viewers": 12,
      "avg_load_time_ms": 850,
      "exports": 15
    }
  },
  "trends": {
    "ingestion_growth": 0.15,
    "query_volume_growth": 0.25,
    "user_activity_change": 0.08,
    "performance_change": -0.02
  }
}
```

## Configuration & Settings

### 19. Get Tenant Configuration
```http
GET /v1/tenants/{tenant_id}/config
```

**Description**: Get tenant configuration settings

**Authentication**: Required (admin role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "configuration": {
    "general": {
      "timezone": "America/New_York",
      "date_format": "MM/DD/YYYY",
      "language": "en",
      "session_timeout_hours": 8
    },
    "security": {
      "password_policy": "strong",
      "mfa_required": true,
      "session_security": {
        "concurrent_sessions": 5,
        "idle_timeout_minutes": 30
      },
      "ip_restrictions": {
        "enabled": false,
        "whitelist": []
      }
    },
    "data": {
      "retention_policy": {
        "hot_storage_days": 30,
        "warm_storage_days": 90,
        "cold_storage_days": 2555
      },
      "backup_policy": {
        "enabled": true,
        "frequency": "daily",
        "retention_days": 30
      }
    },
    "integrations": {
      "api_access": {
        "enabled": true,
        "rate_limit": "10000/hour",
        "webhook_endpoints": 5
      },
      "sso": {
        "enabled": true,
        "provider": "azure_ad",
        "auto_provision": true
      }
    },
    "notifications": {
      "email_notifications": true,
      "slack_integration": true,
      "alert_channels": ["email", "slack"],
      "maintenance_notifications": true
    }
  },
  "last_updated": "2024-01-18T14:30:00Z",
  "updated_by": "user_123"
}
```

### 20. Get Usage Quotas
```http
GET /v1/tenants/{tenant_id}/quotas
```

**Description**: Get usage quotas and limits for tenant

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "subscription_tier": "enterprise",
  "quotas": {
    "users": {
      "limit": 100,
      "used": 25,
      "available": 75,
      "utilization_percent": 25.0,
      "soft_limit_warning": 80
    },
    "storage": {
      "limit_gb": 1000,
      "used_gb": 125.6,
      "available_gb": 874.4,
      "utilization_percent": 12.56,
      "projected_full_date": "2025-08-15"
    },
    "api_calls": {
      "limit_monthly": 10000000,
      "used_monthly": 2500000,
      "available_monthly": 7500000,
      "utilization_percent": 25.0,
      "daily_average": 80645
    },
    "log_ingestion": {
      "limit_gb_monthly": 100,
      "used_gb_monthly": 85.2,
      "available_gb_monthly": 14.8,
      "utilization_percent": 85.2,
      "projected_overage_gb": 12.5
    },
    "dashboards": {
      "limit": 50,
      "used": 12,
      "available": 38,
      "utilization_percent": 24.0
    },
    "alert_rules": {
      "limit": 100,
      "used": 15,
      "available": 85,
      "utilization_percent": 15.0
    }
  },
  "overage_policies": {
    "storage": {
      "auto_scale": true,
      "overage_rate_per_gb": 2.00,
      "notification_threshold": 90
    },
    "api_calls": {
      "auto_scale": true,
      "overage_rate_per_1k": 0.10,
      "rate_limit_enforcement": "soft"
    }
  },
  "alerts": [
    {
      "type": "quota_warning",
      "resource": "log_ingestion",
      "message": "Log ingestion at 85% of monthly quota",
      "action_required": false
    }
  ]
}
```

## Compliance & Legal

### 21. Get Compliance Status
```http
GET /v1/tenants/{tenant_id}/compliance
```

**Description**: Get compliance status for tenant

**Authentication**: Required (admin or compliance_officer role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "compliance_frameworks": ["SOX", "GDPR"],
  "overall_status": "compliant",
  "last_assessment": "2024-01-15T00:00:00Z",
  "next_assessment": "2024-04-15T00:00:00Z",
  "frameworks": {
    "SOX": {
      "status": "compliant",
      "score": 96.5,
      "controls": {
        "total": 45,
        "passed": 43,
        "failed": 0,
        "pending": 2
      },
      "last_audit": "2024-01-15T00:00:00Z",
      "next_audit": "2024-04-15T00:00:00Z"
    },
    "GDPR": {
      "status": "compliant",
      "score": 98.2,
      "controls": {
        "total": 32,
        "passed": 31,
        "failed": 0,
        "pending": 1
      },
      "data_protection": {
        "encryption_at_rest": true,
        "encryption_in_transit": true,
        "data_anonymization": true,
        "right_to_erasure": true
      }
    }
  },
  "data_governance": {
    "data_residency": "US",
    "data_classification": "implemented",
    "retention_policies": "configured",
    "access_controls": "enforced"
  },
  "audit_trail": {
    "enabled": true,
    "retention_days": 2555,
    "immutable": true,
    "events_24h": 12500
  }
}
```

### 22. Legal Hold Status
```http
GET /v1/tenants/{tenant_id}/legal-hold
```

**Description**: Get legal hold status for tenant

**Authentication**: Required (admin or compliance_officer role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "active_holds": [
    {
      "hold_id": "legal_hold_001",
      "case_name": "Litigation Case 2024-001",
      "status": "active",
      "created_at": "2024-01-10T00:00:00Z",
      "custodians": ["user_123", "user_456"],
      "data_preserved": {
        "logs": 125000,
        "emails": 2500,
        "documents": 1500,
        "size_gb": 15.6
      },
      "monthly_cost_usd": 150.00
    }
  ],
  "historical_holds": [
    {
      "hold_id": "legal_hold_002",
      "case_name": "Audit Investigation 2023-005",
      "status": "released",
      "created_at": "2023-08-15T00:00:00Z",
      "released_at": "2023-12-20T00:00:00Z",
      "duration_days": 127
    }
  ],
  "total_data_under_hold_gb": 15.6,
  "estimated_monthly_cost_usd": 150.00
}
```

## Storage & Infrastructure

### 23. Configure Storage
```http
POST /v1/tenants/{tenant_id}/storage/configure
```

**Description**: Configure storage settings for tenant

**Authentication**: Required (admin role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Request Body**:
```json
{
  "storage_class": "standard",
  "retention_policy": {
    "hot_days": 30,
    "warm_days": 90,
    "cold_days": 2555
  },
  "backup_config": {
    "enabled": true,
    "frequency": "daily",
    "retention_days": 30,
    "cross_region": true
  },
  "compression": {
    "enabled": true,
    "algorithm": "lz4",
    "target_ratio": 0.3
  },
  "encryption": {
    "at_rest": true,
    "in_transit": true,
    "key_management": "aws_kms"
  }
}
```

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "storage_configuration": "updated",
  "changes_applied": [
    "retention_policy updated",
    "backup_frequency changed to daily",
    "compression enabled with lz4",
    "encryption configured with AWS KMS"
  ],
  "effective_date": "2024-01-21T00:00:00Z",
  "estimated_cost_impact_usd": 125.00
}
```

### 24. Storage Status
```http
GET /v1/tenants/{tenant_id}/storage/status
```

**Description**: Get storage status and health

**Authentication**: Required

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "storage_health": "healthy",
  "total_storage_gb": 125.6,
  "storage_breakdown": {
    "hot": {
      "size_gb": 45.2,
      "utilization_percent": 36.0,
      "retention_days": 30
    },
    "warm": {
      "size_gb": 65.8,
      "utilization_percent": 52.4,
      "retention_days": 90
    },
    "cold": {
      "size_gb": 14.6,
      "utilization_percent": 11.6,
      "retention_days": 2555
    }
  },
  "performance": {
    "read_latency_ms": 12,
    "write_latency_ms": 18,
    "throughput_mbps": 450,
    "iops": 2500
  },
  "backup_status": {
    "last_backup": "2024-01-20T02:00:00Z",
    "backup_size_gb": 98.5,
    "next_backup": "2024-01-21T02:00:00Z",
    "retention_days": 30
  },
  "compression": {
    "enabled": true,
    "ratio": 0.32,
    "space_saved_gb": 58.4
  }
}
```

## Validation & Testing

### 25. Validate Tenant
```http
GET /v1/tenants/{tenant_id}/validate
```

**Description**: Validate tenant configuration and health

**Authentication**: Required (admin role)

**Path Parameters**:
- `tenant_id` (string): Tenant identifier

**Response** (200):
```json
{
  "tenant_id": "tenant_001",
  "validation_status": "passed",
  "validation_date": "2024-01-20T21:00:00Z",
  "checks": {
    "configuration": {
      "status": "passed",
      "issues": []
    },
    "billing": {
      "status": "passed",
      "payment_method": "valid",
      "subscription": "active"
    },
    "storage": {
      "status": "passed",
      "connectivity": "healthy",
      "performance": "normal"
    },
    "features": {
      "status": "passed",
      "all_features_functional": true
    },
    "compliance": {
      "status": "passed",
      "frameworks_compliant": ["SOX", "GDPR"]
    },
    "security": {
      "status": "passed",
      "encryption": "enabled",
      "access_controls": "enforced"
    }
  },
  "recommendations": [
    "Consider upgrading to annual billing for 15% discount",
    "Enable additional backup regions for disaster recovery"
  ],
  "overall_score": 98.5
}
```

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_tenant_config` | Tenant configuration is invalid |
| 403 | `tenant_access_denied` | User cannot access tenant |
| 404 | `tenant_not_found` | Tenant does not exist |
| 409 | `tenant_name_conflict` | Tenant name already exists |
| 409 | `billing_conflict` | Billing operation conflict |
| 422 | `subscription_error` | Subscription validation failed |
| 429 | `quota_exceeded` | Usage quota exceeded |

### Example Error Response
```json
{
  "detail": "Tenant has exceeded monthly API call quota",
  "type": "quota_exceeded",
  "code": "QUOTA_001",
  "context": {
    "tenant_id": "tenant_001",
    "quota_type": "api_calls",
    "limit": 10000000,
    "current_usage": 10250000,
    "reset_date": "2024-02-01T00:00:00Z"
  }
}
```

## Best Practices

### Tenant Management
1. **Proper Onboarding**: Use structured onboarding process
2. **Resource Monitoring**: Monitor usage and quotas regularly
3. **Billing Accuracy**: Validate billing calculations monthly
4. **Health Checks**: Perform regular tenant health validations
5. **Compliance**: Ensure ongoing compliance with required frameworks

### Usage Tracking
1. **Real-time Monitoring**: Track usage in real-time for quota enforcement
2. **Trend Analysis**: Analyze usage trends for capacity planning
3. **Cost Optimization**: Monitor and optimize costs continuously
4. **Forecasting**: Use historical data for usage forecasting
5. **Alerting**: Set up alerts for quota thresholds

### Multi-tenancy
1. **Data Isolation**: Ensure strict tenant data isolation
2. **Performance Isolation**: Prevent noisy neighbor problems
3. **Security**: Implement tenant-specific security policies
4. **Scalability**: Design for horizontal tenant scaling
5. **Compliance**: Maintain compliance per tenant requirements

---

*See [Enterprise APIs](./Enterprise-APIs.md) for advanced tenant features and [User Management APIs](./User-Management-APIs.md) for tenant user operations.*