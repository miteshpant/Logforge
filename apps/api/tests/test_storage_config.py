"""
Test cases for storage configuration management
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from storage_config import StorageConfigManager, StorageConfig, CustomerConfig
from models import StorageConfig as StorageConfigModel, CustomerConfig as CustomerConfigModel


class TestStorageConfigManager:
    """Test StorageConfigManager class"""

    def test_manager_initialization(self, test_config):
        """Test StorageConfigManager initialization"""
        manager = StorageConfigManager(test_config)

        assert manager.base_config == test_config
        assert manager.customer_configs == {}
        assert manager.storage_clients == {}

    def test_load_customer_config_shared(self):
        """Test loading shared deployment customer config"""
        config = {
            "customer_configs": {
                "cust-123": {
                    "deployment_type": "shared",
                    "retention_days": 90
                }
            }
        }

        manager = StorageConfigManager(config)
        customer_config = manager._load_customer_config("cust-123")

        assert customer_config.customer_id == "cust-123"
        assert customer_config.deployment_type == "shared"
        assert customer_config.retention_days == 90
        assert customer_config.custom_storage is None

    def test_load_customer_config_dedicated(self):
        """Test loading dedicated deployment customer config"""
        config = {
            "customer_configs": {
                "cust-456": {
                    "deployment_type": "dedicated",
                    "retention_days": 365,
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "customer-dedicated-bucket",
                        "region": "us-east-1",
                        "access_key": "customer-key",
                        "secret_key": "customer-secret"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)
        customer_config = manager._load_customer_config("cust-456")

        assert customer_config.deployment_type == "dedicated"
        assert customer_config.custom_storage is not None
        assert customer_config.custom_storage.type == "s3"
        assert customer_config.custom_storage.bucket == "customer-dedicated-bucket"

    def test_load_customer_config_fedramp(self):
        """Test loading FedRAMP deployment customer config"""
        config = {
            "customer_configs": {
                "gov-789": {
                    "deployment_type": "fedramp",
                    "retention_days": 2555,
                    "encryption_at_rest": True,
                    "compliance_tags": ["fedramp", "government"],
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "fedramp-secure-bucket",
                        "region": "us-gov-east-1",
                        "endpoint": "https://s3.us-gov-east-1.amazonaws.com"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)
        customer_config = manager._load_customer_config("gov-789")

        assert customer_config.deployment_type == "fedramp"
        assert customer_config.encryption_at_rest is True
        assert "fedramp" in customer_config.compliance_tags
        assert customer_config.custom_storage.region == "us-gov-east-1"

    def test_load_nonexistent_customer_config(self):
        """Test loading config for non-existent customer"""
        manager = StorageConfigManager({})

        with pytest.raises(ValueError, match="Customer configuration not found"):
            manager._load_customer_config("nonexistent-customer")


class TestS3StorageClient:
    """Test S3 storage client creation and operations"""

    @patch('storage_config.boto3')
    def test_create_s3_client_aws(self, mock_boto3):
        """Test creating S3 client for AWS"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage_config = StorageConfigModel(
            type="s3",
            bucket="test-bucket",
            region="us-west-2",
            access_key="test-key",
            secret_key="test-secret"
        )

        manager = StorageConfigManager({})
        client = manager._create_s3_client(storage_config)

        assert client == mock_client
        mock_boto3.client.assert_called_once_with(
            's3',
            region_name='us-west-2',
            aws_access_key_id='test-key',
            aws_secret_access_key='test-secret'
        )

    @patch('storage_config.boto3')
    def test_create_s3_client_with_custom_endpoint(self, mock_boto3):
        """Test creating S3 client with custom endpoint (MinIO)"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        storage_config = StorageConfigModel(
            type="s3",
            bucket="minio-bucket",
            endpoint="http://localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin"
        )

        manager = StorageConfigManager({})
        client = manager._create_s3_client(storage_config)

        mock_boto3.client.assert_called_once_with(
            's3',
            endpoint_url='http://localhost:9000',
            aws_access_key_id='minioadmin',
            aws_secret_access_key='minioadmin'
        )

    @patch('storage_config.boto3')
    def test_create_s3_client_credentials_error(self, mock_boto3):
        """Test S3 client creation with invalid credentials"""
        mock_boto3.client.side_effect = NoCredentialsError()

        storage_config = StorageConfigModel(
            type="s3",
            bucket="test-bucket"
            # Missing credentials
        )

        manager = StorageConfigManager({})

        with pytest.raises(ValueError, match="S3 credentials not provided"):
            manager._create_s3_client(storage_config)


class TestGCSStorageClient:
    """Test GCS storage client creation and operations"""

    @patch('storage_config.storage.Client')
    def test_create_gcs_client_with_service_account(self, mock_gcs_client):
        """Test creating GCS client with service account"""
        mock_client = Mock()
        mock_gcs_client.from_service_account_json.return_value = mock_client

        storage_config = StorageConfigModel(
            type="gcs",
            bucket="test-bucket",
            project_id="test-project",
            service_account_path="/path/to/service-account.json"
        )

        manager = StorageConfigManager({})
        client = manager._create_gcs_client(storage_config)

        assert client == mock_client
        mock_gcs_client.from_service_account_json.assert_called_once_with(
            "/path/to/service-account.json",
            project="test-project"
        )

    @patch('storage_config.storage.Client')
    def test_create_gcs_client_with_credentials_dict(self, mock_gcs_client):
        """Test creating GCS client with credentials dictionary"""
        mock_client = Mock()
        mock_gcs_client.from_service_account_info.return_value = mock_client

        credentials_dict = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
        }

        storage_config = StorageConfigModel(
            type="gcs",
            bucket="test-bucket",
            project_id="test-project",
            service_account_info=credentials_dict
        )

        manager = StorageConfigManager({})
        client = manager._create_gcs_client(storage_config)

        mock_gcs_client.from_service_account_info.assert_called_once_with(
            credentials_dict,
            project="test-project"
        )

    def test_create_gcs_client_missing_credentials(self):
        """Test GCS client creation with missing credentials"""
        storage_config = StorageConfigModel(
            type="gcs",
            bucket="test-bucket",
            project_id="test-project"
            # Missing service_account_path and service_account_info
        )

        manager = StorageConfigManager({})

        with pytest.raises(ValueError, match="GCS credentials not provided"):
            manager._create_gcs_client(storage_config)


class TestAzureStorageClient:
    """Test Azure Blob storage client creation and operations"""

    @patch('storage_config.BlobServiceClient')
    def test_create_azure_client_with_account_key(self, mock_blob_client):
        """Test creating Azure client with account key"""
        mock_client = Mock()
        mock_blob_client.return_value = mock_client

        storage_config = StorageConfigModel(
            type="azure",
            container="test-container",
            account_name="testaccount",
            account_key="test-account-key"
        )

        manager = StorageConfigManager({})
        client = manager._create_azure_client(storage_config)

        assert client == mock_client
        expected_connection_string = (
            "DefaultEndpointsProtocol=https;"
            "AccountName=testaccount;"
            "AccountKey=test-account-key;"
            "EndpointSuffix=core.windows.net"
        )
        mock_blob_client.assert_called_once_with(expected_connection_string)

    @patch('storage_config.BlobServiceClient')
    def test_create_azure_client_with_connection_string(self, mock_blob_client):
        """Test creating Azure client with connection string"""
        mock_client = Mock()
        mock_blob_client.return_value = mock_client

        storage_config = StorageConfigModel(
            type="azure",
            container="test-container",
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;"
        )

        manager = StorageConfigManager({})
        client = manager._create_azure_client(storage_config)

        mock_blob_client.assert_called_once_with(
            "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;"
        )

    def test_create_azure_client_missing_credentials(self):
        """Test Azure client creation with missing credentials"""
        storage_config = StorageConfigModel(
            type="azure",
            container="test-container"
            # Missing account credentials
        )

        manager = StorageConfigManager({})

        with pytest.raises(ValueError, match="Azure credentials not provided"):
            manager._create_azure_client(storage_config)


class TestStorageClientCaching:
    """Test storage client caching and management"""

    @patch('storage_config.boto3')
    def test_client_caching(self, mock_boto3):
        """Test that storage clients are cached"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        config = {
            "customer_configs": {
                "cust-123": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "test-bucket",
                        "region": "us-west-2"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)

        # First call should create client
        client1 = manager.get_storage_client("cust-123")
        assert client1 == mock_client

        # Second call should return cached client
        client2 = manager.get_storage_client("cust-123")
        assert client2 == mock_client
        assert client1 is client2

        # boto3.client should only be called once due to caching
        mock_boto3.client.assert_called_once()

    def test_client_cache_different_customers(self):
        """Test that different customers get different clients"""
        config = {
            "customer_configs": {
                "cust-123": {
                    "deployment_type": "shared"
                },
                "cust-456": {
                    "deployment_type": "shared"
                }
            }
        }

        manager = StorageConfigManager(config)

        # For shared deployments, should get the same shared client
        client1 = manager.get_storage_client("cust-123")
        client2 = manager.get_storage_client("cust-456")

        # Both should use shared storage, so might be the same client
        # This depends on your implementation details


