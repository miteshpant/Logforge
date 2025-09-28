# User Router API Documentation

## Overview
The User Router provides comprehensive user management functionality for the Logforge platform, including user CRUD operations, admin user management, authentication, and platform security features.

**Base URL**: `/v1`
**Authentication**: Bearer Token Required
**Multi-Tenant**: Supports X-Customer-ID header for tenant isolation

## API Categories

### 1. User CRUD Operations
Standard user management operations with role-based access control.

### 2. Platform Admin User Management  
Specialized endpoints for managing platform administrator accounts.

### 3. User Profile Management
Self-service profile management for authenticated users.

### 4. User Search & Filtering
Advanced user discovery with permission-based filtering.

### 5. Bulk User Operations
High-performance bulk operations for enterprise deployment.

---

## 1. User CRUD Operations

### POST /v1/users
**Create new user account**

**Authentication**: Authenticated user required
**Request Body**:
```json
{
  "email": "user@example.com",
  "name": "John Doe", 
  "password": "SecurePassword123!",
  "status": "active"
}
```

**Password Requirements**:
- Minimum 12 characters
- Must contain uppercase, lowercase, numbers, special characters
- Cannot be common weak passwords

**Response**: `201 Created`
```json
{
  "id": "user_12345",
  "email": "user@example.com",
  "name": "John Doe",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z",
  "last_login_at": null,
  "email_verified_at": null
}
```

**Error Responses**:
- `400 Bad Request`: Password validation failed
- `409 Conflict`: User with email already exists

### GET /v1/users/search
**Search users by name or email**

**Authentication**: Admin permissions required
**Query Parameters**:
- `q` (required): Search query string
- `page` (default: 1): Page number
- `page_size` (default: 20): Results per page

**Response**: `200 OK`
```json
{
  "users": [...],
  "total_count": 150,
  "page": 1,
  "page_size": 20
}
```

**Access Control**:
- Platform admins: Can search all users
- Tenant admins: Can search users in their tenant
- Regular users: Access denied

### GET /v1/users/me
**Get current user's profile**

**Authentication**: Authenticated user required

**Response**: `200 OK`
```json
{
  "id": "user_12345",
  "email": "user@example.com", 
  "name": "John Doe",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z",
  "last_login_at": "2025-01-15T14:22:00Z",
  "email_verified_at": "2025-01-15T10:35:00Z"
}
```

### PUT /v1/users/me
**Update current user's profile**

**Authentication**: Authenticated user required
**Request Body**:
```json
{
  "name": "John Updated",
  "email": "newemail@example.com"
}
```

**Note**: Users cannot change their own status

**Response**: `200 OK` - Updated user object

### GET /v1/users/{user_id}
**Get user by ID**

**Authentication**: Self or admin access required
**Access Control**:
- Users can view their own profile
- Platform admins can view any user
- Tenant admins can view users in their tenant

**Response**: `200 OK` - User object
**Error Responses**:
- `403 Forbidden`: Cross-tenant access denied
- `404 Not Found`: User not found

### PUT /v1/users/{user_id}
**Update user account**

**Authentication**: Self or admin access required
**Access Control**:
- Users can update their own profile
- Platform admins can update any user

**Request Body**: Partial user update object
**Response**: `200 OK` - Updated user object

### DELETE /v1/users/{user_id}
**Delete user account (soft delete)**

**Authentication**: Admin permissions required
**Access Control**: Only platform admins can delete users

**Response**: `200 OK`
```json
{
  "message": "User deleted successfully",
  "user_id": "user_12345"
}
```

### GET /v1/users
**List users with filtering**

**Authentication**: Authenticated user required
**Query Parameters**:
- `page` (default: 1): Page number
- `page_size` (default: 50): Results per page  
- `search`: Search query (name or email)
- `status`: Filter by user status

**Access Control**:
- Platform admins: See all users
- Tenant admins: See users in their tenant
- Regular users: See only themselves

**Response**: `200 OK` - Paginated user list

---

