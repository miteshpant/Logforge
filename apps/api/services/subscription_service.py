"""
Subscription Service
Business logic layer for subscription and billing operations
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import structlog

from dao.subscription_dao import SubscriptionDAO
from models import (
    TenantSubscription, FeatureRate, UsageRecord, TenantDeletion,
    SubscriptionTier, BillingCycle, SubscriptionStatus, PricingModel, DeletionType,
    TenantSubscriptionRequest, FeatureRateRequest, TenantDeletionRequest
)

logger = structlog.get_logger()

class SubscriptionService:
    """Service layer for subscription and billing management with proper database operations"""

    def __init__(self):
        self.subscription_dao = SubscriptionDAO()
        self.feature_bundles = self._initialize_feature_bundles()
        self.endpoint_feature_map = self._initialize_endpoint_mapping()

    def _initialize_feature_bundles(self) -> Dict[str, List[str]]:
        """Initialize subscription tier feature bundles"""
        return {
            "startup": [
                "ingestion.basic",      # Basic log ingestion
                "storage.hot",          # ClickHouse hot storage
                "queries.basic"         # Basic search queries
            ],
            "starter": [
                "ingestion.basic",      # Basic log ingestion
                "storage.hot",          # ClickHouse hot storage
                "queries.basic"         # Basic search queries
            ],
            "smb": [
                "ingestion.*",          # All ingestion features
                "storage.*",            # All storage features
                "queries.*",            # All query features
                "alerts.basic",         # Basic alerting
                "dashboards.readonly",  # View-only dashboards
                "export.basic"          # Basic data export
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
            ],
            "non_profit": [
                "ingestion.basic",      # Basic log ingestion
                "storage.hot",          # ClickHouse hot storage
                "queries.basic",        # Basic search queries
                "alerts.basic"          # Basic alerting for non-profits
            ],
            "government": [
                "ingestion.*",          # All ingestion features
                "storage.*",            # All storage features
                "queries.*",            # All query features
                "alerts.*",             # All alerting features
                "dashboards.*",         # All dashboard features
                "security.*",           # All security features
                "export.basic"          # Basic data export
            ],
            "education": [
                "ingestion.basic",      # Basic log ingestion
                "storage.hot",          # ClickHouse hot storage
                "queries.basic",        # Basic search queries
                "alerts.basic",         # Basic alerting
                "dashboards.readonly"   # View-only dashboards
            ],
            "healthcare": [
                "ingestion.*",          # All ingestion features
                "storage.*",            # All storage features
                "queries.*",            # All query features
                "alerts.*",             # All alerting features
                "dashboards.*",         # All dashboard features
                "security.*",           # All security features (HIPAA compliance)
                "export.basic"          # Basic data export
            ],
            "financial": [
                "ingestion.*",          # All ingestion features
                "storage.*",            # All storage features
                "queries.*",            # All query features
                "alerts.*",             # All alerting features
                "dashboards.*",         # All dashboard features
                "security.*",           # All security features (SOX/PCI compliance)
                "observability.*",      # All observability features
                "export.*"              # All export features
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
            "/v1/security/mitre-coverage": "security.mitre",

            # Observability endpoints
            "/v1/observability/health": "observability.basic",
            "/v1/observability/traces": "observability.traces",
            "/v1/observability/metrics": "observability.metrics",
            "/v1/observability/services": "observability.apm",
            "/v1/observability/dependencies": "observability.apm",

            # AI endpoints
            "/v1/ai/health": "ai_assistant.basic",
            "/v1/ai/query": "ai_assistant.query",
            "/v1/ai/ask": "ai_assistant.query",
            "/v1/ai/nl2query": "ai_assistant.query",
            "/v1/ai/triage": "ai_assistant.query",
            "/v1/ai/pipeline-draft": "ai_assistant.query",
            "/v1/ai/explain": "ai_assistant.query",
            "/v1/ai/copilot/plan": "ai_assistant.query",
            "/v1/ai/copilot/run": "ai_assistant.query",
            "/v1/ai/rule-draft": "ai_assistant.query",
            "/v1/ai/rule-draft/enable": "ai_assistant.query",
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

    def get_features_for_tier(self, tier: str) -> List[str]:
        """Get feature list for a subscription tier"""
        return self.feature_bundles.get(tier, [])

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

        # Store usage record using DAO
        usage_data = {
            'tenant_id': usage_record.tenant_id,
            'feature_name': usage_record.feature_name,
            'usage_type': usage_record.usage_type,
            'quantity': usage_record.quantity,
            'timestamp': usage_record.timestamp,
            'billing_period': usage_record.billing_period,
            'cost_calculated': usage_record.cost_calculated,
            'rate_applied': usage_record.rate_applied,
            'metadata': usage_record.metadata,
            'customer_id': tenant_id
        }
        await self.subscription_dao.create_usage_record(usage_data)

        return usage_record

    async def get_tenant_subscription(self, tenant_id: str) -> Optional[TenantSubscription]:
        """Get tenant subscription details"""
        db_subscription = await self.subscription_dao.get_subscription_by_tenant(tenant_id)

        if not db_subscription:
            return None

        return TenantSubscription(
            tenant_id=db_subscription["tenant_id"],
            subscribed_features=db_subscription["subscribed_features"],
            subscription_tier=SubscriptionTier(db_subscription["subscription_tier"]),
            billing_cycle=BillingCycle(db_subscription["billing_cycle"]),
            status=SubscriptionStatus(db_subscription["status"]),
            started_at=db_subscription["started_at"],
            expires_at=db_subscription.get("expires_at"),
            auto_renew=db_subscription.get("auto_renew", True),
            monthly_spend_limit=db_subscription.get("monthly_spend_limit"),
            overage_allowed=db_subscription.get("overage_allowed", False)
        )

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

        # Store in database using DAO
        subscription_data = {
            'tenant_id': subscription.tenant_id,
            'subscribed_features': subscription.subscribed_features,
            'subscription_tier': subscription.subscription_tier.value,
            'billing_cycle': subscription.billing_cycle.value,
            'status': subscription.status.value,
            'started_at': subscription.started_at,
            'expires_at': subscription.expires_at,
            'auto_renew': subscription.auto_renew,
            'monthly_spend_limit': subscription.monthly_spend_limit,
            'overage_allowed': subscription.overage_allowed,
            'customer_id': tenant_id
        }
        await self.subscription_dao.create_subscription(subscription_data)

        return subscription

    async def create_subscription_for_tier(self, tenant_id: str, subscription_tier: str, billing_cycle: str = "monthly", auto_renew: bool = True) -> TenantSubscription:
        """Create subscription with automatic feature assignment based on tier"""
        # Get features for the tier from the bundle system
        features = self.get_features_for_tier(subscription_tier)
        
        if not features:
            # Fallback for unknown tiers
            logger.warning(f"Unknown subscription tier: {subscription_tier}, using basic features")
            features = ["ingestion.basic", "storage.hot", "queries.basic"]
        
        # Create subscription data directly
        subscription_data = {
            'tenant_id': tenant_id,
            'subscribed_features': features,
            'subscription_tier': subscription_tier,
            'billing_cycle': billing_cycle,
            'status': 'active',
            'started_at': datetime.now(timezone.utc),
            'expires_at': None,
            'auto_renew': auto_renew,
            'monthly_spend_limit': None,
            'overage_allowed': False,
            'customer_id': tenant_id
        }
        
        # Store directly using DAO
        await self.subscription_dao.create_subscription(subscription_data)
        
        # Return created subscription
        return await self.get_tenant_subscription(tenant_id)

    async def get_feature_rate(self, feature: str, tenant_id: str) -> Optional[FeatureRate]:
        """Get current feature rate for tenant, with fallback to YAML pricing"""
        try:
            # First try to get from database
            db_rate = await self.subscription_dao.get_feature_rate(feature)
            if db_rate:
                return FeatureRate(
                    feature_name=db_rate["feature_name"],
                    pricing_model=PricingModel(db_rate["pricing_model"]),
                    base_rate=float(db_rate["base_rate"]),
                    tier_rates=json.loads(db_rate["tier_rates"]),
                    currency=db_rate["currency"],
                    effective_date=db_rate["effective_date"],
                    created_by=db_rate["created_by"],
                    description=db_rate.get("description", "")
                )

        except Exception as e:
            logger.debug("No database rate found, falling back to YAML pricing", feature=feature)

        # Fallback to YAML pricing configuration
        try:
            import yaml
            import os
            from datetime import datetime, timezone
            
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'pricing.yml')
            with open(config_path, 'r') as file:
                pricing_config = yaml.safe_load(file)
                
            feature_pricing = pricing_config.get('feature_pricing', {})
            if feature in feature_pricing:
                rate_config = feature_pricing[feature]
                return FeatureRate(
                    feature_name=feature,
                    pricing_model=PricingModel.PER_UNIT,
                    base_rate=float(rate_config['base_price']),
                    tier_rates={},
                    currency=pricing_config.get('currency', 'USD'),
                    effective_date=datetime.now(timezone.utc),
                    created_by="yaml_config",
                    description=rate_config.get('description', '')
                )
                
            logger.warning("Feature not found in pricing config", feature=feature)
            return None
            
        except Exception as e:
            logger.error("Failed to load YAML pricing config", error=str(e), feature=feature)
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

        # Store using DAO
        rate_data = {
            'feature_name': rate.feature_name,
            'pricing_model': rate.pricing_model.value,
            'base_rate': rate.base_rate,
            'tier_rates': rate.tier_rates,
            'currency': rate.currency,
            'effective_date': rate.effective_date,
            'created_by': rate.created_by,
            'description': rate.description,
            'customer_id': 'platform'
        }
        await self.subscription_dao.create_feature_rate(rate_data)

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

        # Store deletion record using DAO
        deletion_data = {
            'tenant_id': deletion_record.tenant_id,
            'deletion_type': deletion_record.deletion_type.value,
            'deleted_at': deletion_record.deleted_at,
            'deleted_by': deletion_record.deleted_by,
            'reason': deletion_record.reason,
            'data_cleanup_completed': deletion_record.data_cleanup_completed,
            'usage_records_retained': deletion_record.usage_records_retained,
            'final_bill_generated': deletion_record.final_bill_generated,
            'customer_id': tenant_id
        }
        await self.subscription_dao.create_deletion_record(deletion_data)

        return deletion_record

    async def get_tenant_usage(self, tenant_id: str, period: str = "current") -> Dict[str, Any]:
        """Get tenant usage summary"""
        if period == "current":
            period = self._get_current_billing_period()

        db_usage = await self.subscription_dao.get_tenant_usage(tenant_id, period)

        feature_usage = []
        total_cost = 0.0

        for row in db_usage:
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

    def _get_current_billing_period(self) -> str:
        """Get current billing period (YYYY-MM format)"""
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"

    async def _cleanup_tenant_data(self, tenant_id: str, deletion_type: DeletionType):
        """Clean up tenant data based on deletion type"""
        # In production, this would use the DAO to delete data from various tables
        logger.info("Tenant data cleanup initiated", tenant_id=tenant_id, deletion_type=deletion_type.value)

    async def _generate_final_bill(self, tenant_id: str):
        """Generate final bill for tenant"""
        # Get current usage
        usage = await self.get_tenant_usage(tenant_id, "current")
        logger.info("Final bill generated", tenant_id=tenant_id, total_cost=usage.get('total_cost', 0))
    
    async def get_billing_history(self, tenant_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Get tenant billing history"""
        return await self.subscription_dao.get_billing_history(tenant_id, limit)
    
    async def get_all_feature_rates(self) -> List[Dict[str, Any]]:
        """Get all feature rates"""
        return await self.subscription_dao.get_all_feature_rates()
    
    async def get_rate_history(self, feature_name: str) -> List[Dict[str, Any]]:
        """Get feature rate history"""
        return await self.subscription_dao.get_rate_history(feature_name)
    
    async def get_deletion_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant deletion status"""
        return await self.subscription_dao.get_deletion_status(tenant_id)
    
    async def admin_list_tenants_with_billing(self, include_deleted: bool = False, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Admin list all tenants with billing info"""
        return await self.subscription_dao.admin_list_tenants_with_billing(include_deleted, page, page_size)
    
    async def get_subscription_audit_trail(self, tenant_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get subscription change audit trail"""
        return await self.subscription_dao.get_subscription_audit_trail(tenant_id, start_date, end_date)
    
    async def generate_compliance_report(self, report_request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance report"""
        return await self.subscription_dao.generate_compliance_report(report_request)
    
    async def get_retention_compliance_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get data retention compliance status"""
        return await self.subscription_dao.get_retention_compliance_status(tenant_id)
    
    async def admin_billing_override(self, tenant_id: str, override_data: Dict[str, Any]) -> Dict[str, Any]:
        """Admin override billing amount"""
        return await self.subscription_dao.admin_billing_override(tenant_id, override_data)
