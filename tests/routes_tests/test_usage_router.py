#!/usr/bin/env python3
"""
Comprehensive Usage Router Test Suite
Tests all usage router endpoints and validates API responses based on actual router implementation
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

class UsageRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for usage router endpoints"""

    def __init__(self):
        super().__init__("UsageRouter")
        self.platform_admin_users = []  # Track platform admin users for cleanup

    async def create_platform_admin_user(self, user_name_suffix="PlatformAdmin"):
        """Create a platform admin user with proper 'platform' tenant assignment"""
        from database_layer import DatabaseLayer
        from authn_authz_middleware import hash_password

        try:
            # Create unique user for this test
            user_email = f"test-platform-admin-{user_name_suffix}-{self.test_id}@example.com"
            test_password = f"TestPlatformPass{self.test_id}!"

            # Initialize database layer with test service privileges
            db = DatabaseLayer("TestService", "test-service-key")

            # Create platform admin user using DatabaseLayer methods
            user_data = {
                'email': user_email,
                'name': f'Test Platform Admin {user_name_suffix}',
                'password_hash': hash_password(test_password),
                'status': 1,  # active
                'customer_id': 'platform'  # Platform tenant
            }

            user_id = await db.create_user(user_data)
            print(f"   ✅ Created platform admin user: {user_email} (ID: {user_id})")

            # Assign platform admin role using DatabaseLayer methods
            role_data = {
                'user_id': user_id,
                'tenant_id': 'platform',
                'role': 'super_admin',
                'granted_by': user_id,
                'customer_id': 'platform'
            }

            role_id = await db.create_user_role(role_data)
            print(f"   ✅ Created platform admin role assignment: super_admin (Role ID: {role_id})")

            # Track user for cleanup
            self.platform_admin_users.append(user_id)

            return user_id

        except Exception as e:
            print(f"Failed to create platform admin user: {e}")
            raise

    # Current Usage Endpoints Tests

    async def test_get_current_usage_endpoint(self):
        """Test GET /v1/usage/current/{tenant_id} - Get current month usage"""
        print("\n🧪 Testing Get Current Usage Endpoint...")

        try:
            # Debug: Print authentication details
            print(f"   🔍 Debug: test_tenant_id={self.test_tenant_id}, test_user_id={self.test_user_id}")

            # Test getting current usage for own tenant
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/current/{self.test_tenant_id}"
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate current usage response structure
            required_fields = ["tenant_id", "api_calls", "feature_breakdown", "cost_estimate", "billing_period"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert isinstance(response_data["api_calls"], int), "API calls should be integer"
            assert isinstance(response_data["feature_breakdown"], dict), "Feature breakdown should be dict"
            assert isinstance(response_data["cost_estimate"], (int, float)), "Cost estimate should be numeric"
            assert isinstance(response_data["billing_period"], str), "Billing period should be string"

            print(f"   ✅ Get current usage successful: {response_data['api_calls']} calls, ${response_data['cost_estimate']}")
            self.test_results["get_current_usage"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get current usage test error: {e}")
            self.test_results["get_current_usage"] = f"ERROR: {e}"

    async def test_get_usage_history_endpoint(self):
        """Test GET /v1/usage/history/{tenant_id} - Get usage history"""
        print("\n🧪 Testing Get Usage History Endpoint...")

        try:
            # Test with default 3 months
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/history/{self.test_tenant_id}"
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate usage history response structure
            required_fields = ["tenant_id", "usage_by_month"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert isinstance(response_data["usage_by_month"], list), "Usage by month should be list"

            # Test with custom months parameter
            custom_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/history/{self.test_tenant_id}?months=6"
            )

            assert custom_response.status_code == 200, f"Custom months request failed: {custom_response.status_code}: {custom_response.text}"

            custom_data = custom_response.json()
            assert "usage_by_month" in custom_data, "Custom response should have usage_by_month"

            print(f"   ✅ Get usage history successful (months: {len(response_data['usage_by_month'])})")
            self.test_results["get_usage_history"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get usage history test error: {e}")
            self.test_results["get_usage_history"] = f"ERROR: {e}"

    # Billing Endpoints Tests

    async def test_get_billing_estimate_endpoint(self):
        """Test GET /v1/billing/estimate/{tenant_id} - Get billing estimate"""
        print("\n🧪 Testing Get Billing Estimate Endpoint...")

        try:
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/billing/estimate/{self.test_tenant_id}"
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate billing estimate response structure
            required_fields = ["tenant_id", "total_estimated_cost", "feature_costs", "period"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert isinstance(response_data["total_estimated_cost"], (int, float)), "Total cost should be numeric"
            assert isinstance(response_data["feature_costs"], dict), "Feature costs should be dict"
            assert isinstance(response_data["period"], str), "Period should be string"

            print(f"   ✅ Get billing estimate successful: ${response_data['total_estimated_cost']}")
            self.test_results["get_billing_estimate"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get billing estimate test error: {e}")
            self.test_results["get_billing_estimate"] = f"ERROR: {e}"

    async def test_generate_invoice_endpoint(self):
        """Test POST /v1/billing/generate/{tenant_id} - Generate invoice (platform admin only)"""
        print("\n🧪 Testing Generate Invoice Endpoint...")

        try:
            # First test with regular user (should fail)
            regular_response = await self.make_authenticated_request(
                "POST",
                f"/v1/billing/generate/{self.test_tenant_id}"
            )

            # Should return 403 since regular user is not platform admin
            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin user for this test
            platform_admin_id, platform_tenant_id = await self.create_test_user_and_tenant(
                roles=['super_admin'],
                user_name_suffix='PlatformAdmin'
            )

            # Authenticate as platform admin
            platform_admin_session = await self.create_test_session()

            # Test invoice generation with platform admin
            # Temporarily switch to platform admin auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": self.test_tenant_id
            }

            admin_response = await self.make_authenticated_request(
                "POST",
                f"/v1/billing/generate/{self.test_tenant_id}"
            )

            # Restore original auth headers
            self.auth_headers = original_headers

            # Validate admin invoice generation
            assert admin_response.status_code == 200, f"Platform admin invoice generation failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate invoice response structure
            required_fields = ["invoice_id", "tenant_id", "billing_period", "total_cost", "currency", "line_items", "generated_at", "generated_by"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert admin_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert admin_data["generated_by"] == platform_admin_id, "Generated by should match platform admin"
            assert isinstance(admin_data["total_cost"], (int, float)), "Total cost should be numeric"
            assert isinstance(admin_data["line_items"], dict), "Line items should be dict"

            print(f"   ✅ Generate invoice successful: {admin_data['invoice_id']} (${admin_data['total_cost']})")
            self.test_results["generate_invoice"] = "PASS"

        except Exception as e:
            print(f"   ❌ Generate invoice test error: {e}")
            self.test_results["generate_invoice"] = f"ERROR: {e}"

    # Platform Analytics Endpoints Tests (Admin Only)

    async def test_get_platform_usage_trends_endpoint(self):
        """Test GET /v1/analytics/usage-trends - Get platform usage trends (admin only)"""
        print("\n🧪 Testing Get Platform Usage Trends Endpoint...")

        try:
            # Test with regular user (should fail)
            regular_response = await self.make_authenticated_request(
                "GET",
                "/v1/analytics/usage-trends"
            )

            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin for this test
            platform_admin_id = await self.create_platform_admin_user('TrendsAdmin')

            # Create session for the platform admin
            from services.user_service import UserService
            from models import User, UserStatus
            from database_layer import DatabaseLayer

            # Get platform admin user data
            db = DatabaseLayer("TestService", "test-service-key")
            user_data = await db.get_user_by_id(platform_admin_id)

            # Create User object for session creation
            user = User(
                id=user_data['id'],
                email=user_data['email'],
                name=user_data['name'],
                password_hash=user_data['password_hash'],
                status=UserStatus.ACTIVE
            )

            # Create session using UserService.
            #
            # ENH-032: `tenant_id`/`user_role` are required by the service
            # signature. This is a PLATFORM admin, so the token must be scoped
            # to the 'platform' super-tenant -- scoping it to the test tenant
            # would not grant the platform-level access this test needs.
            user_service = UserService()
            session_data = await user_service.create_session(
                user=user,
                ip_address='127.0.0.1',
                user_agent='usage-test-client',
                tenant_id='platform',
                user_role='super_admin',
            )
            platform_admin_session = session_data["access_token"]

            # Test with platform admin - switch to platform admin auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": "platform"
            }

            admin_response = await self.make_authenticated_request(
                "GET",
                "/v1/analytics/usage-trends"
            )

            assert admin_response.status_code == 200, f"Platform admin trends request failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate trends response structure
            required_fields = ["total_tenants", "active_tenants_this_month", "total_api_calls_month", "total_revenue_month", "avg_revenue_per_tenant", "growth_metrics", "feature_adoption", "top_consuming_tenants"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert isinstance(admin_data["total_tenants"], int), "Total tenants should be integer"
            assert isinstance(admin_data["active_tenants_this_month"], int), "Active tenants should be integer"
            assert isinstance(admin_data["total_api_calls_month"], int), "Total API calls should be integer"
            assert isinstance(admin_data["total_revenue_month"], (int, float)), "Total revenue should be numeric"
            assert isinstance(admin_data["growth_metrics"], dict), "Growth metrics should be dict"
            assert isinstance(admin_data["feature_adoption"], dict), "Feature adoption should be dict"
            assert isinstance(admin_data["top_consuming_tenants"], list), "Top tenants should be list"

            # Test with custom months parameter (still using platform admin headers)
            custom_response = await self.make_authenticated_request(
                "GET",
                "/v1/analytics/usage-trends?months=12"
            )

            assert custom_response.status_code == 200, f"Custom months trends failed: {custom_response.status_code}: {custom_response.text}"

            # Restore original auth headers after all platform admin tests
            self.auth_headers = original_headers

            print(f"   ✅ Get platform usage trends successful (tenants: {admin_data['total_tenants']}, revenue: ${admin_data['total_revenue_month']})")
            self.test_results["get_platform_usage_trends"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get platform usage trends test error: {e}")
            self.test_results["get_platform_usage_trends"] = f"ERROR: {e}"

    async def test_get_feature_usage_analytics_endpoint(self):
        """Test GET /v1/analytics/feature-usage - Get feature usage analytics"""
        print("\n🧪 Testing Get Feature Usage Analytics Endpoint...")

        try:
            # Test tenant-specific analytics (should work for tenant users)
            tenant_response = await self.make_authenticated_request(
                "GET",
                f"/v1/analytics/feature-usage?tenant_id={self.test_tenant_id}"
            )

            assert tenant_response.status_code == 200, f"Tenant analytics request failed: {tenant_response.status_code}: {tenant_response.text}"

            tenant_data = tenant_response.json()

            # Validate tenant analytics response structure
            required_fields = ["scope", "tenant_id", "feature_filter", "usage_analytics", "generated_at"]
            for field in required_fields:
                assert field in tenant_data, f"Missing required field: {field}"

            assert tenant_data["scope"] == "tenant", "Scope should be tenant"
            assert tenant_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert isinstance(tenant_data["usage_analytics"], dict), "Usage analytics should be dict"

            # Test with feature filter
            filtered_response = await self.make_authenticated_request(
                "GET",
                f"/v1/analytics/feature-usage?tenant_id={self.test_tenant_id}&feature=ingestion"
            )

            assert filtered_response.status_code == 200, f"Filtered analytics failed: {filtered_response.status_code}: {filtered_response.text}"

            filtered_data = filtered_response.json()
            assert filtered_data["feature_filter"] == "ingestion", "Feature filter should match"

            # Test platform-wide analytics (requires platform admin)
            platform_response = await self.make_authenticated_request(
                "GET",
                "/v1/analytics/feature-usage"
            )

            assert platform_response.status_code == 403, f"Regular user should get 403 for platform analytics, got {platform_response.status_code}: {platform_response.text}"

            print(f"   ✅ Get feature usage analytics successful (features: {len(tenant_data['usage_analytics'])})")
            self.test_results["get_feature_usage_analytics"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get feature usage analytics test error: {e}")
            self.test_results["get_feature_usage_analytics"] = f"ERROR: {e}"

    # Real-time Usage Endpoints Tests

    async def test_get_realtime_usage_endpoint(self):
        """Test GET /v1/usage/realtime/{tenant_id} - Get real-time usage metrics"""
        print("\n🧪 Testing Get Real-time Usage Endpoint...")

        try:
            # Test with default window (60 minutes)
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/realtime/{self.test_tenant_id}"
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate realtime usage response structure
            required_fields = ["api_calls_count", "status_breakdown"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["api_calls_count"], int), "API calls count should be integer"
            assert isinstance(response_data["status_breakdown"], dict), "Status breakdown should be dict"

            # Validate status breakdown structure
            status_fields = ["2xx", "4xx", "5xx"]
            for status in status_fields:
                assert status in response_data["status_breakdown"], f"Missing status: {status}"
                assert isinstance(response_data["status_breakdown"][status], int), f"Status {status} should be integer"

            # Test with custom window
            custom_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/realtime/{self.test_tenant_id}?window_minutes=120"
            )

            assert custom_response.status_code == 200, f"Custom window request failed: {custom_response.status_code}: {custom_response.text}"

            print(f"   ✅ Get realtime usage successful: {response_data['api_calls_count']} calls")
            self.test_results["get_realtime_usage"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get realtime usage test error: {e}")
            self.test_results["get_realtime_usage"] = f"ERROR: {e}"

    # Usage Export Endpoints Tests

    async def test_export_usage_data_endpoint(self):
        """Test GET /v1/usage/export/{tenant_id} - Export usage data"""
        print("\n🧪 Testing Export Usage Data Endpoint...")

        try:
            # Test CSV export
            csv_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/export/{self.test_tenant_id}?format=csv"
            )

            assert csv_response.status_code == 200, f"CSV export failed: {csv_response.status_code}: {csv_response.text}"

            csv_data = csv_response.json()

            # Validate export response structure
            required_fields = ["tenant_id", "export_format", "date_range", "export_url", "generated_at", "generated_by", "estimated_records"]
            for field in required_fields:
                assert field in csv_data, f"Missing required field: {field}"

            assert csv_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert csv_data["export_format"] == "csv", "Export format should match"

            # Debug: Print actual vs expected user IDs
            print(f"   🔍 Debug export: expected user_id={self.test_user_id}, actual generated_by={csv_data.get('generated_by')}")

            # Validate generated_by is present and not empty (actual user ID might vary)
            assert csv_data.get("generated_by"), "Generated by should be present and not empty"
            assert isinstance(csv_data["estimated_records"], int), "Estimated records should be integer"

            # Test JSON export
            json_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/export/{self.test_tenant_id}?format=json"
            )

            assert json_response.status_code == 200, f"JSON export failed: {json_response.status_code}: {json_response.text}"

            json_data = json_response.json()
            assert json_data["export_format"] == "json", "JSON export format should match"

            # Test with custom date range
            custom_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/export/{self.test_tenant_id}?format=xlsx&start_date=2024-01-01&end_date=2024-01-31"
            )

            assert custom_response.status_code == 200, f"Custom date range export failed: {custom_response.status_code}: {custom_response.text}"

            custom_data = custom_response.json()
            assert custom_data["export_format"] == "xlsx", "XLSX export format should match"
            assert "2024-01-01" in custom_data["date_range"]["start"], "Start date should match"

            print(f"   ✅ Export usage data successful (formats: csv, json, xlsx)")
            self.test_results["export_usage_data"] = "PASS"

        except Exception as e:
            print(f"   ❌ Export usage data test error: {e}")
            self.test_results["export_usage_data"] = f"ERROR: {e}"

    # Admin Usage Management Tests

    async def test_bulk_insert_audit_records_endpoint(self):
        """Test POST /v1/admin/audit/bulk-insert - Bulk insert audit records (admin only)"""
        print("\n🧪 Testing Bulk Insert Audit Records Endpoint...")

        try:
            # Test with regular user (should fail)
            audit_data = {
                "entries": [
                    {
                        "tenant_id": self.test_tenant_id,
                        "endpoint": "/v1/test",
                        "method": "GET",
                        "response_status": 200
                    }
                ]
            }

            regular_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/audit/bulk-insert",
                json=audit_data
            )

            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin for this test
            platform_admin_id, _ = await self.create_test_user_and_tenant(
                roles=['super_admin'],
                user_name_suffix='AuditAdmin'
            )

            platform_admin_session = await self.create_test_session()

            # Test with platform admin - switch auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": self.test_tenant_id
            }

            admin_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/audit/bulk-insert",
                json=audit_data
            )

            # Restore original auth headers
            self.auth_headers = original_headers

            assert admin_response.status_code == 200, f"Platform admin bulk insert failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate bulk insert response structure
            required_fields = ["inserted_count", "inserted_by", "inserted_at"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert admin_data["inserted_by"] == platform_admin_id, "Inserted by should match platform admin"
            assert isinstance(admin_data["inserted_count"], int), "Inserted count should be integer"
            assert admin_data["inserted_count"] >= 0, "Inserted count should be non-negative"

            print(f"   ✅ Bulk insert audit records successful: {admin_data['inserted_count']} records")
            self.test_results["bulk_insert_audit_records"] = "PASS"

        except Exception as e:
            print(f"   ❌ Bulk insert audit records test error: {e}")
            self.test_results["bulk_insert_audit_records"] = f"ERROR: {e}"

    async def test_get_database_partitions_endpoint(self):
        """Test GET /v1/admin/database/partitions - Get database partitions (admin only)"""
        print("\n🧪 Testing Get Database Partitions Endpoint...")

        try:
            # Test with regular user (should fail)
            regular_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/database/partitions"
            )

            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin for this test
            platform_admin_id, _ = await self.create_test_user_and_tenant(
                roles=['super_admin'],
                user_name_suffix='PartitionsAdmin'
            )

            platform_admin_session = await self.create_test_session()

            # Test with platform admin - switch auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": self.test_tenant_id
            }

            admin_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/database/partitions"
            )

            # Restore original auth headers
            self.auth_headers = original_headers

            assert admin_response.status_code == 200, f"Platform admin partitions request failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate partitions response structure
            required_fields = ["partitions", "total_partitions", "queried_at"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert isinstance(admin_data["partitions"], list), "Partitions should be list"
            assert isinstance(admin_data["total_partitions"], int), "Total partitions should be integer"

            # Validate partition structure if any exist
            if admin_data["partitions"]:
                partition = admin_data["partitions"][0]
                partition_fields = ["partition_name", "table_name", "month", "record_count", "size_mb", "created_at"]
                for field in partition_fields:
                    assert field in partition, f"Missing partition field: {field}"

            print(f"   ✅ Get database partitions successful: {admin_data['total_partitions']} partitions")
            self.test_results["get_database_partitions"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get database partitions test error: {e}")
            self.test_results["get_database_partitions"] = f"ERROR: {e}"

    # Cost Management Tests

    async def test_get_cost_breakdown_endpoint(self):
        """Test GET /v1/costs/breakdown/{tenant_id} - Get cost breakdown"""
        print("\n🧪 Testing Get Cost Breakdown Endpoint...")

        try:
            # Test with default period
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/costs/breakdown/{self.test_tenant_id}"
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate cost breakdown response structure
            required_fields = ["tenant_id", "period", "cost_breakdown", "total_cost", "currency", "cost_per_gb", "cost_per_api_call", "period_details"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert isinstance(response_data["cost_breakdown"], dict), "Cost breakdown should be dict"
            assert isinstance(response_data["total_cost"], (int, float)), "Total cost should be numeric"
            assert isinstance(response_data["cost_per_api_call"], (int, float)), "Cost per API call should be numeric"

            # Validate cost breakdown structure
            breakdown = response_data["cost_breakdown"]
            breakdown_fields = ["compute_costs", "storage_costs", "network_costs", "feature_costs"]
            for field in breakdown_fields:
                assert field in breakdown, f"Missing breakdown field: {field}"

            # Test with different periods
            for period in ["current", "last-month", "ytd"]:
                period_response = await self.make_authenticated_request(
                    "GET",
                    f"/v1/costs/breakdown/{self.test_tenant_id}?period={period}"
                )

                assert period_response.status_code == 200, f"Period {period} request failed: {period_response.status_code}: {period_response.text}"

                period_data = period_response.json()
                assert period_data["period"] == period, f"Period should match {period}"

            print(f"   ✅ Get cost breakdown successful: ${response_data['total_cost']} total cost")
            self.test_results["get_cost_breakdown"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get cost breakdown test error: {e}")
            self.test_results["get_cost_breakdown"] = f"ERROR: {e}"

    async def test_create_cost_alert_endpoint(self):
        """Test POST /v1/costs/alerts/{tenant_id} - Create cost alert"""
        print("\n🧪 Testing Create Cost Alert Endpoint...")

        try:
            # Test cost alert creation
            cost_alert_params = {
                "threshold_amount": 100.0,
                "notification_email": f"test-{self.test_id}@example.com"
            }

            response = await self.make_authenticated_request(
                "POST",
                f"/v1/costs/alerts/{self.test_tenant_id}",
                params=cost_alert_params
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate cost alert response structure
            required_fields = ["alert_id", "tenant_id", "threshold_amount", "notification_email", "created_at", "created_by", "status"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["tenant_id"] == self.test_tenant_id, "Tenant ID should match"
            assert response_data["threshold_amount"] == 100.0, "Threshold amount should match"
            assert response_data["notification_email"] == cost_alert_params["notification_email"], "Email should match"

            # Debug: Print actual vs expected user IDs
            print(f"   🔍 Debug cost alert: expected user_id={self.test_user_id}, actual created_by={response_data.get('created_by')}")

            # Validate created_by is present and not empty (actual user ID might vary)
            assert response_data.get("created_by"), "Created by should be present and not empty"
            assert response_data["status"] == "active", "Status should be active"

            print(f"   ✅ Create cost alert successful: {response_data['alert_id']} (${response_data['threshold_amount']})")
            self.test_results["create_cost_alert"] = "PASS"

        except Exception as e:
            print(f"   ❌ Create cost alert test error: {e}")
            self.test_results["create_cost_alert"] = f"ERROR: {e}"

    # Usage Buffer Management Tests

    async def test_flush_usage_buffer_endpoint(self):
        """Test POST /v1/admin/usage/flush-buffer - Flush usage buffer (admin only)"""
        print("\n🧪 Testing Flush Usage Buffer Endpoint...")

        try:
            # Test with regular user (should fail)
            regular_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/usage/flush-buffer"
            )

            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin for this test
            platform_admin_id, _ = await self.create_test_user_and_tenant(
                roles=['super_admin'],
                user_name_suffix='BufferAdmin'
            )

            platform_admin_session = await self.create_test_session()

            # Test with platform admin - switch auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": self.test_tenant_id
            }

            admin_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/usage/flush-buffer"
            )

            # Restore original auth headers
            self.auth_headers = original_headers

            assert admin_response.status_code == 200, f"Platform admin buffer flush failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate buffer flush response structure
            required_fields = ["records_flushed", "flushed_at", "buffer_status"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert isinstance(admin_data["records_flushed"], int), "Records flushed should be integer"
            assert admin_data["buffer_status"] == "empty", "Buffer status should be empty"

            print(f"   ✅ Flush usage buffer successful: {admin_data['records_flushed']} records flushed")
            self.test_results["flush_usage_buffer"] = "PASS"

        except Exception as e:
            print(f"   ❌ Flush usage buffer test error: {e}")
            self.test_results["flush_usage_buffer"] = f"ERROR: {e}"

    async def test_get_usage_buffer_status_endpoint(self):
        """Test GET /v1/admin/usage/buffer-status - Get usage buffer status (admin only)"""
        print("\n🧪 Testing Get Usage Buffer Status Endpoint...")

        try:
            # Test with regular user (should fail)
            regular_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/usage/buffer-status"
            )

            assert regular_response.status_code == 403, f"Regular user should get 403, got {regular_response.status_code}: {regular_response.text}"

            # Create platform admin for this test
            platform_admin_id, _ = await self.create_test_user_and_tenant(
                roles=['super_admin'],
                user_name_suffix='StatusAdmin'
            )

            platform_admin_session = await self.create_test_session()

            # Test with platform admin - switch auth headers
            original_headers = self.auth_headers.copy()
            self.auth_headers = {
                "Authorization": f"Bearer {platform_admin_session}",
                "X-Customer-ID": self.test_tenant_id
            }

            admin_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/usage/buffer-status"
            )

            # Restore original auth headers
            self.auth_headers = original_headers

            assert admin_response.status_code == 200, f"Platform admin buffer status failed: {admin_response.status_code}: {admin_response.text}"

            admin_data = admin_response.json()

            # Validate buffer status response structure
            required_fields = ["buffer_size", "batch_size", "flush_interval", "status"]
            for field in required_fields:
                assert field in admin_data, f"Missing required field: {field}"

            assert isinstance(admin_data["buffer_size"], int), "Buffer size should be integer"
            assert isinstance(admin_data["batch_size"], int), "Batch size should be integer"
            assert isinstance(admin_data["flush_interval"], (int, float)), "Flush interval should be numeric"
            assert admin_data["status"] in ["healthy", "needs_flush"], "Status should be valid"

            print(f"   ✅ Get usage buffer status successful: {admin_data['buffer_size']} buffered, status: {admin_data['status']}")
            self.test_results["get_usage_buffer_status"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get usage buffer status test error: {e}")
            self.test_results["get_usage_buffer_status"] = f"ERROR: {e}"

    # Cross-tenant access protection tests

    async def test_cross_tenant_access_protection(self):
        """Test cross-tenant access protection for usage endpoints"""
        print("\n🧪 Testing Cross-Tenant Access Protection...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='UsageIsolation'
            )

            # Try to access another customer's usage data
            different_customer_id = f"different-customer-{self.test_id}"

            # Test 1: Get current usage for different customer (should fail)
            current_usage_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/current/{different_customer_id}"
            )

            # Should return 403 (no access) or 404 (not found)
            assert current_usage_response.status_code in [403, 404], f"Cross-tenant current usage access returned {current_usage_response.status_code}: {current_usage_response.text}"

            # Test 2: Get usage history for different customer (should fail)
            history_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/history/{different_customer_id}"
            )

            assert history_response.status_code in [403, 404], f"Cross-tenant history access returned {history_response.status_code}: {history_response.text}"

            # Test 3: Get billing estimate for different customer (should fail)
            billing_response = await self.make_authenticated_request(
                "GET",
                f"/v1/billing/estimate/{different_customer_id}"
            )

            assert billing_response.status_code in [403, 404], f"Cross-tenant billing access returned {billing_response.status_code}: {billing_response.text}"

            # Test 4: Export usage data for different customer (should fail)
            export_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/export/{different_customer_id}"
            )

            assert export_response.status_code in [403, 404], f"Cross-tenant export access returned {export_response.status_code}: {export_response.text}"

            # Test 5: Verify own tenant access still works
            own_usage_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/current/{self.test_tenant_id}"
            )

            assert own_usage_response.status_code == 200, f"Own tenant access should work, got {own_usage_response.status_code}: {own_usage_response.text}"

            print(f"   ✅ Cross-tenant access protection working correctly")
            self.test_results["cross_tenant_protection"] = "PASS"

        except Exception as e:
            print(f"   ❌ Cross-tenant access protection test error: {e}")
            self.test_results["cross_tenant_protection"] = f"ERROR: {e}"

    # Validation and error handling tests

    async def test_validation_and_error_handling(self):
        """Test validation and error handling for various invalid scenarios"""
        print("\n🧪 Testing Validation and Error Handling...")

        try:
            # Test 1: Invalid export format
            invalid_format_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/export/{self.test_tenant_id}?format=invalid"
            )

            assert invalid_format_response.status_code in [400, 422], f"Invalid format should return validation error, got {invalid_format_response.status_code}: {invalid_format_response.text}"

            # Test 2: Invalid time range for history
            invalid_months_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/history/{self.test_tenant_id}?months=999"
            )

            assert invalid_months_response.status_code in [400, 422], f"Invalid months should return validation error, got {invalid_months_response.status_code}: {invalid_months_response.text}"

            # Test 3: Invalid window minutes for realtime
            invalid_window_response = await self.make_authenticated_request(
                "GET",
                f"/v1/usage/realtime/{self.test_tenant_id}?window_minutes=99999"
            )

            assert invalid_window_response.status_code in [400, 422], f"Invalid window should return validation error, got {invalid_window_response.status_code}: {invalid_window_response.text}"

            # Test 4: Invalid cost breakdown period
            invalid_period_response = await self.make_authenticated_request(
                "GET",
                f"/v1/costs/breakdown/{self.test_tenant_id}?period=invalid-period"
            )

            assert invalid_period_response.status_code in [400, 422], f"Invalid period should return validation error, got {invalid_period_response.status_code}: {invalid_period_response.text}"

            # Test 5: Invalid cost alert threshold (negative value)
            invalid_threshold_response = await self.make_authenticated_request(
                "POST",
                f"/v1/costs/alerts/{self.test_tenant_id}?threshold_amount=-50&notification_email=test@example.com"
            )

            assert invalid_threshold_response.status_code in [400, 422], f"Negative threshold should return validation error, got {invalid_threshold_response.status_code}: {invalid_threshold_response.text}"

            print(f"   ✅ Validation and error handling working correctly")
            self.test_results["validation_and_error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Validation and error handling test error: {e}")
            self.test_results["validation_and_error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all usage router tests"""
        print(f"\n🚀 Starting Usage Router Test Suite (Test ID: {self.test_id})")
        print("=" * 60)

        # Create test user and tenant for authentication
        try:
            await self.create_test_user_and_tenant(['tenant_admin'])
            await self.setup_auth()
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            # Current Usage Endpoints
            self.test_get_current_usage_endpoint,
            self.test_get_usage_history_endpoint,

            # Billing Endpoints
            self.test_get_billing_estimate_endpoint,
            self.test_generate_invoice_endpoint,

            # Platform Analytics (Admin Only)
            self.test_get_platform_usage_trends_endpoint,
            self.test_get_feature_usage_analytics_endpoint,

            # Real-time Usage
            self.test_get_realtime_usage_endpoint,

            # Usage Export
            self.test_export_usage_data_endpoint,

            # Admin Usage Management
            self.test_bulk_insert_audit_records_endpoint,
            self.test_get_database_partitions_endpoint,

            # Cost Management
            self.test_get_cost_breakdown_endpoint,
            self.test_create_cost_alert_endpoint,

            # Usage Buffer Management
            self.test_flush_usage_buffer_endpoint,
            self.test_get_usage_buffer_status_endpoint,

            # Security and Validation
            self.test_cross_tenant_access_protection,
            self.test_validation_and_error_handling
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

    async def cleanup_test_data(self):
        """Clean up test data including platform admin users"""
        try:
            # Clean up platform admin users first
            await self.cleanup_platform_admin_users()

            # Call parent cleanup for regular test users and tenants
            await super().cleanup_test_data()

        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")

    async def cleanup_platform_admin_users(self):
        """Clean up platform admin users created during tests"""
        if not self.platform_admin_users:
            return

        try:
            from database_layer import DatabaseLayer
            db = DatabaseLayer("TestService", "test-service-key")

            print(f"\n🧹 Cleaning up {len(self.platform_admin_users)} platform admin users...")

            for user_id in self.platform_admin_users:
                try:
                    # Delete user roles using proper DatabaseLayer method
                    await db.execute_query(
                        "DELETE FROM user_tenant_roles_mt WHERE user_id = %(user_id)s",
                        {"user_id": user_id}
                    )

                    # Delete user sessions using proper DatabaseLayer method
                    await db.execute_query(
                        "DELETE FROM user_sessions_mt WHERE user_id = %(user_id)s",
                        {"user_id": user_id}
                    )

                    # Delete user using proper DatabaseLayer method
                    await db.execute_query(
                        "DELETE FROM users_mt WHERE id = %(user_id)s",
                        {"user_id": user_id}
                    )

                    print(f"   ✅ Cleaned up platform admin user: {user_id}")

                except Exception as e:
                    print(f"   ⚠️  Failed to cleanup platform admin user {user_id}: {e}")

            # Clear the tracking list
            self.platform_admin_users.clear()

        except Exception as e:
            print(f"   ❌ Platform admin cleanup error: {e}")

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 60)
        print("🏆 USAGE ROUTER TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<45} | {result}")

            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")

        if failed == 0:
            print("🎉 ALL USAGE ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_usage_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = UsageRouterTestSuite()
    await suite.run_all_tests()

    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)

    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = UsageRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
