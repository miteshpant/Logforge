"""
Storage and TTL management API endpoints
"""

from typing import Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from storage_config import get_customer_id
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/storage")

# Global instances (will be injected)
ttl_manager = None

def setup_dependencies(tm):
    """Setup dependencies from main app"""
    global ttl_manager
    ttl_manager = tm

class RetentionPolicyRequest(BaseModel):
    hot_retention_days: int
    cold_retention_days: int
    archive_retention_days: int
    compression_enabled: bool = True
    auto_deletion_enabled: bool = False

# TTL and Storage Management Endpoints

@router.get("/retention/{customer_id}")
async def get_retention_policy(customer_id: str, requesting_customer: str = MiddlewareTenant):
    """Get current retention policy for customer"""
    try:
        
        # Basic auth check - customers can only see their own policies
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not ttl_manager:
            raise HTTPException(status_code=500, detail="TTL manager not initialized")
        
        policy = ttl_manager.get_retention_policy(customer_id)
        
        return {
            "customer_id": customer_id,
            "retention_policy": policy,
            "retrieved_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get retention policy: {str(e)}")

@router.put("/retention/{customer_id}")
async def update_retention_policy(
    customer_id: str, 
    policy_request: RetentionPolicyRequest, 
    requesting_customer: str = MiddlewareTenant
):
    """Update retention policy for customer"""
    try:
        
        # Basic auth check - customers can only update their own policies
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not ttl_manager:
            raise HTTPException(status_code=500, detail="TTL manager not initialized")
        
        # Update policy
        success = ttl_manager.update_retention_policy(customer_id, policy_request.model_dump())
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update retention policy")
        
        return {
            "status": "updated",
            "customer_id": customer_id,
            "policy": policy_request.model_dump(),
            "updated_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update retention policy: {str(e)}")

@router.post("/cleanup")
async def trigger_cleanup(cleanup_request: Dict[str, Any] = None, customer_id: str = MiddlewareTenant):
    """Trigger manual cleanup based on TTL policies"""
    try:
        
        if not ttl_manager:
            raise HTTPException(status_code=500, detail="TTL manager not initialized")
        
        # Trigger cleanup
        result = await ttl_manager.cleanup_expired_data()
        
        return {
            "status": "completed",
            "cleanup_stats": result or {},
            "triggered_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.post("/archive/{customer_id}")
async def archive_old_data(customer_id: str, requesting_customer: str = MiddlewareTenant):
    """Archive old data to cold storage"""
    try:
        
        # Basic auth check
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not ttl_manager:
            raise HTTPException(status_code=500, detail="TTL manager not initialized")
        
        # Trigger archival
        result = await ttl_manager.archive_data(customer_id)
        
        return {
            "status": "archival_started",
            "customer_id": customer_id,
            "result": result,
            "started_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Archival failed: {str(e)}")

@router.get("/health")
async def storage_health_check(customer_id: str = MiddlewareTenant):
    """Get storage system health and capacity information"""
    try:
        
        # This would check ClickHouse, S3, and other storage components
        health_info = {
            "status": "healthy",
            "overall_stats": {
                "total_logs": 12000,  # Mock data for M1 testing
                "total_customers": 5,
                "total_storage_gb": 45.2,
                "hot_storage_gb": 30.1,
                "cold_storage_gb": 15.1
            },
            "clickhouse": {
                "status": "connected",
                "disk_usage_percent": 45.2,
                "available_space_gb": 1500.5
            },
            "cold_storage": {
                "status": "accessible",
                "provider": "s3",
                "total_archived_gb": 250.8
            },
            "ttl_policies": {
                "active_policies": 3,
                "next_cleanup": "2025-08-29T04:00:00Z"
            },
            "checked_at": datetime.now(timezone.utc)
        }
        
        return health_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")