#!/usr/bin/env python3
"""
Mapping between router files and test files - handles naming inconsistencies
"""

ROUTER_TEST_MAPPING = {
    # Router file -> Test file
    "ai_api.py": "test_ai_router.py",
    "alerts.py": "test_alerts_router.py", 
    "auth_api.py": "test_auth_router.py",
    "dashboard.py": "test_dashboard_router.py",
    "enterprise_api.py": "test_enterprise_router.py",
    "health.py": "test_health_router.py",
    "ingestion.py": "test_ingestion_router.py",
    "observability_api.py": "test_observability_router.py",
    "query.py": "test_query_router.py",
    "role_api.py": "test_role_router.py",
    "security_api.py": "test_security_router.py",
    "storage.py": "test_storage_router.py",
    "subscription_api.py": "test_subscription_router.py",
    "tenant_api.py": "test_tenant_router.py",
    "usage_api.py": "test_usage_router.py",
    "user_api.py": "test_user_router.py"
}

def get_test_file_for_router(router_file: str) -> str:
    """Get the corresponding test file for a router file"""
    from pathlib import Path
    router_name = Path(router_file).name
    return ROUTER_TEST_MAPPING.get(router_name, f"test_{Path(router_file).stem}_router.py")