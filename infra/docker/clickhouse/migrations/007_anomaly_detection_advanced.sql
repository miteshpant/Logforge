-- Migration 007: Advanced Anomaly Detection Tables
-- Created: 2025-12-21
-- Purpose: Support industry-leading anomaly detection with multi-metric correlation,
--          seasonal detection, feedback learning, and pattern recognition

-- ============================================================================
-- 1. Anomaly Detection Configurations
-- ============================================================================
-- Stores per-service, per-metric detection configurations
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
    notification_rules String, -- JSON: channels, escalation rules
    config_metadata String, -- JSON: additional config
    enabled Bool DEFAULT true,
    created_by String,
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, service, metric_type, config_id)
SETTINGS index_granularity = 8192;

-- Index for fast config lookups by service
CREATE INDEX IF NOT EXISTS idx_config_service ON anomaly_detection_configs_mt (service) TYPE bloom_filter GRANULARITY 4;


-- ============================================================================
-- 2. Anomaly Feedback for ML Learning
-- ============================================================================
-- Stores user feedback on anomaly detections for model improvement
CREATE TABLE IF NOT EXISTS anomaly_feedback_mt (
    feedback_id UUID,
    anomaly_id UUID,
    customer_id String,
    user_id String,
    user_email String,
    feedback_type Enum8(
        'true_positive' = 1,
        'false_positive' = 2,
        'severity_wrong' = 3,
        'duplicate' = 4
    ),
    correct_severity Nullable(String),
    notes String,
    tags Array(String),
    model_adjustment_applied Bool DEFAULT false,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (customer_id, anomaly_id, created_at)
SETTINGS index_granularity = 8192;

-- Index for feedback analysis queries
CREATE INDEX IF NOT EXISTS idx_feedback_type ON anomaly_feedback_mt (feedback_type) TYPE set(0) GRANULARITY 4;


-- ============================================================================
-- 3. Anomaly Patterns (Signature-based Detection)
-- ============================================================================
-- Stores known anomaly patterns for faster detection and context
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
    pattern_signature String, -- JSON: trigger events, expected metrics
    actions String, -- JSON: suppress_alerts, reduce_severity, add_context
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


-- ============================================================================
-- 4. Anomaly Analysis Results (Deep Dive RCA)
-- ============================================================================
-- Stores comprehensive analysis results for anomalies
CREATE TABLE IF NOT EXISTS anomaly_analysis_mt (
    analysis_id UUID,
    anomaly_id UUID,
    customer_id String,
    root_cause_type String,
    root_cause_confidence Float32,
    evidence Array(String),
    timeline String, -- JSON: sequence of events
    contributing_factors String, -- JSON: additional factors
    impact_assessment String, -- JSON: users, requests, revenue
    similar_incidents Array(UUID),
    recommended_actions String, -- JSON: prioritized actions
    correlated_logs String, -- JSON: related log entries
    correlated_metrics String, -- JSON: related metric changes
    correlated_events String, -- JSON: deployments, config changes
    analysis_duration_ms Int32,
    analyzed_by Enum8('system' = 1, 'user' = 2) DEFAULT 'system',
    analyzed_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (customer_id, anomaly_id, analyzed_at)
SETTINGS index_granularity = 8192;

-- Index for similar incident queries
CREATE INDEX IF NOT EXISTS idx_analysis_root_cause ON anomaly_analysis_mt (root_cause_type) TYPE bloom_filter GRANULARITY 4;


-- ============================================================================
-- 5. Anomaly Webhooks (Integration)
-- ============================================================================
-- Stores webhook configurations for anomaly notifications
CREATE TABLE IF NOT EXISTS anomaly_webhooks_mt (
    webhook_id UUID,
    customer_id String,
    webhook_url String,
    webhook_name String,
    events Array(String), -- anomaly_detected, anomaly_critical, anomaly_resolved
    filters String, -- JSON: min_severity, services, categories
    headers String, -- JSON: custom headers
    retry_policy String, -- JSON: max_retries, backoff_seconds
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


-- ============================================================================
-- 6. Multi-Metric Anomaly Detections
-- ============================================================================
-- Stores anomalies detected across multiple correlated metrics
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
    affected_metrics String, -- JSON: array of metric details
    detection_algorithms String, -- JSON: z_score, isolation_forest, prophet results
    ensemble_voting String, -- JSON: voting method, weights
    root_cause_hints Array(String),
    recommended_actions Array(String),
    status Enum8('active' = 1, 'investigating' = 2, 'resolved' = 3, 'dismissed' = 4) DEFAULT 'active',
    resolved_at Nullable(DateTime64(3)),
    dismissed_at Nullable(DateTime64(3)),
    dismissed_by Nullable(String),
    dismissal_reason Nullable(String),
    tags Array(String)
) ENGINE = MergeTree()
ORDER BY (customer_id, detected_at, severity, anomaly_id)
SETTINGS index_granularity = 8192;

-- Materialized view for active anomalies
CREATE MATERIALIZED VIEW IF NOT EXISTS active_multi_metric_anomalies_mv
ENGINE = AggregatingMergeTree()
ORDER BY (customer_id, service, severity)
POPULATE
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


-- ============================================================================
-- 7. Seasonal Baselines (Prophet/STL)
-- ============================================================================
-- Stores seasonal forecast models for time-aware anomaly detection
CREATE TABLE IF NOT EXISTS seasonal_baselines_mt (
    baseline_id UUID,
    customer_id String,
    service String,
    metric_type String,
    seasonality_config String, -- JSON: daily, weekly, monthly flags
    forecast_model String, -- JSON: prophet model parameters
    training_period_days Int32,
    accuracy_metrics String, -- JSON: mae, rmse, mape
    forecast_data String, -- JSON: predictions with confidence intervals
    changepoints Array(DateTime64(3)),
    last_trained_at DateTime64(3) DEFAULT now64(3),
    next_training_at DateTime64(3),
    model_version Int32 DEFAULT 1,
    enabled Bool DEFAULT true
) ENGINE = ReplacingMergeTree(last_trained_at)
ORDER BY (customer_id, service, metric_type, baseline_id)
SETTINGS index_granularity = 8192;


-- ============================================================================
-- 8. Anomaly Detection Performance Metrics
-- ============================================================================
-- Tracks detection system performance and accuracy
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
    detection_by_algorithm String, -- JSON: counts per algorithm
    detection_by_severity String, -- JSON: counts per severity
    mttr_minutes Float32,
    created_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree()
ORDER BY (customer_id, metric_date, metric_hour)
SETTINGS index_granularity = 8192;


-- ============================================================================
-- 9. Anomaly Export Jobs
-- ============================================================================
-- Tracks anomaly data export requests
CREATE TABLE IF NOT EXISTS anomaly_export_jobs_mt (
    job_id UUID,
    customer_id String,
    export_format Enum8('json' = 1, 'csv' = 2, 'parquet' = 3),
    time_range_start DateTime64(3),
    time_range_end DateTime64(3),
    filters String, -- JSON: severity, services, etc.
    delivery_method Enum8('download' = 1, 's3' = 2, 'email' = 3),
    delivery_config String, -- JSON: bucket, email, etc.
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


-- ============================================================================
-- Indexes for Performance Optimization
-- ============================================================================

-- Fast lookups for active anomalies by service
CREATE INDEX IF NOT EXISTS idx_multi_metric_service ON multi_metric_anomalies_mt (service, status) TYPE bloom_filter GRANULARITY 4;

-- Fast severity filtering
CREATE INDEX IF NOT EXISTS idx_multi_metric_severity ON multi_metric_anomalies_mt (severity) TYPE set(0) GRANULARITY 4;

-- Tag-based filtering
CREATE INDEX IF NOT EXISTS idx_multi_metric_tags ON multi_metric_anomalies_mt (tags) TYPE bloom_filter GRANULARITY 4;


-- ============================================================================
-- Grant Permissions (if needed)
-- ============================================================================
-- GRANT SELECT, INSERT, ALTER, DELETE ON anomaly_detection_configs_mt TO logforge_user;
-- GRANT SELECT, INSERT ON anomaly_feedback_mt TO logforge_user;
-- GRANT SELECT, INSERT, ALTER ON anomaly_patterns_mt TO logforge_user;
-- GRANT SELECT, INSERT ON anomaly_analysis_mt TO logforge_user;
-- GRANT SELECT, INSERT, ALTER ON anomaly_webhooks_mt TO logforge_user;
-- GRANT SELECT, INSERT, ALTER ON multi_metric_anomalies_mt TO logforge_user;
-- GRANT SELECT, INSERT, ALTER ON seasonal_baselines_mt TO logforge_user;
-- GRANT SELECT, INSERT ON anomaly_detection_metrics_mt TO logforge_user;
-- GRANT SELECT, INSERT, ALTER ON anomaly_export_jobs_mt TO logforge_user;


-- ============================================================================
-- Migration Complete
-- ============================================================================
-- This migration adds all necessary tables for industry-leading anomaly detection:
-- ✓ Multi-metric correlation detection
-- ✓ Seasonal/time-aware detection
-- ✓ Feedback-driven ML improvement
-- ✓ Pattern recognition
-- ✓ Deep analysis with RCA
-- ✓ Webhook integrations
-- ✓ Performance tracking
-- ✓ Data export capabilities