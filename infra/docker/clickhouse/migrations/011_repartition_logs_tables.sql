-- ENH-020: rework log table partitioning to avoid part explosion.
--
-- ============================================================================
-- THIS MIGRATION IS DESTRUCTIVE AND IS **NOT** APPLIED AUTOMATICALLY.
--
-- The migration runner (apps/api/schema_migrations.py) refuses any file
-- containing DROP/TRUNCATE/DELETE unless ALLOW_DESTRUCTIVE_MIGRATIONS=true.
-- That refusal is deliberate: this rewrites the primary log tables and must be
-- an explicit, supervised operation with a verified backup -- never part of a
-- routine deploy.
--
-- Run it with:
--   ALLOW_DESTRUCTIVE_MIGRATIONS=true RUN_MIGRATIONS_ON_STARTUP=true
-- ============================================================================
--
-- THE PROBLEM
-- `init_simple.sql:200` declares:
--     PARTITION BY (customer_id, toYYYYMM(ts))
--
-- Partition count is therefore O(tenants x months):
--     100 tenants  x 12 months =   1,200 partitions
--   1,000 tenants  x 12 months =  12,000 partitions
--   5,000 tenants  x 12 months =  60,000 partitions
--
-- ClickHouse guidance is to keep active parts in the low thousands PER TABLE.
-- Beyond that, merges, inserts and server startup all degrade. This directly
-- caps how many tenants the platform can serve, which is a hard ceiling on the
-- business, not just a performance nit.
--
-- THE FIX
-- Partition by month only, and keep `customer_id` FIRST in the ORDER BY (it
-- already is, at init_simple.sql:201). Tenant-scoped queries still prune
-- efficiently via the primary index -- partitioning is not the mechanism that
-- makes them fast, the sort order is. Partition count becomes O(months).
--
-- `PARTITION BY` cannot be changed with ALTER, so this is a create-copy-swap.
--
-- ROLLBACK
-- The original table is RENAMED, never dropped, so recovery is:
--     RENAME TABLE logs_raw_mt TO logs_raw_mt_failed,
--                  logs_raw_mt_old TO logs_raw_mt;
-- Drop the _old tables only after verifying row counts and query behaviour.

-- ---------------------------------------------------------------------------
-- logs_raw_mt
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS logs_raw_mt_new (
    ts DateTime64(3, 'UTC'),
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    span_id String DEFAULT '',
    attrs String,
    status UInt16 DEFAULT 0,
    src_ip String DEFAULT '',
    user_id String DEFAULT '',
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(),
    severity_num UInt8 DEFAULT 0,
    facility UInt8 DEFAULT 16,
    parser_version String DEFAULT 'v1',
    customer_id String,
    -- ENH-020: token index so full-text search on the multi-tenant table is
    -- indexed. The non-MT `logs_raw` had one (init.sql:108); `logs_raw_mt`
    -- never did, so every message search was a full scan.
    INDEX idx_msg_tokens msg TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4,
    INDEX idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)                       -- was (customer_id, toYYYYMM(ts))
ORDER BY (customer_id, service, level, ts, host) -- unchanged: tenant still first
PRIMARY KEY (customer_id, service, level, ts)
TTL toDateTime(ts) + toIntervalDay(30)
SETTINGS index_granularity = 8192;

INSERT INTO logs_raw_mt_new SELECT
    ts, host, service, level, msg, trace_id, span_id, attrs, status,
    src_ip, user_id, ingested_at, severity_num, facility, parser_version,
    customer_id
FROM logs_raw_mt;

RENAME TABLE logs_raw_mt TO logs_raw_mt_old;
RENAME TABLE logs_raw_mt_new TO logs_raw_mt;

-- ---------------------------------------------------------------------------
-- logs_normalized_mt
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS logs_normalized_mt_new (
    ts DateTime64(3, 'UTC'),
    date Date,
    hour UInt8,
    host LowCardinality(String),
    service LowCardinality(String),
    level LowCardinality(String),
    msg String,
    trace_id String,
    span_id String,
    status UInt16,
    src_ip String,
    user_id String,
    severity_num UInt8,
    facility UInt8,
    ingested_at DateTime64(3, 'UTC'),
    customer_id String,
    INDEX idx_msg_tokens msg TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (customer_id, service, level, ts, host)
PRIMARY KEY (customer_id, service, level, ts)
TTL toDateTime(ts) + toIntervalDay(30)
SETTINGS index_granularity = 8192;

INSERT INTO logs_normalized_mt_new SELECT
    ts, date, hour, host, service, level, msg, trace_id, span_id, status,
    src_ip, user_id, severity_num, facility, ingested_at, customer_id
FROM logs_normalized_mt;

RENAME TABLE logs_normalized_mt TO logs_normalized_mt_old;
RENAME TABLE logs_normalized_mt_new TO logs_normalized_mt;

-- ---------------------------------------------------------------------------
-- POST-MIGRATION VERIFICATION -- run these before dropping the _old tables.
--
--   SELECT count() FROM logs_raw_mt;
--   SELECT count() FROM logs_raw_mt_old;         -- must match
--
--   SELECT count() FROM system.parts
--    WHERE table = 'logs_raw_mt' AND active;     -- should be O(months)
--
-- Only after both check out:
--   DROP TABLE logs_raw_mt_old;
--   DROP TABLE logs_normalized_mt_old;
-- ---------------------------------------------------------------------------
