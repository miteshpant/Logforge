-- Migration 018: threat intelligence feeds and indicators (Phase 3)
--
-- threat_feeds_mt: each tenant's feed configurations (one row version per
-- change, read FINAL). A feed's API key is NOT stored here: secret_env names
-- the environment variable that holds it.
-- threat_indicators_mt: the tenant's indicators from feeds and manual entry,
-- one row per (type, value), latest version wins; expired rows are dropped
-- 30 days after expiry.

CREATE TABLE IF NOT EXISTS threat_feeds_mt
(
    tenant_id String,
    id String,
    name String,
    kind LowCardinality(String),
    url String,
    method LowCardinality(String),
    body String,
    auth_header String,
    secret_env String,
    options String,
    interval_minutes UInt32,
    confidence UInt8,
    ttl_days UInt32,
    enabled UInt8,
    last_run_at Nullable(DateTime64(3)),
    last_status LowCardinality(String),
    last_error String,
    last_count UInt64,
    created_at DateTime64(3),
    deleted UInt8 DEFAULT 0,
    version UInt64
)
ENGINE = ReplacingMergeTree(version)
ORDER BY (tenant_id, id);

CREATE TABLE IF NOT EXISTS threat_indicators_mt
(
    tenant_id String,
    indicator_type LowCardinality(String),
    value String,
    threat_type String,
    confidence UInt8,
    source String,
    feed_id String,
    tags Array(String),
    first_seen Nullable(DateTime64(3)),
    last_seen Nullable(DateTime64(3)),
    expires_at Nullable(DateTime64(3)),
    reference String,
    description String,
    updated_at DateTime64(3),
    deleted UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, indicator_type, value)
TTL toDateTime(coalesce(expires_at, toDateTime64('2106-01-01 00:00:00', 3))) + INTERVAL 30 DAY;
