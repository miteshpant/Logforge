# User Management APIs

## Overview

The User Management APIs provide comprehensive CRUD operations for users, role management, and permission systems. These APIs support multi-tenant user management with role-based access control (RBAC) and bulk operations for enterprise efficiency.

**Base Path**: `/v1/users`, `/v1/admin/users`  
**Total Endpoints**: 25+  
**Authentication Required**: Yes (Bearer token + X-Customer-ID header)

## Core User Operations

### 1. List Users
```http
GET /v1/users
```

**Description**: List users in current tenant with filtering and pagination

**Authentication**: Required

**Query Parameters**:
- `limit` (integer, default: 50): Maximum users to return
- `offset` (integer, default: 0): Number of users to skip
- `role` (string, optional): Filter by role
- `status` (string, optional): Filter by status (active, inactive, pending)
- `search` (string, optional): Search by name or email

**Response** (200):
```json
{
  "users": [
    {
      "id": "user_123",
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "tenant_id": "tenant_456",
      "status": "active",
      "roles": ["user", "analyst"],
      "created_at": "2024-01-15T10:30:00Z",
      "last_login": "2024-01-20T14:25:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

**Usage Example**:
```bash
curl -X GET "http://localhost:7080/v1/users?role=analyst&limit=20" \
  -H "Authorization: Bearer <token>" \
  -H "X-Customer-ID: tenant_456"
```

### 2. Create User
```http
POST /v1/users
```

**Description**: Create new user in current tenant

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "SecurePassword123!",
  "roles": ["user"],
  "send_invitation": true
}
```

**Response** (201):
```json
{
  "id": "user_124",
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "tenant_id": "tenant_456",
  "status": "pending",
  "roles": ["user"],
  "created_at": "2024-01-20T15:30:00Z",
  "invitation_sent": true
}
```

### 3. Get User Details
```http
GET /v1/users/{user_id}
```

**Description**: Get detailed information for specific user

**Authentication**: Required

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "tenant_id": "tenant_456",
  "status": "active",
  "roles": ["user", "analyst"],
  "permissions": ["logs:read", "dashboards:write"],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-18T09:15:00Z",
  "last_login": "2024-01-20T14:25:00Z",
  "profile": {
    "timezone": "UTC",
    "language": "en",
    "notifications": true
  }
}
```

### 4. Update User
```http
PUT /v1/users/{user_id}
```

**Description**: Update user information

**Authentication**: Required (admin or self)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "first_name": "Jonathan",
  "last_name": "Doe",
  "status": "active",
  "profile": {
    "timezone": "America/New_York",
    "notifications": false
  }
}
```

**Response** (200):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "first_name": "Jonathan",
  "last_name": "Doe",
  "tenant_id": "tenant_456",
  "status": "active",
  "updated_at": "2024-01-20T15:45:00Z",
  "message": "User updated successfully"
}
```

### 5. Delete User
```http
DELETE /v1/users/{user_id}
```

**Description**: Delete user (soft delete - deactivates user)

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "message": "User deleted successfully",
  "user_id": "user_123",
  "status": "deleted"
}
```

## User Search & Discovery

### 6. Search Users
```http
GET /v1/users/search
```

**Description**: Advanced user search with full-text search capabilities

**Authentication**: Required

**Query Parameters**:
- `q` (string): Search query (name, email, role)
- `limit` (integer, default: 20): Maximum results
- `include_inactive` (boolean, default: false): Include inactive users

**Response** (200):
```json
{
  "users": [
    {
      "id": "user_123",
      "email": "john.doe@example.com",
      "full_name": "John Doe",
      "roles": ["user", "analyst"],
      "status": "active",
      "last_login": "2024-01-20T14:25:00Z"
    }
  ],
  "total": 5,
  "query": "john analyst"
}
```

### 7. Get Current User Profile
```http
GET /v1/users/me
```

**Description**: Get current authenticated user's complete profile

**Authentication**: Required

