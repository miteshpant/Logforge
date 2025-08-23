-- Enhanced ClickHouse schema with TTL policies and cold storage
-- Logforge: Advanced SIEM Platform - Hot/Cold Storage Architecture

-- Create logforge database
CREATE DATABASE IF NOT EXISTS logforge;
USE logforge;

-- Enable experimental features for JSON support
SET allow_experimental_object_type = 1;

-- Create storage policies for hot/cold data tiering
-- Hot storage: Local NVMe/SSD for recent data (7-30 days)
-- Cold storage: Multi-cloud object storage for archived data (30+ days)

-- Main logs table with enhanced TTL and storage policies
CREATE TABLE IF NOT EXISTS logs_raw (
    ts DateTime64(3, 'UTC'),
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String CODEC(LZ4HC),
    trace_id String,
    span_id String DEFAULT '',
    attrs String CODEC(LZ4HC),
    status UInt16 DEFAULT 0,
    src_ip String DEFAULT '',
    user_id String DEFAULT '',
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(),
    -- Additional indexed fields for common queries
    severity_num UInt8 DEFAULT 0,
    facility UInt8 DEFAULT 16,
    parser_version String DEFAULT 'v1',
    -- Customer and deployment tracking
    customer_id String DEFAULT 'shared' CODEC(LZ4),
    deployment_type LowCardinality(String) DEFAULT 'shared'
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(ts), customer_id)  -- Monthly partitions by customer
ORDER BY (customer_id, service, level, ts, host)
PRIMARY KEY (customer_id, service, level, ts)
-- TTL Configuration for data lifecycle management
TTL 
    -- Move to cold storage after 30 days
    toDateTime(ts) + toIntervalDay(30) TO VOLUME 'cold',
    -- Delete after retention period (configurable per customer)
    toDateTime(ts) + toIntervalDay(365) DELETE,
    -- Delete old partitions after 7 years (compliance)
    toDate(ts) + toIntervalYear(7) DELETE
SETTINGS 
    index_granularity = 8192,
    -- Enable compression for better storage efficiency
    compress_marks = 1,
    compress_primary_key = 1,
    -- Optimize for write-heavy workload
    merge_with_ttl_timeout = 3600,
    ttl_only_drop_parts = 1;

-- Normalized logs table with intelligent data tiering
CREATE TABLE IF NOT EXISTS logs_normalized (
    ts DateTime64(3, 'UTC'),
    date Date CODEC(Delta, LZ4),
    hour UInt8,
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String CODEC(LZ4HC),
    trace_id String,
    span_id String,
    status UInt16,
    src_ip IPv4,
    user_id String,
    severity_num UInt8,
    facility UInt8,
    -- Customer context
    customer_id String DEFAULT 'shared',
    deployment_type LowCardinality(String) DEFAULT 'shared',
    -- Enhanced extracted fields with better compression
    extracted_user_id String CODEC(LZ4),
    extracted_ip IPv4,
    http_method LowCardinality(String),
    http_uri String CODEC(LZ4),
    http_status UInt16,
    http_response_time_ms UInt32,
    http_bytes UInt64 CODEC(Delta, LZ4),
    -- Security and error analysis fields
    error_code String DEFAULT '' CODEC(LZ4),
    error_category LowCardinality(String) DEFAULT '',
    security_event_type LowCardinality(String) DEFAULT '',
    threat_level UInt8 DEFAULT 0,
    -- Parsed timestamp components
    ingested_at DateTime64(3, 'UTC'),
    -- Computed analytics fields
    is_error UInt8,
    is_slow UInt8,
    is_security_event UInt8 DEFAULT 0,
    -- Geographic and device info
    geo_country LowCardinality(String) DEFAULT '',
    geo_city LowCardinality(String) DEFAULT '',
    user_agent_family LowCardinality(String) DEFAULT '',
    device_type LowCardinality(String) DEFAULT ''
)
ENGINE = MergeTree()
PARTITION BY (toYYYYMM(ts), customer_id)
ORDER BY (customer_id, service, level, date, ts, host)
PRIMARY KEY (customer_id, service, level, date)
-- Advanced TTL with customer-specific retention
TTL 
    -- Hot data: Keep for 30 days on fast storage
    toDateTime(ts) + toIntervalDay(30) TO VOLUME 'cold',
    -- Standard retention: 1 year for most customers
    toDateTime(ts) + toIntervalDay(365) DELETE,
    -- Extended retention for compliance customers
    toDateTime(ts) + 
        multiIf(
            deployment_type = 'fedramp', toIntervalYear(7),    -- 7 years for government
            deployment_type = 'healthcare', toIntervalYear(6), -- 6 years for HIPAA
            deployment_type = 'financial', toIntervalYear(7),  -- 7 years for SOX
            toIntervalYear(3)  -- 3 years default for enterprise
        ) DELETE
