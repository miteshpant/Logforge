"""
Subscription & Billing API Endpoints
Provides subscription management, billing, and admin rate configuration
"""

from datetime import datetime, timedelta
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional

from models import (
    TenantSubscriptionRequest, TenantSubscriptionResponse, FeatureRateRequest,
    TenantDeletionRequest, FeatureAccessResponse, UsageBreakdownResponse,
    SubscriptionTier, SubscriptionStatus, BillingCycle
)
from subscription_service import subscription_service
from tenant_dependencies import RequiredTenant

router = APIRouter(prefix="/v1", tags=["subscription"])

# =====================================
# Tenant Subscription Management
# =====================================

@router.get("/tenants/{tenant_id}/subscription", response_model=TenantSubscriptionResponse)
async def get_tenant_subscription(
    tenant_id: str,
    _: str = RequiredTenant
):
    """Get tenant subscription details"""
    try:
        subscription = await subscription_service.get_tenant_subscription(tenant_id)
        
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="Subscription not found for tenant"
            )
        
        # Get current usage
        try:
            usage = await subscription_service.get_tenant_usage(tenant_id)
        except Exception:
            # If usage retrieval fails, use empty usage data
            usage = {"feature_usage": [], "total_cost": 0.0}
        
        # Convert feature_usage list to current_usage dict format expected by the model
        feature_usage = usage.get("feature_usage", [])
        current_usage = {}
        for feature in feature_usage:
            feature_name = feature.get("feature_name", "unknown")
            quantity = feature.get("quantity", 0)
            current_usage[feature_name] = int(quantity)
        
        return TenantSubscriptionResponse(
            tenant_id=subscription.tenant_id,
            subscribed_features=subscription.subscribed_features,
            subscription_tier=subscription.subscription_tier,
            billing_cycle=subscription.billing_cycle,
            status=subscription.status,
            started_at=subscription.started_at,
            expires_at=subscription.expires_at,
            auto_renew=subscription.auto_renew,
            monthly_spend_limit=subscription.monthly_spend_limit,
            current_usage=current_usage
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get subscription: {str(e)}")

@router.put("/tenants/{tenant_id}/subscription", response_model=TenantSubscriptionResponse)
async def update_tenant_subscription(
    tenant_id: str,
    subscription_request: TenantSubscriptionRequest,
    _: str = RequiredTenant
):
    """Update tenant subscription"""
    try:
        subscription = await subscription_service.create_subscription(tenant_id, subscription_request)
        
        return TenantSubscriptionResponse(
            tenant_id=subscription.tenant_id,
            subscribed_features=subscription.subscribed_features,
            subscription_tier=subscription.subscription_tier,
            billing_cycle=subscription.billing_cycle,
            status=subscription.status,
            started_at=subscription.started_at,
            expires_at=subscription.expires_at,
            auto_renew=subscription.auto_renew,
            monthly_spend_limit=subscription.monthly_spend_limit,
            current_usage={}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update subscription: {str(e)}")

@router.get("/tenants/{tenant_id}/features")
async def get_tenant_features(
    tenant_id: str,
    _: str = RequiredTenant
):
    """Get available features for tenant"""
    try:
        subscription = await subscription_service.get_tenant_subscription(tenant_id)
        
        if not subscription:
            return {
                "tenant_id": tenant_id,
                "available_features": [],
                "subscription_tier": "none",
                "message": "No active subscription"
            }
        
        # Get all available features based on subscription
        all_features = subscription_service.endpoint_feature_map.values()
        available_features = []
        
        for feature in set(all_features):
            if subscription_service.has_feature_access(subscription.subscribed_features, feature):
                available_features.append(feature)
        
        return {
            "tenant_id": tenant_id,
            "available_features": available_features,
            "subscribed_features": subscription.subscribed_features,
            "subscription_tier": subscription.subscription_tier.value,
            "billing_cycle": subscription.billing_cycle.value,
            "status": subscription.status.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get features: {str(e)}")

@router.get("/tenants/{tenant_id}/features/{feature_name}/access", response_model=FeatureAccessResponse)
async def check_feature_access(
    tenant_id: str,
    feature_name: str,
    _: str = RequiredTenant
):
    """Check if tenant has access to specific feature"""
    try:
        subscription = await subscription_service.get_tenant_subscription(tenant_id)
        
        if not subscription:
            return FeatureAccessResponse(
                tenant_id=tenant_id,
                feature=feature_name,
                access_granted=False,
                subscription_tier=SubscriptionTier.STARTER,
                usage_limits={},
                current_usage={}
            )
        
        has_access = subscription_service.has_feature_access(subscription.subscribed_features, feature_name)
        
        return FeatureAccessResponse(
            tenant_id=tenant_id,
            feature=feature_name,
            access_granted=has_access,
            subscription_tier=subscription.subscription_tier,
            usage_limits={},
            current_usage={}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check feature access: {str(e)}")

# =====================================
# Usage & Billing
# =====================================

@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    period: str = "current",
    _: str = RequiredTenant
):
    """Get tenant usage summary"""
    try:
        usage = await subscription_service.get_tenant_usage(tenant_id, period)
        return usage
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage: {str(e)}")

@router.get("/tenants/{tenant_id}/usage/detailed", response_model=UsageBreakdownResponse)
async def get_detailed_usage(
    tenant_id: str,
    start_date: str,
    end_date: str,
    _: str = RequiredTenant
):
    """Get detailed usage breakdown"""
    try:
        # For now, return current usage (would implement date range filtering)
        usage = await subscription_service.get_tenant_usage(tenant_id, "current")
        
        return UsageBreakdownResponse(
            tenant_id=tenant_id,
            billing_period=f"{start_date} to {end_date}",
            total_cost=usage.get("total_cost", 0.0),
            currency="USD",
            feature_usage=usage.get("feature_usage", []),
            generated_at=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get detailed usage: {str(e)}")

@router.post("/tenants/{tenant_id}/billing/generate")
async def generate_bill(
    tenant_id: str,
    bill_request: Dict[str, Any],
    _: str = RequiredTenant
):
    """Generate bill for tenant"""
    try:
        billing_period = bill_request.get("billing_period", "current")
        include_details = bill_request.get("include_usage_details", True)
        
        # Get usage for billing period
        usage = await subscription_service.get_tenant_usage(tenant_id, billing_period)
        
        bill_id = str(uuid.uuid4())
        
        return {
            "bill_id": bill_id,
            "tenant_id": tenant_id,
            "billing_period": billing_period,
            "total_amount": usage.get("total_cost", 0.0),
            "currency": "USD",
            "generated_at": datetime.now().isoformat(),
            "due_date": (datetime.now() + timedelta(days=30)).isoformat(),
            "usage_details": usage.get("feature_usage", []) if include_details else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate bill: {str(e)}")

@router.get("/tenants/{tenant_id}/billing/history")
async def get_billing_history(
    tenant_id: str,
    limit: int = 12,
    _: str = RequiredTenant
):
    """Get tenant billing history"""
    billing_history = await subscription_service.get_billing_history(tenant_id, limit)
    
    return {
        "tenant_id": tenant_id,
        "bills": billing_history,
        "total_bills": len(billing_history)
    }

# =====================================
# Admin Rate Configuration
# =====================================

@router.get("/admin/rates")
async def list_feature_rates(
    request: Request
):
    """List all feature rates (admin only)"""
    rates = await subscription_service.get_all_feature_rates()
    
    return {
        "rates": rates,
        "total_count": len(rates),
        "currency": "USD"
    }

@router.post("/admin/rates", status_code=201)
async def create_feature_rate(
    rate_request: FeatureRateRequest,
    request: Request
):
    """Create or update feature rate (admin only)"""
    try:
        rate = await subscription_service.set_feature_rate(rate_request, "admin")
        
        return {
            "rate_id": str(uuid.uuid4()),
            "feature_name": rate.feature_name,
            "pricing_model": rate.pricing_model.value,
            "base_rate": rate.base_rate,
            "tier_rates": rate.tier_rates,
            "currency": rate.currency,
            "effective_date": rate.effective_date.isoformat(),
            "created_by": rate.created_by,
            "description": rate.description
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create rate: {str(e)}")

@router.put("/admin/rates/{feature_name}")
async def update_feature_rate(
    feature_name: str,
    rate_update: Dict[str, Any],
    request: Request
):
    """Update existing feature rate (admin only)"""
    try:
        # Create updated rate request
        current_rate = await subscription_service.get_feature_rate(feature_name, "admin")
        
        if not current_rate:
            raise HTTPException(status_code=404, detail="Feature rate not found")
        
        # Update with new values
        updated_request = FeatureRateRequest(
            feature_name=feature_name,
            pricing_model=current_rate.pricing_model,
            base_rate=rate_update.get("base_rate", current_rate.base_rate),
            tier_rates=rate_update.get("tier_rates", current_rate.tier_rates),
            currency=rate_update.get("currency", current_rate.currency),
            description=rate_update.get("description", current_rate.description)
        )
        
        updated_rate = await subscription_service.set_feature_rate(updated_request, "admin")
        
        return {
            "feature_name": updated_rate.feature_name,
            "base_rate": updated_rate.base_rate,
            "updated_at": updated_rate.effective_date.isoformat(),
            "message": "Feature rate updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rate: {str(e)}")

@router.get("/admin/rates/{feature_name}/history")
async def get_rate_history(
    feature_name: str,
    request: Request
):
    """Get feature rate history (admin only)"""
    rate_history = await subscription_service.get_rate_history(feature_name)
    return {
        "feature_name": feature_name,
        "rate_history": rate_history
    }

# =====================================
# Tenant Deletion
# =====================================

@router.delete("/tenants/{tenant_id}/subscription")
async def delete_tenant(
    tenant_id: str,
    deletion_request: TenantDeletionRequest,
    request: Request,
    _: str = RequiredTenant
):
    """Delete tenant with data cleanup"""
    try:
        # Get admin user from request (would implement proper auth)
        deleted_by = request.headers.get("X-Admin-User", "admin")
        
        print(f"DEBUG: About to call delete_tenant for {tenant_id}")
        deletion_record = await subscription_service.delete_tenant(
            tenant_id, 
            deletion_request, 
            deleted_by
        )
        print(f"DEBUG: Got deletion_record: {deletion_record}")
        
        response = {
            "tenant_id": tenant_id,
            "deletion_type": deletion_record.deletion_type.value,
            "deleted_at": deletion_record.deleted_at.isoformat(),
            "data_cleanup_scheduled": deletion_record.data_cleanup_completed,
            "final_bill_generated": deletion_record.final_bill_generated,
            "message": f"Tenant {deletion_record.deletion_type.value.replace('_', ' ')} completed successfully"
        }
        print(f"DEBUG: Returning response: {response}")
        return response
    except Exception as e:
        print(f"DEBUG: Exception in delete_tenant: {str(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tenant: {str(e)}")

@router.get("/tenants/{tenant_id}/deletion/status")
async def get_deletion_status(
    tenant_id: str,
    request: Request
):
    """Get tenant deletion status"""
    deletion_status = await subscription_service.get_deletion_status(tenant_id)
    return deletion_status

# =====================================
# Admin Tenant Management
# =====================================

@router.get("/admin/tenants")
async def admin_list_tenants(
    request: Request,
    include_deleted: bool = False,
    page: int = 1,
    page_size: int = 50
):
    """Admin list all tenants with billing info"""
    tenant_list = await subscription_service.admin_list_tenants_with_billing(include_deleted, page, page_size)
    return tenant_list

@router.get("/admin/tenants/{tenant_id}/details")
async def admin_get_tenant_details(
    tenant_id: str,
    request: Request
):
    """Admin get detailed tenant information"""
    try:
        subscription = await subscription_service.get_tenant_subscription(tenant_id)
        usage = await subscription_service.get_tenant_usage(tenant_id)
        
        return {
            "tenant_info": {
                "tenant_id": tenant_id,
                "status": "active"
            },
            "subscription_info": {
                "tier": subscription.subscription_tier.value if subscription else "none",
                "features": subscription.subscribed_features if subscription else [],
                "status": subscription.status.value if subscription else "none"
            },
            "usage_summary": usage,
            "admin_notes": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tenant details: {str(e)}")

@router.put("/admin/tenants/{tenant_id}/subscription")
async def admin_force_subscription_change(
    tenant_id: str,
    subscription_data: Dict[str, Any],
    request: Request
):
    """Admin force subscription change"""
    try:
        # Convert to subscription request
        subscription_request = TenantSubscriptionRequest(
            subscribed_features=subscription_data["subscribed_features"],
            subscription_tier=SubscriptionTier(subscription_data["subscription_tier"]),
            billing_cycle=BillingCycle(subscription_data.get("billing_cycle", "monthly")),
            monthly_spend_limit=subscription_data.get("monthly_spend_limit"),
            auto_renew=subscription_data.get("auto_renew", True)
        )
        
        subscription = await subscription_service.create_subscription(tenant_id, subscription_request)
        
        return {
            "tenant_id": tenant_id,
            "subscription_tier": subscription.subscription_tier.value,
            "subscribed_features": subscription.subscribed_features,
            "admin_override": True,
            "reason": subscription_data.get("reason", "Administrative change"),
            "updated_at": subscription.started_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to force subscription change: {str(e)}")

@router.post("/admin/tenants/{tenant_id}/billing/override")
async def admin_billing_override(
    tenant_id: str,
    override_data: Dict[str, Any],
    request: Request
):
    """Admin override billing amount"""
    override_result = await subscription_service.admin_billing_override(tenant_id, override_data)
    return override_result

# =====================================
# Compliance & Audit
# =====================================

@router.get("/admin/audit/subscription-changes")
async def get_subscription_audit_trail(
    tenant_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    request: Request = None
):
    """Get subscription change audit trail"""
    audit_events = await subscription_service.get_subscription_audit_trail(tenant_id, start_date, end_date)
    return {
        "audit_events": audit_events,
        "total_events": len(audit_events)
    }

@router.post("/admin/compliance/reports")
async def generate_compliance_report(
    report_request: Dict[str, Any],
    request: Request
):
    """Generate compliance report"""
    compliance_report = await subscription_service.generate_compliance_report(report_request)
    return compliance_report

@router.get("/admin/compliance/retention-status")
async def get_retention_compliance_status(
    tenant_id: Optional[str] = None,
    request: Request = None
):
    """Get data retention compliance status"""
    retention_status = await subscription_service.get_retention_compliance_status(tenant_id)
    return retention_status

# =====================================
# Feature Access Utilities
# =====================================

@router.get("/features/available")
async def list_all_available_features():
    """List all available features in the system"""
    try:
        return {
            "feature_categories": {
                "ingestion": [
                    "ingestion.basic",
                    "ingestion.batch", 
                    "ingestion.bulk",
                    "ingestion.enterprise"
                ],
                "queries": [
                    "queries.basic",
                    "queries.advanced"
                ],
                "alerts": [
                    "alerts.basic",
                    "alerts.advanced"
                ],
                "dashboards": [
                    "dashboards.readonly",
                    "dashboards.edit"
                ],
                "security": [
                    "security.basic",
                    "security.events",
                    "security.rules",
                    "security.hunting",
                    "security.intelligence",
                    "security.mitre"
                ],
                "observability": [
                    "observability.basic",
                    "observability.traces",
                    "observability.metrics", 
                    "observability.apm"
                ],
                "ai_assistant": [
                    "ai_assistant.basic",
                    "ai_assistant.query",
                    "ai_assistant.analysis",
                    "ai_assistant.rca",
                    "ai_assistant.anomaly",
                    "ai_assistant.investigation"
                ],
                "enterprise": [
                    "enterprise.system",
                    "enterprise.auth",
                    "enterprise.rbac",
                    "enterprise.compliance",
                    "enterprise.audit",
                    "enterprise.sso"
                ],
                "export": [
                    "export.basic",
                    "export.advanced"
                ]
            },
            "subscription_bundles": subscription_service.feature_bundles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list features: {str(e)}")