**Response** (200):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "tenant_id": "tenant_456",
  "tenant_name": "ACME Corp",
  "status": "active",
  "roles": ["user", "analyst"],
  "permissions": ["logs:read", "dashboards:write", "alerts:manage"],
  "effective_permissions": {
    "logs": ["read", "write"],
    "dashboards": ["read", "write"],
    "alerts": ["read", "write", "manage"]
  },
  "profile": {
    "timezone": "UTC",
    "language": "en",
    "notifications": true,
    "theme": "light"
  },
  "subscription": {
    "tier": "professional",
    "limits": {
      "log_retention_days": 90,
      "dashboard_count": 50,
      "user_count": 25
    }
  }
}
```

## Role Management

### 8. Get User Roles
```http
GET /v1/users/{user_id}/roles
```

**Description**: Get roles assigned to specific user

**Authentication**: Required

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "user_id": "user_123",
  "roles": [
    {
      "id": "role_001",
      "name": "analyst",
      "display_name": "Security Analyst",
      "permissions": ["logs:read", "dashboards:write", "alerts:manage"],
      "assigned_at": "2024-01-15T10:30:00Z",
      "assigned_by": "admin_user_001"
    },
    {
      "id": "role_002",
      "name": "user",
      "display_name": "Standard User",
      "permissions": ["logs:read", "dashboards:read"],
      "assigned_at": "2024-01-15T10:30:00Z",
      "assigned_by": "admin_user_001"
    }
  ]
}
```

### 9. Assign Role to User
```http
POST /v1/users/{user_id}/roles
```

**Description**: Assign role to user

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "role_name": "security_analyst",
  "grant_reason": "Promoted to security team"
}
```

**Response** (200):
```json
{
  "message": "Role assigned successfully",
  "user_id": "user_123",
  "role": {
    "id": "role_003",
    "name": "security_analyst",
    "display_name": "Security Analyst",
    "assigned_at": "2024-01-20T15:45:00Z"
  }
}
```

### 10. Remove Role from User
```http
DELETE /v1/users/{user_id}/roles/{role_id}
```

**Description**: Remove role from user

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier
- `role_id` (string): Role identifier

**Response** (200):
```json
{
  "message": "Role removed successfully",
  "user_id": "user_123",
  "role_id": "role_003"
}
```

### 11. Get User Effective Permissions
```http
GET /v1/users/{user_id}/effective-permissions
```

**Description**: Get computed effective permissions for user (combined from all roles)

**Authentication**: Required

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "user_id": "user_123",
  "effective_permissions": {
    "logs": ["read", "write"],
    "dashboards": ["read", "write", "share"],
    "alerts": ["read", "write", "manage"],
    "users": ["read"],
    "security": ["read", "analyze"]
  },
  "computed_at": "2024-01-20T15:45:00Z",
  "roles_contributing": [
    {
      "role_name": "analyst",
      "permissions": ["logs:read", "logs:write", "dashboards:write"]
    },
    {
      "role_name": "security_analyst", 
      "permissions": ["security:read", "security:analyze", "alerts:manage"]
    }
  ]
}
```

## Bulk Operations

### 12. Bulk Create Users
```http
POST /v1/users/bulk-create
```

