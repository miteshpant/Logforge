-- Custom roles (Phase 14, docs/enterprise.md): extra permissions and/or a
-- data scope (the services whose logs a role may read), per tenant, and
-- who holds them. Latest version wins; `deleted` marks removal.

CREATE TABLE IF NOT EXISTS custom_roles_mt
(
    customer_id String,
    id String,
    name String,
    description String,
    permissions Array(String),
    services Array(String),
    scoped UInt8,
    deleted UInt8 DEFAULT 0,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);

CREATE TABLE IF NOT EXISTS custom_role_members_mt
(
    customer_id String,
    user_id String,
    role_id String,
    granted_by String,
    deleted UInt8 DEFAULT 0,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, user_id, role_id);
