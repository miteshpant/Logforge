# Service Key Integration Flow - Logforge Platform

## Overview

This document provides a complete analysis of how service authentication and authorization works in the Logforge platform, from application startup to database layer validation.

## Architecture Components

### 1. Application Entry Point (`main.py`)
### 2. Authentication Middleware (`authn_authz_middleware.py`) 
### 3. API Routers (`routers/*.py`)
### 4. Service Layer (`services/*.py`)
### 5. Database Layer (`database_layer.py`)

---

## 🔧 1. Application Startup Flow (`main.py`)

```python
# Application initialization sequence
app = FastAPI(title="Logforge API", lifespan=lifespan)

# 1. CORS middleware setup  
app.add_middleware(CORSMiddleware, ...)

# 2. Authentication middleware registration (CRITICAL)
from authn_authz_middleware import setup_unified_auth_middleware
setup_unified_auth_middleware(app)  # Registers UnifiedAuthMiddleware

# 3. Router registration - all API endpoints
app.include_router(enterprise_router)
app.include_router(dashboard_router)  
app.include_router(ai_router)
# ... all other routers
```

**Key Points:**
- Authentication middleware is registered **BEFORE** all API routers
- Every request passes through `UnifiedAuthMiddleware` first
- Router registration order doesn't affect authentication flow

---

## 🛡️ 2. Authentication Middleware Flow (`authn_authz_middleware.py`)

### Request Processing Pipeline

```python
class UnifiedAuthMiddleware(BaseHTTPMiddleware):
    """Handles ALL incoming requests BEFORE they reach routers"""
    
    async def dispatch(self, request: Request, call_next):
        # 1. Extract Bearer token from Authorization header
        # 2. Extract X-Customer-ID header for tenant isolation
        # 3. JWT token verification and decoding
        # 4. User session validation via DatabaseLayer
        # 5. Permission/feature checking
        # 6. Usage tracking (async, zero-latency)
        # 7. Forward request to appropriate router
```

### Critical Database Layer Usage in Middleware

```python
# Usage tracking buffer uses DatabaseLayer internally
class UsageBuffer:
    async def _insert_usage_batch(self, usage_records):
        # ✅ Uses properly registered service credentials
        service_key = os.getenv("USER_SERVICE_KEY", "user-service-key-dev")
        db = DatabaseLayer("UserService", service_key)  # WORKS
        
        result = await db.batch_insert_usage(usage_records)
```

### Platform Setup Service

```python
class PlatformSetupService:
    def __init__(self):
        # ✅ Uses properly registered service credentials
        self.db = DatabaseLayer("PlatformSetup", "platform-setup-key")  # WORKS
```

---

## 🏗️ 3. Router & Service Instantiation Flow

### Current Pattern (PROBLEMATIC)

```python
# In enterprise_api.py (and all other routers)
@router.post("/v1/enterprise/auth/oidc")
async def configure_oidc(customer_id: str = Header(...)):
    # 1. Request arrives here AFTER passing middleware
    # 2. Service instantiation happens PER REQUEST
    enterprise_service = EnterpriseService()  # ❌ FAILS HERE
    
    # 3. Service tries to call database methods
    result = await enterprise_service.generate_compliance_report(...)
```

### Service Constructor Pattern

```python
# In services/enterprise_service.py
class EnterpriseService:
    def __init__(self):
        # ❌ PROBLEM: Service name not registered in database layer
        self.service_name = "EnterpriseService"  
        self.service_key = os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-service-key-dev')
        
    async def generate_compliance_report(...):
        # ❌ FAILS: DatabaseLayer rejects "EnterpriseService"
        from database_layer import DatabaseLayer
        db = DatabaseLayer(self.service_name, self.service_key)
```

---

## 💾 4. Database Layer Authentication (`database_layer.py`)

### Service Registry System

```python
class DatabaseLayer:
    # Central service authentication registry
    AUTHORIZED_SERVICES = {
        # ✅ REGISTERED SERVICES (These work)
        'UserService': os.getenv('USER_SERVICE_KEY', 'user-service-key-dev'),
        'AlertService': os.getenv('ALERT_SERVICE_KEY', 'alert-service-key-dev'),
        'SecurityService': os.getenv('SECURITY_SERVICE_KEY', 'security-service-key-dev'),
        'IngestionService': os.getenv('INGESTION_SERVICE_KEY', 'ingestion-service-key-dev'),
        'QueryService': os.getenv('QUERY_SERVICE_KEY', 'query-service-key-dev'),
        'StorageService': os.getenv('STORAGE_SERVICE_KEY', 'storage-service-key-dev'),
        'UsageService': os.getenv('USAGE_SERVICE_KEY', 'usage-service-key-dev'),
        'HealthService': os.getenv('HEALTH_SERVICE_KEY', 'health-service-key-dev'),
        
        # ✅ REGISTERED DAOs (These work)
        'AIDAO': os.getenv('AI_SERVICE_KEY', 'ai-dao-service-key'),
        'EnterpriseDAO': os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-dao-service-key'),
        'DashboardDAO': os.getenv('DASHBOARD_SERVICE_KEY', 'dashboard-dao-service-key'),
        'UserDAO': os.getenv('USER_SERVICE_KEY', 'user-dao-service-key'),
        'TenantDAO': os.getenv('TENANT_SERVICE_KEY', 'tenant-dao-service-key'),
        # ... all other DAOs
        
        # ❌ MISSING SERVICES (These fail)
        # 'EnterpriseService': NOT REGISTERED
        # 'DashboardService': NOT REGISTERED  
        # 'AIService': NOT REGISTERED
    }
```

