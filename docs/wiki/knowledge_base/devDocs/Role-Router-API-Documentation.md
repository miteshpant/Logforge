# Role Router API Documentation

## Overview

The Role Router provides comprehensive Role-Based Access Control (RBAC) management with user role assignments, permissions, and multi-tenant security. This router enables enterprise-grade access control with platform and tenant-level role hierarchies, permission validation, and role analytics.

## Architecture

```
Request → Role Router → Role Service → Role DAO → ClickHouse
                    ↓
            Authentication Middleware → Permission Validation
```

**Core Components:**
- **Router**: `/apps/api/routers/role_api.py` - FastAPI endpoints for role management
- **Service**: `/apps/api/services/role_service.py` - Business logic for role operations
- **DAO**: `/apps/api/dao/role_dao.py` - Database operations for role assignments
- **Middleware**: `/apps/api/authn_authz_middleware.py` - Authentication and permission validation
- **Database**: Multi-tenant ClickHouse tables (`user_tenant_roles_mt`)

## Role Hierarchy

### Platform Roles
- **`super_admin`**: Full platform administration (all permissions)
- **`admin`**: Platform administration (limited super admin permissions)
- **`support_admin`**: Platform support operations
- **`billing_admin`**: Platform billing and subscription management

### Tenant Roles  
- **`tenant_admin`**: Full tenant administration (can assign customer roles)
- **`security_analyst`**: Security operations and analysis
- **`devops_engineer`**: Infrastructure and operations management
- **`compliance_officer`**: Compliance reporting and audit access
- **`viewer`**: Read-only access to tenant data

## API Endpoints

### Role Assignment Operations

#### 1. Assign User Role
**Endpoint**: `POST /v1/users/{user_id}/roles`

Assign role to user for specific tenant with permission validation.

**Headers:**
- `Authorization`: Bearer token
- `X-Customer-ID`: Customer identifier

**Path Parameters:**
- `user_id`: Target user identifier

**Request Body:**
```json
{
  "tenant_id": "tenant_123",
  "role": "security_analyst"
}
```

**Response:**
```json
{
  "id": "role_assignment_456",
  "user_id": "user_123",
  "tenant_id": "tenant_123", 
  "role": "security_analyst",
  "granted_by": "admin_user_789",
  "granted_at": "2024-01-15T10:30:00Z",
  "expires_at": null,
  "status": "active"
}
```

**Permission Requirements:**
- **Platform Admins**: Can assign any role to any tenant
- **Tenant Admins**: Can assign customer roles (`security_analyst`, `devops_engineer`, `compliance_officer`, `viewer`) to their tenant only

#### 2. Get User Roles
**Endpoint**: `GET /v1/users/{user_id}/roles`

Retrieve user's role assignments with optional tenant filtering.

**Query Parameters:**
- `tenant_id`: Filter by specific tenant (optional)

**Response:**
```json
{
  "user_id": "user_123",
  "roles": [
    {
      "id": "role_assignment_456",
      "user_id": "user_123",
      "tenant_id": "tenant_123",
      "role": "security_analyst",
      "granted_by": "admin_user_789",
      "granted_at": "2024-01-15T10:30:00Z",
      "expires_at": null,
      "status": "active"
    },
    {
      "id": "role_assignment_789",
      "user_id": "user_123", 
      "tenant_id": "platform",
      "role": "admin",
      "granted_by": "super_admin_001",
      "granted_at": "2024-01-10T09:00:00Z",
      "expires_at": null,
      "status": "active"
    }
  ]
}
```

**Access Control:**
- **Self Access**: Users can view their own roles
- **Platform Admins**: Can view any user's roles across all tenants
- **Tenant Admins**: Can view roles for users in their tenant only

#### 3. Remove User Role
**Endpoint**: `DELETE /v1/users/{user_id}/roles/{role_id}`

Remove role assignment from user with permission validation.

**Path Parameters:**
- `user_id`: Target user identifier
- `role_id`: Role assignment identifier

