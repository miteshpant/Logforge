"""
Simple Event Manager
Coordinates the simple event system startup and shutdown
"""

import asyncio
from typing import Optional
import structlog

from .producer import event_producer
from .consumer import event_consumer
from .handlers import log_ingestion_handler
from .events import LogIngestionEvent

logger = structlog.get_logger(__name__)

class SimpleEventManager:
    """Simple event system manager"""
    
    def __init__(self):
        self.is_started = False
        logger.info("SimpleEventManager initialized")
    
    async def start(self):
        """Start the event system"""
        if self.is_started:
            logger.warning("Event system already started")
            return
        
        try:
            logger.info("Starting simple event system...")
            
            # Start producer
            await event_producer.start()
            
            # Set up consumer with handler
            event_consumer.set_event_handler(log_ingestion_handler.handle_log_ingestion_event)
            
            # Start consumer
            await event_consumer.start()
            await event_consumer.start_consuming()
            
            self.is_started = True
            logger.info("Simple event system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start event system: {e}")
            raise
    
    async def stop(self):
        """Stop the event system"""
        if not self.is_started:
            return
        
        try:
            logger.info("Stopping simple event system...")
            
            # Stop consumer first
            await event_consumer.stop()
            
            # Stop producer
            await event_producer.stop()
            
            self.is_started = False
            logger.info("Simple event system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping event system: {e}")
    
    async def publish_log_ingestion_event(self, 
                                        tenant_id: str,
                                        customer_id: str,
                                        endpoint: str,
                                        log_count: int,
                                        data_size_bytes: int,
                                        processing_time_ms: float,
                                        format_type: str = "json",
                                        user_id: str = "") -> bool:
        """
        Convenience method to publish a log ingestion event
        """
        if not self.is_started:
            logger.error("Event system not started")
            return False
        
        try:
            # Create event
            event = LogIngestionEvent(
                event_id="",  # Will be auto-generated
                tenant_id=tenant_id,
                customer_id=customer_id,
                endpoint=endpoint,
                log_count=log_count,
                data_size_bytes=data_size_bytes,
                data_size_gb=round(data_size_bytes / (1024**3), 6),
                processing_time_ms=processing_time_ms,
                format_type=format_type,
                user_id=user_id
            )
            
            # Publish event
            return await event_producer.publish_event(event)
            
        except Exception as e:
            logger.error(f"Failed to publish log ingestion event: {e}")
            return False
    
    def is_healthy(self) -> bool:
        """Check if event system is healthy"""
        return (self.is_started and 
                event_producer.is_started and 
                event_consumer.is_started)

# Global event manager instance
simple_event_manager = SimpleEventManager()