"""
Tenant Service Wrapper
Maintains backward compatibility while using new service/dao pattern
"""

from typing import Optional

from services.tenant_service import TenantService

# ENH-033/ENH-010: this module previously did
#     tenant_service = TenantService()
# at import time, which built a TenantDAO -> DatabaseLayer chain and opened a
# ClickHouse connection during `import tenant_service`.
#
# Because `tenant_dependencies.py` imports this, and every router imports
# `tenant_dependencies` for `MiddlewareTenant`, that single line made the ENTIRE
# router layer un-importable -- and therefore untestable -- without live
# infrastructure. It was the original root cause reported in ENH-010.
#
# The instance is now created on first use. The PEP 562 module `__getattr__`
# preserves the existing `from tenant_service import tenant_service` spelling
# for the three call sites that use it.
_tenant_service_instance: Optional[TenantService] = None


def get_tenant_service() -> TenantService:
    """Get the shared TenantService, constructing it on first use."""
    global _tenant_service_instance
    if _tenant_service_instance is None:
        _tenant_service_instance = TenantService()
    return _tenant_service_instance


def __getattr__(name: str):
    """Resolve `tenant_service` lazily on attribute access."""
    if name == "tenant_service":
        return get_tenant_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Export the service for backward compatibility
__all__ = ['tenant_service', 'get_tenant_service']
