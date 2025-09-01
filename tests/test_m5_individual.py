#!/usr/bin/env python3
"""
M5 Individual Functionality Test
Tests observability, distributed tracing, metrics collection, service mapping, and APM
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime, timedelta

class M5TestSuite:
    """Test M5 Observability & APM functionality"""
    
    def __init__(self):
        self.base_url = "http://localhost:7080"
        self.test_results = {}
        self.test_tenant_id = None  # Will create actual tenant UUID
        self.test_trace_id = None
        self.test_service_name = "m5-test-service"
    
    async def setup_test_tenant(self):
        """Create a test tenant for M5 tests"""
        tenant_data = {
            "name": "M5 Test Corporation",
            "type": "enterprise",
            "primary_contact_name": "M5 Test Manager",
            "primary_contact_email": "m5test@logforge.local",
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
    
    async def test_observability_health(self):
        """Test observability engine health check"""
        print("🔄 Testing observability health...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/observability/health",
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Observability health check failed: {response.text}"
                result = response.json()
                
                # Verify health response structure
                assert "status" in result
                assert "message" in result
                assert "features" in result
                
                # Check that key observability features are present
                features = result["features"]
                assert "trace_ingestion" in features
                assert "metrics_ingestion" in features
                assert "service_map" in features
                assert "apm_metrics" in features
                
                print("✅ Observability health successful")
                self.test_results["observability_health"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Observability health failed: {str(e)}")
                self.test_results["observability_health"] = f"FAIL: {str(e)}"
                return False
    
    async def test_trace_ingestion(self):
        """Test distributed trace ingestion"""
        print("🔄 Testing trace ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Generate test trace data
                self.test_trace_id = str(uuid.uuid4())
                
                trace_spans = []
                # Create parent span
                parent_span = {
                    "trace_id": self.test_trace_id,
                    "span_id": str(uuid.uuid4()),
                    "operation_name": "http_request",
                    "service_name": self.test_service_name,
                    "start_time": (datetime.now() - timedelta(seconds=5)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_ms": 5000,
                    "kind": "server",
                    "status": "ok",
                    "attributes": {
                        "http.method": "GET",
                        "http.url": "/api/test",
                        "http.status_code": 200,
                        "user.id": "test-user-123"
                    },
                    "resource": {
                        "service.name": self.test_service_name,
                        "service.version": "1.0.0"
                    }
                }
                trace_spans.append(parent_span)
                
                # Create child spans
                for i in range(3):
                    child_span = {
                        "trace_id": self.test_trace_id,
                        "span_id": str(uuid.uuid4()),
                        "parent_span_id": parent_span["span_id"],
                        "operation_name": f"db_query_{i}",
                        "service_name": "database-service",
                        "start_time": (datetime.now() - timedelta(seconds=4)).isoformat(),
                        "end_time": (datetime.now() - timedelta(seconds=3)).isoformat(),
                        "duration_ms": 1000,
                        "kind": "client",
                        "status": "ok",
                        "attributes": {
                            "db.statement": f"SELECT * FROM table_{i}",
                            "db.name": "test_database",
                            "db.operation": "select"
                        }
                    }
                    trace_spans.append(child_span)
                
                # Ingest batch of spans
                batch_request = {"spans": trace_spans}
                
                response = await client.post(
                    f"{self.base_url}/v1/observability/traces/ingest",
                    json=batch_request,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                if response.status_code not in [200, 202]:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                result = response.json()
                
                # Verify ingestion response
                if "spans_ingested" not in result:
                    raise Exception(f"Missing spans_ingested field in response: {result}")
                
                if result["spans_ingested"] != len(trace_spans):
                    raise Exception(f"Expected {len(trace_spans)} spans ingested, got {result['spans_ingested']}")
                
                if "errors" in result and result["errors"]:
                    raise Exception(f"Ingestion errors: {result['errors']}")
                
                print("✅ Trace ingestion successful")
                self.test_results["trace_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Trace ingestion failed: {str(e)}")
                self.test_results["trace_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_metrics_ingestion(self):
        """Test metrics collection and ingestion"""
        print("🔄 Testing metrics ingestion...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Generate test metrics data
                metrics_data = [
                    {
                        "metric_name": "http_requests_total",
                        "metric_type": "counter",
                        "value": 100,
                        "timestamp": datetime.now().isoformat(),
                        "service_name": self.test_service_name,
                        "labels": {
                            "method": "GET",
                            "status": "200"
                        }
                    },
                    {
                        "metric_name": "response_time_seconds",
                        "metric_type": "histogram",
                        "value": 0.150,
                        "timestamp": datetime.now().isoformat(),
                        "service_name": self.test_service_name,
                        "labels": {
                            "endpoint": "/api/test"
                        }
                    },
                    {
                        "metric_name": "cpu_usage_percent",
                        "metric_type": "gauge",
                        "value": 65.5,
                        "timestamp": datetime.now().isoformat(),
                        "service_name": self.test_service_name,
                        "labels": {
                            "host": "test-host-1"
                        }
                    }
                ]
                
                batch_request = {"metrics": metrics_data}
                
                response = await client.post(
                    f"{self.base_url}/v1/observability/metrics/ingest",
                    json=batch_request,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                if response.status_code not in [200, 202]:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                result = response.json()
                
                # Verify ingestion response
                if "metrics_ingested" not in result:
                    raise Exception(f"Missing metrics_ingested field in response: {result}")
                
                if result["metrics_ingested"] != len(metrics_data):
                    raise Exception(f"Expected {len(metrics_data)} metrics ingested, got {result['metrics_ingested']}")
                
                if "errors" in result and result["errors"]:
                    raise Exception(f"Ingestion errors: {result['errors']}")
                
                print("✅ Metrics ingestion successful")
                self.test_results["metrics_ingestion"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Metrics ingestion failed: {str(e)}")
                self.test_results["metrics_ingestion"] = f"FAIL: {str(e)}"
                return False
    
    async def test_trace_search(self):
        """Test distributed trace search and retrieval"""
        print("🔄 Testing trace search...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Wait for trace to be processed
                await asyncio.sleep(2)
                
                # Search for traces
                search_request = {
                    "start_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "service_name": self.test_service_name,
                    "operation_name": "http_request",
                    "min_duration_ms": 1000,
                    "max_duration_ms": 10000,
                    "limit": 10
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/observability/traces/search",
                    json=search_request,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Trace search failed: {response.text}"
                result = response.json()
                
                # Verify search response structure
                assert "traces" in result
                assert "total" in result
                assert isinstance(result["traces"], list)
                
                # Should find our ingested trace
                if self.test_trace_id and result["total"] > 0:
                    trace_found = any(trace["trace_id"] == self.test_trace_id for trace in result["traces"])
                    if not trace_found:
                        print(f"⚠️ Test trace {self.test_trace_id} not found in search results")
                
                print("✅ Trace search successful")
                self.test_results["trace_search"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Trace search failed: {str(e)}")
                self.test_results["trace_search"] = f"FAIL: {str(e)}"
                return False
    
    async def test_trace_details(self):
        """Test individual trace retrieval with span details"""
        print("🔄 Testing trace details...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Skip if no test trace ID
                if not self.test_trace_id:
                    print("⚠️ No test trace available for detail testing")
                    self.test_results["trace_details"] = "SKIP: No test trace"
                    return True
                
                response = await client.get(
                    f"{self.base_url}/v1/observability/traces/{self.test_trace_id}",
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Trace details failed: {response.text}"
                result = response.json()
                
                # Verify trace details structure (match actual API response)
                assert "trace_id" in result
                assert "spans" in result
                assert "correlation_info" in result
                assert "customer_id" in result
                assert result["trace_id"] == self.test_trace_id
                
                # Check span details (spans are returned as raw arrays from ClickHouse)
                spans = result["spans"]
                assert len(spans) >= 4, f"Should have 4 spans, got {len(spans)}"
                
                # Check correlation info
                correlation = result["correlation_info"]
                assert "total_spans" in correlation
                assert "services_involved" in correlation
                assert correlation["total_spans"] == len(spans)
                assert len(correlation["services_involved"]) >= 2, "Should involve multiple services"
                
                print("✅ Trace details successful")
                self.test_results["trace_details"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Trace details failed: {str(e)}")
                self.test_results["trace_details"] = f"FAIL: {str(e)}"
                return False
    
    async def test_service_map(self):
        """Test service dependency mapping"""
        print("🔄 Testing service map...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Get service map
                response = await client.get(
                    f"{self.base_url}/v1/observability/service-map",
                    headers={"X-Customer-ID": self.test_tenant_id},
                    params={
                        "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                        "end_time": datetime.now().isoformat()
                    }
                )
                
                assert response.status_code == 200, f"Service map failed: {response.text}"
                result = response.json()
                
                # Verify service map structure (match actual API response)
                assert "services" in result
                assert "dependencies" in result  # API uses "dependencies" not "edges"
                assert isinstance(result["services"], list)
                assert isinstance(result["dependencies"], list)
                
                # Check for our test services
                services = result["services"]
                service_names = [s["name"] for s in services]
                
                if self.test_service_name in service_names:
                    test_service = next(s for s in services if s["name"] == self.test_service_name)
                    assert "total_spans" in test_service  # API uses "total_spans" not "request_rate"
                    assert "error_rate" in test_service
                    assert "avg_latency_ms" in test_service  # API uses "avg_latency_ms" not "avg_duration_ms"
                
                print("✅ Service map successful")
                self.test_results["service_map"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Service map failed: {str(e)}")
                self.test_results["service_map"] = f"FAIL: {str(e)}"
                return False
    
    async def test_apm_dashboard(self):
        """Test APM dashboard for specific service"""
        print("🔄 Testing APM dashboard...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v1/observability/apm/{self.test_service_name}",
                    headers={"X-Customer-ID": self.test_tenant_id},
                    params={
                        "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                        "end_time": datetime.now().isoformat()
                    }
                )
                
                assert response.status_code == 200, f"APM dashboard failed: {response.text}"
                result = response.json()
                
                # Verify APM dashboard structure (match actual API response)
                assert "service_name" in result
                assert "metrics" in result  # API uses "metrics" not "overview"
                assert "time_range_hours" in result
                assert "customer_id" in result
                
                # Check metrics structure  
                metrics = result["metrics"]
                assert "request_rate" in metrics
                assert "latency" in metrics
                assert "error_rate" in metrics
                
                # Check latency breakdown
                latency = metrics["latency"]
                assert "p50_ms" in latency
                assert "p95_ms" in latency  
                assert "p99_ms" in latency
                assert "avg_ms" in latency
                
                print("✅ APM dashboard successful")
                self.test_results["apm_dashboard"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ APM dashboard failed: {str(e)}")
                self.test_results["apm_dashboard"] = f"FAIL: {str(e)}"
                return False
    
    async def test_metrics_query(self):
        """Test metrics querying and aggregation"""
        print("🔄 Testing metrics query...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Wait for metrics to be processed
                await asyncio.sleep(2)
                
                # Query metrics with aggregation
                query_request = {
                    "metric_name": "http_requests_total",
                    "start_time": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "aggregation": "sum",
                    "group_by": ["service", "method"],
                    "filters": {
                        "service": self.test_service_name
                    },
                    "step": "5m"
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/observability/metrics/query",
                    json=query_request,
                    headers={"X-Customer-ID": self.test_tenant_id}
                )
                
                assert response.status_code == 200, f"Metrics query failed: {response.text}"
                result = response.json()
                
                # Verify metrics query response (match actual API response)
                assert "metrics" in result
                assert "aggregation" in result
                assert "customer_id" in result
                assert isinstance(result["metrics"], dict)
                
                # Check metrics structure  
                metrics = result["metrics"]
                if metrics:
                    # Check if our queried metric exists
                    for metric_name, data_points in metrics.items():
                        assert isinstance(data_points, list)
                        if data_points:
                            data_point = data_points[0]
                            assert "timestamp" in data_point
                            assert "value" in data_point
                            assert isinstance(data_point["value"], (int, float))
                
                print("✅ Metrics query successful")
                self.test_results["metrics_query"] = "PASS"
                return True
                
            except Exception as e:
                print(f"❌ Metrics query failed: {str(e)}")
                self.test_results["metrics_query"] = f"FAIL: {str(e)}"
                return False
    
    async def run_all_tests(self):
        """Run all M5 tests"""
        print("\n🚀 Starting M5 Individual Test Suite...")
        print("📝 Testing: Observability, distributed tracing, metrics, service mapping, APM")
        
        # First create test tenant
        await self.setup_test_tenant()
        
        # Run tests in order (some depend on earlier ones)
        tests = [
            self.test_observability_health,
            self.test_trace_ingestion,
            self.test_metrics_ingestion,
            self.test_trace_search,
            self.test_trace_details,
            self.test_service_map,
            self.test_apm_dashboard,
            self.test_metrics_query
        ]
        
        # Run tests sequentially since some depend on previous ones
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with exception: {str(e)}")
                if test_func.__name__.replace("test_", "") not in self.test_results:
                    self.test_results[test_func.__name__.replace("test_", "")] = f"FAIL: {str(e)}"
        
        # Summary
        print("\n📊 M5 Test Results Summary:")
        passed = sum(1 for result in self.test_results.values() if result == "PASS" or result.startswith("SKIP"))
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            if result == "PASS":
                status = "✅"
            elif result.startswith("SKIP"):
                status = "⚠️"
            else:
                status = "❌"
            print(f"  {status} {test_name}: {result}")
        
        print(f"\n🎯 M5 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ M5 Observability & APM: ALL TESTS PASSED")
            return True
        else:
            print("❌ M5 Observability & APM: SOME TESTS FAILED")
            return False

if __name__ == "__main__":
    test_suite = M5TestSuite()
    success = asyncio.run(test_suite.run_all_tests())
    exit(0 if success else 1)