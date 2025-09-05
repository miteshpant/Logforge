# M8 - User Service & Authentication Foundation
**Duration**: 2 weeks  
**Status**: 🚧 Planning  

## Overview
Implement the foundational user management service that powers both platform administration and customer tenant access. This service provides core authentication, user lifecycle management, role-based access control, and secure onboarding flows that M7 Enterprise features will build upon.

## Scope & Features

### **Core User Management**
- **Unified User Table**: Single table for platform admins and customer users
- **User CRUD Operations**: Create, read, update, delete user accounts
- **Authentication System**: Login, logout, session management, password policies
- **Account Lifecycle**: User activation, deactivation, password reset flows

### **Role-Based Tenant Access**
- **User-Tenant-Role Mapping**: Users can access multiple tenants with different roles
- **Platform Admin Roles**: Super Admin, Admin, Support Admin, Billing Admin
- **Customer User Roles**: Tenant Admin, Security Analyst, DevOps Engineer, Compliance Officer, Viewer
- **Permission Inheritance**: Role-based permission assignment and validation

### **Secure Onboarding Flows**
- **Platform Admin Setup**: Secure initial admin creation without hardcoded credentials
- **Customer Tenant Onboarding**: Email-based invitation system for new tenants
- **User Invitation System**: Tenant admins can invite users with role assignment
- **Self-Service Registration**: Optional customer signup with approval workflow

### **Authentication Middleware**
- **Request Validation**: Verify user authentication and tenant access
- **Header Processing**: Extract and validate X-Customer-ID and user context
- **Permission Enforcement**: Check user permissions against requested resources
- **Audit Logging**: Log all authentication and authorization events
- **API Usage Tracking**: Record every API call for billing and analytics
- **Real-time Metering**: Track usage patterns for cost attribution

## Database Schema (ClickHouse)

### **Users Table**
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
    tenant_id String DEFAULT 'platform' -- Multi-tenant support
) ENGINE = MergeTree() 
ORDER BY (tenant_id, id)
SETTINGS index_granularity = 8192;
```

### **User Tenant Roles Table**
```sql
CREATE TABLE user_tenant_roles_mt (
    id String,
    user_id String,
    tenant_id String, -- 'platform' for admin users
    role String,
    granted_by String, -- User ID who granted this access
    granted_at DateTime DEFAULT now(),
    expires_at Nullable(DateTime),
    status Enum8('active'=1, 'inactive'=2, 'expired'=3),
    customer_id String DEFAULT 'platform' -- Multi-tenant support
) ENGINE = MergeTree() 
ORDER BY (customer_id, user_id, tenant_id)
SETTINGS index_granularity = 8192;
```

### **Sessions Table**
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
    customer_id String DEFAULT 'platform' -- Multi-tenant support
) ENGINE = MergeTree() 
ORDER BY (customer_id, user_id, session_token)
SETTINGS index_granularity = 8192;
```

