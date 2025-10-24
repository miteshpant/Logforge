"""
Simple Event System Constants
Configuration constants for the simple event system
"""

"""
Event Constants
Centralized constants for event types, topic names, and subscriber groups
"""

# ============================================================================
# TOPIC NAMES
# ============================================================================

# Main Kafka topics
TOPIC_USAGE_EVENTS = "usage-events"
TOPIC_ALERT_EVENTS = "alert-events"
TOPIC_LOG_EVENTS = "log-events"
TOPIC_TENANT_EVENTS = "tenant-events"
TOPIC_UI_REALTIME_EVENTS = "ui-realtime-events"
TOPIC_SYSTEM_EVENTS = "system-events"

# All topics list for validation
ALL_TOPICS = [
    TOPIC_USAGE_EVENTS,
    TOPIC_ALERT_EVENTS,
    TOPIC_LOG_EVENTS,
    TOPIC_TENANT_EVENTS,
    TOPIC_UI_REALTIME_EVENTS,
    TOPIC_SYSTEM_EVENTS
]

# ============================================================================
# USAGE & BILLING EVENT TYPES
# ============================================================================

# Usage tracking events
EVENT_USAGE_API_CALL = "usage.api.call"
EVENT_USAGE_INGESTION_BATCH = "usage.ingestion.batch"
EVENT_USAGE_QUERY_EXECUTION = "usage.query.execution"
EVENT_USAGE_STORAGE_OPERATION = "usage.storage.operation"
EVENT_USAGE_QUOTA_EXCEEDED = "usage.quota.exceeded"
EVENT_USAGE_COST_CALCULATED = "usage.cost.calculated"

# Billing events
EVENT_BILLING_SUBSCRIPTION_CHANGED = "billing.subscription_changed"
EVENT_BILLING_PAYMENT_PROCESSED = "billing.payment_processed"

# All usage event types
USAGE_EVENT_TYPES = [
    EVENT_USAGE_API_CALL,
    EVENT_USAGE_INGESTION_BATCH,
    EVENT_USAGE_QUERY_EXECUTION,
    EVENT_USAGE_STORAGE_OPERATION,
    EVENT_USAGE_QUOTA_EXCEEDED,
    EVENT_USAGE_COST_CALCULATED,
    EVENT_BILLING_SUBSCRIPTION_CHANGED,
    EVENT_BILLING_PAYMENT_PROCESSED
]

# ============================================================================
# ALERT EVENT TYPES
# ============================================================================

# Alert rule management
EVENT_ALERT_RULE_CREATED = "alert.rule.created"
EVENT_ALERT_RULE_UPDATED = "alert.rule.updated"
EVENT_ALERT_RULE_DELETED = "alert.rule.deleted"
EVENT_ALERT_RULE_ENABLED = "alert.rule.enabled"
EVENT_ALERT_RULE_DISABLED = "alert.rule.disabled"

# Alert lifecycle
EVENT_ALERT_TRIGGERED = "alert.triggered"
EVENT_ALERT_RESOLVED = "alert.resolved"
EVENT_ALERT_ACKNOWLEDGED = "alert.acknowledged"
EVENT_ALERT_ESCALATED = "alert.escalated"

# Notification events
EVENT_NOTIFICATION_SENT = "notification.sent"
EVENT_NOTIFICATION_FAILED = "notification.failed"

# All alert event types
ALERT_EVENT_TYPES = [
    EVENT_ALERT_RULE_CREATED,
    EVENT_ALERT_RULE_UPDATED,
    EVENT_ALERT_RULE_DELETED,
    EVENT_ALERT_RULE_ENABLED,
    EVENT_ALERT_RULE_DISABLED,
    EVENT_ALERT_TRIGGERED,
    EVENT_ALERT_RESOLVED,
    EVENT_ALERT_ACKNOWLEDGED,
    EVENT_ALERT_ESCALATED,
    EVENT_NOTIFICATION_SENT,
    EVENT_NOTIFICATION_FAILED
]

# ============================================================================
# LOG EVENT TYPES
# ============================================================================

# Log lifecycle events
EVENT_LOGS_BATCH_INGESTED = "logs.batch.ingested"
EVENT_LOGS_PARSING_FAILED = "logs.parsing.failed"
EVENT_LOGS_QUOTA_EXCEEDED = "logs.quota.exceeded"
EVENT_LOGS_REALTIME_BATCH = "logs.realtime.batch"
EVENT_LOGS_ARCHIVED = "logs.archived"
EVENT_LOGS_TTL_EXPIRED = "logs.ttl.expired"
EVENT_LOGS_RESTORED = "logs.restored"

