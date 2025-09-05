# Database Layer Architecture - Logforge Platform

**Version**: 1.0  
**Status**: 🚧 Implementation  
**Last Updated**: 2025-09-05

## Overview

The Logforge Database Layer provides a centralized, secure, and performant abstraction over ClickHouse operations. This layer separates data access concerns from business logic, ensuring consistent database interactions across all platform services.

## Architecture Principles

### **1. Separation of Concerns**
- **Business Logic**: Handled in service layers (UserService, AlertService, etc.)
- **Data Access**: Centralized in DatabaseLayer class
- **Query Optimization**: Managed within database layer
- **Connection Management**: Pooled connections with retry logic

### **2. Security First**
- **Internal Service Only**: Database layer accessible only to internal Logforge services
- **Parameter Sanitization**: All queries use parameterized statements
- **SQL Injection Protection**: No string concatenation in queries
- **Access Control**: Service-level authentication required

### **3. Performance & Reliability**
- **Connection Pooling**: Reuse database connections efficiently
- **Query Caching**: Cache frequently accessed data
- **Retry Logic**: Automatic retry for transient failures
- **Batch Operations**: Support for bulk inserts and updates

## Database Layer Interface

```python
from typing import Dict, List, Optional, Any
from datetime import datetime
import clickhouse_connect

class DatabaseLayer:
    """Centralized database abstraction layer for ClickHouse operations"""
    
    def __init__(self):
        """Initialize with environment-based configuration"""
        
    # Core Query Operations
    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]
    async def execute_insert(self, table: str, data: List[Dict]) -> int
    async def execute_update(self, query: str, params: Dict = None) -> int
    
    # User Management
    async def get_user_by_email(self, email: str) -> Optional[Dict]
    async def get_user_by_id(self, user_id: str) -> Optional[Dict]
    async def create_user(self, user_data: Dict) -> str
    async def update_user(self, user_id: str, updates: Dict) -> bool
    
    # Session Management  
    async def create_session(self, session_data: Dict) -> str
    async def get_session(self, session_token: str) -> Optional[Dict]
    async def update_session_activity(self, session_token: str) -> bool
    async def revoke_session(self, session_token: str) -> bool
    
    # Role Management
    async def get_user_tenant_roles(self, user_id: str, tenant_id: str) -> List[Dict]
    async def create_user_role(self, role_data: Dict) -> str
    async def revoke_user_role(self, user_id: str, tenant_id: str, role: str) -> bool
    
    # Usage Tracking
    async def batch_insert_usage(self, usage_records: List[Dict]) -> int
    async def get_usage_stats(self, tenant_id: str, start_date: datetime, end_date: datetime) -> Dict
```

## Database Schema

### **Users Table (users_mt)**
```sql
CREATE TABLE users_mt (
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
SETTINGS index_granularity = 8192;
```

### **User Sessions Table (user_sessions_mt)**
```sql
CREATE TABLE user_sessions_mt (
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
SETTINGS index_granularity = 8192;
```

### **User Tenant Roles Table (user_tenant_roles_mt)**
```sql
CREATE TABLE user_tenant_roles_mt (
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
SETTINGS index_granularity = 8192;
```

## Security Model

### **Internal Service Authentication**
```python
class DatabaseLayer:
    def __init__(self, service_name: str, service_key: str):
        """Require service authentication"""
        if not self._validate_service_credentials(service_name, service_key):
            raise UnauthorizedError("Invalid service credentials")
```

### **Query Parameter Validation**
```python
async def execute_query(self, query: str, params: Dict = None):
    """All parameters are validated and escaped"""
    validated_params = self._validate_parameters(params)
    sanitized_query = self._sanitize_query(query, validated_params)
    return await self._execute_safe_query(sanitized_query)
```

### **Table Access Control**
```python
ALLOWED_TABLES = {
    'UserService': ['users_mt', 'user_sessions_mt', 'user_tenant_roles_mt'],
    'AlertService': ['alert_rules_mt', 'alert_events_mt'],
    'SecurityService': ['security_events_mt', 'sigma_rules_mt'],
    'IngestionService': ['logs_raw_mt', 'logs_normalized_mt']
}
```

## Error Handling

