-- Support tickets (docs/admin.md): a tenant member asks the platform's
-- support; platform admins answer from the admin UI. The conversation is
-- kept on the ticket as JSON; each change writes a newer version.
CREATE TABLE IF NOT EXISTS support_tickets_mt
(
    tenant_id String,
    id String,
    subject String,
    status LowCardinality(String),
    priority LowCardinality(String),
    created_by String,
    created_by_id String,
    messages String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (tenant_id, id);
