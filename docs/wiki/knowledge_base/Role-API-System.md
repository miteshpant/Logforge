# Role API System Documentation

## Overview

The Role API System provides comprehensive role-based access control (RBAC) for the Logforge platform. This system manages user role assignments, permission validation, tenant-based access control, and role analytics with complete multi-tenant isolation. It serves as the foundation for M8 User Service & Authentication functionality.

## Architecture

### Core Components
- **Role Router** (`/apps/api/routers/role_api.py`): 13 endpoints for complete role management operations
- **Role Service** (`/apps/api/services/role_service.py`): Business logic and permission validation
- **Role DAO** (`/apps/api/dao/role_dao.py`): Database access layer with multi-tenant isolation
- **Authentication Middleware**: JWT-based authentication with role-based access control

### Key Features
- **Role Assignment Management**: Complete CRUD operations for user role assignments
- **Permission Validation**: Real-time permission checking and access control
- **Multi-Tenant Isolation**: Complete tenant data separation and role scoping
- **Bulk Operations**: Platform admin bulk role assignment capabilities
- **Role Analytics**: Usage analytics and role distribution reporting
- **Cross-Tenant Protection**: Robust security controls preventing unauthorized access
- **Effective Permissions**: Consolidated permission calculation across multiple roles

## Supported Roles & Permissions

### Platform Roles (Global Scope)
- **super_admin**: Full platform access, can manage all tenants and users
- **admin**: Platform administrative access with some restrictions
- **support_admin**: Customer support access for troubleshooting
- **billing_admin**: Billing and subscription management access

### Tenant Roles (Tenant-Scoped)
- **tenant_admin**: Full tenant management, can manage all users within tenant
- **security_analyst**: Security monitoring, SIEM access, incident response
- **devops_engineer**: Infrastructure monitoring, alerts, performance analytics
- **compliance_officer**: Compliance reporting, audit access, data governance
- **viewer**: Read-only access to logs and dashboards

### Permission Structure
Permissions follow the format: `resource:action:scope`
- **resource**: logs, dashboards, alerts, users, settings, etc.
- **action**: read, write, create, update, delete, manage
- **scope**: tenant, platform, global

## API Endpoints

### 1. Role Assignment Management

#### POST /v1/users/{user_id}/roles
**Purpose**: Assign role to user for specific tenant

**Authentication**: Bearer token + X-Customer-ID header
**Authorization**: Requires permission to assign the specified role

**Request Body**:
```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "security_analyst"
}
```

**Response** (201 Created):
```json
{
  "id": "role-assignment-uuid",
  "user_id": "user-uuid",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "security_analyst",
  "granted_by": "admin-user-uuid",
  "granted_at": "2024-01-01T12:00:00Z",
  "expires_at": null,
  "status": "active"
}
```

**Validation Rules**:
- Target user must exist
- Granting user must have permission to assign the specified role
- Role must be valid for the tenant scope (platform vs tenant roles)
- Cannot assign platform roles without platform admin privileges

#### GET /v1/users/{user_id}/roles
**Purpose**: Retrieve user's role assignments with optional tenant filtering

**Query Parameters**:
- `tenant_id`: Filter roles for specific tenant (optional)

**Authorization**:
- Users can view their own roles
- Platform admins can view any user's roles
- Tenant admins can view roles within their tenant

**Response**:
```json
{
  "user_id": "user-uuid",
  "roles": [
    {
      "id": "role-assignment-uuid-1",
      "user_id": "user-uuid",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "tenant_admin",
      "granted_by": "platform-admin-uuid",
      "granted_at": "2024-01-01T10:00:00Z",
      "expires_at": null,
      "status": "active"
    },
    {
      "id": "role-assignment-uuid-2",
      "user_id": "user-uuid",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "security_analyst",
      "granted_by": "tenant-admin-uuid",
      "granted_at": "2024-01-01T14:00:00Z",
      "expires_at": null,
      "status": "active"
    }
  ]
}
```

#### DELETE /v1/users/{user_id}/roles/{role_id}
**Purpose**: Remove role assignment from user

**Authorization**: Requires permission to remove the specified role

**Response**:
```json
{
  "message": "Role removed successfully"
}
```

