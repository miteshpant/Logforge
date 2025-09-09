"""
M8 API Usage Tracking & Billing API
FastAPI router for usage analytics, billing estimates, and cost tracking
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from calendar import monthrange
import structlog

from models import (
    UsageCurrentResponse, BillingEstimateResponse, UsageHistoryResponse,
    APIUsageAudit, User
)
from authn_authz_middleware import (
    get_current_user, require_platform_admin, require_tenant_admin,
    usage_buffer, FEATURE_BASE_COSTS, map_endpoint_to_feature
)

logger = structlog.get_logger()

# Create router for usage tracking
router = APIRouter(prefix="/v1", tags=["Usage Analytics & Billing"])

# =================================================================
# USAGE ANALYTICS SERVICE
# =================================================================

class UsageAnalyticsService:
    """Service for usage analytics and billing calculations"""
    
    def __init__(self):
        self.usage_cache = {}  # In-memory cache (use database in production)
        self.monthly_aggregates = {}  # Cached monthly aggregates
    
    async def get_current_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get current month usage for tenant"""
        current_month = datetime.utcnow().strftime("%Y-%m")
        
        # TODO: Query database for current month usage
        # For now, simulate usage data
        usage_data = {
            "tenant_id": tenant_id,
            "api_calls": 12547,
            "feature_breakdown": {
                "ingestion.basic": 8240,
                "queries.advanced": 2890,
                "security.analytics": 1200,
                "alerts.management": 217
            },
            "cost_estimate": 2.47,
            "billing_period": current_month,
            "period_start": f"{current_month}-01",
            "period_end": self._get_month_end(current_month)
        }
        
        return usage_data
    
    async def get_usage_history(self, tenant_id: str, months: int = 3) -> Dict[str, Any]:
        """Get historical usage for tenant"""
        current_date = datetime.utcnow()
        history_data = []
        
        for i in range(months):
            month_date = current_date - timedelta(days=30 * i)
            month_key = month_date.strftime("%Y-%m")
            
            # TODO: Query database for historical data
            # For now, simulate historical data
            monthly_usage = {
                "period": month_key,
                "api_calls": 10000 + (i * 1000),  # Simulated growth
                "total_cost": 2.0 + (i * 0.3),
                "feature_breakdown": {
                    "ingestion.basic": 6000 + (i * 500),
                    "queries.advanced": 2500 + (i * 300),
                    "security.analytics": 1000 + (i * 150),
                    "alerts.management": 500 + (i * 50)
                },
                "storage_gb": 150.5 + (i * 25.3),
                "period_start": f"{month_key}-01",
                "period_end": self._get_month_end(month_key)
            }
            
            history_data.append(monthly_usage)
        
        return {
            "tenant_id": tenant_id,
            "usage_by_month": history_data,
            "months_included": months,
            "generated_at": datetime.utcnow()
        }
    
    async def calculate_billing_estimate(self, tenant_id: str) -> Dict[str, Any]:
        """Calculate current billing estimate for tenant"""
        usage_data = await self.get_current_usage(tenant_id)
        
        # Calculate feature costs
        feature_costs = {}
        total_cost = 0.0
        
        for feature, call_count in usage_data["feature_breakdown"].items():
            base_rate = FEATURE_BASE_COSTS.get(feature, 0.0001)
            
            # Calculate cost based on pricing model
            if feature == "ingestion.basic":
                # $0.10 per 1M events
                cost = (call_count / 1_000_000) * 0.10
            elif feature == "queries.advanced":
                # $0.05 per 1K queries
                cost = (call_count / 1_000) * 0.05
            elif feature == "security.analytics":
                # $0.50 per 1K security queries
                cost = (call_count / 1_000) * 0.50
            elif feature == "alerts.management":
                # $0.20 per 1K alert operations
                cost = (call_count / 1_000) * 0.20
            else:
                cost = call_count * base_rate
            
            feature_costs[feature] = round(cost, 4)
            total_cost += cost
        
        return {
            "tenant_id": tenant_id,
            "total_estimated_cost": round(total_cost, 2),
            "feature_costs": feature_costs,
            "period": usage_data["billing_period"],
            "currency": "USD",
            "calculated_at": datetime.utcnow()
        }
    
    def _get_month_end(self, month_str: str) -> str:
        """Get last day of month"""
        year, month = map(int, month_str.split("-"))
        last_day = monthrange(year, month)[1]
        return f"{month_str}-{last_day:02d}"
    
    async def record_usage_batch(self, usage_records: List[Dict[str, Any]]):
        """Record batch of usage data to database"""
        try:
            # TODO: Implement actual database insertion
            # For now, just update cache
            for record in usage_records:
                cache_key = f"{record['tenant_id']}:{record['request_timestamp']}"
                self.usage_cache[cache_key] = record
            
            logger.info("Usage batch recorded", record_count=len(usage_records))
            
        except Exception as e:
            logger.error("Usage batch recording failed", error=str(e))
            raise

