"""
Test cases for storage configuration - Fixed version
"""

import pytest
from unittest.mock import Mock, patch

from storage_config import StorageConfigManager


class TestStorageConfigManager:
    """Test storage configuration manager"""

    def test_storage_manager_creation(self):
        """Test creating storage config manager"""
        config = {
            "customer_configs": {
                "test-customer": {
                    "deployment_type": "shared",
                    "retention_days": 30
                }
            }
        }

        manager = StorageConfigManager(config)
        assert manager is not None

    @patch('storage_config.boto3')
    def test_get_storage_client_s3(self, mock_boto3):
        """Test getting S3 storage client"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        config = {
            "customer_configs": {
                "test-customer": {
                    "deployment_type": "dedicated",
                    "custom_storage": {
                        "type": "s3",
                        "bucket": "test-bucket",
                        "region": "us-east-1",
                        "access_key": "test-key",
                        "secret_key": "test-secret"
                    }
                }
            }
        }

        manager = StorageConfigManager(config)
        client = manager.get_storage_client("test-customer")

        assert client == mock_client
        mock_boto3.client.assert_called_once()

    def test_get_customer_config(self):
        """Test getting customer configuration"""
        config = {
            "customer_configs": {
                "test-customer": {
                    "deployment_type": "shared",
                    "retention_days": 90
                }
            }
        }

        manager = StorageConfigManager(config)
        customer_config = manager.get_customer_config("test-customer")

        assert customer_config is not None
        assert customer_config["deployment_type"] == "shared"
        assert customer_config["retention_days"] == 90

    def test_get_customer_config_not_found(self):
        """Test getting non-existent customer configuration"""
        config = {"customer_configs": {}}
        manager = StorageConfigManager(config)

        customer_config = manager.get_customer_config("nonexistent-customer")
        assert customer_config is None

    def test_generate_clickhouse_storage_policy(self):
        """Test generating ClickHouse storage policy"""
        storage_config = {
            "type": "s3",
            "bucket": "test-bucket",
            "region": "us-west-2",
            "access_key": "test-key",
            "secret_key": "test-secret"
        }

        manager = StorageConfigManager({})
        policy_xml = manager.generate_clickhouse_storage_policy("test-policy", storage_config)

        assert isinstance(policy_xml, str)
        assert "<type>s3</type>" in policy_xml
        assert "<access_key_id>test-key</access_key_id>" in policy_xml
        assert "test-bucket" in policy_xml
