-- Migration 016: detection tuning (Phase 1)
--
-- Per-tenant exclusions and throttles applied by the detection engine and
-- backtests (apps/api/detection_tuning.py). Each change writes a new row
-- version; reads use FINAL to get the latest. Deletes are tombstones
-- (deleted = 1), so no mutations are needed.

CREATE TABLE IF NOT EXISTS detection_tuning_mt
(
    tenant_id String,
    id String,
    rule_id String,
    kind LowCardinality(String),
    spec String,
    reason String,
    created_by String,
    created_at DateTime64(3),
    updated_at DateTime64(3),
    deleted UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, id);
