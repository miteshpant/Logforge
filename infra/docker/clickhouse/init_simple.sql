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

-- =====================================================
-- MULTI-TENANT LOG TABLES (Required for log ingestion)
-- =====================================================

-- Multi-tenant raw logs table for incoming log data with customer isolation
CREATE TABLE IF NOT EXISTS logs_raw_mt (
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
    severity_num UInt8 DEFAULT 0,
    facility UInt8 DEFAULT 16,
    parser_version String DEFAULT 'v1',
    customer_id String -- Multi-tenant isolation key
)
ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(ts))
ORDER BY (customer_id, service, level, ts, host)
PRIMARY KEY (customer_id, service, level, ts)
TTL toDateTime(ts) + toIntervalDay(30)
SETTINGS index_granularity = 8192;

-- Multi-tenant normalized logs table
CREATE TABLE IF NOT EXISTS logs_normalized_mt (
    ts DateTime64(3, 'UTC'),
    date Date,
    hour UInt8,
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
    ingested_at DateTime64(3, 'UTC'),
    customer_id String -- Multi-tenant isolation key
)
ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(ts))
ORDER BY (customer_id, service, level, ts, host)
PRIMARY KEY (customer_id, service, level, ts)
TTL toDateTime(ts) + toIntervalDay(30)
SETTINGS index_granularity = 8192;

-- Ingestion error tracking table
CREATE TABLE IF NOT EXISTS ingestion_errors_mt (
    id String DEFAULT generateUUIDv4(),
    customer_id String,
    endpoint String,
    error_type String,
    error_message String,
    error_details String DEFAULT '',
    request_data String DEFAULT '',
    occurred_at DateTime64(3) DEFAULT now64(3),
    resolved_at Nullable(DateTime64(3)),
    status Enum8('pending' = 1, 'investigating' = 2, 'resolved' = 3) DEFAULT 'pending'
)
ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(occurred_at))
ORDER BY (customer_id, occurred_at, endpoint)
PRIMARY KEY (customer_id, occurred_at)
TTL toDateTime(occurred_at) + toIntervalMonth(6)
SETTINGS index_granularity = 8192;

-- =====================================================
-- USER MANAGEMENT TABLES (Required for authentication)
-- =====================================================

