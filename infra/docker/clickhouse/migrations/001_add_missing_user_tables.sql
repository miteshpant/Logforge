-- Migration 001: Add missing user management tables
-- This can be run on existing ClickHouse instances without data loss

-- Users table for authentication and user management
CREATE TABLE IF NOT EXISTS users_mt (
    id String,
    email String,
    name String,
    password_hash String,
    status Enum8('active'=1, 'inactive'=2, 'pending'=3, 'suspended'=4),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    last_login_at Nullable(DateTime64(3)),
    password_reset_token Nullable(String),
    password_reset_expires Nullable(DateTime64(3)),
    email_verified_at Nullable(DateTime64(3)),
    setup_token Nullable(String),
    setup_token_expires Nullable(DateTime64(3)),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree() 
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, id)
SETTINGS index_granularity = 8192;

-- User sessions table for JWT token management
CREATE TABLE IF NOT EXISTS user_sessions_mt (
    id String,
    user_id String,
    session_token String,
    ip_address String,
    user_agent String,
    created_at DateTime64(3) DEFAULT now64(3),
    last_activity DateTime64(3) DEFAULT now64(3),
    expires_at DateTime64(3),
    status Enum8('active'=1, 'expired'=2, 'revoked'=3),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree() 
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, session_token)
SETTINGS index_granularity = 8192;

-- User tenant roles table for role-based access control
CREATE TABLE IF NOT EXISTS user_tenant_roles_mt (
    id String,
    user_id String,
    tenant_id String,
    role String,
    granted_by String,
    granted_at DateTime64(3) DEFAULT now64(3),
    expires_at Nullable(DateTime64(3)),
    status Enum8('active'=1, 'inactive'=2, 'expired'=3),
    created_at DateTime64(3) DEFAULT now64(3),
    updated_at DateTime64(3) DEFAULT now64(3),
    customer_id String DEFAULT 'platform'
) ENGINE = MergeTree() 
PARTITION BY toYYYYMM(created_at)
ORDER BY (customer_id, user_id, tenant_id)
SETTINGS index_granularity = 8192;