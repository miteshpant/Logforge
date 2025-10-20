"""
Usage Event Handler - Handles usage and billing events
"""

from typing import List
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_USAGE_API_CALL,
    EVENT_USAGE_INGESTION_BATCH,
    EVENT_USAGE_QUERY_EXECUTION,
    EVENT_USAGE_STORAGE_OPERATION,
    EVENT_BILLING_SUBSCRIPTION_CHANGED,
    EVENT_BILLING_PAYMENT_PROCESSED
)

logger = structlog.get_logger(__name__)


class UsageEventHandler(EventHandler):
    """Handler for usage and billing events"""

    async def handle(self, event: BaseEvent) -> bool:
        """Handle usage events"""
        logger.info(
            "Processing usage event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        # TODO: Implement actual usage tracking logic
        # - Update customer usage metrics
        # - Calculate billing information
        # - Update quotas and limits

        return True

    def get_supported_event_types(self) -> List[str]:
        """Support usage and billing events"""
        return [
            EVENT_USAGE_API_CALL,
            EVENT_USAGE_INGESTION_BATCH,
            EVENT_USAGE_QUERY_EXECUTION,
            EVENT_USAGE_STORAGE_OPERATION,
            EVENT_BILLING_SUBSCRIPTION_CHANGED,
            EVENT_BILLING_PAYMENT_PROCESSED
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "usage_handler"