**Security Controls**:
- Validates that role assignment exists and belongs to specified user
- Checks permission to remove the specific role from the tenant
- Prevents removal of last admin role to avoid tenant lockout

### 2. Role Information & Discovery

#### GET /v1/roles
**Purpose**: List available roles and their assignability based on current user permissions

**Response**:
```json
{
  "roles": [
    {
      "role": "tenant_admin",
      "name": "Tenant Admin",
      "permissions": [
        "users:manage:tenant",
        "logs:read:tenant",
        "dashboards:manage:tenant",
        "alerts:manage:tenant"
      ],
      "scope": "tenant",
      "assignable": true
    },
    {
      "role": "security_analyst",
      "name": "Security Analyst",
      "permissions": [
        "logs:read:tenant",
        "security:read:tenant",
        "security:analyze:tenant",
        "incidents:manage:tenant"
      ],
      "scope": "tenant",
      "assignable": true
    },
    {
      "role": "super_admin",
      "name": "Super Admin",
      "permissions": [
        "platform:manage:global",
        "tenants:manage:global",
        "users:manage:global"
      ],
      "scope": "platform",
      "assignable": false
    }
  ]
}
```

**Access Control**:
- **Platform Admins**: See all roles, can assign all roles
- **Tenant Admins**: See all roles, can only assign tenant-scoped roles
- **Regular Users**: See all roles for reference, cannot assign any roles

#### GET /v1/roles/{role}/permissions
**Purpose**: Get detailed permissions for specific role

**Response**:
```json
{
  "role": "security_analyst",
  "permissions": [
    "logs:read:tenant",
    "security:read:tenant", 
    "security:analyze:tenant",
    "incidents:manage:tenant",
    "dashboards:read:tenant",
    "alerts:read:tenant"
  ],
  "permission_count": 6,
  "scope": "tenant"
}
```

### 3. Tenant User Management

#### GET /v1/tenants/{tenant_id}/users
**Purpose**: List all users assigned to specific tenant with their roles

**Query Parameters**:
- `role`: Filter users by specific role (optional)

**Authorization**: Platform admins or tenant admins for the specified tenant

**Response**:
```json
[
  {
    "user_id": "user-uuid-1",
    "email": "admin@company.com",
    "name": "John Admin",
    "status": "active",
    "role": "tenant_admin",
    "granted_at": "2024-01-01T10:00:00Z",
    "granted_by": "platform-admin-uuid"
  },
  {
    "user_id": "user-uuid-2", 
    "email": "analyst@company.com",
    "name": "Jane Analyst",
    "status": "active",
    "role": "security_analyst",
    "granted_at": "2024-01-01T11:30:00Z",
    "granted_by": "admin@company.com"
  }
]
```

#### POST /v1/tenants/{tenant_id}/users/{user_id}/roles
**Purpose**: Alternative endpoint for tenant-specific role assignment

**Query Parameters**:
- `role`: Role to assign (required)

**Response**: Same as `/v1/users/{user_id}/roles` endpoint

**Usage**: Provides tenant-centric API for role management workflows

### 4. Permission Validation

#### POST /v1/check-permission
**Purpose**: Check if current user has specific permission

