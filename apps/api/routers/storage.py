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
# ENH-010: `StorageService()` opens a database connection in its constructor, so
# building it at import time made this router un-importable -- and untestable --
# without live infrastructure. Built on first use; the PEP 562 hook below
# preserves the bare `storage_service` name at every call site.
_storage_service_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the shared StorageService, constructing it on first use."""
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = StorageService()
    return _storage_service_instance


def _request_user_id(request: Request) -> Optional[str]:
    """The authenticated user's id.

    The auth middleware stores the user object as ``request.state.user``; it
    never sets ``request.state.user_id``.
    """
    user = getattr(request.state, "user", None)
    return getattr(user, "id", None)


async def _require_platform_role(request: Request, allowed_roles, detail: str) -> str:
    """403 unless the caller holds one of ``allowed_roles`` in the platform scope.

    Returns the caller's user id.
    """
    user_id = _request_user_id(request)
    if not user_id:
        raise HTTPException(status_code=403, detail="User context not found")

    from authn_authz_middleware import get_user_service

    roles = await get_user_service().get_user_tenant_roles(user_id, "platform")
    if not any(
        r.get("tenant_id") == "platform" and r.get("role") in allowed_roles
        for r in roles
    ):
        raise HTTPException(status_code=403, detail=detail)
    return user_id


def __getattr__(name: str):
    """Resolve `storage_service` lazily (PEP 562)."""
    if name == "storage_service":
        return get_storage_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def setup_dependencies(ttl_manager):
    """Setup dependencies from main app"""
    get_storage_service().set_ttl_manager(ttl_manager)

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
        result = await get_storage_service().create_retention_policy({
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
        
        policy = await get_storage_service().get_retention_policy(customer_id)
        
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
        result = await get_storage_service().update_retention_policy(
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
        result = await get_storage_service().trigger_cleanup_operation(customer_id, policy_name)
        
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
        result = await get_storage_service().trigger_archive_operation(customer_id)
        
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
async def get_infrastructure_health(request: Request, customer_id: str = MiddlewareTenant):
    """Get system-wide infrastructure health (Platform Admin only)"""
    try:
        user_id = await _require_platform_role(
            request,
            ('super_admin', 'admin', 'support_admin'),
            "Platform admin access required for infrastructure health check",
        )
        
        # Get infrastructure health information using storage service
        health_info = await get_storage_service().get_infrastructure_health()
        
        return {
            "infrastructure_health": health_info,
            "access_level": "platform_admin",
            "accessed_by": user_id,
            "checked_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Infrastructure health check failed: {str(e)}")

@router.get("/health")
async def get_customer_storage_health(customer_id: str = MiddlewareTenant):
    """Get customer-specific storage health (Tenant-level access)"""
    try:
        # Customer can only see their own storage health
        # This is enforced by the middleware tenant validation
        
        # Get comprehensive storage health information using storage service
        health_info = await get_storage_service().get_storage_health(customer_id)
        
        return health_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")

@router.get("/health/{target_customer_id}")
async def get_specific_customer_health(target_customer_id: str, request: Request, requesting_customer: str = MiddlewareTenant):
    """Get specific customer's storage health (Admin access or own data only)"""
    try:
        # Basic tenant isolation check
        if requesting_customer != target_customer_id:
            await _require_platform_role(
                request,
                ('super_admin', 'admin', 'support_admin'),
                "Admin access required to view other tenant's storage health",
            )
        
        # Get storage health for the target customer
        health_info = await get_storage_service().get_storage_health(target_customer_id)
        
        return health_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")

@router.post("/quota/sync")
async def trigger_storage_quota_sync(customer_id: str = MiddlewareTenant):
    """Trigger manual storage quota sync for the authenticated tenant"""
    try:
        from services.storage_quota_sync_service import storage_quota_sync_service
        
        # Trigger sync for the authenticated customer
        result = await storage_quota_sync_service.trigger_manual_sync(customer_id)
        
        return {
            "status": "completed",
            "customer_id": customer_id,
            "sync_result": result,
            "triggered_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage quota sync failed: {str(e)}")

@router.post("/quota/sync/all")
async def trigger_all_storage_quota_sync(request: Request, requesting_customer: str = MiddlewareTenant):
    """Trigger manual storage quota sync for all tenants (Platform Admin only)"""
    try:
        await _require_platform_role(
            request,
            ('super_admin', 'admin'),
            "Platform admin access required for system-wide storage quota sync",
        )
        
        from services.storage_quota_sync_service import storage_quota_sync_service
        
        # Trigger sync for all tenants
        result = await storage_quota_sync_service.trigger_manual_sync()
        
        return {
            "status": "completed",
            "sync_result": result,
            "triggered_by": requesting_customer,
            "user_id": user_id,
            "triggered_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System-wide storage quota sync failed: {str(e)}")

# Archive Retrieval APIs

@router.get("/archives/{customer_id}")
async def list_customer_archives(
    customer_id: str,
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    requesting_customer: str = MiddlewareTenant
):
    """List archived data for a customer with pagination and filtering"""
    try:
        # Validate tenant access
        if requesting_customer != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        archives = await get_storage_service().list_customer_archives(
            customer_id=customer_id,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "customer_id": customer_id,
            "archives": archives,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": len(archives)
            },
            "retrieved_at": datetime.now(timezone.utc)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list archives: {str(e)}")

@router.get("/archive/{archive_key:path}")
async def get_archive_metadata(
    archive_key: str,
    requesting_customer: str = MiddlewareTenant
):
    """Get metadata for a specific archive"""
    try:
        archive_info = await get_storage_service().get_archive_metadata(archive_key, requesting_customer)
        if not archive_info:
            raise HTTPException(status_code=404, detail="Archive not found")
        
        return {
            "archive_metadata": archive_info,
            "retrieved_at": datetime.now(timezone.utc)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get archive metadata: {str(e)}")

@router.post("/archive/{archive_key:path}/download")
async def download_archive(
    archive_key: str,
    request: Request,
    requesting_customer: str = MiddlewareTenant
):
    """Generate presigned URL or direct download for archived data"""
    try:
        # Get user ID from request context
        user_id = _request_user_id(request) or 'unknown'
        
        download_info = await get_storage_service().generate_archive_download(
            archive_key=archive_key,
            customer_id=requesting_customer,
            user_id=user_id
        )
        
        if not download_info:
            raise HTTPException(status_code=404, detail="Archive not found")
        
        return download_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download: {str(e)}")

@router.post("/query-archive")
async def query_archived_data(
    query_request: Dict[str, Any],
    request: Request,
    requesting_customer: str = MiddlewareTenant
):
    """Query data from archived files (experimental feature)"""
    try:
        # Extract parameters
        archive_keys = query_request.get("archive_keys", [])
        filters = query_request.get("filters", {})
        limit = query_request.get("limit", 1000)
        
        # Get user ID from request context
        user_id = _request_user_id(request) or 'unknown'
        
        results = await get_storage_service().query_archived_data(
            customer_id=requesting_customer,
            archive_keys=archive_keys,
            filters=filters,
            limit=limit,
            user_id=user_id
        )
        
        return {
            "customer_id": requesting_customer,
            "query_filters": filters,
            "results": results,
            "total_archives_searched": len(archive_keys),
            "queried_at": datetime.now(timezone.utc)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query archived data: {str(e)}")