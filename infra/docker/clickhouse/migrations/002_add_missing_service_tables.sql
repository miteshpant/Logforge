-- Migration 002: Add missing service tables
-- This can be run on existing ClickHouse instances without data loss

-- Alert events table (used by AlertService)
CREATE TABLE IF NOT EXISTS alert_events_mt (
    id String,
    rule_id String,
    event_type Enum8('triggered' = 1, 'resolved' = 2, 'acknowledged' = 3),
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    message String,
    details String, -- JSON blob
    triggered_at DateTime64(3) DEFAULT now64(3),
    resolved_at Nullable(DateTime64(3)),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(triggered_at))
ORDER BY (customer_id, rule_id, triggered_at)
SETTINGS index_granularity = 8192;

-- Alert notifications table (used by AlertService)
CREATE TABLE IF NOT EXISTS alert_notifications_mt (
    id String,
    alert_event_id String,
    channel_id String,
    notification_type Enum8('email' = 1, 'slack' = 2, 'webhook' = 3, 'pagerduty' = 4),
    status Enum8('pending' = 1, 'sent' = 2, 'failed' = 3, 'delivered' = 4),
    sent_at Nullable(DateTime64(3)),
    delivery_attempts UInt8 DEFAULT 0,
    error_message Nullable(String),
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(created_at))
ORDER BY (customer_id, alert_event_id, created_at)
SETTINGS index_granularity = 8192;

-- Ingestion statistics table (used by IngestionService/IngestionDAO)
CREATE TABLE IF NOT EXISTS ingestion_stats_mt (
    id String,
    endpoint String,
    format_type String,
    records_ingested UInt64,
    bytes_ingested UInt64,
    processing_time_ms UInt32,
    errors_count UInt32 DEFAULT 0,
    timestamp DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(timestamp))
ORDER BY (customer_id, endpoint, timestamp)
SETTINGS index_granularity = 8192;

-- Roles table (used by HealthService)
CREATE TABLE IF NOT EXISTS roles_mt (
    id String,
    name String,
    description String,
    permissions Array(String),
    is_system_role UInt8 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Storage metadata table (used by StorageService)
CREATE TABLE IF NOT EXISTS storage_metadata_mt (
    id String,
    storage_path String,
    storage_type Enum8('hot' = 1, 'warm' = 2, 'cold' = 3, 'archive' = 4),
    file_size_bytes UInt64,
    compressed_size_bytes UInt64,
    record_count UInt64,
    created_at DateTime64(3) DEFAULT now64(3),
    last_accessed Nullable(DateTime64(3)),
    checksum String,
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(created_at))
ORDER BY (customer_id, storage_type, created_at)
SETTINGS index_granularity = 8192;