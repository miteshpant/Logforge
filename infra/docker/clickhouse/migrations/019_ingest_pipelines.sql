-- Migration 019: ingest pipelines (Phase 4)
--
-- ingest_pipelines_mt keeps every saved version of each tenant's pipelines.
-- The current definition is the latest version (ORDER BY ... version DESC
-- LIMIT 1 BY pipeline_id); a delete is a tombstone version (deleted = 1).
-- definition holds {"processors": [...], "on_failure": [...]} as JSON,
-- routing holds {"services": [...], "if": "...", "priority": N, "default": bool}.

CREATE TABLE IF NOT EXISTS ingest_pipelines_mt
(
    tenant_id String,
    pipeline_id String,
    version UInt32,
    name String,
    description String,
    definition String,
    routing String,
    enabled UInt8,
    deleted UInt8 DEFAULT 0,
    updated_at DateTime64(3),
    updated_by String
)
ENGINE = MergeTree
ORDER BY (tenant_id, pipeline_id, version);
