"""
Topic Configuration and Management
Defines Kafka topics, partitions, and routing rules for the event system
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import structlog

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
    "usage-events": TopicConfig(
        name="usage-events",
        partitions=100,
        replication_factor=3,
        retention_ms=604800000,  # 7 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=[
            "usage.api.call",
            "usage.ingestion.batch", 
            "usage.query.execution",
            "usage.storage.operation",
            "usage.quota.exceeded",
            "usage.cost.calculated"
        ],
        subscriber_groups=[
            "usage-tracking-service",
            "billing-service",
            "analytics-service",
            "ui-service"
        ]
    ),
    
    # Alert-related events - medium volume, longer retention
    "alert-events": TopicConfig(
        name="alert-events", 
        partitions=50,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=[
            "alert.rule.created",
            "alert.rule.updated", 
            "alert.rule.deleted",
            "alert.rule.enabled",
            "alert.rule.disabled",
            "alert.triggered",
            "alert.resolved",
            "alert.acknowledged",
            "alert.escalated",
            "notification.sent",
            "notification.failed"
        ],
        subscriber_groups=[
            "alert-engine",
            "notification-service",
            "ui-service",
            "audit-service"
        ]
    ),
    
    # Log lifecycle events - very high volume, short retention
    "log-events": TopicConfig(
        name="log-events",
        partitions=100, 
        replication_factor=3,
        retention_ms=3600000,  # 1 hour (logs already in ClickHouse)
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        compression_type="snappy",  # Better for high volume
        event_types=[
            "logs.batch.ingested",
            "logs.parsing.failed",
            "logs.quota.exceeded",
            "logs.realtime.batch",  # For real-time alert evaluation
            "logs.archived",
            "logs.ttl.expired",
            "logs.restored"
        ],
        subscriber_groups=[
            "alert-engine",
            "usage-tracking-service", 
            "storage-service",
            "ui-service"
        ]
    ),
    
    # Tenant and user management events - low volume, long retention
    "tenant-events": TopicConfig(
        name="tenant-events",
        partitions=20,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        event_types=[
            "tenant.created",
            "tenant.updated",
            "tenant.quota.updated", 
            "tenant.suspended",
            "tenant.activated",
            "user.created",
            "user.updated",
            "user.login",
            "user.logout",
            "user.role.changed"
        ],
        subscriber_groups=[
            "tenant-service",
            "user-service",
            "billing-service",
            "audit-service",
            "admin-ui"
        ]
    ),
    
    # Real-time UI events - very high volume, very short retention
    "ui-realtime-events": TopicConfig(
        name="ui-realtime-events",
        partitions=200,
        replication_factor=2,  # Lower replication for performance
        retention_ms=600000,  # 10 minutes
        partition_strategy=PartitionStrategy.CUSTOMER_HASH,
        compression_type="snappy",
        event_types=[
            "dashboard.metrics.updated",
            "dashboard.chart.refreshed",
            "logs.live.stream",
            "metrics.live.update",
            "query.executed",
            "export.completed",
            "ui.user.action"
        ],
        subscriber_groups=[
            "websocket-service",
            "ui-service"
        ]
    ),
    
    # System and infrastructure events - low volume, broadcast
    "system-events": TopicConfig(
        name="system-events",
        partitions=10,
        replication_factor=3,
        retention_ms=2592000000,  # 30 days
        partition_strategy=PartitionStrategy.SERVICE_HASH,
        event_types=[
            "system.health.check",
            "system.service.started",
            "system.service.stopped",
            "query.expensive",
            "storage.usage.high",
            "security.threat.detected",
            "security.rule.triggered",
            "auth.failed.attempts"
        ],
        subscriber_groups=[
            "monitoring-service",
            "security-service",
            "admin-ui",
            "alert-engine"
        ]
    )
}


class TopicManager:
    """Manages Kafka topics and routing"""
    
    def __init__(self, topic_configs: Dict[str, TopicConfig] = None):
        self.topic_configs = topic_configs or TOPIC_CONFIGS
        self.event_type_to_topic = self._build_event_routing_map()
    
    def _build_event_routing_map(self) -> Dict[str, str]:
        """Build mapping from event type to topic"""
        routing_map = {}
        
        for topic_name, config in self.topic_configs.items():
            for event_type in config.event_types:
                if event_type in routing_map:
                    logger.warning(f"Event type {event_type} mapped to multiple topics")
                routing_map[event_type] = topic_name
        
        logger.info(f"Built event routing map for {len(routing_map)} event types")
        return routing_map
    
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
    return "usage-events"


def get_topic_for_alert_event(alert_action: str) -> str:
    """Get topic for alert events"""
    return "alert-events"


def get_topic_for_log_event(log_action: str) -> str:
    """Get topic for log events"""
    return "log-events"


def get_topic_for_ui_event(ui_action: str) -> str:
    """Get topic for UI events"""
    return "ui-realtime-events"


# Global topic manager instance
topic_manager = TopicManager()

logger.info("Topic configuration initialized with {} topics".format(len(TOPIC_CONFIGS)))