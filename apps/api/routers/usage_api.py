"""
M8 API Usage Tracking & Billing API
FastAPI router for usage analytics, billing estimates, and cost tracking
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query, Header
from fastapi.responses import StreamingResponse
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import structlog
import uuid
import time
import json
import asyncio

from models import (
    UsageCurrentResponse, BillingEstimateResponse, UsageHistoryResponse,
    User
)
from authn_authz_middleware import (
    get_current_user, require_platform_admin,
    usage_buffer
)
from services.usage_service import UsageService

logger = structlog.get_logger()

# Create router for usage tracking
router = APIRouter(prefix="/v1", tags=["Usage Analytics & Billing"])

# =================================================================
# USAGE SERVICE INITIALIZATION
# =================================================================

# Global usage service instance
usage_service = UsageService()

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

        usage_data = await usage_service.get_tenant_usage_summary(tenant_id)

        return UsageCurrentResponse(
            tenant_id=usage_data["tenant_id"],
            api_calls=usage_data["current_month"]["api_calls"],
            feature_breakdown=usage_data["current_month"]["feature_breakdown"],
            cost_estimate=usage_data["billing"]["total_cost"],
            billing_period=usage_data["current_month"]["billing_period"]
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

        history_data = await usage_service.get_tenant_usage_analytics(tenant_id, f"{months}m")

        return UsageHistoryResponse(
            tenant_id=history_data["tenant_id"],
            usage_by_month=history_data["historical_data"]
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

        billing_data = await usage_service.get_billing_estimate(tenant_id)

        return BillingEstimateResponse(
            tenant_id=billing_data["tenant_id"],
            total_estimated_cost=billing_data["total_cost"],
            feature_costs={k: v["cost"] for k, v in billing_data.get("cost_breakdown", {}).items()},
            period=billing_data["billing_period"]
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
            last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
            month = last_month.strftime("%Y-%m")

        # IDEMPOTENCY CHECK - Check if invoice already exists for this period
        from dao.usage_dao import UsageDAO
        usage_dao = UsageDAO()
        
        existing_invoice = await usage_dao.get_existing_bill(tenant_id, month)
        if existing_invoice:
            logger.info("Invoice already exists for period", 
                       tenant_id=tenant_id, 
                       billing_period=month,
                       existing_invoice_id=existing_invoice["id"])
            
            return {
                "invoice_id": existing_invoice["id"],
                "tenant_id": tenant_id,
                "billing_period": month,
                "total_cost": existing_invoice.get("total_amount", 0.0),
                "currency": existing_invoice.get("currency", "USD"),
                "line_items": existing_invoice.get("usage_breakdown", {}),
                "generated_at": existing_invoice["generated_at"],
                "generated_by": existing_invoice.get("customer_id"),
                "status": "already_exists",
                "message": f"Invoice already generated for period {month}"
            }

        # Get usage data for the month
        # Get actual usage data from database
        usage_data = await usage_service.export_usage_report(tenant_id, "json", month)
        billing_data = usage_data["billing_data"]

        feature_usage = {}
        for feature, data in billing_data.get("cost_breakdown", {}).items():
            feature_usage[feature] = {
                "calls": data.get("api_calls", 0),
                "cost": data.get("cost", 0.0)
            }

        usage_data = {
            "tenant_id": tenant_id,
            "billing_period": month,
            "api_calls": sum(data.get("api_calls", 0) for data in billing_data.get("cost_breakdown", {}).values()),
            "feature_usage": feature_usage,
            "total_cost": billing_data.get("total_cost", 0.0),
            "currency": billing_data.get("currency", "USD")
        }

        # Create actual invoice record in database
        invoice_record = {
            "id": f"INV-{tenant_id}-{month}",
            "tenant_id": tenant_id,
            "billing_period": month,
            "total_cost": usage_data["total_cost"],
            "currency": usage_data["currency"],
            "line_items": usage_data["feature_usage"],
            "generated_at": datetime.now(timezone.utc),
            "generated_by": current_admin.id,
            "status": "generated"
        }
        
        # Store invoice in database via usage service
        invoice_id = await usage_service.create_invoice_record(invoice_record)

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
            "generated_at": datetime.now(timezone.utc),
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
        # Get platform-wide analytics from database
        platform_data = await usage_service.get_platform_analytics()

        # Get additional analytics from service
        growth_data = await usage_service.get_growth_metrics()
        feature_adoption = await usage_service.get_feature_adoption_rates()
        total_tenants = await usage_service.get_total_tenant_count()

        trends = {
            "total_tenants": total_tenants,
            "active_tenants_this_month": platform_data["platform_stats"].get("active_tenants_this_month", 0),
            "total_api_calls_month": platform_data["platform_stats"].get("total_api_calls_month", 0),
            "total_revenue_month": platform_data["metrics"].get("total_revenue_estimate", 0.0),
            "avg_revenue_per_tenant": platform_data["metrics"].get("avg_calls_per_tenant", 0) * 0.001,
            "growth_metrics": growth_data,
            "feature_adoption": feature_adoption,
            "top_consuming_tenants": [
                {"tenant_id": tenant["tenant_id"], "cost": await usage_service._estimate_tenant_revenue(tenant["tenant_id"])}
                for tenant in platform_data["top_tenants"][:3]
            ]
        }

        return trends

    except Exception as e:
        logger.error("Platform usage trends failed", error=str(e), exc_info=True)
        raise HTTPException(500, f"Platform usage trends failed: {str(e)}")

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

        # Query database for feature usage analytics
        if tenant_id:
            usage_data = await usage_service.get_tenant_usage_summary(tenant_id)
            feature_breakdown = usage_data["current_month"]["feature_breakdown"]
            cost_breakdown = usage_data["billing"]["cost_breakdown"]
        else:
            platform_data = await usage_service.get_platform_analytics()
            # For platform-wide, aggregate across all tenants from database
            feature_breakdown = await usage_service.get_platform_feature_breakdown()
            cost_breakdown = await usage_service.get_platform_cost_breakdown()

        usage_analytics_data = {}
        for feature_type, calls in feature_breakdown.items():
            cost_data = cost_breakdown.get(feature_type, {"cost": 0.0})
            # Calculate real trend from historical data
            trend = await usage_service.calculate_feature_trend(feature_type, tenant_id)
            usage_analytics_data[feature_type] = {
                "total_calls": calls,
                "avg_calls_per_day": calls // 30,
                "cost_this_month": cost_data.get("cost", 0.0),
                "trend": trend
            }

        analytics = {
            "scope": "tenant" if tenant_id else "platform",
            "tenant_id": tenant_id,
            "feature_filter": feature,
            "usage_analytics": usage_analytics_data,
            "generated_at": datetime.now(timezone.utc)
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
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=window_minutes)

        # Get real-time usage from database
        realtime_data = await usage_service.usage_dao.get_realtime_usage(tenant_id, window_minutes)

        # Get real status breakdown from database
        status_breakdown = await usage_service.get_status_breakdown(tenant_id, window_minutes)
        realtime_data["status_breakdown"] = status_breakdown

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
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Generate export using UsageService
        export_data = await usage_service.export_usage_report(tenant_id, format)

        # Add export metadata
        export_metadata = {
            "tenant_id": tenant_id,
            "export_format": format,
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "export_url": export_data.get("download_url", f"/v1/exports/{tenant_id}/usage-{start_date}-to-{end_date}.{format}"),
            "generated_at": datetime.now(timezone.utc),
            "generated_by": current_user.id,
            "estimated_records": sum(
                data.get("api_calls", 0)
                for data in export_data.get("billing_data", {}).get("cost_breakdown", {}).values()
            )
        }
        export_data = export_metadata

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
            entry.setdefault("request_timestamp", datetime.now(timezone.utc))
            entry.setdefault("id", str(uuid.uuid4()))
            processed_entries.append(entry)

        # Record usage batch using UsageService
        await usage_service.track_batch_usage(processed_entries)

        logger.info("Bulk audit insert completed",
                   record_count=len(processed_entries),
                   inserted_by=current_admin.id)

        return {
            "inserted_count": len(processed_entries),
            "inserted_by": current_admin.id,
            "inserted_at": datetime.now(timezone.utc)
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
        current_date = datetime.now(timezone.utc)
        partitions = []

        # Generate last 6 months of partitions
        for i in range(6):
            month_date = current_date - timedelta(days=30 * i)
            month_key = month_date.strftime("%Y%m")

            partitions.append({
                "partition_name": f"p{month_key}",
                "table_name": "api_usage_audit",
                "month": month_date.strftime("%Y-%m"),
                "record_count": await usage_service.get_partition_record_count(f"p{month_key}"),
                "size_mb": await usage_service.get_partition_size_mb(f"p{month_key}"),
                "created_at": month_date.strftime("%Y-%m-01")
            })

        return {
            "partitions": partitions,
            "total_partitions": len(partitions),
            "queried_at": datetime.now(timezone.utc)
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

        # Get actual cost breakdown from UsageService
        billing_data = await usage_service.get_billing_estimate(tenant_id)

        # Calculate feature costs from breakdown
        feature_costs = {}
        total_feature_cost = 0.0
        for feature, data in billing_data.get("cost_breakdown", {}).items():
            cost = data.get("cost", 0.0)
            feature_costs[feature] = cost
            total_feature_cost += cost

        # Estimate infrastructure costs (simplified)
        compute_costs = total_feature_cost * 0.6  # 60% of feature costs
        storage_costs = total_feature_cost * 0.3  # 30% of feature costs
        network_costs = total_feature_cost * 0.1  # 10% of feature costs

        breakdown = {
            "tenant_id": tenant_id,
            "period": period,
            "cost_breakdown": {
                "compute_costs": round(compute_costs, 2),
                "storage_costs": round(storage_costs, 2),
                "network_costs": round(network_costs, 2),
                "feature_costs": feature_costs
            },
            "total_cost": billing_data.get("total_cost", 0.0),
            "currency": billing_data.get("currency", "USD"),
            "cost_per_gb": await usage_service.get_current_cost_per_gb(),
            "cost_per_api_call": billing_data.get("total_cost", 0.0) / max(1, sum(
                data.get("api_calls", 0) for data in billing_data.get("cost_breakdown", {}).values()
            )),
            "period_details": {
                "start_date": f"{billing_data.get('billing_period', '2024-09')}-01",
                "end_date": f"{billing_data.get('billing_period', '2024-09')}-30",
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
        alert_id = f"cost-alert-{tenant_id}-{int(datetime.now(timezone.utc).timestamp())}"

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
            "created_at": datetime.now(timezone.utc),
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
            "flushed_at": datetime.now(timezone.utc),
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
            "time_since_flush": time.time() - getattr(usage_buffer, '_last_flush', time.time()),
            "status": "healthy" if len(usage_buffer.buffer) < usage_buffer.batch_size else "needs_flush"
        }

    except Exception as e:
        logger.error("Usage buffer status failed", error=str(e))
        raise HTTPException(500, "Usage buffer status failed")


def format_sse_message(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format data as Server-Sent Events message"""
    message = ""
    if event_id:
        message += f"id: {event_id}\n"
    message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data)}\n\n"
    return message