# Additional log processing events
EVENT_LOGS_PARSED = "log.parsed"
EVENT_LOGS_INDEXED = "log.indexed"
EVENT_LOGS_DELETED = "log.deleted"

# All log event types
LOG_EVENT_TYPES = [
    EVENT_LOGS_BATCH_INGESTED,
    EVENT_LOGS_PARSING_FAILED,
    EVENT_LOGS_QUOTA_EXCEEDED,
    EVENT_LOGS_REALTIME_BATCH,
    EVENT_LOGS_ARCHIVED,
    EVENT_LOGS_TTL_EXPIRED,
    EVENT_LOGS_RESTORED,
    EVENT_LOGS_PARSED,
    EVENT_LOGS_INDEXED,
    EVENT_LOGS_DELETED
]

# ============================================================================
# TENANT & USER EVENT TYPES
# ============================================================================

# Tenant management events
EVENT_TENANT_CREATED = "tenant.created"
EVENT_TENANT_UPDATED = "tenant.updated"
EVENT_TENANT_QUOTA_UPDATED = "tenant.quota.updated"
EVENT_TENANT_SUSPENDED = "tenant.suspended"
EVENT_TENANT_ACTIVATED = "tenant.activated"

# User management events
EVENT_USER_CREATED = "user.created"
EVENT_USER_UPDATED = "user.updated"
EVENT_USER_LOGIN = "user.login"
EVENT_USER_LOGOUT = "user.logout"
EVENT_USER_ROLE_CHANGED = "user.role.changed"

# All tenant/user event types
TENANT_EVENT_TYPES = [
    EVENT_TENANT_CREATED,
    EVENT_TENANT_UPDATED,
    EVENT_TENANT_QUOTA_UPDATED,
    EVENT_TENANT_SUSPENDED,
    EVENT_TENANT_ACTIVATED,
    EVENT_USER_CREATED,
    EVENT_USER_UPDATED,
    EVENT_USER_LOGIN,
    EVENT_USER_LOGOUT,
    EVENT_USER_ROLE_CHANGED
]

# ============================================================================
# UI REAL-TIME EVENT TYPES
# ============================================================================

# Dashboard events
EVENT_DASHBOARD_METRICS_UPDATED = "dashboard.metrics.updated"
EVENT_DASHBOARD_CHART_REFRESHED = "dashboard.chart.refreshed"

# Real-time data events
EVENT_LOGS_LIVE_STREAM = "logs.live.stream"
EVENT_METRICS_LIVE_UPDATE = "metrics.live.update"

# User interaction events
EVENT_QUERY_EXECUTED = "query.executed"
EVENT_EXPORT_COMPLETED = "export.completed"
EVENT_UI_USER_ACTION = "ui.user.action"

# Alert UI events
EVENT_UI_ALERT_TRIGGERED = "ui.alert.triggered"
EVENT_UI_ALERT_ACKNOWLEDGED = "ui.alert.acknowledged"
EVENT_UI_ALERT_RESOLVED = "ui.alert.resolved"
EVENT_UI_ALERT_COUNT_UPDATED = "ui.alert.count.updated"
EVENT_UI_RULE_STATUS_CHANGED = "ui.rule.status.changed"

# All UI real-time event types
UI_REALTIME_EVENT_TYPES = [
    EVENT_DASHBOARD_METRICS_UPDATED,
    EVENT_DASHBOARD_CHART_REFRESHED,
    EVENT_LOGS_LIVE_STREAM,
    EVENT_METRICS_LIVE_UPDATE,
    EVENT_QUERY_EXECUTED,
    EVENT_EXPORT_COMPLETED,
    EVENT_UI_USER_ACTION,
    EVENT_UI_ALERT_TRIGGERED,
    EVENT_UI_ALERT_ACKNOWLEDGED,
    EVENT_UI_ALERT_RESOLVED,
    EVENT_UI_ALERT_COUNT_UPDATED,
    EVENT_UI_RULE_STATUS_CHANGED
]

# ============================================================================
# SYSTEM EVENT TYPES
# ============================================================================

# System health events
EVENT_SYSTEM_HEALTH_CHECK = "system.health.check"
EVENT_SYSTEM_SERVICE_STARTED = "system.service.started"
EVENT_SYSTEM_SERVICE_STOPPED = "system.service.stopped"

