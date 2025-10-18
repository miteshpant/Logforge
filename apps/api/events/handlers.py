"""
Simple Event Handlers
Handlers for processing events and updating database tables
"""

import asyncio
from typing import Dict, Any
import structlog

from .events import LogIngestionEvent

logger = structlog.get_logger(__name__)

class LogIngestionEventHandler:
    """Handler for log ingestion events that updates database tables"""
    
    def __init__(self):
        self.dependencies_loaded = False
        self._complete_ingestion_tracking = None
        logger.info("LogIngestionEventHandler initialized")
    
    async def _load_dependencies(self):
        """Load the complete_ingestion_tracking function from dependencies"""
        if self.dependencies_loaded:
            return
        
        try:
            # Import the existing tracking function
            from dependencies import complete_ingestion_tracking
            self._complete_ingestion_tracking = complete_ingestion_tracking
            self.dependencies_loaded = True
            logger.info("Dependencies loaded successfully")
        except ImportError as e:
            logger.error(f"Failed to load dependencies: {e}")
            raise
    
    async def handle_log_ingestion_event(self, event: LogIngestionEvent) -> bool:
        """
        Handle log ingestion event by updating database tables
        This will call the existing complete_ingestion_tracking function
        """
        try:
            # Ensure dependencies are loaded
            await self._load_dependencies()
            
            logger.info(
                f"Handling log ingestion event",
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                log_count=event.log_count,
                data_size_bytes=event.data_size_bytes
            )
            
            # Call the existing tracking function with event data
            await self._complete_ingestion_tracking(
                customer_id=event.customer_id,
                endpoint=event.endpoint,
                format_type=event.format_type,
                log_count=event.log_count,
                bytes_processed=event.data_size_bytes,
                processing_time_ms=event.processing_time_ms
            )
            
            logger.info(
                f"Log ingestion event processed successfully",
                event_id=event.event_id,
                tenant_id=event.tenant_id
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to handle log ingestion event: {e}",
                event_id=event.event_id,
                tenant_id=event.tenant_id
            )
            return False

# Global handler instance
log_ingestion_handler = LogIngestionEventHandler()