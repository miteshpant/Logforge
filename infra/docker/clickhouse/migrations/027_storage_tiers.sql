-- Storage tiers (Phase 12, docs/storage.md).
--
-- tenant_retention_mt: each tenant's retention per data type (logs, security,
-- traces, metrics): days searchable in ClickHouse and days each day's Parquet
-- archive is kept (0: no archive). A tenant without a row has the defaults in
-- apps/api/config/storage_tiers.yml. Latest row per (tenant, type) wins.
--
-- archive_manifest_mt: one row per archived tenant, data type and day: the
-- Parquet object, the rows it holds (read back from the file and counted
-- before the day is deleted from ClickHouse), and whether it has expired.
--
-- The warm tier (the `tiered` storage policy and each table's TTL) is applied
-- by the API at startup, only when the server has that policy
-- (infra/docker/clickhouse/config.d/s3_storage.xml), so this migration runs
-- on servers without object storage too.

CREATE TABLE IF NOT EXISTS tenant_retention_mt
(
    customer_id String,
    data_type LowCardinality(String),
    searchable_days UInt32,
    archive_days UInt32,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, data_type);

CREATE TABLE IF NOT EXISTS archive_manifest_mt
(
    customer_id String,
    data_type LowCardinality(String),
    day Date,
    object_key String,
    rows UInt64,
    bytes UInt64,
    status LowCardinality(String),   -- archived | expired
    archived_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, data_type, day);
