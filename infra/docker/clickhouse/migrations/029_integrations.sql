-- Integrations (Phase 13, docs/response.md): per-tenant connections to Slack,
-- Teams, PagerDuty, Opsgenie, Jira, GitHub, webhooks and containment
-- automations. `secrets` holds the integration's tokens sealed with Fernet
-- under LOGFORGE_SECRETS_KEY; the API never returns them. Latest version per
-- (tenant, id) wins; `deleted` marks removal.

CREATE TABLE IF NOT EXISTS integrations_mt
(
    customer_id String,
    id String,
    name String,
    kind LowCardinality(String),
    config String,
    secrets String,
    enabled UInt8 DEFAULT 1,
    deleted UInt8 DEFAULT 0,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);