SETTINGS 
    index_granularity = 8192,
    compress_marks = 1,
    compress_primary_key = 1;

-- Enhanced materialized view with security analytics
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
    -- Convert IPs to proper IPv4 type with validation
    if(isValidUTF8(src_ip) AND position(src_ip, '.') > 0, toIPv4OrNull(src_ip), toIPv4('0.0.0.0')) as src_ip,
    user_id,
    severity_num,
    facility,
    ingested_at,
    -- Extract customer context from attributes
    coalesce(JSONExtractString(attrs, 'customer_id'), 'shared') as customer_id,
    coalesce(JSONExtractString(attrs, 'deployment_type'), 'shared') as deployment_type,
    -- Enhanced JSON extraction with multiple fallbacks
    coalesce(
        JSONExtractString(attrs, 'user_id'), 
        JSONExtractString(attrs, 'userId'), 
        JSONExtractString(attrs, 'username'),
        user_id
    ) as extracted_user_id,
    if(isValidUTF8(JSONExtractString(attrs, 'ip')) AND position(JSONExtractString(attrs, 'ip'), '.') > 0,
       toIPv4OrNull(JSONExtractString(attrs, 'ip')), 
       if(isValidUTF8(src_ip) AND position(src_ip, '.') > 0, toIPv4OrNull(src_ip), toIPv4('0.0.0.0'))
    ) as extracted_ip,
    upper(coalesce(JSONExtractString(attrs, 'method'), JSONExtractString(attrs, 'http_method'))) as http_method,
    coalesce(JSONExtractString(attrs, 'uri'), JSONExtractString(attrs, 'url'), JSONExtractString(attrs, 'path')) as http_uri,
    coalesce(JSONExtractUInt(attrs, 'status'), JSONExtractUInt(attrs, 'statusCode'), JSONExtractUInt(attrs, 'http_status'), status) as http_status,
    coalesce(JSONExtractUInt(attrs, 'duration_ms'), JSONExtractUInt(attrs, 'responseTime'), JSONExtractUInt(attrs, 'latency'), 0) as http_response_time_ms,
    coalesce(JSONExtractUInt(attrs, 'bytes'), JSONExtractUInt(attrs, 'contentLength'), JSONExtractUInt(attrs, 'body_bytes_sent'), 0) as http_bytes,
    -- Error analysis
    coalesce(JSONExtractString(attrs, 'error_code'), JSONExtractString(attrs, 'errorCode')) as error_code,
    coalesce(JSONExtractString(attrs, 'error_category'), JSONExtractString(attrs, 'category')) as error_category,
    -- Security event detection
    coalesce(JSONExtractString(attrs, 'security_event_type'), 
             if(level = 'error' AND (position(lower(msg), 'attack') > 0 OR position(lower(msg), 'intrusion') > 0 OR position(lower(msg), 'breach') > 0), 'security_incident', '')
    ) as security_event_type,
    coalesce(JSONExtractUInt(attrs, 'threat_level'), 
             multiIf(level = 'fatal', 5, level = 'error', 4, level = 'warn', 3, 1)
    ) as threat_level,
    -- Geographic and device extraction
    coalesce(JSONExtractString(attrs, 'geo_country'), JSONExtractString(attrs, 'country')) as geo_country,
    coalesce(JSONExtractString(attrs, 'geo_city'), JSONExtractString(attrs, 'city')) as geo_city,
    coalesce(JSONExtractString(attrs, 'user_agent_family'), JSONExtractString(attrs, 'browser')) as user_agent_family,
    coalesce(JSONExtractString(attrs, 'device_type'), JSONExtractString(attrs, 'device')) as device_type,
    -- Computed analytics fields
    multiIf(
        level = 'error', 1, 
        level = 'fatal', 1,
        http_status >= 400, 1, 
        position(lower(msg), 'error') > 0, 1,
        position(lower(msg), 'fail') > 0, 1,
        0
    ) as is_error,
    if(http_response_time_ms > 1000, 1, 0) as is_slow,
    multiIf(
        security_event_type != '', 1,
        position(lower(msg), 'login') > 0 AND level = 'error', 1,
        position(lower(msg), 'unauthorized') > 0, 1,
        position(lower(msg), 'forbidden') > 0, 1,
        http_status IN (401, 403, 429), 1,
        0
    ) as is_security_event
