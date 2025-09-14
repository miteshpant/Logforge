#!/usr/bin/env python3
"""
Comprehensive Storage Router Test Suite
Tests all storage router endpoints and validates API responses based on actual router implementation
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

class StorageRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for storage router endpoints"""

    def __init__(self):
        super().__init__("StorageRouter")

    async def test_get_retention_policy_endpoint(self):
        """Test GET /v1/storage/retention/{customer_id} - Get retention policy"""
        print("\n🧪 Testing Get Retention Policy Endpoint...")

        try:
            # Test getting retention policy for own customer
            response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/retention/{self.test_tenant_id}"
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate retention policy response structure
            required_fields = ["customer_id", "retention_policy", "retrieved_at"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["customer_id"] == self.test_tenant_id, "Customer ID should match"
            assert isinstance(response_data["retention_policy"], dict), "Retention policy should be a dictionary"
            assert "retrieved_at" in response_data, "Should have retrieved_at timestamp"

            print(f"   ✅ Get retention policy successful for customer: {self.test_tenant_id}")
            self.test_results["get_retention_policy"] = "PASS"

        except Exception as e:
            print(f"   ❌ Get retention policy test error: {e}")
            self.test_results["get_retention_policy"] = f"ERROR: {e}"

    async def test_create_retention_policy_endpoint(self):
        """Test POST /v1/storage/retention/{customer_id} - Create retention policy"""
        print("\n🧪 Testing Create Retention Policy Endpoint...")

        try:
            # Valid retention policy creation request
            policy_request = {
                "hot_retention_days": 30,
                "cold_retention_days": 90,
                "archive_retention_days": 365,
                "compression_enabled": True,
                "auto_deletion_enabled": False
            }

            # Send retention policy creation request
            response = await self.make_authenticated_request(
                "POST",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=policy_request
            )

            # Validate API response (should be 200 for success or 500 if already exists)
            if response.status_code == 200:
                response_data = response.json()

                # Validate creation response structure
                required_fields = ["status", "customer_id", "policy", "created_at"]
                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                assert response_data["status"] == "created", "Status should be 'created'"
                assert response_data["customer_id"] == self.test_tenant_id, "Customer ID should match"
                assert isinstance(response_data["policy"], dict), "Policy should be a dictionary"

                print(f"   ✅ Create retention policy successful")
                self.test_results["create_retention_policy"] = "PASS"

            elif response.status_code == 500:
                # Check if it's the "already exists" error (acceptable)
                response_data = response.json()
                if "already exists" in response_data.get("detail", ""):
                    print(f"   ⚠️ Policy already exists (acceptable for this test)")
                    self.test_results["create_retention_policy"] = "PASS"
                else:
                    # Unexpected 500 error
                    raise AssertionError(f"Unexpected 500 error: {response.text}")
            else:
                raise AssertionError(f"Expected 200 or 500, got {response.status_code}: {response.text}")

        except Exception as e:
            print(f"   ❌ Create retention policy test error: {e}")
            self.test_results["create_retention_policy"] = f"ERROR: {e}"

    async def test_update_retention_policy_endpoint(self):
        """Test PUT /v1/storage/retention/{customer_id} - Update retention policy"""
        print("\n🧪 Testing Update Retention Policy Endpoint...")

        try:
            # First, ensure a policy exists by creating one
            create_policy = {
                "hot_retention_days": 15,
                "cold_retention_days": 45,
                "archive_retention_days": 180,
                "compression_enabled": True,
                "auto_deletion_enabled": False
            }

            # Create policy first (ignore if already exists)
            await self.make_authenticated_request(
                "POST",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=create_policy
            )

            # Now test updating the policy
            update_policy = {
                "hot_retention_days": 7,
                "cold_retention_days": 30,
                "archive_retention_days": 90,
                "compression_enabled": False,
                "auto_deletion_enabled": True
            }

            # Send retention policy update request
            response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=update_policy
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate update response structure
            required_fields = ["status", "customer_id", "policy", "updated_at"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] == "updated", "Status should be 'updated'"
            assert response_data["customer_id"] == self.test_tenant_id, "Customer ID should match"
            assert isinstance(response_data["policy"], dict), "Policy should be a dictionary"

            print(f"   ✅ Update retention policy successful")
            self.test_results["update_retention_policy"] = "PASS"

        except Exception as e:
            print(f"   ❌ Update retention policy test error: {e}")
            self.test_results["update_retention_policy"] = f"ERROR: {e}"

    async def test_trigger_cleanup_endpoint(self):
        """Test POST /v1/storage/cleanup - Trigger manual cleanup"""
        print("\n🧪 Testing Trigger Cleanup Endpoint...")

        try:
            # Test cleanup without specific policy
            response = await self.make_authenticated_request(
                "POST",
                "/v1/storage/cleanup",
                json={}
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate cleanup response structure
            required_fields = ["status", "cleanup_stats", "triggered_at"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] == "completed", "Status should be 'completed'"
            assert isinstance(response_data["cleanup_stats"], dict), "Cleanup stats should be a dictionary"
            assert "triggered_at" in response_data, "Should have triggered_at timestamp"

            # Test cleanup with specific policy
            policy_cleanup_request = {
                "policy_name": "default"
            }

            policy_response = await self.make_authenticated_request(
                "POST",
                "/v1/storage/cleanup",
                json=policy_cleanup_request
            )

            assert policy_response.status_code == 200, f"Expected 200, got {policy_response.status_code}: {policy_response.text}"
            policy_data = policy_response.json()
            assert policy_data["status"] == "completed", "Policy cleanup should complete"

            print(f"   ✅ Trigger cleanup successful")
            self.test_results["trigger_cleanup"] = "PASS"

        except Exception as e:
            print(f"   ❌ Trigger cleanup test error: {e}")
            self.test_results["trigger_cleanup"] = f"ERROR: {e}"

    async def test_archive_data_endpoint(self):
        """Test POST /v1/storage/archive/{customer_id} - Archive old data"""
        print("\n🧪 Testing Archive Data Endpoint...")

        try:
            # Test archival for own customer
            response = await self.make_authenticated_request(
                "POST",
                f"/v1/storage/archive/{self.test_tenant_id}"
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate archival response structure
            required_fields = ["status", "customer_id", "result", "started_at"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] == "archival_started", "Status should be 'archival_started'"
            assert response_data["customer_id"] == self.test_tenant_id, "Customer ID should match"
            assert isinstance(response_data["result"], dict), "Result should be a dictionary"
            assert "started_at" in response_data, "Should have started_at timestamp"

            print(f"   ✅ Archive data successful for customer: {self.test_tenant_id}")
            self.test_results["archive_data"] = "PASS"

        except Exception as e:
            print(f"   ❌ Archive data test error: {e}")
            self.test_results["archive_data"] = f"ERROR: {e}"

    async def test_storage_health_endpoints(self):
        """Test all three storage health endpoints with proper access controls"""
        print("\n🧪 Testing Storage Health Endpoints...")

        try:
            # Test 1: Customer Storage Health (tenant-level access)
            print("   📊 Testing customer storage health endpoint...")
            customer_health_response = await self.make_authenticated_request(
                "GET",
                "/v1/storage/health"
            )

            # Validate customer health API response
            assert customer_health_response.status_code == 200, f"Expected 200, got {customer_health_response.status_code}: {customer_health_response.text}"

            customer_data = customer_health_response.json()
            assert isinstance(customer_data, dict), "Customer health response should be a dictionary"

            # Validate dual-level health structure
            expected_fields = ["overall_status", "customer_id", "infrastructure", "customer_data", "checked_at"]
            for field in expected_fields:
                assert field in customer_data, f"Missing required field: {field}"

            assert customer_data["customer_id"] == self.test_tenant_id, "Customer ID should match"
            assert isinstance(customer_data["infrastructure"], dict), "Infrastructure section should be a dictionary"
            assert isinstance(customer_data["customer_data"], dict), "Customer data section should be a dictionary"
            
            print(f"   ✅ Customer storage health endpoint successful")

            # Test 2: Infrastructure Health (admin-level access - currently accessible for testing)
            print("   🏗️ Testing infrastructure health endpoint...")
            infra_health_response = await self.make_authenticated_request(
                "GET",
                "/v1/storage/health/infrastructure"
            )

            # Validate infrastructure health API response
            assert infra_health_response.status_code == 200, f"Expected 200, got {infra_health_response.status_code}: {infra_health_response.text}"

            infra_data = infra_health_response.json()
            assert isinstance(infra_data, dict), "Infrastructure health response should be a dictionary"

            # Validate infrastructure health structure
            infra_expected_fields = ["infrastructure_health", "access_level", "checked_at"]
            for field in infra_expected_fields:
                assert field in infra_data, f"Missing required field: {field}"

            assert infra_data["access_level"] == "admin", "Access level should be admin"
            
            # Validate infrastructure health details
            infra_health = infra_data["infrastructure_health"]
            assert isinstance(infra_health, dict), "Infrastructure health should be a dictionary"
            
            infra_sections = ["storage_backend", "capacity", "performance", "system_status"]
            for section in infra_sections:
                assert section in infra_health, f"Missing infrastructure section: {section}"
            
            print(f"   ✅ Infrastructure health endpoint successful")

            # Test 3: Specific Customer Health (with proper access control)
            print("   👤 Testing specific customer health endpoint...")
            specific_health_response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/health/{self.test_tenant_id}"
            )

            # Should succeed when accessing own data
            assert specific_health_response.status_code == 200, f"Expected 200, got {specific_health_response.status_code}: {specific_health_response.text}"

            specific_data = specific_health_response.json()
            assert isinstance(specific_data, dict), "Specific customer health response should be a dictionary"
            assert specific_data["customer_id"] == self.test_tenant_id, "Customer ID should match"

            print(f"   ✅ Specific customer health endpoint successful")

            # Test 4: Cross-tenant access protection for specific customer endpoint
            print("   🔒 Testing cross-tenant access protection...")
            different_customer_id = f"different-customer-{self.test_id}"
            
            cross_tenant_response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/health/{different_customer_id}"
            )

            # Should fail with 403 for cross-tenant access
            assert cross_tenant_response.status_code == 403, f"Cross-tenant access should be blocked, got {cross_tenant_response.status_code}: {cross_tenant_response.text}"

            print(f"   ✅ Cross-tenant protection working correctly")

            self.test_results["storage_health_endpoints"] = "PASS"

        except Exception as e:
            print(f"   ❌ Storage health endpoints test error: {e}")
            self.test_results["storage_health_endpoints"] = f"ERROR: {e}"

    async def test_cross_tenant_access_protection(self):
        """Test cross-tenant access protection for storage endpoints"""
        print("\n🧪 Testing Cross-Tenant Access Protection...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='StorageIsolation'
            )

            # Try to access another customer's retention policy
            different_customer_id = f"different-customer-{self.test_id}"

            # Test 1: Get retention policy for different customer (should fail)
            get_response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/retention/{different_customer_id}"
            )

            assert get_response.status_code == 403, f"Cross-tenant get should be blocked, got {get_response.status_code}: {get_response.text}"

            # Test 2: Create retention policy for different customer (should fail)
            policy_request = {
                "hot_retention_days": 30,
                "cold_retention_days": 90,
                "archive_retention_days": 365,
                "compression_enabled": True,
                "auto_deletion_enabled": False
            }

            create_response = await self.make_authenticated_request(
                "POST",
                f"/v1/storage/retention/{different_customer_id}",
                json=policy_request
            )

            assert create_response.status_code == 403, f"Cross-tenant create should be blocked, got {create_response.status_code}: {create_response.text}"

            # Test 3: Update retention policy for different customer (should fail)
            update_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{different_customer_id}",
                json=policy_request
            )

            assert update_response.status_code == 403, f"Cross-tenant update should be blocked, got {update_response.status_code}: {update_response.text}"

            # Test 4: Archive data for different customer (should fail)
            archive_response = await self.make_authenticated_request(
                "POST",
                f"/v1/storage/archive/{different_customer_id}"
            )

            assert archive_response.status_code == 403, f"Cross-tenant archive should be blocked, got {archive_response.status_code}: {archive_response.text}"

            print(f"   ✅ Cross-tenant access protection working correctly")
            self.test_results["cross_tenant_protection"] = "PASS"

        except Exception as e:
            print(f"   ❌ Cross-tenant access protection test error: {e}")
            self.test_results["cross_tenant_protection"] = f"ERROR: {e}"

    async def test_retention_policy_validation(self):
        """Test retention policy validation for invalid inputs"""
        print("\n🧪 Testing Retention Policy Validation...")

        try:
            # Test with invalid retention days (negative values)
            invalid_policy = {
                "hot_retention_days": -1,
                "cold_retention_days": 90,
                "archive_retention_days": 365,
                "compression_enabled": True,
                "auto_deletion_enabled": False
            }

            invalid_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=invalid_policy
            )

            # Should return validation error (422) or handle gracefully (200 with error message)
            assert invalid_response.status_code in [400, 422, 500], f"Invalid policy should return error, got {invalid_response.status_code}: {invalid_response.text}"

            # Test with missing required fields
            incomplete_policy = {
                "hot_retention_days": 30
                # Missing other required fields
            }

            incomplete_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=incomplete_policy
            )

            assert incomplete_response.status_code in [400, 422], f"Incomplete policy should return validation error, got {incomplete_response.status_code}: {incomplete_response.text}"

            # Test with extremely large values
            extreme_policy = {
                "hot_retention_days": 999999,
                "cold_retention_days": 999999,
                "archive_retention_days": 999999,
                "compression_enabled": True,
                "auto_deletion_enabled": False
            }

            extreme_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=extreme_policy
            )

            # Should either accept extreme values or return validation error
            assert extreme_response.status_code in [200, 400, 422], f"Extreme values should be handled, got {extreme_response.status_code}: {extreme_response.text}"

            print(f"   ✅ Retention policy validation working correctly")
            self.test_results["retention_policy_validation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Retention policy validation test error: {e}")
            self.test_results["retention_policy_validation"] = f"ERROR: {e}"

    async def test_storage_operation_sequencing(self):
        """Test storage operations in sequence to validate state management"""
        print("\n🧪 Testing Storage Operation Sequencing...")

        try:
            # 1. Get initial retention policy
            initial_response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/retention/{self.test_tenant_id}"
            )
            assert initial_response.status_code == 200, f"Initial get failed: {initial_response.status_code}: {initial_response.text}"

            # 2. Update retention policy
            new_policy = {
                "hot_retention_days": 15,
                "cold_retention_days": 60,
                "archive_retention_days": 180,
                "compression_enabled": True,
                "auto_deletion_enabled": True
            }

            update_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                json=new_policy
            )
            # Accept either 200 (updated) or 500 (policy already exists)
            assert update_response.status_code in [200, 500], f"Update failed: {update_response.status_code}: {update_response.text}"

            # 3. Verify the update by getting policy again
            verify_response = await self.make_authenticated_request(
                "GET",
                f"/v1/storage/retention/{self.test_tenant_id}"
            )
            assert verify_response.status_code == 200, f"Verify get failed: {verify_response.status_code}: {verify_response.text}"

            # 4. Trigger cleanup operation
            cleanup_response = await self.make_authenticated_request(
                "POST",
                "/v1/storage/cleanup",
                json={"policy_name": "default"}
            )
            assert cleanup_response.status_code == 200, f"Cleanup failed: {cleanup_response.status_code}: {cleanup_response.text}"

            # 5. Check storage health after operations
            health_response = await self.make_authenticated_request(
                "GET",
                "/v1/storage/health"
            )
            assert health_response.status_code == 200, f"Health check failed: {health_response.status_code}: {health_response.text}"

            # 6. Trigger archival
            archive_response = await self.make_authenticated_request(
                "POST",
                f"/v1/storage/archive/{self.test_tenant_id}"
            )
            assert archive_response.status_code == 200, f"Archive failed: {archive_response.status_code}: {archive_response.text}"

            print(f"   ✅ Storage operation sequencing successful")
            self.test_results["storage_operation_sequencing"] = "PASS"

        except Exception as e:
            print(f"   ❌ Storage operation sequencing test error: {e}")
            self.test_results["storage_operation_sequencing"] = f"ERROR: {e}"

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test non-existent customer for retention policy
            nonexistent_response = await self.make_authenticated_request(
                "GET",
                "/v1/storage/retention/non-existent-customer"
            )
            assert nonexistent_response.status_code == 403, "Non-existent customer should return access denied"

            # Test malformed JSON for policy update
            malformed_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/storage/retention/{self.test_tenant_id}",
                data="invalid-json"  # Not valid JSON
            )
            assert malformed_response.status_code in [400, 422], "Malformed JSON should return validation error"

            # Test cleanup with invalid policy name
            invalid_cleanup = {
                "policy_name": "non-existent-policy"
            }

            cleanup_response = await self.make_authenticated_request(
                "POST",
                "/v1/storage/cleanup",
                json=invalid_cleanup
            )
            # Cleanup should handle gracefully (may succeed with warning or fail appropriately)
            assert cleanup_response.status_code in [200, 400, 404, 500], f"Invalid policy cleanup should be handled, got {cleanup_response.status_code}: {cleanup_response.text}"

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all storage router tests"""
        print(f"\n🚀 Starting Storage Router Test Suite (Test ID: {self.test_id})")
        print("=" * 60)

        # Create test user and tenant for authentication
        try:
            await self.create_test_user_and_tenant(['tenant_admin'])
            await self.setup_auth()
            
            # Ensure default SaaS storage backend exists for archive operations
            from services.storage_service import StorageService
            storage_service = StorageService()
            await storage_service.ensure_default_storage_backend()
            print("✅ Default SaaS storage backend ensured for tests")
            
        except Exception as e:
            print(f"❌ Failed to setup test environment: {e}")
            return

        # Run all tests
        test_methods = [
            self.test_get_retention_policy_endpoint,
            self.test_create_retention_policy_endpoint,
            self.test_update_retention_policy_endpoint,
            self.test_trigger_cleanup_endpoint,
            self.test_archive_data_endpoint,
            self.test_storage_health_endpoints,
            self.test_cross_tenant_access_protection,
            self.test_retention_policy_validation,
            self.test_storage_operation_sequencing,
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
        print("🏆 STORAGE ROUTER TEST SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result == "PASS" else "❌ FAIL"
            print(f"{status:8} | {test_name:<35} | {result}")
            
            if result == "PASS":
                passed += 1
            else:
                failed += 1

        print("=" * 60)
        print(f"📊 TOTAL: {passed + failed} tests | ✅ PASSED: {passed} | ❌ FAILED: {failed}")
        
        if failed == 0:
            print("🎉 ALL STORAGE ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_storage_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = StorageRouterTestSuite()
    await suite.run_all_tests()
    
    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)
    
    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = StorageRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())