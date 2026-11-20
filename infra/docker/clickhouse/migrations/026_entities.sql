-- Migration 026: entities (Phase 11)
--
-- entities_mt: every user, host, IP address, service and cloud account seen
-- in a tenant's events, with when it was first and last seen and how many
-- events mention it. Kept up to date by entities_mv as events are written.
--
-- entity_edges_mt: which entities appear together in the same event (a user
-- on a host, an address reaching a host or signing in as a user, a service
-- on a host), with first and last seen and a count. Kept by entity_edges_mv.
--
-- Both are aggregates: query them with min(first_seen), max(last_seen) and
-- sum(events) grouped by the key. The last statements backfill the last 30
-- days of events written before this migration.

CREATE TABLE IF NOT EXISTS entities_mt
(
    customer_id String,
    entity_type LowCardinality(String),
    value String,
    first_seen SimpleAggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen SimpleAggregateFunction(max, DateTime64(3, 'UTC')),
    events SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (customer_id, entity_type, value);

CREATE TABLE IF NOT EXISTS entity_edges_mt
(
    customer_id String,
    a_type LowCardinality(String),
    a String,
    b_type LowCardinality(String),
    b String,
    first_seen SimpleAggregateFunction(min, DateTime64(3, 'UTC')),
    last_seen SimpleAggregateFunction(max, DateTime64(3, 'UTC')),
    events SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (customer_id, a_type, a, b_type, b);

CREATE MATERIALIZED VIEW IF NOT EXISTS entities_mv TO entities_mt AS
SELECT customer_id, e.1 AS entity_type, e.2 AS value, min(ts) AS first_seen, max(ts) AS last_seen,
       count() AS events
FROM logs_raw_mt
ARRAY JOIN arrayFilter(x -> x.2 != '', [
    tuple('user', if(user_id != '', user_id, JSONExtractString(attrs, 'user'))),
    tuple('host', if(toString(host) != '', toString(host), JSONExtractString(attrs, 'hostname'))),
    tuple('ip', if(src_ip != '', src_ip, JSONExtractString(attrs, 'src_ip'))),
    tuple('ip', JSONExtractString(attrs, 'dst_ip')),
    tuple('service', toString(service)),
    tuple('cloud_account', if(JSONExtractString(attrs, 'recipientAccountId') != '',
                              JSONExtractString(attrs, 'recipientAccountId'),
                              JSONExtractString(attrs, 'ocsf', 'cloud', 'account', 'uid')))
]) AS e
GROUP BY customer_id, entity_type, value;

CREATE MATERIALIZED VIEW IF NOT EXISTS entity_edges_mv TO entity_edges_mt AS
SELECT customer_id, e.1 AS a_type, e.2 AS a, e.3 AS b_type, e.4 AS b, min(ts) AS first_seen, max(ts) AS last_seen,
       count() AS events
FROM
(
    SELECT customer_id, ts,
           if(user_id != '', user_id, JSONExtractString(attrs, 'user')) AS u,
           if(toString(host) != '', toString(host), JSONExtractString(attrs, 'hostname')) AS h,
           if(src_ip != '', src_ip, JSONExtractString(attrs, 'src_ip')) AS i,
           toString(service) AS s
    FROM logs_raw_mt
)
ARRAY JOIN arrayFilter(x -> x.2 != '' AND x.4 != '', [
    tuple('user', u, 'host', h),
    tuple('ip', i, 'host', h),
    tuple('ip', i, 'user', u),
    tuple('service', s, 'host', h)
]) AS e
GROUP BY customer_id, a_type, a, b_type, b;

INSERT INTO entities_mt
SELECT customer_id, e.1 AS entity_type, e.2 AS value, min(ts) AS first_seen, max(ts) AS last_seen,
       count() AS events
FROM logs_raw_mt
ARRAY JOIN arrayFilter(x -> x.2 != '', [
    tuple('user', if(user_id != '', user_id, JSONExtractString(attrs, 'user'))),
    tuple('host', if(toString(host) != '', toString(host), JSONExtractString(attrs, 'hostname'))),
    tuple('ip', if(src_ip != '', src_ip, JSONExtractString(attrs, 'src_ip'))),
    tuple('ip', JSONExtractString(attrs, 'dst_ip')),
    tuple('service', toString(service)),
    tuple('cloud_account', if(JSONExtractString(attrs, 'recipientAccountId') != '',
                              JSONExtractString(attrs, 'recipientAccountId'),
                              JSONExtractString(attrs, 'ocsf', 'cloud', 'account', 'uid')))
]) AS e
WHERE ts > now() - INTERVAL 30 DAY
GROUP BY customer_id, entity_type, value;

INSERT INTO entity_edges_mt
SELECT customer_id, e.1 AS a_type, e.2 AS a, e.3 AS b_type, e.4 AS b, min(ts) AS first_seen, max(ts) AS last_seen,
       count() AS events
FROM
(
    SELECT customer_id, ts,
           if(user_id != '', user_id, JSONExtractString(attrs, 'user')) AS u,
           if(toString(host) != '', toString(host), JSONExtractString(attrs, 'hostname')) AS h,
           if(src_ip != '', src_ip, JSONExtractString(attrs, 'src_ip')) AS i,
           toString(service) AS s
    FROM logs_raw_mt
    WHERE ts > now() - INTERVAL 30 DAY
)
ARRAY JOIN arrayFilter(x -> x.2 != '' AND x.4 != '', [
    tuple('user', u, 'host', h),
    tuple('ip', i, 'host', h),
    tuple('ip', i, 'user', u),
    tuple('service', s, 'host', h)
]) AS e
GROUP BY customer_id, a_type, a, b_type, b;
