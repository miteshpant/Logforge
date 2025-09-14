#!/usr/bin/env python3
"""
Health Router Test Suite
Tests the health router endpoints and validates API responses
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add project paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_test import BaseTestSuite

class HealthRouterTestSuite(BaseTestSuite):
    """Test suite for health router endpoints"""
    
    def __init__(self):
        super().__init__("HealthRouter")
    
    async def test_health_endpoint(self):
        """Test GET /health endpoint"""
        print("\n🧪 Testing Health Endpoint...")
        
        try:
            # Test health endpoint (no auth required)
            response = await self.make_authenticated_request("GET", "/health")
            
            # Validate response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            response_data = response.json()
            
            # Validate required fields based on actual HealthResponse model
            required_fields = ["status", "timestamp", "services"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"
            
            # Validate status is "healthy"
            assert response_data["status"] == "healthy", f"Expected status 'healthy', got {response_data['status']}"
            
            # Validate services health
            services = response_data["services"]
            assert isinstance(services, dict), "Services should be a dictionary"
            
            # Should have basic services
            expected_services = ["api", "database", "clickhouse", "storage"]
            for service in expected_services:
                assert service in services, f"Missing service: {service}"
                assert services[service] == "healthy", f"Service {service} not healthy: {services[service]}"
            
            # Validate timestamp format
            timestamp = response_data["timestamp"]
            assert isinstance(timestamp, str), "Timestamp should be string"
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))  # Validate ISO format
            
            print(f"   ✅ Health endpoint response: {response_data['status']} with {len(services)} services")
            self.test_results["health_endpoint"] = "PASS"
            
        except AssertionError as e:
            print(f"   ❌ Health endpoint test failed: {e}")
            self.test_results["health_endpoint"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Health endpoint test error: {e}")
            self.test_results["health_endpoint"] = f"ERROR: {e}"
    
    async def test_root_endpoint(self):
        """Test GET / root endpoint"""
        print("\n🧪 Testing Root Endpoint...")
        
        try:
            # Test root endpoint (no auth required)
            response = await self.make_authenticated_request("GET", "/")
            
            # Validate response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            response_data = response.json()
            
            # Validate required fields
            required_fields = ["message", "version", "docs", "features"]
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"
            
            # Validate message content
            assert "Logforge" in response_data["message"], "Message should contain 'Logforge'"
            
            # Validate version format
            version = response_data["version"]
            assert isinstance(version, str), "Version should be string"
            assert len(version) > 0, "Version should not be empty"
            
            # Validate docs field
            assert response_data["docs"] == "/docs", "Docs should point to /docs"
            
            # Validate features list
            features = response_data["features"]
            assert isinstance(features, list), "Features should be a list"
            assert len(features) > 0, "Should have at least one feature"
            
            expected_features = ["ingestion", "query", "dashboard", "alert"]
            for expected in expected_features:
                found = any(expected.lower() in feature.lower() for feature in features)
                assert found, f"Missing expected feature category: {expected}"
            
            print(f"   ✅ Root endpoint response with {len(features)} features")
            self.test_results["root_endpoint"] = "PASS"
            
        except AssertionError as e:
            print(f"   ❌ Root endpoint test failed: {e}")
            self.test_results["root_endpoint"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Root endpoint test error: {e}")
            self.test_results["root_endpoint"] = f"ERROR: {e}"
    
    async def test_health_response_times(self):
        """Test health endpoint response times"""
        print("\n🧪 Testing Health Response Times...")
        
        try:
            import time
            
            # Test multiple requests to check consistency
            response_times = []
            
            for i in range(5):
                start_time = time.time()
                response = await self.make_authenticated_request("GET", "/health")
                end_time = time.time()
                
                assert response.status_code == 200, f"Request {i+1} failed with {response.status_code}"
                response_time = (end_time - start_time) * 1000  # Convert to ms
                response_times.append(response_time)
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            # Health endpoint should be fast (under 1 second)
            assert max_response_time < 1000, f"Health endpoint too slow: {max_response_time}ms"
            assert avg_response_time < 500, f"Average response time too slow: {avg_response_time}ms"
            
            print(f"   ✅ Health response times: avg={avg_response_time:.2f}ms, max={max_response_time:.2f}ms")
            self.test_results["health_response_times"] = "PASS"
            
        except AssertionError as e:
            print(f"   ❌ Health response times test failed: {e}")
            self.test_results["health_response_times"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Health response times test error: {e}")
            self.test_results["health_response_times"] = f"ERROR: {e}"
    
    async def test_health_without_auth(self):
        """Test health endpoints work without authentication"""
        print("\n🧪 Testing Health Endpoints Without Auth...")
        
        try:
            import httpx
            
            # Test without any headers
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test health endpoint without auth
                response = await client.get(f"{self.base_url}/health")
                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                response_data = response.json()
                assert response_data["status"] == "healthy", "Health check should work without auth"
                
                # Test root endpoint without auth
                response = await client.get(f"{self.base_url}/")
                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                response_data = response.json()
                assert "Logforge" in response_data["message"], "Root endpoint should work without auth"
            
            print(f"   ✅ Health endpoints accessible without authentication")
            self.test_results["health_without_auth"] = "PASS"
            
        except AssertionError as e:
            print(f"   ❌ Health without auth test failed: {e}")
            self.test_results["health_without_auth"] = f"FAIL: {e}"
        except Exception as e:
            print(f"   ❌ Health without auth test error: {e}")
            self.test_results["health_without_auth"] = f"ERROR: {e}"

async def run_health_router_tests():
    """Run all health router tests"""
    test_suite = HealthRouterTestSuite()
    
    try:
        # Health endpoints don't require authentication, but we'll set it up for consistency
        await test_suite.setup_auth()
        
        # Run all tests
        tests = [
            test_suite.test_health_endpoint,
            test_suite.test_root_endpoint, 
            test_suite.test_health_response_times,
            test_suite.test_health_without_auth
        ]
        
        return await test_suite.run_all_tests(tests)
        
    except Exception as e:
        print(f"❌ Health router test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(run_health_router_tests())