**Request Body**:
```json
{
  "resource": "logs",
  "action": "read", 
  "scope": "tenant",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**:
```json
{
  "user_id": "user-uuid",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "permission": "logs:read:tenant",
  "granted": true,
  "roles": [
    {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "security_analyst",
      "status": "active"
    }
  ]
}
```

**Use Cases**:
- Frontend UI permission-based feature toggling
- API endpoint access validation
- Audit logging for permission checks
- Real-time access control verification

#### GET /v1/permissions/map
**Purpose**: Get complete permission mapping for all roles

**Response**:
```json
{
  "roles": {
    "tenant_admin": {
      "name": "Tenant Admin",
      "permissions": [
        "users:manage:tenant",
        "logs:read:tenant",
        "dashboards:manage:tenant"
      ],
      "scope": "tenant",
      "description": "Role for tenant admin"
    },
    "security_analyst": {
      "name": "Security Analyst", 
      "permissions": [
        "logs:read:tenant",
        "security:read:tenant",
        "security:analyze:tenant"
      ],
      "scope": "tenant",
      "description": "Role for security analyst"
    }
  },
  "total_roles": 8
}
```

### 5. Advanced Features

#### POST /v1/validate-access
**Purpose**: Validate if user can access specific API endpoint

**Query Parameters**:
- `endpoint`: API endpoint path (required)
- `method`: HTTP method (default: GET)
- `tenant_id`: Tenant context (optional, uses X-Customer-ID header if not provided)

**Response**:
```json
{
  "user_id": "user-uuid",
  "endpoint": "/v1/logs/search",
  "method": "POST", 
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "required_permission": "logs:read:tenant",
  "access_granted": true,
  "user_roles": [
    {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "security_analyst",
      "status": "active"
    }
  ],
  "validation_timestamp": "2024-01-01T15:30:00Z"
}
```

**Integration Points**:
- API Gateway access control
- Frontend routing permissions
- Audit trail generation
- Access pattern analysis

#### GET /v1/users/{user_id}/effective-permissions
**Purpose**: Calculate consolidated permissions across all user roles

**Authorization**: Self-access or platform admin required

**Response**:
```json
{
  "user_id": "user-uuid",
  "tenant_filter": null,
  "effective_permissions": [
    "logs:read:tenant",
    "dashboards:read:tenant",
    "dashboards:manage:tenant",
    "alerts:read:tenant",
    "security:read:tenant",
    "security:analyze:tenant",
    "users:read:tenant"
  ],
  "role_breakdown": {
    "550e8400-e29b-41d4-a716-446655440000:tenant_admin": [
      "users:manage:tenant",
      "dashboards:manage:tenant",
      "logs:read:tenant"
    ],
    "550e8400-e29b-41d4-a716-446655440000:security_analyst": [
      "security:read:tenant",
      "security:analyze:tenant",
      "logs:read:tenant"
    ]
  },
  "total_permissions": 7,
  "calculated_at": "2024-01-01T16:00:00Z"
}
```

### 6. Analytics & Reporting

#### GET /v1/roles/analytics
**Purpose**: Get role usage analytics and distribution metrics

**Authorization**: Platform admins or tenant admins for their tenant

**Response**:
```json
{
  "role_distribution": {
    "tenant_admin": {
      "count": 45,
      "percentage": 15.2
    },
    "security_analyst": {
      "count": 123,
      "percentage": 41.6
    },
    "devops_engineer": {
      "count": 67,
      "percentage": 22.7
    },
    "viewer": {
      "count": 61,
      "percentage": 20.5
    }
  },
  "total_assignments": 296,
  "tenant_breakdown": {
    "enterprise_tenants": 12,
    "professional_tenants": 28,
    "starter_tenants": 45
  },
  "growth_metrics": {
    "new_assignments_this_month": 23,
    "removed_assignments_this_month": 4,
    "net_growth": 19
  },
  "generated_at": "2024-01-01T17:00:00Z"
}
```

### 7. Bulk Operations

#### POST /v1/users/bulk-assign-roles
**Purpose**: Bulk assign roles to multiple users (platform admins only)

**Authentication**: Requires platform admin privileges

**Request Body**:
```json
[
  {
    "user_id": "user-uuid-1",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "role": "security_analyst"
  },
  {
    "user_id": "user-uuid-2",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000", 
    "role": "devops_engineer"
  }
]
```

**Response**:
```json
{
  "successful_assignments": 2,
  "errors": [],
  "assignments": [
    {
      "id": "role-assignment-uuid-1",
      "user_id": "user-uuid-1",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "security_analyst"
    },
    {
      "id": "role-assignment-uuid-2", 
      "user_id": "user-uuid-2",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "devops_engineer"
    }
  ]
}
```

**Limits**:
- Maximum 100 assignments per bulk operation
- Each assignment is validated independently
- Partial success supported (some assignments may fail while others succeed)

## Multi-Tenancy & Security

### Data Isolation
- **Role Scoping**: Platform roles vs tenant-specific roles with clear boundaries
- **Cross-Tenant Protection**: Middleware prevents access to other tenant's role data
- **Audit Trails**: Complete role assignment/removal logging per tenant
- **Permission Inheritance**: Platform roles can access tenant data with proper controls

### Authentication & Authorization
- **Bearer Token Required**: JWT-based authentication for all endpoints
- **X-Customer-ID Header**: Mandatory tenant context header
- **Role-Based Access**: Permission validation based on user's assigned roles
- **Permission Checking**: Real-time permission validation for all operations

### Security Controls
- **Self-Access Rules**: Users can view their own roles without admin privileges
- **Admin Scope Validation**: Platform admins vs tenant admin permission boundaries
- **Role Assignment Validation**: Cannot assign roles without proper permissions
- **Last Admin Protection**: Prevents removal of last admin role from tenant

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid role assignment: missing required field 'tenant_id'"
}
```

