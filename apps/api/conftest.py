"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Generator
from unittest.mock import Mock, AsyncMock, MagicMock
from faker import Faker

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import our modules
from main import app
from models import LogEntry, BatchLogEntry, OTLPLogsData
from parsers import ParserFactory
from storage_config import StorageConfigManager

fake = Faker()

# Test fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client for FastAPI app"""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
async def async_client() -> AsyncClient:
    """Async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_clickhouse_client():
    """Mock ClickHouse client"""
    mock_client = Mock()
    mock_client.query.return_value = Mock(result_rows=[])
    mock_client.insert.return_value = None
    return mock_client

@pytest.fixture
def mock_storage_manager():
    """Mock storage config manager"""
    mock_manager = Mock(spec=StorageConfigManager)
    return mock_manager

@pytest.fixture
def parser_factory():
    """Parser factory instance"""
    return ParserFactory()

# Sample log data fixtures
@pytest.fixture
def sample_log_entry() -> LogEntry:
    """Sample LogEntry for testing"""
    return LogEntry(
        ts=datetime.now(timezone.utc),
        host="test-host",
        service="test-service",
        level="info",
        msg="Test log message",
        trace_id="test-trace-123",
        span_id="test-span-456",
        attrs={
            "method": "GET",
            "uri": "/api/test",
            "status": 200,
            "duration_ms": 150,
            "user_id": "user123"
        },
        status=200,
        src_ip="192.168.1.100",
        user_id="user123"
    )

@pytest.fixture
def sample_batch_logs() -> BatchLogEntry:
    """Sample batch of logs"""
    logs = []
    for i in range(5):
        log = LogEntry(
            ts=datetime.now(timezone.utc),
            host=f"test-host-{i}",
            service="test-service",
            level="info" if i % 2 == 0 else "warn",
            msg=f"Test log message {i}",
            trace_id=f"test-trace-{i}",
            attrs={"sequence": i}
        )
        logs.append(log)
    
    return BatchLogEntry(logs=logs)

@pytest.fixture
def sample_nginx_log() -> str:
    """Sample Nginx access log"""
    return (
        '192.168.1.100 - user123 [25/Dec/2023:10:00:00 +0000] '
        '"GET /api/users/123 HTTP/1.1" 200 1234 '
        '"http://example.com/referrer" "Mozilla/5.0 (compatible; test)"'
    )

@pytest.fixture
def sample_nginx_log_with_timing() -> str:
    """Sample Nginx log with timing information"""
    return (
        '10.0.0.1 - - [25/Dec/2023:10:00:00 +0000] '
        '"POST /api/logs HTTP/1.1" 201 156 '
        '"https://app.example.com" "LogShipper/1.0" 0.042 0.041'
    )

@pytest.fixture
def sample_nginx_json_log() -> str:
    """Sample Nginx JSON format log"""
    return """{
        "time_local": "25/Dec/2023:10:00:00 +0000",
        "remote_addr": "203.0.113.1",
        "request": "GET /api/health HTTP/1.1",
        "status": "200",
        "body_bytes_sent": "89",
        "http_referer": "-",
        "http_user_agent": "HealthChecker/2.0",
        "request_time": "0.003",
        "upstream_response_time": "0.002"
    }"""

@pytest.fixture
def sample_syslog_rfc3164() -> str:
    """Sample RFC 3164 syslog message"""
    return "<34>Dec 25 10:00:00 web-server nginx: 192.168.1.100 - GET /api/users HTTP/1.1"

@pytest.fixture
def sample_syslog_rfc5424() -> str:
    """Sample RFC 5424 syslog message"""
    return (
        "<165>1 2023-12-25T10:00:00.123Z web-server.example.com nginx 1234 ID47 "
        "[exampleSDID@32473 iut=\"3\" eventSource=\"Application\" eventID=\"1011\"] "
        "Request processed successfully"
    )

@pytest.fixture
def sample_cef_log() -> str:
    """Sample CEF (Common Event Format) log"""
    return (
        "CEF:0|Security|IDS|1.0|100|Attempted Login|5|"
        "src=192.168.1.100 spt=1234 dst=10.0.0.1 dpt=22 suser=admin "
        "start=Dec 25 2023 10:00:00 msg=SSH login attempt detected"
    )

@pytest.fixture
def sample_structured_json() -> Dict[str, Any]:
    """Sample structured application log"""
    return {
        "timestamp": "2023-12-25T10:00:00.123Z",
        "level": "info",
        "logger": "com.example.UserService",
        "message": "User authentication successful",
        "thread": "http-nio-8080-exec-1",
        "user_id": "user123",
        "session_id": "sess_abc123",
        "request_id": "req_xyz789",
        "http_method": "POST",
        "http_url": "/api/auth/login",
        "http_status_code": 200,
        "response_time_ms": 45,
        "mdc": {
            "traceId": "trace123",
            "spanId": "span456"
        }
    }

@pytest.fixture
def sample_otlp_data() -> Dict[str, Any]:
    """Sample OTLP logs data structure"""
    return {
        "resource_logs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": "user-service"},
                        {"key": "service.version", "value": "1.2.3"},
                        {"key": "host.name", "value": "web-server-01"}
                    ]
                },
                "scope_logs": [
                    {
                        "scope": {"name": "user-service-logger"},
                        "log_records": [
                            {
                                "time_unix_nano": 1703505600123456789,
                                "severity_number": 9,
                                "severity_text": "INFO",
                                "body": "User login successful",
                                "attributes": [
                                    {"key": "user.id", "value": "user123"},
                                    {"key": "http.method", "value": "POST"},
                                    {"key": "http.status_code", "value": 200}
                                ],
                                "trace_id": "0123456789abcdef0123456789abcdef",
                                "span_id": "0123456789abcdef"
                            }
                        ]
                    }
                ]
            }
        ]
    }

@pytest.fixture
def sample_text_logs() -> List[str]:
    """Sample plain text logs"""
    return [
        "2023-12-25 10:00:00.123 INFO  [main] UserService - User login successful for user123",
        "2023-12-25 10:00:01.456 ERROR [http-thread-1] DatabaseService - Connection timeout after 30s",
        "2023-12-25 10:00:02.789 WARN  [scheduler] TaskProcessor - Queue size approaching limit: 950/1000",
        "INFO 2023-12-25T10:00:03.012Z Processing user registration request",
        "ERROR: Failed to connect to database: connection refused"
    ]

# Performance test fixtures
@pytest.fixture
def performance_log_batch(size: int = 100) -> List[Dict[str, Any]]:
    """Generate batch of logs for performance testing"""
    logs = []
    for i in range(size):
        logs.append({
            "ts": fake.date_time(tzinfo=timezone.utc).isoformat(),
            "host": fake.hostname(),
            "service": fake.random_element(elements=("web", "api", "db", "cache")),
            "level": fake.random_element(elements=("info", "warn", "error", "debug")),
            "msg": fake.sentence(),
            "trace_id": fake.uuid4(),
            "attrs": {
                "method": fake.random_element(elements=("GET", "POST", "PUT", "DELETE")),
                "status": fake.random_element(elements=(200, 201, 400, 404, 500)),
                "duration_ms": fake.random_int(min=1, max=5000),
                "user_id": fake.uuid4()
            },
            "src_ip": fake.ipv4(),
            "user_id": fake.uuid4()
        })
    return logs

# Error scenario fixtures
@pytest.fixture
def malformed_logs() -> Dict[str, str]:
    """Various malformed log examples"""
    return {
        "invalid_json": '{"incomplete": json',
        "invalid_timestamp": "not-a-timestamp",
        "empty_message": "",
        "oversized_message": "x" * 100000,  # 100KB message
        "invalid_cef": "CEF:INVALID|FORMAT",
        "invalid_syslog": "<999999>Invalid priority",
        "malformed_nginx": "Not a valid nginx log format"
    }

# Mock external service responses
@pytest.fixture
def mock_successful_response():
    """Mock successful HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    return mock_response

@pytest.fixture
def mock_error_response():
    """Mock error HTTP response"""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"error": "Internal server error"}
    return mock_response

# Database mock fixtures
@pytest.fixture
def mock_successful_insert():
    """Mock successful database insert"""
    def mock_insert(*args, **kwargs):
        return True
    return mock_insert

@pytest.fixture
def mock_failed_insert():
    """Mock failed database insert"""
    def mock_insert(*args, **kwargs):
        raise Exception("Database connection failed")
    return mock_insert

# Configuration fixtures
@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        "storage": {
            "clickhouse_url": "http://test-clickhouse:8123",
            "clickhouse_user": "test_user",
            "clickhouse_password": "test_password", 
            "clickhouse_database": "test_db"
        },
        "ingestion": {
            "max_batch_size": 1000,
            "default_service": "unknown",
            "rate_limit_rps": 10000
        }
    }

# Benchmarking fixtures
@pytest.fixture
def benchmark_data():
    """Data for benchmark tests"""
    return {
        "small_batch": 10,
        "medium_batch": 100, 
        "large_batch": 1000,
        "stress_batch": 10000
    }