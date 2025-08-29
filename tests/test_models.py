"""
Test cases for data models
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import ValidationError

from models import (
    LogEntry, BatchLogEntry, OTLPLogsData, QueryResponse,
    BulkRequest, IngestResponse
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

    def test_log_entry_validation_invalid_timestamp(self):
        """Test LogEntry validation with invalid timestamp"""
        with pytest.raises(ValidationError):
            LogEntry(
                ts="invalid-timestamp",  # Should be datetime
                msg="Test message"
            )

    def test_log_entry_validation_empty_message(self):
        """Test LogEntry allows empty message"""
        log = LogEntry(
            ts=datetime.now(timezone.utc),
            msg=""  # Empty message should be allowed
        )
        assert log.msg == ""

    def test_log_entry_attrs_validation(self):
        """Test LogEntry attrs field validation"""
        # Test with various attribute types
        log = LogEntry(
            ts=datetime.now(timezone.utc),
            msg="Test message",
            attrs={
                "string_attr": "value",
                "int_attr": 123,
                "float_attr": 12.34,
                "bool_attr": True,
                "none_attr": None,
                "nested_dict": {"key": "value"},
                "list_attr": [1, 2, 3]
            }
        )

        assert log.attrs["string_attr"] == "value"
        assert log.attrs["int_attr"] == 123
        assert log.attrs["float_attr"] == 12.34
        assert log.attrs["bool_attr"] is True
        assert log.attrs["none_attr"] is None

    def test_log_entry_ip_validation(self):
        """Test LogEntry IP address validation"""
        # Valid IPv4
        log1 = LogEntry(
            ts=datetime.now(timezone.utc),
            msg="Test",
            src_ip="192.168.1.1"
        )
        assert log1.src_ip == "192.168.1.1"

        # Valid IPv6
        log2 = LogEntry(
            ts=datetime.now(timezone.utc),
            msg="Test",
            src_ip="2001:db8::1"
        )
        assert log2.src_ip == "2001:db8::1"

        # Invalid IP should fail validation
        with pytest.raises(ValidationError):
            LogEntry(
                ts=datetime.now(timezone.utc),
                msg="Test",
                src_ip="invalid.ip.address"
            )

    def test_log_entry_serialization(self, sample_log_entry):
        """Test LogEntry serialization to dict"""
        data = sample_log_entry.model_dump()

        assert isinstance(data, dict)
        assert data["msg"] == "Test log message"
        assert data["level"] == "info"
        assert data["host"] == "test-host"
        assert isinstance(data["ts"], str)  # Should be ISO format string
        assert isinstance(data["attrs"], dict)

    def test_log_entry_json_serialization(self, sample_log_entry):
        """Test LogEntry JSON serialization"""
        json_str = sample_log_entry.model_dump_json()

        assert isinstance(json_str, str)
        assert "Test log message" in json_str
        assert "test-host" in json_str

        # Should be able to parse back
        import json
        data = json.loads(json_str)
        assert data["msg"] == "Test log message"


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

    def test_batch_log_entry_validation(self):
        """Test BatchLogEntry validation with invalid logs"""
        with pytest.raises(ValidationError):
            BatchLogEntry(logs=[
                LogEntry(ts=datetime.now(timezone.utc), msg="Valid log"),
                "Invalid log entry"  # Should be LogEntry instance
            ])

    def test_batch_log_entry_serialization(self, sample_batch_logs):
        """Test BatchLogEntry serialization"""
        data = sample_batch_logs.model_dump()

        assert isinstance(data, dict)
        assert "logs" in data
        assert len(data["logs"]) == 5
        assert all(isinstance(log, dict) for log in data["logs"])


class TestOTLPLogsData:
    """Test OTLP logs data model"""

    def test_otlp_logs_data_creation(self, sample_otlp_data):
        """Test creating OTLPLogsData from sample data"""
        otlp_data = OTLPLogsData(**sample_otlp_data)

        assert len(otlp_data.resource_logs) == 1
        resource_log = otlp_data.resource_logs[0]

        # Check resource attributes
        assert len(resource_log.resource.attributes) == 3
        service_name_attr = next(
            attr for attr in resource_log.resource.attributes
            if attr.key == "service.name"
        )
        assert service_name_attr.value == "user-service"

        # Check log records
        assert len(resource_log.scope_logs) == 1
        scope_log = resource_log.scope_logs[0]
        assert len(scope_log.log_records) == 1

        log_record = scope_log.log_records[0]
        assert log_record.severity_text == "INFO"
        assert log_record.body == "User login successful"
        assert log_record.trace_id == "0123456789abcdef0123456789abcdef"

    def test_otlp_logs_data_empty(self):
        """Test creating empty OTLP logs data"""
        otlp_data = OTLPLogsData(resource_logs=[])
        assert len(otlp_data.resource_logs) == 0

    def test_otlp_attribute_validation(self):
        """Test OTLP attribute value validation"""
        from models import OTLPAttribute

        # Test string value
        attr1 = OTLPAttribute(key="test", value="string_value")
        assert attr1.value == "string_value"

        # Test integer value
        attr2 = OTLPAttribute(key="test", value=123)
        assert attr2.value == 123

        # Test boolean value
        attr3 = OTLPAttribute(key="test", value=True)
        assert attr3.value is True


class TestQueryRequest:
    """Test query request model"""

    def test_query_request_minimal(self):
        """Test creating minimal query request"""
        query = QueryRequest(
            query="level=error",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc)
        )

        assert query.query == "level=error"
        assert query.limit == 1000  # Default limit
        assert query.offset == 0  # Default offset
        assert query.sort_field == "ts"  # Default sort
        assert query.sort_order == "desc"  # Default order

    def test_query_request_full(self):
        """Test creating full query request"""
        start_time = datetime(2023, 12, 25, 10, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2023, 12, 25, 11, 0, 0, tzinfo=timezone.utc)

        query = QueryRequest(
            query="service=web AND level=error",
            start_time=start_time,
            end_time=end_time,
            limit=500,
            offset=100,
            sort_field="host",
            sort_order="asc",
            fields=["ts", "host", "msg", "level"]
        )

        assert query.query == "service=web AND level=error"
        assert query.start_time == start_time
        assert query.end_time == end_time
        assert query.limit == 500
        assert query.offset == 100
        assert query.sort_field == "host"
        assert query.sort_order == "asc"
        assert query.fields == ["ts", "host", "msg", "level"]

    def test_query_request_validation_invalid_sort_order(self):
        """Test query request validation with invalid sort order"""
        with pytest.raises(ValidationError):
            QueryRequest(
                query="test",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                sort_order="invalid"  # Should be 'asc' or 'desc'
            )

    def test_query_request_validation_negative_limit(self):
        """Test query request validation with negative limit"""
        with pytest.raises(ValidationError):
            QueryRequest(
                query="test",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                limit=-1  # Should be positive
            )

    def test_query_request_validation_time_range(self):
        """Test query request validation with invalid time range"""
        start_time = datetime.now(timezone.utc)
        end_time = start_time.replace(hour=start_time.hour - 1)  # End before start

        # Model validation should allow this, business logic should handle it
        query = QueryRequest(
            query="test",
            start_time=start_time,
            end_time=end_time
        )

        assert query.end_time < query.start_time


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
        assert response.has_more is False  # Default

    def test_query_response_empty(self):
        """Test creating empty query response"""
        response = QueryResponse(
            logs=[],
            total_count=0,
            execution_time_ms=25.0
        )

        assert len(response.logs) == 0
        assert response.total_count == 0
        assert response.has_more is False

    def test_query_response_with_pagination(self, sample_batch_logs):
        """Test query response with pagination info"""
        response = QueryResponse(
            logs=sample_batch_logs.logs,
            total_count=1000,  # More than returned
            execution_time_ms=200.0,
            has_more=True
        )

        assert len(response.logs) == 5
        assert response.total_count == 1000
        assert response.has_more is True


class TestStorageConfig:
    """Test storage configuration models"""

    def test_storage_config_s3(self):
        """Test S3 storage configuration"""
        config = StorageConfig(
            type="s3",
            endpoint="https://s3.amazonaws.com",
            bucket="test-bucket",
            access_key="test-key",
            secret_key="test-secret",
            region="us-west-2"
        )

        assert config.type == "s3"
        assert config.endpoint == "https://s3.amazonaws.com"
        assert config.bucket == "test-bucket"
        assert config.region == "us-west-2"

    def test_storage_config_gcs(self):
        """Test GCS storage configuration"""
        config = StorageConfig(
            type="gcs",
            bucket="test-bucket",
            project_id="test-project",
            service_account_path="/path/to/service-account.json"
        )

        assert config.type == "gcs"
        assert config.bucket == "test-bucket"
        assert config.project_id == "test-project"

    def test_storage_config_azure(self):
        """Test Azure storage configuration"""
        config = StorageConfig(
            type="azure",
            container="test-container",
            account_name="testaccount",
            account_key="test-key"
        )

        assert config.type == "azure"
        assert config.container == "test-container"
        assert config.account_name == "testaccount"

    def test_storage_config_validation_invalid_type(self):
        """Test storage config validation with invalid type"""
        with pytest.raises(ValidationError):
            StorageConfig(
                type="invalid",  # Should be s3, gcs, azure, or minio
                bucket="test-bucket"
            )


class TestCustomerConfig:
    """Test customer configuration model"""

    def test_customer_config_shared(self):
        """Test shared deployment customer config"""
        config = CustomerConfig(
            customer_id="cust-123",
            deployment_type="shared"
        )

        assert config.customer_id == "cust-123"
        assert config.deployment_type == "shared"
        assert config.custom_storage is None
        assert config.retention_days == 90  # Default

    def test_customer_config_dedicated(self):
        """Test dedicated deployment customer config"""
        storage_config = StorageConfig(
            type="s3",
            bucket="customer-dedicated-bucket",
            region="us-east-1"
        )

        config = CustomerConfig(
            customer_id="cust-456",
            deployment_type="dedicated",
            custom_storage=storage_config,
            retention_days=365
        )

        assert config.customer_id == "cust-456"
        assert config.deployment_type == "dedicated"
        assert config.custom_storage == storage_config
        assert config.retention_days == 365

    def test_customer_config_fedramp(self):
        """Test FedRAMP deployment customer config"""
        config = CustomerConfig(
            customer_id="gov-789",
            deployment_type="fedramp",
            retention_days=2555,  # 7 years for compliance
            encryption_at_rest=True,
            compliance_tags=["fedramp", "government"]
        )

        assert config.deployment_type == "fedramp"
        assert config.retention_days == 2555
        assert config.encryption_at_rest is True
        assert "fedramp" in config.compliance_tags
        assert "government" in config.compliance_tags


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

    def test_batch_serialization_performance(self, sample_batch_logs):
        """Test batch serialization performance"""
        import time

        # Create larger batch for performance testing
        large_batch_logs = []
        for i in range(1000):
            log = LogEntry(
                ts=datetime.now(timezone.utc),
                host=f"host-{i}",
                service="test-service",
                level="info",
                msg=f"Test message {i}",
                attrs={"index": i}
            )
            large_batch_logs.append(log)

        batch = BatchLogEntry(logs=large_batch_logs)

        start_time = time.time()
        serialized = batch.model_dump()
        elapsed = time.time() - start_time

        # Should serialize 1000-entry batch in under 100ms
        assert elapsed < 0.1, f"Batch serialization too slow: {elapsed}s for 1000 entries"
        assert len(serialized["logs"]) == 1000