# Performance events
EVENT_QUERY_EXPENSIVE = "query.expensive"
EVENT_STORAGE_USAGE_HIGH = "storage.usage.high"

# Security events
EVENT_SECURITY_THREAT_DETECTED = "security.threat.detected"
EVENT_SECURITY_RULE_TRIGGERED = "security.rule.triggered"
EVENT_AUTH_FAILED_ATTEMPTS = "auth.failed.attempts"

# Additional system events
EVENT_SYSTEM_ERROR_OCCURRED = "system.error_occurred"
EVENT_SYSTEM_PERFORMANCE_METRIC = "system.performance_metric"

# All system event types
SYSTEM_EVENT_TYPES = [
    EVENT_SYSTEM_HEALTH_CHECK,
    EVENT_SYSTEM_SERVICE_STARTED,
    EVENT_SYSTEM_SERVICE_STOPPED,
    EVENT_QUERY_EXPENSIVE,
    EVENT_STORAGE_USAGE_HIGH,
    EVENT_SECURITY_THREAT_DETECTED,
    EVENT_SECURITY_RULE_TRIGGERED,
    EVENT_AUTH_FAILED_ATTEMPTS,
    EVENT_SYSTEM_ERROR_OCCURRED,
    EVENT_SYSTEM_PERFORMANCE_METRIC
]

# ============================================================================
# SUBSCRIBER GROUPS
# ============================================================================

# Usage & billing subscriber groups
SUBSCRIBER_USAGE_TRACKING_SERVICE = "usage-tracking-service"
SUBSCRIBER_BILLING_SERVICE = "billing-service"
SUBSCRIBER_ANALYTICS_SERVICE = "analytics-service"

# Alert subscriber groups
SUBSCRIBER_ALERT_ENGINE = "alert-engine"
SUBSCRIBER_NOTIFICATION_SERVICE = "notification-service"

# Storage & log subscriber groups
SUBSCRIBER_STORAGE_SERVICE = "storage-service"

# Tenant & user subscriber groups
SUBSCRIBER_TENANT_SERVICE = "tenant-service"
SUBSCRIBER_USER_SERVICE = "user-service"

# UI subscriber groups
SUBSCRIBER_UI_SERVICE = "ui-service"
SUBSCRIBER_WEBSOCKET_SERVICE = "websocket-service"

# System subscriber groups
SUBSCRIBER_MONITORING_SERVICE = "monitoring-service"
SUBSCRIBER_SECURITY_SERVICE = "security-service"
SUBSCRIBER_AUDIT_SERVICE = "audit-service"
SUBSCRIBER_ADMIN_UI = "admin-ui"

# All subscriber groups
ALL_SUBSCRIBER_GROUPS = [
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
    SUBSCRIBER_ADMIN_UI
]

# ============================================================================
# EVENT TYPE TO TOPIC MAPPING
# ============================================================================

