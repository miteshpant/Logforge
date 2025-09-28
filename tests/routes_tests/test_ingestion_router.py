#!/usr/bin/env python3
"""
Comprehensive Ingestion Router Test Suite
Tests all ingestion endpoints and validates API responses based on actual router implementation
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime, timezone

# Add project paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_test import BaseTestSuite

class IngestionRouterTestSuite(BaseTestSuite):
    """Comprehensive test suite for all ingestion router endpoints"""

    def __init__(self):
        super().__init__("IngestionRouter")
    
    async def setup_ingestion_subscription(self):
        """Setup ingestion subscription with required features"""
        try:
            print(f"   🔧 Setting up ingestion subscription using proven pattern...")
            
            # STEP 1: Create proper tenant via API (to get UUID format)
            tenant_create_request = {
                "name": f"Ingestion Test Org {self.test_id}",
                "type": "startup",
                "primary_contact_name": f"Test Admin {self.test_id}",
                "primary_contact_email": self.test_user_email,
                "industry": "technology",
                "address": f"123 Test St, Suite {self.test_id}",
                "company_size": 50,
                "website": f"https://ingestion-test-{self.test_id}.com",
                "notes": "Created for ingestion router testing"
            }
            
            tenant_response = await self.make_authenticated_request(
                "POST",
                "/v1/tenants",
                json=tenant_create_request
            )
            
            if tenant_response.status_code != 201:
                raise Exception(f"Failed to create tenant: {tenant_response.status_code} - {tenant_response.text}")
            
            tenant_data = tenant_response.json()
            uuid_tenant_id = tenant_data["tenant_id"]
            print(f"   ✅ Tenant created with UUID: {uuid_tenant_id}")
            
            # STEP 3: Update all references to use UUID tenant_id format
            self.test_tenant_id = uuid_tenant_id
            self.auth_headers["X-Customer-ID"] = uuid_tenant_id
            
            # STEP 3: Create subscription with ALL ingestion features
            ingestion_subscription_request = {
                "subscribed_features": [
                    "ingestion.*",    # ALL ingestion features via wildcard
                    "queries.*",     # Ingestion may need query validation
                    "storage.*",     # Ingestion needs storage access
                    "alerts.*"       # Ingestion may trigger alerts
                ],
                "subscription_tier": "startup",
                "billing_cycle": "monthly",
                "auto_renew": True
            }
            
            # Create subscription using the UUID tenant_id with PUT method
            subscription_response = await self.make_authenticated_request(
                "PUT",
                f"/v1/tenants/{uuid_tenant_id}/subscription",
                json=ingestion_subscription_request
            )
            
            if subscription_response.status_code != 200:
                raise Exception(f"Failed to create ingestion subscription: {subscription_response.status_code} - {subscription_response.text}")
            
            subscription_data = subscription_response.json()
            print(f"   ✅ Ingestion subscription created: {subscription_data.get('subscription_tier', 'N/A')}")
            print(f"   📦 Features: {subscription_data.get('subscribed_features', [])}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to setup ingestion subscription: {e}")
            raise Exception(f"Ingestion subscription setup failed: {e}")

    async def test_single_log_ingestion(self):
        """Test POST /v1/ingest/logs - Single LogEntry ingestion"""
        print("\n🧪 Testing Single Log Ingestion...")

        try:
            # Prepare test log entry using correct LogEntry model fields
            test_log = {
                "msg": f"Test log entry from ingestion test {self.test_id}",
                "level": "info",
                "service": "test-service",
                "ts": datetime.now(timezone.utc).isoformat(),
                "host": "test-host",
                "attrs": {
                    "test_id": self.test_id,
                    "component": "ingestion_test"
                }
            }

            # Send ingestion request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs",
                json=test_log
            )
            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate response structure based on IngestResponse model
            required_fields = ["status", "message", "processed_count"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] == "success", f"Expected success, got {response_data['status']}"
            assert response_data["processed_count"] == 1, f"Expected 1 processed, got {response_data['processed_count']}"
            assert "log_id" in response_data, "Missing log_id field"

            print(f"   ✅ Single log ingestion successful: {response_data['message']}")
            self.test_results["single_log_ingestion"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Single log ingestion test failed: {e}")
            self.test_results["single_log_ingestion"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Single log ingestion test error: {e}")
            self.test_results["single_log_ingestion"] = f"ERROR: {e}"

    async def test_batch_log_ingestion(self):
        """Test POST /v1/ingest/logs/batch - Batch LogEntry ingestion"""
        print("\n🧪 Testing Batch Log Ingestion...")

        try:
            # Prepare batch of test logs using correct LogEntry fields
            test_logs = []
            for i in range(3):
                test_log = {
                    "msg": f"Batch test log {i+1} from test {self.test_id}",
                    "level": "info" if i % 2 == 0 else "warn",
                    "service": "batch-test-service",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "host": f"batch-host-{i}",
                    "attrs": {
                        "test_id": self.test_id,
                        "batch_index": i
                    }
                }
                test_logs.append(test_log)

            batch_data = {"logs": test_logs}

            # Send batch ingestion request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs/batch",
                json=batch_data
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()

            # Validate BatchIngestResponse structure
            required_fields = ["status", "message", "processed_count", "error_count"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"

            assert response_data["status"] == "accepted", f"Expected accepted, got {response_data['status']}"
            assert response_data["processed_count"] == 3, f"Expected 3 processed, got {response_data['processed_count']}"
            assert response_data["error_count"] == 0, f"Expected 0 errors, got {response_data['error_count']}"

            print(f"   ✅ Batch log ingestion successful: {response_data['message']}")
            self.test_results["batch_log_ingestion"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Batch log ingestion test failed: {e}")
            self.test_results["batch_log_ingestion"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Batch log ingestion test error: {e}")
            self.test_results["batch_log_ingestion"] = f"ERROR: {e}"

    async def test_bulk_log_ingestion(self):
        """Test POST /v1/ingest/logs/bulk - Bulk ingestion with dict format"""
        print("\n🧪 Testing Bulk Log Ingestion...")

        try:
            # Prepare bulk data format
            bulk_data = {
                "logs": [
                    {
                        "msg": f"Bulk test log 1 from test {self.test_id}",
                        "level": "error",
                        "service": "bulk-test-service",
                        "ts": datetime.now(timezone.utc).isoformat()
                    },
                    {
                        "msg": f"Bulk test log 2 from test {self.test_id}",
                        "level": "debug",
                        "service": "bulk-test-service",
                        "ts": datetime.now(timezone.utc).isoformat()
                    }
                ]
            }

            # Send bulk ingestion request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs/bulk",
                json=bulk_data
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert response_data["status"] == "success", f"Expected success, got {response_data['status']}"
            assert response_data["processed_count"] == 2, f"Expected 2 processed, got {response_data['processed_count']}"

            print(f"   ✅ Bulk log ingestion successful: {response_data['message']}")
            self.test_results["bulk_log_ingestion"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Bulk log ingestion test failed: {e}")
            self.test_results["bulk_log_ingestion"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Bulk log ingestion test error: {e}")
            self.test_results["bulk_log_ingestion"] = f"ERROR: {e}"

    async def test_structured_log_ingestion(self):
        """Test POST /v1/ingest/structured - Structured JSON ingestion"""
        print("\n🧪 Testing Structured Log Ingestion...")

        try:
            # Test single structured log
            structured_data = {
                "msg": f"Structured test log from test {self.test_id}",
                "level": "info",
                "service": "structured-test-service",
                "ts": datetime.now(timezone.utc).isoformat(),
                "attrs": {
                    "custom_field": "custom_value",
                    "test_id": self.test_id
                }
            }

            # Send structured ingestion request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/structured",
                json=structured_data
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert response_data["status"] == "success", f"Expected success, got {response_data['status']}"
            assert response_data["processed_count"] == 1, f"Expected 1 processed, got {response_data['processed_count']}"

            print(f"   ✅ Structured log ingestion successful: {response_data['message']}")
            self.test_results["structured_log_ingestion"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Structured log ingestion test failed: {e}")
            self.test_results["structured_log_ingestion"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Structured log ingestion test error: {e}")
            self.test_results["structured_log_ingestion"] = f"ERROR: {e}"

    async def test_auto_detect_json_ingestion(self):
        """Test POST /v1/ingest - Auto-detect JSON format"""
        print("\n🧪 Testing Auto-Detect JSON Ingestion...")

        try:
            # Test JSON auto-detection
            json_log = {
                "msg": f"Auto-detect JSON log from test {self.test_id}",
                "level": "debug",
                "service": "auto-detect-service",
                "ts": datetime.now(timezone.utc).isoformat()
            }

            # Send auto-detect request with JSON content-type
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest",
                json=json_log,
                headers={"content-type": "application/json"}
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert response_data["status"] == "success", f"Expected success, got {response_data['status']}"
            assert "detected format: json" in response_data["message"], f"Format not detected correctly: {response_data['message']}"

            print(f"   ✅ Auto-detect JSON ingestion successful: {response_data['message']}")
            self.test_results["auto_detect_json"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Auto-detect JSON test failed: {e}")
            self.test_results["auto_detect_json"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Auto-detect JSON test error: {e}")
            self.test_results["auto_detect_json"] = f"ERROR: {e}"

    async def test_auto_detect_text_ingestion(self):
        """Test POST /v1/ingest - Auto-detect text format"""
        print("\n🧪 Testing Auto-Detect Text Ingestion...")

        try:
            # Test plain text auto-detection
            text_log = f"Plain text log entry from auto-detect test {self.test_id} - this is a simple text log"

            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest",
                content=text_log.encode(),
                headers={"content-type": "text/plain"}
            )

            # Validate API response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert response_data["status"] == "success", f"Expected success, got {response_data['status']}"
            assert "detected format: text" in response_data["message"], f"Text format not detected: {response_data['message']}"

            print(f"   ✅ Auto-detect text ingestion successful: {response_data['message']}")
            self.test_results["auto_detect_text"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Auto-detect text test failed: {e}")
            self.test_results["auto_detect_text"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Auto-detect text test error: {e}")
            self.test_results["auto_detect_text"] = f"ERROR: {e}"

    async def test_invalid_log_validation(self):
        """Test ingestion validation with invalid data"""
        print("\n🧪 Testing Invalid Log Validation...")

        try:
            # Test with invalid log data (missing required "msg" field)
            invalid_log = {
                "level": "info",
                "service": "test-service",
                # Missing required "msg" field
                "ts": datetime.now(timezone.utc).isoformat()
            }

            # Send invalid ingestion request
            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs",
                json=invalid_log
            )

            # Should return 422 for validation error (Pydantic validation)
            assert response.status_code == 422, f"Expected 422 for invalid log, got {response.status_code}"

            print(f"   ✅ Invalid log properly rejected with 422 validation error")
            self.test_results["invalid_log_validation"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Invalid log validation test failed: {e}")
            self.test_results["invalid_log_validation"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Invalid log validation test error: {e}")
            self.test_results["invalid_log_validation"] = f"ERROR: {e}"

    async def test_missing_bulk_logs_field(self):
        """Test bulk ingestion error handling for missing logs field"""
        print("\n🧪 Testing Missing Bulk Logs Field...")

        try:
            # Test bulk data without "logs" field
            invalid_bulk = {
                "data": [{"msg": "test", "service": "test"}]
                # Missing required "logs" field
            }

            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs/bulk",
                json=invalid_bulk
            )

            # Should return 400 for missing logs field
            response_data = response.json()
            print(f"Response status: {response.status_code}, Response data: {response_data}")
            assert response.status_code == 400, f"Expected 400 for missing logs field, got {response.status_code}: {response.text}"

            assert "logs" in response_data["detail"], f"Error message should mention 'logs' field: {response_data['detail']}"

            print(f"   ✅ Missing logs field properly rejected with 400 error")
            self.test_results["missing_bulk_logs_field"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Missing bulk logs field test failed: {e}")
            self.test_results["missing_bulk_logs_field"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Missing bulk logs field test error: {e}")
            self.test_results["missing_bulk_logs_field"] = f"ERROR: {e}"

    async def test_empty_batch_handling(self):
        """Test batch ingestion with empty logs array"""
        print("\n🧪 Testing Empty Batch Handling...")

        try:
            # Test empty batch
            empty_batch = {"logs": []}

            response = await self.make_authenticated_request(
                "POST",
                "/v1/ingest/logs/batch",
                json=empty_batch
            )

            # Should accept empty batch (0 logs processed)
            assert response.status_code == 200, f"Expected 200 for empty batch, got {response.status_code}: {response.text}"

            response_data = response.json()
            assert response_data["processed_count"] == 0, f"Expected 0 processed, got {response_data['processed_count']}"
            assert response_data["status"] == "accepted", f"Expected accepted status, got {response_data['status']}"

            print(f"   ✅ Empty batch handled successfully: {response_data['message']}")
            self.test_results["empty_batch_handling"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Empty batch handling test failed: {e}")
            self.test_results["empty_batch_handling"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Empty batch handling test error: {e}")
            self.test_results["empty_batch_handling"] = f"ERROR: {e}"

    async def test_ingestion_response_times(self):
        """Test ingestion performance across different endpoints"""
        print("\n🧪 Testing Ingestion Response Times...")

        try:
            import time

            endpoints_to_test = [
                ("/v1/ingest/logs", "json", {"msg": f"Performance test {self.test_id}", "level": "info", "service": "perf-test"}),
                ("/v1/ingest/structured", "json", {"msg": f"Structured perf test {self.test_id}", "level": "info", "service": "perf-test"})
            ]

            response_times = []

            for endpoint, content_type, data in endpoints_to_test:
                start_time = time.time()

                if content_type == "json":
                    response = await self.make_authenticated_request("POST", endpoint, json=data)
                else:
                    response = await self.make_authenticated_request("POST", endpoint, content=data.encode())

                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                response_times.append(response_time)

                assert response.status_code == 200, f"Performance test failed for {endpoint}: {response.status_code}"

            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)

            # Ingestion should be reasonably fast
            assert max_response_time < 2000, f"Ingestion too slow: {max_response_time}ms"
            assert avg_response_time < 1000, f"Average response time too slow: {avg_response_time}ms"

            print(f"   ✅ Ingestion performance: avg={avg_response_time:.2f}ms, max={max_response_time:.2f}ms")
            self.test_results["ingestion_response_times"] = "PASS"

        except AssertionError as e:
            print(f"   ❌ Ingestion response times test failed: {e}")
            self.test_results["ingestion_response_times"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Ingestion response times test error: {e}")
            self.test_results["ingestion_response_times"] = f"ERROR: {e}"

async def run_ingestion_router_tests():
    """Run all comprehensive ingestion router tests"""
    test_suite = IngestionRouterTestSuite()

    try:
        # Setup authentication with platform admin permissions (needed for tenant creation)
        await test_suite.setup_auth(roles=['super_admin', 'tenant_admin'])
        await test_suite.setup_ingestion_subscription()

        # Run all tests
        tests = [
            test_suite.test_single_log_ingestion,
            test_suite.test_batch_log_ingestion,
            test_suite.test_bulk_log_ingestion,
            test_suite.test_structured_log_ingestion,
            test_suite.test_auto_detect_json_ingestion,
            test_suite.test_auto_detect_text_ingestion,
            test_suite.test_invalid_log_validation,
            test_suite.test_missing_bulk_logs_field,
            test_suite.test_empty_batch_handling,
            test_suite.test_ingestion_response_times
        ]

        return await test_suite.run_all_tests(tests)

    except Exception as e:
        print(f"❌ Ingestion router test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(run_ingestion_router_tests())
