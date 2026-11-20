-- Per-user notifications (docs/cases.md): someone @mentioned you in a case
-- comment, or assigned you a case. One row per notification; reading it
-- writes a newer version with read = 1. Kept 180 days.
CREATE TABLE IF NOT EXISTS user_inbox_mt
(
    tenant_id String,
    user_id String,
    id String,
    kind LowCardinality(String),
    title String,
    body String,
    link String,
    actor String,
    read UInt8 DEFAULT 0,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, user_id, id)
TTL toDateTime(created_at) + INTERVAL 180 DAY;
