-- Migration 022: saved and scheduled searches (Phase 6)
--
-- saved_searches_mt keeps every version of a tenant's saved searches; the
-- current one is the latest version (ORDER BY ... version DESC LIMIT 1 BY
-- tenant_id, search_id), and a delete is a tombstone version (deleted = 1).
-- definition holds {"query", "every", "window", "alert", "report"} as JSON.
--
-- saved_search_runs_mt is the run history: one row per run, kept 90 days.

CREATE TABLE IF NOT EXISTS saved_searches_mt
(
    tenant_id String,
    search_id String,
    version UInt32,
    name String,
    description String,
    definition String,
    enabled UInt8,
    deleted UInt8 DEFAULT 0,
    updated_at DateTime64(3),
    updated_by String
)
ENGINE = MergeTree
ORDER BY (tenant_id, search_id, version);

CREATE TABLE IF NOT EXISTS saved_search_runs_mt
(
    tenant_id String,
    search_id String,
    run_at DateTime64(3, 'UTC'),
    window_start DateTime64(3, 'UTC'),
    window_end DateTime64(3, 'UTC'),
    trigger LowCardinality(String),
    status LowCardinality(String),
    rows UInt32,
    fired UInt8,
    alerted UInt8,
    throttled UInt8,
    value Nullable(Float64),
    duration_ms Float64,
    error String,
    alert_id String
)
ENGINE = MergeTree
ORDER BY (tenant_id, search_id, run_at)
TTL toDateTime(run_at) + INTERVAL 90 DAY;