# Global usage analytics service
usage_analytics = UsageAnalyticsService()

# =================================================================
# CURRENT USAGE ENDPOINTS
# =================================================================

@router.get("/usage/current/{tenant_id}", response_model=UsageCurrentResponse)
async def get_current_usage(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get current month usage for tenant"""
    try:
        # Check permissions - platform admins, billing admins, or tenant users
        is_platform_admin = any(
            r["tenant_id"] == "platform" and r["role"] in ["super_admin", "admin", "billing_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_user = any(
            r["tenant_id"] == tenant_id
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_user:
            raise HTTPException(403, f"No access to usage data for tenant {tenant_id}")
        
        usage_data = await usage_analytics.get_current_usage(tenant_id)
        
        return UsageCurrentResponse(
            tenant_id=usage_data["tenant_id"],
            api_calls=usage_data["api_calls"],
            feature_breakdown=usage_data["feature_breakdown"],
            cost_estimate=usage_data["cost_estimate"],
            billing_period=usage_data["billing_period"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Current usage retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Current usage retrieval failed")

@router.get("/usage/history/{tenant_id}", response_model=UsageHistoryResponse)
async def get_usage_history(
    tenant_id: str,
    months: int = Query(3, ge=1, le=12, description="Number of months to retrieve"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get usage history for tenant"""
    try:
        # Check permissions
        is_platform_admin = any(
            r["tenant_id"] == "platform" and r["role"] in ["super_admin", "admin", "billing_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_user = any(
            r["tenant_id"] == tenant_id
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_user:
            raise HTTPException(403, f"No access to usage history for tenant {tenant_id}")
        
        history_data = await usage_analytics.get_usage_history(tenant_id, months)
        
        return UsageHistoryResponse(
            tenant_id=history_data["tenant_id"],
            usage_by_month=history_data["usage_by_month"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Usage history retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Usage history retrieval failed")

# =================================================================
# BILLING ENDPOINTS
# =================================================================

@router.get("/billing/estimate/{tenant_id}", response_model=BillingEstimateResponse)
async def get_billing_estimate(
    tenant_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get current billing estimate for tenant"""
    try:
        # Check permissions - platform admins, billing admins, or tenant admins
        is_platform_admin = any(
            r["tenant_id"] == "platform" and r["role"] in ["super_admin", "admin", "billing_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, f"No access to billing data for tenant {tenant_id}")
        
        billing_data = await usage_analytics.calculate_billing_estimate(tenant_id)
        
        return BillingEstimateResponse(
            tenant_id=billing_data["tenant_id"],
            total_estimated_cost=billing_data["total_estimated_cost"],
            feature_costs=billing_data["feature_costs"],
            period=billing_data["period"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Billing estimate failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Billing estimate failed")

@router.post("/billing/generate/{tenant_id}")
async def generate_invoice(
    tenant_id: str,
    month: Optional[str] = Query(None, description="Month to generate (YYYY-MM, defaults to last month)"),
    current_admin: User = Depends(require_platform_admin)
):
    """Generate invoice for tenant (platform admins only)"""
    try:
        # Default to last month if not specified
        if not month:
            last_month = datetime.utcnow().replace(day=1) - timedelta(days=1)
            month = last_month.strftime("%Y-%m")
        
        # Get usage data for the month
        # TODO: Query actual usage from database
        usage_data = {
            "tenant_id": tenant_id,
            "billing_period": month,
            "api_calls": 45230,
            "feature_usage": {
                "ingestion.basic": {"calls": 30000, "cost": 3.00},
                "queries.advanced": {"calls": 10000, "cost": 0.50}, 
                "security.analytics": {"calls": 4000, "cost": 2.00},
                "alerts.management": {"calls": 1230, "cost": 0.25}
            },
            "total_cost": 5.75,
            "currency": "USD"
        }
        
        # TODO: Create actual invoice record in database
        invoice_id = f"INV-{tenant_id}-{month}"
        
        logger.info("Invoice generated",
                   tenant_id=tenant_id,
                   invoice_id=invoice_id,
                   month=month,
                   total_cost=usage_data["total_cost"],
                   generated_by=current_admin.id)
        
        return {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
            "billing_period": month,
            "total_cost": usage_data["total_cost"],
            "currency": usage_data["currency"],
            "line_items": usage_data["feature_usage"],
            "generated_at": datetime.utcnow(),
            "generated_by": current_admin.id
        }
        
    except Exception as e:
        logger.error("Invoice generation failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Invoice generation failed")

# =================================================================
# PLATFORM-WIDE ANALYTICS (ADMIN ONLY)
# =================================================================

@router.get("/analytics/usage-trends")
async def get_platform_usage_trends(
    months: int = Query(6, ge=1, le=24, description="Number of months for trend analysis"),
    current_admin: User = Depends(require_platform_admin)
):
    """Get platform-wide usage trends (platform admins only)"""
    try:
        # TODO: Query database for platform-wide usage trends
        # For now, simulate trend data
        trends = {
            "total_tenants": 147,
            "active_tenants_this_month": 142,
            "total_api_calls_month": 2_450_000,
            "total_revenue_month": 12_750.50,
            "avg_revenue_per_tenant": 89.72,
            "growth_metrics": {
                "month_over_month_growth": 15.3,
                "year_over_year_growth": 245.7,
                "new_tenants_this_month": 12,
                "churned_tenants_this_month": 2
            },
            "feature_adoption": {
                "security.analytics": 89.1,  # % of tenants using
                "alerts.management": 76.5,
                "queries.advanced": 94.2,
                "ingestion.basic": 100.0
            },
            "top_consuming_tenants": [
                {"tenant_id": "tenant-001", "cost": 450.75},
                {"tenant_id": "tenant-042", "cost": 380.25},
                {"tenant_id": "tenant-089", "cost": 295.50}
            ]
        }
        
        return trends
        
    except Exception as e:
        logger.error("Platform usage trends failed", error=str(e))
        raise HTTPException(500, "Platform usage trends failed")

@router.get("/analytics/feature-usage")
async def get_feature_usage_analytics(
    tenant_id: Optional[str] = None,
    feature: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get detailed feature usage analytics"""
    try:
        # Check permissions based on scope
        if tenant_id:
            # Tenant-specific analytics
            is_tenant_user = any(
                r["tenant_id"] == tenant_id
                for r in request.state.roles
            ) if hasattr(request.state, "roles") else False
            
            if not is_tenant_user:
                raise HTTPException(403, f"No access to analytics for tenant {tenant_id}")
        else:
            # Platform-wide analytics - require platform admin
            is_platform_admin = any(
                r["tenant_id"] == "platform"
                for r in request.state.roles
            ) if hasattr(request.state, "roles") else False
            
            if not is_platform_admin:
                raise HTTPException(403, "Platform admin access required for platform-wide analytics")
        
        # TODO: Query database for feature usage analytics
        # For now, return simulated data
        analytics = {
            "scope": "tenant" if tenant_id else "platform",
            "tenant_id": tenant_id,
            "feature_filter": feature,
            "usage_analytics": {
                "ingestion.basic": {
                    "total_calls": 850_000,
                    "avg_calls_per_day": 28_333,
                    "cost_this_month": 8.50,
                    "trend": "+12.5%"
                },
                "queries.advanced": {
                    "total_calls": 45_000,
                    "avg_calls_per_day": 1_500,
                    "cost_this_month": 2.25,
                    "trend": "+8.3%"
                },
                "security.analytics": {
                    "total_calls": 12_000,
                    "avg_calls_per_day": 400,
                    "cost_this_month": 6.00,
                    "trend": "+25.1%"
                }
            },
            "generated_at": datetime.utcnow()
        }
        
        if feature:
            # Filter to specific feature
            if feature in analytics["usage_analytics"]:
                analytics["usage_analytics"] = {feature: analytics["usage_analytics"][feature]}
            else:
                analytics["usage_analytics"] = {}
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Feature usage analytics failed", error=str(e))
        raise HTTPException(500, "Feature usage analytics failed")

# =================================================================
# REAL-TIME USAGE TRACKING ENDPOINTS
# =================================================================

@router.get("/usage/realtime/{tenant_id}")
async def get_realtime_usage(
    tenant_id: str,
    window_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get real-time usage metrics for tenant"""
    try:
        # Check permissions
        is_platform_admin = any(
            r["tenant_id"] == "platform"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_user = any(
            r["tenant_id"] == tenant_id
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_user:
            raise HTTPException(403, f"No access to real-time data for tenant {tenant_id}")
        
        # Calculate time window
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=window_minutes)
        
        # TODO: Query database for real-time usage in time window
        # For now, simulate real-time data
        realtime_data = {
            "tenant_id": tenant_id,
            "time_window": {
                "start": start_time,
                "end": end_time,
                "duration_minutes": window_minutes
            },
            "api_calls_count": 245,
            "avg_response_time_ms": 125,
            "error_rate": 0.8,  # percentage
            "top_endpoints": [
                {"endpoint": "/v1/logs", "calls": 89, "avg_time": 95},
                {"endpoint": "/v1/query/advanced", "calls": 67, "avg_time": 450},
                {"endpoint": "/v1/security/events", "calls": 34, "avg_time": 180}
            ],
            "status_breakdown": {
                "2xx": 238,
                "4xx": 5,
                "5xx": 2
            }
        }
        
        return realtime_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Real-time usage retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Real-time usage retrieval failed")

# =================================================================
# USAGE EXPORT ENDPOINTS
# =================================================================

@router.get("/usage/export/{tenant_id}")
async def export_usage_data(
    tenant_id: str,
    format: str = Query("csv", regex="^(csv|json|xlsx)$", description="Export format"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Export usage data for tenant"""
    try:
        # Check permissions - platform admins, billing admins, or tenant admins
        is_platform_admin = any(
            r["tenant_id"] == "platform" and r["role"] in ["super_admin", "admin", "billing_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, f"No permission to export data for tenant {tenant_id}")
        
        # Parse date range
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        
        # TODO: Generate actual export file
        # For now, return export metadata
        export_data = {
            "tenant_id": tenant_id,
            "export_format": format,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "export_url": f"/v1/exports/{tenant_id}/usage-{start_date}-to-{end_date}.{format}",
            "generated_at": datetime.utcnow(),
            "generated_by": current_user.id,
            "estimated_records": 12547
        }
        
        logger.info("Usage export generated",
                   tenant_id=tenant_id,
                   format=format,
                   date_range=f"{start_date} to {end_date}",
                   generated_by=current_user.id)
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Usage export failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Usage export failed")

# =================================================================
# ADMIN USAGE MANAGEMENT ENDPOINTS
# =================================================================

@router.post("/admin/audit/bulk-insert")
async def bulk_insert_audit_records(
    audit_data: Dict[str, List[Dict[str, Any]]],
    current_admin: User = Depends(require_platform_admin)
):
    """Bulk insert audit records (for testing/migration)"""
    try:
        entries = audit_data.get("entries", [])
        
        if len(entries) > 1000:
            raise HTTPException(400, "Bulk insert limited to 1000 records")
        
        # Process and validate entries
        processed_entries = []
        for entry in entries:
            # Add missing fields
            entry.setdefault("request_timestamp", datetime.utcnow())
            entry.setdefault("id", str(uuid.uuid4()))
            processed_entries.append(entry)
        
        # Record usage batch
        await usage_analytics.record_usage_batch(processed_entries)
        
        logger.info("Bulk audit insert completed",
                   record_count=len(processed_entries),
                   inserted_by=current_admin.id)
        
        return {
            "inserted_count": len(processed_entries),
            "inserted_by": current_admin.id,
            "inserted_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bulk audit insert failed", error=str(e))
        raise HTTPException(500, "Bulk audit insert failed")

@router.get("/admin/database/partitions")
async def get_database_partitions(
    current_admin: User = Depends(require_platform_admin)
):
    """Get database partition information (platform admins only)"""
    try:
        # TODO: Query actual database partitions
        # For now, simulate partition data
        current_date = datetime.utcnow()
        partitions = []
        
        # Generate last 6 months of partitions
        for i in range(6):
            month_date = current_date - timedelta(days=30 * i)
            month_key = month_date.strftime("%Y%m")
            
            partitions.append({
                "partition_name": f"p{month_key}",
                "table_name": "api_usage_audit",
                "month": month_date.strftime("%Y-%m"),
                "record_count": 450000 - (i * 50000),  # Simulated
                "size_mb": 125.5 - (i * 15.2),
                "created_at": month_date.strftime("%Y-%m-01")
            })
        
        return {
            "partitions": partitions,
            "total_partitions": len(partitions),
            "queried_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error("Database partition query failed", error=str(e))
        raise HTTPException(500, "Database partition query failed")

# =================================================================
# COST MANAGEMENT ENDPOINTS
# =================================================================

@router.get("/costs/breakdown/{tenant_id}")
async def get_cost_breakdown(
    tenant_id: str,
    period: str = Query("current", regex="^(current|last-month|ytd)$", description="Period for breakdown"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Get detailed cost breakdown for tenant"""
    try:
        # Check permissions
        is_platform_admin = any(
            r["tenant_id"] == "platform" and r["role"] in ["super_admin", "admin", "billing_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] in ["tenant_admin"]
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_platform_admin and not is_tenant_admin:
            raise HTTPException(403, f"No access to cost data for tenant {tenant_id}")
        
        # TODO: Calculate actual cost breakdown from usage data
        # For now, return simulated breakdown
        breakdown = {
            "tenant_id": tenant_id,
            "period": period,
            "cost_breakdown": {
                "compute_costs": 125.50,
                "storage_costs": 45.25,
                "network_costs": 12.75,
                "feature_costs": {
                    "ingestion.basic": 85.00,
                    "queries.advanced": 25.50,
                    "security.analytics": 67.00,
                    "alerts.management": 5.00
                }
            },
            "total_cost": 238.50,
            "currency": "USD",
            "cost_per_gb": 0.045,
            "cost_per_api_call": 0.000195,
            "period_details": {
                "start_date": "2024-09-01",
                "end_date": "2024-09-30",
                "days_in_period": 30
            }
        }
        
        return breakdown
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cost breakdown failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Cost breakdown failed")

@router.post("/costs/alerts/{tenant_id}")
async def create_cost_alert(
    tenant_id: str,
    threshold_amount: float = Query(..., gt=0, description="Cost threshold in USD"),
    notification_email: str = Query(..., description="Email for notifications"),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Create cost threshold alert for tenant"""
    try:
        # Check permissions - tenant admins only
        is_tenant_admin = any(
            r["tenant_id"] == tenant_id and r["role"] == "tenant_admin"
            for r in request.state.roles
        ) if hasattr(request.state, "roles") else False
        
        if not is_tenant_admin:
            raise HTTPException(403, f"Tenant admin access required for {tenant_id}")
        
        # TODO: Create cost alert in database
        alert_id = f"cost-alert-{tenant_id}-{int(datetime.utcnow().timestamp())}"
        
        logger.info("Cost alert created",
                   alert_id=alert_id,
                   tenant_id=tenant_id,
                   threshold=threshold_amount,
                   notification_email=notification_email,
                   created_by=current_user.id)
        
        return {
            "alert_id": alert_id,
            "tenant_id": tenant_id,
            "threshold_amount": threshold_amount,
            "notification_email": notification_email,
            "created_at": datetime.utcnow(),
            "created_by": current_user.id,
            "status": "active"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cost alert creation failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(500, "Cost alert creation failed")

# =================================================================
# USAGE BUFFER MANAGEMENT (INTERNAL)
# =================================================================

@router.post("/admin/usage/flush-buffer")
async def flush_usage_buffer(
    current_admin: User = Depends(require_platform_admin)
):
    """Manually flush usage buffer (admin debugging)"""
    try:
        buffer_size = len(usage_buffer.buffer)
        await usage_buffer.flush_batch()
        
        logger.info("Usage buffer manually flushed",
                   records_flushed=buffer_size,
                   flushed_by=current_admin.id)
        
        return {
            "records_flushed": buffer_size,
            "flushed_at": datetime.utcnow(),
            "buffer_status": "empty"
        }
        
    except Exception as e:
        logger.error("Usage buffer flush failed", error=str(e))
        raise HTTPException(500, "Usage buffer flush failed")

@router.get("/admin/usage/buffer-status")
async def get_usage_buffer_status(
    current_admin: User = Depends(require_platform_admin)
):
    """Get current usage buffer status (admin debugging)"""
    try:
        return {
            "buffer_size": len(usage_buffer.buffer),
            "batch_size": usage_buffer.batch_size,
            "flush_interval": usage_buffer.flush_interval,
            "last_flush": usage_buffer._last_flush,
            "time_since_flush": time.time() - usage_buffer._last_flush,
            "status": "healthy" if len(usage_buffer.buffer) < usage_buffer.batch_size else "needs_flush"
        }
        
    except Exception as e:
        logger.error("Usage buffer status failed", error=str(e))
        raise HTTPException(500, "Usage buffer status failed")

# =================================================================
# GLOBAL SERVICE INSTANCES
# =================================================================

# Make services available for dependency injection
async def get_usage_analytics_service() -> UsageAnalyticsService:
    """Get usage analytics service instance"""
    return usage_analytics

async def get_role_service():
    """Get role service instance"""
    from role_api import role_service
    return role_service