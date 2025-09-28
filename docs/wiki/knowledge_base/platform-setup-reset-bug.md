# Platform Setup Reset Bug - Knowledge Base

## Problem Description

**Issue**: Platform setup shows "Platform setup already completed" even when users table is empty

**Symptoms**:
- `curl /v1/auth/setup/init` returns `{"detail":"Platform setup already completed"}`
- Users table (`users_mt`) is empty: `SELECT count() FROM users_mt` returns `0`
- Cannot create initial admin user
- Authentication system is broken

## Root Cause

The `has_setup_completed()` method in `SetupTokenManager` was checking in-memory token usage instead of the actual database state. When the API restarts, this in-memory state is lost but the method still thinks setup is completed.

**Original flawed code**:
```python
def has_setup_completed(self) -> bool:
    # TODO: Check if any super_admin users exist in database
    # For now, check if any tokens have been used
    return any(token_data["used"] for token_data in self.setup_tokens.values())
```

## Solution

### Fixed Implementation

The method now properly checks the database for existing super admin users:

```python
def has_setup_completed(self) -> bool:
    """Check if initial setup has been completed"""
    try:
        # Check if any super_admin users exist in the database
        query = """
            SELECT count() FROM users_mt 
            WHERE customer_id = 'platform' 
            AND id IN (
                SELECT user_id FROM user_tenant_roles_mt 
                WHERE role = 'super_admin' AND status = 'active'
            )
        """
        result = self.db.client.query(query)
        super_admin_count = result.result_rows[0][0] if result.result_rows else 0
        
        # Setup is completed if there's at least one active super admin
        setup_completed = super_admin_count > 0
        logger.debug("Setup completion check", super_admin_count=super_admin_count, completed=setup_completed)
        
        return setup_completed
        
    except Exception as e:
        logger.error("Failed to check setup completion", error=str(e))
        # Fallback: check if any tokens have been used (old behavior)
        return any(token_data["used"] for token_data in self.setup_tokens.values())
```

### Manual Reset Solution (Emergency Fix)

If you encounter this issue before the code fix is applied:

#### Option 1: Restart API Service
```bash
# Restart the API service to clear in-memory state
docker compose -f infra/docker/compose.yml restart api
```

#### Option 2: Clear Users Table (If No Important Data)
```bash
# WARNING: This deletes all users - only use in development
docker exec logforge-clickhouse clickhouse-client --user=logforge --password=logforge123 --database=logforge --query="TRUNCATE TABLE users_mt"
docker exec logforge-clickhouse clickhouse-client --user=logforge --password=logforge123 --database=logforge --query="TRUNCATE TABLE user_tenant_roles_mt"
docker exec logforge-clickhouse clickhouse-client --user=logforge --password=logforge123 --database=logforge --query="TRUNCATE TABLE user_sessions_mt"
```

#### Option 3: Database-Level Fix (Advanced)
```bash
# Check current state
docker exec logforge-clickhouse clickhouse-client --user=logforge --password=logforge123 --database=logforge --query="SELECT count() FROM users_mt"
docker exec logforge-clickhouse clickhouse-client --user=logforge --password=logforge123 --database=logforge --query="SELECT count() FROM user_tenant_roles_mt WHERE role = 'super_admin'"

# If tables are empty, just restart API service (Option 1)
```

## Prevention

### Database-First Design Pattern

This bug highlights the importance of using **database-first** design patterns for persistent state:

1. **✅ DO**: Store application state in database
2. **❌ DON'T**: Rely on in-memory state for persistent data
3. **✅ DO**: Use database queries to check business logic conditions
4. **❌ DON'T**: Use in-memory variables for setup/configuration state

### Code Review Checklist

When reviewing authentication/setup code:

- [ ] Does setup completion check the database?
- [ ] Are in-memory states only used for caching/performance?
- [ ] Can the system recover after a restart?
- [ ] Are there proper fallback mechanisms?

## Testing

### Verify Fix Works

```bash
# 1. Check setup completion logic
curl http://localhost:7080/v1/auth/setup/init

# If no users exist, should return setup token
# If admin users exist, should return "Platform setup already completed"

# 2. Test complete flow
# Create admin user
curl -X POST http://localhost:7080/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "name": "Admin User", 
    "password": "SecurePassword123!",
    "setup_token": "TOKEN_FROM_INIT"
  }'

# 3. Verify setup is now marked complete
curl http://localhost:7080/v1/auth/setup/init
# Should return: {"detail":"Platform setup already completed"}

# 4. Verify admin can login
curl -X POST http://localhost:7080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@company.com",
    "password": "SecurePassword123!"
  }'
```

### Database Validation

```sql
-- Check if admin users exist
SELECT 
    u.id, u.email, u.name, u.status,
    r.role, r.tenant_id, r.status as role_status
FROM users_mt u
JOIN user_tenant_roles_mt r ON u.id = r.user_id
WHERE r.role = 'super_admin' 
  AND r.status = 'active'
  AND u.customer_id = 'platform';

-- Should return at least one active super admin
```

## Files Modified

- `/apps/api/authn_authz_middleware.py` - Fixed `has_setup_completed()` method
- `/docs/wiki/knowledge_base/platform-setup-reset-bug.md` - This documentation

## Related Issues

- Database schema missing tables (fixed separately)
- Authentication middleware requiring complete database schema
- Setup token persistence across API restarts

## Impact Assessment

- **Severity**: High (blocks initial platform setup)
- **Scope**: Development and fresh installations
- **Data Loss Risk**: None (this is about setup logic, not data)
- **Production Impact**: High if encountered in production deployments

## Future Improvements

1. **Database-Stored Setup Tokens**: Move setup tokens to database table
2. **Idempotent Setup**: Allow re-running setup commands safely
3. **Setup Status API**: Add endpoint to check detailed setup status
4. **Admin Recovery Mode**: Add emergency admin creation mode