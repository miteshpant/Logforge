# Bug Report - Logforge System Issues & Resolutions

## Overview
This document tracks all bugs encountered during the development and refactoring of the Logforge platform, along with their root causes and solutions.

---

## 🐛 **Bug #001: M8 Tests Failing Due to Cache/Database Inconsistency**

**Date**: 2025-09-07  
**Severity**: High  
**Component**: Authentication System  
**Status**: 🔧 In Progress  

### Root Cause Analysis
The system has **three different UserService implementations** causing inconsistencies:

1. **`auth_middleware.py`** - Legacy cache-only implementation with TODOs
2. **`authn_authz_middleware.py`** - Modern database-first with cache fallback  
3. **Mixed imports** - API files importing different versions inconsistently

### Specific Issues
1. **`'UserService' object has no attribute 'users_cache'`**
   - New database-enabled UserService doesn't always initialize cache
   - Old API code still tries to access `self.users_cache`

2. **`Invalid None value in non-Nullable column` in `api_usage_mt`**
   - Usage tracking inserting `None` values for `customer_id` field
   - ClickHouse rejects NULL values in non-nullable columns

3. **Data Persistence Issues**
   - Cache data lost on service restart
   - Database operations work but fallback to cache causes inconsistencies

### Evidence
```
2025-09-07 03:23:34 [error] User creation failed - 'UserService' object has no attribute 'users_cache'
2025-09-07 03:23:35 [ERROR] clickhouse_connect.driver.exceptions.DataError: Invalid None value in non-Nullable column
2025-09-07 03:23:35 [error] Batch insert failed - error=Invalid None value in non-Nullable column service=UserService table=api_usage_mt
```

### Impact
- **M8 tests failing** (0/23 pass) - User creation API endpoints broken
- **M0-M7 tests pass** (71/71) - Database layer works correctly when used directly
- **Admin UI authentication** works with database-created users
- **Inconsistent data state** between cache and database

### Solution Strategy
1. **Remove ALL cache usage** from authentication system
2. **Use database-only operations** consistently across all components
3. **Fix customer_id NULL issues** in usage tracking
4. **Consolidate UserService** to single database-enabled version

### Files Affected
- `apps/api/auth_middleware.py` - Legacy cache-only (to be deprecated)
- `apps/api/authn_authz_middleware.py` - Database-enabled (to be primary)
- `apps/api/auth_api.py` - Mixed cache/database usage
- `apps/api/user_api.py` - Cache fallbacks and TODOs
- `apps/api/database_layer.py` - Missing api_usage_mt table (fixed)

### Decision Rationale
**Why eliminate cache entirely:**
- ✅ Database operations proven reliable (M0-M7 tests pass)
- ✅ ClickHouse designed for high-performance queries
- ❌ Cache adds complexity without performance benefits
- ❌ Cache causes data consistency issues
- ❌ Dual code paths increase maintenance burden

### Progress
- [x] **Added missing `api_usage_mt` table** to DatabaseLayer
- [x] **Fixed imports** in multiple API files to use `authn_authz_middleware`
- [x] **Deleted `auth_middleware.py`** - Removed legacy cache-only implementation entirely
- [x] **Remove cache references systematically** - COMPLETED
  - [x] Fixed `auth_api.py` to use database-only operations
  - [x] Fixed `user_api.py` to use database-only operations  
  - [x] Removed ALL cache fallbacks from `authn_authz_middleware.py`
- [x] **Fix customer_id NULL values** in usage tracking - COMPLETED
- [🔄] **Debug M8 test failures** - IN PROGRESS (new tenant access issues identified)
- [ ] Verify M8 tests pass with database-only operations

### Next Steps (Immediate)
1. **Complete `auth_api.py` cache removal** - Replace remaining 6 cache operations
2. **Fix `user_api.py` systematically** - Replace all cache operations with database queries
3. **Fix customer_id NULL issue** - Ensure usage tracking provides valid customer_id values  
4. **Test M8 functionality** - Verify user creation works end-to-end

---

## 🐛 **Bug #002: Missing API Usage Table**

**Date**: 2025-09-07  
**Severity**: Medium  
**Component**: Database Layer  
**Status**: ✅ Resolved  

### Root Cause
The `api_usage_mt` table was referenced in code but never created during database initialization.

### Error
```
Code: 60. DB::Exception: Table logforge.api_usage_mt does not exist. (UNKNOWN_TABLE)
```

### Solution
Added `api_usage_mt` table creation to `DatabaseLayer._create_user_tables()`:
```sql
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
```

### Files Changed
- `apps/api/database_layer.py` - Added table creation and column mappings

---

## 🐛 **Bug #003: M5 Observability Permission Issues**

**Date**: 2025-09-07  
**Severity**: Low  
**Component**: Permission System  
**Status**: ✅ Resolved  

### Root Cause
Missing permission mappings for `/v1/observability/` endpoints in the authentication middleware.

### Error
```
{"error":"Insufficient permissions for /v1/observability/health"}
```

### Solution
1. Added observability endpoint mapping to `get_endpoint_permission()`
2. Added `observability:*:tenant` permissions to `TENANT_ADMIN` role

### Files Changed
- `apps/api/authn_authz_middleware.py` - Added permission mappings

---

## Template for Future Bugs

## 🐛 **Bug #XXX: [Bug Title]**

**Date**: YYYY-MM-DD  
**Severity**: [Critical|High|Medium|Low]  
**Component**: [Component Name]  
**Status**: [🔧 In Progress | ✅ Resolved | 🚫 Won't Fix]  

### Root Cause
[Detailed explanation of why the bug occurred]

### Error/Evidence
```
[Error messages, logs, or evidence]
```

### Impact
[What functionality is affected]

### Solution
[How it was fixed or will be fixed]

### Files Changed
[List of files modified]

---

## Summary

**Total Bugs Tracked**: 3  
**Resolved**: 2  
**In Progress**: 1  
**Critical/High Severity**: 1  

## Lessons Learned
1. **Systematic testing** helps identify architectural inconsistencies
2. **Database-first design** reduces complexity compared to cache fallbacks  
3. **Comprehensive logging** crucial for debugging distributed systems
4. **API contract consistency** important across different service layers