"""
Subscription Service Wrapper
Maintains backward compatibility while using new service/dao pattern
"""

from typing import Optional

from services.subscription_service import SubscriptionService

# ENH-008/ENH-010: this module previously did
#     subscription_service = SubscriptionService()
# at import time, which built a SubscriptionDAO -> DatabaseLayer chain and
# opened a ClickHouse connection during `import subscription_service`.
#
# Three modules import this singleton at their own import time
# (authn_authz_middleware.py:25, feature_access_middleware.py:9,
# routers/subscription_api.py:20), so that single line made the entire
# authentication middleware un-importable without live infrastructure -- and
# therefore untestable.
#
# The instance is now created on first use. The PEP 562 module `__getattr__`
# below preserves the existing `from subscription_service import
# subscription_service` spelling, so no consumer changes.
_subscription_service_instance: Optional[SubscriptionService] = None


def get_subscription_service() -> SubscriptionService:
    """Get the shared SubscriptionService, constructing it on first use."""
    global _subscription_service_instance
    if _subscription_service_instance is None:
        _subscription_service_instance = SubscriptionService()
    return _subscription_service_instance


def __getattr__(name: str):
    """Resolve `subscription_service` lazily on attribute access."""
    if name == "subscription_service":
        return get_subscription_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Export the service for backward compatibility
__all__ = ['subscription_service', 'get_subscription_service']
