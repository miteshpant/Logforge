-- Migration 012 (LF-018): token bloom-filter skip index for full-text search
--
-- WHY
-- Keyword search compiles to `msg LIKE '%term%'`, which decompresses and scans
-- the entire msg column for the queried time range because logs_raw_mt has NO
-- data-skipping indexes (verified live: system.data_skipping_indices is empty
-- for both log tables). A tokenbf_v1 index lets ClickHouse skip granules that
-- cannot contain the token, and the query engine emits `hasToken(msg, term)`
-- for plain single-token searches so the index is actually used.
--
-- INDEX PARAMETERS
-- tokenbf_v1(32768, 3, 0): 32KiB bloom filter per granule-block, 3 hash
-- functions, seed 0. GRANULARITY 4 = one filter per 4 index granules
-- (4 x 8192 rows), balancing filter selectivity against index size.
--
-- BACKFILL
-- ADD INDEX only indexes parts written AFTER this migration. To index
-- existing data, run the following manually IN AN OFF-PEAK WINDOW (it rewrites
-- index files for every part and is IO-expensive on large tables):
--
--     ALTER TABLE logs_raw_mt MATERIALIZE INDEX idx_msg_tokens;
--     ALTER TABLE logs_normalized_mt MATERIALIZE INDEX idx_msg_tokens;
--
-- Monitor with: SELECT * FROM system.mutations WHERE is_done = 0;

ALTER TABLE logs_raw_mt
    ADD INDEX IF NOT EXISTS idx_msg_tokens msg
    TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4;

ALTER TABLE logs_normalized_mt
    ADD INDEX IF NOT EXISTS idx_msg_tokens msg
    TYPE tokenbf_v1(32768, 3, 0) GRANULARITY 4;
