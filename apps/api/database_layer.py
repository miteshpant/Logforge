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
        'AlertService': os.getenv('ALERT_SERVICE_KEY', 'alert-service-key-dev'),
        'SecurityService': os.getenv('SECURITY_SERVICE_KEY', 'security-service-key-dev'),
        'IngestionService': os.getenv('INGESTION_SERVICE_KEY', 'ingestion-service-key-dev'),
        'QueryService': os.getenv('QUERY_SERVICE_KEY', 'query-service-key-dev'),
        'StorageService': os.getenv('STORAGE_SERVICE_KEY', 'storage-service-key-dev'),
        'TestService': 'test-service-key'  # For testing only
    }
    
    # Table access control by service
    TABLE_ACCESS_CONTROL = {
        'UserService': ['users_mt', 'user_sessions_mt', 'user_tenant_roles_mt', 'api_usage_mt'],
        'AlertService': ['alert_rules_mt', 'alert_events_mt', 'alert_notifications_mt'],
        'SecurityService': ['security_events_mt', 'sigma_rules_mt', 'threat_intel_mt'],
        'IngestionService': ['logs_raw_mt', 'logs_normalized_mt', 'ingestion_stats_mt'],
        'QueryService': ['logs_normalized_mt', 'query_cache_mt'],
        'StorageService': ['logs_raw_mt', 'logs_normalized_mt', 'storage_metadata_mt'],
        'TestService': ['*']  # Test service can access all tables
    }
    
    # Dangerous operations requiring admin privileges
    ADMIN_OPERATIONS = ['DROP', 'TRUNCATE', 'DELETE FROM', 'CREATE TABLE']
    ADMIN_SERVICES = ['TestService']  # Services allowed to perform admin operations
    
    # Services allowed to perform UPDATE operations (ALTER TABLE ... UPDATE)
    UPDATE_ALLOWED_SERVICES = ['UserService', 'AlertService', 'SecurityService', 'TestService']
    
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
        
        # Initialize ClickHouse client
        try:
            self.client = clickhouse_connect.get_client(
                host=os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
                port=int(os.getenv('CLICKHOUSE_PORT', '8123')),
                username=os.getenv('CLICKHOUSE_USER', 'logforge'),
                password=os.getenv('CLICKHOUSE_PASSWORD', 'logforge123'),
                database=os.getenv('CLICKHOUSE_DATABASE', 'logforge')
            )
            logger.info("ClickHouse client initialized", service=service_name)
        except Exception as e:
            logger.error("Failed to initialize ClickHouse client", service=service_name, error=str(e))
            raise DatabaseError(f"Database connection failed: {str(e)}")
        
        # Ensure required tables exist
        self._ensure_tables_exist()
    
    def _validate_service_credentials(self, service_name: str, service_key: str) -> bool:
        """Validate service authentication credentials"""
        expected_key = self.AUTHORIZED_SERVICES.get(service_name)
        if not expected_key or expected_key != service_key:
            logger.warning("Invalid service credentials", service=service_name)
            return False
        return True
    
    def _ensure_tables_exist(self):
        """Create required tables if they don't exist"""
        try:
            # User management tables
            if self.service_name == 'UserService':
                self._create_user_tables()
            
            # Alert management tables
            elif self.service_name == 'AlertService':
                self._create_alert_tables()
            
            # Security analytics tables
            elif self.service_name == 'SecurityService':
                self._create_security_tables()
            
            # Ingestion and query tables (created by respective services)
            elif self.service_name in ['IngestionService', 'QueryService', 'StorageService']:
                self._create_log_tables()
            
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
                status_code UInt16,
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
                          'expires_at', 'status', 'customer_id']
            elif table == 'api_usage_mt':
                columns = ['id', 'tenant_id', 'user_id', 'endpoint', 'method', 'status_code',
                          'processing_time_ms', 'response_size_bytes', 'ip_address', 'user_agent',
                          'request_timestamp', 'billing_feature', 'cost_credits', 'created_at', 'customer_id']
            else:
                # For other tables, let ClickHouse determine columns
                self.client.insert(table, data)
                return len(data)
            
            # Convert dict data to list format with correct column order
            rows = []
            for record in data:
                row = [record.get(col) for col in columns]
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
            'expires_at': role_data.get('expires_at')
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
                countIf(status_code < 400) * 100.0 / count(*) as success_rate
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
            if hasattr(self.client, 'close'):
                self.client.close()
            logger.info("Database connection closed", service=self.service_name)
        except Exception as e:
            logger.warning("Error closing database connection", error=str(e))
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.create_task(self.close())