"""
Tenant Validation Dependencies
=============================
FastAPI dependencies for tenant UUID validation across all endpoints
"""

import structlog
from fastapi import Header, HTTPException, Depends, Request
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
    
    # Track API usage - REMOVED: Handled by authentication middleware to prevent duplicates
    # await tenant_service.track_usage(x_customer_id, "api_call")
    
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
    
    # Track API usage for valid tenants - REMOVED: Handled by authentication middleware to prevent duplicates
    # if validated_id != "default":
    #     await tenant_service.track_usage(validated_id, "api_call")
    
    return validated_id

async def require_valid_tenant(
    x_customer_id: str = Header(..., alias="X-Customer-ID"),
    request: Request = None
) -> str:
    """Require valid tenant UUID (no fallback to default)"""
    
    if not x_customer_id:
        raise HTTPException(
            status_code=400,
            detail="X-Customer-ID header is required"
        )
    
    # Allow "platform" only for platform admin operations
    if x_customer_id == "platform":
        # Validate user has platform admin roles
        if not hasattr(request.state, "roles"):
            logger.warning("Platform access attempted without role information", tenant_id=x_customer_id)
            raise HTTPException(
                status_code=403,
                detail="Platform access requires authentication"
            )
        
        # Check if user has platform admin roles
        platform_roles = [r for r in request.state.roles if r["tenant_id"] == "platform"]
        if not platform_roles:
            logger.warning("Platform access attempted by non-platform admin", tenant_id=x_customer_id, user_roles=[r["role"] for r in request.state.roles])
            raise HTTPException(
                status_code=403,
                detail="Platform admin access required"
            )
        
        logger.info("Platform admin access granted", tenant_id=x_customer_id, platform_roles=[r["role"] for r in platform_roles])
        return x_customer_id
    
    # Validate tenant UUID
    is_valid = await tenant_service.validate_tenant_uuid(x_customer_id)
    if not is_valid:
        logger.warning("Invalid tenant UUID required", tenant_id=x_customer_id)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tenant UUID: {x_customer_id}"
        )
    
    # Track API usage - REMOVED: Handled by authentication middleware to prevent duplicates
    # await tenant_service.track_usage(x_customer_id, "api_call")
    
    return x_customer_id

async def get_middleware_tenant_id(request: Request) -> str:
    """Get tenant ID from middleware-validated request state"""
    if hasattr(request.state, 'tenant_id') and request.state.tenant_id:
        return request.state.tenant_id
    
    # Fallback to header validation for non-middleware endpoints
    tenant_id = request.headers.get("X-Customer-ID")
    if not tenant_id:
        raise HTTPException(400, "X-Customer-ID header required")
    
    return tenant_id

# Commonly used aliases
ValidatedTenant = Depends(validate_tenant_header)
RequiredTenant = Depends(require_valid_tenant)
TenantOrDefault = Depends(get_validated_tenant_id)
MiddlewareTenant = Depends(get_middleware_tenant_id)