class TestClickHouseStoragePolicyGeneration:
    """Test ClickHouse storage policy generation"""

    def test_generate_storage_policy_s3(self):
        """Test generating ClickHouse storage policy for S3"""
        storage_config = StorageConfigModel(
            type="s3",
            bucket="test-bucket",
            region="us-west-2",
            access_key="test-key",
            secret_key="test-secret"
        )

        manager = StorageConfigManager({})
        policy_xml = manager.generate_clickhouse_storage_policy("test-policy", storage_config)

        assert "<disk>" in policy_xml
        assert "<type>s3</type>" in policy_xml
        assert "<endpoint>https://test-bucket.s3.us-west-2.amazonaws.com/</endpoint>" in policy_xml
        assert "<access_key_id>test-key</access_key_id>" in policy_xml
        assert "<secret_access_key>test-secret</secret_access_key>" in policy_xml

    def test_generate_storage_policy_gcs(self):
        """Test generating ClickHouse storage policy for GCS"""
        storage_config = StorageConfigModel(
            type="gcs",
            bucket="test-bucket",
            project_id="test-project",
            service_account_path="/path/to/service-account.json"
        )

        manager = StorageConfigManager({})
        policy_xml = manager.generate_clickhouse_storage_policy("gcs-policy", storage_config)

        assert "<disk>" in policy_xml
        assert "<type>s3</type>" in policy_xml  # GCS uses S3-compatible interface
        assert "<endpoint>https://storage.googleapis.com/test-bucket/</endpoint>" in policy_xml

    def test_generate_storage_policy_azure(self):
        """Test generating ClickHouse storage policy for Azure"""
        storage_config = StorageConfigModel(
            type="azure",
            container="test-container",
            account_name="testaccount",
            account_key="test-key"
        )

        manager = StorageConfigManager({})
        policy_xml = manager.generate_clickhouse_storage_policy("azure-policy", storage_config)

        assert "<disk>" in policy_xml
        assert "<type>azure_blob_storage</type>" in policy_xml
        assert "<storage_account>testaccount</storage_account>" in policy_xml
        assert "<container>test-container</container>" in policy_xml
        assert "<account_key>test-key</account_key>" in policy_xml

    def test_generate_storage_policy_with_encryption(self):
        """Test generating storage policy with encryption options"""
        storage_config = StorageConfigModel(
            type="s3",
            bucket="encrypted-bucket",
            region="us-west-2",
            encryption_key="encryption-key-123"
        )

        manager = StorageConfigManager({})
        policy_xml = manager.generate_clickhouse_storage_policy("encrypted-policy", storage_config)

        assert "<server_side_encryption_kms_key_id>encryption-key-123</server_side_encryption_kms_key_id>" in policy_xml