**Response:**
```json
{
  "message": "Role removed successfully"
}
```

**Permission Requirements:**
- Same permissions as role assignment (platform admins or tenant admins for their scope)

### Role Information & Discovery

#### 4. List Available Roles
**Endpoint**: `GET /v1/roles`

List available roles and their permissions based on current user's scope.

**Response:**
```json
{
  "roles": [
    {
      "role": "security_analyst",
      "name": "Security Analyst", 
      "permissions": [
        "logs:read:*",
        "alerts:*:*",
        "security:*:*",
        "dashboards:read:*"
      ],
      "scope": "tenant",
      "assignable": true
    },
    {
      "role": "devops_engineer",
      "name": "Devops Engineer",
      "permissions": [
        "logs:*:*",
        "metrics:*:*", 
        "infrastructure:*:*",
        "dashboards:*:*"
      ],
      "scope": "tenant",
      "assignable": true
    },
    {
      "role": "super_admin",
      "name": "Super Admin",
      "permissions": ["*:*:*"],
      "scope": "platform",
      "assignable": false
    }
  ]
}
```

**Scope-Based Filtering:**
- **Platform Admins**: See all roles, can assign all roles
- **Tenant Admins**: See all roles, can assign customer roles only
- **Regular Users**: See all roles, cannot assign any roles

#### 5. Get Role Permissions
**Endpoint**: `GET /v1/roles/{role}/permissions`

Get detailed permissions for a specific role.

**Path Parameters:**
- `role`: Role name (e.g., `security_analyst`, `tenant_admin`)

**Response:**
```json
{
  "role": "security_analyst",
  "permissions": [
    "logs:read:*",
    "alerts:create:*",
    "alerts:read:*", 
    "alerts:update:*",
    "alerts:delete:*",
    "security:create:*",
    "security:read:*",
    "security:update:*",
    "security:delete:*",
    "dashboards:read:*"
  ],
  "permission_count": 9,
  "scope": "tenant"
}
```

### Tenant User Management

#### 6. List Tenant Users
**Endpoint**: `GET /v1/tenants/{tenant_id}/users`

List all users for a specific tenant with their roles.

**Path Parameters:**
- `tenant_id`: Tenant identifier

**Query Parameters:**
- `role`: Filter by specific role (optional)

**Response:**
```json
[
  {
    "user_id": "user_123",
    "email": "analyst@company.com",
    "name": "Security Analyst",
    "status": "active",
    "role": "security_analyst",
    "granted_at": "2024-01-15T10:30:00Z",
    "granted_by": "admin_user_789"
  },
  {
    "user_id": "user_456",
    "email": "engineer@company.com", 
    "name": "DevOps Engineer",
    "status": "active",
    "role": "devops_engineer",
    "granted_at": "2024-01-12T14:20:00Z",
    "granted_by": "admin_user_789"
  }
]
```

**Permission Requirements:**
- **Platform Admins**: Can list users for any tenant
- **Tenant Admins**: Can list users for their tenant only

#### 7. Assign Tenant Role (Alternative)
**Endpoint**: `POST /v1/tenants/{tenant_id}/users/{user_id}/roles`

Alternative endpoint for assigning roles with tenant context.

**Request Body:**
```json
{
  "role": "compliance_officer"
}
```

**Response:**
```json
{
  "id": "role_assignment_789",
  "user_id": "user_456",
  "tenant_id": "tenant_123",
  "role": "compliance_officer",
  "granted_by": "admin_user_789",
  "granted_at": "2024-01-15T10:30:00Z",
  "expires_at": null,
  "status": "active"
}
```

### Permission Validation

#### 8. Check User Permission
**Endpoint**: `POST /v1/check-permission`

Check if current user has specific permission for resource and action.

**Request Body:**
```json
{
  "resource": "alerts",
  "action": "create",
  "scope": "*",
  "tenant_id": "tenant_123"
}
```