@router.get("/usage-stream/{tenant_id}")
async def stream_usage_data(
    tenant_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time usage data"""
    try:
        # Validate tenant access
        if customer_id != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to tenant data")
            
        async def generate_usage():
            while True:
                try:
                    # Get current usage statistics using real UsageService
                    usage_data = await usage_service.get_usage_summary(
                        customer_id=tenant_id,
                        start_date=datetime.now().date() - timedelta(days=1),
                        end_date=datetime.now().date()
                    )
                    
                    if usage_data:
                        yield format_sse_message("usage", usage_data)
                    
                    await asyncio.sleep(30)  # Update every 30 seconds
                    
                except Exception as e:
                    logger.error("Error streaming usage data", error=str(e), tenant_id=tenant_id)
                    yield format_sse_message("error", {"message": f"Usage streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_usage(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start usage stream", error=str(e), tenant_id=tenant_id)
        raise HTTPException(status_code=500, detail=f"Failed to start usage stream: {str(e)}")


# =================================================================
# GLOBAL SERVICE INSTANCES
# =================================================================

# Make services available for dependency injection
async def get_usage_service() -> UsageService:
    """Get usage service instance"""
    return usage_service

async def get_role_service():
    """Get role service instance"""
    from apps.api.routers.role_api import role_service
    return role_service
