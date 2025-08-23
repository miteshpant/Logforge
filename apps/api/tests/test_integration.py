"""
Integration tests for end-to-end log processing pipeline
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
import json

from fastapi.testclient import TestClient
from httpx import AsyncClient

from main import app
from models import LogEntry, BatchLogEntry
from parsers import ParserFactory
from storage_config import StorageConfigManager


class TestEndToEndLogIngestion:
    """Test complete log ingestion pipeline"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_json_ingestion_pipeline(self, mock_process, mock_clickhouse, async_client, sample_structured_json):
        """Test complete JSON log ingestion pipeline"""
        # Mock ClickHouse insertion success
        mock_clickhouse.insert.return_value = None
        
        # Make the background processor actually process logs
        def actual_process(*args, **kwargs):
            # This would normally insert to ClickHouse
            pass
        mock_process.side_effect = actual_process
        
        # Send log via API
        response = await async_client.post("/v1/ingest/logs", json=sample_structured_json)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        
        # Verify background processor was called
        mock_process.assert_called_once()
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_nginx_to_clickhouse_pipeline(self, mock_process, mock_clickhouse, async_client, sample_nginx_log):
        """Test Nginx log parsing and storage pipeline"""
        mock_clickhouse.insert.return_value = None
        
        # Capture processed logs
        processed_logs = []
        def capture_process(logs):
            processed_logs.extend(logs)
        mock_process.side_effect = capture_process
        
        # Send Nginx log
        response = await async_client.post("/v1/ingest/nginx", 
                                         data=sample_nginx_log,
                                         headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        
        # Verify log was parsed correctly
        mock_process.assert_called_once()
        call_args = mock_process.call_args[0][0]
        assert len(call_args) == 1
        
        log_entry = call_args[0]
        assert isinstance(log_entry, LogEntry)
        assert log_entry.src_ip == "192.168.1.100"
        assert log_entry.status == 200
        assert log_entry.attrs["method"] == "GET"
    
    @patch('main.clickhouse_client')
    async def test_query_after_ingestion(self, mock_clickhouse, async_client, sample_log_entry):
        """Test querying logs after ingestion"""
        # Mock ClickHouse query response
        mock_result = Mock()
        mock_result.result_rows = [
            (
                sample_log_entry.ts,
                sample_log_entry.host,
                sample_log_entry.service,
                sample_log_entry.level,
                sample_log_entry.msg,
                sample_log_entry.trace_id,
                sample_log_entry.span_id,
                json.dumps(sample_log_entry.attrs),
                sample_log_entry.status,
                sample_log_entry.src_ip,
                sample_log_entry.user_id
            )
        ]
        mock_clickhouse.query.return_value = mock_result
        
        # Query for the log
        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z"
        }
        
        response = await async_client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["logs"]) == 1
        returned_log = data["logs"][0]
        assert returned_log["host"] == sample_log_entry.host
        assert returned_log["level"] == sample_log_entry.level
        assert returned_log["msg"] == sample_log_entry.msg


