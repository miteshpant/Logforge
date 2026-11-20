-- Per-tenant SLA targets for cases (docs/cases.md): overrides of the default
-- minutes to acknowledge and resolve per severity, as JSON
-- ({"acknowledge": {"critical": 10}, ...}). Latest version wins; an empty
-- object means the defaults.
CREATE TABLE IF NOT EXISTS case_sla_mt
(
    customer_id String,
    overrides String,
    updated_by String,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY customer_id;
