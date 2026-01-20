-- Migration: Add original_metric_name column to metrics_mt table
-- Purpose: Preserve the original metric name sent by customers before normalization
-- Example: Customer sends "latency", stored as metric_name="response_time", original_metric_name="latency"

-- Add original_metric_name column to store the customer's original metric name
ALTER TABLE metrics_mt ADD COLUMN IF NOT EXISTS original_metric_name String DEFAULT '';

-- Add index for querying by original metric name (useful for debugging)
-- Note: ClickHouse doesn't support traditional indexes, but the column will be
-- part of the data files and can be filtered efficiently