**Description**: Create multiple users in batch operation

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "users": [
    {
      "email": "user1@example.com",
      "first_name": "Alice",
      "last_name": "Johnson",
      "roles": ["user"]
    },
    {
      "email": "user2@example.com", 
      "first_name": "Bob",
      "last_name": "Wilson",
      "roles": ["user", "analyst"]
    }
  ],
  "send_invitations": true,
  "default_password_policy": "generate_secure"
}
```

**Response** (200):
```json
{
  "message": "Bulk user creation completed",
  "created": 2,
  "failed": 0,
  "results": [
    {
      "email": "user1@example.com",
      "status": "success",
      "user_id": "user_125",
      "invitation_sent": true
    },
    {
      "email": "user2@example.com",
      "status": "success", 
      "user_id": "user_126",
      "invitation_sent": true
    }
  ]
}
```

### 13. Bulk Assign Roles
```http
POST /v1/users/bulk-assign-roles
```

**Description**: Assign roles to multiple users

**Authentication**: Required (admin role)

**Request Body**:
```json
{
  "user_ids": ["user_123", "user_124", "user_125"],
  "roles": ["security_analyst"],
  "action": "add"
}
```

**Response** (200):
```json
{
  "message": "Bulk role assignment completed",
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "user_id": "user_123",
      "status": "success",
      "roles_added": ["security_analyst"]
    },
    {
      "user_id": "user_124", 
      "status": "success",
      "roles_added": ["security_analyst"]
    },
    {
      "user_id": "user_125",
      "status": "success", 
      "roles_added": ["security_analyst"]
    }
  ]
}
```

## Admin User Management

### 14. List All Users (Admin)
```http
GET /v1/admin/users
```

**Description**: List users across all tenants (platform admin only)

**Authentication**: Required (platform admin)

**Query Parameters**:
- `tenant_id` (string, optional): Filter by specific tenant
- `status` (string, optional): Filter by status
- `limit` (integer, default: 100): Maximum users to return
- `offset` (integer, default: 0): Number of users to skip

**Response** (200):
```json
{
  "users": [
    {
      "id": "user_123",
      "email": "user@tenant1.com",
      "tenant_id": "tenant_001",
      "tenant_name": "ACME Corp",
      "status": "active",
      "roles": ["user", "analyst"],
      "last_login": "2024-01-20T14:25:00Z"
    },
    {
      "id": "user_456",
      "email": "admin@tenant2.com", 
      "tenant_id": "tenant_002",
      "tenant_name": "TechStart Inc",
      "status": "active",
      "roles": ["admin"],
      "last_login": "2024-01-19T16:30:00Z"
    }
  ],
  "total": 450,
  "limit": 100,
  "offset": 0
}
```

### 15. Create Admin User
```http
POST /v1/admin/users
```

**Description**: Create platform admin user (super admin only)

**Authentication**: Required (super admin)

**Request Body**:
```json
{
  "email": "newadmin@platform.com",
  "first_name": "Admin",
  "last_name": "User",
  "password": "SecureAdminPassword123!",
  "roles": ["admin"],
  "tenant_id": "platform"
}
```

**Response** (201):
```json
{
  "id": "user_789",
  "email": "newadmin@platform.com",
  "tenant_id": "platform", 
  "status": "active",
  "roles": ["admin"],
  "created_at": "2024-01-20T16:00:00Z"
}
```

### 16. Get Admin User Details
```http
GET /v1/admin/users/{user_id}
```

**Description**: Get detailed user information (cross-tenant access)

**Authentication**: Required (platform admin)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "tenant_id": "tenant_456",
  "tenant_name": "ACME Corp",
  "status": "active",
  "roles": ["user", "analyst"],
  "created_at": "2024-01-15T10:30:00Z",
  "last_login": "2024-01-20T14:25:00Z",
  "login_history": [
    {
      "timestamp": "2024-01-20T14:25:00Z",
      "ip_address": "192.168.1.100",
      "device": "Chrome on MacOS"
    }
  ],
  "usage_stats": {
    "api_calls_30d": 1250,
    "dashboards_created": 5,
    "alerts_configured": 12
  }
}
```

### 17. Update Admin User
```http
PUT /v1/admin/users/{user_id}
```

**Description**: Update any user (cross-tenant access)

**Authentication**: Required (platform admin)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "status": "suspended",
  "suspension_reason": "Policy violation",
  "suspension_until": "2024-02-01T00:00:00Z"
}
```

**Response** (200):
```json
{
  "id": "user_123",
  "status": "suspended",
  "suspension_reason": "Policy violation",
  "suspension_until": "2024-02-01T00:00:00Z",
  "updated_at": "2024-01-20T16:15:00Z",
  "updated_by": "admin_user_001"
}
```

### 18. Delete Admin User
```http
DELETE /v1/admin/users/{user_id}
```

**Description**: Delete any user (cross-tenant access)

**Authentication**: Required (platform admin)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "message": "User deleted successfully",
  "user_id": "user_123",
  "tenant_id": "tenant_456",
  "deleted_at": "2024-01-20T16:20:00Z",
  "deleted_by": "admin_user_001"
}
```

## User Status Management

### 19. Activate User
```http
POST /v1/users/{user_id}/activate
```

**Description**: Activate pending user account

**Authentication**: Required (admin or invitation holder)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body** (optional):
```json
{
  "activation_token": "token_123",
  "password": "NewSecurePassword123!"
}
```

**Response** (200):
```json
{
  "message": "User activated successfully",
  "user_id": "user_123",
  "status": "active",
  "activated_at": "2024-01-20T16:30:00Z"
}
```

### 20. Suspend User
```http
POST /v1/users/{user_id}/suspend
```

**Description**: Suspend user account

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "reason": "Policy violation",
  "duration_days": 30,
  "notify_user": true
}
```

**Response** (200):
```json
{
  "message": "User suspended successfully",
  "user_id": "user_123", 
  "status": "suspended",
  "suspended_until": "2024-02-20T16:30:00Z",
  "reason": "Policy violation"
}
```

### 21. Reactivate User
```http
POST /v1/users/{user_id}/reactivate
```

**Description**: Reactivate suspended user

**Authentication**: Required (admin role)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "message": "User reactivated successfully",
  "user_id": "user_123",
  "status": "active",
  "reactivated_at": "2024-01-20T16:35:00Z"
}
```

## User Analytics & Reporting

### 22. User Activity Report
```http
GET /v1/users/{user_id}/activity
```

**Description**: Get user activity and usage analytics