## 2. Platform Admin User Management

### POST /v1/admin/users
**Create platform admin user**

**Authentication**: Platform admin required
**Request Body**: Same as regular user creation
**Note**: Admin users start with active status

**Response**: `201 Created` - Admin user object

### GET /v1/admin/users
**List platform admin users**

**Authentication**: Platform admin required
**Query Parameters**:
- `page` (default: 1): Page number
- `page_size` (default: 50): Results per page

**Response**: `200 OK` - List of users with platform admin roles

### PUT /v1/admin/users/{user_id}
**Update admin user**

**Authentication**: Platform admin required
**Security Checks**:
- Verifies target user has platform roles
- Prevents unauthorized role escalation

**Request Body**: User update object
**Response**: `200 OK` - Updated admin user

### DELETE /v1/admin/users/{user_id}
**Delete admin user**

**Authentication**: Platform admin required
**Security Checks**:
- Prevents self-deletion
- Verifies target user has platform roles
- Prevents deletion of last super admin (lockout protection)
- Revokes all user sessions for security

**Response**: `200 OK`
```json
{
  "message": "Admin user deleted successfully",
  "user_id": "user_12345"
}
```

### GET /v1/admin/users/{user_id}
**Get admin user details**

**Authentication**: Platform admin required
**Security Checks**:
- Verifies target user has platform roles

**Response**: `200 OK` - Admin user object

---

## 3. User Profile Management

### Profile Update Capabilities
- Name and email updates
- Password changes (with validation)
- Cannot modify own status or roles
- Automatic timestamp updates

### Email Verification
- Email verification status tracking
- Updated email requires re-verification
- System maintains verification timestamps

---

## 4. User Search & Filtering

### Search Capabilities
- Full-text search across name and email fields
- Case-insensitive matching
- Database-level search optimization
- Pagination support

### Filtering Options
- Status filtering (active, inactive, pending)
- Role-based result filtering
- Tenant-scoped search for tenant admins

---

## 5. Bulk User Operations

### POST /v1/users/bulk-create
**Bulk create multiple users**

**Authentication**: Platform admin required
**Request Body**:
```json
[
  {
    "email": "user1@example.com",
    "name": "User One",
    "password": "SecurePassword123!"
  },
  {
    "email": "user2@example.com", 
    "name": "User Two",
    "password": "AnotherSecure456!"
  }
]
```

**Limitations**:
- Maximum 100 users per request
- Continues processing on individual failures
- Returns successfully created users

**Response**: `200 OK` - Array of created user objects

**Error Handling**:
- Individual creation failures logged
- Duplicate email detection
- Partial success supported

---

## Security Features

### Password Security
- **Strength Validation**: 12+ characters with mixed case, numbers, special characters
- **Weak Password Detection**: Blocks common passwords
- **Bcrypt Hashing**: 12 rounds for secure storage
- **Password Updates**: Full validation on changes

### Platform Admin Security
- **Role Verification**: All admin operations verify platform roles
- **Lockout Prevention**: Cannot delete last super admin
- **Session Revocation**: Security-triggered session cleanup
- **Self-Protection**: Prevents admin self-deletion

### Multi-Tenant Isolation
- **Header Validation**: X-Customer-ID enforcement
- **Cross-Tenant Protection**: Blocks unauthorized access
- **Role-Based Filtering**: Tenant-scoped data access
- **Platform Override**: Platform admins can access all tenants

### Authentication & Authorization
- **JWT Token Validation**: Bearer token required
- **Session Management**: Database-persisted sessions
- **Role Enforcement**: Granular permission checking
- **Activity Tracking**: Login and access logging

---

## Database Operations

### User Storage
- **Primary Table**: `users_mt` (multi-tenant)
- **Soft Deletes**: Status-based deletion (active → inactive)
- **Timestamps**: Created, updated, last login tracking
- **Email Verification**: Verification status and timestamps

