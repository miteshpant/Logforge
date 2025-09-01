# Tenant Subscription & Billing System

## Overview

A comprehensive tenant subscription system that enables feature-based billing, rate configuration, and access control. Tenants subscribe to specific features and are billed only for what they use, with 403 enforcement for unauthorized feature access.

## Core Requirements

### 1. Feature Subscription System
- Tenants subscribe to specific Logforge features (ingestion, alerts, security, etc.)
- 403 Forbidden response for accessing non-subscribed features
- Granular feature control at endpoint level
- Subscription status validation on every API call

### 2. Admin Rate Configuration
- Administrators can set pricing rates for each feature
- Per-feature pricing models (per log, per query, per alert, fixed monthly)
- Rate tiers based on tenant type (startup, professional, enterprise)
- Dynamic rate updates without service restart

### 3. Soft Delete with Data Cleanup
- Tenant deletion marks tenant as "deleted" but preserves usage records
- All tenant log data is permanently deleted from ClickHouse
- Usage and billing records are retained for compliance
- Graceful cleanup process with confirmation

## Feature Categories

### Core Features
| Feature | Description | Pricing Model |
|---------|-------------|---------------|
| `ingestion` | Log ingestion (all formats) | Per log ingested |
| `storage` | Hot storage (ClickHouse) | Per GB stored per month |
| `queries` | Log search and analytics | Per query executed |
| `dashboards` | Pre-built dashboards | Fixed monthly fee |
| `export` | Data export capabilities | Per GB exported |

### Advanced Features  
| Feature | Description | Pricing Model |
|---------|-------------|---------------|
| `alerts` | Alert rules and notifications | Per alert rule + notifications |
| `security` | SIEM and security analytics | Per security event processed |
| `observability` | APM and distributed tracing | Per span ingested |
| `ai_assistant` | AI-powered analysis | Per AI query + analysis |
| `enterprise` | SSO, RBAC, compliance | Fixed enterprise fee |

### Enterprise Features
| Feature | Description | Pricing Model |
|---------|-------------|---------------|
| `multi_tenant` | Dedicated tenant isolation | Fixed monthly fee |
| `compliance` | Compliance reporting | Per report generated |
| `premium_support` | 24/7 enterprise support | Fixed annual fee |
| `custom_integrations` | Custom API integrations | Per integration endpoint |

## Data Models

### Tenant Subscription
```python
@dataclass
class TenantSubscription:
    tenant_id: str
    subscribed_features: List[str]
    subscription_tier: SubscriptionTier  # STARTER, PROFESSIONAL, ENTERPRISE
    billing_cycle: BillingCycle  # MONTHLY, ANNUAL
    status: SubscriptionStatus  # ACTIVE, SUSPENDED, CANCELLED
    started_at: datetime
    expires_at: Optional[datetime]
    auto_renew: bool
```

### Feature Rate Configuration
```python
@dataclass
class FeatureRate:
    feature_name: str
    pricing_model: PricingModel  # PER_UNIT, FIXED_MONTHLY, TIERED
    base_rate: Decimal  # Base price per unit
    tier_rates: Dict[str, Decimal]  # Rates by subscription tier
    currency: str  # USD, EUR, etc.
    effective_date: datetime
    created_by: str  # Admin user who set the rate
```

### Usage Tracking
```python
@dataclass
class UsageRecord:
    usage_id: str
    tenant_id: str
    feature_name: str
    usage_type: str  # logs_ingested, queries_executed, alerts_triggered
    quantity: int
    timestamp: datetime
    billing_period: str  # 2025-09
    cost_calculated: Decimal
    rate_applied: Decimal
```

### Tenant Deletion
```python
@dataclass
class TenantDeletion:
    tenant_id: str
    deletion_type: DeletionType  # SOFT_DELETE, HARD_DELETE
    deleted_at: datetime
    deleted_by: str
    reason: str
    data_cleanup_completed: bool
    usage_records_retained: bool
    final_bill_generated: bool
```

## API Endpoints

### Subscription Management
```http
# Get tenant subscription details
GET /v1/tenants/{tenant_id}/subscription

# Update tenant subscription
PUT /v1/tenants/{tenant_id}/subscription
{
  "subscribed_features": ["ingestion", "queries", "alerts"],
  "subscription_tier": "professional",
  "billing_cycle": "monthly"
}

# Get feature availability for tenant
GET /v1/tenants/{tenant_id}/features

# Check specific feature access
GET /v1/tenants/{tenant_id}/features/{feature_name}/access
```