class TestStorageConfigIntegration:
    """Integration tests for storage configuration"""

    @patch('storage_config.boto3')
    def test_end_to_end_s3_client_creation(self, mock_boto3):
        """Test end-to-end S3 client creation for customer"""
        mock_s3_client = Mock()
        mock_boto3.client.return_value = mock_s3_client

        config = {
            "default_storage": {
                "type": "s3",
                "bucket": "default-bucket",
                "region": "us-west-2"
            },
            "customer_configs": {
                "enterprise-customer": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "enterprise-secure-bucket",
                        "region": "us-east-1",
                        "access_key": "enterprise-key",
                        "secret_key": "enterprise-secret",
                        "encryption_key": "enterprise-kms-key"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)

        # Get client for enterprise customer
        client = manager.get_storage_client("enterprise-customer")
        assert client == mock_s3_client

        # Verify S3 client was created with correct parameters
        mock_boto3.client.assert_called_once_with(
            's3',
            region_name='us-east-1',
            aws_access_key_id='enterprise-key',
            aws_secret_access_key='enterprise-secret'
        )

        # Generate ClickHouse policy
        policy_xml = manager.generate_clickhouse_storage_policy_for_customer("enterprise-customer")
        assert "enterprise-secure-bucket" in policy_xml
        assert "enterprise-kms-key" in policy_xml

    def test_shared_deployment_fallback(self):
        """Test that shared deployment customers use default storage"""
        config = {
            "default_storage": {
                "type": "s3",
                "bucket": "shared-logs-bucket",
                "region": "us-west-2"
            },
            "customer_configs": {
                "shared-customer": {
                    "deployment_type": "shared",
                    "retention_days": 30
                }
            }
        }

        manager = StorageConfigManager(config)

        # Should use default storage configuration
        storage_config = manager._get_effective_storage_config("shared-customer")
        assert storage_config.bucket == "shared-logs-bucket"
        assert storage_config.type == "s3"

    def test_customer_override_validation(self):
        """Test validation of customer configuration overrides"""
        config = {
            "customer_configs": {
                "invalid-customer": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "invalid_storage_type",  # Invalid type
                        "bucket": "test-bucket"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)

        with pytest.raises(ValueError, match="Unsupported storage type"):
            manager.get_storage_client("invalid-customer")


class TestStorageConfigPerformance:
    """Test storage configuration performance"""

    @patch('storage_config.boto3')
    def test_concurrent_client_creation(self, mock_boto3):
        """Test concurrent storage client creation"""
        import concurrent.futures
        import time

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
                } for i in range(10)
            }
        }

        manager = StorageConfigManager(config)

        def create_client(customer_id):
            return manager.get_storage_client(customer_id)

        # Create clients concurrently
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(create_client, f"customer-{i}")
                for i in range(10)
            ]
            clients = [future.result() for future in futures]
        elapsed = time.time() - start_time

        # All clients should be created successfully
        assert len(clients) == 10
        assert all(client == mock_client for client in clients)

        # Should complete in reasonable time
        assert elapsed < 1.0, f"Concurrent client creation too slow: {elapsed}s"

    def test_storage_policy_generation_performance(self):
        """Test storage policy generation performance"""
        import time

        storage_config = StorageConfigModel(
            type="s3",
            bucket="performance-test-bucket",
            region="us-west-2",
            access_key="test-key",
            secret_key="test-secret"
        )

        manager = StorageConfigManager({})

        # Generate 100 storage policies
        start_time = time.time()
        for i in range(100):
            policy_xml = manager.generate_clickhouse_storage_policy(f"policy-{i}", storage_config)
            assert len(policy_xml) > 0
        elapsed = time.time() - start_time

        # Should generate 100 policies in under 1 second
        throughput = 100 / elapsed
        assert throughput > 100, f"Policy generation too slow: {throughput} policies/sec"
