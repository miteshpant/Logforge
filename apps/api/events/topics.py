"""
Topic Configuration and Management
Defines Kafka topics, partitions, and routing rules for the event system
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import structlog

from .constants import (
    # Topic names
    TOPIC_USAGE_EVENTS,
    TOPIC_ALERT_EVENTS,
    TOPIC_LOG_EVENTS,
    TOPIC_TENANT_EVENTS,
    TOPIC_UI_REALTIME_EVENTS,
    TOPIC_SYSTEM_EVENTS,
    ALL_TOPICS,

    # Event types
    USAGE_EVENT_TYPES,
    ALERT_EVENT_TYPES,
    LOG_EVENT_TYPES,
    TENANT_EVENT_TYPES,
    UI_REALTIME_EVENT_TYPES,
    SYSTEM_EVENT_TYPES,

    # Subscriber groups
    SUBSCRIBER_USAGE_TRACKING_SERVICE,
    SUBSCRIBER_BILLING_SERVICE,
    SUBSCRIBER_ANALYTICS_SERVICE,
    SUBSCRIBER_ALERT_ENGINE,
    SUBSCRIBER_NOTIFICATION_SERVICE,
    SUBSCRIBER_STORAGE_SERVICE,
    SUBSCRIBER_TENANT_SERVICE,
    SUBSCRIBER_USER_SERVICE,
    SUBSCRIBER_UI_SERVICE,
    SUBSCRIBER_WEBSOCKET_SERVICE,
    SUBSCRIBER_MONITORING_SERVICE,
    SUBSCRIBER_SECURITY_SERVICE,
    SUBSCRIBER_AUDIT_SERVICE,
    SUBSCRIBER_ADMIN_UI,

    # Mappings
    EVENT_TYPE_TO_TOPIC,
    TOPIC_TO_SUBSCRIBER_GROUPS
)

logger = structlog.get_logger(__name__)


class PartitionStrategy(str, Enum):
    """Partitioning strategies for different event types"""
    CUSTOMER_HASH = "customer_hash"     # Hash customer_id for even distribution
    ROUND_ROBIN = "round_robin"         # Round-robin distribution
    BROADCAST = "broadcast"             # All consumers get all messages
    SERVICE_HASH = "service_hash"       # Hash by service name


@dataclass
class TopicConfig:
    """Configuration for a Kafka topic"""
    name: str
    partitions: int
    replication_factor: int = 3
    retention_ms: int = 86400000  # 24 hours default
    cleanup_policy: str = "delete"
    partition_strategy: PartitionStrategy = PartitionStrategy.CUSTOMER_HASH
    max_message_bytes: int = 1048576  # 1MB
    compression_type: str = "lz4"

    # Event routing configuration
    event_types: List[str] = None
    subscriber_groups: List[str] = None

    def __post_init__(self):
        if self.event_types is None:
            self.event_types = []
        if self.subscriber_groups is None:
            self.subscriber_groups = []


# Topic configurations for all event types
TOPIC_CONFIGS = {
    # Usage and billing events - high volume, medium retention
    TOPIC_USAGE_EVENTS: TopicConfig(
        name=TOPIC_USAGE_EVENTS,
        partitions=100,
        replication_factor=3,
        retention_ms=604800000,  # 7 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=USAGE_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_USAGE_TRACKING_SERVICE,
            SUBSCRIBER_BILLING_SERVICE,
            SUBSCRIBER_ANALYTICS_SERVICE,
            SUBSCRIBER_UI_SERVICE
        ]
    ),

    # Alert-related events - medium volume, longer retention
    TOPIC_ALERT_EVENTS: TopicConfig(
        name=TOPIC_ALERT_EVENTS,
        partitions=50,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=ALERT_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_ALERT_ENGINE,
            SUBSCRIBER_NOTIFICATION_SERVICE,
            SUBSCRIBER_UI_SERVICE,
            SUBSCRIBER_AUDIT_SERVICE
        ]
    ),

    # Log lifecycle events - very high volume, short retention
    TOPIC_LOG_EVENTS: TopicConfig(
        name=TOPIC_LOG_EVENTS,
        partitions=100,
        replication_factor=3,
        retention_ms=3600000,  # 1 hour (logs already in ClickHouse)
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        compression_type="snappy",  # Better for high volume
        event_types=LOG_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_ALERT_ENGINE,
            SUBSCRIBER_USAGE_TRACKING_SERVICE,
            SUBSCRIBER_STORAGE_SERVICE,
            SUBSCRIBER_UI_SERVICE
        ]
    ),

    # Tenant and user management events - low volume, long retention
    TOPIC_TENANT_EVENTS: TopicConfig(
        name=TOPIC_TENANT_EVENTS,
        partitions=20,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=TENANT_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_TENANT_SERVICE,
            SUBSCRIBER_USER_SERVICE,
            SUBSCRIBER_BILLING_SERVICE,
            SUBSCRIBER_AUDIT_SERVICE,
            SUBSCRIBER_ADMIN_UI
        ]
    ),

    # Real-time UI events - very high volume, very short retention
    TOPIC_UI_REALTIME_EVENTS: TopicConfig(
        name=TOPIC_UI_REALTIME_EVENTS,
        partitions=200,
        replication_factor=2,  # Lower replication for performance
        retention_ms=600000,  # 10 minutes
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        compression_type="snappy",
        event_types=UI_REALTIME_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_WEBSOCKET_SERVICE,
            SUBSCRIBER_UI_SERVICE
        ]
    ),

    # System and infrastructure events - low volume, broadcast
    TOPIC_SYSTEM_EVENTS: TopicConfig(
        name=TOPIC_SYSTEM_EVENTS,
        partitions=10,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.SERVICE_HASH,
        event_types=SYSTEM_EVENT_TYPES,
        subscriber_groups=[
            SUBSCRIBER_MONITORING_SERVICE,
            SUBSCRIBER_SECURITY_SERVICE,
            SUBSCRIBER_ADMIN_UI,
            SUBSCRIBER_ALERT_ENGINE
        ]
    )
}


class TopicManager:
    """Manages Kafka topics and routing"""

    def __init__(self, topic_configs: Dict[str, TopicConfig] = None):
        self.topic_configs = topic_configs or TOPIC_CONFIGS
        self.event_type_to_topic = EVENT_TYPE_TO_TOPIC


    def get_topic_for_event(self, event_type: str) -> Optional[str]:
        """Get topic name for an event type"""
        topic = self.event_type_to_topic.get(event_type)
        if not topic:
            logger.warning(f"No topic configured for event type: {event_type}")
        return topic

    def get_topic_config(self, topic_name: str) -> Optional[TopicConfig]:
        """Get configuration for a topic"""
        return self.topic_configs.get(topic_name)

    def get_partition_count(self, topic_name: str) -> int:
        """Get partition count for a topic"""
        config = self.get_topic_config(topic_name)
        return config.partitions if config else 1

    def get_partition_strategy(self, topic_name: str) -> PartitionStrategy:
        """Get partition strategy for a topic"""
        config = self.get_topic_config(topic_name)
        return config.partition_strategy if config else PartitionStrategy.CUSTOMER_HASH

    def get_event_types_for_topic(self, topic_name: str) -> List[str]:
        """Get all event types for a topic"""
        config = self.get_topic_config(topic_name)
        return config.event_types if config else []

    def get_subscribers_for_topic(self, topic_name: str) -> List[str]:
        """Get subscriber groups for a topic"""
        config = self.get_topic_config(topic_name)
        return config.subscriber_groups if config else []

    def validate_event_routing(self) -> Dict[str, List[str]]:
        """Validate event routing configuration"""
        issues = {
            "missing_topics": [],
            "duplicate_events": [],
            "orphaned_events": []
        }

        # Check for duplicate event type mappings
        event_counts = {}
        for config in self.topic_configs.values():
            for event_type in config.event_types:
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

        for event_type, count in event_counts.items():
            if count > 1:
                issues["duplicate_events"].append(event_type)

        return issues

    def get_topic_creation_configs(self) -> Dict[str, Dict[str, any]]:
        """Get Kafka topic creation configurations"""
        configs = {}

        for topic_name, config in self.topic_configs.items():
            configs[topic_name] = {
                "num_partitions": config.partitions,
                "replication_factor": config.replication_factor,
                "config": {
                    "retention.ms": str(config.retention_ms),
                    "cleanup.policy": config.cleanup_policy,
                    "max.message.bytes": str(config.max_message_bytes),
                    "compression.type": config.compression_type
                }
            }

        return configs

    def get_metrics(self) -> Dict[str, any]:
        """Get topic configuration metrics"""
        total_partitions = sum(config.partitions for config in self.topic_configs.values())
        total_event_types = sum(len(config.event_types) for config in self.topic_configs.values())

        return {
            "total_topics": len(self.topic_configs),
            "total_partitions": total_partitions,
            "total_event_types": total_event_types,
            "avg_partitions_per_topic": total_partitions / len(self.topic_configs),
            "topics": {
                name: {
                    "partitions": config.partitions,
                    "event_types": len(config.event_types),
                    "retention_hours": config.retention_ms / (1000 * 60 * 60)
                }
                for name, config in self.topic_configs.items()
            }
        }


# Utility functions for common topic operations
def get_topic_for_usage_event(usage_type: str) -> str:
    """Get topic for usage events"""
    return TOPIC_USAGE_EVENTS


def get_topic_for_alert_event(alert_action: str) -> str:
    """Get topic for alert events"""
    return TOPIC_ALERT_EVENTS


def get_topic_for_log_event(log_action: str) -> str:
    """Get topic for log events"""
    return TOPIC_LOG_EVENTS


def get_topic_for_ui_event(ui_action: str) -> str:
    """Get topic for UI events"""
    return TOPIC_UI_REALTIME_EVENTS


# Global topic manager instance
topic_manager = TopicManager()

logger.info("Topic configuration initialized with {} topics".format(len(TOPIC_CONFIGS)))
