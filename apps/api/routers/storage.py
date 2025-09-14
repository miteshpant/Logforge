"""
Storage and TTL management API endpoints
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from services.storage_service import StorageService
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/storage")

# Initialize storage service
storage_service = StorageService()

def setup_dependencies(ttl_manager):
    """Setup dependencies from main app"""
    storage_service.set_ttl_manager(ttl_manager)

class RetentionPolicyRequest(BaseModel):
    hot_retention_days: int
    cold_retention_days: int
    archive_retention_days: int
    compression_enabled: bool = True
    auto_deletion_enabled: bool = False

# TTL and Storage Management Endpoints

@router.post("/retention/{customer_id}")
async def create_retention_policy(
    customer_id: str, 
    policy_request: RetentionPolicyRequest, 
    requesting_customer: str = MiddlewareTenant
):
    """Create a new retention policy for customer"""
    try:
        # Basic auth check - customers can only create their own policies
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Create policy using storage service
        result = await storage_service.create_retention_policy({
            "customer_id": customer_id,
            "policy_name": "default",
            "hot_retention_days": policy_request.hot_retention_days,
            "cold_retention_days": policy_request.cold_retention_days,
            "archive_retention_days": policy_request.archive_retention_days,
            "compression_enabled": policy_request.compression_enabled,
            "auto_deletion_enabled": policy_request.auto_deletion_enabled
        })
        
        return {
            "status": "created",
            "customer_id": customer_id,
            "policy": result,
            "created_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create retention policy: {str(e)}")

@router.get("/retention/{customer_id}")
async def get_retention_policy(customer_id: str, requesting_customer: str = MiddlewareTenant):
    """Get current retention policy for customer"""
    try:
        # Basic auth check - customers can only see their own policies
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        policy = await storage_service.get_retention_policy(customer_id)
        
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
        
        # Update policy using storage service
        result = await storage_service.update_retention_policy(
            customer_id, 
            "default",  # policy_name
            {
                "hot_retention_days": policy_request.hot_retention_days,
                "cold_retention_days": policy_request.cold_retention_days,
                "archive_retention_days": policy_request.archive_retention_days,
                "compression_enabled": policy_request.compression_enabled,
                "auto_deletion_enabled": policy_request.auto_deletion_enabled
            }
        )
        
        return {
            "status": "updated",
            "customer_id": customer_id,
            "policy": result,
            "updated_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update retention policy: {str(e)}")

@router.post("/cleanup")
async def trigger_cleanup(cleanup_request: Optional[Dict[str, Any]] = None, customer_id: str = MiddlewareTenant):
    """Trigger manual cleanup based on TTL policies"""
    try:
        # Extract policy name from request if provided
        policy_name = None
        if cleanup_request and "policy_name" in cleanup_request:
            policy_name = cleanup_request["policy_name"]
        
        # Trigger cleanup using storage service
        result = await storage_service.trigger_cleanup_operation(customer_id, policy_name)
        
        return {
            "status": "completed",
            "cleanup_stats": result,
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
        
        # Trigger archival using storage service
        result = await storage_service.trigger_archive_operation(customer_id)
        
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

@router.get("/health/infrastructure")
async def get_infrastructure_health(customer_id: str = MiddlewareTenant):
    """Get system-wide infrastructure health (Admin-only access)"""
    try:
        # TODO: Add admin access check here
        # For now, we'll implement the check in a future admin authorization system
        # if not is_admin(customer_id):
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get infrastructure health information using storage service
        health_info = await storage_service.get_infrastructure_health()
        
        return {
            "infrastructure_health": health_info,
            "access_level": "admin",
            "checked_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Infrastructure health check failed: {str(e)}")

@router.get("/health")
async def get_customer_storage_health(customer_id: str = MiddlewareTenant):
    """Get customer-specific storage health (Tenant-level access)"""
    try:
        # Customer can only see their own storage health
        # This is enforced by the middleware tenant validation
        
        # Get comprehensive storage health information using storage service
        health_info = await storage_service.get_storage_health(customer_id)
        
        return health_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")

@router.get("/health/{target_customer_id}")
async def get_specific_customer_health(target_customer_id: str, requesting_customer: str = MiddlewareTenant):
    """Get specific customer's storage health (Admin access or own data only)"""
    try:
        # Basic tenant isolation check
        if requesting_customer != target_customer_id:
            # TODO: Add admin access check here
            # For now, block cross-tenant access (will be enhanced with admin roles)
            # if not is_admin(requesting_customer):
            raise HTTPException(status_code=403, detail="Access denied - can only view own storage health")
        
        # Get storage health for the target customer
        health_info = await storage_service.get_storage_health(target_customer_id)
        
        return health_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")