### **API Usage Audit Table (Monthly Partitioned)**
```sql
-- Monthly partitioned table for billing and analytics
CREATE TABLE api_usage_audit (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid()),
    tenant_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method ENUM('GET', 'POST', 'PUT', 'DELETE', 'PATCH') NOT NULL,
    status_code INT NOT NULL,
    response_size_bytes BIGINT DEFAULT 0,
    processing_time_ms INT DEFAULT 0,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT NOT NULL,
    request_timestamp DATETIME NOT NULL DEFAULT NOW(),
    billing_feature VARCHAR(100) NOT NULL, -- ingestion.basic, queries.advanced, etc.
    cost_credits DECIMAL(10,4) DEFAULT 0.0000,
    INDEX idx_tenant_timestamp (tenant_id, request_timestamp),
    INDEX idx_billing_feature (billing_feature, request_timestamp),
    INDEX idx_user_timestamp (user_id, request_timestamp)
) PARTITION BY RANGE (YEAR(request_timestamp) * 100 + MONTH(request_timestamp)) (
    PARTITION p202401 VALUES LESS THAN (202402),
    PARTITION p202402 VALUES LESS THAN (202403),
    -- Auto-created monthly partitions
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

## Role Definitions & Permissions

### **Platform Admin Roles**

#### 1. **Super Admin** (`super_admin`)
- **Scope**: Platform-wide control
- **Permissions**: 
  - `platform:*:*` - All platform operations
  - `tenants:*:*` - Complete tenant management
  - `users:*:*` - All user management
  - `billing:*:*` - Financial operations
  - `system:*:*` - System administration

#### 2. **Admin** (`admin`)
- **Scope**: Operational management
- **Permissions**:
  - `tenants:read,write,create:platform`
  - `usage:read:platform` 
  - `billing:read,generate:platform`
  - `users:read:platform`

#### 3. **Support Admin** (`support_admin`)
- **Scope**: Customer support
- **Permissions**:
  - `support:*:platform`
  - `users:read,write:platform`
  - `tenants:read:platform`
  - `audit:read:platform`

#### 4. **Billing Admin** (`billing_admin`)
- **Scope**: Financial operations
- **Permissions**:
  - `billing:*:platform`
  - `usage:read:platform`
  - `reports:generate:platform`
  - `tenants:read:platform`

### **Customer User Roles**

#### 1. **Tenant Admin** (`tenant_admin`)
- **Scope**: Full tenant control
- **Permissions**:
  - `logs:*:tenant`
  - `alerts:*:tenant`
  - `dashboards:*:tenant`
  - `security:*:tenant`
  - `users:*:tenant`
  - `settings:*:tenant`

#### 2. **Security Analyst** (`security_analyst`)
- **Scope**: Security operations
- **Permissions**:
  - `security:*:tenant`
  - `logs:read,search:tenant`
  - `alerts:read,investigate:tenant`
  - `compliance:read:tenant`
  - `threat_hunting:*:tenant`

#### 3. **DevOps Engineer** (`devops_engineer`)
- **Scope**: Infrastructure monitoring
- **Permissions**:
  - `logs:read,search:tenant`
  - `alerts:*:tenant`
  - `dashboards:*:tenant`
  - `observability:*:tenant`
  - `integrations:*:tenant`

#### 4. **Compliance Officer** (`compliance_officer`)
- **Scope**: Compliance and audit
- **Permissions**:
  - `compliance:*:tenant`
  - `audit:read:tenant`
  - `reports:generate:tenant`
  - `legal_hold:*:tenant`
  - `logs:read:tenant`

#### 5. **Viewer** (`viewer`)
- **Scope**: Read-only access
- **Permissions**:
  - `logs:read:tenant`
  - `dashboards:read:tenant`
  - `alerts:read:own`
  - `reports:read:tenant`

## API Endpoints

### **User Management APIs**

#### User CRUD Operations
```yaml
GET    /v1/users                    # List users (filtered by current user's scope)
POST   /v1/users                    # Create new user
GET    /v1/users/{id}              # Get user details
PUT    /v1/users/{id}              # Update user
DELETE /v1/users/{id}              # Delete user
```

#### Admin User Management (Platform)
```yaml
GET    /v1/admin/users             # List platform admin users
POST   /v1/admin/users             # Create platform admin user
PUT    /v1/admin/users/{id}        # Update admin user
DELETE /v1/admin/users/{id}        # Delete admin user
```

#### Authentication APIs
```yaml
POST   /v1/auth/login              # User login
POST   /v1/auth/logout             # User logout
POST   /v1/auth/refresh            # Refresh session
GET    /v1/auth/me                 # Current user profile
POST   /v1/auth/setup              # Initial platform setup
POST   /v1/auth/password/reset     # Password reset request
POST   /v1/auth/password/change    # Change password
POST   /v1/auth/invite             # Send user invitation
POST   /v1/auth/accept-invite      # Accept invitation and create account
```

#### Role Management APIs
```yaml
GET    /v1/users/{id}/roles        # Get user's roles across tenants
POST   /v1/users/{id}/roles        # Assign role to user for tenant
DELETE /v1/users/{id}/roles/{role_id} # Remove role assignment
GET    /v1/roles                   # List available roles
POST   /v1/roles                   # Create custom role (tenant admins only)
```

## User Onboarding Flows

### **1. Platform Admin Setup (First Time)**
```yaml
Flow:
  1. System generates setup token on first startup
  2. Admin visits /setup?token=xyz
  3. Admin creates account (name, email, password)
  4. System assigns super_admin role to platform tenant
  5. Setup token expires
  
Security:
  - Setup token: 256-bit random, expires in 24 hours
  - No default credentials stored
  - Audit log of initial setup
```

### **2. Customer Tenant Onboarding**
```yaml
Flow:
  1. Platform admin creates tenant via Admin UI
  2. System sends invitation email to tenant admin
  3. Tenant admin clicks link, creates account
  4. System assigns tenant_admin role to new tenant
  5. Tenant admin can invite additional users
  
Email Template:
  Subject: "Welcome to Logforge - Complete Your Account Setup"
  Link: https://app.logforge.com/invite?token=xyz&tenant=abc-001
```

### **3. Customer User Invitation**
```yaml
Flow:
  1. Tenant admin invites user via Customer UI
  2. System sends invitation email with role information
  3. User clicks link, creates account
  4. System assigns specified role to tenant
  5. User gains immediate access based on role
  
