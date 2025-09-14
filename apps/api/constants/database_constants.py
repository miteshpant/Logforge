"""
Database Constants - Logforge API  
Centralized constants for database configuration, table names, and queries
"""

# Database Connection
DEFAULT_CONNECTION_TIMEOUT = 30
DEFAULT_QUERY_TIMEOUT = 120
MAX_CONNECTIONS = 20
MIN_CONNECTIONS = 5

# Table Names - Multi-Tenant
USERS_TABLE = "users_mt"
USER_SESSIONS_TABLE = "user_sessions_mt" 
USER_TENANT_ROLES_TABLE = "user_tenant_roles_mt"
TENANTS_TABLE = "tenants_mt"
TENANT_CONFIGS_TABLE = "tenant_configs_mt"
TENANT_QUOTAS_TABLE = "tenant_quotas_mt"
TENANT_STORAGE_CONFIGS_TABLE = "tenant_storage_configs_mt"
LEGAL_HOLDS_TABLE = "legal_holds_mt"

# Alert System Tables
ALERT_RULES_TABLE = "alert_rules_mt"
ALERT_INSTANCES_TABLE = "alert_instances_mt"
NOTIFICATION_CHANNELS_TABLE = "notification_channels_mt"
ALERT_RULE_STATES_TABLE = "alert_rule_states_mt"

# Security Analytics Tables
SIGMA_RULES_TABLE = "sigma_rules_mt"
THREAT_INTEL_TABLE = "threat_intel_mt"
SECURITY_EVENTS_TABLE = "security_events_mt"

# AI System Tables
AI_INVESTIGATIONS_TABLE = "ai_investigations_mt"
AI_ANALYSES_TABLE = "ai_analyses_mt"
AI_BASELINES_TABLE = "ai_baselines_mt"
AI_QUERY_HISTORY_TABLE = "ai_query_history_mt"

# Enterprise Tables
AUTH_PROVIDERS_TABLE = "auth_providers_mt"
API_KEYS_ENTERPRISE_TABLE = "api_keys_enterprise_mt"
MFA_SETUPS_TABLE = "mfa_setups_mt"
COMPLIANCE_REPORTS_TABLE = "compliance_reports_mt"
INTEGRATIONS_TABLE = "integrations_mt"
BACKUP_POLICIES_TABLE = "backup_policies_mt"

# Observability Tables
SERVICE_TOPOLOGY_TABLE = "service_topology_mt"

# User Invitations
USER_INVITATIONS_TABLE = "user_invitations_mt"

# Log Storage Tables
LOGS_RAW_TABLE = "logs_raw_mt"
LOGS_NORMALIZED_TABLE = "logs_normalized_mt"

# Ingestion Tracking Tables
INGESTION_STATS_TABLE = "ingestion_stats_mt"
INGESTION_ERRORS_TABLE = "ingestion_errors_mt"

# Query Management Tables
SAVED_QUERIES_TABLE = "saved_queries_mt"
QUERY_CACHE_TABLE = "query_cache_mt"

# Dashboard Management Tables
DASHBOARDS_TABLE = "dashboards_mt"
DASHBOARD_WIDGETS_TABLE = "dashboard_widgets_mt"
DASHBOARD_SHARES_TABLE = "dashboard_shares_mt"

# Storage Management Tables
RETENTION_POLICIES_TABLE = "retention_policies_mt"
STORAGE_BACKENDS_TABLE = "storage_backends_mt"
STORAGE_OPERATIONS_TABLE = "storage_operations_mt"
STORAGE_QUOTAS_TABLE = "storage_quotas_mt"
DATA_ARCHIVES_TABLE = "data_archives_mt"

# Index Names
IDX_USERS_EMAIL = "idx_users_email"
IDX_TENANTS_DOMAIN = "idx_tenants_domain"
IDX_ALERT_RULES_ENABLED = "idx_alert_rules_enabled"
IDX_SECURITY_EVENTS_TIME = "idx_security_events_time"

# Query Limits
DEFAULT_BATCH_SIZE = 1000
MAX_BATCH_SIZE = 10000
DEFAULT_TTL_DAYS = 90
MAX_TTL_DAYS = 2555  # ~7 years

# Status Values
STATUS_ACTIVE = "active"
STATUS_INACTIVE = "inactive"
STATUS_PENDING = "pending"
STATUS_SUSPENDED = "suspended"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"

# Default Quotas
DEFAULT_MONTHLY_LOG_LIMIT = 1000000  # 1M logs per month
DEFAULT_STORAGE_LIMIT_GB = 100
DEFAULT_API_CALLS_LIMIT = 10000
DEFAULT_USER_LIMIT = 50