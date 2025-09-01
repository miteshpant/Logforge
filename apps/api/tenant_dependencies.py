"""
Tenant Validation Dependencies
=============================
FastAPI dependencies for tenant UUID validation across all endpoints
"""

import structlog
from fastapi import Header, HTTPException, Depends
from typing import Optional

from tenant_service import tenant_service

logger = structlog.get_logger()

async def validate_tenant_header(
    x_customer_id: str = Header(default="default", alias="X-Customer-ID")
) -> str:
    """Validate tenant UUID from X-Customer-ID header"""
    
    # Allow default for backward compatibility
    if x_customer_id == "default":
        return x_customer_id
    
    # Validate tenant UUID
    is_valid = await tenant_service.validate_tenant_uuid(x_customer_id)
    if not is_valid:
        logger.warning("Invalid tenant UUID provided", tenant_id=x_customer_id)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tenant UUID: {x_customer_id}. Use valid UUID or 'default'"
        )
    
    # Track API usage
    await tenant_service.track_usage(x_customer_id, "api_call")
    
    return x_customer_id

async def get_validated_tenant_id(
    x_customer_id: str = Header(default="default", alias="X-Customer-ID")
) -> str:
    """Get validated tenant ID with automatic fallback to default"""
    
    # If no header provided or empty, use default
    if not x_customer_id:
        return "default"
    
    # Allow default explicitly
    if x_customer_id == "default":
        return x_customer_id
    
    # Validate tenant UUID exists
    validated_id = await tenant_service.get_tenant_by_uuid_or_default(x_customer_id)
    
    # Track API usage for valid tenants
    if validated_id != "default":
        await tenant_service.track_usage(validated_id, "api_call")
    
    return validated_id

async def require_valid_tenant(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
) -> str:
    """Require valid tenant UUID (no fallback to default)"""
    
    if not x_customer_id:
        raise HTTPException(
            status_code=400,
            detail="X-Customer-ID header is required"
        )
    
    # Validate tenant UUID
    is_valid = await tenant_service.validate_tenant_uuid(x_customer_id)
    if not is_valid:
        logger.warning("Invalid tenant UUID required", tenant_id=x_customer_id)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tenant UUID: {x_customer_id}"
        )
    
    # Track API usage
    await tenant_service.track_usage(x_customer_id, "api_call")
    
    return x_customer_id

# Commonly used aliases
ValidatedTenant = Depends(validate_tenant_header)
RequiredTenant = Depends(require_valid_tenant)
TenantOrDefault = Depends(get_validated_tenant_id)