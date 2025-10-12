# Login API Runbook - POST /v1/auth/login

## Overview
This runbook covers the authentication login API endpoint that validates user credentials and creates authenticated sessions.

**Endpoint**: `POST /v1/auth/login`  
**Purpose**: User authentication with email/password and JWT session creation  
**Authentication**: Public endpoint (no auth required)

## API Flow

### Request Format
```json
{
  "email": "user@example.com",
  "password": "userPassword123"
}
```

### Success Response (200)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": "2025-10-08T15:53:37Z",
  "user": {
    "id": "b4004684-e9b5-419d-8c79-795d82d59a63",
    "email": "user@example.com",
    "name": "User Name",
    "status": "active",
    "created_at": "2025-10-07T10:00:00Z",
    "updated_at": "2025-10-08T08:00:00Z",
    "last_login_at": "2025-10-08T08:53:37Z",
    "email_verified_at": null
  }
}
```

### Error Responses
- **401**: Invalid email or password
- **403**: User has no tenant role assignments
- **500**: Login system error

## Database Operations

### Tables Updated/Accessed
1. **`users_mt`**
   - **READ**: User lookup by email for authentication
   - **UPDATE**: `last_login_at` timestamp updated on successful login

2. **`user_sessions_mt`**
   - **INSERT**: New session record created with JWT token, IP address, user agent, expiry

3. **`user_tenant_roles_mt`**
   - **READ**: User's tenant role assignments queried to determine permissions

### SQL Operations
```sql
-- 1. User lookup and authentication
SELECT * FROM users_mt WHERE email = 'user@example.com' LIMIT 1

-- 2. Update last login timestamp
ALTER TABLE users_mt UPDATE last_login_at = now() WHERE id = 'user-uuid'

-- 3. Get user tenant roles
SELECT * FROM user_tenant_roles_mt WHERE user_id = 'user-uuid' AND status = 'active'

-- 4. Insert new session
INSERT INTO user_sessions_mt (id, user_id, session_token, ip_address, user_agent, expires_at, status, customer_id) 
VALUES (...)
```

## Code Flow

### 1. Authentication (`user_service.authenticate_user`)
- Look up user by email in `users_mt`
- Verify password hash using bcrypt
- Update `last_login_at` timestamp
- Return User object if authentication successful

### 2. Role Resolution (`role_service.get_user_roles`)
- Query `user_tenant_roles_mt` for user's tenant assignments
- Determine primary tenant context for session
- Validate user has at least one active role assignment

### 3. Session Creation (`user_service.create_session`)
- Generate JWT token with user ID, tenant ID, and role
- Create UserSession object with IP address and user agent
- Insert session record into `user_sessions_mt`
- Return session data with access token

## Testing

### Manual Testing with curl
```bash
# 1. Login request
curl -X POST http://localhost:7080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "shrutipande14@gmail.com",
    "password": "*Pdq2C8CJhj9$U2q"
  }'

# 2. Use returned token for authenticated requests
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -X POST http://localhost:7080/v1/ingest/logs \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Customer-ID: 505908f9-8718-4dea-b2d8-9b9e5ae0bd45" \
  -H "Content-Type: application/json" \
  -d '{"service": "test", "msg": "Test message"}'
```

### Verification Checklist
- [ ] User can login with valid credentials
- [ ] Invalid credentials return 401 error
- [ ] `last_login_at` timestamp updated in `users_mt`
- [ ] New session record created in `user_sessions_mt`
- [ ] JWT token contains correct user and tenant information
- [ ] Token can be used for subsequent authenticated API calls

## Troubleshooting

### Common Issues

#### "Invalid or expired session" on subsequent API calls
**Cause**: JWT token not properly formatted or expired  
**Solution**: 
- Verify token is included in `Authorization: Bearer <token>` header
- Check token expiration time
- Ensure `X-Customer-ID` header matches token's tenant

#### "User has no tenant role assignments"
**Cause**: User exists but has no active roles in `user_tenant_roles_mt`  
**Solution**:
```sql
-- Check user's role assignments
SELECT * FROM user_tenant_roles_mt WHERE user_id = 'user-uuid';

-- Assign role if missing (requires admin)
INSERT INTO user_tenant_roles_mt (id, user_id, tenant_id, role, granted_by, status) 
VALUES (uuid(), 'user-uuid', 'tenant-uuid', 'tenant_admin', 'system', 'active');
```

#### Login fails with 500 error
**Cause**: Database connectivity or service errors  
**Diagnostics**:
```bash
# Check database health
curl http://localhost:7080/health/detailed

# Check ClickHouse connectivity
docker exec clickhouse clickhouse-client --query "SELECT 1"

# Review application logs
docker logs logforge-api
```

### Performance Monitoring

#### Key Metrics
- Login success rate (target: >99%)
- Average response time (target: <500ms)
- Session creation rate
- Failed authentication attempts

#### Database Query Performance
```sql
-- Monitor slow login queries
SELECT query, query_duration_ms, user, result_rows 
FROM system.query_log 
WHERE query LIKE '%users_mt%' AND query_duration_ms > 1000
ORDER BY event_time DESC LIMIT 10;
```

## Security Considerations

### Password Security
- Passwords hashed with bcrypt (12 rounds)
- Plain passwords never logged or stored
- Failed login attempts logged for monitoring

### Session Security
- JWT tokens expire in 8 hours
- Sessions tied to IP address and user agent
- Session revocation supported via logout API

### Rate Limiting
- Consider implementing rate limiting for login attempts
- Monitor for brute force attack patterns
- Log suspicious login activity

## Related Documentation
- [Authentication Middleware Runbook](./auth-middleware-runbook.md)
- [User Management API Runbook](./user-management-runbook.md)
- [Session Management Runbook](./session-management-runbook.md)
- [Database Schema Documentation](../schemas/user-management-schema.md)

## Changelog
- **2025-10-08**: Initial runbook creation
- **Version**: M8 Authentication Foundation