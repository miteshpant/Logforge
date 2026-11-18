-- Migration 017: cases (Phase 2)
--
-- cases_mt: one row version per change (ReplacingMergeTree on `version`);
-- read with FINAL. case_events_mt: the append-only case timeline, which is
-- also the audit trail of every case change.

CREATE TABLE IF NOT EXISTS cases_mt
(
    tenant_id String,
    id String,
    title String,
    severity LowCardinality(String),
    status LowCardinality(String),
    assignee Nullable(String),
    description String,
    tags Array(String),
    alert_ids Array(String),
    entities String,
    group_key String,
    created_by String,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    acknowledged_at Nullable(DateTime64(3)),
    contained_at Nullable(DateTime64(3)),
    resolved_at Nullable(DateTime64(3)),
    last_alert_at Nullable(DateTime64(3)),
    close_reason String,
    merged_into String,
    version UInt64
)
ENGINE = ReplacingMergeTree(version)
ORDER BY (tenant_id, id);

CREATE TABLE IF NOT EXISTS case_events_mt
(
    tenant_id String,
    case_id String,
    id String,
    ts DateTime64(3),
    seq UInt32,  -- order of events written together (they share ts)
    actor String,
    kind LowCardinality(String),
    data String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, case_id, ts, seq);
