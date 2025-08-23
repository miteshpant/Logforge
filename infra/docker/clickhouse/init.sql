-- Create logforge database
CREATE DATABASE IF NOT EXISTS logforge;
USE logforge;

-- Enable experimental features for JSON support
SET allow_experimental_object_type = 1;

-- S3 storage policy will be configured via config.d/s3_storage.xml

-- Create logs_raw table for incoming log data with enhanced schema
CREATE TABLE IF NOT EXISTS logs_raw (
    ts DateTime64(3, 'UTC'),
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String CODEC(ZSTD(3)),  -- Compress message field
    trace_id String,
    span_id String DEFAULT '',
    attrs String CODEC(ZSTD(3)),  -- Compress attributes
    status UInt16 DEFAULT 0,
    src_ip IPv4 DEFAULT toIPv4('0.0.0.0'),
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
    date Date MATERIALIZED toDate(ts),  -- For fast date-based filtering
    hour UInt8 MATERIALIZED toHour(ts), -- For time-based aggregations
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String CODEC(ZSTD(3)),
    trace_id String,
    span_id String,
    status UInt16,
    src_ip IPv4,
    user_id String,
    severity_num UInt8,
    facility UInt8,
    -- Extracted and parsed fields
    extracted_user_id String,
    extracted_ip IPv4,
    http_method LowCardinality(String),
    http_uri String CODEC(ZSTD(3)),
    http_status UInt16,
    http_response_time_ms UInt32,
    http_bytes UInt64,
    -- Common log patterns
    error_code String DEFAULT '',
    error_category LowCardinality(String) DEFAULT '',
    -- Parsed timestamp components for fast filtering
    ingested_at DateTime64(3, 'UTC'),
    -- Computed fields for analytics
    is_error UInt8 MATERIALIZED multiIf(level = 'error', 1, http_status >= 400, 1, 0),
    is_slow UInt8 MATERIALIZED if(http_response_time_ms > 1000, 1, 0)
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
    toIPv4OrDefault(coalesce(JSONExtractString(attrs, 'ip'), JSONExtractString(attrs, 'clientIP'), toString(src_ip))) as extracted_ip,
    upper(JSONExtractString(attrs, 'method')) as http_method,
    JSONExtractString(attrs, 'uri') as http_uri,
    coalesce(JSONExtractUInt(attrs, 'status'), JSONExtractUInt(attrs, 'statusCode'), status) as http_status,
    coalesce(JSONExtractUInt(attrs, 'duration_ms'), JSONExtractUInt(attrs, 'responseTime'), 0) as http_response_time_ms,
    coalesce(JSONExtractUInt(attrs, 'bytes'), JSONExtractUInt(attrs, 'contentLength'), 0) as http_bytes,
    JSONExtractString(attrs, 'error_code') as error_code,
    JSONExtractString(attrs, 'error_category') as error_category
FROM logs_raw;

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_logs_raw_trace_id ON logs_raw (trace_id) TYPE bloom_filter(0.01);
CREATE INDEX IF NOT EXISTS idx_logs_raw_user_id ON logs_raw (user_id) TYPE bloom_filter(0.01);
CREATE INDEX IF NOT EXISTS idx_logs_raw_msg ON logs_raw (msg) TYPE tokenbf_v1(32768, 3, 0);
CREATE INDEX IF NOT EXISTS idx_logs_normalized_extracted_user_id ON logs_normalized (extracted_user_id) TYPE bloom_filter(0.01);
CREATE INDEX IF NOT EXISTS idx_logs_normalized_http_uri ON logs_normalized (http_uri) TYPE bloom_filter(0.01);

-- Create aggregated tables for fast analytics
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
    total_bytes UInt64,
    unique_ips UInt32
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
    sum(http_bytes) as total_bytes,
    uniqHLL12(extracted_ip) as unique_ips
FROM logs_normalized
GROUP BY hour, service, level, host;

-- Create table for storing parsed log patterns/templates
CREATE TABLE IF NOT EXISTS log_patterns (
    pattern_hash UInt64,
    service LowCardinality(String),
    level LowCardinality(String),
    template String,
    first_seen DateTime,
    last_seen DateTime,
    occurrence_count UInt64,
    example_message String
)
ENGINE = ReplacingMergeTree(last_seen)
PARTITION BY service
ORDER BY (service, level, pattern_hash)
SETTINGS index_granularity = 8192;

-- Create user session tracking table
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id String,
    user_id String,
    start_time DateTime64(3, 'UTC'),
    end_time DateTime64(3, 'UTC'),
    total_requests UInt32,
    error_requests UInt32,
    unique_ips Array(IPv4),
    services Array(LowCardinality(String)),
    last_activity DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(last_activity)
PARTITION BY toDate(start_time)
ORDER BY (user_id, start_time)
TTL toDateTime(start_time) + toIntervalDay(30) DELETE
SETTINGS index_granularity = 8192;

-- Create functions for common log analysis tasks
CREATE OR REPLACE FUNCTION extractLogLevel(msg String) -> String AS (msg) -> 
multiIf(
    match(msg, '(?i)(fatal|critical)'), 'fatal',
    match(msg, '(?i)error'), 'error', 
    match(msg, '(?i)(warn|warning)'), 'warn',
    match(msg, '(?i)info'), 'info',
    match(msg, '(?i)debug'), 'debug',
    'info'
);

CREATE OR REPLACE FUNCTION isSlowQuery(response_time_ms UInt32, uri String) -> UInt8 AS (response_time_ms, uri) ->
multiIf(
    match(uri, '(?i)/(api|admin)'), if(response_time_ms > 2000, 1, 0),
    match(uri, '(?i)/(static|assets)'), if(response_time_ms > 500, 1, 0),
    if(response_time_ms > 1000, 1, 0)
);

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