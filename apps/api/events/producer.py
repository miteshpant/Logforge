"""
Simple Event Producer
Minimal Kafka producer for publishing log ingestion events
"""

import asyncio
import json
from typing import Optional
import structlog

from .config import event_config
from .events import LogIngestionEvent
from .partitioning import tenant_partitioner

# Import aiokafka components
try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    from aiokafka.errors import KafkaError, TopicAlreadyExistsError
    kafka_available = True
except ImportError:
    AIOKafkaProducer = None
    AIOKafkaAdminClient = None
    NewTopic = None
    KafkaError = Exception
    TopicAlreadyExistsError = Exception
    kafka_available = False

logger = structlog.get_logger(__name__)

class EventProducer:
    """Simple Kafka producer for log ingestion events"""
    
    def __init__(self):
        if not kafka_available:
            raise ImportError("aiokafka is required. Install with: pip install aiokafka")
        
        self.producer: Optional[AIOKafkaProducer] = None
        self.admin_client: Optional[AIOKafkaAdminClient] = None
        self.is_started = False
        
        logger.info("EventProducer initialized")
    
    async def start(self):
        """Start the producer and ensure topic exists"""
        if self.is_started:
            return
        
        try:
            # Start admin client first to create topic
            await self._start_admin_client()
            await self._ensure_topic_exists()
            
            # Start producer
            await self._start_producer()
            
            self.is_started = True
            logger.info("EventProducer started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start EventProducer: {e}")
            raise
    
    async def _start_admin_client(self):
        """Start admin client for topic management"""
        self.admin_client = AIOKafkaAdminClient(
            bootstrap_servers=event_config.bootstrap_servers,
            security_protocol=event_config.security_protocol
        )
        await self.admin_client.start()
        logger.info("Admin client started")
    
    async def _ensure_topic_exists(self):
        """Create topic if it doesn't exist"""
        try:
            topic = NewTopic(
                name=event_config.topic_name,
                num_partitions=event_config.partitions,
                replication_factor=event_config.replication_factor
            )
            
            await self.admin_client.create_topics([topic])
            logger.info(f"Topic '{event_config.topic_name}' created with {event_config.partitions} partitions")
            
        except TopicAlreadyExistsError:
            logger.info(f"Topic '{event_config.topic_name}' already exists")
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            raise
    
    async def _start_producer(self):
        """Start the Kafka producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=event_config.bootstrap_servers,
            security_protocol=event_config.security_protocol,
            acks=event_config.acks,
            retries=event_config.retries,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka producer started")
    
    async def publish_event(self, event: LogIngestionEvent) -> bool:
        """Publish a log ingestion event"""
        if not self.is_started:
            logger.error("Producer not started")
            return False
        
        try:
            # Get partition based on tenant hash
            partition = tenant_partitioner.get_partition(event.tenant_id)
            
            # Convert event to dict for JSON serialization
            event_data = event.to_dict()
            
            # Send to Kafka
            future = await self.producer.send(
                topic=event_config.topic_name,
                value=event_data,
                partition=partition,
                key=event.tenant_id.encode('utf-8') if event.tenant_id else None
            )
            
            logger.info(
                f"Event published successfully",
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                partition=partition,
                topic=event_config.topic_name
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event: {e}", event_id=event.event_id)
            return False
    
    async def stop(self):
        """Stop the producer and admin client"""
        if not self.is_started:
            return
        
        try:
            if self.producer:
                await self.producer.stop()
                self.producer = None
            
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None
            
            self.is_started = False
            logger.info("EventProducer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping EventProducer: {e}")

# Global producer instance
event_producer = EventProducer()