**Response:**
```json
{
  "user_id": "user_123",
  "tenant_id": "tenant_123",
  "permission": "alerts:create:*",
  "granted": true,
  "roles": [
    {
      "tenant_id": "tenant_123",
      "role": "security_analyst",
      "status": "active"
    }
  ]
}
```

#### 9. Get Permission Map
**Endpoint**: `GET /v1/permissions/map`

Get complete permission mapping for all roles.

**Response:**
```json
{
  "roles": {
    "super_admin": {
      "name": "Super Admin",
      "permissions": ["*:*:*"],
      "scope": "platform",
      "description": "Role for super admin"
    },
    "security_analyst": {
      "name": "Security Analyst", 
      "permissions": [
        "logs:read:*",
        "alerts:*:*",
        "security:*:*",
        "dashboards:read:*"
      ],
      "scope": "tenant",
      "description": "Role for security analyst"
    }
  },
  "total_roles": 8
}
```

### Analytics & Reporting

#### 10. Get Role Analytics
**Endpoint**: `GET /v1/roles/analytics`

Get role usage analytics and distribution.

**Query Parameters:**
- `tenant_id`: Filter by specific tenant (optional)

**Response:**
```json
{
  "tenant_id": "tenant_123",
  "role_distribution": {
    "security_analyst": 15,
    "devops_engineer": 8,
    "compliance_officer": 4,
    "viewer": 25,
    "tenant_admin": 2
  },
  "tenant_breakdown": null,
  "total_assignments": 54,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

**Platform-Wide Analytics (Platform Admins):**
```json
{
  "tenant_id": null,
  "role_distribution": {
    "super_admin": 2,
    "admin": 5,
    "security_analyst": 45,
    "devops_engineer": 32,
    "tenant_admin": 12
  },
  "tenant_breakdown": {
    "platform": {
      "super_admin": 2,
      "admin": 5
    },
    "tenant_123": {
      "security_analyst": 15,
      "tenant_admin": 2
    }
  },
  "total_assignments": 96,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

### Bulk Operations

#### 11. Bulk Assign Roles
**Endpoint**: `POST /v1/users/bulk-assign-roles`

Bulk assign roles to multiple users (platform admins only).

**Request Body:**
```json
[
  {
    "user_id": "user_123",
    "tenant_id": "tenant_123", 
    "role": "security_analyst"
  },
  {
    "user_id": "user_456",
    "tenant_id": "tenant_123",
    "role": "devops_engineer"
  },
  {
    "user_id": "user_789",
    "tenant_id": "tenant_456",
    "role": "compliance_officer"
  }
]
```

**Response:**
```json
{
  "successful_assignments": 3,
  "errors": [],
  "assignments": [
    {
      "id": "role_assignment_001",
      "user_id": "user_123",
      "tenant_id": "tenant_123",
      "role": "security_analyst"
    },
    {
      "id": "role_assignment_002", 
      "user_id": "user_456",
      "tenant_id": "tenant_123",
      "role": "devops_engineer"
    },
    {
      "id": "role_assignment_003",
      "user_id": "user_789",
      "tenant_id": "tenant_456",
      "role": "compliance_officer"
    }
  ]
}
```

**Limitations:**
- Maximum 100 assignments per request
- Platform admins only
- All users must exist

### Access Validation & Debugging

#### 12. Validate User Access
**Endpoint**: `POST /v1/validate-access`

Validate if user can access specific endpoint.

**Request Body:**
```json
{
  "endpoint": "/v1/alerts",
  "method": "POST",
  "tenant_id": "tenant_123"
}
```

**Response:**
```json
{
  "user_id": "user_123",
  "endpoint": "/v1/alerts",
  "method": "POST",
  "tenant_id": "tenant_123",
  "required_permission": "alerts:create:*",
  "access_granted": true,
  "user_roles": [
    {
      "tenant_id": "tenant_123",
      "role": "security_analyst",
      "status": "active"
    }
  ],
  "validation_timestamp": "2024-01-15T10:30:00Z"
}
```

#### 13. Get User Effective Permissions
**Endpoint**: `GET /v1/users/{user_id}/effective-permissions`

Get user's effective permissions across all roles.

**Query Parameters:**
- `tenant_id`: Filter by specific tenant (optional)

**Response:**
```json
{
  "user_id": "user_123",
  "tenant_filter": "tenant_123",
  "effective_permissions": [
    "alerts:create:*",
    "alerts:delete:*", 
    "alerts:read:*",
    "alerts:update:*",
    "dashboards:read:*",
    "logs:read:*",
    "security:create:*",
    "security:delete:*",
    "security:read:*",
    "security:update:*"
  ],
  "role_breakdown": {
    "tenant_123:security_analyst": [
      "logs:read:*",
      "alerts:*:*",
      "security:*:*",
      "dashboards:read:*"
    ]
  },
  "total_permissions": 10,
  "calculated_at": "2024-01-15T10:30:00Z"
}
```

## Permission Format

### Permission Structure
Permissions follow the format: `resource:action:scope`

**Resources:**
- `*`: All resources
- `logs`: Log data and queries
- `alerts`: Alert rules and notifications
- `security`: Security analytics and events
- `dashboards`: Dashboard management
- `users`: User management
- `tenants`: Tenant administration
- `metrics`: Performance metrics
- `infrastructure`: System infrastructure

**Actions:**
- `*`: All actions
- `create`: Create new resources
- `read`: View/read resources
- `update`: Modify existing resources
- `delete`: Remove resources

**Scopes:**
- `*`: All scopes
- `own`: Own resources only
- `tenant`: Tenant-scoped resources
- `platform`: Platform-wide resources

### Example Permissions
```
*:*:*                    # Super admin - all permissions
logs:read:*              # Read all logs
alerts:*:tenant          # All alert actions within tenant
security:create:own      # Create own security resources only
dashboards:read:*        # Read all dashboards
users:update:tenant      # Update users within tenant
```

## Role Permission Matrix

| Role | Logs | Alerts | Security | Dashboards | Users | Tenants | Metrics |
|------|------|--------|----------|------------|-------|---------|---------|
| **super_admin** | `*:*:*` | `*:*:*` | `*:*:*` | `*:*:*` | `*:*:*` | `*:*:*` | `*:*:*` |
| **admin** | `*:*:platform` | `*:*:platform` | `*:*:platform` | `*:*:platform` | `*:*:platform` | `read:*:platform` | `*:*:platform` |
| **tenant_admin** | `*:*:tenant` | `*:*:tenant` | `*:*:tenant` | `*:*:tenant` | `*:*:tenant` | `*:*:own` | `*:*:tenant` |
| **security_analyst** | `read:*:*` | `*:*:*` | `*:*:*` | `read:*:*` | `read:*:tenant` | - | `read:*:*` |
| **devops_engineer** | `*:*:*` | `*:*:*` | `read:*:*` | `*:*:*` | `read:*:tenant` | - | `*:*:*` |
| **compliance_officer** | `read:*:*` | `read:*:*` | `read:*:*` | `read:*:*` | `read:*:tenant` | `read:*:own` | `read:*:*` |
| **viewer** | `read:*:*` | `read:*:*` | `read:*:*` | `read:*:*` | - | - | `read:*:*` |

## Authentication & Headers

All role endpoints require authentication:

```http
Authorization: Bearer <jwt_token>
X-Customer-ID: <customer_id>
Content-Type: application/json
```

## Error Handling

**Common HTTP Status Codes:**
- `200`: Success
- `201`: Created (role assignment)
- `400`: Bad request (validation error)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (insufficient permissions)
- `404`: Resource not found (user or role not found)
- `422`: Unprocessable entity (invalid role data)
- `500`: Internal server error

**Error Response Format:**
```json
{
  "detail": "No permission to assign security_analyst to tenant tenant_123",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123"
}
```

## Code Integration

### Service Layer Integration

```python
from services.role_service import RoleService

# Initialize service
role_service = RoleService()

# Assign role
role_assignment = await role_service.assign_role(
    user_id="user_123",
    tenant_id="tenant_123",
    role=UserRole.SECURITY_ANALYST,
    granted_by="admin_user_789"
)

# Get user roles
user_roles = await role_service.get_user_roles("user_123", "tenant_123")

# Check permissions
can_assign = await role_service.validate_role_assignment_permission(
    granter_id="admin_user_789",
    tenant_id="tenant_123", 
    role_to_assign=UserRole.DEVOPS_ENGINEER
)

# Get role permissions
permissions = role_service.get_role_permissions(UserRole.SECURITY_ANALYST)

# Get role analytics
analytics = await role_service.get_role_analytics("tenant_123")
```

### Permission Checking

```python
from authn_authz_middleware import check_permission

# Check if user has permission
user_roles = [
    {"tenant_id": "tenant_123", "role": "security_analyst", "status": "active"}
]

has_permission = check_permission(
    user_roles, 
    "alerts:create:*", 
    "tenant_123"
)

# Example permission checks
can_read_logs = check_permission(user_roles, "logs:read:*", "tenant_123")
can_create_alerts = check_permission(user_roles, "alerts:create:*", "tenant_123")
can_manage_users = check_permission(user_roles, "users:update:tenant", "tenant_123")
```

### Role Validation

```python
from models import UserRole

# Validate role assignments
valid_customer_roles = [
    UserRole.SECURITY_ANALYST,
    UserRole.DEVOPS_ENGINEER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.VIEWER
]

valid_platform_roles = [
    UserRole.SUPER_ADMIN,
    UserRole.ADMIN,
    UserRole.SUPPORT_ADMIN,
    UserRole.BILLING_ADMIN
]

# Check if role is assignable by tenant admin
is_customer_role = role in valid_customer_roles

# Check if role requires platform admin
is_platform_role = role in valid_platform_roles
```

## Database Schema

**User Tenant Roles Table:**
```sql
CREATE TABLE user_tenant_roles_mt (
    id String,
    user_id String,
    tenant_id String,
    role String,
    granted_by String,
    granted_at DateTime64(9),
    expires_at Nullable(DateTime64(9)),
    status String,
    created_at DateTime64(9),
    updated_at DateTime64(9),
    customer_id String
) ENGINE = MergeTree()
PARTITION BY customer_id
ORDER BY (customer_id, user_id, tenant_id)
```

## Performance Characteristics

- **Role Assignment**: < 100ms for database operations
- **Role Retrieval**: < 50ms for user role queries
- **Permission Checking**: < 10ms for cached role permissions
- **Bulk Operations**: < 5s for 100 role assignments
- **Analytics**: < 2s for tenant-wide role distribution
- **Validation**: < 20ms for permission validation

## Security Considerations

- **Multi-Tenant Isolation**: Complete role isolation via tenant_id
- **Permission Hierarchy**: Platform roles supersede tenant roles
- **Role Assignment Validation**: Strict permission checking for role assignments
- **Audit Logging**: All role operations logged with timestamps and actors
- **Session Integration**: Role data integrated with authentication sessions

## Best Practices

1. **Principle of Least Privilege**: Assign minimum required roles
2. **Role Hierarchy**: Use appropriate scope (platform vs tenant)
3. **Regular Audits**: Monitor role assignments and usage analytics  
4. **Permission Validation**: Always validate permissions before operations
5. **Bulk Operations**: Use bulk assignment for efficiency
6. **Role Expiration**: Set expiration dates for temporary access
7. **Documentation**: Maintain clear role and permission documentation

## Related Documentation

- [Authentication & Authorization Guide](./Auth-Router-API-Documentation.md)
- [Multi-Tenant Security Model](../../../wiki/Multi-Tenant-Security-Model.md)
- [RBAC Implementation Guide](../../../wiki/RBAC-Implementation-Guide.md)
- [Permission System Architecture](../../../wiki/Permission-System-Architecture.md)