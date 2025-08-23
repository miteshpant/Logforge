-- Create logforge database
CREATE DATABASE IF NOT EXISTS logforge;
USE logforge;

-- Enable experimental features for JSON support
SET allow_experimental_object_type = 1;

-- Create logs_raw table for incoming log data with enhanced schema
CREATE TABLE IF NOT EXISTS logs_raw (
    ts DateTime64(3, 'UTC'),
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    span_id String DEFAULT '',
    attrs String,
    status UInt16 DEFAULT 0,
    src_ip String DEFAULT '',
    user_id String DEFAULT '',
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(),
    -- Additional indexed fields for common queries
    severity_num UInt8 DEFAULT 0,  -- Numeric severity for ordering
    facility UInt8 DEFAULT 16,     -- Syslog facility
    parser_version String DEFAULT 'v1'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)  -- Monthly partitions for better management
ORDER BY (service, level, ts, host)  -- Optimized sort key
PRIMARY KEY (service, level, ts)
TTL toDateTime(ts) + toIntervalDay(7)  -- Basic TTL for now
SETTINGS index_granularity = 8192;

-- Create table for storing the materialized view data with enhanced schema
CREATE TABLE IF NOT EXISTS logs_normalized (
    ts DateTime64(3, 'UTC'),
    date Date,  -- For fast date-based filtering
    hour UInt8, -- For time-based aggregations
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    span_id String,
    status UInt16,
    src_ip String,
    user_id String,
    severity_num UInt8,
    facility UInt8,
    -- Extracted and parsed fields
    extracted_user_id String,
    extracted_ip String,
    http_method LowCardinality(String),
    http_uri String,
    http_status UInt16,
    http_response_time_ms UInt32,
    http_bytes UInt64,
    -- Common log patterns
    error_code String DEFAULT '',
    error_category LowCardinality(String) DEFAULT '',
    -- Parsed timestamp components for fast filtering
    ingested_at DateTime64(3, 'UTC'),
    -- Computed fields for analytics
    is_error UInt8,
    is_slow UInt8
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)  -- Monthly partitions to match logs_raw
ORDER BY (service, level, date, ts, host)
PRIMARY KEY (service, level, date)
TTL toDateTime(ts) + toIntervalDay(7)  -- Basic TTL for now
SETTINGS index_granularity = 8192;

-- Create materialized view for normalized log data with enhanced parsing
CREATE MATERIALIZED VIEW IF NOT EXISTS logs_view
TO logs_normalized
AS SELECT 
    ts,
    toDate(ts) as date,
    toHour(ts) as hour,
    host,
    service,
    level,
    msg,
    trace_id,
    span_id,
    status,
    src_ip,
    user_id,
    severity_num,
    facility,
    ingested_at,
    -- Enhanced JSON extraction with fallbacks
    coalesce(JSONExtractString(attrs, 'user_id'), JSONExtractString(attrs, 'userId'), user_id) as extracted_user_id,
    coalesce(JSONExtractString(attrs, 'ip'), JSONExtractString(attrs, 'clientIP'), src_ip) as extracted_ip,
    upper(JSONExtractString(attrs, 'method')) as http_method,
    JSONExtractString(attrs, 'uri') as http_uri,
    coalesce(JSONExtractUInt(attrs, 'status'), JSONExtractUInt(attrs, 'statusCode'), status) as http_status,
    coalesce(JSONExtractUInt(attrs, 'duration_ms'), JSONExtractUInt(attrs, 'responseTime'), 0) as http_response_time_ms,
    coalesce(JSONExtractUInt(attrs, 'bytes'), JSONExtractUInt(attrs, 'contentLength'), 0) as http_bytes,
    JSONExtractString(attrs, 'error_code') as error_code,
    JSONExtractString(attrs, 'error_category') as error_category,
    multiIf(level = 'error', 1, http_status >= 400, 1, 0) as is_error,
    if(http_response_time_ms > 1000, 1, 0) as is_slow
FROM logs_raw;

-- Create aggregated table for fast analytics
CREATE TABLE IF NOT EXISTS logs_hourly_stats (
    hour DateTime,
    service LowCardinality(String),
    level LowCardinality(String),
    host LowCardinality(String),
    total_count UInt64,
    error_count UInt64,
    unique_users UInt64,
    avg_response_time Float64,
    p95_response_time Float64,
    total_bytes UInt64
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (hour, service, level, host)
TTL toDateTime(hour) + toIntervalDay(90) DELETE
SETTINGS index_granularity = 8192;

-- Create materialized view for hourly aggregations
CREATE MATERIALIZED VIEW IF NOT EXISTS logs_hourly_stats_mv
TO logs_hourly_stats
AS SELECT 
    toStartOfHour(ts) as hour,
    service,
    level,
    host,
    count() as total_count,
    countIf(is_error = 1) as error_count,
    uniqHLL12(extracted_user_id) as unique_users,
    avg(http_response_time_ms) as avg_response_time,
    quantile(0.95)(http_response_time_ms) as p95_response_time,
    sum(http_bytes) as total_bytes
FROM logs_normalized
GROUP BY hour, service, level, host;

-- Create views for common queries
CREATE VIEW IF NOT EXISTS recent_errors AS
SELECT 
    ts,
    service,
    level,
    host,
    msg,
    http_status,
    extracted_user_id,
    extracted_ip
FROM logs_normalized 
WHERE ts > now() - INTERVAL 1 HOUR 
  AND is_error = 1
ORDER BY ts DESC;

CREATE VIEW IF NOT EXISTS service_health_summary AS
SELECT 
    service,
    count() as total_requests,
    countIf(is_error = 1) as error_count,
    round(countIf(is_error = 1) * 100.0 / count(), 2) as error_rate_percent,
    round(avg(http_response_time_ms), 2) as avg_response_time_ms,
    round(quantile(0.95)(http_response_time_ms), 2) as p95_response_time_ms,
    uniqHLL12(extracted_user_id) as unique_users,
    max(ts) as last_seen
FROM logs_normalized 
WHERE ts > now() - INTERVAL 1 HOUR
GROUP BY service
ORDER BY error_rate_percent DESC;

-- Tables, views, and functions are created successfully