FROM logs_raw;

-- Advanced aggregation table for analytics and dashboards
CREATE TABLE IF NOT EXISTS logs_hourly_stats (
    hour DateTime,
    customer_id String,
    service LowCardinality(String),
    level LowCardinality(String),
    host LowCardinality(String),
    deployment_type LowCardinality(String),
    -- Volume metrics
    total_count UInt64,
    error_count UInt64,
    security_event_count UInt64,
    unique_users UInt64,
    unique_ips UInt64,
    -- Performance metrics
    avg_response_time Float64,
    p50_response_time Float64,
    p95_response_time Float64,
    p99_response_time Float64,
    total_bytes UInt64,
    -- Security metrics
    failed_auth_count UInt64,
    high_threat_count UInt64,
    top_error_codes Array(String),
    top_user_agents Array(String),
    top_countries Array(String)
)
ENGINE = SummingMergeTree()
PARTITION BY (toYYYYMM(hour), customer_id)
ORDER BY (customer_id, hour, service, level, host)
PRIMARY KEY (customer_id, hour, service)
TTL toDateTime(hour) + toIntervalDay(395) DELETE  -- Keep aggregated data longer
SETTINGS index_granularity = 8192;

-- Enhanced materialized view for comprehensive analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS logs_hourly_stats_mv
TO logs_hourly_stats
AS SELECT 
    toStartOfHour(ts) as hour,
    customer_id,
    service,
    level,
    host,
    deployment_type,
    -- Volume metrics
    count() as total_count,
    countIf(is_error = 1) as error_count,
    countIf(is_security_event = 1) as security_event_count,
    uniqHLL12(extracted_user_id) as unique_users,
    uniqHLL12(extracted_ip) as unique_ips,
    -- Performance metrics
    avg(http_response_time_ms) as avg_response_time,
    quantile(0.5)(http_response_time_ms) as p50_response_time,
    quantile(0.95)(http_response_time_ms) as p95_response_time,
    quantile(0.99)(http_response_time_ms) as p99_response_time,
    sum(http_bytes) as total_bytes,
    -- Security metrics
    countIf(http_status IN (401, 403)) as failed_auth_count,
    countIf(threat_level >= 4) as high_threat_count,
    topK(5)(error_code) as top_error_codes,
    topK(5)(user_agent_family) as top_user_agents,
    topK(5)(geo_country) as top_countries
FROM logs_normalized
GROUP BY customer_id, hour, service, level, host, deployment_type;