#### 403 Forbidden - Insufficient Permissions
```json
{
  "detail": "No permission to assign security_analyst to tenant 550e8400-e29b-41d4-a716-446655440000"
}
```

#### 403 Forbidden - Cross-Tenant Access
```json
{
  "detail": "No permission to view user roles"
}
```

#### 404 Not Found - User
```json
{
  "detail": "User user-uuid not found"
}
```

#### 404 Not Found - Role Assignment
```json
{
  "detail": "Role assignment role-uuid not found for user user-uuid"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "role"],
      "msg": "Invalid role: invalid_role_name",
      "type": "value_error"
    }
  ]
}
```

#### 500 Server Error
```json
{
  "detail": "Role assignment failed: database connection timeout"
}
```

## Permission Matrix

### Platform Roles Permissions

| **Permission** | **super_admin** | **admin** | **support_admin** | **billing_admin** |
|----------------|-----------------|-----------|-------------------|-------------------|
| `platform:manage:global` | ✅ | ✅ | ❌ | ❌ |
| `tenants:manage:global` | ✅ | ✅ | ❌ | ❌ |
| `users:manage:global` | ✅ | ✅ | ❌ | ❌ |
| `billing:manage:global` | ✅ | ✅ | ❌ | ✅ |
| `support:access:global` | ✅ | ✅ | ✅ | ❌ |
| `logs:read:global` | ✅ | ✅ | ✅ | ❌ |

### Tenant Roles Permissions

| **Permission** | **tenant_admin** | **security_analyst** | **devops_engineer** | **compliance_officer** | **viewer** |
|----------------|------------------|---------------------|-------------------|----------------------|-----------|
| `users:manage:tenant` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `logs:read:tenant` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `logs:write:tenant` | ✅ | ❌ | ✅ | ❌ | ❌ |
| `dashboards:manage:tenant` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `dashboards:read:tenant` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `alerts:manage:tenant` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `alerts:read:tenant` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `security:analyze:tenant` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `security:read:tenant` | ✅ | ✅ | ❌ | ✅ | ❌ |
| `compliance:manage:tenant` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `compliance:read:tenant` | ✅ | ✅ | ❌ | ✅ | ❌ |

## Integration Examples

### Role Assignment Workflow
```python
import httpx
import json

async def assign_security_analyst_role():
    headers = {
        "Authorization": "Bearer your-jwt-token",
        "X-Customer-ID": "550e8400-e29b-41d4-a716-446655440000",
        "Content-Type": "application/json"
    }
    
    # Assign role to user
    assignment_request = {
        "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
        "role": "security_analyst"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.logforge.com/v1/users/target-user-id/roles",
            headers=headers,
            json=assignment_request
        )
        
        if response.status_code == 201:
            assignment = response.json()
            print(f"Role assigned: {assignment['id']}")
            return assignment
        else:
            print(f"Assignment failed: {response.text}")
            return None
```

### Permission Validation
```python
async def check_user_permission():
    permission_request = {
        "resource": "security",
        "action": "analyze", 
        "scope": "tenant"
    }
    
    response = await client.post(
        "https://api.logforge.com/v1/check-permission",
        headers=headers,
        json=permission_request
    )
    
    if response.status_code == 200:
        result = response.json()
        if result["granted"]:
            print("Permission granted - user can analyze security data")
            return True
        else:
            print("Permission denied - user cannot analyze security data") 
            return False
    else:
        print(f"Permission check failed: {response.text}")
        return False
```