### Authentication Validation Process

```python
def __init__(self, service_name: str, service_key: str):
    # 1. Validate service credentials
    if not self._validate_service_credentials(service_name, service_key):
        # ❌ This is where the error is thrown
        raise SecurityError(f"Invalid credentials for service: {service_name}")
    
    # 2. Initialize ClickHouse client (only if validation passes)
    self.client = clickhouse_connect.get_client(...)

def _validate_service_credentials(self, service_name: str, service_key: str) -> bool:
    # Look up expected key for service
    expected_key = self.AUTHORIZED_SERVICES.get(service_name)  # ❌ Returns None for unregistered services
    
    if not expected_key or expected_key != service_key:
        logger.warning("Invalid service credentials", service=service_name)
        return False  # ❌ Validation fails
    
    return True  # ✅ Only for registered services
```

### Table Access Control System

```python
TABLE_ACCESS_CONTROL = {
    # Services have specific table permissions
    'UserService': ['users_mt', 'user_sessions_mt', 'user_tenant_roles_mt', 'api_usage_mt'],
    'AlertService': ['alert_rules_mt', 'alert_events_mt', 'alert_notifications_mt'],
    'SecurityService': ['security_events_mt', 'sigma_rules_mt', 'threat_intel_mt'],
    
    # DAOs inherit permissions from parent services
    'EnterpriseDAO': ['auth_providers_mt', 'api_keys_enterprise_mt', 'tenants_mt', 'enterprise_compliance_mt', 'enterprise_integrations_mt', 'enterprise_audit_logs_mt', 'api_usage_mt'],
    'DashboardDAO': ['dashboards_mt', 'dashboard_widgets_mt', 'dashboard_shares_mt', 'logs_normalized_mt'],
    'AIDAO': ['ai_investigations_mt', 'ai_analyses_mt', 'ai_baselines_mt', 'ai_query_history_mt'],
    
    # ❌ MISSING: EnterpriseService, DashboardService, AIService table permissions
}
```

---

## 🔍 5. Error Analysis: "Invalid credentials for service: EnterpriseService"

### Error Flow Sequence

1. **Router Request**: `enterprise_service = EnterpriseService()`
2. **Service Init**: `self.service_name = "EnterpriseService"`
3. **Database Call**: `db = DatabaseLayer("EnterpriseService", service_key)`
4. **Registry Lookup**: `AUTHORIZED_SERVICES.get("EnterpriseService")` → `None`
5. **Validation Failure**: `_validate_service_credentials()` → `False`
6. **Error Thrown**: `SecurityError("Invalid credentials for service: EnterpriseService")`

### Why Some Services Work and Others Don't

#### ✅ Working Services:
- **UserService**: Registered in `AUTHORIZED_SERVICES`
- **AlertService**: Registered in `AUTHORIZED_SERVICES`
- **All DAOs**: Registered with `-dao-service-key` pattern

#### ❌ Failing Services:
- **EnterpriseService**: NOT in `AUTHORIZED_SERVICES`
- **DashboardService**: NOT in `AUTHORIZED_SERVICES`
- **AIService**: NOT in `AUTHORIZED_SERVICES`

---

## 📊 6. Service Registration Patterns

### Environment Variable Pattern
```python
# Services use environment variables with dev fallbacks
'UserService': os.getenv('USER_SERVICE_KEY', 'user-service-key-dev'),
'AlertService': os.getenv('ALERT_SERVICE_KEY', 'alert-service-key-dev'),

# DAOs use environment variables with dao fallbacks  
'UserDAO': os.getenv('USER_SERVICE_KEY', 'user-dao-service-key'),
'EnterpriseDAO': os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-dao-service-key'),
```

### Key Naming Conventions
- **Services**: `{SERVICE}_SERVICE_KEY` → `{service}-service-key-dev`
- **DAOs**: `{SERVICE}_SERVICE_KEY` → `{service}-dao-service-key`
- **Special**: `TestService` → `test-service-key` (hardcoded for testing)

