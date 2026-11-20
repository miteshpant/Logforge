-- Playbooks (Phase 13, docs/response.md).
--
-- playbooks_mt: each tenant's playbook definitions (YAML); latest version per
-- (tenant, id) wins, `deleted` marks removal.
-- playbook_runs_mt: every run, its state (steps, outputs, approvals) as JSON,
-- one row per change; latest per (tenant, id) wins. (playbook_id,
-- trigger_ref) identifies what started it, so an alert starts a playbook once.
-- case_tickets_mt: tickets created for cases (Jira, GitHub), kept in sync
-- both ways.

CREATE TABLE IF NOT EXISTS playbooks_mt
(
    customer_id String,
    id String,
    name String,
    definition String,
    enabled UInt8 DEFAULT 1,
    deleted UInt8 DEFAULT 0,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id);

CREATE TABLE IF NOT EXISTS playbook_runs_mt
(
    customer_id String,
    id String,
    playbook_id String,
    trigger LowCardinality(String),
    trigger_ref String,
    status LowCardinality(String),
    state String,
    created_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC') DEFAULT now64(),
    INDEX idx_trigger trigger_ref TYPE bloom_filter(0.01) GRANULARITY 4
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, id)
TTL toDateTime(created_at) + INTERVAL 180 DAY;

CREATE TABLE IF NOT EXISTS case_tickets_mt
(
    customer_id String,
    case_id String,
    integration_id String,
    system LowCardinality(String),
    ticket String,
    url String,
    ticket_status String,
    case_status String,
    synced_at DateTime64(3, 'UTC'),
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id, case_id, ticket);
