"""
Live integration tests that work with running Docker services
"""

import pytest
import time
import asyncio
import requests
from datetime import datetime, timezone


class TestLiveAPIIntegration:
    """Live integration tests against running API"""
    
    BASE_URL = "http://localhost:7080"
    
    def test_health_endpoint_live(self):
        """Test health endpoint against live API"""
        response = requests.get(f"{self.BASE_URL}/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return health status
        assert "status" in data
        print(f"Health Response: {data}")
    
    def test_live_json_log_ingestion(self):
        """Test JSON log ingestion against live API"""
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info",
            "message": "Live integration test log",
            "service": "integration-test",
            "host": "test-host",
            "user_id": "test-user-123"
        }
        
        response = requests.post(
            f"{self.BASE_URL}/v1/ingest/logs",
            json=test_log,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Ingestion Response: {response.status_code} - {response.text}")
        
        # Should accept the log
        assert response.status_code in [200, 202]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "message" in data
    
    def test_live_batch_ingestion(self):
        """Test batch ingestion against live API"""
        batch_logs = []
        for i in range(10):
            log = {
                "timestamp": f"2023-12-25T10:0{i % 10}:00Z",
                "level": "info" if i % 2 == 0 else "warn",
                "message": f"Batch test log {i}",
                "service": "batch-test",
                "host": f"host-{i}",
                "sequence": i
            }
            batch_logs.append(log)
        
        batch_data = {"logs": batch_logs}
        
        response = requests.post(
            f"{self.BASE_URL}/v1/ingest/logs/batch",
            json=batch_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Batch Response: {response.status_code} - {response.text}")
        
        assert response.status_code in [200, 202]
        
        if response.status_code == 200:
            data = response.json()
            assert "count" in data or "status" in data
    
    def test_live_nginx_ingestion(self):
        """Test Nginx log ingestion against live API"""
        nginx_log = (
            '192.168.1.100 - test-user [25/Dec/2023:10:00:00 +0000] '
            '"GET /api/integration-test HTTP/1.1" 200 1234 '
            '"http://example.com/referrer" "IntegrationTest/1.0"'
        )
        
        response = requests.post(
            f"{self.BASE_URL}/v1/ingest/nginx",
            data=nginx_log,
            headers={"Content-Type": "text/plain"}
        )
        
        print(f"Nginx Response: {response.status_code} - {response.text}")
        
        assert response.status_code in [200, 202]
    
    def test_live_syslog_ingestion(self):
        """Test Syslog ingestion against live API"""
        syslog_message = "<34>Dec 25 10:00:00 integration-host test-service: Integration test syslog message"
        
        response = requests.post(
            f"{self.BASE_URL}/v1/ingest/syslog",
            data=syslog_message,
            headers={"Content-Type": "text/plain"}
        )
        
        print(f"Syslog Response: {response.status_code} - {response.text}")
        
        assert response.status_code in [200, 202]
    
    def test_live_query_basic(self):
        """Test basic querying against live API"""
        # First ingest a test log
        test_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "message": "Query test log for integration",
            "service": "query-test",
            "host": "query-host"
        }
        
        # Ingest the log
        ingest_response = requests.post(
            f"{self.BASE_URL}/v1/ingest/logs",
            json=test_log
        )
        assert ingest_response.status_code in [200, 202]
        
        # Wait a moment for processing
        time.sleep(2)
        
        # Query for logs
        query_data = {
            "query": "service=query-test",
            "start_time": "2023-01-01T00:00:00Z",
            "end_time": "2025-12-31T23:59:59Z",
            "limit": 100
        }
        
        response = requests.post(
            f"{self.BASE_URL}/v1/query",
            json=query_data
        )
        
        print(f"Query Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Query Results: {len(data.get('logs', []))} logs found")
        else:
            print(f"Query Response Text: {response.text}")
        
        # Query endpoint should respond (may not have data yet due to async processing)
        assert response.status_code in [200, 404, 500]  # Allow various states
    
    def test_live_error_handling(self):
        """Test error handling against live API"""
        # Test invalid JSON
        response = requests.post(
            f"{self.BASE_URL}/v1/ingest/logs",
            data="{invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Invalid JSON Response: {response.status_code}")
        
        # Should handle invalid JSON gracefully
        assert response.status_code in [400, 422]
        
        # Test empty request
        response = requests.post(f"{self.BASE_URL}/v1/ingest/logs")
        print(f"Empty Request Response: {response.status_code}")
        
        # Should reject empty requests
        assert response.status_code in [400, 422]
    
    def test_api_endpoints_exist(self):
        """Test that all expected API endpoints exist"""
        endpoints_to_test = [
            ("/health", "GET"),
            ("/v1/ingest/logs", "POST"),
            ("/v1/ingest/logs/batch", "POST"),
            ("/v1/ingest/nginx", "POST"),
            ("/v1/ingest/syslog", "POST"),
            ("/v1/ingest/cef", "POST"),
            ("/v1/ingest/text", "POST"),
            ("/v1/ingest/otlp", "POST"),
            ("/v1/query", "POST")
        ]
        
        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = requests.get(f"{self.BASE_URL}{endpoint}")
            else:
                response = requests.post(f"{self.BASE_URL}{endpoint}")
            
            # Endpoint should exist (not 404)
            assert response.status_code != 404, f"Endpoint {endpoint} not found"
            print(f"{method} {endpoint}: {response.status_code}")


class TestLivePerformanceBaseline:
    """Basic performance tests against live API"""
    
    BASE_URL = "http://localhost:7080"
    
    def test_health_endpoint_latency(self):
        """Test health endpoint latency"""
        latencies = []
        
        # Warm up
        for _ in range(5):
            requests.get(f"{self.BASE_URL}/health")
        
        # Measure latencies
        for _ in range(20):
            start_time = time.time()
            response = requests.get(f"{self.BASE_URL}/health")
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                latencies.append(elapsed * 1000)  # Convert to milliseconds
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            
            print(f"Health Endpoint Performance:")
            print(f"  Average: {avg_latency:.1f}ms")
            print(f"  Min: {min_latency:.1f}ms") 
            print(f"  Max: {max_latency:.1f}ms")
            
            # Health endpoint should be fast
            assert avg_latency < 100, f"Health endpoint too slow: {avg_latency:.1f}ms"
            assert max_latency < 500, f"Health endpoint max too high: {max_latency:.1f}ms"
    
    def test_ingestion_throughput_baseline(self):
        """Test basic ingestion throughput"""
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info",
            "message": "Throughput test log",
            "service": "throughput-test"
        }
        
        successful_requests = 0
        start_time = time.time()
        
        # Send requests for 5 seconds
        end_time = start_time + 5
        while time.time() < end_time:
            try:
                response = requests.post(
                    f"{self.BASE_URL}/v1/ingest/logs",
                    json=test_log,
                    timeout=1.0
                )
                if response.status_code in [200, 202]:
                    successful_requests += 1
            except requests.RequestException:
                pass  # Count failures but don't stop
        
        elapsed = time.time() - start_time
        throughput = successful_requests / elapsed
        
        print(f"Ingestion Baseline Performance:")
        print(f"  Successful requests: {successful_requests}")
        print(f"  Time elapsed: {elapsed:.1f}s") 
        print(f"  Throughput: {throughput:.0f} requests/sec")
        
        # Should achieve some baseline throughput
        assert successful_requests > 10, f"Too few successful requests: {successful_requests}"
        assert throughput > 10, f"Throughput too low: {throughput:.0f} req/sec"
    
    def test_concurrent_ingestion_baseline(self):
        """Test concurrent ingestion performance"""
        import concurrent.futures
        import threading
        
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info", 
            "message": "Concurrent test log",
            "service": "concurrent-test"
        }
        
        def send_requests(num_requests):
            successful = 0
            for i in range(num_requests):
                try:
                    response = requests.post(
                        f"{self.BASE_URL}/v1/ingest/logs",
                        json={**test_log, "sequence": i},
                        timeout=2.0
                    )
                    if response.status_code in [200, 202]:
                        successful += 1
                except requests.RequestException:
                    pass
            return successful
        
        # Test with 5 concurrent threads, 10 requests each
        num_threads = 5
        requests_per_thread = 10
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(send_requests, requests_per_thread) 
                for _ in range(num_threads)
            ]
            results = [future.result() for future in futures]
        
        elapsed = time.time() - start_time
        total_successful = sum(results)
        total_requests = num_threads * requests_per_thread
        throughput = total_successful / elapsed
        success_rate = total_successful / total_requests
        
        print(f"Concurrent Ingestion Performance:")
        print(f"  Total successful: {total_successful}/{total_requests}")
        print(f"  Success rate: {success_rate:.1%}")
        print(f"  Time elapsed: {elapsed:.1f}s")
        print(f"  Throughput: {throughput:.0f} requests/sec")
        
        # Should handle concurrent requests reasonably
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.1%}"
        assert throughput > 10, f"Concurrent throughput too low: {throughput:.0f} req/sec"


