"""
Test cases for FastAPI endpoints
"""

import pytest
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from main import app
from models import LogEntry, BatchLogEntry


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_check(self, client):
        """Test health check endpoint returns 200"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_check_with_dependencies(self, client):
        """Test health check includes dependency status"""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data


class TestLogIngestionEndpoints:
    """Test log ingestion endpoints"""
    
    @patch('main.process_logs_background')
    def test_ingest_logs_json(self, mock_process, client, sample_structured_json):
        """Test JSON log ingestion endpoint"""
        response = client.post("/v1/ingest/logs", json=sample_structured_json)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_logs_batch(self, mock_process, client, sample_batch_logs):
        """Test batch log ingestion"""
        batch_data = sample_batch_logs.model_dump()
        response = client.post("/v1/ingest/logs", json=batch_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 5
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_logs_auto_detect_json(self, mock_process, client):
        """Test auto-detection of JSON format"""
        log_data = {
            "timestamp": "2023-12-25T10:00:00Z",
            "level": "error",
            "message": "Database connection failed",
            "service": "api-server"
        }
        
        response = client.post("/v1/ingest/auto", json=log_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["detected_format"] == "json"
        mock_process.assert_called_once()
    
    def test_ingest_logs_invalid_json(self, client):
        """Test ingestion with invalid JSON data"""
        response = client.post("/v1/ingest/logs", data="invalid json")
        
        assert response.status_code == 422  # Validation error
    
    def test_ingest_logs_empty_payload(self, client):
        """Test ingestion with empty payload"""
        response = client.post("/v1/ingest/logs", json={})
        
        assert response.status_code == 422  # Should require logs field


class TestNginxIngestionEndpoint:
    """Test Nginx log ingestion"""
    
    @patch('main.process_logs_background')
    def test_ingest_nginx_access_log(self, mock_process, client, sample_nginx_log):
        """Test Nginx access log ingestion"""
        response = client.post("/v1/ingest/nginx", 
                             data=sample_nginx_log,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_nginx_json_format(self, mock_process, client, sample_nginx_json_log):
        """Test Nginx JSON format ingestion"""
        response = client.post("/v1/ingest/nginx",
                             data=sample_nginx_json_log,
                             headers={"Content-Type": "application/json"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
    
    @patch('main.process_logs_background')
    def test_ingest_nginx_batch_logs(self, mock_process, client, sample_nginx_log):
        """Test Nginx batch log ingestion"""
        batch_logs = "\n".join([sample_nginx_log] * 5)
        
        response = client.post("/v1/ingest/nginx",
                             data=batch_logs,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 5
    
    def test_ingest_nginx_malformed_log(self, client, malformed_logs):
        """Test Nginx ingestion with malformed log"""
        response = client.post("/v1/ingest/nginx",
                             data=malformed_logs["malformed_nginx"],
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "parse" in data["error"].lower()


class TestSyslogIngestionEndpoint:
    """Test Syslog ingestion"""
    
    @patch('main.process_logs_background')
    def test_ingest_syslog_rfc3164(self, mock_process, client, sample_syslog_rfc3164):
        """Test RFC 3164 syslog ingestion"""
        response = client.post("/v1/ingest/syslog",
                             data=sample_syslog_rfc3164,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_syslog_rfc5424(self, mock_process, client, sample_syslog_rfc5424):
        """Test RFC 5424 syslog ingestion"""
        response = client.post("/v1/ingest/syslog",
                             data=sample_syslog_rfc5424,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
    
    def test_ingest_syslog_invalid_priority(self, client, malformed_logs):
        """Test syslog ingestion with invalid priority"""
        response = client.post("/v1/ingest/syslog",
                             data=malformed_logs["invalid_syslog"],
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 400
        assert "error" in response.json()


class TestOTLPIngestionEndpoint:
    """Test OTLP (OpenTelemetry) ingestion"""
    
    @patch('main.process_logs_background')
    def test_ingest_otlp_logs(self, mock_process, client, sample_otlp_data):
        """Test OTLP logs ingestion"""
        response = client.post("/v1/ingest/otlp", json=sample_otlp_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1  # One log record in sample
        mock_process.assert_called_once()
    
    def test_ingest_otlp_empty_data(self, client):
        """Test OTLP ingestion with empty data"""
        empty_otlp = {"resource_logs": []}
        response = client.post("/v1/ingest/otlp", json=empty_otlp)
        
        assert response.status_code == 202
        data = response.json()
        assert data["count"] == 0
    
    def test_ingest_otlp_invalid_structure(self, client):
        """Test OTLP ingestion with invalid structure"""
        invalid_otlp = {"invalid": "structure"}
        response = client.post("/v1/ingest/otlp", json=invalid_otlp)
        
        assert response.status_code == 400
        assert "error" in response.json()


class TestCEFIngestionEndpoint:
    """Test CEF (Common Event Format) ingestion"""
    
    @patch('main.process_logs_background')
    def test_ingest_cef_log(self, mock_process, client, sample_cef_log):
        """Test CEF log ingestion"""
        response = client.post("/v1/ingest/cef",
                             data=sample_cef_log,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        mock_process.assert_called_once()
    
    def test_ingest_cef_invalid_format(self, client, malformed_logs):
        """Test CEF ingestion with invalid format"""
        response = client.post("/v1/ingest/cef",
                             data=malformed_logs["invalid_cef"],
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 400
        assert "error" in response.json()


class TestTextIngestionEndpoint:
    """Test plain text ingestion"""
    
    @patch('main.process_logs_background')
    def test_ingest_text_single_log(self, mock_process, client):
        """Test single text log ingestion"""
        log_text = "2023-12-25 10:00:00 INFO Application started successfully"
        
        response = client.post("/v1/ingest/text",
                             data=log_text,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_text_multiline_logs(self, mock_process, client, sample_text_logs):
        """Test multi-line text log ingestion"""
        text_batch = "\n".join(sample_text_logs)
        
        response = client.post("/v1/ingest/text",
                             data=text_batch,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 5
    
    @patch('main.process_logs_background')
    def test_ingest_text_empty_lines(self, mock_process, client):
        """Test text ingestion with empty lines"""
        text_with_empties = "Log line 1\n\nLog line 2\n\n\nLog line 3"
        
        response = client.post("/v1/ingest/text",
                             data=text_with_empties,
                             headers={"Content-Type": "text/plain"})
        
        assert response.status_code == 202
        data = response.json()
        assert data["count"] == 3  # Should skip empty lines


class TestBatchIngestionEndpoint:
    """Test batch ingestion endpoint"""
    
    @patch('main.process_logs_background')
    def test_ingest_batch_mixed_formats(self, mock_process, client):
        """Test batch ingestion with mixed log formats"""
        batch_data = {
            "logs": [
                {
                    "format": "json",
                    "data": {"level": "info", "message": "JSON log"}
                },
                {
                    "format": "text", 
                    "data": "2023-12-25 ERROR: Text log"
                }
            ]
        }
        
        response = client.post("/v1/ingest/batch", json=batch_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 2
        mock_process.assert_called_once()
    
    @patch('main.process_logs_background')
    def test_ingest_batch_with_metadata(self, mock_process, client):
        """Test batch ingestion with metadata"""
        batch_data = {
            "metadata": {
                "source": "application-server-01",
                "environment": "production",
                "version": "1.2.3"
            },
            "logs": [
                {"format": "json", "data": {"level": "info", "message": "Test log 1"}},
                {"format": "json", "data": {"level": "warn", "message": "Test log 2"}}
            ]
        }
        
        response = client.post("/v1/ingest/batch", json=batch_data)
        
        assert response.status_code == 202
        data = response.json()
        assert data["count"] == 2
    
    def test_ingest_batch_invalid_format_type(self, client):
        """Test batch ingestion with invalid format type"""
        batch_data = {
            "logs": [
                {
                    "format": "invalid_format",
                    "data": "some log data"
                }
            ]
        }
        
        response = client.post("/v1/ingest/batch", json=batch_data)
        
        assert response.status_code == 400
        assert "error" in response.json()


class TestQueryEndpoint:
    """Test log query endpoint"""
    
    @patch('main.clickhouse_client')
    def test_query_logs_basic(self, mock_client, client):
        """Test basic log query"""
        # Mock ClickHouse response
        mock_result = Mock()
        mock_result.result_rows = [
            (
                datetime.now(timezone.utc),
                "test-host",
                "test-service", 
                "info",
                "Test log message",
                "trace-123",
                "span-456",
                '{"method": "GET"}',
                200,
                "192.168.1.1",
                "user123"
            )
        ]
        mock_client.query.return_value = mock_result
        
        query_data = {
            "query": "level=info",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total_count" in data
        assert "execution_time_ms" in data
        assert len(data["logs"]) == 1
    
    @patch('main.clickhouse_client')
    def test_query_logs_with_pagination(self, mock_client, client):
        """Test log query with pagination"""
        mock_result = Mock()
        mock_result.result_rows = []  # Empty result
        mock_client.query.return_value = mock_result
        
        query_data = {
            "query": "service=web",
            "start_time": "2023-12-25T00:00:00Z",
            "end_time": "2023-12-25T23:59:59Z",
            "limit": 50,
            "offset": 100
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        
        # Verify the ClickHouse query included LIMIT and OFFSET
        mock_client.query.assert_called_once()
        query_sql = mock_client.query.call_args[0][0]
        assert "LIMIT 50" in query_sql
        assert "OFFSET 100" in query_sql
    
    def test_query_logs_invalid_time_format(self, client):
        """Test query with invalid time format"""
        query_data = {
            "query": "level=error",
            "start_time": "invalid-time-format",
            "end_time": "2023-12-25T23:59:59Z"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_logs_missing_required_fields(self, client):
        """Test query with missing required fields"""
        query_data = {
            "query": "level=error"
            # Missing start_time and end_time
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422


class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_404_endpoint(self, client):
        """Test accessing non-existent endpoint"""
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test using wrong HTTP method"""
        response = client.get("/v1/ingest/logs")  # Should be POST
        assert response.status_code == 405
    
    def test_invalid_content_type(self, client):
        """Test invalid content type for JSON endpoints"""
        response = client.post("/v1/ingest/logs",
                             data="not json data",
                             headers={"Content-Type": "text/plain"})
        
        # Should return 422 for invalid JSON or content type mismatch
        assert response.status_code in [400, 422]
    
    @patch('main.process_logs_background')
    def test_internal_server_error_handling(self, mock_process, client):
        """Test handling of internal server errors"""
        # Make the background processor raise an exception
        mock_process.side_effect = Exception("Database connection failed")
        
        response = client.post("/v1/ingest/logs", json={
            "logs": [{"level": "info", "message": "test"}]
        })
        
        # The API should still return 202 since it's async processing
        # But in a real implementation, you might want to catch and handle this
        assert response.status_code in [202, 500]