-- Users table for authentication and user management
CREATE TABLE IF NOT EXISTS users_mt (
    id String,
    email String,
    name String,
    password_hash String,
    status Enum8('active'=1, 'inactive'=2, 'pending'=3, 'suspended'=4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    last_login_at Nullable(DateTime64(3)),
    password_reset_token Nullable(String),
    password_reset_expires Nullable(DateTime64(3)),
    email_verified_at Nullable(DateTime64(3)),
    setup_token Nullable(String),
    setup_token_expires Nullable(DateTime64(3)),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- User sessions table for JWT token management
CREATE TABLE IF NOT EXISTS user_sessions_mt (
    id String,
    user_id String,
    session_token String,
    ip_address String,
    user_agent String,
    created_at DateTime64(3) DEFAULT now64(3),
    last_activity DateTime64(3) DEFAULT now64(3),
    expires_at DateTime64(3),
    status Enum8('active'=1, 'expired'=2, 'revoked'=3),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, session_token)
SETTINGS index_granularity = 8192;

-- User tenant roles table for role-based access control
CREATE TABLE IF NOT EXISTS user_tenant_roles_mt (
    id String,
    user_id String,
    tenant_id String,
    role String,
    granted_by String,
    granted_at DateTime64(3) DEFAULT now64(3),
    expires_at Nullable(DateTime64(3)),
    status Enum8('active'=1, 'inactive'=2, 'expired'=3),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, tenant_id)
SETTINGS index_granularity = 8192;

-- =====================================================
-- MISSING REQUIRED TABLES (Referenced by services)
-- =====================================================

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

-- =====================================================
-- SERVICE TABLES FOR LOGFORGE PLATFORM ENGINES
-- This consolidates all service tables from logforge-service-tables.sql
-- =====================================================

-- =====================================================
-- 1. TENANT SYSTEM TABLES (tenant_service.py)
-- =====================================================

-- Core tenant metadata table
CREATE TABLE IF NOT EXISTS tenants_mt (
    id String,
    organization_name String,
    domain String,
    subscription_tier Enum8('enterprise' = 1, 'smb' = 2, 'startup' = 3, 'non_profit' = 4, 'government' = 5, 'education' = 6, 'healthcare' = 7, 'financial' = 8),
    status Enum8('active' = 1, 'inactive' = 2, 'suspended' = 3, 'pending' = 4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    billing_email String,
    admin_contact String,
    industry String DEFAULT '',
    region String DEFAULT 'us-east-1',
    compliance_requirements Array(String) DEFAULT [],
    feature_flags Map(String, String) DEFAULT map(),
    customer_id String -- Multi-tenant key
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Tenant configuration settings
CREATE TABLE IF NOT EXISTS tenant_configs_mt (
    id String,
    tenant_id String,
    config_key String,
    config_value String,
    config_type Enum8('string' = 1, 'number' = 2, 'boolean' = 3, 'json' = 4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    created_by String,
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, tenant_id, config_key)
SETTINGS index_granularity = 8192;

-- Tenant quotas and limits
CREATE TABLE IF NOT EXISTS tenant_quotas_mt (
    id String,
    tenant_id String,
    quota_type Enum8('daily_ingestion' = 1, 'monthly_ingestion' = 2, 'storage_gb' = 3, 'api_calls' = 4, 'users' = 5, 'alerts' = 6),
    quota_limit UInt64,
    current_usage UInt64 DEFAULT 0,
    reset_period Enum8('daily' = 1, 'monthly' = 2, 'never' = 3),
    last_reset DateTime64(3) DEFAULT now64(3),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, tenant_id, quota_type)
SETTINGS index_granularity = 8192;

-- Quota usage history table for storing usage snapshots when quotas are reset
CREATE TABLE IF NOT EXISTS quota_usage_history_mt (
    id String,
    tenant_id String,
    customer_id String,
    quota_type Enum8('daily_ingestion' = 1, 'monthly_ingestion' = 2, 'storage_gb' = 3, 'api_calls' = 4, 'users' = 5, 'alerts' = 6),
    usage_amount UInt64,
    quota_limit UInt64,
    reset_period_start DateTime64(3),
    reset_period_end DateTime64(3),
    billing_period String, -- YYYY-MM format
    reset_reason Enum8('scheduled_reset' = 1, 'manual_reset' = 2, 'policy_change' = 3, 'billing_cycle' = 4),
    metadata String DEFAULT '{}', -- JSON blob for additional context
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(reset_period_end))
ORDER BY (customer_id, tenant_id, quota_type, reset_period_end)
SETTINGS index_granularity = 8192;

-- Tenant storage backend configurations
CREATE TABLE IF NOT EXISTS tenant_storage_configs_mt (
    tenant_id String,
    storage_type Enum8('s3' = 1, 'gcs' = 2, 'azure' = 3, 'minio' = 4),
    config_data String, -- JSON blob
    is_active UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, tenant_id, storage_type)
SETTINGS index_granularity = 8192;

-- Legal hold requests
CREATE TABLE IF NOT EXISTS legal_holds_mt (
    id String,
    tenant_id String,
    requester String,
    reason String,
    start_date DateTime64(3),
    end_date Nullable(DateTime64(3)),
    status Enum8('active' = 1, 'expired' = 2, 'cancelled' = 3),
    retention_config String, -- JSON blob
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, tenant_id, id)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 2. M3 ALERT ENGINE TABLES (alert_engine.py)
-- =====================================================

-- Alert rules configuration
CREATE TABLE IF NOT EXISTS alert_rules_mt (
    id String,
    name String,
    description String,
    rule_type Enum8('threshold' = 1, 'anomaly' = 2, 'pattern' = 3, 'frequency' = 4, 'absence' = 5, 'sequence' = 6),
    query String,
    condition_config String, -- JSON blob
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    is_enabled UInt8 DEFAULT 1,
    notification_channels Array(String),
    cooldown_minutes UInt32 DEFAULT 5,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Active alert instances
CREATE TABLE IF NOT EXISTS alert_instances_mt (
    id String,
    rule_id String,
    status Enum8('triggered' = 1, 'acknowledged' = 2, 'resolved' = 3, 'suppressed' = 4),
    triggered_at DateTime64(3),
    resolved_at Nullable(DateTime64(3)),
    acknowledged_by Nullable(String),
    acknowledged_at Nullable(DateTime64(3)),
    trigger_data String, -- JSON blob with trigger details
    resolution_data Nullable(String), -- JSON blob with resolution details
    escalation_level UInt8 DEFAULT 0,
    next_escalation Nullable(DateTime64(3)),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(triggered_at)
ORDER BY (customer_id, rule_id, triggered_at)
SETTINGS index_granularity = 8192;

-- Notification channels configuration
CREATE TABLE IF NOT EXISTS notification_channels_mt (
    id String,
    name String,
    channel_type Enum8('email' = 1, 'slack' = 2, 'webhook' = 3, 'pagerduty' = 4, 'discord' = 5, 'teams' = 6),
    config String, -- JSON blob with channel-specific config
    is_enabled UInt8 DEFAULT 1,
    last_used Nullable(DateTime64(3)),
    success_count UInt64 DEFAULT 0,
    failure_count UInt64 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Alert rule evaluation states
CREATE TABLE IF NOT EXISTS alert_rule_states_mt (
    rule_id String,
    last_evaluation DateTime64(3),
    last_trigger Nullable(DateTime64(3)),
    evaluation_count UInt64 DEFAULT 0,
    trigger_count UInt64 DEFAULT 0,
    consecutive_failures UInt32 DEFAULT 0,
    state_data String, -- JSON blob for rule-specific state
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, rule_id)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 3. M4 SECURITY ANALYTICS TABLES (security_analytics.py)
-- =====================================================

-- Sigma detection rules
CREATE TABLE IF NOT EXISTS sigma_rules_mt (
    id String,
    name String,
    description String,
    rule_content String, -- YAML content
    mitre_techniques Array(String),
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    is_enabled UInt8 DEFAULT 1,
    false_positive_rate Float32 DEFAULT 0.0,
    last_matched Nullable(DateTime64(3)),
    match_count UInt64 DEFAULT 0,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Threat intelligence indicators
CREATE TABLE IF NOT EXISTS threat_intel_mt (
    id String,
    indicator_type Enum8('domain' = 1, 'ip' = 2, 'hash' = 3, 'url' = 4, 'email' = 5, 'filename' = 6),
    indicator_value String,
    threat_type Enum8('malware' = 1, 'c2' = 2, 'phishing' = 3, 'scanning' = 4, 'bot' = 5),
    confidence_score UInt8, -- 0-100
    source String,
    first_seen DateTime64(3),
    last_seen DateTime64(3),
    tags Array(String),
    context String, -- JSON blob with additional context
    is_active UInt8 DEFAULT 1,
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(first_seen)
ORDER BY (customer_id, indicator_type, indicator_value)
SETTINGS index_granularity = 8192;

-- Security events and detections
CREATE TABLE IF NOT EXISTS security_events_mt (
    id String,
    event_type Enum8('detection' = 1, 'alert' = 2, 'incident' = 3),
    rule_id Nullable(String), -- Links to sigma_rules_mt
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    status Enum8('new' = 1, 'investigating' = 2, 'resolved' = 3, 'false_positive' = 4),
    title String,
    description String,
    raw_log_data String, -- Original log data that triggered event
    enrichment_data String, -- JSON blob with additional context
    mitre_techniques Array(String),
    assigned_to Nullable(String),
    investigation_notes Array(String),
    artifacts Array(String), -- Associated IOCs, files, etc.
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, created_at, id)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 4. M6 AI ENGINE TABLES (ai_engine.py)
-- =====================================================

-- AI-powered investigations
CREATE TABLE IF NOT EXISTS ai_investigations_mt (
    id String,
    title String,
    description String,
    investigation_type Enum8('root_cause' = 1, 'anomaly' = 2, 'correlation' = 3, 'prediction' = 4),
    status Enum8('running' = 1, 'completed' = 2, 'failed' = 3, 'cancelled' = 4),
    input_data String, -- JSON blob with investigation parameters
    results String, -- JSON blob with investigation results
    confidence_score Float32,
    started_by String,
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    execution_time_ms UInt64 DEFAULT 0,
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (customer_id, started_at, id)
SETTINGS index_granularity = 8192;

-- Root cause analysis results
CREATE TABLE IF NOT EXISTS ai_analyses_mt (
    id String,
    investigation_id String,
    analysis_type Enum8('root_cause' = 1, 'impact_assessment' = 2, 'trend_analysis' = 3, 'correlation' = 4),
    findings String, -- JSON blob with analysis findings
    recommendations String, -- JSON blob with recommendations
    evidence Array(String), -- Log references, metrics, etc.
    confidence_score Float32,
    created_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, investigation_id, id)
SETTINGS index_granularity = 8192;

-- ML model baselines and learning data
CREATE TABLE IF NOT EXISTS ai_baselines_mt (
    model_id String,
    baseline_type Enum8('anomaly' = 1, 'pattern' = 2, 'threshold' = 3, 'seasonal' = 4),
    baseline_data String, -- JSON blob with model parameters
    training_period String, -- ISO 8601 duration
    last_trained DateTime64(3),
    accuracy_score Float32,
    false_positive_rate Float32,
    false_negative_rate Float32,
    sample_count UInt64,
    is_active UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, model_id)
SETTINGS index_granularity = 8192;

-- Query history for AI natural language processing
CREATE TABLE IF NOT EXISTS ai_query_history_mt (
    id String,
    user_id String,
    natural_query String,
    generated_sql String,
    execution_status Enum8('success' = 1, 'error' = 2, 'timeout' = 3),
    result_count UInt64,
    execution_time_ms UInt64,
    feedback_score Nullable(Int8), -- -1 to 1
    feedback_notes Nullable(String),
    created_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, created_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 5. M7 ENTERPRISE ENGINE TABLES (enterprise_engine.py)
-- =====================================================

-- Enterprise authentication providers
CREATE TABLE IF NOT EXISTS auth_providers_mt (
    id String,
    provider_type Enum8('oidc' = 1, 'saml' = 2, 'ldap' = 3, 'oauth2' = 4),
    name String,
    config String, -- JSON blob with provider configuration
    is_enabled UInt8 DEFAULT 1,
    is_default UInt8 DEFAULT 0,
    user_mapping String, -- JSON blob for user attribute mapping
    group_mapping String, -- JSON blob for group/role mapping
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Enterprise API keys management
CREATE TABLE IF NOT EXISTS api_keys_enterprise_mt (
    id String,
    name String,
    key_hash String, -- Hashed API key
    tenant_id String,
    created_by String,
    permissions Array(String),
    rate_limit UInt32 DEFAULT 1000,
    expires_at Nullable(DateTime64(3)),
    last_used Nullable(DateTime64(3)),
    usage_count UInt64 DEFAULT 0,
    is_active UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, tenant_id, id)
SETTINGS index_granularity = 8192;

-- MFA setup configurations
CREATE TABLE IF NOT EXISTS mfa_setups_mt (
    user_id String,
    mfa_type Enum8('totp' = 1, 'sms' = 2, 'email' = 3, 'hardware' = 4),
    config String, -- JSON blob with MFA configuration
    backup_codes Array(String),
    is_verified UInt8 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    verified_at Nullable(DateTime64(3)),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, mfa_type)
SETTINGS index_granularity = 8192;

-- Compliance reports
CREATE TABLE IF NOT EXISTS compliance_reports_mt (
    id String,
    report_type Enum8('sox' = 1, 'gdpr' = 2, 'pci_dss' = 3, 'hipaa' = 4, 'iso27001' = 5),
    period_start DateTime64(3),
    period_end DateTime64(3),
    status Enum8('generating' = 1, 'completed' = 2, 'failed' = 3),
    report_data String, -- JSON blob with report content
    generated_by String,
    generated_at DateTime64(3) DEFAULT now64(3),
    file_path Nullable(String), -- S3/storage path to report file
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(generated_at)
ORDER BY (customer_id, report_type, period_start)
SETTINGS index_granularity = 8192;

-- Enterprise integrations
CREATE TABLE IF NOT EXISTS integrations_mt (
    id String,
    integration_type Enum8('slack' = 1, 'servicenow' = 2, 'jira' = 3, 'splunk' = 4, 'elasticsearch' = 5),
    name String,
    config String, -- JSON blob with integration configuration
    health_status Enum8('healthy' = 1, 'degraded' = 2, 'unhealthy' = 3),
    last_sync Nullable(DateTime64(3)),
    sync_count UInt64 DEFAULT 0,
    error_count UInt64 DEFAULT 0,
    is_enabled UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Backup policies
CREATE TABLE IF NOT EXISTS backup_policies_mt (
    id String,
    policy_name String,
    backup_type Enum8('full' = 1, 'incremental' = 2, 'differential' = 3),
    schedule_cron String,
    retention_days UInt32,
    storage_config String, -- JSON blob with backup storage configuration
    is_enabled UInt8 DEFAULT 1,
    last_backup Nullable(DateTime64(3)),
    next_backup DateTime64(3),
    backup_count UInt64 DEFAULT 0,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 6. M5 OBSERVABILITY ENGINE TABLES (observability_engine.py)
-- =====================================================

-- Service topology and dependencies
CREATE TABLE IF NOT EXISTS service_topology_mt (
    service_name String,
    service_type Enum8('api' = 1, 'database' = 2, 'cache' = 3, 'queue' = 4, 'external' = 5),
    dependencies Array(String), -- Array of dependent service names
    health_status Enum8('healthy' = 1, 'degraded' = 2, 'unhealthy' = 3, 'unknown' = 4),
    metadata String, -- JSON blob with service metadata
    last_seen DateTime64(3),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, service_name)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 7. USER INVITATIONS TABLE (authn_authz_middleware.py)
-- =====================================================

-- User invitation system
CREATE TABLE IF NOT EXISTS user_invitations_mt (
    id String,
    email String,
    tenant_id String,
    invited_by String,
    role Enum8('super_admin' = 1, 'admin' = 2, 'support_admin' = 3, 'billing_admin' = 4,
               'tenant_admin' = 5, 'security_analyst' = 6, 'devops_engineer' = 7,
               'compliance_officer' = 8, 'viewer' = 9),
    invitation_token String,
    status Enum8('pending' = 1, 'accepted' = 2, 'expired' = 3, 'revoked' = 4),
    expires_at DateTime64(3),
    accepted_at Nullable(DateTime64(3)),
    created_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, email, created_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 8. QUERY MANAGEMENT TABLES (query_service.py)
-- =====================================================

-- Saved queries table
CREATE TABLE IF NOT EXISTS saved_queries_mt (
    id String,
    customer_id String,
    name String,
    description String,
    query_definition String,
    query_type String DEFAULT 'advanced',
    created_by String DEFAULT 'system',
    tags String DEFAULT '[]',
    is_public UInt8 DEFAULT 0,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, created_at)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- Query cache table
CREATE TABLE IF NOT EXISTS query_cache_mt (
    id String,
    customer_id String,
    cache_key String,
    query_definition String,
    result_data String,
    created_at DateTime64(3, 'UTC'),
    expires_at Float64
) ENGINE = MergeTree()
ORDER BY (customer_id, cache_key)
PARTITION BY toYYYYMM(created_at)
TTL toDateTime(expires_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 9. DASHBOARD MANAGEMENT TABLES (dashboard_service.py)
-- =====================================================

-- Dashboards table
CREATE TABLE IF NOT EXISTS dashboards_mt (
    id String,
    customer_id String,
    name String,
    description String,
    layout String,
    filters String DEFAULT '[]',
    tags String DEFAULT '[]',
    is_public UInt8 DEFAULT 0,
    is_default UInt8 DEFAULT 0,
    created_by String DEFAULT 'system',
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, created_at)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- Dashboard widgets table
CREATE TABLE IF NOT EXISTS dashboard_widgets_mt (
    id String,
    dashboard_id String,
    customer_id String,
    name String,
    type String,
    query_definition String,
    visualization_config String,
    position String DEFAULT '{}',
    size String DEFAULT '{}',
    refresh_interval UInt32 DEFAULT 300,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, dashboard_id, created_at)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 10. STORAGE MANAGEMENT TABLES (storage_service.py)
-- =====================================================

-- Retention policies for customers
CREATE TABLE IF NOT EXISTS retention_policies_mt (
    id String,
    customer_id String,
    policy_name String,
    hot_retention_days UInt32,
    cold_retention_days UInt32,
    archive_retention_days UInt32,
    compression_enabled UInt8 DEFAULT 1,
    auto_deletion_enabled UInt8 DEFAULT 0,
    storage_backend String DEFAULT 's3',
    created_by String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, policy_name)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- Storage backend configurations
CREATE TABLE IF NOT EXISTS storage_backends_mt (
    id String,
    customer_id String,
    backend_name String,
    backend_type Enum8('s3' = 1, 'gcs' = 2, 'azure' = 3, 'minio' = 4, 'local' = 5),
    connection_config String, -- JSON blob with connection details
    is_default UInt8 DEFAULT 0,
    is_enabled UInt8 DEFAULT 1,
    health_status Enum8('healthy' = 1, 'degraded' = 2, 'unhealthy' = 3, 'unknown' = 4),
    last_health_check Nullable(DateTime64(3, 'UTC')),
    total_storage_gb Float64 DEFAULT 0,
    used_storage_gb Float64 DEFAULT 0,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, backend_type, backend_name)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- Storage operations and cleanup jobs
CREATE TABLE IF NOT EXISTS storage_operations_mt (
    id String,
    customer_id String,
    operation_type Enum8('cleanup' = 1, 'archive' = 2, 'restore' = 3, 'migration' = 4, 'compression' = 5),
    operation_status Enum8('pending' = 1, 'running' = 2, 'completed' = 3, 'failed' = 4, 'cancelled' = 5),
    policy_id Nullable(String),
    backend_id Nullable(String),
    started_at DateTime64(3, 'UTC'),
    completed_at Nullable(DateTime64(3, 'UTC')),
    duration_seconds Nullable(UInt64),
    records_processed UInt64 DEFAULT 0,
    data_size_gb Float64 DEFAULT 0,
    error_message Nullable(String),
    operation_metadata String DEFAULT '{}', -- JSON blob
    triggered_by String,
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, started_at, operation_type)
PARTITION BY toYYYYMM(started_at)
SETTINGS index_granularity = 8192;

-- Storage quotas and usage tracking
CREATE TABLE IF NOT EXISTS storage_quotas_mt (
    id String,
    customer_id String,
    quota_type Enum8('hot_storage' = 1, 'cold_storage' = 2, 'archive_storage' = 3, 'total_storage' = 4),
    quota_limit_gb Float64,
    current_usage_gb Float64 DEFAULT 0,
    usage_percentage Float32 DEFAULT 0,
    warning_threshold Float32 DEFAULT 0.8,
    critical_threshold Float32 DEFAULT 0.9,
    last_calculated DateTime64(3, 'UTC'),
    alerts_enabled UInt8 DEFAULT 1,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, quota_type)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- Data archival tracking
CREATE TABLE IF NOT EXISTS data_archives_mt (
    id String,
    customer_id String,
    archive_name String,
    archive_type Enum8('logs' = 1, 'metrics' = 2, 'traces' = 3, 'events' = 4),
    source_table String,
    archive_backend_id String,
    archive_path String,
    start_date DateTime64(3, 'UTC'),
    end_date DateTime64(3, 'UTC'),
    record_count UInt64,
    compressed_size_gb Float64,
    uncompressed_size_gb Float64,
    compression_ratio Float32,
    checksum String,
    encryption_enabled UInt8 DEFAULT 0,
    created_at DateTime64(3, 'UTC'),
    expires_at Nullable(DateTime64(3, 'UTC')),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, archive_type, start_date)
PARTITION BY toYYYYMM(start_date)
SETTINGS index_granularity = 8192;

-- Dashboard shares table
CREATE TABLE IF NOT EXISTS dashboard_shares_mt (
    id String,
    dashboard_id String,
    customer_id String,
    shared_with_email Nullable(String),
    shared_with_tenant Nullable(String),
    permission_level String DEFAULT 'view',
    expires_at Nullable(DateTime64(3, 'UTC')),
    created_by String DEFAULT 'system',
    created_at DateTime64(3, 'UTC'),
    status String DEFAULT 'active'
) ENGINE = MergeTree()
ORDER BY (customer_id, dashboard_id, created_at)
PARTITION BY toYYYYMM(created_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 11. USAGE TRACKING & BILLING TABLES (usage_api.py)
-- =====================================================

-- API usage audit trail for billing and analytics
CREATE TABLE IF NOT EXISTS api_usage_audit_mt (
    id String,
    customer_id String,
    tenant_id String,
    user_id Nullable(String),
    endpoint String,
    method Enum8('GET' = 1, 'POST' = 2, 'PUT' = 3, 'DELETE' = 4, 'PATCH' = 5),
    request_timestamp DateTime64(3) DEFAULT now64(3),
    response_status UInt16,
    response_time_ms UInt32,
    feature_type String, -- ingestion, query, analytics, alerts, security, storage, api
    request_size_bytes UInt64 DEFAULT 0,
    response_size_bytes UInt64 DEFAULT 0,
    ip_address Nullable(String),
    user_agent Nullable(String),
    api_version String DEFAULT 'v1'
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(request_timestamp))
ORDER BY (customer_id, tenant_id, request_timestamp, endpoint)
TTL toDateTime(request_timestamp) + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- =====================================================
-- 12. SECURITY ANALYTICS TABLES (security_analytics.py) - EXTENDED
-- =====================================================

-- Sigma detection rules table (secondary definition for compatibility)
CREATE TABLE IF NOT EXISTS sigma_rules_mt (
    id String,
    customer_id String,
    title String,
    description String,
    severity Enum8('critical' = 1, 'high' = 2, 'medium' = 3, 'low' = 4, 'info' = 5),
    status String DEFAULT 'active',
    author String DEFAULT 'logforge',
    date String,
    tags String,  -- JSON array
    attack_techniques String,  -- JSON array of MITRE ATT&CK techniques
    kill_chain_phases String,  -- JSON array
    logsource String,  -- JSON object
    detection String,  -- JSON object with Sigma detection logic
    references String,  -- JSON array
    falsepositives String,  -- JSON array
    enabled UInt8 DEFAULT 1,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, severity, created_at)
TTL toDateTime(created_at) + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- =====================================================
-- 13. OBSERVABILITY & APM TABLES (observability_engine.py) - EXTENDED
-- =====================================================

-- OpenTelemetry traces table
CREATE TABLE IF NOT EXISTS traces_mt (
    id String,
    trace_id String,
    span_id String,
    parent_span_id Nullable(String),
    operation_name String,
    service_name String,
    start_time DateTime64(3) DEFAULT now64(3),
    end_time Nullable(DateTime64(3)),
    duration_ms UInt32,
    kind Enum8('unspecified' = 1, 'internal' = 2, 'server' = 3, 'client' = 4, 'producer' = 5, 'consumer' = 6),
    status Enum8('unset' = 1, 'ok' = 2, 'error' = 3),
    status_message Nullable(String),
    attributes String,  -- JSON object with span attributes
    events String,  -- JSON array of span events
    links String,  -- JSON array of span links
    resource String,  -- JSON object with resource attributes
    customer_id String,
    ingested_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(start_time))
ORDER BY (customer_id, service_name, start_time, trace_id, span_id)
TTL toDateTime(start_time) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- Metrics data table
CREATE TABLE IF NOT EXISTS metrics_mt (
    id String,
    metric_name String,
    metric_type Enum8('counter' = 1, 'gauge' = 2, 'histogram' = 3, 'summary' = 4),
    value Float64,
    timestamp DateTime64(3) DEFAULT now64(3),
    labels String,  -- JSON object with metric labels
    service_name String,
    resource String,  -- JSON object with resource attributes
    customer_id String,
    ingested_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(timestamp))
ORDER BY (customer_id, service_name, metric_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Service dependencies/calls mapping
CREATE TABLE IF NOT EXISTS service_dependencies_mt (
    id String,
    from_service String,
    to_service String,
    call_count UInt64,
    avg_latency_ms Float64,
    error_rate Float64,
    last_seen DateTime64(3) DEFAULT now64(3),
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY customer_id
ORDER BY (customer_id, from_service, to_service)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 14. SUBSCRIPTION & BILLING TABLES (subscription_service.py)
-- =====================================================

-- Tenant subscriptions table
CREATE TABLE IF NOT EXISTS tenant_subscriptions_mt (
    id String,
    tenant_id String,
    subscribed_features Array(String),
    subscription_tier Enum8('enterprise' = 1, 'smb' = 2, 'startup' = 3, 'non_profit' = 4, 'government' = 5, 'education' = 6, 'healthcare' = 7, 'financial' = 8),
    billing_cycle Enum8('monthly' = 1, 'quarterly' = 2, 'yearly' = 3),
    status Enum8('active' = 1, 'inactive' = 2, 'cancelled' = 3, 'suspended' = 4),
    started_at DateTime64(3) DEFAULT now64(3),
    expires_at Nullable(DateTime64(3)),
    auto_renew UInt8 DEFAULT 1,
    monthly_spend_limit Nullable(Float64),
    overage_allowed UInt8 DEFAULT 0,
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(started_at))
ORDER BY (customer_id, tenant_id, started_at)
SETTINGS index_granularity = 8192;

-- Feature rates table
CREATE TABLE IF NOT EXISTS feature_rates_mt (
    id String,
    feature_name String,
    pricing_model Enum8('per_unit' = 1, 'fixed_monthly' = 2, 'tiered' = 3),
    base_rate Float64,
    tier_rates String, -- JSON object with tier-specific rates
    currency String DEFAULT 'USD',
    effective_date DateTime64(3) DEFAULT now64(3),
    created_by String,
    description String DEFAULT '',
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(effective_date))
ORDER BY (customer_id, feature_name, effective_date)
SETTINGS index_granularity = 8192;

-- Usage records table
CREATE TABLE IF NOT EXISTS usage_records_mt (
    id String,
    tenant_id String,
    feature_name String,
    usage_type String,
    quantity UInt64,
    timestamp DateTime64(3) DEFAULT now64(3),
    billing_period String, -- YYYY-MM format
    cost_calculated Float64 DEFAULT 0.0,
    rate_applied Float64 DEFAULT 0.0,
    metadata String, -- JSON object with additional metadata
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(timestamp))
ORDER BY (customer_id, tenant_id, feature_name, timestamp)
SETTINGS index_granularity = 8192;

-- Tenant deletion records table
CREATE TABLE IF NOT EXISTS tenant_deletions_mt (
    id String,
    tenant_id String,
    deletion_type Enum8('soft_delete' = 1, 'hard_delete' = 2),
    deleted_at DateTime64(3) DEFAULT now64(3),
    deleted_by String,
    reason String,
    data_cleanup_completed UInt8 DEFAULT 0,
    usage_records_retained UInt8 DEFAULT 1,
    final_bill_generated UInt8 DEFAULT 0,
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(deleted_at))
ORDER BY (customer_id, tenant_id, deleted_at)
SETTINGS index_granularity = 8192;

-- =====================================================
-- 15. ENTERPRISE COMPLIANCE TABLES (enterprise_api.py)
-- =====================================================

-- Enterprise compliance and legal hold table
CREATE TABLE IF NOT EXISTS enterprise_compliance_mt (
    id String,
    type Enum8('legal_hold' = 1, 'audit_request' = 2, 'compliance_report' = 3, 'data_export' = 4),
    case_id String,
    custodian String,
    reason String,
    date_range String, -- JSON blob with start/end dates
    scope String, -- JSON blob with data types and departments
    status Enum8('active' = 1, 'completed' = 2, 'cancelled' = 3, 'expired' = 4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(created_at))
ORDER BY (customer_id, type, created_at)
SETTINGS index_granularity = 8192;

-- Enterprise integrations table
CREATE TABLE IF NOT EXISTS enterprise_integrations_mt (
    id String,
    integration_type Enum8('slack' = 1, 'servicenow' = 2, 'jira' = 3, 'pagerduty' = 4, 'webhook' = 5),
    name String,
    config String, -- JSON blob with integration configuration
    is_enabled UInt8 DEFAULT 1,
    health_status Enum8('healthy' = 1, 'degraded' = 2, 'unhealthy' = 3, 'unknown' = 4),
    last_health_check Nullable(DateTime64(3)),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(created_at))
ORDER BY (customer_id, integration_type, id)
SETTINGS index_granularity = 8192;

-- Enterprise audit logs table
CREATE TABLE IF NOT EXISTS enterprise_audit_logs_mt (
    id String,
    user_id String,
    tenant_id Nullable(String),
    action_type Enum8('create' = 1, 'update' = 2, 'delete' = 3, 'view' = 4, 'login' = 5, 'logout' = 6),
    resource_type String,
    resource_id Nullable(String),
    details String, -- JSON blob with action details
    ip_address String DEFAULT 'unknown',
    user_agent String DEFAULT '',
    timestamp DateTime64(3) DEFAULT now64(3),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(timestamp))
ORDER BY (customer_id, timestamp, user_id)
SETTINGS index_granularity = 8192;

-- API usage table for billing tracking
CREATE TABLE IF NOT EXISTS api_usage_mt (
    id String,
    customer_id String,
    tenant_id String,
    user_id Nullable(String),
    endpoint String,
    method Enum8('GET' = 1, 'POST' = 2, 'PUT' = 3, 'DELETE' = 4, 'PATCH' = 5),
    request_timestamp DateTime64(3) DEFAULT now64(3),
    response_status UInt16,
    processing_time_ms UInt32,
    billing_feature String, -- ingestion, query, analytics, alerts, security, storage
    cost_credits Float64 DEFAULT 0.0,
    request_size_bytes UInt64 DEFAULT 0,
    response_size_bytes UInt64 DEFAULT 0,
    ip_address Nullable(String),
    user_agent Nullable(String)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(request_timestamp))
ORDER BY (customer_id, tenant_id, request_timestamp, endpoint)
TTL toDateTime(request_timestamp) + INTERVAL 2 YEAR
SETTINGS index_granularity = 8192;

-- Tenant bills table for usage-based billing
CREATE TABLE IF NOT EXISTS tenant_bills_mt (
    id String,
    tenant_id String,
    billing_period String, -- YYYY-MM format
    subscription_tier String,
    base_fee Float64,
    usage_charges Float64,
    tier_discount Float64 DEFAULT 0.0,
    promo_discount Float64 DEFAULT 0.0,
    subtotal Float64,
    total_amount Float64,
    currency String DEFAULT 'USD',
    status Enum8('generated' = 1, 'sent' = 2, 'paid' = 3, 'overdue' = 4, 'cancelled' = 5),
    usage_breakdown String, -- JSON blob with detailed usage breakdown
    promo_code Nullable(String),
    generated_at DateTime64(3) DEFAULT now64(3),
    due_date DateTime64(3),
    paid_at Nullable(DateTime64(3)),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(generated_at))
ORDER BY (customer_id, tenant_id, billing_period, generated_at)
SETTINGS index_granularity = 8192;

-- Billing overrides table for admin adjustments
CREATE TABLE IF NOT EXISTS billing_overrides_mt (
    id String,
    tenant_id String,
    billing_period Nullable(String), -- YYYY-MM format
    original_amount Float64 DEFAULT 0.0,
    override_amount Float64,
    reason String,
    approved_by String,
    customer_id String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    status Enum8('applied' = 1, 'pending' = 2, 'cancelled' = 3) DEFAULT 'applied'
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(created_at))
ORDER BY (customer_id, tenant_id, created_at)
SETTINGS index_granularity = 8192;

-- Insert default storage cost rate for all subscription tiers
INSERT INTO feature_rates_mt (id, feature_name, pricing_model, base_rate, tier_rates, currency, effective_date, created_by, description, customer_id)
VALUES
    ('rate-storage-cost-per-gb', 'storage.cost_per_gb', 'per_unit', 0.023, '{"enterprise": 0.023, "smb": 0.025, "startup": 0.027, "non_profit": 0.020, "government": 0.021, "education": 0.019, "healthcare": 0.022, "financial": 0.024}', 'USD', now(), 'system', 'Storage cost per GB', 'platform');

-- Archive tracking table to prevent duplicate archival and track customer data access
CREATE TABLE IF NOT EXISTS archive_metadata_mt (
    id UUID DEFAULT generateUUIDv4(),
    customer_id String,
    archive_key String,
    original_start_date DateTime64(3, 'UTC'),
    original_end_date DateTime64(3, 'UTC'),
    records_archived UInt64,
    data_size_bytes UInt64,
    compression_type LowCardinality(String) DEFAULT 'gzip',
    encryption_enabled UInt8 DEFAULT 0,
    archive_date DateTime64(3, 'UTC'),
    storage_backend LowCardinality(String) DEFAULT 'minio',
    bucket_name String DEFAULT 'logforge',
    checksum String,
    retention_policy_id String,
    created_at DateTime64(3, 'UTC') DEFAULT now64(),
    status LowCardinality(String) DEFAULT 'completed',
    access_count UInt64 DEFAULT 0,
    last_accessed_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(archive_date))
ORDER BY (customer_id, archive_date, archive_key)
PRIMARY KEY (customer_id, archive_date)
SETTINGS index_granularity = 8192;

-- Archive access log for tracking customer data retrievals
CREATE TABLE IF NOT EXISTS archive_access_log_mt (
    id UUID DEFAULT generateUUIDv4(),
    customer_id String,
    archive_key String,
    access_type LowCardinality(String), -- 'read', 'download', 'query'
    user_id String,
    session_id String,
    accessed_at DateTime64(3, 'UTC') DEFAULT now64(),
    bytes_transferred UInt64 DEFAULT 0,
    query_filter String DEFAULT '',
    client_ip String
)
ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(accessed_at))
ORDER BY (customer_id, accessed_at, archive_key)
PRIMARY KEY (customer_id, accessed_at)
TTL toDateTime(accessed_at) + toIntervalDay(365)
SETTINGS index_granularity = 8192;
