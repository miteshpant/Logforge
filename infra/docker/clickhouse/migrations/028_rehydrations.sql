-- Rehydration (Phase 12, docs/storage.md): archived days copied back into
-- ClickHouse, and until when. The retention job doesn't delete a rehydrated
-- day before `until`; after that the day is deleted again (its archive stays).

CREATE TABLE IF NOT EXISTS rehydrations_mt
(
    customer_id String,
    data_type LowCardinality(String),
    day Date,
    until Date,
    rows UInt64,
    requested_by String,
    requested_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = MergeTree
ORDER BY (customer_id, data_type, day)
TTL until + INTERVAL 30 DAY;