EVENT_TYPE_TO_TOPIC = {
    # Usage events
    EVENT_USAGE_API_CALL: TOPIC_USAGE_EVENTS,
    EVENT_USAGE_INGESTION_BATCH: TOPIC_USAGE_EVENTS,
    EVENT_USAGE_QUERY_EXECUTION: TOPIC_USAGE_EVENTS,
    EVENT_USAGE_STORAGE_OPERATION: TOPIC_USAGE_EVENTS,
    EVENT_USAGE_QUOTA_EXCEEDED: TOPIC_USAGE_EVENTS,
    EVENT_USAGE_COST_CALCULATED: TOPIC_USAGE_EVENTS,
    EVENT_BILLING_SUBSCRIPTION_CHANGED: TOPIC_USAGE_EVENTS,
    EVENT_BILLING_PAYMENT_PROCESSED: TOPIC_USAGE_EVENTS,

    # Alert events
    EVENT_ALERT_RULE_CREATED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_RULE_UPDATED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_RULE_DELETED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_RULE_ENABLED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_RULE_DISABLED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_TRIGGERED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_RESOLVED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_ACKNOWLEDGED: TOPIC_ALERT_EVENTS,
    EVENT_ALERT_ESCALATED: TOPIC_ALERT_EVENTS,
    EVENT_NOTIFICATION_SENT: TOPIC_ALERT_EVENTS,
    EVENT_NOTIFICATION_FAILED: TOPIC_ALERT_EVENTS,

    # Log events
    EVENT_LOGS_BATCH_INGESTED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_PARSING_FAILED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_QUOTA_EXCEEDED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_REALTIME_BATCH: TOPIC_LOG_EVENTS,
    EVENT_LOGS_ARCHIVED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_TTL_EXPIRED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_RESTORED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_PARSED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_INDEXED: TOPIC_LOG_EVENTS,
    EVENT_LOGS_DELETED: TOPIC_LOG_EVENTS,

    # Tenant/User events
    EVENT_TENANT_CREATED: TOPIC_TENANT_EVENTS,
    EVENT_TENANT_UPDATED: TOPIC_TENANT_EVENTS,
    EVENT_TENANT_QUOTA_UPDATED: TOPIC_TENANT_EVENTS,
    EVENT_TENANT_SUSPENDED: TOPIC_TENANT_EVENTS,
    EVENT_TENANT_ACTIVATED: TOPIC_TENANT_EVENTS,
    EVENT_USER_CREATED: TOPIC_TENANT_EVENTS,
    EVENT_USER_UPDATED: TOPIC_TENANT_EVENTS,
    EVENT_USER_LOGIN: TOPIC_TENANT_EVENTS,
    EVENT_USER_LOGOUT: TOPIC_TENANT_EVENTS,
    EVENT_USER_ROLE_CHANGED: TOPIC_TENANT_EVENTS,

    # UI Real-time events
    EVENT_DASHBOARD_METRICS_UPDATED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_DASHBOARD_CHART_REFRESHED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_LOGS_LIVE_STREAM: TOPIC_UI_REALTIME_EVENTS,
    EVENT_METRICS_LIVE_UPDATE: TOPIC_UI_REALTIME_EVENTS,
    EVENT_QUERY_EXECUTED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_EXPORT_COMPLETED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_USER_ACTION: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_ALERT_TRIGGERED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_ALERT_ACKNOWLEDGED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_ALERT_RESOLVED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_ALERT_COUNT_UPDATED: TOPIC_UI_REALTIME_EVENTS,
    EVENT_UI_RULE_STATUS_CHANGED: TOPIC_UI_REALTIME_EVENTS,

    # System events
    EVENT_SYSTEM_HEALTH_CHECK: TOPIC_SYSTEM_EVENTS,
    EVENT_SYSTEM_SERVICE_STARTED: TOPIC_SYSTEM_EVENTS,
    EVENT_SYSTEM_SERVICE_STOPPED: TOPIC_SYSTEM_EVENTS,
    EVENT_QUERY_EXPENSIVE: TOPIC_SYSTEM_EVENTS,
    EVENT_STORAGE_USAGE_HIGH: TOPIC_SYSTEM_EVENTS,
    EVENT_SECURITY_THREAT_DETECTED: TOPIC_SYSTEM_EVENTS,
    EVENT_SECURITY_RULE_TRIGGERED: TOPIC_SYSTEM_EVENTS,
    EVENT_AUTH_FAILED_ATTEMPTS: TOPIC_SYSTEM_EVENTS,
    EVENT_SYSTEM_ERROR_OCCURRED: TOPIC_SYSTEM_EVENTS,
    EVENT_SYSTEM_PERFORMANCE_METRIC: TOPIC_SYSTEM_EVENTS
}

# ============================================================================
# TOPIC TO SUBSCRIBER GROUPS MAPPING
# ============================================================================

TOPIC_TO_SUBSCRIBER_GROUPS = {
    TOPIC_USAGE_EVENTS: [
        SUBSCRIBER_USAGE_TRACKING_SERVICE,
        SUBSCRIBER_BILLING_SERVICE,
        SUBSCRIBER_ANALYTICS_SERVICE,
        SUBSCRIBER_UI_SERVICE
    ],
    TOPIC_ALERT_EVENTS: [
        SUBSCRIBER_ALERT_ENGINE,
        SUBSCRIBER_NOTIFICATION_SERVICE,
        SUBSCRIBER_UI_SERVICE,
        SUBSCRIBER_AUDIT_SERVICE
    ],
    TOPIC_LOG_EVENTS: [
        SUBSCRIBER_ALERT_ENGINE,
        SUBSCRIBER_USAGE_TRACKING_SERVICE,
        SUBSCRIBER_STORAGE_SERVICE,
        SUBSCRIBER_UI_SERVICE
    ],
    TOPIC_TENANT_EVENTS: [
        SUBSCRIBER_TENANT_SERVICE,
        SUBSCRIBER_USER_SERVICE,
        SUBSCRIBER_BILLING_SERVICE,
        SUBSCRIBER_AUDIT_SERVICE,
        SUBSCRIBER_ADMIN_UI
    ],
    TOPIC_UI_REALTIME_EVENTS: [
        SUBSCRIBER_WEBSOCKET_SERVICE,
        SUBSCRIBER_UI_SERVICE
    ],
    TOPIC_SYSTEM_EVENTS: [
        SUBSCRIBER_MONITORING_SERVICE,
        SUBSCRIBER_SECURITY_SERVICE,
        SUBSCRIBER_ADMIN_UI,
        SUBSCRIBER_ALERT_ENGINE
    ]
}

