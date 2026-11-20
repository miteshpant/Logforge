-- Scheduled reports (Phase 13, docs/response.md): a security operations
-- report sent daily, weekly or monthly, as PDF or CSV, through an email
-- integration. Latest version per (tenant, id) wins; last_sent is updated
-- by the scheduler after each send.

CREATE TABLE IF NOT EXISTS report_schedules_mt
(
    customer_id String,
    id String,
    name String,
    every LowCardinality(String),
    hour UInt8,
    format LowCardinality(String),
    integration_id String,
    recipients Array(String),
    enabled UInt8 DEFAULT 1,
    deleted UInt8 DEFAULT 0,
    last_sent Nullable(DateTime64(3, 'UTC')),
    last_error String DEFAULT '',
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);
