-- SCIM provisioning (Phase 14, docs/enterprise.md).
-- scim_tokens_mt: tenant-scoped bearer tokens, stored as SHA-256 hashes.
-- scim_links_mt: the IdP's externalId for each provisioned user, per tenant.

CREATE TABLE IF NOT EXISTS scim_tokens_mt
(
    customer_id String,
    id String,
    name String,
    token_hash String,
    revoked UInt8 DEFAULT 0,
    created_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);

CREATE TABLE IF NOT EXISTS scim_links_mt
(
    customer_id String,
    user_id String,
    external_id String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, user_id);
