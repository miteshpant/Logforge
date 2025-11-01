"""
Normalized Log Event Handler - Handles normalized log write events
"""

from typing import List
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import EVENT_LOGS_NORMALIZED

logger = structlog.get_logger(__name__)


class NormalizedLogEventHandler(EventHandler):
    """Handler for normalized log events - writes to logs_normalized_mt"""

    async def handle(self, event: BaseEvent) -> bool:
        """Handle normalized log events"""
        logger.info(
            "Processing normalized log event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )
        
        # Handle different types of log events
        if event.event_type == EVENT_LOGS_NORMALIZED:
            return await self._handle_normalized_logs_write(event)
        else:
            logger.info(f"Normalized log event type {event.event_type} received but not implemented")
            return True

    async def _handle_normalized_logs_write(self, event: BaseEvent) -> bool:
        """Write normalized logs to logs_normalized_mt table"""
        try:
            customer_id = event.customer_id
            normalized_logs = event.data.get('normalized_logs', [])
            
            if not normalized_logs:
                logger.warning(f"Empty normalized logs received for customer {customer_id}")
                return True
                
            logger.info(
                f"💾 NORMALIZED WRITE: Writing {len(normalized_logs)} normalized logs for customer {customer_id}",
                event_id=event.metadata.event_id,
                log_count=len(normalized_logs),
                field_mapping_applied=event.data.get('field_mapping_applied', True)
            )
            
            # Write normalized logs to logs_normalized_mt table
            from events.management.processors.log_processor import process_normalized_write_only
            
            write_success = await process_normalized_write_only(normalized_logs, customer_id)
            
            if write_success:
                logger.info(
                    f"💾 NORMALIZED WRITE SUCCESS: {len(normalized_logs)} logs written for customer {customer_id}",
                    event_id=event.metadata.event_id,
                    customer_id=customer_id
                )
            else:
                logger.error(
                    f"💾 NORMALIZED WRITE FAILED: Failed to write logs for customer {customer_id}",
                    event_id=event.metadata.event_id,
                    customer_id=customer_id
                )
                
            return write_success
            
        except Exception as e:
            logger.error(
                f"💾 NORMALIZED WRITE ERROR: {e}",
                event_id=event.metadata.event_id,
                customer_id=event.customer_id,
                exc_info=True
            )
            return False

    def get_supported_event_types(self) -> List[str]:
        """Support normalized log events"""
        return [
            EVENT_LOGS_NORMALIZED
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "normalized_log_handler"