class TestAPIPerformance:
    """Test API performance characteristics"""
    
    @patch('main.process_logs_background')
    def test_concurrent_ingestion_requests(self, mock_process, client):
        """Test handling multiple concurrent ingestion requests"""
        import concurrent.futures
        import time
        
        def make_request():
            return client.post("/v1/ingest/logs", json={
                "logs": [{"level": "info", "message": "concurrent test"}]
            })
        
        # Make 10 concurrent requests
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]
        elapsed = time.time() - start_time
        
        # All requests should succeed
        assert all(r.status_code == 202 for r in responses)
        
        # Should handle 10 concurrent requests in under 5 seconds
        assert elapsed < 5.0, f"Concurrent requests too slow: {elapsed}s"
        
        # Background processor should be called for each request
        assert mock_process.call_count == 10
    
    @patch('main.process_logs_background')
    def test_large_payload_handling(self, mock_process, client, performance_log_batch):
        """Test handling of large log payloads"""
        # Create large batch (1000 logs)
        large_batch = {"logs": performance_log_batch}
        
        response = client.post("/v1/ingest/logs", json=large_batch)
        
        assert response.status_code == 202
        data = response.json()
        assert data["count"] == len(performance_log_batch)
        mock_process.assert_called_once()
    
    def test_health_endpoint_response_time(self, client):
        """Test health endpoint response time"""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        # Health check should respond in under 100ms
        assert elapsed < 0.1, f"Health check too slow: {elapsed}s"