# ============================================================================
# ALL EVENT TYPES (for validation)
# ============================================================================

ALL_EVENT_TYPES = (
    USAGE_EVENT_TYPES +
    ALERT_EVENT_TYPES +
    LOG_EVENT_TYPES +
    TENANT_EVENT_TYPES +
    UI_REALTIME_EVENT_TYPES +
    SYSTEM_EVENT_TYPES
)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_topic_for_event_type(event_type: str) -> str:
    """Get topic name for an event type"""
    return EVENT_TYPE_TO_TOPIC.get(event_type, TOPIC_SYSTEM_EVENTS)


def get_subscriber_groups_for_topic(topic_name: str) -> list[str]:
    """Get subscriber groups for a topic"""
    return TOPIC_TO_SUBSCRIBER_GROUPS.get(topic_name, [])


def get_event_types_for_topic(topic_name: str) -> list[str]:
    """Get all event types for a topic"""
    return [
        event_type for event_type, topic in EVENT_TYPE_TO_TOPIC.items()
        if topic == topic_name
    ]


def is_valid_event_type(event_type: str) -> bool:
    """Check if event type is valid"""
    return event_type in ALL_EVENT_TYPES


def is_valid_topic(topic_name: str) -> bool:
    """Check if topic name is valid"""
    return topic_name in ALL_TOPICS


def is_valid_subscriber_group(subscriber_group: str) -> bool:
    """Check if subscriber group is valid"""
    return subscriber_group in ALL_SUBSCRIBER_GROUPS


# ============================================================================
# VALIDATION CONSTANTS
# ============================================================================

# Maximum lengths for validation
MAX_EVENT_TYPE_LENGTH = 100
MAX_TOPIC_NAME_LENGTH = 50
MAX_SUBSCRIBER_GROUP_LENGTH = 50

# Event type pattern validation
VALID_EVENT_TYPE_PATTERN = r"^[a-z][a-z0-9]*\.[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)*$"

# Topic configuration defaults
DEFAULT_PARTITIONS = 10
DEFAULT_REPLICATION_FACTOR = 3
DEFAULT_RETENTION_MS = 86400000  # 24 hours
DEFAULT_MAX_MESSAGE_BYTES = 1048576  # 1MB
DEFAULT_COMPRESSION_TYPE = "lz4"

# Usage tracking buffer configuration
USAGE_BATCH_SIZE = 100  # Number of usage records to batch before flushing
USAGE_FLUSH_INTERVAL_SECONDS = 30  # Flush usage records every 30 seconds

# Event system configuration
DEFAULT_PARTITION_COUNT = 3  # Number of partitions for tenant-based partitioning
DEFAULT_CONSUMER_GROUP = "logforge-simple-consumer"
DEFAULT_TOPIC_NAME = "log-ingestion-events"

# Retry and timeout configuration
PRODUCER_RETRY_ATTEMPTS = 3
CONSUMER_RETRY_ATTEMPTS = 3
CONNECTION_TIMEOUT_SECONDS = 30
PROCESSING_TIMEOUT_SECONDS = 60

# Event processing configuration
EVENT_BATCH_SIZE = 50  # Number of events to process in a batch
EVENT_PROCESSING_INTERVAL_SECONDS = 10  # Process events every 10 seconds

# ============================================================================
# REDIS CACHE CONSTANTS
# ============================================================================

# Alert rule cache keys
ALERT_RULE_CACHE_PREFIX = "alerts:rules:"
ALERT_COOLDOWN_CACHE_PREFIX = "alerts:cooldown:"
ALERT_CACHE_METADATA_KEY = "alerts:cache:metadata"
