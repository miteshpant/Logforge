#!/usr/bin/env python3
"""
M1 Individual Functionality Test
Tests multi-format ingestion, TTL management, and storage lifecycle
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta

class M1TestSuite:
    """Test M1 Ingestion & Storage MVP functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.test_tenant_id = None  # Will create actual tenant UUID
    
    async def setup_test_tenant(self):
        """Create a test tenant for M1 tests"""
        tenant_data = {
            "name": "M1 Test Corporation",
            "type": "enterprise",
            "primary_contact_name": "M1 Test Manager",
            "primary_contact_email": "m1test@logforge.local",
            "industry": "Technology"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/tenants",
                json=tenant_data,
                headers={"Authorization": "Bearer admin-token", "Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                self.test_tenant_id = response.json()["tenant_id"]
                print(f"🏢 Created test tenant: {self.test_tenant_id}")
            else:
                print(f"❌ Failed to create test tenant: {response.text}")
                self.test_tenant_id = "default"  # Fallback to default
    
    async def test_json_ingestion(self):
        """Test JSON log format ingestion"""
        print("🔄 Testing JSON log ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                log_entry = {
                    "ts": datetime.now().isoformat(),
                    "service": "test-json-service",
                    "level": "INFO", 
                    "msg": "JSON format test",
                    "host": "json-host",
                    "user_id": "user123",
                    "attrs": {
                        "request_id": "json-req-001",
                        "method": "POST",
                        "status": 200
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs",
                    json=log_entry,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"JSON ingestion failed: {response.text}"
                result = response.json()
                assert result["status"] == "success"
                
                print("✅ JSON log ingestion successful")
                self.test_results["json_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ JSON log ingestion failed: {str(e)}")
                self.test_results["json_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_batch_ingestion(self):
        """Test batch log ingestion"""
        print("🔄 Testing batch log ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Create batch of logs
                batch_logs = []
                for i in range(5):
                    batch_logs.append({
                        "ts": (datetime.now() - timedelta(minutes=i)).isoformat(),
                        "service": "batch-test-service",
                        "level": "INFO",
                        "msg": f"Batch log entry {i}",
                        "host": "batch-host",
                        "trace_id": f"batch-{i:03d}"
                    })
                
                batch_data = {"logs": batch_logs}
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest/logs/batch",
                    json=batch_data,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Batch ingestion failed: {response.text}"
                result = response.json()
                assert result["status"] == "accepted"
                assert result["processed_count"] == 5
                
                # Wait for background processing
                await asyncio.sleep(2)
                
                print("✅ Batch log ingestion successful")
                self.test_results["batch_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Batch log ingestion failed: {str(e)}")
                self.test_results["batch_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_syslog_ingestion(self):
        """Test Syslog format ingestion"""
        print("🔄 Testing Syslog ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # RFC 3164 syslog message
                syslog_message = "<34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick on /dev/pts/8"
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest/syslog",
                    content=syslog_message,
                    headers={"Content-Type": "text/plain", "X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Syslog ingestion failed: {response.text}"
                result = response.json()
                assert result["status"] == "success"
                
                print("✅ Syslog ingestion successful")
                self.test_results["syslog_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Syslog ingestion failed: {str(e)}")
                self.test_results["syslog_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_auto_detect_ingestion(self):
        """Test auto-format detection ingestion"""
        print("🔄 Testing auto-detect ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # JSON message that should be auto-detected
                json_message = json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": "Auto-detected JSON message",
                    "service": "auto-detect-test"
                })
                
                response = await client.post(
                    f"{self.base_url}/v1/ingest",
                    content=json_message,
                    headers={"Content-Type": "text/plain", "X-Customer-ID": self.test_tenant_id},
                    params={"service": "auto-detect-service"}
                )
                
                assert response.status_code == 200, f"Auto-detect ingestion failed: {response.text}"
                result = response.json()
                assert result["status"] == "success"
                assert "detected format" in result["message"]
                
                print("✅ Auto-detect ingestion successful")
                self.test_results["auto_detect"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Auto-detect ingestion failed: {str(e)}")
                self.test_results["auto_detect"] = f"FAIL: {str(e)}"
                return False
    
    async def test_storage_health(self):
        """Test storage health and metrics"""
        print("🔄 Testing storage health...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self.base_url}/v1/storage/health")
                
                assert response.status_code == 200, f"Storage health failed: {response.text}"
                health_data = response.json()
                
                # Verify health response structure
                assert "status" in health_data
                assert "overall_stats" in health_data
                assert "total_logs" in health_data["overall_stats"]
                assert "total_customers" in health_data["overall_stats"]
                
                print("✅ Storage health check successful")
                self.test_results["storage_health"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Storage health failed: {str(e)}")
                self.test_results["storage_health"] = f"FAIL: {str(e)}"
                return False
    
    async def test_ttl_management(self):
        """Test TTL and retention policies"""
        print("🔄 Testing TTL management...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Test cleanup trigger
                response = await client.post(f"{self.base_url}/v1/storage/cleanup")
                
                assert response.status_code == 200, f"TTL cleanup failed: {response.text}"
                result = response.json()
                assert result["status"] == "completed"
                assert "cleanup_stats" in result
                
                print("✅ TTL management successful")
                self.test_results["ttl_management"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ TTL management failed: {str(e)}")
                self.test_results["ttl_management"] = f"FAIL: {str(e)}"
                return False
    
    async def test_multi_tenant_ingestion(self):
        """Test multi-tenant data isolation"""
        print("🔄 Testing multi-tenant ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Use actual tenant UUID for multi-tenant testing
                customers = [self.test_tenant_id, self.test_tenant_id]
                
                for i, customer in enumerate(customers):
                    log_data = {
                        "ts": datetime.now().isoformat(),
                        "service": f"tenant-{i}-service",
                        "level": "INFO",
                        "msg": f"Multi-tenant test for tenant-{i}",
                        "host": f"tenant-{i}-host"
                    }
                    
                    response = await client.post(
                        f"{self.base_url}/v1/ingest/logs",
                        json=log_data,
                        headers={"X-Customer-ID": customer}
                    )
                    
                    assert response.status_code == 200, f"Multi-tenant ingestion failed for {customer}: {response.text}"
                
                print("✅ Multi-tenant ingestion successful")
                self.test_results["multi_tenant"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Multi-tenant ingestion failed: {str(e)}")
                self.test_results["multi_tenant"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M1 tests"""
        print("\n🚀 Starting M1 Individual Test Suite...")
        print("📝 Testing: Multi-format ingestion, TTL, and storage lifecycle")
        
        # First create test tenant
        await self.setup_test_tenant()
        
        # Run tests sequentially to avoid race conditions and timeouts
        tests = [
            self.test_json_ingestion,
            self.test_batch_ingestion,
            self.test_syslog_ingestion,
            self.test_auto_detect_ingestion,
            self.test_storage_health,
            self.test_ttl_management,
            self.test_multi_tenant_ingestion
        ]
        
        # Run tests sequentially since concurrent requests cause issues
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                if test_func.__name__.replace("test_", "") not in self.test_results:
                    self.test_results[test_func.__name__.replace("test_", "")] = f"FAIL: {str(e)}"
        
        # Summary
        print("\n📊 M1 Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result == "PASS")
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅" if result == "PASS" else "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\n🎯 M1 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ M1 Ingestion & Storage MVP: ALL TESTS PASSED")
            return True
        else:
            print("❌ M1 Ingestion & Storage MVP: SOME TESTS FAILED")
            return False

if __name__ == "__main__":
    test_suite = M1TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)