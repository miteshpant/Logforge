# Logforge Test Suite

This directory contains comprehensive route-based test suites for the Logforge platform, covering all API endpoints and functionality.

## Test Organization

### Router Test Suites (routes_tests/)
The primary test suite covering all API endpoints organized by router:

- `test_health_router.py` - Health check endpoints
- `test_ingestion_router.py` - Log ingestion endpoints  
- `test_query_router.py` - Query and search endpoints
- `test_dashboard_router.py` - Dashboard management endpoints
- `test_storage_router.py` - Storage and retention policy endpoints
- `test_alerts_router.py` - Alert management endpoints
- `test_security_router.py` - Security analytics and SIEM endpoints
- `test_observability_router.py` - Observability and APM endpoints
- `test_ai_router.py` - AI assistant and analysis endpoints
- `test_enterprise_router.py` - Enterprise features endpoints
- `test_tenant_router.py` - Multi-tenant management endpoints
- `test_subscription_router.py` - Subscription and billing endpoints
- `test_user_router.py` - User management endpoints (M8)
- `test_auth_router.py` - Authentication endpoints (M8)
- `test_role_router.py` - Role and permission endpoints (M8)
- `test_usage_router.py` - Usage tracking and analytics endpoints

### Support Files (routes_tests/)
- `base_test.py` - Base test class with isolated test environment setup
- `conftest.py` - Pytest configuration and fixtures
- `run_route_tests.py` - Test runner for all route tests

## Running Tests

### Quick Start

```bash
# Run all route tests
cd tests/routes_tests
python run_route_tests.py

# Run individual router tests
python test_health_router.py
python test_security_router.py
python test_auth_router.py
```

### Test Features

#### Isolated Test Environment
- Each test creates unique tenant and user IDs
- Automatic setup and teardown of test data
- No conflicts between parallel test runs
- Real database operations with cleanup

#### Authentication Testing
- Bearer token validation
- Multi-tenant isolation testing
- Role-based access control validation
- Session management testing

#### Comprehensive Coverage
- **227+ API endpoints** tested across 16 routers
- **Real database operations** (no mocking)
- **Multi-tenant data isolation** validation
- **Performance timing** measurements
- **Error condition** testing

## Test Results

The route test suite provides comprehensive validation of:

✅ **Core Platform (M0-M7)**: 100% operational  
✅ **Authentication Foundation (M8)**: Core functionality working  
✅ **Multi-Tenant Isolation**: Fully validated  
✅ **API Endpoint Coverage**: All 227 endpoints tested  
✅ **Database Integration**: Real ClickHouse operations  

## Architecture

### Test Structure
```
tests/
├── README.md                 # This file
└── routes_tests/            # All route-based tests
    ├── base_test.py         # Base test infrastructure
    ├── conftest.py          # Pytest configuration
    ├── run_route_tests.py   # Test runner
    └── test_*_router.py     # Individual router tests (16 files)
```

### Test Isolation
Each test suite uses the `BaseTestSuite` class which provides:
- Unique test identifiers to prevent data conflicts
- Automated user and tenant creation
- JWT session management
- Complete cleanup after test completion
- Real database operations with proper multi-tenant isolation

This ensures tests can run independently and in parallel without interfering with each other or leaving test data in the system.