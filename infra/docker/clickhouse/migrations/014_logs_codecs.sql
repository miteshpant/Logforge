-- Migration 014 (LF-030): ZSTD compression codecs on the two largest columns
--
-- WHY
-- init.sql specified `msg String CODEC(ZSTD(3))` and `attrs String
-- CODEC(ZSTD(3))`, but compose.yml mounts init_simple.sql, which declares
-- both columns with NO codec -- so the deployed tables compress at ~5x where
-- the intended ZSTD(3) reaches far higher ratios on log text. Storage is the
-- dominant recurring cost for this workload; these two columns are the bulk
-- of every row.
--
-- SCOPE
-- MODIFY COLUMN ... CODEC applies to parts written AFTER this migration.
-- Existing parts keep their old encoding until merged. To recompress history
-- immediately, run manually IN AN OFF-PEAK WINDOW (rewrites every part):
--
--     OPTIMIZE TABLE logs_raw_mt FINAL;
--     OPTIMIZE TABLE logs_normalized_mt FINAL;
--
-- Measure before/after with:
--     SELECT table, sum(data_compressed_bytes) c, sum(data_uncompressed_bytes) u,
--            round(u / c, 2) AS ratio
--     FROM system.columns WHERE table IN ('logs_raw_mt', 'logs_normalized_mt')
--     GROUP BY table;

ALTER TABLE logs_raw_mt MODIFY COLUMN msg String CODEC(ZSTD(3));

ALTER TABLE logs_raw_mt MODIFY COLUMN attrs String CODEC(ZSTD(3));

ALTER TABLE logs_normalized_mt MODIFY COLUMN msg String CODEC(ZSTD(3));
