"""
Tenant Management API
====================
FastAPI endpoints for tenant lifecycle management
"""

import structlog
from fastapi import APIRouter, HTTPException, Header, Query, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime

from models import (
    TenantCreate, TenantUpdate, TenantResponse, TenantListResponse,
    StorageConfig, StorageStatusResponse, TenantQuotas, TenantConfig,
    LegalHoldRequest, TenantUsageResponse, TenantHealthResponse,
    TenantType, TenantStatus
)
# ENH-033/ENH-010: resolved lazily; importing the singleton connected to
# the database at import time and made this module untestable offline.
from tenant_service import get_tenant_service

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])

# Tenant CRUD Operations
@router.post("", status_code=201)
async def create_tenant(request: TenantCreate) -> TenantResponse:
    """Create a new tenant with UUID generation"""
    try:
        tenant = await get_tenant_service().create_tenant(request)

        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            type=tenant.type,
            status=tenant.status,
            primary_contact_name=tenant.primary_contact_name,
            primary_contact_email=tenant.primary_contact_email,
            industry=tenant.industry,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )
    except Exception as e:
        logger.error("Tenant creation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.get("")
async def list_tenants(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    status: Optional[TenantStatus] = Query(None, description="Filter by status"),
    type: Optional[TenantType] = Query(None, description="Filter by type")
) -> TenantListResponse:
    """List tenants with pagination and filtering"""
    try:
        return await get_tenant_service().list_tenants(
            page=page,
            page_size=page_size,
            status_filter=status,
            type_filter=type
        )
    except Exception as e:
        logger.error("Tenant listing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_tenant_stats() -> Dict[str, Any]:
    """Get lightweight tenant statistics for dashboard (performance optimized)"""
    try:
        return await get_tenant_service().get_tenant_stats()
    except Exception as e:
        logger.error("Tenant stats retrieval failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str) -> TenantResponse:
    """Get tenant details by ID"""
    try:
        tenant = await get_tenant_service().get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Return 404 for decommissioned/inactive tenants (they exist but are not accessible)
        if tenant.status == TenantStatus.INACTIVE:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            type=tenant.type,
            status=tenant.status,
            primary_contact_name=tenant.primary_contact_name,
            primary_contact_email=tenant.primary_contact_email,
            industry=tenant.industry,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tenant retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, request: TenantUpdate) -> TenantResponse:
    """Update tenant information"""
    try:
        tenant = await get_tenant_service().update_tenant(tenant_id, request)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return TenantResponse(
            tenant_id=tenant.tenant_id,
            name=tenant.name,
            type=tenant.type,
            status=tenant.status,
            primary_contact_name=tenant.primary_contact_name,
            primary_contact_email=tenant.primary_contact_email,
            industry=tenant.industry,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Tenant update failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{tenant_id}")
async def decommission_tenant(
    tenant_id: str,
    reason: str = Query("", description="Decommissioning reason"),
    data_retention: str = Query("backup", description="Data retention strategy"),
    backup_required: bool = Query(True, description="Require backup before deletion")
) -> Dict[str, Any]:
    """Securely decommission tenant"""
    try:
        result = await get_tenant_service().decommission_tenant(
            tenant_id=tenant_id,
            reason=reason,
            data_retention=data_retention,
            backup_required=backup_required
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant decommissioning failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Storage Management
@router.post("/{tenant_id}/storage/configure")
async def configure_storage(tenant_id: str, request: StorageConfig) -> Dict[str, Any]:
    """Configure storage backend for tenant"""
    try:
        result = await get_tenant_service().configure_storage(tenant_id, request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Storage configuration failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tenant_id}/storage/test-connection")
async def test_storage_connection(tenant_id: str) -> Dict[str, Any]:
    """Test storage connectivity"""
    try:
        result = await get_tenant_service().test_storage_connection(tenant_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Storage connection test failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/storage/status")
async def get_storage_status(tenant_id: str) -> StorageStatusResponse:
    """Get storage status and usage"""
    try:
        return await get_tenant_service().get_storage_status(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Storage status retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Usage & Billing
@router.get("/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str) -> TenantUsageResponse:
    """Get tenant usage statistics and billing data"""
    try:
        return await get_tenant_service().get_tenant_usage(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant usage retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/quotas")
async def get_tenant_quotas(tenant_id: str) -> TenantQuotas:
    """Get tenant quotas and limits"""
    try:
        return await get_tenant_service().get_tenant_quotas(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant quotas retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tenant_id}/quotas")
async def update_tenant_quotas(tenant_id: str, request: TenantQuotas) -> TenantQuotas:
    """Update tenant quotas and limits"""
    try:
        return await get_tenant_service().update_tenant_quotas(tenant_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant quotas update failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Configuration & Compliance
@router.get("/{tenant_id}/config")
async def get_tenant_config(tenant_id: str) -> TenantConfig:
    """Get tenant configuration"""
    try:
        return await get_tenant_service().get_tenant_config(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant config retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tenant_id}/config")
async def update_tenant_config(tenant_id: str, request: TenantConfig) -> TenantConfig:
    """Update tenant configuration"""
    try:
        return await get_tenant_service().update_tenant_config(tenant_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant config update failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/compliance")
async def get_compliance_status(tenant_id: str) -> Dict[str, Any]:
    """Get compliance status and reports"""
    try:
        return await get_tenant_service().get_compliance_status(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Compliance status retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tenant_id}/legal-hold")
async def create_legal_hold(tenant_id: str, request: LegalHoldRequest) -> Dict[str, Any]:
    """Create legal hold for data preservation"""
    try:
        return await get_tenant_service().create_legal_hold(tenant_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Legal hold creation failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Health & Monitoring
@router.get("/{tenant_id}/health")
async def get_tenant_health(tenant_id: str) -> TenantHealthResponse:
    """Get tenant health status"""
    try:
        return await get_tenant_service().get_tenant_health(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant health retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/metrics")
async def get_tenant_metrics(tenant_id: str) -> Dict[str, Any]:
    """Get tenant performance metrics and analytics"""
    try:
        return await get_tenant_service().get_tenant_metrics(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant metrics retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tenant_id}/alerts")
async def get_tenant_alerts(tenant_id: str) -> Dict[str, Any]:
    """Get tenant-specific alerts configuration"""
    try:
        return await get_tenant_service().get_tenant_alerts(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Tenant alerts retrieval failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Utility endpoints
@router.get("/{tenant_id}/validate")
async def validate_tenant(tenant_id: str) -> Dict[str, Any]:
    """Validate tenant UUID and existence"""
    try:
        is_valid = await get_tenant_service().validate_tenant_uuid(tenant_id)
        # For database-backed implementation, validate_tenant_uuid already checks existence
        return {
            "tenant_id": tenant_id,
            "valid": is_valid,
            "exists": is_valid,  # If valid, then it exists in database
            "validated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Tenant validation failed", tenant_id=tenant_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
