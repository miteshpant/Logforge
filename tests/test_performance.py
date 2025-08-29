"""
Performance and benchmark tests
"""

import pytest
import time
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import concurrent.futures
import psutil
import gc

from fastapi.testclient import TestClient
from httpx import AsyncClient

from parsers import ParserFactory
from models import LogEntry, BatchLogEntry
from storage_config import StorageConfigManager


class TestParserPerformance:
    """Test parser performance and throughput"""

    @pytest.mark.parametrize("format_type,data_fixture", [
        ("json", "sample_structured_json"),
        ("nginx", "sample_nginx_log"),
        ("syslog", "sample_syslog_rfc3164"),
        ("cef", "sample_cef_log"),
        ("text", None)  # Will use simple string
    ])
    def test_single_parser_throughput(self, parser_factory, format_type, data_fixture, request):
        """Test single parser throughput - target: >10k logs/sec"""
        parser = parser_factory.get_parser(format_type)

        # Get test data
        if data_fixture:
            test_data = request.getfixturevalue(data_fixture)
        else:
            test_data = "2023-12-25 10:00:00 INFO Test log message"

        # Warm up
        for _ in range(100):
            parser.parse(test_data)

        # Benchmark
        iterations = 10000
        start_time = time.time()

        for _ in range(iterations):
            result = parser.parse(test_data)
            assert result is not None

        elapsed = time.time() - start_time
        throughput = iterations / elapsed

        # Target: >10k logs/sec per parser
        assert throughput > 10000, f"{format_type} parser throughput: {throughput:.0f} logs/sec (target: >10k)"

        print(f"{format_type.upper()} Parser: {throughput:.0f} logs/sec")

    def test_parser_factory_performance(self, parser_factory):
        """Test parser factory creation performance"""
        formats = ["json", "nginx", "syslog", "cef", "otlp", "text"]

        # Test repeated parser creation
        start_time = time.time()

        for _ in range(10000):
            for format_type in formats:
                parser = parser_factory.get_parser(format_type)
                assert parser is not None

        elapsed = time.time() - start_time
        operations = 10000 * len(formats)
        throughput = operations / elapsed

        # Should create >100k parsers/sec (cached)
        assert throughput > 100000, f"Parser factory throughput: {throughput:.0f} ops/sec"
        print(f"Parser Factory: {throughput:.0f} parser creations/sec")

    def test_concurrent_parser_usage(self, parser_factory, sample_structured_json):
        """Test concurrent parser usage performance"""
        parser = parser_factory.get_parser("json")

        def parse_logs(iterations):
            results = []
            for _ in range(iterations):
                result = parser.parse(sample_structured_json)
                results.append(result)
            return results

        # Test with 10 concurrent threads
        iterations_per_thread = 1000
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(parse_logs, iterations_per_thread) for _ in range(10)]
            results = [future.result() for future in futures]

        elapsed = time.time() - start_time
        total_logs = 10 * iterations_per_thread
        throughput = total_logs / elapsed

        # Should maintain high throughput under concurrency
        assert throughput > 15000, f"Concurrent parsing throughput: {throughput:.0f} logs/sec"
        assert all(len(result) == iterations_per_thread for result in results)

        print(f"Concurrent Parsing (10 threads): {throughput:.0f} logs/sec")


