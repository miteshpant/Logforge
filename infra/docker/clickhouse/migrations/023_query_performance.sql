-- Migration 023: query performance (Phase 6)
--
-- p_hourly_counts: count() per (tenant, hour, service, level, status). The
-- LogforgeQL compiler answers count queries over these fields from it (whole
-- hours) plus the events at the partial hours at each end of the window, so
-- the answer is exact. A projection is kept part by part with the events, so
-- it can never count an event twice or miss one.
--
-- Skip indexes for point lookups on high-cardinality fields that are not in
-- the sort key (trace id, source IP, user id).
--
-- MATERIALIZE builds the projection and indexes for existing parts in the
-- background; until a part has them, queries read that part's events.

ALTER TABLE logs_raw_mt ADD PROJECTION IF NOT EXISTS p_hourly_counts
(
    SELECT customer_id, toStartOfHour(ts), service, level, status, count()
    GROUP BY customer_id, toStartOfHour(ts), service, level, status
);
ALTER TABLE logs_raw_mt MATERIALIZE PROJECTION p_hourly_counts;

ALTER TABLE logs_raw_mt ADD INDEX IF NOT EXISTS idx_trace_id trace_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE logs_raw_mt ADD INDEX IF NOT EXISTS idx_src_ip src_ip TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE logs_raw_mt ADD INDEX IF NOT EXISTS idx_user_id user_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE logs_raw_mt MATERIALIZE INDEX idx_trace_id;
ALTER TABLE logs_raw_mt MATERIALIZE INDEX idx_src_ip;
ALTER TABLE logs_raw_mt MATERIALIZE INDEX idx_user_id;
