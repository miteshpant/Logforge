-- Migration 004: Add threat hunting campaigns table for Phase 2 async processing
-- Creates table to track threat hunting campaign status and progress

CREATE TABLE IF NOT EXISTS threat_hunting_campaigns_mt
(
    id String,
    customer_id String,
    description String,
    status Enum8(
        'started' = 1,
        'running' = 2,
        'completed' = 3,
        'failed' = 4,
        'cancelled' = 5
    ) DEFAULT 'started',
    time_range String DEFAULT '24h',
    severity_filter Array(String),
    rule_ids Array(String),
    created_at DateTime64(3) DEFAULT now64(3),
    started_at DateTime64(3),
    completed_at DateTime64(3),
    rules_evaluated UInt32 DEFAULT 0,
    events_found UInt32 DEFAULT 0,
    indicators_detected UInt32 DEFAULT 0,
    progress_percentage UInt8 DEFAULT 0,
    error_message Nullable(String)
)
ENGINE = MergeTree()
ORDER BY (customer_id, created_at)
PARTITION BY customer_id;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON threat_hunting_campaigns_mt (status) TYPE bloom_filter GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_campaigns_time_range ON threat_hunting_campaigns_mt (time_range) TYPE bloom_filter GRANULARITY 1;

-- Migration record will be tracked automatically by the migration runner