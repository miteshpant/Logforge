-- Exactly-once ingest: each insert into logs_raw_mt carries an
-- insert_deduplication_token derived from the batch's content
-- (log_processor.dedup_token), and ClickHouse drops an insert whose token it
-- has seen among the table's last 1000 inserts. Plain MergeTree needs this
-- window set; Replicated tables (the HA compose) deduplicate by default.
ALTER TABLE logs_raw_mt MODIFY SETTING non_replicated_deduplication_window = 1000;
ALTER TABLE logs_normalized_mt MODIFY SETTING non_replicated_deduplication_window = 1000;
