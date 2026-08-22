-- Migration 013 (LF-019): create the anomaly tables migration 007 failed to create
--
-- WHY
-- schema_migrations records 007_anomaly_detection_advanced as executed, but
-- only anomaly_feedback_mt actually exists. The shell migration runner joined
-- every line of a statement onto one line WITHOUT stripping inline
-- "-- comment" text first, so every CREATE TABLE in 007 that contained an
-- inline comment was truncated at the first comment and rejected by
-- ClickHouse -- and the runner did not check ClickHouse's HTTP status, so the
-- migration was recorded as successful anyway. (Runner fixed alongside this
-- migration; see run_migrations.sh.)
--
-- The most visible casualty: GET /v1/ai/anomalies/history returned 500 with
-- "Table logforge.multi_metric_anomalies_mt does not exist".
--
-- This migration re-issues the missing DDL. Column definitions match the
-- readers/writers in apps/api (routers/ai_api.py history + dismiss handlers,
-- services/anomaly_analyzer.py) and migration 007's intent. Everything is
-- IF NOT EXISTS, so it is a no-op where 007 genuinely applied.
--
-- multi_metric_anomalies_mt additionally gets the partitioning/retention the
-- other event-history _mt tables use:
--   PARTITION BY (customer_id, toYYYYMM(detected_at))
--   ORDER BY (customer_id, detected_at, anomaly_id)
--   TTL 90 days (matches the 90-day analytic-history retention used elsewhere)

CREATE TABLE IF NOT EXISTS multi_metric_anomalies_mt (
    anomaly_id UUID,
    customer_id String,
    detected_at DateTime64(3) DEFAULT now64(3),
    service String,
    title String,
    description String,
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    confidence Float32,
    correlation_score Float32,
    affected_metrics String,
    detection_algorithms String,
    ensemble_voting String,
    root_cause_hints Array(String),
    recommended_actions Array(String),
    status Enum8('active' = 1, 'investigating' = 2, 'resolved' = 3, 'dismissed' = 4) DEFAULT 'active',
    resolved_at Nullable(DateTime64(3)),
    dismissed_at Nullable(DateTime64(3)),
    dismissed_by Nullable(String),
    dismissal_reason Nullable(String),
    tags Array(String)
) ENGINE = MergeTree()
PARTITION BY (customer_id, toYYYYMM(detected_at))
ORDER BY (customer_id, detected_at, anomaly_id)
TTL toDateTime(detected_at) + toIntervalDay(90)
SETTINGS index_granularity = 8192;

ALTER TABLE multi_metric_anomalies_mt
    ADD INDEX IF NOT EXISTS idx_multi_metric_service (service, status)
    TYPE bloom_filter GRANULARITY 4;

ALTER TABLE multi_metric_anomalies_mt
    ADD INDEX IF NOT EXISTS idx_multi_metric_severity severity
    TYPE set(0) GRANULARITY 4;

-- Per-service, per-metric detection configurations
CREATE TABLE IF NOT EXISTS anomaly_detection_configs_mt (
    config_id UUID,
    customer_id String,
    service String,
    metric_type String,
    algorithm Enum8(
        'z_score' = 1,
        'isolation_forest' = 2,
        'prophet' = 3,
        'ensemble' = 4,
        'seasonal' = 5
    ),
    sensitivity Enum8('low' = 1, 'medium' = 2, 'high' = 3),
    baseline_period_days Int32 DEFAULT 30,
    z_score_threshold Float32 DEFAULT 3.0,
    seasonal_adjustment Bool DEFAULT false,
    auto_tune Bool DEFAULT false,
    min_data_points Int32 DEFAULT 100,
    alert_cooldown_minutes Int32 DEFAULT 5,
    notification_rules String,
    config_metadata String,
    enabled Bool DEFAULT true,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, service, metric_type, config_id)
SETTINGS index_granularity = 8192;

-- Known anomaly patterns for signature-based detection
CREATE TABLE IF NOT EXISTS anomaly_patterns_mt (
    pattern_id UUID,
    customer_id String,
    pattern_name String,
    pattern_type Enum8(
        'deployment_spike' = 1,
        'traffic_surge' = 2,
        'scheduled_maintenance' = 3,
        'cascading_failure' = 4,
        'resource_exhaustion' = 5,
        'custom' = 6
    ),
    pattern_signature String,
    actions String,
    match_count Int32 DEFAULT 0,
    last_matched_at Nullable(DateTime64(3)),
    effectiveness_score Float32 DEFAULT 0.0,
    enabled Bool DEFAULT true,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, pattern_id)
