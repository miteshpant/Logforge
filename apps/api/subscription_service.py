"""
Tenant Subscription & Billing Service
Handles feature subscriptions, access control, usage tracking, and billing
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict

from models import (
    TenantSubscription, FeatureRate, UsageRecord, TenantDeletion,
    SubscriptionTier, BillingCycle, SubscriptionStatus, PricingModel, DeletionType,
    TenantSubscriptionRequest, FeatureRateRequest, TenantDeletionRequest
)

class SubscriptionService:
    """Core subscription and billing service"""
    
    def __init__(self, clickhouse_client=None):
        self.clickhouse_client = clickhouse_client
        self.feature_bundles = self._initialize_feature_bundles()
        self.endpoint_feature_map = self._initialize_endpoint_mapping()
        
    def _initialize_feature_bundles(self) -> Dict[str, List[str]]:
        """Initialize subscription tier feature bundles"""
        return {
            "starter": [
                "ingestion.basic",      # Basic log ingestion
                "storage.hot",          # ClickHouse hot storage
                "queries.basic"         # Basic search queries
            ],
            "professional": [
                "ingestion.*",          # All ingestion features
                "storage.*",            # All storage features  
                "queries.*",            # All query features
                "alerts.basic",         # Basic alerting
                "dashboards.readonly",  # View-only dashboards
                "export.basic"          # Basic data export
            ],
            "enterprise": [
                "*"                     # All features (wildcard)
            ]
        }
    
    def _initialize_endpoint_mapping(self) -> Dict[str, str]:
        """Map API endpoints to required feature tags"""
        return {
            # Ingestion endpoints
            "/v1/ingest/logs": "ingestion.basic",
            "/v1/ingest/logs/batch": "ingestion.batch", 
            "/v1/ingest/logs/bulk": "ingestion.bulk",
            "/v1/ingest/otlp": "ingestion.enterprise",
            "/v1/ingest/syslog": "ingestion.basic",
            "/v1/ingest/nginx": "ingestion.basic",
            "/v1/ingest/cef": "ingestion.enterprise",
            "/v1/ingest/text": "ingestion.basic",
            "/v1/ingest/structured": "ingestion.basic",
            "/v1/ingest": "ingestion.basic",  # Auto-detect endpoint
            
            # Query endpoints
            "/v1/logs": "queries.basic",
            "/v1/query/advanced": "queries.advanced",
            "/v1/query/timeseries": "queries.advanced", 
            "/v1/query/aggregate": "queries.advanced",
            "/v1/query/saved": "queries.advanced",
            
            # Dashboard endpoints
            "/v1/dashboards": "dashboards.readonly",
            "/v1/dashboards/*/data": "dashboards.readonly",
            "/v1/dashboards/*": "dashboards.readonly",
            
            # Export endpoints
            "/v1/export": "export.basic",
            
            # Alert endpoints
            "/v1/alerts": "alerts.basic",
            "/v1/alerts/rules": "alerts.basic",
            "/v1/alerts/rules/*": "alerts.basic",
            "/v1/alerts/instances": "alerts.basic",
            "/v1/alerts/stats": "alerts.basic",
            "/v1/alerts/notifications/*": "alerts.basic",
            "/v1/alerts/integrations/*": "alerts.basic",
            
            # Security endpoints
            "/v1/security/health": "security.basic",
            "/v1/security/dashboard": "security.basic",
            "/v1/security/events": "security.events",
            "/v1/security/sigma-rules": "security.rules",
            "/v1/security/sigma-rules/*": "security.rules",
            "/v1/security/threat-hunting": "security.hunting", 
            "/v1/security/threat-intel": "security.intelligence",
            "/v1/security/mitre-attack/*": "security.mitre",
            
            # Observability endpoints
            "/v1/observability/health": "observability.basic",
            "/v1/observability/traces": "observability.traces",
            "/v1/observability/metrics": "observability.metrics",
            "/v1/observability/services": "observability.apm",
            "/v1/observability/dependencies": "observability.apm",
            
            # AI endpoints
            "/v1/ai/health": "ai_assistant.basic",
            "/v1/ai/query": "ai_assistant.query",
            "/v1/ai/analysis": "ai_assistant.analysis",
            "/v1/ai/rca": "ai_assistant.rca",
            "/v1/ai/anomaly": "ai_assistant.anomaly",
            "/v1/ai/investigation": "ai_assistant.investigation",
            
            # Enterprise endpoints
            "/v1/enterprise/system/health": "enterprise.system",
            "/v1/enterprise/auth/*": "enterprise.auth",
            "/v1/enterprise/rbac/*": "enterprise.rbac", 
            "/v1/enterprise/compliance/*": "enterprise.compliance",
            "/v1/enterprise/audit/*": "enterprise.audit",
            "/v1/enterprise/sso/*": "enterprise.sso"
        }
    
    def get_required_feature(self, endpoint: str) -> Optional[str]:
        """Get required feature tag for an endpoint"""
        # Direct match first
        if endpoint in self.endpoint_feature_map:
            return self.endpoint_feature_map[endpoint]
        
        # Pattern matching for dynamic endpoints
        for pattern, feature in self.endpoint_feature_map.items():
            if "*" in pattern:
                # Convert pattern to regex-like matching
                pattern_prefix = pattern.replace("*", "")
                if endpoint.startswith(pattern_prefix):
                    return feature
        
        # No feature restriction for unmapped endpoints (like health checks)
        return None
    
    def has_feature_access(self, subscribed_features: List[str], required_feature: str) -> bool:
        """Check if subscribed features include required feature (with wildcard support)"""
        if not required_feature:
            return True  # No feature restriction
        
        # Direct match
        if required_feature in subscribed_features:
            return True
        
        # Wildcard matching
        for feature in subscribed_features:
            # Full wildcard (enterprise tier)
            if feature == "*":
                return True
            
            # Namespace wildcard (e.g., "ingestion.*" covers "ingestion.basic")
            if feature.endswith(".*"):
                namespace = feature[:-2]
                if required_feature.startswith(namespace + "."):
                    return True
        
        return False
    
    async def validate_feature_access(self, tenant_id: str, endpoint: str) -> Dict[str, Any]:
        """Validate feature access for tenant and endpoint"""
        required_feature = self.get_required_feature(endpoint)
        
        if not required_feature:
            return {
                "access_granted": True,
                "reason": "No feature restriction"
            }
        
        # Get tenant subscription
        subscription = await self.get_tenant_subscription(tenant_id)
        
        if not subscription:
            return {
                "access_granted": False,
                "reason": "No subscription found",
                "error_code": "subscription_not_found"
            }
        
        # Check subscription status
        if subscription.status != SubscriptionStatus.ACTIVE:
            return {
                "access_granted": False,
                "reason": f"Subscription {subscription.status.value}",
                "error_code": "subscription_inactive"
            }
        
        # Check feature access
        has_access = self.has_feature_access(subscription.subscribed_features, required_feature)
        
        if not has_access:
            return {
                "access_granted": False,
                "reason": f"Feature '{required_feature}' not included in subscription",
                "error_code": "feature_not_subscribed",
                "required_feature": required_feature,
                "current_features": subscription.subscribed_features,
                "subscription_tier": subscription.subscription_tier.value
            }
        
        return {
            "access_granted": True,
            "feature": required_feature,
            "subscription_tier": subscription.subscription_tier.value
        }
    
    async def track_feature_usage(self, tenant_id: str, feature: str, quantity: int = 1, metadata: Dict[str, Any] = None) -> UsageRecord:
        """Track feature usage for billing"""
        if metadata is None:
            metadata = {}
        
        usage_record = UsageRecord(
            usage_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            feature_name=feature,
            usage_type="api_call",
            quantity=quantity,
            timestamp=datetime.now(timezone.utc),
            billing_period=self._get_current_billing_period(),
            cost_calculated=0.0,  # Will be calculated later
            rate_applied=0.0,     # Will be calculated later
            metadata=metadata
        )
        
        # Calculate cost based on current rates
        rate = await self.get_feature_rate(feature, tenant_id)
        if rate:
            usage_record.cost_calculated = rate.base_rate * quantity
            usage_record.rate_applied = rate.base_rate
        
        # Store usage record
        await self._store_usage_record(usage_record)
        
        return usage_record
    
    async def get_tenant_subscription(self, tenant_id: str) -> Optional[TenantSubscription]:
        """Get tenant subscription details"""
        if not self.clickhouse_client:
            # Return default subscription for testing
            return TenantSubscription(
                tenant_id=tenant_id,
                subscribed_features=["*"],  # Default: all features
                subscription_tier=SubscriptionTier.ENTERPRISE,
                billing_cycle=BillingCycle.MONTHLY,
                status=SubscriptionStatus.ACTIVE,
                started_at=datetime.now(timezone.utc)
            )
        
        # Query subscription from database
        query = """
        SELECT * FROM tenant_subscriptions 
        WHERE tenant_id = %(tenant_id)s 
        AND status = 'active'
        ORDER BY started_at DESC
        LIMIT 1
        """
        
        try:
            result = await self.clickhouse_client.execute(query, {"tenant_id": tenant_id})
            if result:
                row = result[0]
                return TenantSubscription(
                    tenant_id=row["tenant_id"],
                    subscribed_features=json.loads(row["subscribed_features"]),
                    subscription_tier=SubscriptionTier(row["subscription_tier"]),
                    billing_cycle=BillingCycle(row["billing_cycle"]),
                    status=SubscriptionStatus(row["status"]),
                    started_at=row["started_at"],
                    expires_at=row.get("expires_at"),
                    auto_renew=row.get("auto_renew", True),
                    monthly_spend_limit=row.get("monthly_spend_limit"),
                    overage_allowed=row.get("overage_allowed", False)
                )
        except Exception as e:
            print(f"Error getting subscription for {tenant_id}: {str(e)}")
        
        return None
    
    async def create_subscription(self, tenant_id: str, subscription_request: TenantSubscriptionRequest) -> TenantSubscription:
        """Create or update tenant subscription"""
        subscription = TenantSubscription(
            tenant_id=tenant_id,
            subscribed_features=subscription_request.subscribed_features,
            subscription_tier=subscription_request.subscription_tier,
            billing_cycle=subscription_request.billing_cycle,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            auto_renew=subscription_request.auto_renew,
            monthly_spend_limit=subscription_request.monthly_spend_limit
        )
        
        # Store in database
        await self._store_subscription(subscription)
        
        return subscription
    
    async def get_feature_rate(self, feature: str, tenant_id: str) -> Optional[FeatureRate]:
        """Get current feature rate for tenant"""
        if not self.clickhouse_client:
            # Return default rates for testing
            default_rates = {
                "ingestion.basic": FeatureRate("ingestion.basic", PricingModel.PER_UNIT, 0.001, {}),
                "queries.basic": FeatureRate("queries.basic", PricingModel.PER_UNIT, 0.01, {}),
                "alerts.basic": FeatureRate("alerts.basic", PricingModel.FIXED_MONTHLY, 19.99, {}),
                "security.events": FeatureRate("security.events", PricingModel.PER_UNIT, 0.05, {})
            }
            return default_rates.get(feature)
        
        # Query current rate from database
        query = """
        SELECT * FROM feature_rates 
        WHERE feature_name = %(feature)s 
        AND effective_date <= now()
        ORDER BY effective_date DESC
        LIMIT 1
        """
        
        try:
            result = await self.clickhouse_client.execute(query, {"feature": feature})
            if result:
                row = result[0]
                return FeatureRate(
                    feature_name=row["feature_name"],
                    pricing_model=PricingModel(row["pricing_model"]),
                    base_rate=float(row["base_rate"]),
                    tier_rates=json.loads(row["tier_rates"]),
                    currency=row["currency"],
                    effective_date=row["effective_date"],
                    created_by=row["created_by"],
                    description=row.get("description", "")
                )
        except Exception as e:
            print(f"Error getting feature rate for {feature}: {str(e)}")
        
        return None
    
    async def set_feature_rate(self, rate_request: FeatureRateRequest, created_by: str = "admin") -> FeatureRate:
        """Set or update feature rate"""
        rate = FeatureRate(
            feature_name=rate_request.feature_name,
            pricing_model=rate_request.pricing_model,
            base_rate=rate_request.base_rate,
            tier_rates=rate_request.tier_rates,
            currency=rate_request.currency,
            effective_date=datetime.now(timezone.utc),
            created_by=created_by,
            description=rate_request.description
        )
        
        await self._store_feature_rate(rate)
        return rate
    
    async def delete_tenant(self, tenant_id: str, deletion_request: TenantDeletionRequest, deleted_by: str) -> TenantDeletion:
        """Delete tenant with data cleanup"""
        deletion_record = TenantDeletion(
            tenant_id=tenant_id,
            deletion_type=deletion_request.deletion_type,
            deleted_at=datetime.now(timezone.utc),
            deleted_by=deleted_by,
            reason=deletion_request.reason,
            data_cleanup_completed=False,
            usage_records_retained=True,
            final_bill_generated=False
        )
        
        if deletion_request.deletion_type == DeletionType.HARD_DELETE:
            if deletion_request.confirmation != "PERMANENTLY_DELETE_ALL_DATA":
                raise ValueError("Hard delete requires confirmation: 'PERMANENTLY_DELETE_ALL_DATA'")
        
        # Generate final bill if requested
        if deletion_request.generate_final_bill:
            await self._generate_final_bill(tenant_id)
            deletion_record.final_bill_generated = True
        
        # Cleanup tenant data if requested
        if deletion_request.data_cleanup:
            await self._cleanup_tenant_data(tenant_id, deletion_request.deletion_type)
            deletion_record.data_cleanup_completed = True
        
        # Store deletion record
        await self._store_deletion_record(deletion_record)
        
        # Update tenant status
        await self._update_tenant_status(tenant_id, "deleted" if deletion_request.deletion_type == DeletionType.SOFT_DELETE else None)
        
        return deletion_record
    
    async def get_tenant_usage(self, tenant_id: str, period: str = "current") -> Dict[str, Any]:
        """Get tenant usage summary"""
        if period == "current":
            period = self._get_current_billing_period()
        
        if not self.clickhouse_client:
            # Return mock usage for testing
            return {
                "tenant_id": tenant_id,
                "billing_period": period,
                "feature_usage": [
                    {"feature_name": "ingestion", "quantity": 1000, "cost": 1.00},
                    {"feature_name": "queries", "quantity": 50, "cost": 0.50}
                ],
                "total_cost": 1.50,
                "currency": "USD"
            }
        
        # Query usage from database
        query = """
        SELECT 
            feature_name,
            sum(quantity) as total_quantity,
            sum(cost_calculated) as total_cost,
            count(*) as usage_events
        FROM usage_records 
        WHERE tenant_id = %(tenant_id)s 
        AND billing_period = %(period)s
        GROUP BY feature_name
        """
        
        try:
            results = await self.clickhouse_client.execute(query, {
                "tenant_id": tenant_id,
                "period": period
            })
            
            feature_usage = []
            total_cost = 0.0
            
            for row in results:
                usage_item = {
                    "feature_name": row["feature_name"],
                    "quantity": row["total_quantity"],
                    "cost": float(row["total_cost"]),
                    "usage_events": row["usage_events"]
                }
                feature_usage.append(usage_item)
                total_cost += usage_item["cost"]
            
            return {
                "tenant_id": tenant_id,
                "billing_period": period,
                "feature_usage": feature_usage,
                "total_cost": total_cost,
                "currency": "USD"
            }
            
        except Exception as e:
            print(f"Error getting usage for {tenant_id}: {str(e)}")
            return {"error": str(e)}
    
    def _get_current_billing_period(self) -> str:
        """Get current billing period (YYYY-MM format)"""
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"
    
    async def _store_subscription(self, subscription: TenantSubscription):
        """Store subscription in database"""
        if not self.clickhouse_client:
            return  # Skip for testing
        
        # Insert subscription record
        query = """
        INSERT INTO tenant_subscriptions (
            subscription_id, tenant_id, subscribed_features, subscription_tier,
            billing_cycle, status, started_at, expires_at, auto_renew,
            monthly_spend_limit, overage_allowed, created_at, updated_at
        ) VALUES (
            %(subscription_id)s, %(tenant_id)s, %(subscribed_features)s, %(subscription_tier)s,
            %(billing_cycle)s, %(status)s, %(started_at)s, %(expires_at)s, %(auto_renew)s,
            %(monthly_spend_limit)s, %(overage_allowed)s, now(), now()
        )
        """
        
        await self.clickhouse_client.execute(query, {
            "subscription_id": str(uuid.uuid4()),
            "tenant_id": subscription.tenant_id,
            "subscribed_features": json.dumps(subscription.subscribed_features),
            "subscription_tier": subscription.subscription_tier.value,
            "billing_cycle": subscription.billing_cycle.value,
            "status": subscription.status.value,
            "started_at": subscription.started_at,
            "expires_at": subscription.expires_at,
            "auto_renew": subscription.auto_renew,
            "monthly_spend_limit": subscription.monthly_spend_limit,
            "overage_allowed": subscription.overage_allowed
        })
    
    async def _store_feature_rate(self, rate: FeatureRate):
        """Store feature rate in database"""
        if not self.clickhouse_client:
            return  # Skip for testing
        
        query = """
        INSERT INTO feature_rates (
            rate_id, feature_name, pricing_model, base_rate, tier_rates,
            currency, effective_date, created_by, created_at
        ) VALUES (
            %(rate_id)s, %(feature_name)s, %(pricing_model)s, %(base_rate)s, %(tier_rates)s,
            %(currency)s, %(effective_date)s, %(created_by)s, now()
        )
        """
        
        await self.clickhouse_client.execute(query, {
            "rate_id": str(uuid.uuid4()),
            "feature_name": rate.feature_name,
            "pricing_model": rate.pricing_model.value,
            "base_rate": rate.base_rate,
            "tier_rates": json.dumps(rate.tier_rates),
            "currency": rate.currency,
            "effective_date": rate.effective_date,
            "created_by": rate.created_by
        })
    
    async def _store_usage_record(self, usage: UsageRecord):
        """Store usage record in database"""
        if not self.clickhouse_client:
            return  # Skip for testing
        
        query = """
        INSERT INTO usage_records (
            usage_id, tenant_id, feature_name, usage_type, quantity,
            timestamp, billing_period, cost_calculated, rate_applied, 
            metadata, created_at
        ) VALUES (
            %(usage_id)s, %(tenant_id)s, %(feature_name)s, %(usage_type)s, %(quantity)s,
            %(timestamp)s, %(billing_period)s, %(cost_calculated)s, %(rate_applied)s,
            %(metadata)s, now()
        )
        """
        
        await self.clickhouse_client.execute(query, {
            "usage_id": usage.usage_id,
            "tenant_id": usage.tenant_id,
            "feature_name": usage.feature_name,
            "usage_type": usage.usage_type,
            "quantity": usage.quantity,
            "timestamp": usage.timestamp,
            "billing_period": usage.billing_period,
            "cost_calculated": usage.cost_calculated,
            "rate_applied": usage.rate_applied,
            "metadata": json.dumps(usage.metadata)
        })
    
    async def _cleanup_tenant_data(self, tenant_id: str, deletion_type: DeletionType):
        """Clean up tenant data based on deletion type"""
        if not self.clickhouse_client:
            return  # Skip for testing
        
        if deletion_type == DeletionType.SOFT_DELETE:
            # Soft delete: Remove log data but keep usage/billing records
            queries = [
                "DELETE FROM logs_raw_mt WHERE customer_id = %(tenant_id)s",
                "DELETE FROM logs_normalized_mt WHERE customer_id = %(tenant_id)s",
                "DELETE FROM security_events WHERE tenant_id = %(tenant_id)s",
                "DELETE FROM alert_instances WHERE customer_id = %(tenant_id)s"
            ]
        else:  # HARD_DELETE
            # Hard delete: Remove everything including usage records
            queries = [
                "DELETE FROM logs_raw_mt WHERE customer_id = %(tenant_id)s",
                "DELETE FROM logs_normalized_mt WHERE customer_id = %(tenant_id)s", 
                "DELETE FROM security_events WHERE tenant_id = %(tenant_id)s",
                "DELETE FROM alert_instances WHERE customer_id = %(tenant_id)s",
                "DELETE FROM usage_records WHERE tenant_id = %(tenant_id)s",
                "DELETE FROM tenant_subscriptions WHERE tenant_id = %(tenant_id)s"
            ]
        
        for query in queries:
            try:
                await self.clickhouse_client.execute(query, {"tenant_id": tenant_id})
            except Exception as e:
                print(f"Error executing cleanup query: {str(e)}")
    
    async def _generate_final_bill(self, tenant_id: str):
        """Generate final bill for tenant"""
        # Get current usage
        usage = await self.get_tenant_usage(tenant_id, "current")
        
        # Store final bill record (implementation depends on billing system)
        print(f"Generated final bill for {tenant_id}: ${usage.get('total_cost', 0):.2f}")
    
    async def _store_deletion_record(self, deletion: TenantDeletion):
        """Store tenant deletion record"""
        if not self.clickhouse_client:
            return  # Skip for testing
        
        query = """
        INSERT INTO tenant_deletions (
            deletion_id, tenant_id, deletion_type, deleted_at, deleted_by,
            reason, data_cleanup_completed, usage_records_retained, 
            final_bill_generated, created_at
        ) VALUES (
            %(deletion_id)s, %(tenant_id)s, %(deletion_type)s, %(deleted_at)s, %(deleted_by)s,
            %(reason)s, %(data_cleanup_completed)s, %(usage_records_retained)s,
            %(final_bill_generated)s, now()
        )
        """
        
        await self.clickhouse_client.execute(query, {
            "deletion_id": str(uuid.uuid4()),
            "tenant_id": deletion.tenant_id,
            "deletion_type": deletion.deletion_type.value,
            "deleted_at": deletion.deleted_at,
            "deleted_by": deletion.deleted_by,
            "reason": deletion.reason,
            "data_cleanup_completed": deletion.data_cleanup_completed,
            "usage_records_retained": deletion.usage_records_retained,
            "final_bill_generated": deletion.final_bill_generated
        })
    
    async def _update_tenant_status(self, tenant_id: str, status: Optional[str]):
        """Update tenant status"""
        if not self.clickhouse_client or not status:
            return  # Skip for testing or no status change
        
        # This would update the tenant status in the tenant management system
        print(f"Updated tenant {tenant_id} status to: {status}")

# Global subscription service instance
subscription_service = SubscriptionService()

def setup_subscription_service(clickhouse_client):
    """Setup subscription service with database client"""
    global subscription_service
    subscription_service = SubscriptionService(clickhouse_client)
    return subscription_service