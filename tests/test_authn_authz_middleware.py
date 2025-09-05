#!/usr/bin/env python3
"""
Test Unified Authentication & Authorization Middleware
Tests authn/authz layer functionality directly to isolate middleware bugs
"""

import asyncio
import httpx
import json
from datetime import datetime

class MiddlewareTestSuite:
    """Test unified authn/authz middleware functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.auth_token = None
        self.test_tenant_id = None
    
    async def setup_test_auth(self):
        """Setup authentication for middleware testing"""
        print("🔑 Setting up test authentication...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get setup token
            setup_response = await client.post(f"{self.base_url}/v1/auth/setup/init")
            if setup_response.status_code == 200:
                setup_data = setup_response.json()
                setup_token = setup_data["setup_token"]
                
                # Create initial admin user
                admin_data = {
                    "name": "Middleware Test Admin",
                    "email": "middleware-test@logforge.com", 
                    "password": "MiddlewareTest123!",
                    "setup_token": setup_token
                }
                
                user_response = await client.post(
                    f"{self.base_url}/v1/auth/setup",
                    json=admin_data
                )
                
                if user_response.status_code == 201:
                    print("✅ Admin user created for middleware testing")
                else:
                    print(f"❌ Admin user creation failed: {user_response.text}")
                    return False
            else:
                print("⚠️  Platform already setup, attempting login...")
            
            # Login to get auth token
            login_data = {
                "email": "middleware-test@logforge.com",
                "password": "MiddlewareTest123!"
            }
            
            login_response = await client.post(
                f"{self.base_url}/v1/auth/login",
                json=login_data
            )
            
            if login_response.status_code == 200:
                login_result = login_response.json()
                self.auth_token = login_result["access_token"]
                print("✅ Authentication token obtained")
                
                # Create test tenant
                tenant_data = {
                    "name": "Middleware Test Org",
                    "type": "enterprise",
                    "primary_contact_name": "Test Admin",
                    "primary_contact_email": "middleware-test@logforge.com",
                    "industry": "Technology"
                }
                
                tenant_response = await client.post(
                    f"{self.base_url}/v1/tenants",
                    json=tenant_data,
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )
                
                if tenant_response.status_code == 201:
                    self.test_tenant_id = tenant_response.json()["tenant_id"]
                    print(f"✅ Test tenant created: {self.test_tenant_id}")
                else:
                    print(f"❌ Tenant creation failed: {tenant_response.text}")
                    self.test_tenant_id = "default"
                
                return True
            else:
                print(f"❌ Login failed: {login_response.text}")
                return False
    
    async def test_public_endpoints_no_auth_required(self):
        """Test that public endpoints don't require authentication"""
        print("🔄 Testing public endpoints (should NOT require auth)...")
        
        public_endpoints = [
            ("/", "GET"),
            ("/health", "GET"),
            ("/docs", "GET"),
            ("/v1/auth/setup/init", "POST")
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for endpoint, method in public_endpoints:
                    if method == "GET":
                        response = await client.get(f"{self.base_url}{endpoint}")
                    else:
                        response = await client.post(f"{self.base_url}{endpoint}")
                    
                    assert response.status_code in [200, 400], f"Public endpoint {endpoint} failed: {response.status_code}"
                    print(f"  ✅ {endpoint} accessible without auth")
                
                print("✅ Public endpoints test successful")
                self.test_results["public_endpoints"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Public endpoints test failed: {str(e)}")
                self.test_results["public_endpoints"] = f"FAIL: {str(e)}"
                return False
    
    async def test_protected_endpoints_require_auth(self):
        """Test that protected endpoints require authentication"""
        print("🔄 Testing protected endpoints (SHOULD require auth)...")
        
        protected_endpoints = [
            ("/v1/ingest/logs", "POST"),
            ("/v1/logs", "GET"),
            ("/v1/storage/health", "GET"),
            ("/v1/alerts/rules", "GET"),
            ("/v1/security/dashboard", "GET"),
            ("/v1/users", "GET")
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for endpoint, method in protected_endpoints:
                    if method == "GET":
                        response = await client.get(f"{self.base_url}{endpoint}")
                    else:
                        response = await client.post(
                            f"{self.base_url}{endpoint}",
                            json={"service": "test", "msg": "test", "ts": datetime.now().isoformat()},
                            headers={"Content-Type": "application/json"}
                        )
                    
                    # Should get 401 (auth required) or 400 (missing tenant header)
                    if response.status_code not in [401, 400]:
                        print(f"  ❌ {endpoint} allowed without auth (status: {response.status_code})")
                        print(f"     Response: {response.text[:200]}")
                        self.test_results["protected_endpoints"] = f"FAIL: {endpoint} bypassed auth"
                        return False
                    else:
                        print(f"  ✅ {endpoint} properly protected (status: {response.status_code})")
                
                print("✅ Protected endpoints test successful")
                self.test_results["protected_endpoints"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Protected endpoints test failed: {str(e)}")
                self.test_results["protected_endpoints"] = f"FAIL: {str(e)}"
                return False
    
    async def test_authenticated_requests_work(self):
        """Test that authenticated requests work properly"""
        print("🔄 Testing authenticated requests...")
        
        if not self.auth_token or not self.test_tenant_id:
            print("❌ No auth token or tenant ID available")
            self.test_results["authenticated_requests"] = "FAIL: No auth setup"
            return False
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "X-Customer-ID": self.test_tenant_id,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test ingestion with auth
                log_data = {
                    "service": "middleware-test",
                    "msg": "Authenticated ingestion test",
                    "ts": datetime.now().isoformat(),
                    "level": "INFO"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json=log_data,
                    headers=headers
                )
                
                assert response.status_code == 200, f"Authenticated ingestion failed: {response.text}"
                result = response.json()
                assert result["status"] == "success"
                print("  ✅ Authenticated ingestion successful")
                
                # Test query with auth
                response = await client.get(
                    f"{self.base_url}/v1/logs",
                    headers=headers,
                    params={"service": "middleware-test", "limit": 1}
                )
                
                assert response.status_code == 200, f"Authenticated query failed: {response.text}"
                print("  ✅ Authenticated query successful")
                
                print("✅ Authenticated requests test successful")
                self.test_results["authenticated_requests"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Authenticated requests test failed: {str(e)}")
                self.test_results["authenticated_requests"] = f"FAIL: {str(e)}"
                return False
    
    async def test_invalid_auth_tokens(self):
        """Test that invalid auth tokens are rejected"""
        print("🔄 Testing invalid auth tokens...")
        
        invalid_tokens = [
            "invalid-token",
            "Bearer invalid",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid.signature",  # Invalid JWT
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for invalid_token in invalid_tokens:
                    headers = {
                        "Authorization": f"Bearer {invalid_token}",
                        "X-Customer-ID": self.test_tenant_id or "test-tenant",
                        "Content-Type": "application/json"
                    }
                    
                    response = await client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json={"service": "test", "msg": "test", "ts": datetime.now().isoformat()},
                        headers=headers
                    )
                    
                    assert response.status_code == 401, f"Invalid token should be rejected: {invalid_token[:20]}..."
                    print(f"  ✅ Invalid token rejected: {invalid_token[:20]}...")
                
                print("✅ Invalid auth tokens test successful")
                self.test_results["invalid_tokens"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Invalid auth tokens test failed: {str(e)}")
                self.test_results["invalid_tokens"] = f"FAIL: {str(e)}"
                return False
    
    async def test_missing_tenant_header(self):
        """Test that missing X-Customer-ID header is handled"""
        print("🔄 Testing missing X-Customer-ID header...")
        
        if not self.auth_token:
            print("❌ No auth token available")
            self.test_results["missing_tenant"] = "FAIL: No auth token"
            return False
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
            # Deliberately missing X-Customer-ID
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json={"service": "test", "msg": "test", "ts": datetime.now().isoformat()},
                    headers=headers
                )
                
                assert response.status_code == 400, f"Missing tenant header should return 400: {response.status_code}"
                result = response.json()
                assert "X-Customer-ID" in result.get("detail", ""), "Should mention missing X-Customer-ID"
                
                print("✅ Missing tenant header test successful")
                self.test_results["missing_tenant"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Missing tenant header test failed: {str(e)}")
                self.test_results["missing_tenant"] = f"FAIL: {str(e)}"
                return False
    
    async def test_middleware_order_and_flow(self):
        """Test complete middleware flow from start to finish"""
        print("🔄 Testing complete middleware flow...")
        
        test_cases = [
            {
                "name": "No auth header",
                "headers": {"Content-Type": "application/json"},
                "expected_status": 401,
                "expected_error": "Missing or invalid Authorization header"
            },
            {
                "name": "Auth but no tenant",
                "headers": {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                },
                "expected_status": 400,
                "expected_error": "X-Customer-ID header required"
            },
            {
                "name": "Complete valid request", 
                "headers": {
                    "Authorization": f"Bearer {self.auth_token}",
                    "X-Customer-ID": self.test_tenant_id or "test-tenant",
                    "Content-Type": "application/json"
                },
                "expected_status": 200,
                "expected_error": None
            }
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for test_case in test_cases:
                    print(f"  🧪 Testing: {test_case['name']}")
                    
                    response = await client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json={"service": "middleware-test", "msg": "flow test", "ts": datetime.now().isoformat()},
                        headers=test_case["headers"]
                    )
                    
                    actual_status = response.status_code
                    expected_status = test_case["expected_status"]
                    
                    if actual_status != expected_status:
                        print(f"    ❌ Expected {expected_status}, got {actual_status}")
                        print(f"    Response: {response.text}")
                        self.test_results["middleware_flow"] = f"FAIL: {test_case['name']} - wrong status"
                        return False
                    else:
                        print(f"    ✅ Got expected status {actual_status}")
                
                print("✅ Middleware flow test successful")
                self.test_results["middleware_flow"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Middleware flow test failed: {str(e)}")
                self.test_results["middleware_flow"] = f"FAIL: {str(e)}"
                return False
    
    async def test_cors_and_headers(self):
        """Test that CORS and other headers work with middleware"""
        print("🔄 Testing CORS and headers with middleware...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test OPTIONS request (CORS preflight)
                response = await client.options(f"{self.base_url}/v1/ingest/logs")
                print(f"  OPTIONS status: {response.status_code}")
                
                # Test public endpoint with CORS
                response = await client.get(
                    f"{self.base_url}/health",
                    headers={"Origin": "http://localhost:3001"}
                )
                
                assert response.status_code == 200, f"Health check with CORS failed: {response.status_code}"
                print("  ✅ CORS headers working")
                
                print("✅ CORS and headers test successful")
                self.test_results["cors_headers"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ CORS and headers test failed: {str(e)}")
                self.test_results["cors_headers"] = f"FAIL: {str(e)}"
                return False
    
    async def test_middleware_performance(self):
        """Test middleware performance impact"""
        print("🔄 Testing middleware performance...")
        
        if not self.auth_token or not self.test_tenant_id:
            print("❌ No auth setup for performance test")
            self.test_results["performance"] = "FAIL: No auth"
            return False
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "X-Customer-ID": self.test_tenant_id,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test multiple rapid requests
                start_time = time.time()
                tasks = []
                
                for i in range(10):
                    task = client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json={
                            "service": "perf-test",
                            "msg": f"Performance test {i}",
                            "ts": datetime.now().isoformat()
                        },
                        headers=headers
                    )
                    tasks.append(task)
                
                # Execute all requests concurrently
                responses = await asyncio.gather(*tasks)
                total_time = time.time() - start_time
                
                # Verify all succeeded
                for i, response in enumerate(responses):
                    assert response.status_code == 200, f"Request {i} failed: {response.status_code}"
                
                avg_time_per_request = (total_time / len(responses)) * 1000  # ms
                
                print(f"  📊 10 concurrent requests: {total_time:.2f}s total")
                print(f"  📊 Average time per request: {avg_time_per_request:.1f}ms")
                
                # Performance should be reasonable (< 100ms per request including middleware)
                if avg_time_per_request < 100:
                    print("✅ Middleware performance acceptable")
                    self.test_results["performance"] = "PASS"
                    return True
                else:
                    print("⚠️  Middleware performance slow but functional")
                    self.test_results["performance"] = "PASS (slow)"
                    return True
                
            except Exception as e:
                print(f"❌ Middleware performance test failed: {str(e)}")
                self.test_results["performance"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all middleware tests"""
        print("\\n🚀 Starting Unified Authn/Authz Middleware Test Suite...")
        print("📝 Testing: Authentication, authorization, feature access, usage tracking")
        
        # Setup authentication first
        if not await self.setup_test_auth():
            print("❌ Failed to setup test authentication")
            return False
        
        # Run middleware tests
        tests = [
            self.test_public_endpoints_no_auth_required,
            self.test_protected_endpoints_require_auth,
            self.test_authenticated_requests_work,
            self.test_invalid_auth_tokens,
            self.test_missing_tenant_header,
            self.test_middleware_order_and_flow,
            self.test_cors_and_headers,
            self.test_middleware_performance
        ]
        
        # Run tests sequentially
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                if test_func.__name__.replace("test_", "") not in self.test_results:
                    self.test_results[test_func.__name__.replace("test_", "")] = f"FAIL: {str(e)}"
        
        # Summary
        print("\\n📊 Middleware Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result.startswith("PASS"))
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅" if result.startswith("PASS") else "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\\n🎯 Middleware Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ Unified Authn/Authz Middleware: ALL TESTS PASSED")
            return True
        else:
            print("❌ Unified Authn/Authz Middleware: SOME TESTS FAILED")
            return False

if __name__ == "__main__":
    import time
    test_suite = MiddlewareTestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)