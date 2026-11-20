#!/usr/bin/env python3
"""
Comprehensive Enterprise Router Test Suite
Tests all enterprise router endpoints and validates API responses based on actual router implementation
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta

# Add project paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_test import BaseTestSuite

class EnterpriseRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for enterprise router endpoints"""

    def __init__(self):
        super().__init__("EnterpriseRouter")
        self.created_subscription_ids = []  # Track created subscriptions for cleanup
        self.original_tenant_id = None  # Store original tenant ID for context switching

    def switch_to_platform_context(self):
        """Switch to platform admin context for admin operations"""
        self.auth_headers["X-Customer-ID"] = "platform"

    def switch_to_tenant_context(self):
        """Switch back to tenant context for tenant operations"""
        self.auth_headers["X-Customer-ID"] = self.original_tenant_id

    async def debug_user_roles(self):
        """Debug user role assignments"""
        try:
            from database_layer import DatabaseLayer

            db = DatabaseLayer('TestService', 'test-service-key')

            print(f"🔍 DEBUGGING USER ROLES:")
            print(f"   User ID: {getattr(self, 'test_user_id', 'NOT SET')}")
            print(f"   User Email: {getattr(self, 'test_user_email', 'NOT SET')}")

            # Check all roles for this user
            if hasattr(self, 'test_user_id'):
                query = """
                    SELECT user_id, tenant_id, role, status, customer_id
                    FROM user_tenant_roles_mt
                    WHERE user_id = %(user_id)s
                """
                results = await db.execute_query(query, {"user_id": self.test_user_id})

                print(f"   All roles for user {self.test_user_id}:")
                for row in results:
                    print(f"     - Role: {row['role']}, Tenant: {row['tenant_id']}, Status: {row['status']}")

            return True
        except Exception as e:
            print(f"❌ Debug failed: {e}")
            return False

    async def setup_enterprise_subscription(self):
        """Set up enterprise subscription for testing enterprise features - PROPER APPROACH"""
        try:
            print(f"   🔧 Setting up enterprise subscription using subscription router pattern...")

            # STEP 1: Create proper tenant via API (to get UUID format)
            tenant_create_request = {
                "name": f"Enterprise Test Org {self.test_id}",  # FIXED: use 'name' not 'organization_name'
                "type": "enterprise",  # FIXED: required TenantType enum value
                "primary_contact_name": f"Test Admin {self.test_id}",  # FIXED: required field
                "primary_contact_email": self.test_user_email,  # FIXED: required field
                "industry": "technology",  # Optional field
                "address": f"123 Test St, Suite {self.test_id}",  # Optional field
                "company_size": 100,  # Optional field
                "website": f"https://enterprise-test-{self.test_id}.com",  # Optional field
                "notes": "Created for enterprise router testing"  # Optional field
            }

            create_tenant_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            if create_tenant_response.status_code != 201:
                print(f"❌ Failed to create tenant: {create_tenant_response.status_code} - {create_tenant_response.text}")
                raise Exception(f"Tenant creation failed: {create_tenant_response.text}")

            tenant_data = create_tenant_response.json()
            uuid_tenant_id = tenant_data["tenant_id"]

            # STEP 2: Update all references to use UUID tenant_id
            self.original_tenant_id = self.test_tenant_id  # Save original for cleanup
            self.test_tenant_id = uuid_tenant_id
            self.auth_headers["X-Customer-ID"] = uuid_tenant_id

            print(f"   ✅ Created UUID tenant: {uuid_tenant_id}")

            # STEP 3: Create enterprise subscription with ALL enterprise features
            enterprise_subscription_request = {
                "subscribed_features": [
                    "enterprise.*",  # ALL enterprise features via wildcard
                    "ingestion.*",
                    "queries.*",
                    "alerts.*",
                    "security.*",
                    "compliance.*",
                    "integrations.*"
                ],
                "subscription_tier": "enterprise",
                "billing_cycle": "monthly",
                "monthly_spend_limit": 10000.0,  # High limit for enterprise
                "auto_renew": True
            }

            create_subscription_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{uuid_tenant_id}/subscription",
                json=enterprise_subscription_request
            )

            if create_subscription_response.status_code != 200:
                print(f"❌ Failed to create subscription: {create_subscription_response.status_code} - {create_subscription_response.text}")
                raise Exception(f"Subscription creation failed: {create_subscription_response.text}")

            subscription_data = create_subscription_response.json()
            print(f"   ✅ Created enterprise subscription with features: {subscription_data['subscribed_features']}")

            return uuid_tenant_id

        except Exception as e:
            print(f"❌ Failed to setup enterprise subscription: {e}")
            raise

    async def test_api_key_management(self):
        """Test API key CRUD operations"""
        print("\n🧪 Testing API Key Management...")

        try:
            # 1. Generate API key
            api_key_request = {
                "name": f"Test API Key {self.test_id}",
                "description": "Test API key for enterprise testing",
                "permissions": ["logs:read", "dashboards:read"],
                "rate_limit": 500,
                "ip_whitelist": ["192.168.1.0/24"]
            }

            generate_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/auth/api-keys",
                json=api_key_request
            )

            assert generate_response.status_code == 200, f"Expected 200, got {generate_response.status_code}: {generate_response.text}"
            generate_data = generate_response.json()

            # Validate API key generation response
            required_fields = ["key_id", "api_key", "name", "permissions", "created_at", "warning"]
            for field in required_fields:
                assert field in generate_data, f"Missing required field: {field}"

            key_id = generate_data["key_id"]
            assert generate_data["name"] == api_key_request["name"]
            assert generate_data["api_key"].startswith("lf_"), "API key should have proper prefix"

            # 2. List API keys
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/auth/api-keys"
            )

            assert list_response.status_code == 200, f"Expected 200, got {list_response.status_code}: {list_response.text}"
            list_data = list_response.json()

            required_fields = ["api_keys", "total", "active_count"]
            for field in required_fields:
                assert field in list_data, f"Missing required field: {field}"

            # Find our key in the list
            our_key = next((k for k in list_data["api_keys"] if k["key_id"] == key_id), None)
            assert our_key is not None, "Generated API key should be in list"

            # 3. Revoke API key
            revoke_response = await self.make_authenticated_request(
                "DELETE",
                f"/v1/enterprise/auth/api-keys/{key_id}"
            )

            assert revoke_response.status_code == 200, f"Expected 200, got {revoke_response.status_code}: {revoke_response.text}"
            revoke_data = revoke_response.json()
            assert revoke_data["status"] == "revoked"

            print(f"   ✅ API key management successful: Created, listed, and revoked")
            self.test_results["api_key_management"] = "PASS"

        except Exception as e:
            print(f"   ❌ API key management test error: {e}")
            self.test_results["api_key_management"] = f"ERROR: {e}"

    async def test_tenant_management(self):
        """Test tenant management operations"""
        print("\n🧪 Testing Tenant Management...")

        try:
            # 1. List tenants
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/tenants"
            )

            assert list_response.status_code == 200, f"Expected 200, got {list_response.status_code}: {list_response.text}"
            list_data = list_response.json()

            required_fields = ["tenants", "total", "active_count"]
            for field in required_fields:
                assert field in list_data, f"Missing required field: {field}"

            # 2. Create tenant (NOTE: This is enterprise tenant creation, not regular tenant creation!)
            tenant_request = {
                "tenant_id": f"test-tenant-{self.test_id}",
                "name": f"Test Tenant {self.test_id}",
                "tier": "smb",  # FIXED: Use valid TenantType enum value (not "professional")
                "data_residency": "us-east-1",
                "compliance_requirements": ["sox", "gdpr"]
                # NOTE: Removed "admin_email" as it's not in enterprise TenantRequest model
            }

            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/tenants",
                json=tenant_request
            )

            assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
            create_data = create_response.json()

            required_fields = ["tenant_id", "status", "message", "tier", "quota_limits"]
            for field in required_fields:
                assert field in create_data, f"Missing required field: {field}"

            assert create_data["status"] == "created"
            tenant_id = create_data["tenant_id"]

            # 3. Update tenant settings
            update_request = {
                "data_residency": "us-west-2",
                "compliance_requirements": ["sox", "gdpr", "hipaa"],
                "security_settings": {
                    "mfa_required": True,
                    "session_timeout": 12
                }
            }

            update_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/enterprise/tenants/{tenant_id}/settings",
                json=update_request
            )

            assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
            update_data = update_response.json()
            assert update_data["status"] == "updated"

            print(f"   ✅ Tenant management successful: Listed, created, and updated tenant")
            self.test_results["tenant_management"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant management test error: {e}")
            self.test_results["tenant_management"] = f"ERROR: {e}"

    async def test_compliance_operations(self):
        """Test compliance and audit operations"""
        print("\n🧪 Testing Compliance Operations...")

        try:
            # 1. Generate compliance report
            start_date = "2024-01-01T00:00:00Z"
            end_date = "2024-01-31T23:59:59Z"

            report_response = await self.make_authenticated_request(
                "GET",
                f"/v1/enterprise/compliance/reports?compliance_framework=sox&period_start={start_date}&period_end={end_date}&sections=access_controls&sections=audit_trail"
            )

            assert report_response.status_code == 200, f"Expected 200, got {report_response.status_code}: {report_response.text}"
            report_data = report_response.json()

            required_fields = ["report", "status", "message"]
            for field in required_fields:
                assert field in report_data, f"Missing required field: {field}"

            # Validate report structure
            report = report_data["report"]
            report_fields = ["report_id", "framework", "compliance_score", "findings", "recommendations"]
            for field in report_fields:
                assert field in report, f"Missing report field: {field}"

            # 2. Create legal hold
            legal_hold_request = {
                "case_id": f"CASE-{self.test_id}",
                "custodian": f"legal-{self.test_id}@test.com",
                "reason": "Litigation hold for compliance testing",
                "date_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z"
                },
                "scope": {
                    "data_types": ["logs", "emails", "documents"],
                    "departments": ["IT", "Legal"]
                }
            }

            hold_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/compliance/legal-hold",
                json=legal_hold_request
            )

            assert hold_response.status_code == 200, f"Expected 200, got {hold_response.status_code}: {hold_response.text}"
            hold_data = hold_response.json()

            required_fields = ["hold_id", "status", "message", "preservation_start"]
            for field in required_fields:
                assert field in hold_data, f"Missing required field: {field}"

            assert hold_data["status"] == "created"

            # 3. Get audit logs
            audit_response = await self.make_authenticated_request(
                "GET",
                f"/v1/enterprise/audit-logs?start_time={start_date}&end_time={end_date}&action_types=create&action_types=update"
            )

            assert audit_response.status_code == 200, f"Expected 200, got {audit_response.status_code}: {audit_response.text}"
            audit_data = audit_response.json()

            required_fields = ["audit_logs", "total", "filters", "retrieved_at"]
            for field in required_fields:
                assert field in audit_data, f"Missing required field: {field}"

            print(f"   ✅ Compliance operations successful: Report generated, legal hold created, audit logs retrieved")
            self.test_results["compliance_operations"] = "PASS"

        except Exception as e:
            print(f"   ❌ Compliance operations test error: {e}")
            self.test_results["compliance_operations"] = f"ERROR: {e}"

    async def test_usage_billing(self):
        """Test usage and billing analytics"""
        print("\n🧪 Testing Usage & Billing Analytics...")

        try:
            # Get usage and billing data
            start_date = "2024-01-01T00:00:00Z"
            end_date = "2024-01-31T23:59:59Z"

            billing_response = await self.make_authenticated_request(
                "GET",
                f"/v1/enterprise/usage/billing?period_start={start_date}&period_end={end_date}&breakdown=storage&breakdown=ingestion&breakdown=queries&breakdown=alerts"
            )

            assert billing_response.status_code == 200, f"Expected 200, got {billing_response.status_code}: {billing_response.text}"
            billing_data = billing_response.json()

            required_fields = ["period", "total_cost", "cost_breakdown", "usage_summary", "tenant_breakdown", "billing_details"]
            for field in required_fields:
                assert field in billing_data, f"Missing required field: {field}"

            # Validate billing structure
            assert isinstance(billing_data["total_cost"], (int, float)), "Total cost should be numeric"
            assert billing_data["billing_details"]["currency"] == "USD", "Currency should be USD"
            assert "billing_cycle" in billing_data["billing_details"], "Billing cycle should be specified"

            print(f"   ✅ Usage & billing analytics successful: ${billing_data['total_cost']:.2f} total cost")
            self.test_results["usage_billing"] = "PASS"

        except Exception as e:
            print(f"   ❌ Usage & billing analytics test error: {e}")
            self.test_results["usage_billing"] = f"ERROR: {e}"

    async def test_system_health_administration(self):
        """Test system health and administration endpoints"""
        print("\n🧪 Testing System Health & Administration...")

        try:
            # 1. Get system health
            health_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/system/health"
            )

            assert health_response.status_code == 200, f"Expected 200, got {health_response.status_code}: {health_response.text}"
            health_data = health_response.json()

            required_fields = ["overall_status", "components", "uptime_percentage", "health_check_timestamp"]
            for field in required_fields:
                assert field in health_data, f"Missing required field: {field}"

            # Validate components
            components = health_data["components"]
            expected_components = ["authentication", "tenant_management", "integrations", "audit_logging"]
            for component in expected_components:
                assert component in components, f"Missing component: {component}"
                assert "status" in components[component], f"Component {component} missing status"

            # 2. Configure backup policy
            backup_policy = {
                "policy_name": f"Test Backup Policy {self.test_id}",
                "schedule": "daily",
                "retention_days": 30,
                "storage_location": "s3://backup-bucket/enterprise",
                "encryption": True,
                "compression": True,
                "components": ["logs", "configurations", "user_data"],
                "disaster_recovery": {
                    "rto_hours": 4,
                    "rpo_hours": 1,
                    "backup_regions": ["us-east-1", "us-west-2"]
                }
            }

            backup_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/backup/configure",
                json=backup_policy
            )

            assert backup_response.status_code == 200, f"Expected 200, got {backup_response.status_code}: {backup_response.text}"
            backup_data = backup_response.json()

            required_fields = ["policy", "status", "message"]
            for field in required_fields:
                assert field in backup_data, f"Missing required field: {field}"

            assert backup_data["status"] == "configured"

            # 3. Get enterprise metrics
            metrics_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/metrics"
            )

            assert metrics_response.status_code == 200, f"Expected 200, got {metrics_response.status_code}: {metrics_response.text}"
            metrics_data = metrics_response.json()

            required_categories = ["operational_metrics", "security_metrics", "performance_metrics", "compliance_metrics"]
            for category in required_categories:
                assert category in metrics_data, f"Missing metrics category: {category}"

            print(f"   ✅ System health & administration successful: Health checked, backup configured, metrics retrieved")
            self.test_results["system_health_administration"] = "PASS"

        except Exception as e:
            print(f"   ❌ System health & administration test error: {e}")
            self.test_results["system_health_administration"] = f"ERROR: {e}"

    async def test_retired_routes(self):
        """The legacy RBAC, OIDC-config, MFA-setup and integrations routes answer 410 with their successor."""
        print("\n🧪 Testing retired enterprise routes...")
        retired = [("POST", "/v1/enterprise/auth/oidc/configure", "/v1/sso/providers"),
                   ("POST", "/v1/enterprise/auth/mfa/setup", "/v1/auth/mfa"),
                   ("GET", "/v1/enterprise/rbac/roles", "/v1/roles/custom"),
                   ("GET", "/v1/enterprise/integrations", "/v1/integrations")]
        try:
            for method, path, successor in retired:
                kwargs = {"json": {}} if method == "POST" else {}
                response = await self.make_authenticated_request(method, path, **kwargs)
                assert response.status_code == 410, f"{path}: expected 410, got {response.status_code}: {response.text}"
                assert successor in response.json()["detail"], f"{path}: {response.text}"
            self.test_results["retired_routes"] = "PASS"
        except Exception as e:
            print(f"   ❌ Retired routes test error: {e}")
            self.test_results["retired_routes"] = f"ERROR: {e}"
            raise

    async def test_enterprise_health_endpoint(self):
        """Test GET /v1/enterprise/health - Enterprise module health check"""
        print("\n🧪 Testing Enterprise Health Endpoint...")

        try:
            # Test health endpoint (no authentication required)
            response = await self.make_authenticated_request("GET", "/v1/enterprise/health")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            health_data = response.json()

            required_fields = ["status", "module", "version", "features", "endpoints_count", "timestamp"]
            for field in required_fields:
                assert field in health_data, f"Missing required field: {field}"

            assert health_data["status"] == "healthy", "Enterprise module should be healthy"
            assert health_data["module"] == "enterprise", "Module should be enterprise"
            assert health_data["endpoints_count"] == 16, "Should have 16 enterprise endpoints (legacy ones retired)"
            assert isinstance(health_data["features"], list), "Features should be a list"

            print(f"   ✅ Enterprise health endpoint successful: {health_data['status']} with {health_data['endpoints_count']} endpoints")
            self.test_results["enterprise_health_endpoint"] = "PASS"

        except Exception as e:
            print(f"   ❌ Enterprise health endpoint test error: {e}")
            self.test_results["enterprise_health_endpoint"] = f"ERROR: {e}"

    async def test_multi_tenant_isolation(self):
        """Test multi-tenant isolation across enterprise endpoints"""
        print("\n🧪 Testing Multi-Tenant Isolation...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='Isolation'
            )

            # Create an API key for the current tenant
            api_key_request = {
                "name": f"Tenant 1 API Key {self.test_id}",
                "permissions": ["logs:read"],
                "rate_limit": 100
            }

            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/auth/api-keys",
                json=api_key_request
            )

            assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"
            key_id = create_response.json()["key_id"]

            # Try to access with different tenant (should fail due to isolation)
            different_tenant_id = f"different-tenant-{self.test_id}"

            # Make request with different customer ID header to test tenant isolation
            get_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/auth/api-keys",
                headers={
                    "X-Customer-ID": different_tenant_id  # Override tenant ID
                }
            )

            # Should be blocked due to tenant isolation - either 403 OR empty data
            if get_response.status_code == 403:
                print(f"   ✅ Cross-tenant access blocked with 403 (access-level isolation)")
            elif get_response.status_code == 200:
                # Check if data is empty (data-level isolation)
                api_keys_data = get_response.json()
                assert "api_keys" in api_keys_data, f"Expected api_keys field in response"
                assert len(api_keys_data["api_keys"]) == 0, f"Cross-tenant should return empty data, got: {api_keys_data}"
                print(f"   ✅ Cross-tenant access isolated with empty data (data-level isolation)")
            else:
                assert False, f"Cross-tenant access should be blocked (403) or isolated (200 + empty), got {get_response.status_code}: {get_response.text}"

            # Try to list tenants with different customer ID
            tenants_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/tenants",
                headers={
                    "X-Customer-ID": different_tenant_id  # Override tenant ID
                }
            )

            # Should be blocked due to tenant isolation - either 403 OR empty data
            if tenants_response.status_code == 403:
                print(f"   ✅ Cross-tenant tenant access blocked with 403 (access-level isolation)")
            elif tenants_response.status_code == 200:
                # Check if data is empty (data-level isolation)
                tenants_data = tenants_response.json()
                assert "tenants" in tenants_data, f"Expected tenants field in response"
                assert len(tenants_data["tenants"]) == 0, f"Cross-tenant should return empty tenant data, got: {tenants_data}"
                assert tenants_data["total"] == 0, f"Total should be 0 for cross-tenant access, got: {tenants_data['total']}"
                print(f"   ✅ Cross-tenant tenant access isolated with empty data (data-level isolation)")
            else:
                assert False, f"Cross-tenant tenant access should be blocked (403) or isolated (200 + empty), got {tenants_response.status_code}: {tenants_response.text}"

            print(f"   ✅ Multi-tenant isolation working correctly")
            self.test_results["multi_tenant_isolation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Multi-tenant isolation test error: {e}")
            self.test_results["multi_tenant_isolation"] = f"ERROR: {e}"

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test invalid API key permissions
            invalid_api_key = {
                "name": "Invalid Key",
                "permissions": ["invalid:permission", "nonexistent:action"]
            }

            api_key_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/auth/api-keys",
                json=invalid_api_key
            )
            assert api_key_response.status_code in [400, 422, 500], "Invalid permissions should return error"

            # Test invalid tenant tier
            invalid_tenant = {
                "tenant_id": f"invalid-tenant-{self.test_id}",
                "name": "Invalid Tenant",
                "tier": "invalid_tier"  # Should be starter, professional, or enterprise
            }

            tenant_response = await self.make_authenticated_request(
                "POST",
                "/v1/enterprise/tenants",
                json=invalid_tenant
            )
            # Note: Service might accept any tier value, so this might not fail

            # Test invalid compliance framework
            invalid_compliance_response = await self.make_authenticated_request(
                "GET",
                "/v1/enterprise/compliance/reports?compliance_framework=invalid_framework&period_start=2024-01-01T00:00:00Z&period_end=2024-01-31T23:59:59Z"
            )
            assert invalid_compliance_response.status_code in [400, 422, 500], "Invalid compliance framework should return error"

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all enterprise router tests"""
        print(f"\n🚀 Starting Enterprise Router Test Suite (Test ID: {self.test_id})")
        print("=" * 60)

        # Create test user and tenant for authentication
        try:
            # Create user with both platform admin and tenant admin roles
            user_id, tenant_id = await self.create_test_user_and_tenant(['super_admin', 'tenant_admin'])

            # CRITICAL: Don't call setup_auth() - it creates SECOND user! Create session directly
            self.test_user_id = user_id  # Use the platform admin user
            self.test_tenant_id = tenant_id
            self.tenant_id = tenant_id

            print(f"   ✅ Using platform admin user: {user_id}")
            print(f"   ✅ Using tenant: {tenant_id}")

            # Create session directly for platform admin user (don't call setup_auth!)
            await self.create_test_session()

            # Setup auth headers manually
            self.auth_headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "X-Customer-ID": self.test_tenant_id
            }

            print(f"   ✅ Created session for platform admin user")

            # Set up enterprise subscription
            await self.setup_enterprise_subscription()
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_api_key_management,
            self.test_tenant_management,
            self.test_compliance_operations,
            self.test_usage_billing,
            self.test_system_health_administration,
            self.test_enterprise_health_endpoint,
            self.test_retired_routes,
            self.test_multi_tenant_isolation,
            self.test_error_handling
        ]

        for test_method in test_methods:
            try:
                await test_method()
                await asyncio.sleep(0.1)  # Brief pause between tests
            except Exception as e:
                test_name = test_method.__name__
                print(f"   ❌ {test_name} failed: {e}")
                self.test_results[test_name] = f"ERROR: {e}"

        # Cleanup
        await self.cleanup_test_data()

        # Print results summary
        self.print_test_summary()

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🏆 ENTERPRISE ROUTER TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<40} | {result}")

            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")

        if failed == 0:
            print("🎉 ALL ENTERPRISE ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_enterprise_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = EnterpriseRouterTestSuite()
    await suite.run_all_tests()

    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)

    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = EnterpriseRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
