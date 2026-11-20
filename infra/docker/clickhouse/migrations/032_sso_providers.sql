-- OIDC sign-in providers (Phase 14, docs/enterprise.md). One row per
-- version; the latest per (tenant, id) wins, `deleted` marks removal.
-- client_secret is sealed with LOGFORGE_SECRETS_KEY (integrations/secrets.py).

CREATE TABLE IF NOT EXISTS sso_providers_mt
(
    customer_id String,
    id String,
    name String,
    issuer String,
    client_id String,
    client_secret String,
    scopes String,
    groups_claim String,
    role_mapping String,
    default_role String,
    allowed_domains Array(String),
    enabled UInt8 DEFAULT 1,
    deleted UInt8 DEFAULT 0,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);