Role Selection:
  - Tenant Admin, Security Analyst, DevOps Engineer, Compliance Officer, Viewer
  - Multiple role assignment supported
```

## Authentication Middleware Architecture

### **Request Processing Flow**
```python
class AuthenticationMiddleware:
    async def __call__(self, request):
        # 1. Extract authentication (session token, API key, etc.)
        auth_context = await self.extract_auth(request)
        
        # 2. Validate user exists and is active
        user = await self.validate_user(auth_context)
        
        # 3. Extract requested tenant from X-Customer-ID header
        tenant_id = request.headers.get("X-Customer-ID")
        
        # 4. Verify user has access to requested tenant
        user_roles = await self.get_user_tenant_roles(user.id, tenant_id)
        
        # 5. Check permissions for requested endpoint
        required_permission = self.get_endpoint_permission(request.path, request.method)
        
        # 6. Authorize request
        if not self.has_permission(user_roles, required_permission):
            raise HTTPException(403, "Insufficient permissions")
        
        # 7. Add user context to request
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.roles = user_roles
```

## Security Considerations

### **Password Security**
- **Hashing**: bcrypt with 12 rounds minimum
- **Policy**: Minimum 12 characters, complexity requirements
- **Reset Flow**: Secure token-based reset with expiration
- **Setup Tokens**: High-entropy tokens with short expiration

### **Session Management**
- **Token Format**: JWT or secure random tokens
- **Expiration**: Configurable (default 8 hours)
- **Refresh**: Automatic refresh with activity
- **Revocation**: Immediate logout capability

### **Audit Requirements**
- **Login Events**: Success/failure with IP, user-agent
- **Permission Changes**: Role assignments, removals
- **Administrative Actions**: User creation, tenant access grants
- **Security Events**: Failed login attempts, suspicious activity

## Implementation Plan

### **Phase 1: Core Infrastructure (Week 1)**
- Database schema creation and migration
- Basic user CRUD operations
- Authentication middleware foundation
- Session management system

### **Phase 2: Role & Permission System (Week 1)**
- Role definition and assignment APIs
- Permission validation middleware
- User-tenant-role mapping logic
- Admin user management APIs

### **Phase 3: Onboarding Flows (Week 2)**
- Secure platform admin setup
- Customer tenant invitation system
- User invitation and acceptance flows
- Email templates and notifications

### **Phase 4: API Usage Tracking & Billing (Week 2)**
- Monthly partitioned audit table implementation
- Usage tracking middleware integration
- Billing feature mapping and cost calculation
- Real-time usage analytics APIs

### **Phase 5: Integration & Testing (Week 2)**
- Integration with existing tenant service
- Comprehensive test suite
- Performance optimization
- Security validation

## API Usage Tracking & Billing Integration

### **Billing Feature Mapping**
```yaml
# Map API endpoints to billable features
Billing Features:
  ingestion.basic:        # $0.10 per 1M events
    - POST /v1/ingestion/json
    - POST /v1/ingestion/syslog
    - POST /v1/ingestion/otlp
  
  queries.advanced:       # $0.05 per 1K queries
    - POST /v1/query/advanced
    - GET /v1/logs/search
  
  security.analytics:     # $0.50 per 1K security queries
    - GET /v1/security/*
    - POST /v1/security/threat-hunting
  
  alerts.management:      # $0.20 per 1K alert operations
    - POST /v1/alerts/rules
    - GET /v1/alerts/events
  
  storage.retrieval:      # $0.02 per GB retrieved
    - GET /v1/storage/export
    - GET /v1/query/* (with data size tracking)
```

### **Enhanced Middleware Flow (Async Usage Tracking)**
```python
import asyncio
import time
from typing import List, Dict

class UsageBuffer:
    """Batched usage tracking for zero-latency API calls"""
    def __init__(self):
        self.buffer: List[Dict] = []
        self.batch_size = 100
        self.flush_interval = 30  # seconds
        
    async def add_usage(self, usage_data: Dict):
        """Add usage data to buffer, flush when batch size reached"""
        self.buffer.append(usage_data)
        
        if len(self.buffer) >= self.batch_size:
            await self.flush_batch()
    
    async def flush_batch(self):
        """Batch insert to database with retry logic"""
        if not self.buffer:
            return
            
        try:
            await self.insert_usage_batch(self.buffer)
            self.buffer.clear()
        except Exception as e:
            # Retry logic for failed writes
            logger.error(f"Usage tracking batch failed: {e}")
            # Could implement retry queue here

class UsageTrackingMiddleware:
    def __init__(self):
        self.usage_buffer = UsageBuffer()
        
    async def __call__(self, request):
        start_time = time.time()
        
        # Process request through auth middleware (normal flow)
        response = await self.call_next(request)
        
        # Async usage tracking (zero latency impact)
        if hasattr(request.state, 'tenant_id') and request.state.tenant_id != 'platform':
            # Fire-and-forget usage recording
            asyncio.create_task(
                self.usage_buffer.add_usage({
                    'tenant_id': request.state.tenant_id,
                    'user_id': request.state.user.id,
                    'endpoint': request.url.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'processing_time_ms': int((time.time() - start_time) * 1000),
                    'response_size_bytes': len(response.body) if hasattr(response, 'body') else 0,
                    'ip_address': request.client.host,
                    'user_agent': request.headers.get('user-agent', ''),
                    'billing_feature': self.map_endpoint_to_feature(request.url.path),
                    'cost_credits': self.calculate_cost(request.url.path, response.status_code)
                })
            )
        
        return response  # Immediate return to user
        
    def calculate_cost(self, endpoint: str, status_code: int) -> float:
        """Calculate cost based on endpoint and response status"""
        base_cost = self.get_endpoint_base_cost(endpoint)
        
        # Billing policy for failed requests
        if 500 <= status_code < 600:
            return 0.0  # No charge for server errors
        elif status_code in [401, 403]:
            return base_cost * 0.1  # Minimal charge for auth processing
        elif 400 <= status_code < 500:
            return base_cost * 0.5  # Partial charge for client errors  
        else:
            return base_cost  # Full charge for successful requests
```

### **Failed Request Billing Policy**
```yaml
Billing Rules by Status Code:
  2xx (Success):        Full charge - request completed successfully
  400 (Bad Request):    50% charge - consumed parsing/validation resources
  401 (Unauthorized):   10% charge - authentication processing only
  403 (Forbidden):      10% charge - auth + permission check
  404 (Not Found):      50% charge - full request processing
  429 (Rate Limited):   0% charge - protective throttling, no customer fault
  5xx (Server Error):   0% charge - platform issue, customer not at fault
  
Cost Calculation Examples:
  - POST /v1/ingestion/json → 200 OK → $0.0001 (full charge)
  - POST /v1/ingestion/json → 400 Bad Request → $0.00005 (50% charge)  
  - GET /v1/security/events → 401 Unauthorized → $0.00001 (10% charge)
  - POST /v1/query/advanced → 500 Error → $0.0000 (no charge)
```

### **Performance Optimization**
```yaml
Usage Tracking Performance:
  - Latency Impact: 0ms (async fire-and-forget)
  - Batch Size: 100 records per database insert
  - Flush Interval: 30 seconds max buffer time
  - Memory Usage: ~10KB per 100 records in buffer
  - Database Load: Reduced by 100x through batching
  
Expected Throughput:
  - 10,000 API calls/minute → 100 batch inserts/minute
  - Memory buffer: ~1MB max during high traffic
  - Database writes: 1,440 batch operations/day vs 14,400,000 individual inserts
```

### **Real-time Usage APIs**
```yaml
GET    /v1/usage/current/{tenant_id}     # Current month usage
GET    /v1/usage/history/{tenant_id}     # Historical usage patterns  
GET    /v1/billing/estimate/{tenant_id}  # Current month bill estimate
POST   /v1/billing/generate/{tenant_id}  # Generate monthly invoice
GET    /v1/analytics/usage-trends        # Platform-wide usage analytics (admin only)
```

## Success Criteria
- ✅ Unified user management for platform and customer users
- ✅ Role-based access control with tenant isolation
- ✅ Secure onboarding flows without hardcoded credentials
- ✅ Authentication middleware protecting all endpoints
- ✅ **Real-time API usage tracking for accurate billing**
- ✅ **Monthly partitioned audit tables for performance**
- ✅ 95%+ test coverage for user management operations
- ✅ Sub-100ms authentication middleware performance
- ✅ Complete audit trail for all user operations

## Integration with M7
M7 Enterprise features will consume User Service APIs:
- **OIDC Integration** → Maps external users to internal user records
- **RBAC Policies** → Uses role definitions from User Service
- **Compliance Audit** → Queries User Service audit logs
- **Multi-Tenant Management** → Uses User Service tenant access controls

## Files to Create/Modify
- `/apps/api/user_service.py` - Core user management logic
- `/apps/api/user_api.py` - FastAPI user management endpoints  
- `/apps/api/auth_middleware.py` - Authentication and authorization middleware
- `/apps/api/models.py` - User, role, and session models (extend existing)
- `/apps/api/auth_api.py` - Authentication endpoints (login, logout, setup)
- `/tests/test_m8_individual.py` - M8 comprehensive test suite
- Database migration scripts for user tables

This foundation enables rapid go-live while supporting enterprise scalability through M7 features.