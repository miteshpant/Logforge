"""
Event Subscribers
Comprehensive subscriber management for event-driven architecture
"""

import asyncio
import json
import yaml
import os
from typing import Dict, List, Any, Optional, Type, Callable, Set
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import structlog

from .base import BaseEvent, EventSubscriber, EventSubscribeError, EventMetrics
from .constants import (
    # Topic names
    TOPIC_USAGE_EVENTS,
    TOPIC_ALERT_EVENTS,
    TOPIC_LOG_EVENTS,
    TOPIC_TENANT_EVENTS,
    TOPIC_UI_REALTIME_EVENTS,
    TOPIC_SYSTEM_EVENTS,

    # Event type collections
    USAGE_EVENT_TYPES,
    ALERT_EVENT_TYPES,
    LOG_EVENT_TYPES,
    TENANT_EVENT_TYPES,
    UI_REALTIME_EVENT_TYPES,
    SYSTEM_EVENT_TYPES,

)

# Import aiokafka components
try:
    from aiokafka import AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    kafka_available = True
except ImportError:
    AIOKafkaConsumer = None
    KafkaError = Exception
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
            "consumer": {
                "consumer_group": "logforge-events",
                "max_batch_size": 100,
                "auto_offset_reset": "latest"
            },
            "topics": {}
        }


# Load configuration
EVENT_CONFIG = load_event_config()


@dataclass
class SubscriberConfig:
    """Configuration for event subscribers"""
    name: str
    consumer_group: str
    topics: List[str] = field(default_factory=list)
    event_types: List[str] = field(default_factory=list)
    enabled: bool = True
    max_batch_size: int = 100
    batch_timeout_ms: int = 1000
    max_retries: int = 3
    retry_delay_ms: int = 500
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    max_parallel_workers: int = 10
    health_check_interval_s: int = 30
    metrics_enabled: bool = True


# Import modular event handlers
from .handlers import (
    EventHandler,
    AlertEventHandler,
    LogEventHandler,
    UsageEventHandler,
    SystemEventHandler,
    SecurityEventHandler,
    NormalizedLogEventHandler
    # UIEventHandler
)


