"""
Simple Event Consumer
Minimal Kafka consumer for processing log ingestion events
"""

import asyncio
import json
from typing import Optional, Callable, Dict, Any
import structlog

from .config import event_config
from .events import LogIngestionEvent

# Import aiokafka components
try:
    from aiokafka import AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    kafka_available = True
except ImportError:
    # Type: ignore to avoid IDE warnings about None not being callable
    AIOKafkaConsumer = None  # type: ignore
    KafkaError = Exception
    kafka_available = False

logger = structlog.get_logger(__name__)

class EventConsumer:
    """Simple Kafka consumer for log ingestion events"""
    
    def __init__(self, event_handler: Optional[Callable[[LogIngestionEvent], bool]] = None):
        if not kafka_available:
            raise ImportError("aiokafka is required. Install with: pip install aiokafka")
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.event_handler = event_handler
        self.is_started = False
        self.is_consuming = False
        
        logger.info("EventConsumer initialized")
    
    def set_event_handler(self, handler: Callable[[LogIngestionEvent], bool]):
        """Set the event handler function"""
        self.event_handler = handler
        logger.info("Event handler set")
    
    async def start(self):
        """Start the consumer"""
        if self.is_started:
            return
        
        try:
            self.consumer = AIOKafkaConsumer(  # type: ignore
                event_config.topic_name,
                bootstrap_servers=event_config.bootstrap_servers,
                security_protocol=event_config.security_protocol,
                group_id=event_config.consumer_group,
                auto_offset_reset=event_config.auto_offset_reset,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            await self.consumer.start()
            self.is_started = True
            
            logger.info(
                f"EventConsumer started successfully",
                topic=event_config.topic_name,
                group_id=event_config.consumer_group
            )
            
        except Exception as e:
            logger.error(f"Failed to start EventConsumer: {e}")
            raise
    
    async def start_consuming(self):
        """Start consuming events in a background task"""
        if not self.is_started:
            await self.start()
        
        if self.is_consuming:
            logger.warning("Already consuming events")
            return
        
        if not self.event_handler:
            logger.error("No event handler set")
            return
        
        self.is_consuming = True
        logger.info("Starting event consumption loop")
        
        # Start consuming in background
        asyncio.create_task(self._consume_events())
    
    async def _consume_events(self):
        """Main event consumption loop"""
        try:
            async for message in self.consumer:
                await self._process_message(message)
                
        except Exception as e:
            logger.error(f"Error in consumption loop: {e}")
            self.is_consuming = False
            raise
    
    async def _process_message(self, message):
        """Process a single Kafka message"""
        try:
            # Convert message value to LogIngestionEvent
            event_data = message.value
            event = LogIngestionEvent.from_dict(event_data)
            
            logger.info(
                f"Processing event",
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                partition=message.partition,
                offset=message.offset
            )
            
            # Call the event handler
            success = await self._call_handler(event)
            
            if success:
                logger.info(f"Event processed successfully", event_id=event.event_id)
            else:
                logger.error(f"Event processing failed", event_id=event.event_id)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _call_handler(self, event: LogIngestionEvent) -> bool:
        """Call the event handler safely"""
        try:
            if asyncio.iscoroutinefunction(self.event_handler):
                return await self.event_handler(event)
            else:
                return self.event_handler(event)
        except Exception as e:
            logger.error(f"Event handler failed: {e}", event_id=event.event_id)
            return False
    
    async def stop(self):
        """Stop the consumer"""
        if not self.is_started:
            return
        
        try:
            self.is_consuming = False
            
            if self.consumer:
                await self.consumer.stop()
                self.consumer = None
            
            self.is_started = False
            logger.info("EventConsumer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping EventConsumer: {e}")

# Global consumer instance
event_consumer = EventConsumer()