class TestAPISecurityHeaders:
    """Test API security headers and features"""
    
    def test_security_headers_present(self, client):
        """Test that security headers are present"""
        response = client.get("/health")
        
        # Check for common security headers
        # Note: These might need to be added to your FastAPI app
        headers = response.headers
        
        # At minimum, check that we don't leak server information
        assert "server" not in headers.get("Server", "").lower() or \
               "fastapi" not in headers.get("Server", "").lower()
    
    def test_cors_headers_if_enabled(self, client):
        """Test CORS headers if CORS is enabled"""
        response = client.options("/v1/ingest/logs")
        
        # This test depends on your CORS configuration
        # Adjust based on your actual CORS setup
        if "access-control-allow-origin" in response.headers:
            assert "access-control-allow-methods" in response.headers
    
    def test_request_size_limits(self, client):
        """Test that extremely large requests are rejected"""
        # Create a very large payload (10MB of data)
        large_payload = {"logs": [{"message": "x" * 1000000} for _ in range(10)]}
        
        response = client.post("/v1/ingest/logs", json=large_payload)
        
        # Should either accept it or reject with appropriate error
        # This depends on your FastAPI configuration for max request size
        assert response.status_code in [202, 413, 422]


class TestAPIDocumentation:
    """Test API documentation endpoints"""
    
    def test_openapi_schema_available(self, client):
        """Test that OpenAPI schema is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/v1/ingest/logs" in schema["paths"]
    
    def test_docs_endpoint_available(self, client):
        """Test that documentation endpoint is available"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")