### Platform Role Management
- **Role Table**: `user_tenant_roles_mt`
- **Platform Tenant**: Special "platform" tenant for admin roles
- **Role Types**: super_admin, admin, support_admin, billing_admin
- **Expiration Support**: Role-based expiration dates

### Session Management
- **Session Table**: `user_sessions_mt`
- **JWT Integration**: Database persistence with JWT tokens
- **Expiration Tracking**: Automatic session cleanup
- **Security Revocation**: Admin-triggered session invalidation

---

## Performance Optimizations

### Database Queries
- **Pagination**: Efficient offset-based pagination
- **Indexing**: Optimized database indexes on email, status
- **Filtering**: Database-level search and filtering
- **Connection Pooling**: Optimized database connections

### Caching Strategy
- **No Cache Dependencies**: Pure database operations
- **Consistency**: Read-after-write consistency handling
- **Real-time Updates**: Immediate database reflection

### Async Operations
- **Non-blocking**: Full async/await implementation
- **Background Tasks**: Async session activity updates
- **Parallel Processing**: Bulk operations optimization

---

## Error Handling

### HTTP Status Codes
- `200 OK`: Successful operations
- `201 Created`: Resource creation
- `400 Bad Request`: Validation errors
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflicts (duplicate email)
- `500 Internal Server Error`: System errors

### Error Response Format
```json
{
  "detail": "Error description",
  "status_code": 400,
  "error_type": "validation_error"
}
```

### Validation Errors
- Password strength violations
- Email format validation
- Required field validation
- Business rule violations

---

## Integration Points

### Authentication Middleware
- **Token Validation**: JWT token processing
- **User Resolution**: Database user lookup
- **Role Loading**: Platform and tenant role resolution
- **Request Context**: User and role injection

### Authorization Dependencies
- **Platform Admin Checks**: require_platform_admin dependency
- **Tenant Admin Checks**: require_tenant_admin dependency
- **Current User**: get_current_user dependency
- **Multi-Tenant Headers**: X-Customer-ID processing

### Database Layer Integration
- **UserService**: Business logic layer
- **UserDAO**: Data access layer
- **DatabaseLayer**: Low-level database operations
- **Transaction Support**: Database transaction handling

---

## Testing & Validation

### Unit Test Coverage
- User CRUD operations
- Admin user management
- Password validation
- Security checks
- Database operations

### Integration Testing
- Authentication flows
- Multi-tenant isolation
- Role-based access control
- Bulk operations
- Error handling

### Security Testing
- Password strength validation
- Role escalation prevention
- Cross-tenant access blocking
- Session security
- Admin lockout prevention

---

## Deployment Considerations

### Environment Configuration
- Database connection settings
- JWT secret configuration
- Password complexity rules
- Session timeout settings

### Production Security
- HTTPS enforcement
- Rate limiting implementation
- Audit logging
- Monitoring and alerting

### Scalability
- Database connection pooling
- Horizontal scaling support
- Load balancer compatibility
- Session distribution

---

## API Change Log

### Version 1.0 (Current)
- Complete user CRUD operations
- Platform admin management
- Password security implementation
- Multi-tenant isolation
- Bulk operations support
- Database-only architecture (no cache dependencies)

### Planned Enhancements
- Password reset workflows
- Email verification flows
- Advanced role management
- API usage tracking
- User invitation system

---

## Support & Troubleshooting

### Common Issues
1. **Password Validation Failures**: Check password complexity requirements
2. **Cross-Tenant Access Denied**: Verify X-Customer-ID header and user roles
3. **Admin Lockout**: Ensure multiple super admins before deletion
4. **Session Issues**: Check JWT token validity and database session state

### Monitoring Points
- User creation/update success rates
- Authentication failure rates
- Admin operation audit trails
- Database performance metrics
- Security violation alerts

### Contact Information
- **API Issues**: Platform engineering team
- **Security Concerns**: Security team escalation
- **Database Issues**: Infrastructure team
- **Documentation**: Technical writing team

---

*Last Updated: 2025-01-15*
*Version: 1.0*
*Status: Production Ready*