### Admin Rate Configuration
```http
# List all feature rates
GET /v1/admin/rates

# Set feature rate
POST /v1/admin/rates
{
  "feature_name": "ingestion",
  "pricing_model": "per_unit",
  "base_rate": "0.001",
  "tier_rates": {
    "starter": "0.002",
    "professional": "0.0015", 
    "enterprise": "0.001"
  },
  "currency": "USD"
}

# Update feature rate
PUT /v1/admin/rates/{feature_name}

# Get rate history
GET /v1/admin/rates/{feature_name}/history
```

### Usage & Billing
```http
# Get tenant usage summary
GET /v1/tenants/{tenant_id}/usage?period=2025-09

# Get detailed usage breakdown
GET /v1/tenants/{tenant_id}/usage/detailed?start_date=2025-09-01&end_date=2025-09-30

# Generate bill for tenant
POST /v1/tenants/{tenant_id}/billing/generate
{
  "billing_period": "2025-09",
  "include_usage_details": true
}

# Get billing history
GET /v1/tenants/{tenant_id}/billing/history
```

### Tenant Deletion
```http
# Soft delete tenant (preserves usage records)
DELETE /v1/tenants/{tenant_id}?type=soft
{
  "reason": "Customer requested account closure",
  "data_cleanup": true,
  "generate_final_bill": true
}

# Hard delete tenant (admin only - removes everything)
DELETE /v1/admin/tenants/{tenant_id}?type=hard
{
  "confirmation": "PERMANENTLY_DELETE_ALL_DATA",
  "reason": "Compliance requirement"
}

# Get deletion status
GET /v1/tenants/{tenant_id}/deletion/status
```

## Feature Access Control

### Middleware Implementation
```python
class FeatureAccessMiddleware:
    def __init__(self):
        self.feature_map = {
            # Ingestion endpoints
            "/v1/ingest/*": "ingestion",
            
            # Query endpoints  
            "/v1/query/*": "queries",
            "/v1/logs": "queries",
            
            # Dashboard endpoints
            "/v1/dashboards/*": "dashboards",
            
            # Alert endpoints
            "/v1/alerts/*": "alerts",
            
            # Security endpoints
            "/v1/security/*": "security",
            
            # Observability endpoints
            "/v1/observability/*": "observability",
            
            # AI endpoints
            "/v1/ai/*": "ai_assistant",
            
            # Enterprise endpoints
            "/v1/enterprise/*": "enterprise"
        }
    
    async def check_feature_access(self, tenant_id: str, endpoint: str) -> bool:
        feature = self.get_required_feature(endpoint)
        if not feature:
            return True  # No feature restriction
            
        subscription = await self.get_tenant_subscription(tenant_id)
        return feature in subscription.subscribed_features
```

### Usage Tracking Integration
```python
class UsageTracker:
    async def track_feature_usage(self, tenant_id: str, feature: str, quantity: int = 1):
        """Track usage for billing purposes"""
        usage_record = UsageRecord(
            usage_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            feature_name=feature,
            quantity=quantity,
            timestamp=datetime.now(timezone.utc),
            billing_period=self.get_current_billing_period()
        )
        
        # Calculate cost based on current rates
        rate = await self.get_feature_rate(feature, tenant_id)
        usage_record.cost_calculated = rate * quantity
        
        await self.store_usage_record(usage_record)
```

## Implementation Plan

### Phase 1: Core Subscription Model
1. **Data Models**: Create subscription, rate, and usage models
2. **Database Schema**: Add subscription and billing tables
3. **Basic API**: Tenant subscription CRUD operations
4. **Feature Mapping**: Map API endpoints to required features

### Phase 2: Access Control Enforcement
1. **Middleware**: Feature access validation middleware
2. **403 Responses**: Proper error messages for unauthorized access
3. **Subscription Checks**: Real-time subscription validation
4. **Performance**: Optimize subscription lookups (caching)

### Phase 3: Admin Configuration
1. **Rate Management**: Admin APIs for feature rate configuration
2. **Tier Management**: Subscription tier management
3. **Usage Monitoring**: Real-time usage tracking and alerts
4. **Billing Generation**: Automated billing calculation

