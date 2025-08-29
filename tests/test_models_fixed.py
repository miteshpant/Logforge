"""
Test cases for data models - Fixed version matching actual implementation
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import ValidationError

from models import (
    LogEntry, BatchLogEntry, OTLPLogsData,
    QueryResponse, IngestResponse, BulkRequest
)


class TestLogEntry:
    """Test LogEntry model validation and serialization"""

    def test_log_entry_creation_minimal(self):
        """Test creating LogEntry with minimal required fields"""
        log = LogEntry(
            ts=datetime.now(timezone.utc),
            msg="Test message"
        )

        assert log.msg == "Test message"
        assert log.level == "info"  # Default level
        assert log.host is None
        assert log.service is None
        assert log.attrs == {}

    def test_log_entry_creation_full(self, sample_log_entry):
        """Test creating LogEntry with all fields"""
        assert sample_log_entry.msg == "Test log message"
        assert sample_log_entry.level == "info"
        assert sample_log_entry.host == "test-host"
        assert sample_log_entry.service == "test-service"
        assert sample_log_entry.trace_id == "test-trace-123"
        assert sample_log_entry.span_id == "test-span-456"
        assert sample_log_entry.status == 200
        assert sample_log_entry.src_ip == "192.168.1.100"
        assert sample_log_entry.user_id == "user123"
        assert sample_log_entry.attrs["method"] == "GET"
        assert sample_log_entry.attrs["uri"] == "/api/test"

    def test_log_entry_validation_invalid_level(self):
        """Test LogEntry validation with invalid level"""
        with pytest.raises(ValidationError):
            LogEntry(
                ts=datetime.now(timezone.utc),
                msg="Test message",
                level="invalid_level"  # Not in allowed levels
            )

    def test_log_entry_serialization(self, sample_log_entry):
        """Test LogEntry serialization to dict"""
        data = sample_log_entry.model_dump()

        assert isinstance(data, dict)
        assert data["msg"] == "Test log message"
        assert data["level"] == "info"
        assert data["host"] == "test-host"
        assert isinstance(data["attrs"], dict)


class TestBatchLogEntry:
    """Test BatchLogEntry model"""

    def test_batch_log_entry_creation(self, sample_batch_logs):
        """Test creating BatchLogEntry"""
        assert len(sample_batch_logs.logs) == 5
        assert all(isinstance(log, LogEntry) for log in sample_batch_logs.logs)
        assert sample_batch_logs.logs[0].host == "test-host-0"
        assert sample_batch_logs.logs[4].host == "test-host-4"

    def test_batch_log_entry_empty(self):
        """Test creating empty BatchLogEntry"""
        batch = BatchLogEntry(logs=[])
        assert len(batch.logs) == 0


class TestQueryResponse:
    """Test query response model"""

    def test_query_response_creation(self, sample_log_entry):
        """Test creating query response"""
        response = QueryResponse(
            logs=[sample_log_entry],
            total_count=1,
            execution_time_ms=150.5
        )

        assert len(response.logs) == 1
        assert response.logs[0] == sample_log_entry
        assert response.total_count == 1
        assert response.execution_time_ms == 150.5


class TestIngestResponse:
    """Test ingest response model"""

    def test_ingest_response_creation(self):
        """Test creating ingest response"""
        response = IngestResponse(
            status="accepted",
            count=1,
            message="Log ingested successfully"
        )

        assert response.status == "accepted"
        assert response.count == 1
        assert response.message == "Log ingested successfully"


class TestModelSerializationPerformance:
    """Test model serialization performance"""

    def test_log_entry_serialization_performance(self, performance_log_batch):
        """Test LogEntry serialization performance"""
        import time

        # Create LogEntry objects from performance batch
        log_entries = []
        for log_data in performance_log_batch[:100]:  # Test with 100 entries
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

        # Test serialization performance
        start_time = time.time()

        serialized_data = []
        for log_entry in log_entries:
            data = log_entry.model_dump()
            serialized_data.append(data)

        elapsed = time.time() - start_time
        throughput = len(log_entries) / elapsed

        # Should serialize at least 1000 LogEntry objects per second
        assert throughput > 1000, f"Serialization too slow: {throughput} objects/sec"
        assert len(serialized_data) == 100
