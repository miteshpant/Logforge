"""
Event Publishers
Comprehensive publisher management for event-driven architecture
"""

import asyncio
import json
import yaml
import os
from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass, field
import structlog

from .base import BaseEvent, EventPublisher, EventPublishError, EventMetrics
from .constants import (
    get_topic_for_event_type,
    TOPIC_LOG_EVENTS,
    TOPIC_UI_REALTIME_EVENTS,
    TOPIC_ALERT_EVENTS,
    TOPIC_SYSTEM_EVENTS,
    TOPIC_USAGE_EVENTS,
    TOPIC_TENANT_EVENTS
)

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


def load_event_config():
    """Load event configuration from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "events.yml")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Get environment-specific overrides
        env = os.getenv('ENVIRONMENT', 'development')
        if env in config:
            # Merge environment-specific config
            for section, values in config[env].items():
                if section in config:
                    config[section].update(values)

        # Substitute environment variables
        def substitute_env_vars(obj):
            if isinstance(obj, dict):
                return {k: substitute_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            else:
                return obj

        return substitute_env_vars(config)

    except Exception as e:
        logger.error(f"Failed to load event config: {e}")
        # Return default config
        return {
            "kafka": {
                "bootstrap_servers": "localhost:19092",
                "security_protocol": "PLAINTEXT"
            },
            "producer": {
                "batch_size": 100,
                "flush_interval_ms": 1000,
                "max_retries": 3
            },
            "topics": {}
        }


# Load configuration
EVENT_CONFIG = load_event_config()


@dataclass
class PublisherConfig:
    """Configuration for event publishers"""
    name: str
    enabled: bool = True
    topics: List[str] = field(default_factory=list)
    max_batch_size: int = 100
    batch_timeout_ms: int = 1000
    retry_attempts: int = 3
    retry_delay_ms: int = 1000
    health_check_interval_s: int = 30
    metrics_enabled: bool = True


class KafkaEventPublisher(EventPublisher):
    """Kafka-based event publisher implementation"""

    def __init__(self, config: PublisherConfig):
        if not kafka_available:
            raise ImportError("aiokafka is required. Install with: pip install aiokafka")

        self.config = config
        self.producer: Optional[AIOKafkaProducer] = None
        self.admin_client: Optional[AIOKafkaAdminClient] = None
        self.is_started = False
        self.metrics = EventMetrics()
        self._pending_events: Dict[str, List[BaseEvent]] = {}  # topic -> events
        self._batch_timer: Optional[asyncio.Task] = None

        logger.info("KafkaEventPublisher initialized", publisher=config.name)

    async def start(self):
        """Start the Kafka publisher"""
        if self.is_started:
            return

        try:
            # Start admin client first to create topics
            await self._start_admin_client()
            await self._ensure_topics_exist()

            # Start producer
            await self._start_producer()

            # Start batch processing if enabled
            if self.config.max_batch_size > 1:
                self._batch_timer = asyncio.create_task(self._batch_processor())

            self.is_started = True
            logger.info("KafkaEventPublisher started", publisher=self.config.name)

        except Exception as e:
            logger.error(f"Failed to start KafkaEventPublisher: {e}", publisher=self.config.name)
            raise EventPublishError(f"Failed to start publisher: {e}")

    async def _start_admin_client(self):
        """Start admin client for topic management"""
        kafka_config = EVENT_CONFIG.get("kafka", {})

        self.admin_client = AIOKafkaAdminClient(
            bootstrap_servers=kafka_config.get("bootstrap_servers", "localhost:19092"),
            security_protocol=kafka_config.get("security_protocol", "PLAINTEXT")
        )
        await self.admin_client.start()

    async def _ensure_topics_exist(self):
        """Create topics if they don't exist"""
        topics_config = EVENT_CONFIG.get("topics", {})

        for topic_key in self.config.topics:
            if topic_key not in topics_config:
                logger.warning(f"No configuration found for topic: {topic_key}")
                continue

            topic_config = topics_config[topic_key]
            topic_name = topic_config.get("name", topic_key)

            try:
                topic = NewTopic(
                    name=topic_name,
                    num_partitions=topic_config.get("partitions", 10),
                    replication_factor=topic_config.get("replication_factor", 1)
                )

                await self.admin_client.create_topics([topic])
                logger.info(f"Topic created", topic=topic_name)

            except TopicAlreadyExistsError:
                logger.debug(f"Topic already exists", topic=topic_name)
            except Exception as e:
                logger.error(f"Failed to create topic {topic_name}: {e}")
                raise

    async def _start_producer(self):
        """Start the Kafka producer"""
        kafka_config = EVENT_CONFIG.get("kafka", {})
        producer_config = EVENT_CONFIG.get("producer", {})

        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_config.get("bootstrap_servers", "localhost:19092"),
            security_protocol=kafka_config.get("security_protocol", "PLAINTEXT"),
            acks=kafka_config.get("acks", "all"),
            retries=kafka_config.get("retries", 3),
            batch_size=producer_config.get("batch_size", 16384),
            linger_ms=kafka_config.get("linger_ms", 10),
            compression_type=kafka_config.get("compression_type", "lz4"),
            max_request_size=kafka_config.get("max_request_size", 1048576),
            enable_idempotence=producer_config.get("enable_idempotence", True),
            max_in_flight_requests_per_connection=producer_config.get("max_in_flight_requests", 5),
            request_timeout_ms=producer_config.get("request_timeout_ms", 30000),
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()

    async def publish(self, event: BaseEvent) -> bool:
        """Publish a single event"""
        if not self.is_started:
            raise EventPublishError("Publisher not started")

        if not self.config.enabled:
            logger.debug("Publisher disabled, skipping event", publisher=self.config.name)
            return True

        try:
            # Determine topic
            topic = self._get_topic_for_event(event)

            # Add to batch if batching is enabled
            if self.config.max_batch_size > 1:
                if topic not in self._pending_events:
                    self._pending_events[topic] = []

                self._pending_events[topic].append(event)

                # Flush immediately if batch is full
                if len(self._pending_events[topic]) >= self.config.max_batch_size:
                    await self._flush_topic_batch(topic)

                return True
            else:
                # Publish immediately
                return await self._publish_single(event, topic)

        except Exception as e:
            logger.error(f"Failed to publish event: {e}", event_id=event.metadata.event_id)
            self.metrics.record_event_failed()
            return False

    async def _publish_single(self, event: BaseEvent, topic: str) -> bool:
        """Publish a single event immediately"""
        try:
            # Get partition
            partition = self._get_partition_for_event(event, topic)

            # Convert event to publishable format
            event_data = event.to_dict()

            # Send to Kafka
            future = await self.producer.send(
                topic=topic,
                value=event_data,
                partition=partition,
                key=event.get_partition_key().encode('utf-8')
            )

            self.metrics.record_event_published()
            logger.debug(
                "Event published successfully",
                event_id=event.metadata.event_id,
                event_type=event.event_type,
                topic=topic,
                partition=partition
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send event to Kafka: {e}", event_id=event.metadata.event_id)
            raise

    async def publish_batch(self, events: List[BaseEvent]) -> Dict[str, bool]:
        """Publish multiple events in batch"""
        if not self.is_started:
            raise EventPublishError("Publisher not started")

        results = {}

        # Group events by topic
        events_by_topic = {}
        for event in events:
            topic = self._get_topic_for_event(event)
            if topic not in events_by_topic:
                events_by_topic[topic] = []
            events_by_topic[topic].append(event)

        # Publish each topic batch
        for topic, topic_events in events_by_topic.items():
            for event in topic_events:
                try:
                    success = await self._publish_single(event, topic)
                    results[event.metadata.event_id] = success
                except Exception as e:
                    logger.error(f"Failed to publish event in batch: {e}", event_id=event.metadata.event_id)
                    results[event.metadata.event_id] = False

        return results

    async def _batch_processor(self):
        """Background task to process batched events"""
        while self.is_started:
            try:
                await asyncio.sleep(self.config.batch_timeout_ms / 1000)

                # Flush all topic batches
                for topic in list(self._pending_events.keys()):
                    if self._pending_events[topic]:
                        await self._flush_topic_batch(topic)

            except Exception as e:
                logger.error(f"Error in batch processor: {e}")

    async def _flush_topic_batch(self, topic: str):
        """Flush pending events for a specific topic"""
        if topic not in self._pending_events or not self._pending_events[topic]:
            return

        events_to_send = self._pending_events[topic].copy()
        self._pending_events[topic].clear()

        logger.debug(f"Flushing batch of {len(events_to_send)} events for topic {topic}")

        for event in events_to_send:
            try:
                await self._publish_single(event, topic)
            except Exception as e:
                logger.error(f"Failed to publish event in batch flush: {e}", event_id=event.metadata.event_id)

    def _get_topic_for_event(self, event: BaseEvent) -> str:
        """Determine topic for event based on type using centralized constants"""
        # Use centralized mapping from events_constants.py
        topic_name = get_topic_for_event_type(event.event_type)

        # Convert topic name to actual topic name from config if needed
        topics_config = EVENT_CONFIG.get("topics", {})
        if topic_name in topics_config:
            return topics_config[topic_name].get("name", topic_name)

        return topic_name

    def _get_partition_for_event(self, event: BaseEvent, topic: str) -> int:
        """Determine partition for event"""
        topics_config = EVENT_CONFIG.get("topics", {})

        # Find topic config by name
        topic_partitions = 10  # default
        for topic_key, topic_config in topics_config.items():
            if topic_config.get("name") == topic:
                topic_partitions = topic_config.get("partitions", 10)
                break

        # Use hash of partition key for consistent partitioning
        partition_key = event.get_partition_key()
        return hash(partition_key) % topic_partitions

    async def health_check(self) -> bool:
        """Check if publisher is healthy"""
        try:
            if not self.is_started or not self.producer:
                return False

            # Simple health check - check producer status
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def close(self):
        """Close publisher and cleanup resources"""
        if not self.is_started:
            return

        try:
            self.is_started = False

            # Cancel batch timer
            if self._batch_timer:
                self._batch_timer.cancel()
                try:
                    await self._batch_timer
                except asyncio.CancelledError:
                    pass

            # Flush any pending events
            for topic in list(self._pending_events.keys()):
                if self._pending_events[topic]:
                    await self._flush_topic_batch(topic)

            # Close producer
            if self.producer:
                await self.producer.stop()
                self.producer = None

            # Close admin client
            if self.admin_client:
                await self.admin_client.close()
                self.admin_client = None

            logger.info("KafkaEventPublisher closed", publisher=self.config.name)

        except Exception as e:
            logger.error(f"Error closing KafkaEventPublisher: {e}")


class MockEventPublisher(EventPublisher):
    """Mock publisher for testing and development"""

    def __init__(self, config: PublisherConfig):
        self.config = config
        self.is_started = False
        self.metrics = EventMetrics()
        self.published_events: List[BaseEvent] = []

        logger.info("MockEventPublisher initialized", publisher=config.name)

    async def publish(self, event: BaseEvent) -> bool:
        """Mock publish - just store the event"""
        if not self.is_started:
            raise EventPublishError("Publisher not started")

        if not self.config.enabled:
            return True

        self.published_events.append(event)
        self.metrics.record_event_published()

        logger.debug(
            "Event mock published",
            event_id=event.metadata.event_id,
            event_type=event.event_type
        )
        return True

    async def publish_batch(self, events: List[BaseEvent]) -> Dict[str, bool]:
        """Mock batch publish"""
        results = {}

        for event in events:
            success = await self.publish(event)
            results[event.metadata.event_id] = success

        return results

    async def health_check(self) -> bool:
        """Mock health check"""
        return self.is_started

    async def close(self):
        """Close mock publisher"""
        self.is_started = False
        logger.info("MockEventPublisher closed", publisher=self.config.name)


class EventPublisherManager:
    """Manages multiple event publishers"""

    def __init__(self):
        self.publishers: Dict[str, EventPublisher] = {}
        self.publisher_configs: Dict[str, PublisherConfig] = {}
        self.is_started = False

        # Setup configurations from YAML
        self._setup_configurations()

        logger.info("EventPublisherManager initialized")

    def _setup_configurations(self):
        """Setup publisher configurations from YAML"""
        producer_config = EVENT_CONFIG.get("producer", {})
        topics_config = EVENT_CONFIG.get("topics", {})

        # Create topic lists for different publisher types using constants
        all_topics = list(topics_config.keys())
        high_throughput_topics = [TOPIC_LOG_EVENTS, TOPIC_UI_REALTIME_EVENTS]
        low_latency_topics = [TOPIC_ALERT_EVENTS, TOPIC_SYSTEM_EVENTS]
        analytics_topics = [TOPIC_USAGE_EVENTS, TOPIC_TENANT_EVENTS]

        self.publisher_configs = {
            "kafka_main": PublisherConfig(
                name="kafka_main",
                enabled=True,
                topics=all_topics,
                max_batch_size=producer_config.get("batch_size", 100),
                batch_timeout_ms=producer_config.get("flush_interval_ms", 1000),
                retry_attempts=producer_config.get("max_retries", 3),
                retry_delay_ms=producer_config.get("retry_delay_ms", 500)
            ),
            "kafka_analytics": PublisherConfig(
                name="kafka_analytics",
                enabled=True,
                topics=analytics_topics,
                max_batch_size=500,  # Larger batches for analytics
                batch_timeout_ms=5000,  # Longer timeout for efficiency
                retry_attempts=5
            ),
            "kafka_realtime": PublisherConfig(
                name="kafka_realtime",
                enabled=True,
                topics=low_latency_topics,
                max_batch_size=1,  # No batching for low latency
                batch_timeout_ms=0,
                retry_attempts=1
            ),
            "mock_test": PublisherConfig(
                name="mock_test",
                enabled=False,
                topics=all_topics
            )
        }

    def register_publisher(self, name: str, publisher_class: Type[EventPublisher],
                          config: Optional[PublisherConfig] = None):
        """Register a new publisher"""
        if not config:
            config = self.publisher_configs.get(name) or PublisherConfig(name=name)

        publisher = publisher_class(config)
        self.publishers[name] = publisher
        self.publisher_configs[name] = config

        logger.info("Publisher registered", name=name, class_name=publisher_class.__name__)

    async def start(self):
        """Start all enabled publishers"""
        if self.is_started:
            return

        # Register default publishers
        if kafka_available:
            self.register_publisher("kafka_main", KafkaEventPublisher)
            # Only register specialized publishers if kafka is available and enabled
            if EVENT_CONFIG.get("producer", {}).get("enable_compression", True):
                self.register_publisher("kafka_analytics", KafkaEventPublisher)

        # Always register mock for testing
        self.register_publisher("mock_test", MockEventPublisher)

        # Start all enabled publishers
        for name, publisher in self.publishers.items():
            config = self.publisher_configs[name]
            if config.enabled:
                try:
                    await publisher.start() if hasattr(publisher, 'start') else None
                    logger.info("Publisher started", name=name)
                except Exception as e:
                    logger.error(f"Failed to start publisher {name}: {e}")

        self.is_started = True
        logger.info("EventPublisherManager started")

    async def publish(self, event: BaseEvent, publisher_names: Optional[List[str]] = None) -> Dict[str, bool]:
        """Publish event to specified publishers or all enabled ones"""
        if not self.is_started:
            raise EventPublishError("PublisherManager not started")

        if publisher_names is None:
            # Use all enabled publishers that support this event's topic
            event_topic = self._get_topic_for_event_type(event.event_type)
            publisher_names = []

            for name, config in self.publisher_configs.items():
                if config.enabled and (not config.topics or event_topic in config.topics):
                    publisher_names.append(name)

        results = {}

        for name in publisher_names:
            if name not in self.publishers:
                logger.warning(f"Publisher not found: {name}")
                results[name] = False
                continue

            try:
                success = await self.publishers[name].publish(event)
                results[name] = success
            except Exception as e:
                logger.error(f"Failed to publish to {name}: {e}")
                results[name] = False

        return results

    def _get_topic_for_event_type(self, event_type: str) -> str:
        """Get topic key for event type using centralized constants"""
        return get_topic_for_event_type(event_type)

    async def publish_batch(self, events: List[BaseEvent],
                           publisher_names: Optional[List[str]] = None) -> Dict[str, Dict[str, bool]]:
        """Publish batch of events to specified publishers"""
        if not self.is_started:
            raise EventPublishError("PublisherManager not started")

        if publisher_names is None:
            publisher_names = [name for name, config in self.publisher_configs.items() if config.enabled]

        results = {}

        for name in publisher_names:
            if name not in self.publishers:
                logger.warning(f"Publisher not found: {name}")
                continue

            try:
                publisher_results = await self.publishers[name].publish_batch(events)
                results[name] = publisher_results
            except Exception as e:
                logger.error(f"Failed to publish batch to {name}: {e}")
                results[name] = {event.metadata.event_id: False for event in events}

        return results

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all publishers"""
        results = {}

        for name, publisher in self.publishers.items():
            try:
                results[name] = await publisher.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False

        return results

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all publishers"""
        metrics = {}

        for name, publisher in self.publishers.items():
            if hasattr(publisher, 'metrics'):
                metrics[name] = publisher.metrics.to_dict()

        return metrics

    async def close(self):
        """Close all publishers"""
        if not self.is_started:
            return

        for name, publisher in self.publishers.items():
            try:
                await publisher.close()
                logger.info("Publisher closed", name=name)
            except Exception as e:
                logger.error(f"Error closing publisher {name}: {e}")

        self.is_started = False
        logger.info("EventPublisherManager closed")


# Global publisher manager instance
publisher_manager = EventPublisherManager()


logger.info("Event publishers module initialized")