**Authentication**: Required (admin or self)

**Path Parameters**:
- `user_id` (string): User identifier

**Query Parameters**:
- `days` (integer, default: 30): Number of days to analyze

**Response** (200):
```json
{
  "user_id": "user_123",
  "period": "30_days",
  "activity": {
    "login_count": 25,
    "api_calls": 1250,
    "dashboards_viewed": 15,
    "queries_executed": 342,
    "alerts_created": 5,
    "last_activity": "2024-01-20T14:25:00Z"
  },
  "usage_by_feature": {
    "logs": {
      "queries": 280,
      "exports": 12
    },
    "dashboards": {
      "views": 15,
      "created": 2,
      "shared": 3
    },
    "alerts": {
      "created": 5,
      "acknowledged": 18
    }
  }
}
```

### 23. User Session History
```http
GET /v1/users/{user_id}/sessions/history
```

**Description**: Get user login/session history

**Authentication**: Required (admin or self)

**Path Parameters**:
- `user_id` (string): User identifier

**Query Parameters**:
- `limit` (integer, default: 50): Maximum sessions to return
- `days` (integer, default: 30): Number of days to look back

**Response** (200):
```json
{
  "user_id": "user_123",
  "sessions": [
    {
      "session_id": "sess_456",
      "login_time": "2024-01-20T14:25:00Z",
      "logout_time": "2024-01-20T18:30:00Z",
      "duration_minutes": 245,
      "ip_address": "192.168.1.100",
      "device": "Chrome on MacOS",
      "location": "San Francisco, CA"
    }
  ],
  "summary": {
    "total_sessions": 25,
    "avg_session_duration": 180,
    "unique_devices": 3,
    "unique_locations": 2
  }
}
```

## User Preferences & Settings

### 24. Get User Preferences
```http
GET /v1/users/{user_id}/preferences
```

**Description**: Get user preferences and settings

**Authentication**: Required (admin or self)

**Path Parameters**:
- `user_id` (string): User identifier

**Response** (200):
```json
{
  "user_id": "user_123",
  "preferences": {
    "ui": {
      "theme": "dark",
      "language": "en",
      "timezone": "America/New_York",
      "date_format": "MM/DD/YYYY",
      "time_format": "12h"
    },
    "notifications": {
      "email_alerts": true,
      "push_notifications": false,
      "alert_frequency": "immediate",
      "digest_frequency": "daily"
    },
    "dashboard": {
      "default_dashboard": "security_overview",
      "auto_refresh": true,
      "refresh_interval": 300
    }
  }
}
```

### 25. Update User Preferences
```http
PUT /v1/users/{user_id}/preferences
```

**Description**: Update user preferences

**Authentication**: Required (admin or self)

**Path Parameters**:
- `user_id` (string): User identifier

**Request Body**:
```json
{
  "ui": {
    "theme": "light",
    "timezone": "UTC"
  },
  "notifications": {
    "email_alerts": false,
    "digest_frequency": "weekly"
  }
}
```

**Response** (200):
```json
{
  "message": "Preferences updated successfully",
  "user_id": "user_123",
  "updated_at": "2024-01-20T16:45:00Z"
}
```

## Error Responses

### Common Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_request` | Invalid request parameters |
| 401 | `unauthorized` | Authentication required |
| 403 | `insufficient_permissions` | User lacks required permissions |
| 404 | `user_not_found` | User does not exist |
| 409 | `user_already_exists` | User with email already exists |
| 409 | `role_conflict` | Role assignment conflict |
| 422 | `validation_error` | Request validation failed |

### Example Error Response
```json
{
  "detail": "User with email already exists in tenant",
  "type": "user_already_exists",
  "code": "USER_001",
  "context": {
    "email": "user@example.com",
    "existing_user_id": "user_456"
  }
}
```

## Permission Model

### Role Hierarchy
1. **super_admin**: Platform-wide access
2. **admin**: Tenant administrator
3. **security_analyst**: Security operations access
4. **devops_engineer**: Infrastructure and logs access
5. **compliance_officer**: Compliance and audit access
6. **user**: Basic platform access

### Permission Format
Permissions follow the format: `resource:action:scope`

**Examples**:
- `logs:read:tenant`: Read logs in current tenant
- `users:write:own`: Modify own user profile
- `dashboards:share:team`: Share dashboards with team
- `alerts:manage:all`: Manage all alerts in tenant

---

*See [Authentication APIs](./Authentication-APIs.md) for login/session management and [Enterprise APIs](./Enterprise-APIs.md) for advanced RBAC features.*