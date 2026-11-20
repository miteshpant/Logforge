-- Quota usage is counted by appending, not by mutating tenant_quotas_mt on every
-- request (a per-request ALTER TABLE ... UPDATE queues one ClickHouse mutation per
-- call and loses increments when two requests race).
--
-- Each increment is a row keyed by the quota's last_reset (to the second: query
-- parameters drop milliseconds) at the time it was counted; rows with the same key are summed in the background. A reset moves
-- last_reset on, so older rows stop counting without being deleted (TTL removes
-- them later). tenant_quotas_mt.current_usage stays as the baseline, which is what
-- absolute writers (the storage sync) and resets set.
CREATE TABLE IF NOT EXISTS quota_usage_events_mt (
    tenant_id String,
    quota_type LowCardinality(String),
    reset_epoch DateTime,
    amount UInt64
) ENGINE = SummingMergeTree(amount)
ORDER BY (tenant_id, quota_type, reset_epoch)
TTL toDateTime(reset_epoch) + INTERVAL 400 DAY;

-- Quotas with the counted usage added: read this instead of tenant_quotas_mt.
CREATE OR REPLACE VIEW tenant_quotas_v AS
SELECT
    q.id AS id, q.tenant_id AS tenant_id, q.quota_type AS quota_type,
    q.quota_limit AS quota_limit,
    q.current_usage + ifNull(c.counted, 0) AS current_usage,
    q.reset_period AS reset_period, q.last_reset AS last_reset,
    q.created_at AS created_at, q.updated_at AS updated_at, q.customer_id AS customer_id
FROM tenant_quotas_mt AS q
LEFT JOIN (
    SELECT tenant_id, quota_type, reset_epoch, sum(amount) AS counted
    FROM quota_usage_events_mt
    GROUP BY tenant_id, quota_type, reset_epoch
) AS c
ON c.tenant_id = q.tenant_id AND c.quota_type = toString(q.quota_type) AND c.reset_epoch = toDateTime(q.last_reset);
