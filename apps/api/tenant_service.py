"""
Tenant Service Wrapper
Maintains backward compatibility while using new service/dao pattern
"""

from services.tenant_service import TenantService

# Global tenant service instance - using new database-backed service  
tenant_service = TenantService()

# Export the service for backward compatibility
__all__ = ['tenant_service']