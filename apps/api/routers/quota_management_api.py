"""
Quota Management API - Administrative endpoints for quota reset management
Provides endpoints for monitoring and controlling the automated quota reset system
"""

import structlog
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from datetime import datetime, timezone

from services.quota_reset_service import get_quota_reset_service, get_quota_reset_scheduler
from tenant_dependencies import RequiredTenant, TenantOrDefault, MiddlewareTenant
from models import BaseResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/admin/quotas")

@router.get("/reset-schedule", response_model=Dict[str, Any])
async def get_quota_reset_schedule(
    customer_id: str = MiddlewareTenant
):
    """Get current quota reset schedule and configuration"""
    try:
        schedule_info = await get_quota_reset_service().get_quota_reset_schedule()
        
        return {
            "status": "success",
            "data": schedule_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get quota reset schedule", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quota reset schedule")

@router.post("/check-and-reset", response_model=Dict[str, Any])
async def trigger_quota_reset_check(
    customer_id: str = MiddlewareTenant
):
    """Manually trigger quota reset check (admin operation)"""
    try:
        # Only allow platform admins to trigger manual resets
        if customer_id != "platform":
            raise HTTPException(status_code=403, detail="Only platform admins can trigger manual quota resets")
        
        logger.info("Manual quota reset check triggered", admin_customer_id=customer_id)
        
        # Run quota reset check
        reset_summary = await get_quota_reset_service().check_and_reset_quotas()
        
        return {
            "status": "success",
            "message": "Quota reset check completed",
            "data": reset_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Manual quota reset check failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Quota reset check failed: {str(e)}")

@router.post("/reset-tenant/{tenant_id}", response_model=Dict[str, Any])
async def force_reset_tenant_quotas(
    tenant_id: str,
    quota_types: Optional[List[str]] = None,
    customer_id: str = MiddlewareTenant
):
    """Force reset specific tenant quotas (admin operation)"""
    try:
        # SECURITY: Only platform admins can reset quotas (affects billing and SLA)
        if customer_id != "platform":
            raise HTTPException(status_code=403, detail="Only platform administrators can reset tenant quotas")
        
        logger.info("Force quota reset requested", 
                   target_tenant_id=tenant_id, 
                   quota_types=quota_types,
                   admin_customer_id=customer_id)
        
        # Validate quota types if provided
        valid_quota_types = ['daily_ingestion', 'monthly_ingestion', 'storage_gb', 'api_calls', 'users', 'alerts']
        if quota_types:
            invalid_types = [qt for qt in quota_types if qt not in valid_quota_types]
            if invalid_types:
                raise HTTPException(status_code=400, detail=f"Invalid quota types: {invalid_types}")
        
        # Force reset tenant quotas
        reset_results = await get_quota_reset_service().force_reset_tenant_quotas(tenant_id, quota_types)
        
        return {
            "status": "success",
            "message": f"Force reset completed for tenant {tenant_id}",
            "data": reset_results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Force quota reset failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Force quota reset failed: {str(e)}")

@router.get("/usage-history/{tenant_id}", response_model=Dict[str, Any])
async def get_tenant_quota_history(
    tenant_id: str,
    quota_type: Optional[str] = None,
    months: int = 6,
    customer_id: str = MiddlewareTenant
):
    """Get historical quota usage data for tenant (tenant can view own data)"""
    try:
        # Tenant isolation - only allow access to own data or platform admin
        if customer_id != "platform" and customer_id != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to tenant quota history")
        
        # Validate quota type if provided
        valid_quota_types = ['daily_ingestion', 'monthly_ingestion', 'storage_gb', 'api_calls', 'users', 'alerts']
        if quota_type and quota_type not in valid_quota_types:
            raise HTTPException(status_code=400, detail=f"Invalid quota type: {quota_type}")
        
        # Limit months to reasonable range
        months = min(max(months, 1), 24)  # Between 1 and 24 months
        
        # Build query filters
        filters = {"tenant_id": tenant_id}
        if quota_type:
            filters["quota_type"] = quota_type
        
        # Calculate date range
        from datetime import timedelta
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30 * months)
        
        # Query historical usage data
        from database_layer import DatabaseLayer
        db = DatabaseLayer("QuotaHistoryAPI", "quota-history-api-key")
        
        query = """
        SELECT 
            tenant_id,
            quota_type,
            usage_amount,
            quota_limit,
            reset_period_start,
            reset_period_end,
            billing_period,
            reset_reason,
            created_at
        FROM quota_usage_history_mt
        WHERE tenant_id = %(tenant_id)s
        AND reset_period_end >= %(start_date)s
        AND reset_period_end <= %(end_date)s
        """ + (f"AND quota_type = %(quota_type)s" if quota_type else "") + """
        ORDER BY reset_period_end DESC, quota_type
        LIMIT 1000
        """
        
        query_params = {
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date
        }
        if quota_type:
            query_params["quota_type"] = quota_type
        
        history_records = await db.execute_query(query, query_params)
        
        # Format response
        history_data = []
        for record in history_records:
            history_data.append({
                "quota_type": record["quota_type"],
                "usage_amount": record["usage_amount"],
                "quota_limit": record["quota_limit"],
                "utilization_percent": round((record["usage_amount"] / record["quota_limit"]) * 100, 2) if record["quota_limit"] > 0 else 0,
                "reset_period_start": record["reset_period_start"].isoformat(),
                "reset_period_end": record["reset_period_end"].isoformat(),
                "billing_period": record["billing_period"],
                "reset_reason": record["reset_reason"],
                "created_at": record["created_at"].isoformat()
            })
        
        return {
            "status": "success",
            "data": {
                "tenant_id": tenant_id,
                "quota_type_filter": quota_type,
                "months_requested": months,
                "records_found": len(history_data),
                "history": history_data
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tenant quota history", 
                    tenant_id=tenant_id, 
                    quota_type=quota_type, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quota history")

@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    customer_id: str = MiddlewareTenant
):
    """Get quota reset scheduler status"""
    try:
        # Only allow platform admins to view scheduler status
        if customer_id != "platform":
            raise HTTPException(status_code=403, detail="Only platform admins can view scheduler status")
        
        scheduler = get_quota_reset_scheduler()
        service = get_quota_reset_service()
        
        scheduler_status = {
            "scheduler_running": scheduler.running,
            "check_interval_minutes": scheduler.check_interval,
            "configuration": service.reset_config,
            "service_status": "active"
        }
        
        return {
            "status": "success",
            "data": scheduler_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get scheduler status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")

@router.post("/scheduler/start", response_model=BaseResponse)
async def start_quota_scheduler(
    background_tasks: BackgroundTasks,
    customer_id: str = MiddlewareTenant
):
    """Start the quota reset scheduler"""
    try:
        # Only allow platform admins to control scheduler
        if customer_id != "platform":
            raise HTTPException(status_code=403, detail="Only platform admins can control scheduler")
        
        scheduler = get_quota_reset_scheduler()
        
        if scheduler.running:
            return BaseResponse(
                status="success",
                message="Quota reset scheduler is already running"
            )
        
        # Start scheduler in background
        background_tasks.add_task(scheduler.start_scheduler)
        
        logger.info("Quota reset scheduler started", admin_customer_id=customer_id)
        
        return BaseResponse(
            status="success",
            message="Quota reset scheduler started successfully"
        )
        
    except Exception as e:
        logger.error("Failed to start scheduler", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start scheduler")

@router.post("/scheduler/stop", response_model=BaseResponse)
async def stop_quota_scheduler(
    customer_id: str = MiddlewareTenant
):
    """Stop the quota reset scheduler"""
    try:
        # Only allow platform admins to control scheduler
        if customer_id != "platform":
            raise HTTPException(status_code=403, detail="Only platform admins can control scheduler")
        
        scheduler = get_quota_reset_scheduler()
        
        if not scheduler.running:
            return BaseResponse(
                status="success",
                message="Quota reset scheduler is already stopped"
            )
        
        scheduler.stop_scheduler()
        
        logger.info("Quota reset scheduler stopped", admin_customer_id=customer_id)
        
        return BaseResponse(
            status="success",
            message="Quota reset scheduler stopped successfully"
        )
        
    except Exception as e:
        logger.error("Failed to stop scheduler", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to stop scheduler")

# =================================================================
# TENANT-FACING QUOTA ENDPOINTS (non-admin)
# =================================================================

@router.get("/current/{tenant_id}", response_model=Dict[str, Any])
async def get_current_quota_status(
    tenant_id: str,
    customer_id: str = MiddlewareTenant
):
    """Get current quota status for tenant (tenant can view own data)"""
    try:
        # Tenant isolation - only allow access to own data or platform admin
        if customer_id != "platform" and customer_id != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied to tenant quota status")
        
        # Query current quotas
        from database_layer import DatabaseLayer
        db = DatabaseLayer("QuotaViewAPI", "quota-view-api-key")
        
        query = """
        SELECT 
            quota_type,
            quota_limit,
            current_usage,
            reset_period,
            last_reset,
            round((current_usage / quota_limit) * 100, 2) as utilization_percent
        FROM tenant_quotas_v
        WHERE tenant_id = %(tenant_id)s
        ORDER BY quota_type
        """
        
        quotas = await db.execute_query(query, {"tenant_id": tenant_id})
        
        # Format response
        quota_status = []
        for quota in quotas:
            quota_status.append({
                "quota_type": quota["quota_type"],
                "limit": quota["quota_limit"],
                "current_usage": quota["current_usage"],
                "utilization_percent": quota["utilization_percent"],
                "reset_period": quota["reset_period"],
                "last_reset": quota["last_reset"].isoformat(),
                "status": "approaching_limit" if quota["utilization_percent"] > 80 else 
                         "over_limit" if quota["utilization_percent"] > 100 else "normal"
            })
        
        return {
            "status": "success",
            "data": {
                "tenant_id": tenant_id,
                "quotas": quota_status,
                "total_quotas": len(quota_status)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get quota status", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get quota status")

@router.post("/reset-request/{tenant_id}", response_model=BaseResponse)
async def request_quota_reset(
    tenant_id: str,
    quota_types: List[str],
    justification: str,
    customer_id: str = MiddlewareTenant
):
    """Request quota reset from platform admin (tenant self-service)"""
    try:
        # Tenant isolation - only allow requests for own tenant
        if customer_id != "platform" and customer_id != tenant_id:
            raise HTTPException(status_code=403, detail="Can only request reset for your own tenant")
        
        # Validate inputs
        valid_quota_types = ['daily_ingestion', 'monthly_ingestion', 'storage_gb', 'api_calls', 'users', 'alerts']
        invalid_types = [qt for qt in quota_types if qt not in valid_quota_types]
        if invalid_types:
            raise HTTPException(status_code=400, detail=f"Invalid quota types: {invalid_types}")
        
        if not justification or len(justification.strip()) < 10:
            raise HTTPException(status_code=400, detail="Justification must be at least 10 characters")
        
        # TODO: In production, this would create a support ticket or notification
        # For now, we'll log the request and return a response
        
        logger.info("Quota reset request submitted", 
                   tenant_id=tenant_id,
                   quota_types=quota_types,
                   justification=justification,
                   requested_by_customer=customer_id)
        
        # TODO: Store in quota_reset_requests table
        # TODO: Send notification to platform admins
        # TODO: Integration with support ticket system
        
        return BaseResponse(
            status="success",
            message=f"Quota reset request submitted for {', '.join(quota_types)}. "
                   "Platform administrators will review your request and respond within 24 hours."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit quota reset request", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to submit quota reset request")