---

## 🔧 7. Solution Options

### Option A: Register Missing Services (RECOMMENDED)

**Add to `database_layer.py` `AUTHORIZED_SERVICES`:**
```python
AUTHORIZED_SERVICES = {
    # ... existing services ...
    
    # Add missing services
    'EnterpriseService': os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-service-key-dev'),
    'DashboardService': os.getenv('DASHBOARD_SERVICE_KEY', 'dashboard-service-key-dev'),
    'AIService': os.getenv('AI_SERVICE_KEY', 'ai-service-key-dev'),
}
```

**Add to `TABLE_ACCESS_CONTROL`:**
```python
TABLE_ACCESS_CONTROL = {
    # ... existing permissions ...
    
    # Add service permissions (inherit from corresponding DAOs)
    'EnterpriseService': ['auth_providers_mt', 'api_keys_enterprise_mt', 'tenants_mt', 'enterprise_compliance_mt', 'enterprise_integrations_mt', 'enterprise_audit_logs_mt', 'api_usage_mt'],
    'DashboardService': ['dashboards_mt', 'dashboard_widgets_mt', 'dashboard_shares_mt', 'logs_normalized_mt'],
    'AIService': ['ai_investigations_mt', 'ai_analyses_mt', 'ai_baselines_mt', 'ai_query_history_mt'],
}
```

**Add to `UPDATE_ALLOWED_SERVICES`:**
```python
UPDATE_ALLOWED_SERVICES = [
    # ... existing services ...
    'EnterpriseService', 'DashboardService', 'AIService'
]
```

### Option B: Use Existing DAO Credentials

**Change service names to use existing registrations:**
```python
# In services/enterprise_service.py
class EnterpriseService:
    def __init__(self):
        self.service_name = "EnterpriseDAO"  # Use registered DAO name
        self.service_key = os.getenv('ENTERPRISE_SERVICE_KEY', 'enterprise-dao-service-key')
```

### Option C: Service Factory Pattern

**Implement centralized service management:**
```python
class ServiceFactory:
    @staticmethod
    def get_database_layer(service_type: str) -> DatabaseLayer:
        service_registry = {
            'enterprise': ('EnterpriseDAO', 'enterprise-dao-service-key'),
            'dashboard': ('DashboardDAO', 'dashboard-dao-service-key'),
            'ai': ('AIDAO', 'ai-dao-service-key'),
        }
        service_name, service_key = service_registry[service_type]
        return DatabaseLayer(service_name, service_key)
```

---

## 🎯 8. Recommended Implementation

### Immediate Fix (Option A)
1. **Add missing service registrations** to `database_layer.py`
2. **Maintain consistency** with existing authentication patterns
3. **Preserve service architecture** without major refactoring

### Long-term Improvements
1. **Service Factory Pattern** for better credential management
2. **Dependency Injection** to avoid per-request service instantiation
3. **Configuration Validation** on startup to catch missing registrations

---

## 📋 9. Testing the Fix

### Before Fix
```bash
❌ FAIL | rbac_operations | ERROR: Expected 200, got 500: 
{"detail":"Invalid credentials for service: EnterpriseService"}
```

### After Fix
```bash
✅ PASS | rbac_operations | Status: 200
✅ PASS | compliance_operations | Status: 200  
```

---

## 🔒 10. Security Implications

### Current Security Model
- **Service-level authentication** prevents unauthorized database access
- **Table-level permissions** restrict service access to specific tables
- **Environment-based credentials** support secure key management
- **Audit logging** tracks all database operations by service

### Registration Benefits
- **Explicit permission grants** for each service
- **Environment variable support** for secure credential management
- **Table access isolation** prevents cross-service data access
- **Consistent authentication flow** across all services

---

## 📚 11. Related Documentation

- **Authentication Middleware**: `authn_authz_middleware.py`
- **Database Layer**: `database_layer.py`  
- **Service Implementation**: `services/*.py`
- **API Routers**: `routers/*.py`
- **Configuration**: Environment variables and `app_config.py`

---

## ⚡ 12. Quick Reference

### Check Service Registration
```python
from database_layer import DatabaseLayer
print(DatabaseLayer.AUTHORIZED_SERVICES.keys())
```

### Test Service Credentials
```python
try:
    db = DatabaseLayer("EnterpriseService", "enterprise-service-key-dev")
    print("✅ Service registered")
except SecurityError as e:
    print(f"❌ Service not registered: {e}")
```

### Environment Variables
```bash
# Required for new services
export ENTERPRISE_SERVICE_KEY=enterprise-service-key-dev
export DASHBOARD_SERVICE_KEY=dashboard-service-key-dev  
export AI_SERVICE_KEY=ai-service-key-dev
```

---

*Last Updated: December 2024*
*Status: Issue Analysis Complete - Implementation Required*