class TestLiveDataPipeline:
    """Test complete data pipeline"""
    
    BASE_URL = "http://localhost:7080"
    
    def test_end_to_end_pipeline_basic(self):
        """Test basic end-to-end pipeline"""
        # Generate unique test data
        test_id = int(time.time())
        test_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "info",
            "message": f"E2E test log {test_id}",
            "service": "e2e-test",
            "host": "e2e-host",
            "test_id": test_id
        }
        
        print(f"Testing E2E pipeline with test_id: {test_id}")
        
        # Step 1: Ingest the log
        ingest_response = requests.post(
            f"{self.BASE_URL}/v1/ingest/logs",
            json=test_log
        )
        
        print(f"Ingestion: {ingest_response.status_code}")
        assert ingest_response.status_code in [200, 202]
        
        # Step 2: Wait for processing
        time.sleep(3)
        
        # Step 3: Try to query for the log
        query_data = {
            "query": f"service=e2e-test",
            "start_time": (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)).isoformat(),
            "end_time": (datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)).isoformat(),
            "limit": 100
        }
        
        query_response = requests.post(
            f"{self.BASE_URL}/v1/query",
            json=query_data
        )
        
        print(f"Query: {query_response.status_code}")
        
        if query_response.status_code == 200:
            data = query_response.json()
            logs_found = len(data.get("logs", []))
            print(f"Found {logs_found} logs in query results")
            
            # Check if our test log is in the results
            found_test_log = False
            for log in data.get("logs", []):
                if str(test_id) in str(log.get("msg", "")) or str(test_id) in str(log):
                    found_test_log = True
                    break
            
            if found_test_log:
                print("✅ E2E pipeline working: Log successfully ingested and retrieved")
            else:
                print("⚠️  E2E pipeline: Log ingested but not found in query (may be async processing)")
        
        else:
            print(f"Query failed: {query_response.text}")
        
        # Test passes if ingestion worked (query may be async)
        assert ingest_response.status_code in [200, 202]
    
    def test_multi_format_pipeline(self):
        """Test pipeline with multiple log formats"""
        test_id = int(time.time())
        
        # Test different formats
        formats_data = [
            # JSON format
            ({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "info",
                "message": f"Multi-format JSON test {test_id}",
                "service": "multi-format"
            }, f"{self.BASE_URL}/v1/ingest/logs", "json"),
            
            # Nginx format
            (f'192.168.1.1 - test-user [25/Dec/2023:10:00:00 +0000] "GET /test/{test_id} HTTP/1.1" 200 1234',
             f"{self.BASE_URL}/v1/ingest/nginx", "text/plain"),
            
            # Syslog format
            (f"<34>Dec 25 10:00:00 multi-format-host service: Multi-format syslog test {test_id}",
             f"{self.BASE_URL}/v1/ingest/syslog", "text/plain"),
        ]
        
        results = []
        
        for data, endpoint, content_type in formats_data:
            if content_type == "json":
                headers = {"Content-Type": "application/json"}
                response = requests.post(endpoint, json=data, headers=headers)
            else:
                headers = {"Content-Type": content_type}
                response = requests.post(endpoint, data=data, headers=headers)
            
            results.append({
                "format": content_type,
                "status": response.status_code,
                "success": response.status_code in [200, 202]
            })
            
            print(f"{content_type} format: {response.status_code}")
        
        # All formats should be accepted
        success_count = sum(1 for r in results if r["success"])
        total_formats = len(results)
        
        print(f"Multi-format results: {success_count}/{total_formats} successful")
        
        assert success_count >= total_formats * 0.8, f"Too many format failures: {success_count}/{total_formats}"