### Phase 4: Tenant Lifecycle
1. **Soft Delete**: Tenant deletion with data cleanup
2. **Usage Retention**: Preserve billing records after deletion
3. **Data Cleanup**: Remove all tenant log data from ClickHouse
4. **Final Billing**: Generate final bill before deletion

## Database Schema

### Tenant Subscriptions Table
```sql
CREATE TABLE tenant_subscriptions (
    subscription_id String,
    tenant_id String,
    subscribed_features Array(String),
    subscription_tier Enum('starter', 'professional', 'enterprise'),
    billing_cycle Enum('monthly', 'annual'),
    status Enum('active', 'suspended', 'cancelled'),
    started_at DateTime64(3, 'UTC'),
    expires_at Nullable(DateTime64(3, 'UTC')),
    auto_renew Bool,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
ORDER BY (tenant_id, started_at);
```

### Feature Rates Table
```sql
CREATE TABLE feature_rates (
    rate_id String,
    feature_name String,
    pricing_model Enum('per_unit', 'fixed_monthly', 'tiered'),
    base_rate Decimal64(4),
    tier_rates String,  -- JSON object with tier-specific rates
    currency String,
    effective_date DateTime64(3, 'UTC'),
    created_by String,
    created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
ORDER BY (feature_name, effective_date);
```

### Usage Records Table
```sql
CREATE TABLE usage_records (
    usage_id String,
    tenant_id String,
    feature_name String,
    usage_type String,
    quantity UInt64,
    timestamp DateTime64(3, 'UTC'),
    billing_period String,
    cost_calculated Decimal64(4),
    rate_applied Decimal64(4),
    created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY billing_period
ORDER BY (tenant_id, feature_name, timestamp);
```

## Feature Access Examples

### Subscription Check Flow
```python
# Before processing any request
async def validate_feature_access(tenant_id: str, endpoint: str):
    required_feature = get_required_feature(endpoint)
    if not required_feature:
        return True
        
    subscription = await get_tenant_subscription(tenant_id)
    if required_feature not in subscription.subscribed_features:
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{required_feature}' not included in your subscription. Please upgrade your plan."
        )
    
    # Track usage for billing
    await track_feature_usage(tenant_id, required_feature, 1)
    return True
```

### 403 Response Format
```json
{
  "error": "feature_not_subscribed",
  "message": "Feature 'security' not included in your subscription. Please upgrade your plan.",
  "required_feature": "security",
  "current_subscription": ["ingestion", "queries", "dashboards"],
  "upgrade_url": "/v1/tenants/{tenant_id}/subscription/upgrade",
  "contact_sales": "sales@logforge.com"
}
```

## Business Rules

### Default Subscription Tiers
```yaml
starter:
  features: ["ingestion", "storage", "queries"]
  limits:
    logs_per_month: 1000000
    storage_gb: 10
    queries_per_month: 1000

professional:  
  features: ["ingestion", "storage", "queries", "dashboards", "alerts", "export"]
  limits:
    logs_per_month: 50000000
    storage_gb: 100
    queries_per_month: 10000

enterprise:
  features: ["*"]  # All features
  limits:
    logs_per_month: "unlimited"
    storage_gb: "unlimited"
    queries_per_month: "unlimited"
```

### Usage-Based Pricing Examples
```yaml
feature_rates:
  ingestion:
    per_million_logs: 5.00  # $5 per million logs
  storage:
    per_gb_per_month: 0.10  # $0.10 per GB per month
  queries:
    per_query: 0.01  # $0.01 per query
  alerts:
    per_rule_per_month: 2.00  # $2 per alert rule per month
    per_notification: 0.05  # $0.05 per notification sent
  security:
    per_security_event: 0.02  # $0.02 per security event processed
```

## Implementation Benefits

1. **Revenue Optimization** - Feature-based billing maximizes revenue per customer
2. **Cost Control** - Customers pay only for features they actually use
3. **Scalable Growth** - Natural upgrade path as customer needs evolve  
4. **Compliance** - Proper data deletion with usage record retention
5. **Admin Control** - Flexible rate configuration for different markets
6. **Customer Transparency** - Clear billing breakdown by feature usage

This system transforms Logforge into a modern SaaS platform with transparent, usage-based pricing and enterprise-grade subscription management.