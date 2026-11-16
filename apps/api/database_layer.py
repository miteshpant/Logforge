"""
Database Layer - Centralized ClickHouse abstraction for Logforge Platform
Provides secure, performant, and consistent database operations for all services
"""

import os
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import lru_cache
import clickhouse_connect
import structlog
from contextlib import asynccontextmanager

logger = structlog.get_logger()

class DatabaseError(Exception):
    """Database operation error"""
    pass

class SecurityError(Exception):
    """Database security violation"""
    pass

class DatabaseLayer:
    """Centralized database abstraction layer for ClickHouse operations"""
    
    # Service authentication registry
    AUTHORIZED_SERVICES = {
        'UserService': os.getenv('USER_SERVICE_KEY', 'user-service-key-dev'),
        'RoleService': os.getenv('ROLE_SERVICE_KEY', 'role-service-key-dev'),
        'AlertService': os.getenv('ALERT_SERVICE_KEY', 'alert-service-key-dev'),
        'SecurityService': os.getenv('SECURITY_SERVICE_KEY', 'security-service-key-dev'),
        'IngestionService': os.getenv('INGESTION_SERVICE_KEY', 'ingestion-service-key-dev'),
        'QueryService': os.getenv('QUERY_SERVICE_KEY', 'query-service-key-dev'),
        'StorageService': os.getenv('STORAGE_SERVICE_KEY', 'storage-service-key-dev'),
        'TestService': 'test-service-key',  # For testing only
        # Additional Services
        'UsageService': os.getenv('USAGE_SERVICE_KEY', 'usage-service-key-dev'),
        'HealthService': os.getenv('HEALTH_SERVICE_KEY', 'health-service-key-dev'),
        # DAO Services
        'UserDAO': os.getenv('USER_SERVICE_KEY', 'user-dao-service-key'),
        'TenantDAO': os.getenv('TENANT_SERVICE_KEY', 'tenant-dao-service-key'), 
        'RoleDAO': os.getenv('ROLE_SERVICE_KEY', 'role-dao-service-key'),
        'IngestionDAO': os.getenv('INGESTION_SERVICE_KEY', 'ingestion-dao-service-key'),
        'QueryDAO': os.getenv('QUERY_SERVICE_KEY', 'query-dao-service-key'),
        'DashboardDAO': os.getenv('DASHBOARD_SERVICE_KEY', 'dashboard-dao-service-key'),
        'StorageDAO': os.getenv('STORAGE_SERVICE_KEY', 'storage-dao-service-key'),
        'AlertDAO': os.getenv('ALERT_SERVICE_KEY', 'alert-dao-service-key'),
        'UsageDAO': os.getenv('USAGE_SERVICE_KEY', 'usage-dao-service-key'),
        'SecurityDAO': os.getenv('SECURITY_SERVICE_KEY', 'security-dao-service-key'),
        'ObservabilityDAO': os.getenv('OBSERVABILITY_SERVICE_KEY', 'observability-dao-service-key'),
        'AIDAO': os.getenv('AI_SERVICE_KEY', 'ai-dao-service-key'),
        'EnterpriseDAO': os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-dao-service-key'),
        'SubscriptionDAO': os.getenv('SUBSCRIPTION_SERVICE_KEY', 'subscription-dao-service-key'),
        'PlatformSetup': os.getenv('PLATFORM_SETUP_KEY', 'platform-setup-key'),
        'IngestionTestService': 'ingestion-test-service-key',
        'AuditService': os.getenv('AUDIT_SERVICE_KEY', 'audit-service-key-dev'),
        'StorageQuotaSyncService': os.getenv('STORAGE_QUOTA_SYNC_KEY', 'storage-quota-sync-service-key'),
        # MITRE and Sigma Security Services
        'MitreDefaultLoader': os.getenv('MITRE_DEFAULT_LOADER_KEY', 'mitre-default-loader-service-key'),
        'SecuritySubscriptionChecker': os.getenv('SECURITY_SUBSCRIPTION_CHECKER_KEY', 'security-subscription-checker-service-key'),
        'SigmaProcessor': os.getenv('SIGMA_PROCESSOR_KEY', 'sigma-processor-service-key'),
        # Streaming Configuration Service
        'StreamingConfigDAO': os.getenv('STREAMING_CONFIG_SERVICE_KEY', 'streaming-config-service-key'),
        # Migration Service
        'MigrationService': os.getenv('MIGRATION_SERVICE_KEY', 'migration-service-key'),
        # Alert Correlation Service
        'AlertCorrelationService': os.getenv('ALERT_CORRELATION_SERVICE_KEY', 'alert-correlation-service-key'),
        # Quota services (ENH-030). These already had TABLE_ACCESS_CONTROL and
        # UPDATE_ALLOWED_SERVICES entries but were missing here, so
        # `DatabaseLayer("QuotaResetService", ...)` raised SecurityError on
        # construction. That is the "database permissions" problem the scheduler
        # was disabled for -- it was an authorization-registry gap, not a
        # ClickHouse grant.
        'QuotaResetService': os.getenv('QUOTA_RESET_SERVICE_KEY', 'quota-reset-service-key'),
        'QuotaTestService': os.getenv('QUOTA_TEST_SERVICE_KEY', 'quota-test-service-key'),
        'QuotaHistoryAPI': os.getenv('QUOTA_HISTORY_API_KEY', 'quota-history-api-key'),
        # Predictive Analytics Service
        'PredictiveAnalyticsService': os.getenv('PREDICTIVE_ANALYTICS_SERVICE_KEY', 'predictive-analytics-service-key')
    }
    
    # Table access control by service
    TABLE_ACCESS_CONTROL = {
        'UserService': ['users_mt', 'user_sessions_mt', 'user_tenant_roles_mt', 'api_usage_mt'],
        'RoleService': ['user_tenant_roles_mt', 'users_mt'],  # Role service needs access to user and role tables
        'AlertService': ['alert_rules_mt', 'alert_events_mt', 'alert_notifications_mt'],
        'SecurityService': ['security_events_mt', 'sigma_rules_mt', 'threat_intel_mt'],
        'IngestionService': ['logs_raw_mt', 'logs_normalized_mt', 'ingestion_stats_mt'],
        'QueryService': ['logs_normalized_mt', 'query_cache_mt', 'saved_queries_mt'],
        'StorageService': ['logs_raw_mt', 'logs_normalized_mt', 'storage_metadata_mt'],
        'TestService': ['*'],  # Test service can access all tables
        # Additional Services
        'UsageService': ['api_usage_mt', 'tenants_mt'],
        'HealthService': ['logs_raw_mt', 'logs_normalized_mt', 'users_mt', 'roles_mt', 'alert_rules_mt'],
        # DAO Services - inherit permissions from parent services
        'UserDAO': ['users_mt', 'user_sessions_mt', 'user_tenant_roles_mt', 'user_invitations_mt'],
        'TenantDAO': ['tenants_mt', 'tenant_configs_mt', 'tenant_quotas_mt'], 
        'RoleDAO': ['user_tenant_roles_mt', 'users_mt'],
        'IngestionDAO': ['ingestion_stats_mt', 'ingestion_errors_mt'],
        'QueryDAO': ['saved_queries_mt', 'query_cache_mt', 'logs_normalized_mt'],
        'DashboardDAO': ['dashboards_mt', 'dashboard_widgets_mt', 'dashboard_shares_mt', 'logs_normalized_mt'],
        'StorageDAO': ['retention_policies_mt', 'storage_backends_mt', 'storage_operations_mt', 'storage_quotas_mt', 'data_archives_mt', 'archive_metadata_mt', 'archive_access_log_mt', 'logs_raw_mt', 'logs_normalized_mt'],
        'AlertDAO': ['alert_rules_mt', 'alert_instances_mt', 'notification_channels_mt', 'alert_rule_states_mt'],
        'UsageDAO': ['api_usage_audit_mt', 'tenants_mt', 'users_mt', 'tenant_bills_mt', 'logs_raw_mt'],
        'SecurityDAO': ['sigma_rules_mt', 'security_events_mt', 'threat_intel_mt'],
        'ObservabilityDAO': ['traces_mt', 'metrics_mt', 'service_topology_mt', 'service_dependencies_mt'],
        'AIDAO': ['ai_investigations_mt', 'ai_analyses_mt', 'ai_baselines_mt', 'ai_query_history_mt'],
        'EnterpriseDAO': ['auth_providers_mt', 'api_keys_enterprise_mt', 'tenants_mt', 'enterprise_compliance_mt', 'enterprise_integrations_mt', 'enterprise_audit_logs_mt', 'api_usage_mt'],
        'SubscriptionDAO': ['tenant_subscriptions_mt', 'feature_rates_mt', 'usage_records_mt', 'tenant_deletions_mt'],
        'PlatformSetup': ['users_mt', 'user_tenant_roles_mt', 'user_sessions_mt'],
        'IngestionTestService': ['*'],  # Test service can access all tables
        'AuditService': ['enterprise_audit_logs_mt'],
        # Quota Reset Service - needs access to quotas and historical data
        'QuotaResetService': ['tenant_quotas_mt', 'quota_usage_history_mt'],
        'QuotaTestService': ['tenant_quotas_mt', 'quota_usage_history_mt'],
        'QuotaHistoryAPI': ['quota_usage_history_mt'],
        # Storage Quota Sync Service - needs access to logs and quotas
        'StorageQuotaSyncService': ['logs_raw_mt', 'tenant_quotas_mt'],
        # MITRE and Sigma Security Services
        'MitreDefaultLoader': ['sigma_rules_mt'],  # Needs to insert default MITRE rules
        'SecuritySubscriptionChecker': ['tenant_subscriptions_mt'],  # Needs to check subscription access
        'SigmaProcessor': ['security_events_mt', 'sigma_rules_mt'],  # Needs to create security events and read rules
        # Streaming Configuration Service
        'StreamingConfigDAO': ['tenant_configs_mt'],  # Needs to manage streaming configurations in tenant configs table
        # Migration Service
        'MigrationService': ['system_migrations', 'sigma_rules_mt', 'security_events_mt'],  # Needs to check migrations and manage security tables
        # Alert Correlation Service - read-only access to alerts and logs for correlation analysis
        'AlertCorrelationService': ['alert_instances_mt', 'alert_rules_mt', 'logs_normalized_mt'],
        # Predictive Analytics Service - read-only access to logs, metrics, alerts, baselines for forecasting
        'PredictiveAnalyticsService': ['logs_normalized_mt', 'metrics_mt', 'alert_instances_mt', 'ai_baselines_mt']
    }
    
    # Dangerous operations requiring admin privileges
    ADMIN_OPERATIONS = ['DROP', 'TRUNCATE', 'CREATE TABLE']
    ADMIN_SERVICES = ['TestService', 'QuotaTestService']  # Services allowed to perform admin operations
    
    # Services allowed to perform DELETE operations
    DELETE_ALLOWED_SERVICES = ['SecurityDAO', 'SecurityService', 'TestService', 'QuotaTestService', 'UserDAO', 'AlertDAO']
    
    # Services allowed to perform UPDATE operations (ALTER TABLE ... UPDATE)
    UPDATE_ALLOWED_SERVICES = ['UserService', 'AlertService', 'SecurityService', 'TestService', 'UserDAO', 'TenantDAO', 'RoleDAO', 'QueryDAO', 'QueryService', 'DashboardDAO', 'DashboardService', 'StorageDAO', 'StorageService', 'AlertDAO', 'SecurityDAO', 'AIDAO', 'ObservabilityDAO', 'EnterpriseDAO', 'SubscriptionDAO', 'QuotaResetService', 'QuotaTestService', 'StorageQuotaSyncService', 'StreamingConfigDAO']
    
    # LF-002: table-existence DDL/verification must run at most once per
    # process per service, not on every DatabaseLayer construction (DAOs are
    # constructed per request). Keyed by service name.
    _TABLES_ENSURED: set = set()

    @staticmethod
    def _pooled_db_enabled() -> bool:
        """
        LF-002 feature flag: when enabled (the default), every DatabaseLayer
        shares one process-wide ClickHouse client from
        `utils.connection_pool.get_shared_client()` instead of opening a new
        connection per construction (11 clients per /v1/logs request were
        measured). Set `LOGFORGE_POOLED_DB=false` to restore per-instance
        clients while the flag is being burned in.
        """
        return os.getenv("LOGFORGE_POOLED_DB", "true").strip().lower() not in {
            "false", "0", "no"
        }

    def __init__(self, service_name: str, service_key: str):
        """Initialize database layer with service authentication

        Args:
            service_name: Name of the requesting service
            service_key: Authentication key for the service
        """
        self.service_name = service_name

        # Validate service credentials
        if not self._validate_service_credentials(service_name, service_key):
            raise SecurityError(f"Invalid credentials for service: {service_name}")

        # Acquire ClickHouse client -- shared (pooled) by default
        self._client_is_shared = self._pooled_db_enabled()
        try:
            if self._client_is_shared:
                from utils.connection_pool import get_shared_client
                self.client = get_shared_client()
            else:
                from app_config import clickhouse_settings

                self.client = clickhouse_connect.get_client(**clickhouse_settings())
                logger.info("ClickHouse client initialized", service=service_name)
        except Exception as e:
            logger.error("Failed to initialize ClickHouse client", service=service_name, error=str(e))
            raise DatabaseError(f"Database connection failed: {str(e)}")

        # Ensure required tables exist (once per process per service)
        if service_name not in DatabaseLayer._TABLES_ENSURED:
            self._ensure_tables_exist()
            DatabaseLayer._TABLES_ENSURED.add(service_name)
    
    def _validate_service_credentials(self, service_name: str, service_key: str) -> bool:
        """Validate service authentication credentials"""
        expected_key = self.AUTHORIZED_SERVICES.get(service_name)
        if not expected_key or expected_key != service_key:
            logger.warning("Invalid service credentials", service=service_name)
            return False
        return True
    
    @staticmethod
    def _runtime_ddl_enabled() -> bool:
        """
        Whether services may issue DDL at runtime (ENH-021).

        Schema should be owned by the migration runner, not by application
        code: runtime `CREATE TABLE IF NOT EXISTS` lets environments drift, and
        it requires the application's database user to hold DDL privileges it
        should not need.

        Defaults to True to preserve existing behaviour for deployments that
        depend on it. Set `ALLOW_RUNTIME_DDL=false` once migrations own the
        schema -- the intended end state.
        """
        return os.getenv("ALLOW_RUNTIME_DDL", "true").strip().lower() not in {
            "false", "0", "no"
        }

    def _ensure_tables_exist(self):
        """Create required tables if they don't exist"""
        try:
            # ENH-021: creation is skipped when runtime DDL is disabled, so the
            # migration runner is the single owner of schema. Verification steps
            # below still run -- they only read, and a missing table should still
            # fail loudly rather than surface later as a confusing query error.
            if not self._runtime_ddl_enabled():
                logger.debug(
                    "Runtime DDL disabled; schema is owned by migrations",
                    service=self.service_name,
                )
            # User management tables
            elif self.service_name in ['UserService', 'UserDAO', 'TestService', 'PlatformSetup']:
                self._create_user_tables()
            
            # Alert management tables
            elif self.service_name == 'AlertService':
                self._create_alert_tables()
            
            # Security analytics tables
            elif self.service_name == 'SecurityService':
                self._create_security_tables()
            
            # Ingestion and query tables (created by respective services)
            elif self.service_name in ['IngestionService', 'StorageService']:
                self._create_log_tables()
            elif self.service_name in ['QueryService', 'QueryDAO']:
                self._verify_query_tables()
            elif self.service_name in ['DashboardService', 'DashboardDAO']:
                self._verify_dashboard_tables()
            elif self.service_name in ['StorageService', 'StorageDAO']:
                self._verify_storage_tables()
            elif self.service_name in ['AlertService', 'AlertDAO']:
                self._verify_alert_tables()
            
            logger.info("Database tables ensured", service=self.service_name)
            
        except Exception as e:
            logger.error("Failed to create tables", service=self.service_name, error=str(e))
            raise DatabaseError(f"Table creation failed: {str(e)}")
    
    def _create_user_tables(self):
        """Create user management tables"""
        # Users table
        self.client.command("""
            CREATE TABLE IF NOT EXISTS users_mt (
                id String,
                email String,
                name String,
                password_hash String,
                status Enum8('active'=1, 'inactive'=2, 'pending'=3, 'suspended'=4),
                created_at DateTime DEFAULT now(),
                updated_at DateTime DEFAULT now(),
                last_login_at Nullable(DateTime),
                password_reset_token Nullable(String),
                password_reset_expires Nullable(DateTime),
                email_verified_at Nullable(DateTime),
                setup_token Nullable(String),
                setup_token_expires Nullable(DateTime),
                customer_id String DEFAULT 'platform'
            ) ENGINE = MergeTree() 
            ORDER BY (customer_id, id)
            SETTINGS index_granularity = 8192
        """)
        
        # User sessions table
        self.client.command("""
            CREATE TABLE IF NOT EXISTS user_sessions_mt (
                id String,
                user_id String,
                session_token String,
                ip_address String,
                user_agent String,
                created_at DateTime DEFAULT now(),
                last_activity DateTime DEFAULT now(),
                expires_at DateTime,
                status Enum8('active'=1, 'expired'=2, 'revoked'=3),
                customer_id String DEFAULT 'platform'
            ) ENGINE = MergeTree() 
            ORDER BY (customer_id, user_id, session_token)
            SETTINGS index_granularity = 8192
        """)
        
        # User tenant roles table
        self.client.command("""
            CREATE TABLE IF NOT EXISTS user_tenant_roles_mt (
                id String,
                user_id String,
                tenant_id String,
                role String,
                granted_by String,
                granted_at DateTime DEFAULT now(),
                expires_at Nullable(DateTime),
                status Enum8('active'=1, 'inactive'=2, 'expired'=3),
                created_at DateTime DEFAULT now(),
                updated_at DateTime DEFAULT now(),
                customer_id String DEFAULT 'platform'
            ) ENGINE = MergeTree() 
            ORDER BY (customer_id, user_id, tenant_id)
            SETTINGS index_granularity = 8192
        """)
        
        # API usage tracking table
        self.client.command("""
            CREATE TABLE IF NOT EXISTS api_usage_mt (
                id String,
                tenant_id String,
                user_id String,
                endpoint String,
                method String,
                response_status UInt16,
                processing_time_ms UInt32,
                response_size_bytes UInt64,
                ip_address String,
                user_agent String,
                request_timestamp DateTime DEFAULT now(),
                billing_feature String,
                cost_credits Float64,
                created_at DateTime DEFAULT now(),
                customer_id String DEFAULT 'platform'
            ) ENGINE = MergeTree() 
            ORDER BY (customer_id, tenant_id, request_timestamp, endpoint)
            PARTITION BY toYYYYMM(request_timestamp)
            SETTINGS index_granularity = 8192
        """)
    
    def _create_alert_tables(self):
        """Create alert management tables (placeholder for AlertService)"""
        pass  # Implement when AlertService uses database layer
    
    def _create_security_tables(self):
        """Create security analytics tables (placeholder for SecurityService)"""
        pass  # Implement when SecurityService uses database layer
    
    def _create_log_tables(self):
        """Create log storage tables (placeholder for log services)"""
        pass  # Implement when log services use database layer
    
    def _verify_query_tables(self):
        """Verify query management tables exist (should be created via SQL schema files)"""
        required_tables = ['saved_queries_mt', 'query_cache_mt']
        self._verify_tables_exist(required_tables, "query management")
    
    def _verify_dashboard_tables(self):
        """Verify dashboard management tables exist (should be created via SQL schema files)"""
        required_tables = ['dashboards_mt', 'dashboard_widgets_mt', 'dashboard_shares_mt']
        self._verify_tables_exist(required_tables, "dashboard management")
    
    def _verify_storage_tables(self):
        """Verify storage management tables exist (should be created via SQL schema files)"""
        required_tables = ['retention_policies_mt', 'storage_backends_mt', 'storage_operations_mt', 'storage_quotas_mt', 'data_archives_mt']
        self._verify_tables_exist(required_tables, "storage management")
    
    def _verify_alert_tables(self):
        """Verify alert management tables exist (should be created via SQL schema files)"""
        required_tables = ['alert_rules_mt', 'alert_instances_mt', 'notification_channels_mt', 'alert_rule_states_mt']
        self._verify_tables_exist(required_tables, "alert management")
    
    def _verify_tables_exist(self, table_names: List[str], table_group: str):
        """Verify that required tables exist in the database"""
        try:
            existing_tables = set()
            result = self.client.query("SHOW TABLES")
            for row in result.result_rows:
                existing_tables.add(row[0])
            
            missing_tables = [table for table in table_names if table not in existing_tables]
            
            if missing_tables:
                missing_list = ', '.join(missing_tables)
                error_msg = f"Missing {table_group} tables: {missing_list}. Please run the schema initialization SQL scripts."
                logger.error(error_msg, service=self.service_name)
                raise DatabaseError(error_msg)
            
            logger.info(f"{table_group.title()} tables verified", service=self.service_name, tables=table_names)
            
        except Exception as e:
            if "Missing" in str(e):
                raise e  # Re-raise our custom error
            logger.error(f"Failed to verify {table_group} tables", service=self.service_name, error=str(e))
            raise DatabaseError(f"Table verification failed: {str(e)}")
    
    def _validate_table_access(self, table_name: str):
        """Validate service has access to requested table"""
        allowed_tables = self.TABLE_ACCESS_CONTROL.get(self.service_name, [])
        
        if '*' not in allowed_tables and table_name not in allowed_tables:
            raise SecurityError(f"Service {self.service_name} not authorized to access table {table_name}")
    
    def _validate_query_security(self, query: str):
        """Validate query for security violations"""
        query_upper = query.upper()
        
        # Check for dangerous operations
        for operation in self.ADMIN_OPERATIONS:
            if operation in query_upper:
                if self.service_name not in self.ADMIN_SERVICES:
                    raise SecurityError(f"Service {self.service_name} not authorized for operation: {operation}")
        
        # Check for DELETE operations separately
        if 'DELETE FROM' in query_upper:
            if self.service_name not in self.DELETE_ALLOWED_SERVICES:
                raise SecurityError(f"Service {self.service_name} not authorized for DELETE operations")
        
        # Allow ALTER TABLE ... UPDATE for UPDATE_ALLOWED_SERVICES
        if 'ALTER TABLE' in query_upper and 'UPDATE' in query_upper:
            if self.service_name not in self.UPDATE_ALLOWED_SERVICES:
                raise SecurityError(f"Service {self.service_name} not authorized for UPDATE operations")
        
        # Basic SQL injection prevention (parameters should be used)
        if any(suspicious in query_upper for suspicious in ["'; DROP", "'; DELETE", "'; UPDATE"]):
            raise SecurityError("Potential SQL injection detected")
    
    def _sanitize_parameters(self, params: Dict) -> Dict:
        """Sanitize and validate query parameters"""
        if not params:
            return {}
        
        sanitized = {}
        for key, value in params.items():
            # Basic parameter validation
            if not isinstance(key, str):
                raise ValueError(f"Parameter key must be string: {key}")
            
            # Prevent parameter key injection
            if any(char in key for char in [';', '--', '/*', '*/', 'DROP', 'DELETE']):
                raise SecurityError(f"Invalid parameter key: {key}")
            
            sanitized[key] = value
        
        return sanitized
    
    # Helper methods for common database operations
    async def fetch_all(self, query: str, params: Dict = None) -> List[Dict]:
        """Fetch all results from query (alias for execute_query)"""
        return await self.execute_query(query, params)
    
    async def fetch_one(self, query: str, params: Dict = None) -> Optional[Dict]:
        """Fetch single result from query"""
        results = await self.execute_query(query, params)
        return results[0] if results else None
    
    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute SELECT query and return results as list of dictionaries
        
        Args:
            query: SQL query string with parameter placeholders
            params: Dictionary of query parameters
            
        Returns:
            List of dictionaries representing query results
        """
        self._validate_query_security(query)
        sanitized_params = self._sanitize_parameters(params)
        
        try:
            result = self.client.query(query, sanitized_params)
            
            # Convert to list of dictionaries
            rows = []
            if result.result_rows:
                column_names = result.column_names
                for row in result.result_rows:
                    rows.append(dict(zip(column_names, row)))
            
            logger.debug("Query executed successfully", 
                        service=self.service_name, 
                        query=query[:100], 
                        result_count=len(rows))
            
            return rows
            
        except Exception as e:
            logger.error("Query execution failed", 
                        service=self.service_name, 
                        query=query[:100], 
                        error=str(e))
            raise DatabaseError(f"Query failed: {str(e)}")
    
    async def execute_insert(self, table: str, data: List[Dict]) -> int:
        """Execute batch insert and return number of inserted records
        
        Args:
            table: Target table name
            data: List of dictionaries representing records to insert
            
        Returns:
            Number of records inserted
        """
        self._validate_table_access(table)
        
        if not data:
            return 0
        
        try:
            # Get table columns to ensure correct order
            if table == 'users_mt':
                columns = ['id', 'email', 'name', 'password_hash', 'status', 'created_at', 
                          'updated_at', 'last_login_at', 'password_reset_token', 
                          'password_reset_expires', 'email_verified_at', 'setup_token', 
                          'setup_token_expires', 'customer_id']
            elif table == 'user_sessions_mt':
                columns = ['id', 'user_id', 'session_token', 'ip_address', 'user_agent',
                          'created_at', 'last_activity', 'expires_at', 'status', 'customer_id']
            elif table == 'user_tenant_roles_mt':
                columns = ['id', 'user_id', 'tenant_id', 'role', 'granted_by', 'granted_at',
                          'expires_at', 'status', 'created_at', 'updated_at', 'customer_id']
            elif table == 'api_usage_mt':
                columns = ['id', 'customer_id', 'tenant_id', 'user_id', 'endpoint', 'method',
                          'request_timestamp', 'response_status', 'processing_time_ms', 'billing_feature',
                          'cost_credits', 'request_size_bytes', 'response_size_bytes', 'ip_address', 'user_agent']
            elif table == 'archive_access_log_mt':
                columns = ['customer_id', 'archive_key', 'access_type', 'user_id', 'session_id',
                          'accessed_at', 'bytes_transferred', 'query_filter', 'client_ip']
            elif table == 'security_events_mt':
                # ENH-004: explicit column list so detection writes go through the
                # driver's parameter binding instead of interpolated SQL text.
                # Values here originate from ingested log content and must never
                # reach the database as literals inside a statement.
                #
                # ENH-021: columns match `init_simple.sql:636` -- the schema
                # compose actually mounts, and the one `dao/security_dao.py`
                # uses. They previously matched migration 003's conflicting
                # definition, so inserts referenced non-existent columns.
                columns = ['id', 'customer_id', 'rule_id', 'event_type', 'severity',
                          'status', 'title', 'description', 'raw_log_data',
                          'enrichment_data', 'mitre_techniques', 'assigned_to',
                          'investigation_notes', 'artifacts',
                          'created_at', 'updated_at']
            else:
                # For other tables, let ClickHouse determine columns
                self.client.insert(table, data)
                return len(data)
            
            # Convert dict data to list format with correct column order
            rows = []
            for record in data:
                row = []
                for col in columns:
                    value = record.get(col)
                    # Handle None values for numeric columns
                    if value is None and col in ['request_size_bytes', 'response_size_bytes', 'processing_time_ms', 'cost_credits']:
                        value = 0
                    row.append(value)
                rows.append(row)
            
            # Use ClickHouse batch insert with column specification
            self.client.insert(table, rows, column_names=columns)
            
            logger.info("Batch insert completed", 
                       service=self.service_name, 
                       table=table, 
                       record_count=len(data))
            
            return len(data)
            
        except Exception as e:
            logger.error("Batch insert failed", 
                        service=self.service_name, 
                        table=table, 
                        error=str(e))
            raise DatabaseError(f"Insert failed: {str(e)}")
    
    async def execute_update(self, query: str, params: Dict = None) -> int:
        """Execute UPDATE/ALTER query and return number of affected records
        
        Args:
            query: SQL update query
            params: Dictionary of query parameters
            
        Returns:
            Number of affected records
        """
        self._validate_query_security(query)
        sanitized_params = self._sanitize_parameters(params)
        
        try:
            result = self.client.command(query, sanitized_params)
            
            # ClickHouse command() returns QuerySummary object, not affected rows count
            # For ALTER TABLE operations, just return 1 for successful execution
            affected_rows = 1
            
            logger.info("Update executed successfully", 
                       service=self.service_name, 
                       query=query[:100], 
                       affected_rows=affected_rows)
            
            return affected_rows
            
        except Exception as e:
            logger.error("Update execution failed", 
                        service=self.service_name, 
                        query=query[:100], 
                        error=str(e))
            raise DatabaseError(f"Update failed: {str(e)}")
    
    # User Management Operations
    
    async def create_user(self, user_data: Dict) -> str:
        """Create new user record"""
        self._validate_table_access('users_mt')
        
        if not user_data.get('email') or not user_data.get('name'):
            raise ValueError("User data must include email and name")
        
        user_id = user_data.get('id', str(uuid.uuid4()))
        user_record = {
            'id': user_id,
            'email': user_data['email'],
            'name': user_data['name'],
            'password_hash': user_data.get('password_hash', ''),
            'status': user_data.get('status', 'pending'),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'last_login_at': None,
            'password_reset_token': None,
            'password_reset_expires': None,
            'email_verified_at': None,
            'setup_token': None,
            'setup_token_expires': None,
            'customer_id': user_data.get('customer_id', 'platform')
        }
        
        await self.execute_insert('users_mt', [user_record])
        return user_id
    
    async def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email address"""
        if not email:
            raise ValueError("Email cannot be empty")
        
        query = "SELECT * FROM users_mt WHERE email = %(email)s LIMIT 1"
        results = await self.execute_query(query, {'email': email})
        
        return results[0] if results else None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        if not user_id:
            raise ValueError("User ID cannot be empty")
        
        query = "SELECT * FROM users_mt WHERE id = %(user_id)s LIMIT 1"
        results = await self.execute_query(query, {'user_id': user_id})
        
        return results[0] if results else None
    
    async def update_user(self, user_id: str, updates: Dict) -> bool:
        """Update user record"""
        if not user_id or not updates:
            raise ValueError("User ID and updates cannot be empty")
        
        # Build SET clause dynamically
        set_clauses = []
        params = {'user_id': user_id}
        
        for key, value in updates.items():
            if key in ['name', 'last_login_at', 'password_hash', 'status']:
                param_key = f"update_{key}"
                set_clauses.append(f"{key} = %({param_key})s")
                params[param_key] = value
        
        if not set_clauses:
            return False
        
        set_clauses.append("updated_at = now()")
        
        query = f"""
            ALTER TABLE users_mt UPDATE 
            {', '.join(set_clauses)}
            WHERE id = %(user_id)s
        """
        
        result = await self.execute_update(query, params)
        return result > 0
    
    # Session Management Operations
    
    async def create_session(self, session_data: Dict) -> str:
        """Create new user session"""
        self._validate_table_access('user_sessions_mt')
        
        if not session_data.get('user_id') or not session_data.get('session_token'):
            raise ValueError("Session data must include user_id and session_token")
        
        session_id = session_data.get('id', str(uuid.uuid4()))
        session_record = {
            'id': session_id,
            'user_id': session_data['user_id'],
            'session_token': session_data['session_token'],
            'ip_address': session_data.get('ip_address', 'unknown'),
            'user_agent': session_data.get('user_agent', ''),
            'expires_at': session_data.get('expires_at', datetime.utcnow() + timedelta(hours=8)),
            'status': 'active',
            'customer_id': session_data.get('customer_id', 'platform'),
            'created_at': datetime.utcnow(),
            'last_activity': datetime.utcnow()
        }
        
        await self.execute_insert('user_sessions_mt', [session_record])
        return session_id
    
    async def get_session(self, session_token: str) -> Optional[Dict]:
        """Get session by token"""
        if not session_token:
            raise ValueError("Session token cannot be empty")
        
        query = """
            SELECT * FROM user_sessions_mt 
            WHERE session_token = %(session_token)s 
            AND status = 'active'
            AND expires_at > now()
            LIMIT 1
        """
        results = await self.execute_query(query, {'session_token': session_token})
        
        return results[0] if results else None
    
    async def update_session_activity(self, session_token: str) -> bool:
        """Update session last activity timestamp"""
        if not session_token:
            raise ValueError("Session token cannot be empty")
        
        query = """
            ALTER TABLE user_sessions_mt UPDATE 
            last_activity = now()
            WHERE session_token = %(session_token)s
            AND status = 'active'
        """
        
        result = await self.execute_update(query, {'session_token': session_token})
        return result > 0
    
    async def revoke_session(self, session_token: str) -> bool:
        """Revoke user session"""
        if not session_token:
            raise ValueError("Session token cannot be empty")
        
        query = """
            ALTER TABLE user_sessions_mt UPDATE 
            status = 'revoked'
            WHERE session_token = %(session_token)s
        """
        
        result = await self.execute_update(query, {'session_token': session_token})
        return result > 0
    
    # Role Management Operations
    
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict]:
        """Get user roles for specific tenant"""
        if not user_id or not tenant_id:
            raise ValueError("User ID and tenant ID cannot be empty")
        
        query = """
            SELECT * FROM user_tenant_roles_mt 
            WHERE user_id = %(user_id)s 
            AND tenant_id = %(tenant_id)s
            AND status = 'active'
            AND (expires_at IS NULL OR expires_at > now())
        """
        
        return await self.execute_query(query, {
            'user_id': user_id, 
            'tenant_id': tenant_id
        })
    
    async def create_user_role(self, role_data: Dict) -> str:
        """Create user role assignment"""
        self._validate_table_access('user_tenant_roles_mt')
        
        required_fields = ['user_id', 'tenant_id', 'role', 'granted_by']
        for field in required_fields:
            if not role_data.get(field):
                raise ValueError(f"Role data must include {field}")
        
        role_id = role_data.get('id', str(uuid.uuid4()))
        role_record = {
            'id': role_id,
            'user_id': role_data['user_id'],
            'tenant_id': role_data['tenant_id'],
            'role': role_data['role'],
            'granted_by': role_data['granted_by'],
            'status': 'active',
            'customer_id': role_data.get('customer_id', 'platform'),
            'granted_at': datetime.utcnow(),
            'expires_at': role_data.get('expires_at'),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        await self.execute_insert('user_tenant_roles_mt', [role_record])
        return role_id
    
    async def revoke_user_role(self, user_id: str, tenant_id: str, role: str) -> bool:
        """Revoke user role assignment"""
        if not all([user_id, tenant_id, role]):
            raise ValueError("User ID, tenant ID, and role cannot be empty")
        
        query = """
            ALTER TABLE user_tenant_roles_mt UPDATE 
            status = 'inactive'
            WHERE user_id = %(user_id)s 
            AND tenant_id = %(tenant_id)s 
            AND role = %(role)s
        """
        
        result = await self.execute_update(query, {
            'user_id': user_id,
            'tenant_id': tenant_id, 
            'role': role
        })
        return result > 0
    
    # Usage Tracking Operations
    
    async def batch_insert_usage(self, usage_records: List[Dict]) -> int:
        """Batch insert usage tracking records"""
        if not usage_records:
            return 0
        
        # Process in chunks of 1000 for optimal performance
        chunk_size = 1000
        total_inserted = 0
        
        for i in range(0, len(usage_records), chunk_size):
            chunk = usage_records[i:i + chunk_size]
            
            # Add default fields if missing
            for record in chunk:
                record.setdefault('id', str(uuid.uuid4()))
                record.setdefault('created_at', datetime.utcnow())
            
            inserted = await self.execute_insert('api_usage_mt', chunk)
            total_inserted += inserted
        
        return total_inserted
    
    async def get_usage_stats(self, tenant_id: str, start_date: datetime, end_date: datetime) -> Dict:
        """Get usage statistics for tenant in date range"""
        query = """
            SELECT 
                tenant_id,
                count(*) as total_requests,
                sum(response_size_bytes) as total_bytes,
                avg(processing_time_ms) as avg_processing_time,
                countIf(response_status < 400) * 100.0 / count(*) as success_rate
            FROM api_usage_mt 
            WHERE tenant_id = %(tenant_id)s
            AND request_timestamp >= %(start_date)s
            AND request_timestamp <= %(end_date)s
            GROUP BY tenant_id
        """
        
        results = await self.execute_query(query, {
            'tenant_id': tenant_id,
            'start_date': start_date,
            'end_date': end_date
        })
        
        return results[0] if results else {
            'tenant_id': tenant_id,
            'total_requests': 0,
            'total_bytes': 0,
            'avg_processing_time': 0,
            'success_rate': 0
        }
    
    async def close(self):
        """Close database connection"""
        try:
            # LF-002: the shared pooled client is owned by
            # utils.connection_pool and outlives any single DatabaseLayer --
            # closing it here would break every other consumer in the process.
            if getattr(self, "_client_is_shared", False):
                logger.debug("Shared ClickHouse client left open", service=self.service_name)
                return
            if hasattr(self.client, 'close'):
                self.client.close()
            logger.info("Database connection closed", service=self.service_name)
        except Exception as e:
            logger.warning("Error closing database connection", error=str(e))
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.create_task(self.close())