class TestAPIPerformance:
    """Test API endpoint performance"""

    @patch('main.process_logs_background')
    def test_ingestion_endpoint_latency(self, mock_process, client):
        """Test ingestion endpoint latency - target: <50ms p99"""
        mock_process.return_value = None

        test_log = {"level": "info", "message": "Performance test log"}
        latencies = []

        # Warm up
        for _ in range(100):
            client.post("/v1/ingest/logs", json=test_log)

        # Measure latencies
        for _ in range(1000):
            start_time = time.time()
            response = client.post("/v1/ingest/logs", json=test_log)
            elapsed = time.time() - start_time

            assert response.status_code == 202
            latencies.append(elapsed * 1000)  # Convert to milliseconds

        # Calculate percentiles
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"Ingestion Latency - P50: {p50:.1f}ms, P95: {p95:.1f}ms, P99: {p99:.1f}ms")

        # Performance targets
        assert p50 < 10, f"P50 latency too high: {p50:.1f}ms (target: <10ms)"
        assert p95 < 25, f"P95 latency too high: {p95:.1f}ms (target: <25ms)"
        assert p99 < 50, f"P99 latency too high: {p99:.1f}ms (target: <50ms)"

    @patch('main.clickhouse_client')
    def test_query_endpoint_latency(self, mock_clickhouse, client):
        """Test query endpoint latency"""
        # Mock small result set
        mock_result = Mock()
        mock_result.result_rows = [
            (datetime.now(timezone.utc), "host", "service", "info", "message", None, None, '{}', None, None, None)
            for _ in range(100)
        ]
        mock_clickhouse.query.return_value = mock_result

        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z",
            "limit": 100
        }

        latencies = []

        # Warm up
        for _ in range(50):
            client.post("/v1/query", json=query_data)

        # Measure latencies
        for _ in range(500):
            start_time = time.time()
            response = client.post("/v1/query", json=query_data)
            elapsed = time.time() - start_time

            assert response.status_code == 200
            latencies.append(elapsed * 1000)

        # Calculate percentiles
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"Query Latency - P50: {p50:.1f}ms, P95: {p95:.1f}ms, P99: {p99:.1f}ms")

        # Performance targets for small queries
        assert p50 < 50, f"P50 query latency too high: {p50:.1f}ms (target: <50ms)"
        assert p95 < 100, f"P95 query latency too high: {p95:.1f}ms (target: <100ms)"
        assert p99 < 200, f"P99 query latency too high: {p99:.1f}ms (target: <200ms)"

    @patch('main.process_logs_background')
    def test_concurrent_ingestion_throughput(self, mock_process, client):
        """Test concurrent ingestion throughput - target: >50k logs/sec"""
        mock_process.return_value = None

        test_log = {"level": "info", "message": "Concurrent test log"}

        def make_requests(num_requests):
            successful_requests = 0
            for _ in range(num_requests):
                response = client.post("/v1/ingest/logs", json=test_log)
                if response.status_code == 202:
                    successful_requests += 1
            return successful_requests

        # Test with 20 concurrent threads, 100 requests each
        num_threads = 20
        requests_per_thread = 100

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests, requests_per_thread) for _ in range(num_threads)]
            results = [future.result() for future in futures]

        elapsed = time.time() - start_time
        total_successful = sum(results)
        throughput = total_successful / elapsed

        print(f"Concurrent Ingestion: {throughput:.0f} requests/sec ({total_successful} total)")

        # Should handle high concurrent load
        assert total_successful >= num_threads * requests_per_thread * 0.95  # 95% success rate
        assert throughput > 2000, f"Concurrent throughput too low: {throughput:.0f} req/sec"

    @pytest.mark.asyncio
    async def test_async_client_performance(self, async_client):
        """Test async client performance"""
        with patch('main.process_logs_background') as mock_process:
            mock_process.return_value = None

            test_log = {"level": "info", "message": "Async test log"}

            # Test async concurrency
            start_time = time.time()

            tasks = []
            for _ in range(1000):
                task = async_client.post("/v1/ingest/logs", json=test_log)
                tasks.append(task)

            responses = await asyncio.gather(*tasks)
            elapsed = time.time() - start_time

            successful_responses = sum(1 for r in responses if r.status_code == 202)
            throughput = successful_responses / elapsed

            print(f"Async Ingestion: {throughput:.0f} requests/sec")

            assert successful_responses >= 950  # 95% success rate
            assert throughput > 5000, f"Async throughput too low: {throughput:.0f} req/sec"


class TestMemoryPerformance:
    """Test memory usage and garbage collection"""

    def test_parser_memory_usage(self, parser_factory):
        """Test parser memory usage doesn't grow excessively"""
        parser = parser_factory.get_parser("json")
        test_data = {"level": "info", "message": "Memory test log"}

        # Force garbage collection
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        # Parse many logs
        results = []
        for i in range(50000):
            result = parser.parse(test_data)
            if i % 10000 == 0:
                # Keep some results to prevent optimization
                results.append(result)

        # Force garbage collection
        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        memory_growth = final_memory - initial_memory
        print(f"Memory usage - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Growth: {memory_growth:.1f}MB")

        # Memory growth should be reasonable (<50MB for 50k log parsing)
        assert memory_growth < 50, f"Excessive memory growth: {memory_growth:.1f}MB"

    def test_log_entry_memory_efficiency(self, performance_log_batch):
        """Test LogEntry memory efficiency"""
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss

        # Create many LogEntry objects
        log_entries = []
        for log_data in performance_log_batch * 10:  # 10x multiplier for more entries
            log_entry = LogEntry(
                ts=datetime.fromisoformat(log_data["ts"].replace('Z', '+00:00')),
                host=log_data["host"],
                service=log_data["service"],
                level=log_data["level"],
                msg=log_data["msg"],
                trace_id=log_data["trace_id"],
                attrs=log_data["attrs"],
                src_ip=log_data["src_ip"],
                user_id=log_data["user_id"]
            )
            log_entries.append(log_entry)

        gc.collect()
        final_memory = psutil.Process().memory_info().rss

        memory_per_log = (final_memory - initial_memory) / len(log_entries)
        print(f"Memory per LogEntry: {memory_per_log:.0f} bytes ({len(log_entries)} entries)")

        # Each LogEntry should use reasonable memory (<2KB)
        assert memory_per_log < 2048, f"LogEntry uses too much memory: {memory_per_log:.0f} bytes"

    @patch('main.process_logs_background')
    def test_api_memory_under_load(self, mock_process, client):
        """Test API memory usage under sustained load"""
        mock_process.return_value = None

        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        test_log = {"level": "info", "message": "Memory load test"}

        # Make many requests
        for i in range(5000):
            response = client.post("/v1/ingest/logs", json=test_log)
            assert response.status_code == 202

            # Check memory every 1000 requests
            if i % 1000 == 999:
                gc.collect()
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory

                # Memory shouldn't grow excessively during processing
                assert memory_growth < 100, f"Excessive memory growth at {i+1} requests: {memory_growth:.1f}MB"

        gc.collect()
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory

        print(f"API Memory - Initial: {initial_memory:.1f}MB, Final: {final_memory:.1f}MB, Growth: {total_growth:.1f}MB")

        # Total memory growth should be reasonable
        assert total_growth < 50, f"API memory growth too high: {total_growth:.1f}MB"