class TestMultiFormatIngestionPipeline:
    """Test ingestion pipeline with multiple log formats"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_batch_mixed_formats(self, mock_process, mock_clickhouse, async_client,
                                     sample_structured_json, sample_nginx_log, sample_syslog_rfc3164):
        """Test batch ingestion with mixed log formats"""
        mock_clickhouse.insert.return_value = None
        
        processed_logs = []
        def capture_process(logs):
            processed_logs.extend(logs)
        mock_process.side_effect = capture_process
        
        # Send mixed format batch
        batch_data = {
            "logs": [
                {"format": "json", "data": sample_structured_json},
                {"format": "nginx", "data": sample_nginx_log},
                {"format": "syslog", "data": sample_syslog_rfc3164}
            ]
        }
        
        response = await async_client.post("/v1/ingest/batch", json=batch_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["count"] == 3
        
        # Verify all logs were processed
        mock_process.assert_called_once()
        call_args = mock_process.call_args[0][0]
        assert len(call_args) == 3
        
        # Verify different parsers were used
        json_log, nginx_log, syslog_log = call_args
        
        # JSON log should have trace info
        assert json_log.trace_id == "trace123"
        
        # Nginx log should have IP and status
        assert nginx_log.src_ip == "192.168.1.100"
        assert nginx_log.status == 200
        
        # Syslog should have host info
        assert syslog_log.host == "web-server"
    
    @patch('main.clickhouse_client') 
    async def test_auto_format_detection_pipeline(self, mock_clickhouse, async_client):
        """Test automatic format detection pipeline"""
        mock_clickhouse.insert.return_value = None
        
        # Test various formats via auto-detection endpoint
        test_cases = [
            ({"level": "info", "message": "JSON log"}, "json"),
            ('192.168.1.1 - - [25/Dec/2023:10:00:00 +0000] "GET / HTTP/1.1" 200 1234', "nginx"),
            ("<34>Dec 25 10:00:00 host service: syslog message", "syslog"),
            ("CEF:0|Vendor|Product|1.0|100|Event|5|msg=CEF log", "cef"),
            ("2023-12-25 10:00:00 INFO Plain text log", "text")
        ]
        
        for log_data, expected_format in test_cases:
            if isinstance(log_data, dict):
                response = await async_client.post("/v1/ingest/auto", json=log_data)
            else:
                response = await async_client.post("/v1/ingest/auto", 
                                                 data=log_data,
                                                 headers={"Content-Type": "text/plain"})
            
            assert response.status_code == 202
            data = response.json()
            assert data["detected_format"] == expected_format


class TestStorageIntegration:
    """Test integration with storage backends"""
    
    @patch('storage_config.boto3')
    @patch('main.clickhouse_client')
    def test_customer_specific_storage(self, mock_clickhouse, mock_boto3, client):
        """Test customer-specific storage configuration"""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client
        
        # Mock storage config manager
        config = {
            "customer_configs": {
                "enterprise-customer": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "enterprise-logs",
                        "region": "us-east-1"
                    }
                }
            }
        }
        
        storage_manager = StorageConfigManager(config)
        
        # Test that customer gets dedicated storage client
        client_instance = storage_manager.get_storage_client("enterprise-customer")
        assert client_instance == mock_s3_client
        
        # Verify S3 client was created with correct parameters
        mock_boto3.client.assert_called_once()
        call_args = mock_boto3.client.call_args
        assert call_args[0][0] == 's3'
        assert call_args[1]['region_name'] == 'us-east-1'
    
    @patch('main.clickhouse_client')
    def test_clickhouse_storage_policy_generation(self, mock_clickhouse):
        """Test ClickHouse storage policy generation for customers"""
        storage_config = {
            "type": "s3",
            "bucket": "customer-logs",
            "region": "us-west-2",
            "access_key": "customer-key",
            "secret_key": "customer-secret"
        }
        
        storage_manager = StorageConfigManager({})
        policy_xml = storage_manager.generate_clickhouse_storage_policy("customer-policy", storage_config)
        
        # Verify policy contains correct S3 configuration
        assert "<type>s3</type>" in policy_xml
        assert "<endpoint>https://customer-logs.s3.us-west-2.amazonaws.com/</endpoint>" in policy_xml
        assert "<access_key_id>customer-key</access_key_id>" in policy_xml


class TestErrorHandlingIntegration:
    """Test error handling across the pipeline"""
    
    @patch('main.clickhouse_client')
    async def test_clickhouse_connection_failure(self, mock_clickhouse, async_client):
        """Test handling of ClickHouse connection failures"""
        # Mock ClickHouse connection failure
        mock_clickhouse.query.side_effect = Exception("Connection refused")
        
        query_data = {
            "query": "level=error",
            "start_time": "2023-12-25T00:00:00Z", 
            "end_time": "2023-12-25T23:59:59Z"
        }
        
        response = await async_client.post("/v1/query", json=query_data)
        
        # Should return proper error response
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
    
    @patch('main.process_logs_background')
    async def test_parser_error_handling(self, mock_process, async_client, malformed_logs):
        """Test handling of parser errors"""
        # Test various malformed logs
        error_cases = [
            ("/v1/ingest/nginx", malformed_logs["malformed_nginx"]),
            ("/v1/ingest/syslog", malformed_logs["invalid_syslog"]),
            ("/v1/ingest/cef", malformed_logs["invalid_cef"])
        ]
        
        for endpoint, bad_data in error_cases:
            response = await async_client.post(endpoint,
                                             data=bad_data,
                                             headers={"Content-Type": "text/plain"})
            
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            assert "parse" in data["error"].lower()
    
    async def test_oversized_payload_handling(self, async_client, malformed_logs):
        """Test handling of oversized payloads"""
        # Create very large payload
        large_log = {"message": malformed_logs["oversized_message"]}
        
        response = await async_client.post("/v1/ingest/logs", json=large_log)
        
        # Should either accept or reject with proper error code
        assert response.status_code in [202, 413, 422]
        
        if response.status_code in [413, 422]:
            data = response.json()
            assert "error" in data


class TestPerformanceIntegration:
    """Test performance characteristics of the pipeline"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_high_throughput_ingestion(self, mock_process, mock_clickhouse, async_client, performance_log_batch):
        """Test high-throughput log ingestion"""
        import asyncio
        import time
        
        mock_clickhouse.insert.return_value = None
        
        # Create batch of 1000 logs
        batch_data = {"logs": performance_log_batch}
        
        # Send multiple concurrent batches
        start_time = time.time()
        tasks = []
        for i in range(5):  # 5 concurrent batches = 5000 logs total
            task = async_client.post("/v1/ingest/logs", json=batch_data)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        # All requests should succeed
        assert all(r.status_code == 202 for r in responses)
        
        # Calculate throughput
        total_logs = 5 * len(performance_log_batch)  # 5 batches
        throughput = total_logs / elapsed
        
        # Should achieve reasonable throughput (adjust based on your performance targets)
        assert throughput > 1000, f"Throughput too low: {throughput} logs/sec"
        
        # Background processor should be called for each batch
        assert mock_process.call_count == 5
    
    @patch('main.clickhouse_client')
    async def test_query_performance_large_dataset(self, mock_clickhouse, async_client):
        """Test query performance with large dataset simulation"""
        import time
        
        # Mock large result set (simulate 10k results)
        large_result_set = []
        base_time = datetime.now(timezone.utc)
        
        for i in range(10000):
            row = (
                base_time,
                f"host-{i % 100}",
                f"service-{i % 10}",
                "info",
                f"Log message {i}",
                f"trace-{i}",
                f"span-{i}", 
                '{"index": ' + str(i) + '}',
                200,
                f"192.168.1.{i % 255}",
                f"user-{i}"
            )
            large_result_set.append(row)
        
        mock_result = Mock()
        mock_result.result_rows = large_result_set
        mock_clickhouse.query.return_value = mock_result
        
        # Execute query
        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z",
            "limit": 10000
        }
        
        start_time = time.time()
        response = await async_client.post("/v1/query", json=query_data)
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 10000
        
        # Should process large result set in reasonable time
        assert elapsed < 5.0, f"Query processing too slow: {elapsed}s for 10k results"
    
    @patch('main.clickhouse_client')
    async def test_concurrent_queries(self, mock_clickhouse, async_client):
        """Test handling of concurrent queries"""
        import asyncio
        import time
        
        # Mock query result
        mock_result = Mock()
        mock_result.result_rows = [
            (datetime.now(timezone.utc), "host", "service", "info", "message", None, None, '{}', None, None, None)
        ]
        mock_clickhouse.query.return_value = mock_result
        
        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z"
        }
        
        # Execute 20 concurrent queries
        start_time = time.time()
        tasks = [async_client.post("/v1/query", json=query_data) for _ in range(20)]
        responses = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        # All queries should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Should handle concurrent queries in reasonable time
        assert elapsed < 2.0, f"Concurrent queries too slow: {elapsed}s for 20 queries"
        
        # ClickHouse should be queried for each request
        assert mock_clickhouse.query.call_count == 20


