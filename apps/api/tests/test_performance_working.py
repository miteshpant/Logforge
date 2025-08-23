"""
Working performance tests for the Logforge API
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import concurrent.futures

from fastapi.testclient import TestClient
from httpx import AsyncClient

from main import app


class TestAPIPerformanceLive:
    """Live performance tests that work with actual implementation"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    def test_single_log_ingestion_latency(self, mock_process, mock_clickhouse, client):
        """Test single log ingestion latency"""
        mock_clickhouse.insert.return_value = None
        mock_process.return_value = None
        
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info", 
            "message": "Performance test log",
            "service": "test-service",
            "host": "test-host"
        }
        
        latencies = []
        
        # Warm up
        for _ in range(10):
            client.post("/v1/ingest/logs", json=test_log)
        
        # Measure latencies
        for _ in range(100):
            start_time = time.time()
            response = client.post("/v1/ingest/logs", json=test_log)
            elapsed = time.time() - start_time
            
            if response.status_code in [200, 202]:
                latencies.append(elapsed * 1000)  # Convert to milliseconds
        
        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            
            print(f"Single Log Ingestion - P50: {p50:.1f}ms, P95: {p95:.1f}ms, P99: {p99:.1f}ms")
            
            # Basic performance assertions
            assert p50 < 50, f"P50 latency too high: {p50:.1f}ms"
            assert p99 < 200, f"P99 latency too high: {p99:.1f}ms"
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')  
    def test_batch_ingestion_throughput(self, mock_process, mock_clickhouse, client):
        """Test batch ingestion throughput"""
        mock_clickhouse.insert.return_value = None
        mock_process.return_value = None
        
        # Create batch of 100 logs
        batch_logs = []
        for i in range(100):
            log = {
                "timestamp": "2023-12-25T10:00:00Z",
                "level": "info",
                "message": f"Batch test log {i}",
                "service": "test-service",
                "host": f"test-host-{i % 10}",
                "user_id": f"user-{i}"
            }
            batch_logs.append(log)
        
        batch_data = {"logs": batch_logs}
        
        # Test throughput
        start_time = time.time()
        num_batches = 10
        successful_requests = 0
        
        for _ in range(num_batches):
            response = client.post("/v1/ingest/logs/batch", json=batch_data)
            if response.status_code in [200, 202]:
                successful_requests += 1
        
        elapsed = time.time() - start_time
        total_logs = successful_requests * len(batch_logs)
        throughput = total_logs / elapsed
        
        print(f"Batch Throughput: {throughput:.0f} logs/sec ({total_logs} total logs)")
        
        assert successful_requests >= num_batches * 0.9  # 90% success rate
        assert throughput > 5000, f"Batch throughput too low: {throughput:.0f} logs/sec"
    
    @pytest.mark.asyncio
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_concurrent_ingestion_async(self, mock_process, mock_clickhouse, async_client):
        """Test concurrent ingestion with async client"""
        mock_clickhouse.insert.return_value = None
        mock_process.return_value = None
        
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info",
            "message": "Concurrent test log", 
            "service": "test-service",
            "host": "test-host"
        }
        
        # Test concurrent requests
        num_concurrent = 100
        start_time = time.time()
        
        tasks = []
        for i in range(num_concurrent):
            task = async_client.post("/v1/ingest/logs", json={**test_log, "sequence": i})
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start_time
        
        successful_responses = sum(
            1 for r in responses 
            if hasattr(r, 'status_code') and r.status_code in [200, 202]
        )
        throughput = successful_responses / elapsed
        
        print(f"Concurrent Async: {throughput:.0f} requests/sec ({successful_responses}/{num_concurrent} successful)")
        
        assert successful_responses >= num_concurrent * 0.9  # 90% success rate
        assert throughput > 500, f"Async throughput too low: {throughput:.0f} req/sec"
    
    @patch('main.clickhouse_client')
    def test_query_performance_mock(self, mock_clickhouse, client):
        """Test query performance with mocked data"""
        # Mock large result set
        mock_rows = []
        for i in range(1000):
            row = (
                datetime.now(timezone.utc),
                f"host-{i % 10}",
                f"service-{i % 5}",
                "info",
                f"Log message {i}",
                f"trace-{i}",
                f"span-{i}",
                '{"index": ' + str(i) + '}',
                200,
                f"192.168.1.{i % 255}",
                f"user-{i}"
            )
            mock_rows.append(row)
        
        mock_result = Mock()
        mock_result.result_rows = mock_rows
        mock_clickhouse.query.return_value = mock_result
        
        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z",
            "limit": 1000
        }
        
        # Test query performance
        latencies = []
        for _ in range(10):
            start_time = time.time()
            response = client.post("/v1/query", json=query_data)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                latencies.append(elapsed * 1000)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"Query Performance - Avg: {avg_latency:.1f}ms, Max: {max_latency:.1f}ms")
            
            assert avg_latency < 500, f"Average query latency too high: {avg_latency:.1f}ms"
            assert max_latency < 1000, f"Max query latency too high: {max_latency:.1f}ms"
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint performance"""
        latencies = []
        
        # Test health endpoint performance
        for _ in range(50):
            start_time = time.time()
            response = client.get("/health")
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                latencies.append(elapsed * 1000)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"Health Endpoint - Avg: {avg_latency:.1f}ms, Max: {max_latency:.1f}ms")
            
            # Health endpoint should be very fast
            assert avg_latency < 10, f"Health endpoint too slow: {avg_latency:.1f}ms"
            assert max_latency < 50, f"Health endpoint max latency too high: {max_latency:.1f}ms"
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    def test_mixed_format_performance(self, mock_process, mock_clickhouse, client):
        """Test performance with different log formats"""
        mock_clickhouse.insert.return_value = None
        mock_process.return_value = None
        
        # Test data for different formats
        test_cases = [
            # JSON format
            ({
                "timestamp": "2023-12-25T10:00:00Z",
                "level": "info",
                "message": "JSON log",
                "service": "json-service"
            }, "/v1/ingest/logs"),
            
            # Nginx format
            ('192.168.1.1 - - [25/Dec/2023:10:00:00 +0000] "GET /api/test HTTP/1.1" 200 1234',
             "/v1/ingest/nginx"),
            
            # Syslog format  
            ("<34>Dec 25 10:00:00 host service: test syslog message",
             "/v1/ingest/syslog"),
        ]
        
        results = {}
        
        for data, endpoint in test_cases:
            latencies = []
            
            # Warm up
            for _ in range(5):
                if isinstance(data, dict):
                    client.post(endpoint, json=data)
                else:
                    client.post(endpoint, data=data, headers={"Content-Type": "text/plain"})
            
            # Measure performance
            for _ in range(20):
                start_time = time.time()
                
                if isinstance(data, dict):
                    response = client.post(endpoint, json=data)
                else:
                    response = client.post(endpoint, data=data, headers={"Content-Type": "text/plain"})
                
                elapsed = time.time() - start_time
                
                if response.status_code in [200, 202]:
                    latencies.append(elapsed * 1000)
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                results[endpoint] = avg_latency
        
        # Print results
        print("\nFormat Performance Results:")
        for endpoint, avg_latency in results.items():
            print(f"{endpoint}: {avg_latency:.1f}ms average")
        
        # All formats should perform reasonably
        for endpoint, avg_latency in results.items():
            assert avg_latency < 100, f"{endpoint} too slow: {avg_latency:.1f}ms"


class TestMemoryAndResourceUsage:
    """Test memory and resource usage"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    def test_memory_usage_under_load(self, mock_process, mock_clickhouse, client):
        """Test memory usage doesn't grow excessively under load"""
        import psutil
        import gc
        
        mock_clickhouse.insert.return_value = None
        mock_process.return_value = None
        
        # Force garbage collection
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        test_log = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "info",
            "message": "Memory test log",
            "service": "memory-test"
        }
        
        # Make many requests
        for i in range(1000):
            response = client.post("/v1/ingest/logs", json=test_log)
            
            # Check memory periodically
            if i % 100 == 99:
                gc.collect()
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Memory shouldn't grow excessively
                assert memory_growth < 50, f"Excessive memory growth: {memory_growth:.1f}MB at {i+1} requests"
        
        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        print(f"Memory Usage - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Growth: {total_growth:.1f}MB")
        
        # Total memory growth should be reasonable
        assert total_growth < 30, f"Total memory growth too high: {total_growth:.1f}MB"
    
    def test_cpu_usage_efficiency(self, client):
        """Test that CPU usage is reasonable under load"""
        import psutil
        import threading
        import time
        
        # Monitor CPU usage
        cpu_samples = []
        stop_monitoring = threading.Event()
        
        def monitor_cpu():
            while not stop_monitoring.is_set():
                cpu_percent = psutil.cpu_percent(interval=0.1)
                cpu_samples.append(cpu_percent)
        
        # Start CPU monitoring
        cpu_thread = threading.Thread(target=monitor_cpu)
        cpu_thread.start()
        
        try:
            # Generate load
            for _ in range(100):
                client.get("/health")
                time.sleep(0.01)  # Small delay between requests
            
        finally:
            stop_monitoring.set()
            cpu_thread.join()
        
        if cpu_samples:
            avg_cpu = sum(cpu_samples) / len(cpu_samples)
            max_cpu = max(cpu_samples)
            
            print(f"CPU Usage - Average: {avg_cpu:.1f}%, Max: {max_cpu:.1f}%")
            
            # CPU usage should be reasonable
            assert avg_cpu < 50, f"Average CPU usage too high: {avg_cpu:.1f}%"
            assert max_cpu < 90, f"Peak CPU usage too high: {max_cpu:.1f}%"


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client():
    """Async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac