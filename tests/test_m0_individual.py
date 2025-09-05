#!/usr/bin/env python3
"""
M0 Individual Functionality Test
Tests basic scaffold, health checks, and basic log ingestion
"""

import asyncio
import httpx
from datetime import datetime
from base_test import BaseTestSuite

class M0TestSuite(BaseTestSuite):
    """Test M0 Basic Scaffold & Hello Logs functionality"""
    
    def __init__(self):
        super().__init__("M0 Basic Scaffold & Hello Logs")
    
    async def test_health_check(self):
        """Test basic health check endpoint"""
        print("🔄 Testing health check...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                
                assert response.status_code == 200, f"Health check failed: {response.status_code}"
                health_data = response.json()
                
                # Verify health response structure
                assert "status" in health_data
                assert "timestamp" in health_data
                assert "services" in health_data
                
                # Verify ClickHouse is healthy
                assert "clickhouse" in health_data["services"]
                
                print("✅ Health check successful")
                self.test_results["health_check"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Health check failed: {str(e)}")
                self.test_results["health_check"] = f"FAIL: {str(e)}"
                return False
    
    async def test_root_endpoint(self):
        """Test root endpoint with API information"""
        print("🔄 Testing root endpoint...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/")
                
                assert response.status_code == 200, f"Root endpoint failed: {response.status_code}"
                root_data = response.json()
                
                # Verify root response structure
                assert "message" in root_data
                assert "version" in root_data
                assert "features" in root_data
                assert "docs" in root_data
                
                # Verify expected features
                features = root_data["features"]
                assert isinstance(features, list)
                assert any("ingestion" in str(f).lower() for f in features)
                
                print("✅ Root endpoint successful")
                self.test_results["root_endpoint"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Root endpoint failed: {str(e)}")
                self.test_results["root_endpoint"] = f"FAIL: {str(e)}"
                return False
    
    async def test_basic_log_ingestion(self):
        """Test basic log ingestion (hello logs)"""
        print("🔄 Testing basic log ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test simple log ingestion
                log_entry = {
                    "ts": datetime.now().isoformat(),
                    "service": "test-service-m0",
                    "level": "INFO",
                    "msg": "Hello Logs - M0 Test",
                    "host": "test-host",
                    "trace_id": "m0-test-trace-001"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json=log_entry,
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Basic ingestion failed: {response.status_code} - {response.text}"
                result = response.json()
                
                # Verify ingestion response
                assert result["status"] == "success"
                assert "message" in result
                assert "log_id" in result
                
                print("✅ Basic log ingestion successful")
                self.test_results["basic_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Basic log ingestion failed: {str(e)}")
                self.test_results["basic_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_basic_log_retrieval(self):
        """Test basic log retrieval"""
        print("🔄 Testing basic log retrieval...")
        
        # Wait for background ingestion processing
        await asyncio.sleep(8)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Query logs
                response = await client.get(
                    f"{self.base_url}/v1/logs",
                    params={
                        "service": "test-service-m0",
                        "limit": 10
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200, f"Log retrieval failed: {response.status_code} - {response.text}"
                result = response.json()
                
                # Verify retrieval response
                assert "logs" in result
                assert "total" in result
                assert isinstance(result["logs"], list)
                
                # Should find our test log
                test_logs = [log for log in result["logs"] if log["service"] == "test-service-m0"]
                assert len(test_logs) > 0, "Test log not found in retrieval"
                
                print("✅ Basic log retrieval successful")
                self.test_results["basic_retrieval"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Basic log retrieval failed: {str(e)}")
                self.test_results["basic_retrieval"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M0 tests using base class runner"""
        print("📝 Testing: Basic scaffold, health checks, and hello logs")
        
        tests = [
            self.test_health_check,
            self.test_root_endpoint,
            self.test_basic_log_ingestion,
            self.test_basic_log_retrieval
        ]
        
        return await super().run_all_tests(tests)

if __name__ == "__main__":
    test_suite = M0TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)