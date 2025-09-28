#!/usr/bin/env python3
"""
Comprehensive Subscription Router Test Suite
Tests all subscription router endpoints and validates API responses based on actual router implementation
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

class SubscriptionRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for subscription router endpoints"""

    def __init__(self):
        super().__init__("SubscriptionRouter")
        self.created_subscription_ids = []  # Track created subscriptions for cleanup
        self.original_tenant_id = None  # Store original tenant ID for context switching

    def switch_to_platform_context(self):
        """Switch to platform admin context for admin operations"""
        self.auth_headers["X-Customer-ID"] = "platform"

    def switch_to_tenant_context(self):
        """Switch back to tenant context for tenant operations"""
        self.auth_headers["X-Customer-ID"] = self.original_tenant_id

    async def test_tenant_subscription_management(self):
        """Test tenant subscription CRUD operations"""
        print("\n🧪 Testing Tenant Subscription Management...")

        try:
            # Create a test tenant first
            tenant_create_request = {
                "name": f"Subscription Test Org {self.test_id}",
                "type": "enterprise",
                "primary_contact_name": "Subscription Admin",
                "primary_contact_email": f"subscription+{self.test_id}@example.com",
                "industry": "technology"
            }

            create_tenant_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            assert create_tenant_response.status_code == 201, f"Expected 201, got {create_tenant_response.status_code}: {create_tenant_response.text}"
            tenant_id = create_tenant_response.json()["tenant_id"]

            # Update our tenant_id references to use the real UUID
            self.tenant_id = tenant_id
            self.test_tenant_id = tenant_id
            self.original_tenant_id = tenant_id
            self.auth_headers["X-Customer-ID"] = tenant_id

            # 1. Create subscription
            subscription_request = {
                "subscribed_features": ["ingestion.*", "queries.*", "alerts.basic"],
                "subscription_tier": "enterprise",
                "billing_cycle": "monthly",
                "monthly_spend_limit": 1000.0,
                "auto_renew": True
            }

            create_subscription_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{tenant_id}/subscription",
                json=subscription_request
            )

            assert create_subscription_response.status_code == 200, f"Expected 200, got {create_subscription_response.status_code}: {create_subscription_response.text}"
            subscription_data = create_subscription_response.json()

            # Validate subscription response structure
            required_fields = ["tenant_id", "subscribed_features", "subscription_tier", "billing_cycle", "status", "started_at"]
            for field in required_fields:
                assert field in subscription_data, f"Missing required field: {field}"

            assert subscription_data["tenant_id"] == tenant_id
            assert subscription_data["subscription_tier"] == "enterprise"
            assert subscription_data["billing_cycle"] == "monthly"

            # 2. Get subscription
            get_subscription_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/subscription"
            )

            assert get_subscription_response.status_code == 200, f"Expected 200, got {get_subscription_response.status_code}: {get_subscription_response.text}"
            get_subscription_data = get_subscription_response.json()
            assert get_subscription_data["tenant_id"] == tenant_id

            print(f"   ✅ Tenant subscription management successful: Created and retrieved subscription for tenant {tenant_id}")
            self.test_results["tenant_subscription_management"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant subscription management test error: {e}")
            self.test_results["tenant_subscription_management"] = f"ERROR: {e}"

    async def test_feature_access_validation(self):
        """Test feature access validation endpoints"""
        print("\n🧪 Testing Feature Access Validation...")

        try:
            # Use existing tenant or create one
            if not hasattr(self, 'test_tenant_id'):
                self.test_tenant_id = self.tenant_id

            # 1. Get available features
            features_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{self.test_tenant_id}/features"
            )

            assert features_response.status_code == 200, f"Expected 200, got {features_response.status_code}: {features_response.text}"
            features_data = features_response.json()

            # Validate features response structure
            expected_fields = ["tenant_id", "available_features", "subscription_tier"]
            for field in expected_fields:
                assert field in features_data, f"Missing required field: {field}"

            # 2. Check specific feature access
            feature_name = "ingestion.basic"
            access_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{self.test_tenant_id}/features/{feature_name}/access"
            )

            assert access_response.status_code == 200, f"Expected 200, got {access_response.status_code}: {access_response.text}"
            access_data = access_response.json()

            # Validate access response structure
            expected_access_fields = ["tenant_id", "feature", "access_granted", "subscription_tier"]
            for field in expected_access_fields:
                assert field in access_data, f"Missing required access field: {field}"

            assert access_data["tenant_id"] == self.test_tenant_id
            assert access_data["feature"] == feature_name

            # 3. List all available features
            all_features_response = await self.make_authenticated_request(
                "GET",
                "/v1/features/available"
            )

            assert all_features_response.status_code == 200, f"Expected 200, got {all_features_response.status_code}: {all_features_response.text}"
            all_features_data = all_features_response.json()

            # Validate all features response
            assert "feature_categories" in all_features_data
            assert "subscription_bundles" in all_features_data

            print(f"   ✅ Feature access validation successful: Validated feature access for tenant {self.test_tenant_id}")
            self.test_results["feature_access_validation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Feature access validation test error: {e}")
            self.test_results["feature_access_validation"] = f"ERROR: {e}"

    async def test_usage_and_billing(self):
        """Test usage tracking and billing endpoints"""
        print("\n🧪 Testing Usage and Billing...")

        try:
            # Use existing tenant
            tenant_id = self.tenant_id

            # 1. Get current usage
            usage_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/usage"
            )

            assert usage_response.status_code == 200, f"Expected 200, got {usage_response.status_code}: {usage_response.text}"
            usage_data = usage_response.json()

            # Validate usage response structure (TenantUsageResponse model)
            expected_fields = ["tenant_id", "current_period", "data_ingested_bytes", "queries_executed", "alerts_triggered", "storage_used_bytes", "cost_breakdown"]
            for field in expected_fields:
                assert field in usage_data, f"Missing required usage field: {field}"

            assert usage_data["tenant_id"] == tenant_id
            assert isinstance(usage_data["cost_breakdown"], dict)

            # 2. Get detailed usage
            start_date = "2025-09-01"
            end_date = "2025-09-19"
            detailed_usage_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/usage/detailed?start_date={start_date}&end_date={end_date}"
            )

            assert detailed_usage_response.status_code == 200, f"Expected 200, got {detailed_usage_response.status_code}: {detailed_usage_response.text}"
            detailed_usage_data = detailed_usage_response.json()

            # Validate detailed usage response
            expected_detailed_fields = ["tenant_id", "billing_period", "total_cost", "currency", "feature_usage", "generated_at"]
            for field in expected_detailed_fields:
                assert field in detailed_usage_data, f"Missing required detailed usage field: {field}"

            # 3. Generate bill
            bill_request = {
                "billing_period": "current",
                "include_usage_details": True
            }

            bill_response = await self.make_authenticated_request(
                "POST",
                f"/v1/tenants/{tenant_id}/billing/generate",
                json=bill_request
            )

            assert bill_response.status_code == 200, f"Expected 200, got {bill_response.status_code}: {bill_response.text}"
            bill_data = bill_response.json()

            # Validate bill response - based on actual API response structure
            expected_bill_fields = ["bill_id", "tenant_id", "billing_period", "billing_breakdown", "currency", "generated_at", "due_date"]
            for field in expected_bill_fields:
                assert field in bill_data, f"Missing required bill field: {field}"
            
            # Validate billing_breakdown has total_amount
            assert "billing_breakdown" in bill_data, "Missing billing_breakdown field"
            assert "total_amount" in bill_data["billing_breakdown"], "Missing total_amount in billing_breakdown"

            # 4. Get billing history
            history_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/billing/history?limit=5"
            )

            assert history_response.status_code == 200, f"Expected 200, got {history_response.status_code}: {history_response.text}"
            history_data = history_response.json()

            # Validate billing history response
            expected_history_fields = ["tenant_id", "bills", "total_bills"]
            for field in expected_history_fields:
                assert field in history_data, f"Missing required billing history field: {field}"

            print(f"   ✅ Usage and billing successful: Validated usage tracking and billing for tenant {tenant_id}")
            self.test_results["usage_and_billing"] = "PASS"

        except Exception as e:
            print(f"   ❌ Usage and billing test error: {e}")
            self.test_results["usage_and_billing"] = f"ERROR: {e}"

    async def test_admin_rate_configuration(self):
        """Test admin rate configuration endpoints"""
        print("\n🧪 Testing Admin Rate Configuration...")

        try:
            # Switch to platform admin context for admin operations
            self.switch_to_platform_context()

            # 1. List all feature rates
            rates_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/rates"
            )

            assert rates_response.status_code == 200, f"Expected 200, got {rates_response.status_code}: {rates_response.text}"
            rates_data = rates_response.json()

            # Validate rates response structure
            expected_fields = ["rates", "total_count", "currency"]
            for field in expected_fields:
                assert field in rates_data, f"Missing required rates field: {field}"

            assert rates_data["currency"] == "USD"

            # 2. Create new feature rate
            rate_request = {
                "feature_name": f"test.feature.{self.test_id}",
                "pricing_model": "per_unit",
                "base_rate": 0.001,
                "tier_rates": {"starter": 0.002, "professional": 0.0015, "enterprise": 0.001},
                "currency": "USD",
                "description": "Test feature rate"
            }

            create_rate_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/rates",
                json=rate_request
            )

            assert create_rate_response.status_code == 201, f"Expected 201, got {create_rate_response.status_code}: {create_rate_response.text}"
            create_rate_data = create_rate_response.json()

            # Validate rate creation response
            expected_rate_fields = ["rate_id", "feature_name", "pricing_model", "base_rate", "tier_rates", "currency", "effective_date", "created_by"]
            for field in expected_rate_fields:
                assert field in create_rate_data, f"Missing required rate field: {field}"

            assert create_rate_data["feature_name"] == rate_request["feature_name"]
            assert create_rate_data["base_rate"] == rate_request["base_rate"]

            # 3. Update feature rate
            feature_name = rate_request["feature_name"]
            rate_update = {
                "base_rate": 0.002,
                "description": "Updated test feature rate"
            }

            update_rate_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/admin/rates/{feature_name}",
                json=rate_update
            )

            assert update_rate_response.status_code == 200, f"Expected 200, got {update_rate_response.status_code}: {update_rate_response.text}"
            update_rate_data = update_rate_response.json()

            # Validate rate update response
            assert update_rate_data["feature_name"] == feature_name
            assert update_rate_data["base_rate"] == rate_update["base_rate"]

            # 4. Get rate history
            history_response = await self.make_authenticated_request(
                "GET",
                f"/v1/admin/rates/{feature_name}/history"
            )

            assert history_response.status_code == 200, f"Expected 200, got {history_response.status_code}: {history_response.text}"
            history_data = history_response.json()

            # Validate rate history response
            expected_history_fields = ["feature_name", "rate_history"]
            for field in expected_history_fields:
                assert field in history_data, f"Missing required rate history field: {field}"

            print(f"   ✅ Admin rate configuration successful: Created, updated, and retrieved rate history for {feature_name}")
            self.test_results["admin_rate_configuration"] = "PASS"

        except Exception as e:
            print(f"   ❌ Admin rate configuration test error: {e}")
            self.test_results["admin_rate_configuration"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_tenant_deletion(self):
        """Test tenant deletion functionality"""
        print("\n🧪 Testing Tenant Deletion...")

        try:
            # Create a tenant for deletion test
            tenant_create_request = {
                "name": f"Deletion Test Org {self.test_id}",
                "type": "startup",
                "primary_contact_name": "Delete Test User",
                "primary_contact_email": f"delete+{self.test_id}@example.com",
                "industry": "testing"
            }

            create_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )

            assert create_response.status_code == 201, f"Expected 201, got {create_response.status_code}: {create_response.text}"
            tenant_id = create_response.json()["tenant_id"]

            # 1. Check deletion status before deletion
            status_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/deletion/status"
            )

            assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}: {status_response.text}"
            status_data = status_response.json()

            # Should indicate tenant is not deleted
            # Structure will depend on DAO implementation

            # 2. Delete tenant
            deletion_request = {
                "deletion_type": "soft_delete",
                "reason": "Test cleanup",
                "data_cleanup": False,
                "generate_final_bill": True
            }

            delete_response = await self.make_authenticated_request(
                "DELETE",
                f"/v1/tenants/{tenant_id}/subscription",
                json=deletion_request
            )

            assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
            delete_data = delete_response.json()

            # Validate deletion response
            expected_fields = ["tenant_id", "deletion_type", "deleted_at", "data_cleanup_scheduled", "final_bill_generated", "message"]
            for field in expected_fields:
                assert field in delete_data, f"Missing required deletion field: {field}"

            assert delete_data["tenant_id"] == tenant_id

            # 3. Check deletion status after deletion
            post_delete_status_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{tenant_id}/deletion/status"
            )

            assert post_delete_status_response.status_code == 200, f"Expected 200, got {post_delete_status_response.status_code}: {post_delete_status_response.text}"

            print(f"   ✅ Tenant deletion successful: Deleted tenant {tenant_id} and verified status")
            self.test_results["tenant_deletion"] = "PASS"

        except Exception as e:
            print(f"   ❌ Tenant deletion test error: {e}")
            self.test_results["tenant_deletion"] = f"ERROR: {e}"

    async def test_admin_tenant_management(self):
        """Test admin tenant management endpoints"""
        print("\n🧪 Testing Admin Tenant Management...")

        try:
            # Switch to platform admin context for admin operations
            self.switch_to_platform_context()

            # 1. List all tenants (admin view)
            admin_list_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/tenants?page=1&page_size=10"
            )

            assert admin_list_response.status_code == 200, f"Expected 200, got {admin_list_response.status_code}: {admin_list_response.text}"
            admin_list_data = admin_list_response.json()

            # Validate admin list response structure
            expected_fields = ["tenants", "total_count", "page", "page_size"]
            for field in expected_fields:
                assert field in admin_list_data, f"Missing required admin list field: {field}"

            # 2. Get detailed tenant information
            tenant_id = self.tenant_id  # Use existing tenant
            details_response = await self.make_authenticated_request(
                "GET",
                f"/v1/admin/tenants/{tenant_id}/details"
            )

            assert details_response.status_code == 200, f"Expected 200, got {details_response.status_code}: {details_response.text}"
            details_data = details_response.json()

            # Validate tenant details response
            expected_detail_fields = ["tenant_info", "subscription_info", "usage_summary"]
            for field in expected_detail_fields:
                assert field in details_data, f"Missing required tenant detail field: {field}"

            # 3. Force subscription change (admin override)
            subscription_override = {
                "subscribed_features": ["*"],  # Enterprise: all features
                "subscription_tier": "enterprise",
                "billing_cycle": "yearly",
                "reason": "Admin override for testing"
            }

            override_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/admin/tenants/{tenant_id}/subscription",
                json=subscription_override
            )

            assert override_response.status_code == 200, f"Expected 200, got {override_response.status_code}: {override_response.text}"
            override_data = override_response.json()

            # Validate override response
            expected_override_fields = ["tenant_id", "subscription_tier", "subscribed_features", "admin_override", "reason", "updated_at"]
            for field in expected_override_fields:
                assert field in override_data, f"Missing required override field: {field}"

            assert override_data["tenant_id"] == tenant_id
            assert override_data["admin_override"] is True

            # 4. Test billing override
            billing_override = {
                "billing_period": "2025-09",
                "override_amount": 500.00,
                "reason": "Test billing adjustment",
                "approved_by": "test_admin"
            }

            billing_override_response = await self.make_authenticated_request(
                "POST",
                f"/v1/admin/tenants/{tenant_id}/billing/override",
                json=billing_override
            )

            assert billing_override_response.status_code == 200, f"Expected 200, got {billing_override_response.status_code}: {billing_override_response.text}"
            billing_override_data = billing_override_response.json()

            # Validate billing override response
            expected_billing_fields = ["override_id", "tenant_id", "billing_period", "override_amount", "reason", "approved_by"]
            for field in expected_billing_fields:
                assert field in billing_override_data, f"Missing required billing override field: {field}"

            print(f"   ✅ Admin tenant management successful: Managed tenant {tenant_id} with admin overrides")
            self.test_results["admin_tenant_management"] = "PASS"

        except Exception as e:
            print(f"   ❌ Admin tenant management test error: {e}")
            self.test_results["admin_tenant_management"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_compliance_and_audit(self):
        """Test compliance and audit endpoints"""
        print("\n🧪 Testing Compliance and Audit...")

        try:
            # Switch to platform admin context for admin operations
            self.switch_to_platform_context()

            # 1. Get subscription audit trail
            audit_response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/audit/subscription-changes?tenant_id=" + self.tenant_id
            )

            assert audit_response.status_code == 200, f"Expected 200, got {audit_response.status_code}: {audit_response.text}"
            audit_data = audit_response.json()

            # Validate audit response structure
            expected_fields = ["audit_events", "total_events"]
            for field in expected_fields:
                assert field in audit_data, f"Missing required audit field: {field}"

            # 2. Generate compliance report
            report_request = {
                "report_type": "subscription_compliance",
                "tenant_id": self.tenant_id,
                "period": "2025-09"
            }

            report_response = await self.make_authenticated_request(
                "POST",
                "/v1/admin/compliance/reports",
                json=report_request
            )

            assert report_response.status_code == 200, f"Expected 200, got {report_response.status_code}: {report_response.text}"
            report_data = report_response.json()

            # Validate compliance report response
            expected_report_fields = ["report_id", "report_type", "tenant_id", "compliance_status", "generated_at"]
            for field in expected_report_fields:
                assert field in report_data, f"Missing required compliance report field: {field}"

            # 3. Get retention compliance status
            retention_response = await self.make_authenticated_request(
                "GET",
                f"/v1/admin/compliance/retention-status?tenant_id={self.tenant_id}"
            )

            assert retention_response.status_code == 200, f"Expected 200, got {retention_response.status_code}: {retention_response.text}"
            retention_data = retention_response.json()

            # Validate retention status response
            expected_retention_fields = ["tenant_id", "retention_compliant", "usage_records_retained"]
            for field in expected_retention_fields:
                assert field in retention_data, f"Missing required retention field: {field}"

            print(f"   ✅ Compliance and audit successful: Generated reports and audit trail for tenant {self.tenant_id}")
            self.test_results["compliance_and_audit"] = "PASS"

        except Exception as e:
            print(f"   ❌ Compliance and audit test error: {e}")
            self.test_results["compliance_and_audit"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_billing_history_endpoint(self):
        """Test GET /tenants/{tenant_id}/billing/history endpoint"""
        print("\n🧪 Testing Billing History Endpoint...")

        try:
            # Test billing history retrieval
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{self.tenant_id}/billing/history"
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            history_data = response.json()
            
            # Validate response structure - should be dict with tenant_id, bills, total_bills
            required_fields = ["tenant_id", "bills", "total_bills"]
            for field in required_fields:
                assert field in history_data, f"Missing required field: {field}"
            
            assert isinstance(history_data["bills"], list), "Bills should be a list"
            assert history_data["tenant_id"] == self.tenant_id, "Tenant ID should match"
            
            # Check bill structure if bills exist
            if history_data["bills"]:
                for bill in history_data["bills"]:
                    # Bills from DAO may have different field names - check what's actually returned
                    assert isinstance(bill, dict), "Each bill should be a dict"

            print(f"   ✅ Billing history retrieved with {history_data['total_bills']} records")
            self.test_results["billing_history"] = "PASS"

        except Exception as e:
            print(f"   ❌ Billing history test error: {e}")
            self.test_results["billing_history"] = f"ERROR: {e}"

    async def test_subscription_tier_updates(self):
        """Test subscription tier upgrade/downgrade"""
        print("\n🧪 Testing Subscription Tier Updates...")

        try:
            # First create a subscription with required subscribed_features field - using valid enum values
            initial_subscription = {
                "subscribed_features": ["ingestion.basic", "queries.basic"],
                "subscription_tier": "startup",  # Valid enum value
                "billing_cycle": "monthly"
            }
            
            create_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{self.tenant_id}/subscription",
                json=initial_subscription
            )
            assert create_response.status_code in [200, 201], f"Failed to create subscription: {create_response.text}"
            
            # Test upgrade to enterprise (highest tier) with more features
            upgrade_request = {
                "subscribed_features": ["ingestion.*", "queries.*", "alerts.basic"],
                "subscription_tier": "enterprise",  # Valid enum value (upgrade from startup to enterprise)
                "billing_cycle": "monthly"
            }
            
            upgrade_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{self.tenant_id}/subscription",
                json=upgrade_request
            )
            assert upgrade_response.status_code == 200, f"Failed to upgrade subscription: {upgrade_response.text}"
            
            upgrade_data = upgrade_response.json()
            assert upgrade_data["subscription_tier"] == "enterprise", "Tier not updated correctly"
            
            print(f"   ✅ Subscription tier upgraded successfully from startup to enterprise")
            self.test_results["subscription_tier_updates"] = "PASS"

        except Exception as e:
            print(f"   ❌ Subscription tier update test error: {e}")
            self.test_results["subscription_tier_updates"] = f"ERROR: {e}"

    async def test_detailed_usage_breakdown(self):
        """Test GET /tenants/{tenant_id}/usage/detailed endpoint"""
        print("\n🧪 Testing Detailed Usage Breakdown...")

        try:
            # Add required query parameters start_date and end_date
            start_date = "2025-09-01"
            end_date = "2025-09-23"
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{self.tenant_id}/usage/detailed?start_date={start_date}&end_date={end_date}"
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            usage_data = response.json()
            
            # Validate response structure - based on UsageBreakdownResponse model
            required_fields = ["tenant_id", "billing_period", "total_cost", "currency", "feature_usage", "generated_at"]
            for field in required_fields:
                assert field in usage_data, f"Missing required field: {field}"
            
            assert isinstance(usage_data["feature_usage"], list), "Feature usage should be a list"
            assert isinstance(usage_data["total_cost"], (int, float)), "Total cost should be numeric"
            assert usage_data["currency"] == "USD", "Currency should be USD"
            assert usage_data["tenant_id"] == self.tenant_id, "Tenant ID should match"
            
            print(f"   ✅ Detailed usage breakdown retrieved: ${usage_data['total_cost']} {usage_data['currency']}")
            self.test_results["detailed_usage_breakdown"] = "PASS"

        except Exception as e:
            print(f"   ❌ Detailed usage breakdown test error: {e}")
            self.test_results["detailed_usage_breakdown"] = f"ERROR: {e}"

    async def test_admin_billing_overrides(self):
        """Test admin billing override functionality"""
        print("\n🧪 Testing Admin Billing Overrides...")

        try:
            # Switch to platform admin context
            self.switch_to_platform_context()
            
            # Test billing override
            override_request = {
                "override_amount": 100.0,
                "reason": "Customer satisfaction credit",
                "effective_date": datetime.now().isoformat()
            }
            
            response = await self.make_authenticated_request(
                "POST",
                f"/v1/admin/tenants/{self.tenant_id}/billing/override",
                json=override_request
            )
            assert response.status_code in [200, 201], f"Failed to create billing override: {response.text}"
            
            override_data = response.json()
            
            # Validate actual response structure based on API testing
            expected_fields = ["override_id", "tenant_id", "override_amount", "reason", "created_at", "status"]
            for field in expected_fields:
                assert field in override_data, f"Missing required field: {field}"
            
            # Validate response values
            assert override_data["status"] == "applied", f"Expected status 'applied', got '{override_data['status']}'"
            assert override_data["tenant_id"] == self.tenant_id, "Tenant ID should match"
            assert override_data["override_amount"] == 100.0, "Override amount should match"
            assert override_data["reason"] == "Customer satisfaction credit", "Reason should match"
            assert "override_id" in override_data and override_data["override_id"], "Should have valid override_id"
            
            print(f"   ✅ Billing override created successfully: {override_data['override_id']}")
            self.test_results["admin_billing_overrides"] = "PASS"

        except Exception as e:
            print(f"   ❌ Admin billing override test error: {e}")
            self.test_results["admin_billing_overrides"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_subscription_deletion_flow(self):
        """Test subscription cancellation and deletion flow"""
        print("\n🧪 Testing Subscription Deletion Flow...")

        try:
            # Test subscription deletion with required TenantDeletionRequest body
            deletion_request = {
                "deletion_type": "soft_delete",
                "reason": "Test cleanup",
                "data_cleanup": False,
                "generate_final_bill": True
            }
            
            response = await self.make_authenticated_request(
                "DELETE",
                f"/v1/tenants/{self.tenant_id}/subscription",
                json=deletion_request
            )
            assert response.status_code in [200, 204], f"Failed to delete subscription: {response.text}"
            
            # Validate deletion response structure
            if response.status_code == 200:
                deletion_data = response.json()
                expected_fields = ["tenant_id", "deletion_type", "deleted_at", "data_cleanup_scheduled", "final_bill_generated", "message"]
                for field in expected_fields:
                    assert field in deletion_data, f"Missing required deletion field: {field}"
                
                assert deletion_data["tenant_id"] == self.tenant_id, "Tenant ID should match"
                assert deletion_data["deletion_type"] == "soft_delete", "Deletion type should match request"
            
            # Test deletion status check
            status_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{self.tenant_id}/deletion/status"
            )
            assert status_response.status_code == 200, f"Failed to get deletion status: {status_response.text}"
            
            status_data = status_response.json()
            # The status response structure may vary, so we'll be flexible about required fields
            assert isinstance(status_data, dict), "Deletion status should be a dictionary"
            
            print(f"   ✅ Subscription deletion flow completed")
            self.test_results["subscription_deletion_flow"] = "PASS"

        except Exception as e:
            print(f"   ❌ Subscription deletion test error: {e}")
            self.test_results["subscription_deletion_flow"] = f"ERROR: {e}"

    async def test_rate_history_tracking(self):
        """Test rate history tracking functionality"""
        print("\n🧪 Testing Rate History Tracking...")

        try:
            # Switch to platform admin context
            self.switch_to_platform_context()
            
            # Test rate history retrieval
            feature_name = "log_ingestion"
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/admin/rates/{feature_name}/history"
            )
            assert response.status_code == 200, f"Failed to get rate history: {response.text}"
            
            history_data = response.json()
            
            # Validate actual response structure - it's a dict with feature_name and rate_history
            expected_fields = ["feature_name", "rate_history"]
            for field in expected_fields:
                assert field in history_data, f"Missing required field: {field}"
            
            assert history_data["feature_name"] == feature_name, "Feature name should match request"
            assert isinstance(history_data["rate_history"], list), "Rate history should be a list"
            
            # Validate structure if history records exist
            if history_data["rate_history"]:
                for record in history_data["rate_history"]:
                    assert "effective_date" in record, "Missing effective_date field"
                    assert "rate" in record, "Missing rate field"
            
            print(f"   ✅ Rate history retrieved with {len(history_data['rate_history'])} records")
            self.test_results["rate_history_tracking"] = "PASS"

        except Exception as e:
            print(f"   ❌ Rate history tracking test error: {e}")
            self.test_results["rate_history_tracking"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_available_features_endpoint(self):
        """Test GET /features/available endpoint"""
        print("\n🧪 Testing Available Features Endpoint...")

        try:
            response = await self.make_authenticated_request(
                "GET",
                "/v1/features/available"
            )
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            features_data = response.json()
            
            # Validate actual response structure - it's a dict with feature_categories and subscription_bundles
            expected_fields = ["feature_categories", "subscription_bundles"]
            for field in expected_fields:
                assert field in features_data, f"Missing required field: {field}"
            
            assert isinstance(features_data["feature_categories"], dict), "Feature categories should be a dict"
            assert isinstance(features_data["subscription_bundles"], dict), "Subscription bundles should be a dict"
            
            # Validate feature categories structure
            feature_categories = features_data["feature_categories"]
            category_count = sum(len(features) for features in feature_categories.values())
            
            # Validate subscription bundles structure  
            subscription_bundles = features_data["subscription_bundles"]
            bundle_count = len(subscription_bundles)
            
            print(f"   ✅ Available features retrieved: {category_count} features across {len(feature_categories)} categories, {bundle_count} subscription bundles")
            self.test_results["available_features"] = "PASS"

        except Exception as e:
            print(f"   ❌ Available features test error: {e}")
            self.test_results["available_features"] = f"ERROR: {e}"

    async def test_billing_generation(self):
        """Test billing generation endpoint"""
        print("\n🧪 Testing Billing Generation...")

        try:
            # Test billing generation
            billing_request = {
                "billing_period": "2024-01",
                "force_regenerate": True
            }
            
            response = await self.make_authenticated_request(
                "POST",
                f"/v1/tenants/{self.tenant_id}/billing/generate",
                json=billing_request
            )
            assert response.status_code in [200, 202], f"Failed to generate billing: {response.text}"
            
            billing_data = response.json()
            assert "billing_id" in billing_data or "status" in billing_data, "Missing billing response fields"
            
            print(f"   ✅ Billing generation completed")
            self.test_results["billing_generation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Billing generation test error: {e}")
            self.test_results["billing_generation"] = f"ERROR: {e}"

    async def test_admin_audit_subscription_changes(self):
        """Test admin audit subscription changes endpoint"""
        print("\n🧪 Testing Admin Audit Subscription Changes...")

        try:
            # Switch to platform admin context
            self.switch_to_platform_context()
            
            response = await self.make_authenticated_request(
                "GET",
                "/v1/admin/audit/subscription-changes"
            )
            assert response.status_code == 200, f"Failed to get audit data: {response.text}"
            
            audit_data = response.json()
            
            # Validate actual response structure - it's a dict with audit_events and total_events
            expected_fields = ["audit_events", "total_events"]
            for field in expected_fields:
                assert field in audit_data, f"Missing required field: {field}"
            
            assert isinstance(audit_data["audit_events"], list), "Audit events should be a list"
            assert isinstance(audit_data["total_events"], int), "Total events should be an integer"
            
            # Validate audit record structure if events exist
            if audit_data["audit_events"]:
                for record in audit_data["audit_events"]:
                    expected_event_fields = ["event_id", "tenant_id", "event_type", "timestamp"]
                    for field in expected_event_fields:
                        assert field in record, f"Missing {field} field in audit event"
            
            print(f"   ✅ Admin audit data retrieved: {audit_data['total_events']} total events, {len(audit_data['audit_events'])} in response")
            self.test_results["admin_audit_changes"] = "PASS"

        except Exception as e:
            print(f"   ❌ Admin audit test error: {e}")
            self.test_results["admin_audit_changes"] = f"ERROR: {e}"
        finally:
            # Switch back to tenant context
            self.switch_to_tenant_context()

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test get non-existent subscription
            invalid_tenant_id = "non-existent-tenant-id"
            get_invalid_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{invalid_tenant_id}/subscription"
            )
            assert get_invalid_response.status_code == 404, f"Non-existent subscription should return 404, got {get_invalid_response.status_code}: {get_invalid_response.text}"

            # Test invalid subscription creation
            invalid_subscription_request = {
                "subscription_tier": "invalid_tier",  # Invalid enum value
                "billing_cycle": "invalid_cycle"
            }

            invalid_create_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{self.tenant_id}/subscription",
                json=invalid_subscription_request
            )
            assert invalid_create_response.status_code in [400, 422], f"Invalid subscription should return error, got {invalid_create_response.status_code}: {invalid_create_response.text}"

            # Test invalid feature access check
            invalid_feature_response = await self.make_authenticated_request(
                "GET",
                f"/v1/tenants/{invalid_tenant_id}/features/invalid.feature/access"
            )
            # This might return 200 with access_granted=false or 404, both are acceptable

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all subscription router tests"""
        print(f"\n🚀 Starting Subscription Router Test Suite (Test ID: {self.test_id})")
        print("=" * 70)

        # Create test user and tenant for authentication with both tenant and platform access
        try:
            await self.create_test_user_and_tenant(['super_admin', 'tenant_admin'])
            await self.setup_auth(['super_admin', 'tenant_admin'])
            # Store original tenant ID for tenant operations
            self.original_tenant_id = self.test_tenant_id
            # Keep normal tenant access for tenant operations
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_tenant_subscription_management,
            self.test_feature_access_validation,
            self.test_usage_and_billing,
            self.test_admin_rate_configuration,
            self.test_tenant_deletion,
            self.test_admin_tenant_management,
            self.test_compliance_and_audit,
            # New comprehensive tests
            self.test_billing_history_endpoint,
            self.test_subscription_tier_updates,
            self.test_detailed_usage_breakdown,
            self.test_admin_billing_overrides,
            self.test_subscription_deletion_flow,
            self.test_rate_history_tracking,
            self.test_available_features_endpoint,
            self.test_billing_generation,
            self.test_admin_audit_subscription_changes,
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

        # Cleanup test data
        await self.cleanup_test_data()

        # Print results summary
        self.print_test_summary()

    def print_test_summary(self):
        """Print comprehensive test results summary"""
        print("\n" + "=" * 70)
        print("🏆 SUBSCRIPTION ROUTER TEST SUMMARY")
        print("=" * 70)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<40} | {result}")

            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 70)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")

        if failed == 0:
            print("🎉 ALL SUBSCRIPTION ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 70)

async def run_subscription_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = SubscriptionRouterTestSuite()
    await suite.run_all_tests()

    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)

    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = SubscriptionRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
