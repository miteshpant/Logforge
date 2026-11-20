-- Migration 021: lookup tables and managed lists (Phase 6)
--
-- lookup_tables_mt keeps every version of a tenant's lookup's metadata; the
-- current one is the latest version (ORDER BY ... version DESC LIMIT 1 BY
-- name), and a delete is a tombstone version (deleted = 1).
--
-- lookup_rows_mt holds the rows of each version. An upload writes the new
-- version's rows first and its metadata last, so a query (which reads the
-- version named by the metadata) never sees a half-written table. Rows of
-- older versions are deleted after the new metadata is written.

CREATE TABLE IF NOT EXISTS lookup_tables_mt
(
    tenant_id String,
    name String,
    version UInt32,
    kind LowCardinality(String),
    description String,
    columns Array(String),
    key_column String,
    row_count UInt32,
    deleted UInt8 DEFAULT 0,
    updated_at DateTime64(3),
    updated_by String
)
ENGINE = MergeTree
ORDER BY (tenant_id, name, version);

CREATE TABLE IF NOT EXISTS lookup_rows_mt
(
    tenant_id String,
    lookup String,
    version UInt32,
    key String,
    values Map(String, String)
)
ENGINE = MergeTree
ORDER BY (tenant_id, lookup, version, key);