class TestDataConsistencyIntegration:
    """Test data consistency across the pipeline"""
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_log_field_preservation(self, mock_process, mock_clickhouse, async_client):
        """Test that all log fields are preserved through the pipeline"""
        mock_clickhouse.insert.return_value = None
        
        # Capture what gets processed
        processed_logs = []
        def capture_logs(logs):
            processed_logs.extend(logs)
        mock_process.side_effect = capture_logs
        
        # Send comprehensive log with all fields
        comprehensive_log = {
            "timestamp": "2023-12-25T10:00:00.123Z",
            "level": "warn",
            "logger": "com.example.Service",
            "message": "Complex operation completed",
            "thread": "worker-thread-1",
            "user_id": "user-12345",
            "session_id": "sess-abcdef",
            "request_id": "req-xyz789",
            "http_method": "POST",
            "http_url": "/api/complex-operation",
            "http_status_code": 201,
            "response_time_ms": 1250,
            "database_queries": 5,
            "cache_hits": 3,
            "cache_misses": 2,
            "memory_usage_mb": 145.67,
            "cpu_usage_percent": 23.4,
            "mdc": {
                "traceId": "trace-complex-123",
                "spanId": "span-complex-456",
                "baggage": {"environment": "production"}
            },
            "tags": ["performance", "database", "cache"],
            "exception": {
                "type": "ValidationWarning",
                "message": "Non-critical validation warning",
                "stack_trace": "Stack trace would be here..."
            }
        }
        
        response = await async_client.post("/v1/ingest/logs", json=comprehensive_log)
        assert response.status_code == 202
        
        # Verify all important fields were preserved
        assert len(processed_logs) == 1
        log_entry = processed_logs[0]
        
        assert log_entry.level == "warn"
        assert log_entry.msg == "Complex operation completed"
        assert log_entry.user_id == "user-12345"
        assert log_entry.trace_id == "trace-complex-123"
        assert log_entry.span_id == "span-complex-456"
        assert log_entry.status == 201
        assert log_entry.attrs["http_method"] == "POST"
        assert log_entry.attrs["response_time_ms"] == 1250
        assert log_entry.attrs["database_queries"] == 5
        assert log_entry.attrs["memory_usage_mb"] == 145.67
    
    @patch('main.clickhouse_client')
    async def test_timestamp_consistency(self, mock_clickhouse, async_client):
        """Test timestamp handling consistency"""
        # Test various timestamp formats
        timestamp_formats = [
            "2023-12-25T10:00:00Z",
            "2023-12-25T10:00:00.123Z", 
            "2023-12-25T10:00:00+00:00",
            "2023-12-25T10:00:00.123456+00:00",
            "2023-12-25 10:00:00",
            "Dec 25 10:00:00"  # Syslog format
        ]
        
        processed_logs = []
        
        for ts_format in timestamp_formats[:4]:  # Test JSON formats
            log_data = {
                "timestamp": ts_format,
                "level": "info",
                "message": f"Test timestamp {ts_format}"
            }
            
            with patch('main.process_logs_background') as mock_process:
                def capture_logs(logs):
                    processed_logs.extend(logs)
                mock_process.side_effect = capture_logs
                
                response = await async_client.post("/v1/ingest/logs", json=log_data)
                assert response.status_code == 202
        
        # All timestamps should be parsed into datetime objects
        assert len(processed_logs) == 4
        for log_entry in processed_logs:
            assert isinstance(log_entry.ts, datetime)
            assert log_entry.ts.tzinfo is not None  # Should have timezone info
    
    @patch('main.clickhouse_client')
    @patch('main.process_logs_background')
    async def test_unicode_and_special_characters(self, mock_process, mock_clickhouse, async_client):
        """Test handling of Unicode and special characters"""
        mock_clickhouse.insert.return_value = None
        
        processed_logs = []
        def capture_logs(logs):
            processed_logs.extend(logs)
        mock_process.side_effect = capture_logs
        
        # Test various Unicode and special character scenarios
        unicode_log = {
            "level": "info",
            "message": "Unicode test: 你好世界 🌍 emoji 🚀 åäö ñoël",
            "user": "João",
            "location": "São Paulo",
            "description": "Test with quotes 'single' \"double\" and symbols @#$%^&*()",
            "json_field": '{"nested": "unicode 测试", "emoji": "🎉"}',
            "special_chars": "Line1\nLine2\tTabbed\rCarriage\\Backslash"
        }
        
        response = await async_client.post("/v1/ingest/logs", json=unicode_log)
        assert response.status_code == 202
        
        # Verify Unicode characters are preserved
        assert len(processed_logs) == 1
        log_entry = processed_logs[0]
        
        assert "你好世界" in log_entry.msg
        assert "🌍" in log_entry.msg
        assert "🚀" in log_entry.msg
        assert log_entry.attrs["user"] == "João"
        assert log_entry.attrs["location"] == "São Paulo"
        assert "\"double\"" in log_entry.attrs["description"]
        assert "\n" in log_entry.attrs["special_chars"]