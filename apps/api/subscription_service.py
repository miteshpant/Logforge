"""
Subscription Service Wrapper
Maintains backward compatibility while using new service/dao pattern
"""

from services.subscription_service import SubscriptionService

# Global subscription service instance - using new database-backed service  
subscription_service = SubscriptionService()

# Export the service for backward compatibility
__all__ = ['subscription_service']