-- Security-focused daily aggregations for compliance reporting
CREATE TABLE IF NOT EXISTS security_daily_summary (
    date Date,
    customer_id String,
    deployment_type LowCardinality(String),
    -- Security metrics
    total_events UInt64,
    security_events UInt64,
    failed_logins UInt64,
    brute_force_attempts UInt64,
    unique_threat_ips UInt64,
    high_severity_events UInt64,
    -- Compliance metrics
    data_volume_gb Float64,
    retention_compliance UInt8,  -- Boolean for compliance status
    encryption_events UInt64,
    audit_events UInt64
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (customer_id, date, deployment_type)
TTL toDate(date) + 
    multiIf(
        deployment_type = 'fedramp', toIntervalYear(10),    -- Extended for government
        deployment_type = 'healthcare', toIntervalYear(10), -- Extended for HIPAA
        deployment_type = 'financial', toIntervalYear(10),  -- Extended for SOX
        toIntervalYear(5)  -- Default extended retention for security data
    ) DELETE
SETTINGS index_granularity = 8192;

-- Materialized view for daily security summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS security_daily_summary_mv
TO security_daily_summary
AS SELECT 
    toDate(ts) as date,
    customer_id,
    deployment_type,
    count() as total_events,
    countIf(is_security_event = 1) as security_events,
    countIf(position(lower(msg), 'login') > 0 AND is_error = 1) as failed_logins,
    countIf(position(lower(msg), 'brute') > 0 OR (http_status = 429 AND position(lower(msg), 'rate') > 0)) as brute_force_attempts,
    uniqHLL12(if(threat_level >= 3, extracted_ip, NULL)) as unique_threat_ips,
    countIf(threat_level >= 4) as high_severity_events,
    sum(http_bytes) / 1024 / 1024 / 1024 as data_volume_gb,
    1 as retention_compliance,  -- Placeholder for compliance check
    countIf(position(lower(msg), 'encrypt') > 0) as encryption_events,
    countIf(position(lower(msg), 'audit') > 0) as audit_events
FROM logs_normalized
GROUP BY customer_id, date, deployment_type;

-- Enhanced operational views for monitoring and alerting
CREATE VIEW IF NOT EXISTS recent_security_events AS
SELECT 
    ts,
    customer_id,
    service,
    level,
    host,
    msg,
    security_event_type,
    threat_level,
    extracted_user_id,
    extracted_ip,
    http_status,
    geo_country
FROM logs_normalized 
WHERE ts > now() - INTERVAL 1 HOUR 
  AND is_security_event = 1
ORDER BY threat_level DESC, ts DESC
LIMIT 1000;

CREATE VIEW IF NOT EXISTS service_health_dashboard AS
SELECT 
    customer_id,
    service,
    deployment_type,
    count() as total_requests,
    countIf(is_error = 1) as error_count,
    round(countIf(is_error = 1) * 100.0 / count(), 2) as error_rate_percent,
    countIf(is_security_event = 1) as security_events,
    round(avg(http_response_time_ms), 2) as avg_response_time_ms,
    round(quantile(0.95)(http_response_time_ms), 2) as p95_response_time_ms,
    uniqHLL12(extracted_user_id) as unique_users,
    uniqHLL12(extracted_ip) as unique_ips,
    max(ts) as last_seen,
    -- Health scoring (0-100)
    100 - least(100, countIf(is_error = 1) * 100.0 / count() * 10 + countIf(is_security_event = 1) * 100.0 / count() * 20) as health_score
FROM logs_normalized 
WHERE ts > now() - INTERVAL 1 HOUR
GROUP BY customer_id, service, deployment_type
ORDER BY health_score ASC;

-- Performance monitoring view for SLA tracking
CREATE VIEW IF NOT EXISTS sla_performance_tracking AS
SELECT 
    customer_id,
    service,
    deployment_type,
    toStartOfMinute(ts) as minute,
    count() as requests_per_minute,
    avg(http_response_time_ms) as avg_latency_ms,
    quantile(0.95)(http_response_time_ms) as p95_latency_ms,
    countIf(is_error = 1) * 100.0 / count() as error_rate_percent,
    countIf(http_response_time_ms > 1000) * 100.0 / count() as slow_request_percent
FROM logs_normalized 
WHERE ts > now() - INTERVAL 1 HOUR
GROUP BY customer_id, service, deployment_type, minute
ORDER BY minute DESC;

-- Threat intelligence and anomaly detection view
CREATE VIEW IF NOT EXISTS threat_intelligence_summary AS
SELECT 
    customer_id,
    extracted_ip as threat_ip,
    geo_country,
    count() as event_count,
    countIf(is_security_event = 1) as security_events,
    countIf(http_status IN (401, 403)) as auth_failures,
    uniqHLL12(extracted_user_id) as targeted_users,
    uniqHLL12(service) as targeted_services,
    max(threat_level) as max_threat_level,
    min(ts) as first_seen,
    max(ts) as last_seen,
    -- Risk scoring
    multiIf(
        countIf(is_security_event = 1) > 100, 'HIGH',
        countIf(is_security_event = 1) > 10, 'MEDIUM',
        'LOW'
    ) as risk_level
FROM logs_normalized 
WHERE ts > now() - INTERVAL 24 HOUR
  AND (is_security_event = 1 OR http_status IN (401, 403, 429))
GROUP BY customer_id, extracted_ip, geo_country
HAVING event_count > 5  -- Filter out noise
ORDER BY security_events DESC, event_count DESC;

-- Storage optimization: Create dictionaries for common values
CREATE DICTIONARY IF NOT EXISTS http_status_codes
(
    code UInt16,
    description String,
    category String
)
PRIMARY KEY code
SOURCE(CLICKHOUSE(HOST 'localhost' PORT 9000 TABLE 'http_status_reference'))
LIFETIME(MIN 3600 MAX 7200)
LAYOUT(FLAT());

-- Initialize the database with proper settings
OPTIMIZE TABLE logs_raw FINAL;
OPTIMIZE TABLE logs_normalized FINAL;