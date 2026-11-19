-- Migration 025: AI foundation (Phase 8)
--
-- ai_settings_mt: one row per change of a tenant's AI settings (opt-in,
-- provider, extra redacted fields, budgets); the latest row (by seq) is
-- current. A tenant with no row has AI off.
--
-- ai_audit_mt: every prompt, response, tool call and tool result of every AI
-- request, as sent to the provider (after redaction), with token counts on
-- responses. Kept for 90 days; config/ai.yml audit_retention_days changes
-- the TTL when the API starts.

CREATE TABLE IF NOT EXISTS ai_settings_mt
(
    tenant_id String,
    seq UInt64,
    settings String,
    updated_at DateTime64(3, 'UTC'),
    updated_by String
)
ENGINE = MergeTree
ORDER BY (tenant_id, seq);

CREATE TABLE IF NOT EXISTS ai_audit_mt
(
    tenant_id String,
    request_id String,
    seq UInt32,
    ts DateTime64(3, 'UTC'),
    user_id String,
    feature LowCardinality(String),
    kind LowCardinality(String),
    provider String,
    model String,
    external UInt8,
    content String,
    input_tokens UInt32,
    output_tokens UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, ts, request_id, seq)
TTL toDateTime(ts) + INTERVAL 90 DAY;
