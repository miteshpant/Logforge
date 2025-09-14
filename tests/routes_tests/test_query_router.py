#!/usr/bin/env python3
"""
Comprehensive Query Router Test Suite
Tests all query router endpoints and validates API responses based on actual router implementation
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

class QueryRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for query router endpoints"""

    def __init__(self):
        super().__init__("QueryRouter")

    async def test_advanced_query_endpoint(self):
        """Test POST /v1/query/advanced - Advanced query with filters and aggregations"""
        print("\n🧪 Testing Advanced Query Endpoint...")

        try:
            # Valid advanced query request
            query_request = {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T23:59:59Z",
                "filters": [
                    {
                        "field": "level",
                        "operator": "eq",
                        "value": "ERROR"
                    },
                    {
                        "field": "service",
                        "operator": "contains",
                        "value": "test"
                    }
                ],
                "text_search": "error",
                "sort_field": "ts",
                "sort_order": "desc",
                "limit": 100,
                "offset": 0
            }

            # Send advanced query request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/query/advanced",
                json=query_request
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate QueryResponse structure
            required_fields = ["logs", "total_count", "execution_time_ms"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["logs"], list), "Logs should be a list"
            assert isinstance(response_data["total_count"], int), "Total count should be an integer"
            assert isinstance(response_data["execution_time_ms"], (int, float)) or response_data["execution_time_ms"] is None, "Execution time should be a number"

            print(f"   ✅ Advanced query successful: Found {response_data['total_count']} logs")
            self.test_results["advanced_query"] = "PASS"

        except Exception as e:
            print(f"   ❌ Advanced query test error: {e}")
            self.test_results["advanced_query"] = f"ERROR: {e}"

    async def test_aggregate_query_endpoint(self):
        """Test POST /v1/query/aggregate - Aggregation query"""
        print("\n🧪 Testing Aggregate Query Endpoint...")

        try:
            # Valid aggregation request
            aggregate_request = {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T23:59:59Z",
                "group_by": ["service", "level"],
                "aggregations": [
                    {
                        "field": "service",
                        "type": "count"
                    }
                ],
                "filters": [
                    {
                        "field": "level",
                        "operator": "in",
                        "value": ["ERROR", "WARN"]
                    }
                ]
            }

            # Send aggregation request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/query/aggregate",
                json=aggregate_request
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate aggregation response structure
            required_fields = ["aggregations", "group_by", "total_groups", "execution_time_ms", "customer_id"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["aggregations"], dict), "Aggregations should be a dictionary"
            assert isinstance(response_data["group_by"], list), "Group by should be a list"

            print(f"   ✅ Aggregation query successful: {response_data['total_groups']} groups")
            self.test_results["aggregate_query"] = "PASS"

        except Exception as e:
            print(f"   ❌ Aggregation query test error: {e}")
            self.test_results["aggregate_query"] = f"ERROR: {e}"

    async def test_timeseries_query_endpoint(self):
        """Test POST /v1/query/timeseries - Timeseries query"""
        print("\n🧪 Testing Timeseries Query Endpoint...")

        try:
            # Valid timeseries request
            timeseries_request = {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T23:59:59Z",
                "interval": "1h",
                "metrics": ["count"],
                "filters": [
                    {
                        "field": "level",
                        "operator": "eq",
                        "value": "ERROR"
                    }
                ],
                "group_by": ["service"],
                "aggregations": [
                    {
                        "field": "*",
                        "type": "count"
                    }
                ],
                "granularity": "hour"
            }

            # Send timeseries request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/query/timeseries",
                json=timeseries_request
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate timeseries response structure
            required_fields = ["buckets", "aggregations", "total_count", "execution_time_ms", "customer_id"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert isinstance(response_data["buckets"], list), "Buckets should be a list"
            assert isinstance(response_data["aggregations"], dict), "Aggregations should be a dictionary"

            print(f"   ✅ Timeseries query successful: {len(response_data['buckets'])} time buckets")
            self.test_results["timeseries_query"] = "PASS"

        except Exception as e:
            print(f"   ❌ Timeseries query test error: {e}")
            self.test_results["timeseries_query"] = f"ERROR: {e}"

    async def test_saved_queries_crud(self):
        """Test saved queries CRUD operations"""
        print("\n🧪 Testing Saved Queries CRUD Operations...")

        try:
            # 1. Create/Save a query
            save_request = {
                "name": f"Test Query {self.test_id}",
                "description": "Test query for CRUD operations",
                "query_definition": {
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-01T23:59:59Z",
                    "filters": [
                        {
                            "field": "level",
                            "operator": "eq",
                            "value": "ERROR"
                        }
                    ]
                },
                "query_type": "advanced",
                "created_by": "test-user",
                "tags": ["test", "error-logs"]
            }

            # Save query
            save_response = await self.make_authenticated_request(
                "POST",
                "/v1/query/saved",
                json=save_request
            )

            assert save_response.status_code == 200, f"Expected 200, got {save_response.status_code}: {save_response.text}"
            save_data = save_response.json()
            assert save_data["status"] == "saved"
            assert "query_id" in save_data
            query_id = save_data["query_id"]

            # 2. List saved queries
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/query/saved"
            )

            assert list_response.status_code == 200, f"Expected 200, got {list_response.status_code}: {list_response.text}"
            list_data = list_response.json()
            assert "saved_queries" in list_data

            # 3. Get specific saved query
            get_response = await self.make_authenticated_request(
                "GET",
                f"/v1/query/saved/{query_id}"
            )

            assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}: {get_response.text}"
            get_data = get_response.json()
            assert get_data["name"] == f"Test Query {self.test_id}"

            # 4. Update saved query
            update_request = {
                "name": f"Updated Test Query {self.test_id}",
                "description": "Updated description"
            }

            update_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/query/saved/{query_id}",
                json=update_request
            )

            assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
            update_data = update_response.json()
            assert update_data["status"] == "updated"

            # 5. Delete saved query
            delete_response = await self.make_authenticated_request(
                "DELETE",
                f"/v1/query/saved/{query_id}"
            )

            assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
            delete_data = delete_response.json()
            assert delete_data["status"] == "deleted"

            # 6. Verify deletion - should return 404
            get_deleted_response = await self.make_authenticated_request(
                "GET",
                f"/v1/query/saved/{query_id}"
            )

            assert get_deleted_response.status_code == 404, "Deleted query should return 404"

            print(f"   ✅ Saved queries CRUD operations successful")
            self.test_results["saved_queries_crud"] = "PASS"

        except Exception as e:
            print(f"   ❌ Saved queries CRUD test error: {e}")
            self.test_results["saved_queries_crud"] = f"ERROR: {e}"

    async def test_query_validation_endpoint(self):
        """Test POST /v1/query/validate - Query validation"""
        print("\n🧪 Testing Query Validation Endpoint...")

        try:
            # Valid query structure
            valid_query = {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-02T00:00:00Z",
                "filters": [
                    {
                        "field": "level",
                        "operator": "eq",
                        "value": "ERROR"
                    },
                    {
                        "field": "service",
                        "operator": "contains",
                        "value": "api"
                    }
                ],
                "aggregations": [
                    {
                        "field": "service",
                        "type": "count"
                    }
                ]
            }

            # Validate valid query
            response = await self.make_authenticated_request(
                "POST",
                "/v1/query/validate",
                json=valid_query
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert "valid" in data
            assert "errors" in data
            assert "warnings" in data

            # Test invalid query structure
            invalid_query = {
                "start_time": "2024-01-02T00:00:00Z",
                "end_time": "2024-01-01T00:00:00Z",  # End before start
                "filters": [
                    {
                        "field": "level"
                        # Missing operator and value
                    }
                ]
            }

            invalid_response = await self.make_authenticated_request(
                "POST",
                "/v1/query/validate",
                json=invalid_query
            )

            assert invalid_response.status_code == 200, f"Expected 200, got {invalid_response.status_code}: {invalid_response.text}"
            invalid_data = invalid_response.json()
            assert "valid" in invalid_data
            assert invalid_data["valid"] is False
            assert len(invalid_data["errors"]) > 0

            print(f"   ✅ Query validation successful")
            self.test_results["query_validation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Query validation test error: {e}")
            self.test_results["query_validation"] = f"ERROR: {e}"

    async def test_export_functionality(self):
        """Test POST /v1/export - Export query results in JSON and CSV"""
        print("\n🧪 Testing Export Functionality...")

        try:
            # Test JSON export
            json_export_request = {
                "query": {
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-01T23:59:59Z",
                    "filters": [
                        {
                            "field": "level",
                            "operator": "eq",
                            "value": "ERROR"
                        }
                    ],
                    "limit": 10
                },
                "format": "json"
            }

            json_response = await self.make_authenticated_request(
                "POST",
                "/v1/export",
                json=json_export_request
            )

            assert json_response.status_code == 200, f"Expected 200, got {json_response.status_code}: {json_response.text}"
            json_data = json_response.json()
            assert "data" in json_data
            assert "format" in json_data
            assert "count" in json_data
            assert json_data["format"] == "json"
            assert isinstance(json_data["data"], list)

            # Test CSV export
            csv_export_request = {
                "query": {
                    "start_time": "2024-01-01T00:00:00Z",
                    "end_time": "2024-01-01T23:59:59Z",
                    "filters": [
                        {
                            "field": "service",
                            "operator": "contains",
                            "value": "test"
                        }
                    ],
                    "limit": 5
                },
                "format": "csv"
            }

            csv_response = await self.make_authenticated_request(
                "POST",
                "/v1/export",
                json=csv_export_request
            )

            assert csv_response.status_code == 200, f"Expected 200, got {csv_response.status_code}: {csv_response.text}"
            csv_data = csv_response.json()
            assert "data" in csv_data
            assert "format" in csv_data
            assert csv_data["format"] == "csv"
            assert isinstance(csv_data["data"], str)
            assert "timestamp,level,service,message,host" in csv_data["data"]  # CSV header

            print(f"   ✅ Export functionality successful: JSON and CSV formats working")
            self.test_results["export_functionality"] = "PASS"

        except Exception as e:
            print(f"   ❌ Export functionality test error: {e}")
            self.test_results["export_functionality"] = f"ERROR: {e}"

    async def test_basic_logs_retrieval(self):
        """Test GET /v1/logs - Basic logs retrieval endpoint (M0 compatibility)"""
        print("\n🧪 Testing Basic Logs Retrieval...")

        try:
            # Test with query parameters
            response = await self.make_authenticated_request(
                "GET",
                "/v1/logs?service=test-service&level=ERROR&limit=50&offset=0"
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            
            # Validate basic logs response structure
            required_fields = ["logs", "total", "limit", "offset", "customer_id"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

            assert isinstance(data["logs"], list), "Logs should be a list"
            assert isinstance(data["total"], int), "Total should be an integer"

            # Test logs structure if logs exist
            if data["logs"]:
                log = data["logs"][0]
                expected_log_fields = ["ts", "service", "level", "msg", "host", "customer_id"]
                for field in expected_log_fields:
                    assert field in log, f"Missing log field: {field}"

            print(f"   ✅ Basic logs retrieval successful: Found {data['total']} logs")
            self.test_results["basic_logs_retrieval"] = "PASS"

        except Exception as e:
            print(f"   ❌ Basic logs retrieval test error: {e}")
            self.test_results["basic_logs_retrieval"] = f"ERROR: {e}"

    async def test_multi_tenant_isolation(self):
        """Test multi-tenant isolation across query endpoints"""
        print("\n🧪 Testing Multi-Tenant Isolation...")

        try:
            # Create a test user and tenant for this specific test
            test_user_id, test_tenant_id = await self.create_test_user_and_tenant(
                roles=['tenant_admin'],
                user_name_suffix='Isolation'
            )

            # Save query for first customer
            save_request = {
                "name": f"Customer 1 Query {self.test_id}",
                "query_definition": {"filters": []},
                "created_by": "customer1-user"
            }

            save_response = await self.make_authenticated_request(
                "POST",
                "/v1/query/saved",
                json=save_request
            )

            assert save_response.status_code == 200, f"Expected 200, got {save_response.status_code}: {save_response.text}"
            query_id = save_response.json()["query_id"]

            # Try to access with different tenant (should fail due to isolation)
            different_tenant_id = f"different-tenant-{self.test_id}"
            
            # Make request with different customer ID header to test tenant isolation
            get_response = await self.make_authenticated_request(
                "GET",
                f"/v1/query/saved/{query_id}",
                headers={
                    "X-Customer-ID": different_tenant_id  # Override tenant ID
                }
            )

            # Should return 403 due to tenant isolation (middleware blocks access)
            assert get_response.status_code == 403, f"Cross-tenant access should be blocked, got {get_response.status_code}: {get_response.text}"

            # List queries for second customer should return 403 (no access to that tenant)
            list_response = await self.make_authenticated_request(
                "GET",
                "/v1/query/saved",
                headers={
                    "X-Customer-ID": different_tenant_id  # Override tenant ID
                }
            )

            assert list_response.status_code == 403, f"Expected 403 for cross-tenant list access, got {list_response.status_code}: {list_response.text}"
            
            # 403 response means no access to tenant - this is the expected behavior
            # No need to check the response data since access is properly blocked

            print(f"   ✅ Multi-tenant isolation working correctly")
            self.test_results["multi_tenant_isolation"] = "PASS"

        except Exception as e:
            print(f"   ❌ Multi-tenant isolation test error: {e}")
            self.test_results["multi_tenant_isolation"] = f"ERROR: {e}"

    async def test_error_handling(self):
        """Test error handling for various invalid scenarios"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test empty advanced query
            empty_response = await self.make_authenticated_request(
                "POST",
                "/v1/query/advanced",
                json={}
            )
            assert empty_response.status_code == 422, "Empty query should return validation error"

            # Test malformed query
            malformed_query = {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-01T23:59:59Z",
                "filters": "not-a-list"  # Should be a list
            }

            malformed_response = await self.make_authenticated_request(
                "POST",
                "/v1/query/advanced",
                json=malformed_query
            )
            assert malformed_response.status_code == 422, "Malformed query should return validation error"

            # Test invalid query ID for saved queries
            invalid_id_response = await self.make_authenticated_request(
                "GET",
                "/v1/query/saved/invalid-id"
            )
            assert invalid_id_response.status_code in [400, 404], "Invalid query ID should return error"

            # Test update non-existent query
            update_response = await self.make_authenticated_request(
                "PUT",
                "/v1/query/saved/non-existent-id",
                json={"name": "Updated Name"}
            )
            assert update_response.status_code in [400, 404], f"Non-existent query update should return error, got {update_response.status_code}: {update_response.text}"

            print(f"   ✅ Error handling working correctly")
            self.test_results["error_handling"] = "PASS"

        except Exception as e:
            print(f"   ❌ Error handling test error: {e}")
            self.test_results["error_handling"] = f"ERROR: {e}"

    async def run_all_tests(self):
        """Execute all query router tests"""
        print(f"\n🚀 Starting Query Router Test Suite (Test ID: {self.test_id})")
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
            self.test_advanced_query_endpoint,
            self.test_aggregate_query_endpoint,
            self.test_timeseries_query_endpoint,
            self.test_saved_queries_crud,
            self.test_query_validation_endpoint,
            self.test_export_functionality,
            self.test_basic_logs_retrieval,
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
        print("🏆 QUERY ROUTER TEST SUMMARY")
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
            print("🎉 ALL QUERY ROUTER TESTS PASSED!")
        else:
            print(f"⚠️  {failed} test(s) failed - review errors above")

        print("=" * 60)

async def run_query_router_tests():
    """Main test runner function for integration with run_route_tests.py"""
    suite = QueryRouterTestSuite()
    await suite.run_all_tests()
    
    # Return True if all tests passed, False otherwise
    passed_tests = sum(1 for result in suite.test_results.values() if result == "PASS")
    total_tests = len(suite.test_results)
    
    return passed_tests == total_tests

async def main():
    """Main test runner"""
    suite = QueryRouterTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())