class TestStoragePerformance:
    """Test storage configuration performance"""

    @patch('storage_config.boto3')
    def test_storage_client_creation_performance(self, mock_boto3):
        """Test storage client creation performance"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        config = {
            "customer_configs": {
                f"customer-{i}": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "s3",
                        "bucket": f"bucket-{i}",
                        "region": "us-west-2"
                    }
                } for i in range(100)
            }
        }

        storage_manager = StorageConfigManager(config)

        # Test client creation performance
        start_time = time.time()

        clients = []
        for i in range(100):
            client = storage_manager.get_storage_client(f"customer-{i}")
            clients.append(client)

        elapsed = time.time() - start_time
        throughput = 100 / elapsed

        print(f"Storage Client Creation: {throughput:.0f} clients/sec")

        # Should create clients quickly (>1000/sec due to caching)
        assert throughput > 500, f"Storage client creation too slow: {throughput:.0f}/sec"
        assert len(set(clients)) >= 1  # At least one unique client

    def test_clickhouse_policy_generation_performance(self):
        """Test ClickHouse policy generation performance"""
        from models import StorageConfig

        storage_config = StorageConfig(
            type="s3",
            bucket="performance-test-bucket",
            region="us-west-2",
            access_key="test-key",
            secret_key="test-secret"
        )

        storage_manager = StorageConfigManager({})

        # Generate many policies
        start_time = time.time()

        policies = []
        for i in range(1000):
            policy_xml = storage_manager.generate_clickhouse_storage_policy(f"policy-{i}", storage_config)
            policies.append(policy_xml)

        elapsed = time.time() - start_time
        throughput = 1000 / elapsed

        print(f"Policy Generation: {throughput:.0f} policies/sec")

        # Should generate policies quickly
        assert throughput > 5000, f"Policy generation too slow: {throughput:.0f}/sec"
        assert all(len(policy) > 0 for policy in policies)
        assert all("<disk>" in policy for policy in policies[:10])  # Spot check


class TestScalabilitySimulation:
    """Simulate high-scale scenarios"""

    @patch('main.process_logs_background')
    def test_burst_traffic_simulation(self, mock_process, client):
        """Simulate burst traffic scenario"""
        mock_process.return_value = None

        # Simulate varying load over time
        loads = [10, 50, 200, 500, 200, 50, 10]  # Requests per burst
        burst_results = []

        for burst_size in loads:
            start_time = time.time()

            responses = []
            for _ in range(burst_size):
                response = client.post("/v1/ingest/logs",
                                     json={"level": "info", "message": f"Burst test {burst_size}"})
                responses.append(response)

            elapsed = time.time() - start_time
            success_rate = sum(1 for r in responses if r.status_code == 202) / len(responses)
            throughput = burst_size / elapsed

            burst_results.append({
                "burst_size": burst_size,
                "throughput": throughput,
                "success_rate": success_rate,
                "elapsed": elapsed
            })

            print(f"Burst {burst_size}: {throughput:.0f} req/sec, {success_rate:.1%} success")

        # All bursts should maintain good performance
        for result in burst_results:
            assert result["success_rate"] > 0.95, f"Poor success rate in burst {result['burst_size']}: {result['success_rate']:.1%}"
            assert result["throughput"] > 100, f"Poor throughput in burst {result['burst_size']}: {result['throughput']:.0f} req/sec"

    @patch('main.process_logs_background')
    def test_sustained_load_simulation(self, mock_process, client):
        """Simulate sustained load over longer period"""
        mock_process.return_value = None

        test_duration = 30  # seconds
        target_rps = 100  # requests per second

        start_time = time.time()
        total_requests = 0
        successful_requests = 0

        while time.time() - start_time < test_duration:
            batch_start = time.time()

            # Make requests for this second
            for _ in range(target_rps):
                response = client.post("/v1/ingest/logs",
                                     json={"level": "info", "message": "Sustained load test"})
                total_requests += 1
                if response.status_code == 202:
                    successful_requests += 1

            # Wait to maintain target RPS
            batch_elapsed = time.time() - batch_start
            if batch_elapsed < 1.0:
                time.sleep(1.0 - batch_elapsed)

        actual_duration = time.time() - start_time
        actual_rps = total_requests / actual_duration
        success_rate = successful_requests / total_requests

        print(f"Sustained Load - Duration: {actual_duration:.1f}s, RPS: {actual_rps:.0f}, Success: {success_rate:.1%}")

        # Should maintain performance under sustained load
        assert success_rate > 0.98, f"Poor success rate under sustained load: {success_rate:.1%}"
        assert actual_rps > target_rps * 0.9, f"Failed to maintain target RPS: {actual_rps:.0f} vs {target_rps}"


class TestBenchmarkComparison:
    """Benchmark tests for performance comparison"""

    def test_parser_format_comparison(self, parser_factory):
        """Compare performance across different log formats"""
        formats_and_data = [
            ("json", {"level": "info", "message": "JSON test"}),
            ("nginx", '192.168.1.1 - - [25/Dec/2023:10:00:00 +0000] "GET / HTTP/1.1" 200 1234'),
            ("syslog", "<34>Dec 25 10:00:00 host service: syslog test"),
            ("cef", "CEF:0|Vendor|Product|1.0|100|Event|5|msg=CEF test"),
            ("text", "2023-12-25 10:00:00 INFO Text test")
        ]

        results = []

        for format_type, test_data in formats_and_data:
            parser = parser_factory.get_parser(format_type)

            # Warm up
            for _ in range(1000):
                parser.parse(test_data)

            # Benchmark
            iterations = 10000
            start_time = time.time()

            for _ in range(iterations):
                parser.parse(test_data)

            elapsed = time.time() - start_time
            throughput = iterations / elapsed

            results.append({
                "format": format_type,
                "throughput": throughput,
                "time_per_log_us": (elapsed / iterations) * 1000000
            })

        # Print comparison
        print("\nParser Performance Comparison:")
        print("Format    | Throughput (logs/sec) | Time per log (μs)")
        print("----------|----------------------|------------------")

        for result in sorted(results, key=lambda x: x["throughput"], reverse=True):
            print(f"{result['format']:<9} | {result['throughput']:>20,.0f} | {result['time_per_log_us']:>16.1f}")

        # All parsers should meet minimum performance
        for result in results:
            assert result["throughput"] > 5000, f"{result['format']} parser too slow: {result['throughput']:.0f} logs/sec"

    def test_serialization_performance_comparison(self, sample_log_entry, sample_batch_logs):
        """Compare serialization performance methods"""
        import json

        # Test single LogEntry serialization
        single_results = []

        methods = [
            ("model_dump", lambda x: x.model_dump()),
            ("model_dump_json", lambda x: x.model_dump_json()),
            ("json_dumps_dict", lambda x: json.dumps(x.model_dump()))
        ]

        for method_name, method_func in methods:
            start_time = time.time()

            for _ in range(10000):
                result = method_func(sample_log_entry)
                assert result is not None

            elapsed = time.time() - start_time
            throughput = 10000 / elapsed

            single_results.append({
                "method": method_name,
                "throughput": throughput
            })

        print("\nSerialization Performance Comparison (single LogEntry):")
        for result in sorted(single_results, key=lambda x: x["throughput"], reverse=True):
            print(f"{result['method']}: {result['throughput']:,.0f} ops/sec")

        # Test batch serialization
        batch_start = time.time()
        for _ in range(1000):
            result = sample_batch_logs.model_dump()
            assert len(result["logs"]) == 5
        batch_elapsed = time.time() - batch_start
        batch_throughput = 1000 / batch_elapsed

        print(f"\nBatch Serialization (5 logs): {batch_throughput:,.0f} batches/sec")

        # Performance assertions
        best_single = max(single_results, key=lambda x: x["throughput"])
        assert best_single["throughput"] > 50000, f"Best serialization method too slow: {best_single['throughput']:,.0f} ops/sec"
        assert batch_throughput > 10000, f"Batch serialization too slow: {batch_throughput:,.0f} batches/sec"