SETTINGS index_granularity = 8192;

-- Root-cause analysis results per anomaly
CREATE TABLE IF NOT EXISTS anomaly_analysis_mt (
    analysis_id UUID,
    anomaly_id UUID,
    customer_id String,
    root_cause_type String,
    root_cause_confidence Float32,
    evidence Array(String),
    timeline String,
    contributing_factors String,
    impact_assessment String,
    similar_incidents Array(UUID),
    recommended_actions String,
    correlated_logs String,
    correlated_metrics String,
    correlated_events String,
    analysis_duration_ms Int32,
    analyzed_by Enum8('system' = 1, 'user' = 2) DEFAULT 'system',
    analyzed_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (customer_id, anomaly_id, analyzed_at)
SETTINGS index_granularity = 8192;

-- Webhook configurations for anomaly notifications
CREATE TABLE IF NOT EXISTS anomaly_webhooks_mt (
    webhook_id UUID,
    customer_id String,
    webhook_url String,
    webhook_name String,
    events Array(String),
    filters String,
    headers String,
    retry_policy String,
    last_triggered_at Nullable(DateTime64(3)),
    success_count Int32 DEFAULT 0,
    failure_count Int32 DEFAULT 0,
    enabled Bool DEFAULT true,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, webhook_id)
SETTINGS index_granularity = 8192;

-- Seasonal forecast models for time-aware detection
CREATE TABLE IF NOT EXISTS seasonal_baselines_mt (
    baseline_id UUID,
    customer_id String,
    service String,
    metric_type String,
    seasonality_config String,
    forecast_model String,
    training_period_days Int32,
    accuracy_metrics String,
    forecast_data String,
    changepoints Array(DateTime64(3)),
    last_trained_at DateTime64(3) DEFAULT now64(3),
    next_training_at DateTime64(3),
    model_version Int32 DEFAULT 1,
    enabled Bool DEFAULT true
) ENGINE = ReplacingMergeTree(last_trained_at)
ORDER BY (customer_id, service, metric_type, baseline_id)
SETTINGS index_granularity = 8192;

-- Detection system performance / accuracy tracking
CREATE TABLE IF NOT EXISTS anomaly_detection_metrics_mt (
    metric_id UUID,
    customer_id String,
    metric_date Date,
    metric_hour DateTime,
    total_detections Int32,
    true_positives Int32,
    false_positives Int32,
    false_negatives Int32,
    avg_detection_time_ms Float32,
    avg_confidence_score Float32,
    detection_by_algorithm String,
    detection_by_severity String,
    mttr_minutes Float32,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (customer_id, metric_date, metric_hour)
SETTINGS index_granularity = 8192;

-- Anomaly data export jobs
CREATE TABLE IF NOT EXISTS anomaly_export_jobs_mt (
    job_id UUID,
    customer_id String,
    export_format Enum8('json' = 1, 'csv' = 2, 'parquet' = 3),
    time_range_start DateTime64(3),
    time_range_end DateTime64(3),
    filters String,
    delivery_method Enum8('download' = 1, 's3' = 2, 'email' = 3),
    delivery_config String,
    status Enum8('pending' = 1, 'processing' = 2, 'completed' = 3, 'failed' = 4) DEFAULT 'pending',
    record_count Int32 DEFAULT 0,
    file_size_bytes Int64 DEFAULT 0,
    download_url Nullable(String),
    error_message Nullable(String),
    requested_by String,
    requested_at DateTime64(3) DEFAULT now64(3),
    completed_at Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (customer_id, requested_at, job_id)
SETTINGS index_granularity = 8192;

-- Aggregate view of active anomalies per service/severity
CREATE MATERIALIZED VIEW IF NOT EXISTS active_multi_metric_anomalies_mv
ENGINE = AggregatingMergeTree()
ORDER BY (customer_id, service, severity)
AS SELECT
    customer_id,
    service,
    severity,
    count() as anomaly_count,
    max(detected_at) as last_detected,
    uniq(anomaly_id) as unique_anomalies
FROM multi_metric_anomalies_mt
WHERE status = 'active'
GROUP BY customer_id, service, severity;
