-- Create logforge database
CREATE DATABASE IF NOT EXISTS logforge;
USE logforge;

-- Enable experimental features for JSON support
SET allow_experimental_object_type = 1;

-- Create logs_raw table for incoming log data
CREATE TABLE IF NOT EXISTS logs_raw (
    ts DateTime64(3, 'UTC'),
    host String,
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    attrs String,
    status UInt16 DEFAULT 0,
    src_ip String DEFAULT '',
    user_id String DEFAULT ''
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, ts)
TTL toDateTime(ts) + toIntervalDay(7)
SETTINGS index_granularity = 8192;

-- Create table for storing the materialized view data
CREATE TABLE IF NOT EXISTS logs_normalized (
    ts DateTime64(3, 'UTC'),
    host String,
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    status UInt16,
    src_ip String,
    user_id String,
    extracted_user_id String,
    extracted_ip String,
    http_method String,
    http_uri String,
    http_status UInt16,
    duration_ms UInt32
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (service, level, ts)
TTL toDateTime(ts) + toIntervalDay(7)
SETTINGS index_granularity = 8192;

-- Create materialized view for normalized log data
CREATE MATERIALIZED VIEW IF NOT EXISTS logs_view
TO logs_normalized
AS SELECT 
    ts,
    host,
    service,
    level,
    msg,
    trace_id,
    status,
    src_ip,
    user_id,
    JSONExtractString(attrs, 'user_id') as extracted_user_id,
    JSONExtractString(attrs, 'ip') as extracted_ip,
    JSONExtractString(attrs, 'method') as http_method,
    JSONExtractString(attrs, 'uri') as http_uri,
    JSONExtractUInt(attrs, 'status') as http_status,
    JSONExtractUInt(attrs, 'duration_ms') as duration_ms
FROM logs_raw;

-- Tables and views are created successfully