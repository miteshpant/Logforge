-- Migration: Seed MITRE ATT&CK Default Rules
-- Description: Load all 286 MITRE ATT&CK Enterprise techniques as default Sigma rules
-- Created: 2025-10-28
-- 
-- This migration creates a stored procedure to seed MITRE rules
-- The actual data loading is handled by a Python script that runs after this migration

-- Create system_migrations table if it doesn't exist (for tracking)
CREATE TABLE IF NOT EXISTS system_migrations (
    migration_name String,
    version String,
    applied_at DateTime DEFAULT now(),
    description String,
    status Enum8('success' = 1, 'failed' = 2, 'rollback' = 3)
) ENGINE = MergeTree()
ORDER BY migration_name;

-- Ensure sigma_rules_mt table has the correct structure
CREATE TABLE IF NOT EXISTS sigma_rules_mt (
    id String,
    name String,
    description String,
    rule_content String,
    mitre_techniques Array(String),
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    is_enabled UInt8 DEFAULT 1,
    false_positive_rate Float32 DEFAULT 0.0,
    last_matched Nullable(DateTime64(3)),
    match_count UInt64 DEFAULT 0,
    created_by String DEFAULT 'system',
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id Nullable(String)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- Create security_events_mt table for storing sigma rule matches
CREATE TABLE IF NOT EXISTS security_events_mt (
    id String,
    customer_id String,
    rule_id String,
    event_type String,
    severity Enum8('low' = 1, 'medium' = 2, 'high' = 3, 'critical' = 4),
    title String,
    description String,
    attack_techniques Array(String),
    kill_chain_phases Array(String),
    artifact_data String,
    matched_fields String,
    status Enum8('open' = 1, 'investigating' = 2, 'resolved' = 3, 'false_positive' = 4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, created_at, id)
SETTINGS index_granularity = 8192;

-- Insert a marker to indicate MITRE rules should be loaded
-- This will be checked by the application to trigger the Python-based loading
INSERT INTO system_migrations (
    migration_name, 
    version, 
    applied_at, 
    description, 
    status
) VALUES (
    '003_seed_mitre_rules_marker', 
    '1.0.0', 
    now(), 
    'Marker for MITRE rules seeding - triggers Python script execution', 
    'success'
);