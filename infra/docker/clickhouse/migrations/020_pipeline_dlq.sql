-- Migration 020: the ingest pipeline dead-letter queue (Phase 4)
--
-- An event that a pipeline cannot process is stored here in the form it
-- arrived in, with the pipeline, processor and error, so nothing is lost
-- and it can be replayed once the pipeline is fixed. status moves from
-- pending to replayed or discarded (a new row version; read FINAL).
-- Entries are kept for 30 days.

CREATE TABLE IF NOT EXISTS pipeline_dlq_mt
(
    tenant_id String,
    id String,
    pipeline_id String,
    pipeline_version UInt32,
    processor LowCardinality(String),
    processor_index Int32,
    tag String,
    error String,
    event String,
    failed_at DateTime64(3),
    status LowCardinality(String) DEFAULT 'pending',
    resolved_at Nullable(DateTime64(3)),
    resolved_by String DEFAULT '',
    version UInt64
)
ENGINE = ReplacingMergeTree(version)
ORDER BY (tenant_id, id)
TTL toDateTime(failed_at) + INTERVAL 30 DAY;