class KafkaEventSubscriber(EventSubscriber):
    """Kafka-based event subscriber implementation"""

    def __init__(self, config: SubscriberConfig):
        if not kafka_available:
            raise ImportError("aiokafka is required. Install with: pip install aiokafka")

        self.config = config
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.is_started = False
        self.is_consuming = False
        self.metrics = EventMetrics()
        self.handlers: Dict[str, EventHandler] = {}
        self._consumer_task: Optional[asyncio.Task] = None
        self._worker_tasks: List[asyncio.Task] = []
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        logger.info("KafkaEventSubscriber initialized", subscriber=config.name)

    def register_handler(self, handler: EventHandler):
        """Register an event handler"""
        handler_name = handler.get_handler_name()
        supported_types = handler.get_supported_event_types()

        self.handlers[handler_name] = handler

        logger.info(
            "Event handler registered",
            subscriber=self.config.name,
            handler=handler_name,
            supported_types=supported_types
        )

    async def start(self):
        """Start the subscriber"""
        if self.is_started:
            return

        try:
            await self._start_consumer()
            await self._start_workers()
            await self._start_consuming()

            self.is_started = True
            logger.info("KafkaEventSubscriber started", subscriber=self.config.name)

        except Exception as e:
            logger.error(f"Failed to start KafkaEventSubscriber: {e}", subscriber=self.config.name)
            raise EventSubscribeError(f"Failed to start subscriber: {e}")

    async def _start_consumer(self):
        """Start the Kafka consumer"""
        kafka_config = EVENT_CONFIG.get("kafka", {})
        consumer_config = EVENT_CONFIG.get("consumer", {})
        topics_config = EVENT_CONFIG.get("topics", {})

        # Get topic names from configuration
        topic_names = []
        for topic_key in self.config.topics:
            if topic_key in topics_config:
                topic_name = topics_config[topic_key].get("name", topic_key)
                topic_names.append(topic_name)
            else:
                topic_names.append(topic_key)  # Use key as name if not found

        if not topic_names:
            logger.warning("No topics configured for subscriber", subscriber=self.config.name)
            return

        self.consumer = AIOKafkaConsumer(
            *topic_names,
            bootstrap_servers=kafka_config.get("bootstrap_servers", "localhost:19092"),
            security_protocol=kafka_config.get("security_protocol", "PLAINTEXT"),
            group_id=self.config.consumer_group,
            auto_offset_reset=self.config.auto_offset_reset,
            enable_auto_commit=self.config.enable_auto_commit,
            auto_commit_interval_ms=consumer_config.get("enable_auto_commit_interval_ms", 5000),
            max_poll_records=consumer_config.get("max_poll_records", 500),
            fetch_min_bytes=consumer_config.get("fetch_min_bytes", 1),
            fetch_max_wait_ms=consumer_config.get("fetch_max_wait_ms", 500),
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )

        await self.consumer.start()
        logger.info("Kafka consumer started", topics=topic_names, group=self.config.consumer_group)

    async def _start_workers(self):
        """Start worker tasks for parallel event processing"""
        for i in range(self.config.max_parallel_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._worker_tasks.append(worker)

        logger.info(f"Started {len(self._worker_tasks)} worker tasks")

    async def _start_consuming(self):
        """Start consuming events"""
        if self.is_consuming:
            return

        self.is_consuming = True
        self._consumer_task = asyncio.create_task(self._consume_loop())

        logger.info("Started event consumption")

    async def _consume_loop(self):
        """Main consumption loop"""
        try:
            batch = []
            last_commit_time = asyncio.get_event_loop().time()

            async for message in self.consumer:
                # Add message to queue for worker processing
                try:
                    event_data = message.value
                    event = BaseEvent.from_dict(event_data)

                    # Check if we have handlers for this event type
                    if self._should_process_event(event):
                        await self._event_queue.put((message, event))
                    else:
                        logger.debug(
                            "No handlers for event type, skipping",
                            event_type=event.event_type,
                            event_id=event.metadata.event_id
                        )

                    # Batch commit periodically
                    batch.append(message)
                    current_time = asyncio.get_event_loop().time()

                    if (len(batch) >= self.config.max_batch_size or
                        current_time - last_commit_time >= self.config.batch_timeout_ms / 1000):

                        if not self.config.enable_auto_commit:
                            await self.consumer.commit()

                        batch.clear()
                        last_commit_time = current_time

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in consumption loop: {e}")
            self.is_consuming = False
            raise

    async def _worker_loop(self, worker_id: str):
        """Worker loop for processing events"""
        logger.debug(f"Worker {worker_id} started")

        while self.is_consuming:
            try:
                # Get event from queue with timeout
                try:
                    message, event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process the event
                success = await self._process_event(event, message, worker_id)

                if success:
                    self.metrics.record_event_consumed(0.0)  # TODO: track actual processing time
                else:
                    self.metrics.record_event_failed()

                # Mark task as done
                self._event_queue.task_done()

            except Exception as e:
                logger.error(f"Error in worker {worker_id}: {e}")

    def _should_process_event(self, event: BaseEvent) -> bool:
        """Check if we should process this event type"""
        if not self.config.event_types:
            return True  # Process all event types if none specified

        return event.event_type in self.config.event_types

    async def _process_event(self, event: BaseEvent, message, worker_id: str) -> bool:
        """Process a single event with all applicable handlers"""
        logger.debug(
            "Processing event",
            event_id=event.metadata.event_id,
            event_type=event.event_type,
            worker=worker_id,
            partition=message.partition,
            offset=message.offset
        )

        event.mark_processing()

        # Find handlers for this event type
        applicable_handlers = []
        for handler_name, handler in self.handlers.items():
            if event.event_type in handler.get_supported_event_types():
                applicable_handlers.append((handler_name, handler))

        if not applicable_handlers:
            logger.debug("No handlers found for event type", event_type=event.event_type)
            return True  # Not an error, just no handlers

        # Process with all applicable handlers
        all_successful = True
        for handler_name, handler in applicable_handlers:
            try:
                success = await handler.handle(event)
                if not success:
                    logger.error(f"Handler {handler_name} failed to process event", event_id=event.metadata.event_id)
                    all_successful = False
            except Exception as e:
                logger.error(f"Handler {handler_name} threw exception: {e}", event_id=event.metadata.event_id)
                all_successful = False

        if all_successful:
            event.mark_completed()
        else:
            event.mark_failed("One or more handlers failed")

        return all_successful

    async def handle_event(self, event: BaseEvent) -> bool:
        """Handle a single event (called by base class)"""
        # This method is for the abstract base class
        # In practice, events are handled through the consumption loop
        return await self._process_event(event, None, "direct")

    async def handle_batch(self, events: List[BaseEvent]) -> Dict[str, bool]:
        """Handle multiple events in batch"""
        results = {}

        for event in events:
            try:
                success = await self.handle_event(event)
                results[event.metadata.event_id] = success
            except Exception as e:
                logger.error(f"Failed to handle event in batch: {e}", event_id=event.metadata.event_id)
                results[event.metadata.event_id] = False

        return results

    def get_subscribed_events(self) -> List[str]:
        """Get list of event types this subscriber handles"""
        return self.config.event_types.copy()

    async def stop(self):
        """Stop the subscriber"""
        if not self.is_started:
            return

        try:
            self.is_consuming = False

            # Cancel consumer task
            if self._consumer_task:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

            # Wait for queue to be processed
            await self._event_queue.join()

            # Cancel worker tasks
            for worker_task in self._worker_tasks:
                worker_task.cancel()

            # Wait for workers to finish
            if self._worker_tasks:
                await asyncio.gather(*self._worker_tasks, return_exceptions=True)

            # Stop consumer
            if self.consumer:
                await self.consumer.stop()
                self.consumer = None

            self.is_started = False
            logger.info("KafkaEventSubscriber stopped", subscriber=self.config.name)

        except Exception as e:
            logger.error(f"Error stopping KafkaEventSubscriber: {e}")


# MockEventSubscriber removed - using only real Kafka subscribers


class EventSubscriberManager:
    """Manages multiple event subscribers"""

    def __init__(self):
        self.subscribers: Dict[str, EventSubscriber] = {}
        self.subscriber_configs: Dict[str, SubscriberConfig] = {}
        self.is_started = False

        # Setup configurations from YAML
        self._setup_configurations()

        logger.info("EventSubscriberManager initialized")

    def _setup_configurations(self):
        """Setup subscriber configurations from YAML"""
        consumer_config = EVENT_CONFIG.get("consumer", {})
        topics_config = EVENT_CONFIG.get("topics", {})

        # Create topic lists for different subscriber types
        all_topics = list(topics_config.keys())

        base_group = consumer_config.get("consumer_group", "logforge-events")

        self.subscriber_configs = {
            "usage_subscriber": SubscriberConfig(
                name="usage_subscriber",
                consumer_group=f"{base_group}-usage",
                topics=[TOPIC_USAGE_EVENTS],
                event_types=USAGE_EVENT_TYPES,
                enabled=True,
                max_batch_size=consumer_config.get("max_batch_size", 100),
                max_parallel_workers=consumer_config.get("max_parallel_workers", 10)
            ),
            "alert_subscriber": SubscriberConfig(
                name="alert_subscriber",
                consumer_group=f"{base_group}-alerts",
                topics=[TOPIC_ALERT_EVENTS],
                event_types=ALERT_EVENT_TYPES,
                enabled=True,
                max_batch_size=50,  # Smaller batches for low latency
                max_parallel_workers=5
            ),
            "log_subscriber": SubscriberConfig(
                name="log_subscriber",
                consumer_group=f"{base_group}-logs",
                topics=[TOPIC_LOG_EVENTS],
                event_types=LOG_EVENT_TYPES,
                enabled=True,
                max_batch_size=500,  # Larger batches for throughput
                max_parallel_workers=20
            ),
            "tenant_subscriber": SubscriberConfig(
                name="tenant_subscriber",
                consumer_group=f"{base_group}-tenant",
                topics=[TOPIC_TENANT_EVENTS],
                event_types=TENANT_EVENT_TYPES,
                enabled=True,
                max_batch_size=50,  # Medium batches for user management
                max_parallel_workers=5
            ),
            "ui_subscriber": SubscriberConfig(
                name="ui_subscriber",
                consumer_group=f"{base_group}-ui",
                topics=[TOPIC_UI_REALTIME_EVENTS],
                event_types=UI_REALTIME_EVENT_TYPES,
                enabled=True,
                max_batch_size=10,  # Small batches for real-time updates
                max_parallel_workers=3
            ),
            "system_subscriber": SubscriberConfig(
                name="system_subscriber",
                consumer_group=f"{base_group}-system",
                topics=[TOPIC_SYSTEM_EVENTS],
                event_types=SYSTEM_EVENT_TYPES,
                enabled=True,
                max_batch_size=100,
                max_parallel_workers=5
            ),
# Mock subscriber configuration removed - using only real Kafka subscribers
        }

    def register_subscriber(self, name: str, subscriber_class: Type[EventSubscriber],
                           config: Optional[SubscriberConfig] = None):
        """Register a new subscriber"""
        if not config:
            config = self.subscriber_configs.get(name) or SubscriberConfig(name=name, consumer_group=f"logforge-{name}")

        subscriber = subscriber_class(config)
        self.subscribers[name] = subscriber
        self.subscriber_configs[name] = config

        logger.info("Subscriber registered", name=name, class_name=subscriber_class.__name__)

    async def start(self):
        """Start all enabled subscribers"""
        if self.is_started:
            return

        # Register default subscribers
        if kafka_available:
            self.register_subscriber("usage_subscriber", KafkaEventSubscriber)
            self.register_subscriber("alert_subscriber", KafkaEventSubscriber)
            self.register_subscriber("log_subscriber", KafkaEventSubscriber)
            self.register_subscriber("tenant_subscriber", KafkaEventSubscriber)
            self.register_subscriber("ui_subscriber", KafkaEventSubscriber)
            self.register_subscriber("system_subscriber", KafkaEventSubscriber)

        # Mock subscriber registration removed - using only real Kafka subscribers

        # Register default handlers
        await self._register_default_handlers()

        # Start all enabled subscribers
        for name, subscriber in self.subscribers.items():
            config = self.subscriber_configs[name]
            if config.enabled:
                try:
                    await subscriber.start()
                    logger.info("Subscriber started", name=name)
                except Exception as e:
                    logger.error(f"Failed to start subscriber {name}: {e}")

        self.is_started = True
        logger.info("EventSubscriberManager started")

    async def _register_default_handlers(self):
        """Register default event handlers with subscribers"""
        handlers = [
            UsageEventHandler(),
            AlertEventHandler(),
            LogEventHandler(),
            SystemEventHandler(),
            SecurityEventHandler(),
            NormalizedLogEventHandler()
            # UIEventHandler()
        ]

        for subscriber_name, subscriber in self.subscribers.items():
            if hasattr(subscriber, 'register_handler'):
                for handler in handlers:
                    # Register handler if subscriber handles any of the handler's event types
                    subscriber_events = set(self.subscriber_configs[subscriber_name].event_types)
                    handler_events = set(handler.get_supported_event_types())

                    if subscriber_events.intersection(handler_events):
                        subscriber.register_handler(handler)
                        logger.info(
                            "Handler registered with subscriber",
                            subscriber=subscriber_name,
                            handler=handler.get_handler_name()
                        )

    def get_subscriber(self, name: str) -> Optional[EventSubscriber]:
        """Get a subscriber by name"""
        return self.subscribers.get(name)

    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all subscribers"""
        metrics = {}

        for name, subscriber in self.subscribers.items():
            if hasattr(subscriber, 'metrics'):
                metrics[name] = subscriber.metrics.to_dict()

        return metrics

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all subscribers"""
        results = {}

        for name, subscriber in self.subscribers.items():
            try:
                # Simple health check - check if started
                results[name] = getattr(subscriber, 'is_started', False)
            except Exception as e:
                logger.error(f"Health check failed for subscriber {name}: {e}")
                results[name] = False

        return results

    async def stop(self):
        """Stop all subscribers"""
        if not self.is_started:
            return

        for name, subscriber in self.subscribers.items():
            try:
                await subscriber.stop()
                logger.info("Subscriber stopped", name=name)
            except Exception as e:
                logger.error(f"Error stopping subscriber {name}: {e}")

        self.is_started = False
        logger.info("EventSubscriberManager stopped")


# Global subscriber manager instance
subscriber_manager = EventSubscriberManager()


logger.info("Event subscribers module initialized")