### **Connection Failures**
```python
@retry(max_attempts=3, backoff_seconds=[1, 2, 4])
async def _execute_with_retry(self, operation):
    """Automatic retry for transient failures"""
    try:
        return await operation()
    except ClickHouseConnectionError as e:
        logger.warning("Database connection failed, retrying...", error=str(e))
        raise
```

### **Query Validation**
```python
def _validate_query(self, query: str, service_name: str):
    """Validate query is safe and authorized for service"""
    if any(dangerous in query.upper() for dangerous in ['DROP', 'TRUNCATE', 'DELETE FROM']):
        if service_name not in ADMIN_SERVICES:
            raise SecurityError("Destructive operations not allowed")
```

## Performance Optimization

### **Connection Pooling**
```python
class DatabaseLayer:
    def __init__(self):
        self.connection_pool = ClickHousePool(
            max_connections=20,
            idle_timeout=300,
            connection_timeout=10
        )
```

### **Query Caching**
```python
@lru_cache(maxsize=1000, ttl=300)  # 5 minute TTL
async def get_user_by_id(self, user_id: str):
    """Cache frequently accessed user data"""
    return await self._query_user_by_id(user_id)
```

### **Batch Operations**
```python
async def batch_insert_usage(self, usage_records: List[Dict]):
    """Efficient bulk insert for usage tracking"""
    if len(usage_records) > 1000:
        # Process in chunks
        for chunk in self._chunk_records(usage_records, 1000):
            await self._insert_chunk(chunk)
```

## Usage Examples

### **User Authentication Flow**
```python
# UserService using DatabaseLayer
class UserService:
    def __init__(self):
        self.db = DatabaseLayer('UserService', os.getenv('USER_SERVICE_KEY'))
    
    async def authenticate_user(self, email: str, password: str):
        user = await self.db.get_user_by_email(email)
        if user and verify_password(password, user['password_hash']):
            session_data = {
                'user_id': user['id'],
                'session_token': generate_jwt_token(user['id'])['access_token'],
                'ip_address': request.client.host,
                'user_agent': request.headers.get('user-agent'),
                'expires_at': datetime.utcnow() + timedelta(hours=8)
            }
            session_id = await self.db.create_session(session_data)
            return session_data
        return None
```

### **Usage Tracking**
```python
# Usage tracking with batch insert
usage_buffer = []

async def track_api_usage(usage_data):
    usage_buffer.append(usage_data)
    if len(usage_buffer) >= 100:
        await db.batch_insert_usage(usage_buffer)
        usage_buffer.clear()
```

## Testing Strategy

### **Unit Tests**
- Mock ClickHouse client for service logic testing
- Test parameter validation and sanitization
- Verify error handling and retry logic

### **Integration Tests**
- Test with real ClickHouse instance
- Validate multi-tenant data isolation
- Performance benchmarks for query operations

### **Security Tests**
- SQL injection prevention
- Service authentication verification
- Unauthorized table access attempts

## Migration & Rollout Plan

### **Phase 1: Core Implementation**
1. Implement DatabaseLayer with user management operations
2. Create comprehensive test suite
3. Update UserService to use DatabaseLayer

### **Phase 2: Service Integration**  
1. Migrate AlertService, SecurityService to use DatabaseLayer
2. Add usage tracking batch operations
3. Performance optimization and caching

### **Phase 3: Production Readiness**
1. Connection pooling and retry logic
2. Monitoring and alerting integration
3. Backup and recovery procedures

## Monitoring & Observability

### **Metrics**
- Query execution times
- Connection pool utilization
- Error rates by service
- Cache hit/miss ratios

### **Logging**
- All database operations logged with service context
- Query performance metrics
- Security events and access violations

### **Alerts**
- Database connection failures
- Query performance degradation
- Unauthorized access attempts

## Configuration

### **Environment Variables**
```bash
# ClickHouse Configuration
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=logforge
CLICKHOUSE_PASSWORD=logforge123
CLICKHOUSE_DATABASE=logforge

# Service Authentication
USER_SERVICE_KEY=secure-user-service-key
ALERT_SERVICE_KEY=secure-alert-service-key
SECURITY_SERVICE_KEY=secure-security-service-key

# Performance Tuning
DB_CONNECTION_POOL_SIZE=20
DB_QUERY_TIMEOUT=30
DB_CACHE_TTL=300
```

This database layer architecture ensures scalable, secure, and maintainable data access across the Logforge platform while maintaining high performance and reliability standards.