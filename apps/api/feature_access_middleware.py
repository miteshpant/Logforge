"""
Feature Access Middleware
Enforces tenant feature subscriptions with 403 responses for unauthorized access
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from subscription_service import subscription_service
import time

class FeatureAccessMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce feature access based on tenant subscriptions"""
    
    def __init__(self, app):
        super().__init__(app)
        self.subscription_service = subscription_service
        
        # Endpoints that don't require feature validation
        self.public_endpoints = {
            "/health",
            "/",
            "/docs", 
            "/openapi.json",
            "/v1/tenants",  # Tenant creation
            "/redoc"
        }
        
        # Admin endpoints that bypass feature checks
        self.admin_endpoints = {
            "/v1/admin/",
            "/v1/test-runner/"
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request and enforce feature access"""
        start_time = time.time()
        
        # Skip validation for public endpoints
        if self._is_public_endpoint(request.url.path):
            response = await call_next(request)
            return response
        
        # Skip validation for admin endpoints
        if self._is_admin_endpoint(request.url.path):
            response = await call_next(request)
            return response
        
        # Get tenant ID from headers
        tenant_id = request.headers.get("X-Customer-ID")
        
        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_tenant_id",
                    "message": "X-Customer-ID header is required",
                    "required_header": "X-Customer-ID",
                    "example": "X-Customer-ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                }
            )
        
        # Validate feature access
        try:
            access_result = await self.subscription_service.validate_feature_access(
                tenant_id, 
                request.url.path
            )
            
            if not access_result["access_granted"]:
                # Track usage attempt for billing/analytics
                await self.subscription_service.track_feature_usage(
                    tenant_id,
                    access_result.get("required_feature", "unknown"),
                    0,  # No quantity for denied access
                    {"status": "denied", "endpoint": request.url.path}
                )
                
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": access_result["error_code"],
                        "message": access_result["reason"],
                        "required_feature": access_result.get("required_feature"),
                        "current_subscription": access_result.get("current_features", []),
                        "subscription_tier": access_result.get("subscription_tier"),
                        "upgrade_url": f"/v1/tenants/{tenant_id}/subscription/upgrade",
                        "contact_sales": "sales@logforge.com"
                    }
                )
            
            # Access granted - proceed with request
            response = await call_next(request)
            
            # Track successful usage for billing
            if response.status_code < 400:  # Only track successful requests
                feature = access_result.get("feature")
                if feature:
                    await self.subscription_service.track_feature_usage(
                        tenant_id,
                        feature,
                        1,
                        {
                            "endpoint": request.url.path,
                            "method": request.method,
                            "status_code": response.status_code,
                            "processing_time_ms": round((time.time() - start_time) * 1000, 2)
                        }
                    )
            
            return response
            
        except Exception as e:
            print(f"Feature access validation error: {str(e)}")
            # On error, allow access but log the issue
            response = await call_next(request)
            return response
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (no feature validation needed)"""
        return any(path.startswith(endpoint) or path == endpoint for endpoint in self.public_endpoints)
    
    def _is_admin_endpoint(self, path: str) -> bool:
        """Check if endpoint is admin (bypasses feature validation)"""
        return any(path.startswith(endpoint) for endpoint in self.admin_endpoints)
