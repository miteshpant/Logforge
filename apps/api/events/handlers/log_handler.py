"""
Log Event Handler - Handles log lifecycle events
"""

from typing import List
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_BATCH_INGESTED,
    EVENT_LOGS_PARSED,
    EVENT_LOGS_INDEXED,
    EVENT_LOGS_ARCHIVED,
    EVENT_LOGS_DELETED
)

logger = structlog.get_logger(__name__)


class LogEventHandler(EventHandler):
    """Handler for log lifecycle events"""

    async def handle(self, event: BaseEvent) -> bool:
        """Handle log events"""
        logger.info(
            "Processing log event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )
        
        # Handle different types of log events
        if event.event_type == EVENT_LOGS_BATCH_INGESTED:
            return await self._handle_logs_batch_ingested(event)
        else:
            # For now, just log other event types
            logger.info(f"Log event type {event.event_type} received but not yet implemented")
            return True

    async def _handle_logs_batch_ingested(self, event: BaseEvent) -> bool:
        """Handle logs.batch.ingested event using new event processing"""
        try:
            # Import here to avoid circular dependencies
            from event_processing import handle_log_ingestion_event
            
            # Convert event to the format expected by handle_log_ingestion_event
            # Use the correct field names that match what the publisher sends
            event_data = {
                'customer_id': event.customer_id,
                'logs': event.data.get('logs', []),
                'ingestion_endpoint': event.data.get('ingestion_endpoint', '/logs'),  # Fix: Use correct field name
                'source_format': event.data.get('source_format', 'json'),            # Fix: Use correct field name  
                'log_count': event.data.get('log_count', 0),
                'bytes_processed': event.data.get('bytes_processed', 0),
                'processing_time_ms': event.data.get('processing_time_ms', 0),
                'batch_id': event.data.get('batch_id', ''),
                'timestamp': event.data.get('timestamp', '')
            }
            
            logger.info(
                f"Processing log batch ingestion event via event_processing module",
                event_id=event.metadata.event_id,
                customer_id=event.customer_id,
                log_count=event_data['log_count'],
                bytes_processed=event_data['bytes_processed']
            )
            
            # Process the event using our new modular functions
            success = await handle_log_ingestion_event(event_data)
            
            if success:
                logger.info(
                    f"Log batch ingestion event processed successfully",
                    event_id=event.metadata.event_id,
                    customer_id=event.customer_id
                )
            else:
                logger.error(
                    f"Log batch ingestion event processing failed",
                    event_id=event.metadata.event_id,
                    customer_id=event.customer_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Exception in log batch ingestion handler: {e}",
                event_id=event.metadata.event_id,
                customer_id=event.customer_id
            )
            return False

    def get_supported_event_types(self) -> List[str]:
        """Support log events"""
        return [
            EVENT_LOGS_BATCH_INGESTED,
            EVENT_LOGS_PARSED,
            EVENT_LOGS_INDEXED,
            EVENT_LOGS_ARCHIVED,
            EVENT_LOGS_DELETED
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "log_handler"