### Bulk Role Assignment
```python
async def bulk_assign_roles():
    # Requires platform admin privileges
    bulk_assignments = [
        {
            "user_id": "analyst-1-uuid",
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "security_analyst"
        },
        {
            "user_id": "engineer-1-uuid", 
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "devops_engineer"
        },
        {
            "user_id": "viewer-1-uuid",
            "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
            "role": "viewer"
        }
    ]
    
    response = await client.post(
        "https://api.logforge.com/v1/users/bulk-assign-roles",
        headers=platform_admin_headers,
        json=bulk_assignments
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Successfully assigned {result['successful_assignments']} roles")
        if result['errors']:
            print(f"Errors: {result['errors']}")
        return result
```

### Effective Permissions Analysis
```python
async def analyze_user_permissions(user_id):
    response = await client.get(
        f"https://api.logforge.com/v1/users/{user_id}/effective-permissions",
        headers=headers
    )
    
    if response.status_code == 200:
        permissions_data = response.json()
        
        print(f"User {user_id} has {permissions_data['total_permissions']} effective permissions:")
        
        for permission in permissions_data['effective_permissions']:
            print(f"  - {permission}")
            
        print("\nRole breakdown:")
        for role_key, role_permissions in permissions_data['role_breakdown'].items():
            tenant_id, role = role_key.split(':', 1)
            print(f"  {role} ({tenant_id}): {len(role_permissions)} permissions")
            
        return permissions_data
```

## Best Practices

### Role Management
1. **Principle of Least Privilege**: Assign minimum required roles for user function
2. **Role Lifecycle Management**: Regular review and cleanup of unused role assignments
3. **Temporary Access**: Use role expiration for temporary access grants
4. **Documentation**: Maintain clear role definitions and permission mappings
5. **Audit Trail**: Monitor all role assignments and changes for security compliance

### Multi-Tenant Considerations
1. **Tenant Isolation**: Never assign cross-tenant roles without explicit authorization
2. **Admin Role Protection**: Ensure each tenant maintains at least one admin user
3. **Platform vs Tenant Roles**: Clearly separate platform administration from tenant management
4. **Permission Validation**: Always validate permissions in real-time rather than caching
5. **Cross-Tenant Access**: Use platform roles only when legitimate cross-tenant access is required

### Security Considerations
1. **Authentication First**: Always validate Bearer token before role operations
2. **Permission Checking**: Validate permissions for every role management operation
3. **Audit Logging**: Log all role assignments, removals, and permission checks
4. **Session Management**: Invalidate sessions when user roles change significantly
5. **Regular Reviews**: Periodic access reviews and role assignment audits

### API Integration
1. **Error Handling**: Implement comprehensive error handling for all role operations
2. **Retry Logic**: Handle transient failures with exponential backoff
3. **Bulk Operations**: Use bulk endpoints for multiple role assignments to improve performance
4. **Real-Time Validation**: Use permission checking endpoints for dynamic UI features
5. **Analytics Integration**: Monitor role usage patterns for security and optimization insights

## Integration with Other Systems

### Authentication Middleware Integration
- **Request Validation**: Every API request validated against user's effective permissions
- **Role Context**: Current user's roles injected into request state for downstream services
- **Permission Enforcement**: Automatic permission checking based on endpoint requirements
- **Session Management**: Role changes trigger session updates and cache invalidation

### Audit System Integration
- **Role Change Logging**: All role assignments/removals logged to audit system
- **Permission Check Logging**: High-value permission checks logged for security monitoring
- **Access Pattern Analysis**: Role usage patterns analyzed for anomaly detection
- **Compliance Reporting**: Role-based access reports generated for compliance audits

### Tenant Management Integration
- **Tenant Creation**: New tenants automatically get default admin role assignments
- **Tenant Deletion**: Role cleanup handled during tenant deactivation process
- **Tenant Analytics**: Role distribution metrics integrated with tenant analytics
- **Cross-Tenant Operations**: Platform admin roles enable legitimate cross-tenant management

This comprehensive Role API system provides enterprise-grade role-based access control with complete multi-tenant isolation, enabling secure and scalable user management for the Logforge platform.