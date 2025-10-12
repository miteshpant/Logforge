"""
Multi-Cloud Storage Configuration Manager
Handles different storage backends and deployment models
"""

import os
import yaml
import boto3
import logging
from typing import Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

class DeploymentType(Enum):
    SHARED = "shared"
    DEDICATED = "dedicated" 
    FEDRAMP = "fedramp"
    PRIVATE = "private"

class StorageBackend(Enum):
    S3 = "s3"
    GCS = "gcs" 
    AZURE = "azure"
    MINIO = "minio"

class ComplianceTier(Enum):
    STANDARD = "standard"
    FEDRAMP = "fedramp"
    HIPAA = "hipaa"
    PCI = "pci"
    SOC2 = "soc2"

@dataclass
class StorageCredentials:
    """Storage backend credentials"""
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    service_account_key: Optional[str] = None
    connection_string: Optional[str] = None
    project_id: Optional[str] = None
    account_name: Optional[str] = None

@dataclass 
class StorageEndpoint:
    """Storage endpoint configuration"""
    backend: StorageBackend
    region: str
    bucket: str
    endpoint_url: Optional[str] = None
    credentials: Optional[StorageCredentials] = None
    encryption_enabled: bool = True
    kms_key_id: Optional[str] = None

class StorageConfigManager:
    """Manages storage configuration for different deployment models"""
    
    def __init__(self, config_path: str = "config/storage-config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._storage_clients = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load storage configuration"""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                # Try relative to API directory
                config_file = Path(__file__).parent.parent.parent / self.config_path
                
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {self.config_path} not found, using defaults")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default configuration for development"""
        return {
            'storage': {
                'deployment': {
                    'type': 'shared',
                    'region': 'us-east-1',
                    'compliance_tier': 'standard'
                },
                'cold': {
                    'enabled': True,
                    'backend': 'minio',  # Default to MinIO for local development
                    'backends': {
                        'minio': {
                            'enabled': True,
                            'bucket': 'logforge',
                            'endpoint': os.getenv('MINIO_ENDPOINT', 'http://minio:9000'),
                            'access_key': os.getenv('MINIO_ACCESS_KEY', 'minio'),
                            'secret_key': os.getenv('MINIO_SECRET_KEY', 'minio123'),
                            'secure': os.getenv('MINIO_SECURE', 'false').lower() == 'true'
                        },
                        's3': {
                            'shared': {
                                'enabled': True,
                                'bucket_prefix': 'logforge-dev',
                                'region': 'us-east-1'
                            },
                            'dedicated': {
                                'enabled': True,
                                'bucket_prefix': 'logforge-dedicated', 
                                'region': 'us-east-1'
                            }
                        }
                    }
                }
            },
            'customers': {
                # Example: Tenant-specific S3 configuration
                # 'enterprise-customer-id': {
                #     'storage': {
                #         'cold': {
                #             'backend': 's3',
                #             'deployment': {
                #                 'type': 'dedicated'
                #             }
                #         }
                #     }
                # }
            }
        }
    
    def get_storage_endpoint(self, customer_id: Optional[str] = None, 
                           storage_type: str = "cold") -> StorageEndpoint:
        """Get storage endpoint configuration for customer"""
        
        # Get customer-specific config if available
        customer_config = None
        if customer_id and customer_id in self.config.get('customers', {}):
            customer_config = self.config['customers'][customer_id]
            
        # Merge with base config
        storage_config = self.config['storage']
        if customer_config:
            storage_config = self._merge_configs(storage_config, customer_config)
            
        # Get deployment info
        deployment = storage_config.get('deployment', {})
        deployment_type = DeploymentType(deployment.get('type', 'shared'))
        region = deployment.get('region', 'us-east-1')
        
        # Get cold storage config
        cold_config = storage_config.get('cold', {})
        backend_name = cold_config.get('backend', 'minio')  # Default to MinIO
        backend = StorageBackend(backend_name)
        
        # Build endpoint based on backend and deployment type
        return self._build_storage_endpoint(
            backend=backend,
            deployment_type=deployment_type,
            region=region,
            cold_config=cold_config,
            customer_id=customer_id
        )
    
    def _build_storage_endpoint(self, backend: StorageBackend, 
                              deployment_type: DeploymentType,
                              region: str, cold_config: Dict[str, Any],
                              customer_id: Optional[str]) -> StorageEndpoint:
        """Build storage endpoint based on configuration"""
        
        if backend == StorageBackend.S3:
            return self._build_s3_endpoint(deployment_type, region, cold_config, customer_id)
        elif backend == StorageBackend.GCS:
            return self._build_gcs_endpoint(deployment_type, region, cold_config, customer_id)  
        elif backend == StorageBackend.AZURE:
            return self._build_azure_endpoint(deployment_type, region, cold_config, customer_id)
        elif backend == StorageBackend.MINIO:
            return self._build_minio_endpoint(deployment_type, region, cold_config, customer_id)
        else:
            raise ValueError(f"Unsupported backend: {backend}")
    
    def _build_s3_endpoint(self, deployment_type: DeploymentType, region: str,
                          cold_config: Dict[str, Any], customer_id: Optional[str]) -> StorageEndpoint:
        """Build S3 storage endpoint"""
        s3_config = cold_config.get('backends', {}).get('s3', {})
        
        # Select appropriate config based on deployment type
        if deployment_type == DeploymentType.FEDRAMP:
            backend_config = s3_config.get('fedramp', {})
            endpoint_url = f"https://s3.{region}.amazonaws.com" if region.startswith('us-gov') else None
        elif deployment_type == DeploymentType.DEDICATED:
            backend_config = s3_config.get('dedicated', {})
            endpoint_url = backend_config.get('endpoint')
        else:  # SHARED
            backend_config = s3_config.get('shared', {})
            endpoint_url = None
            
        if not backend_config.get('enabled', True):
            raise ValueError(f"S3 backend not enabled for deployment type: {deployment_type}")
            
        # Build bucket name
        if deployment_type == DeploymentType.SHARED:
            bucket_prefix = backend_config.get('bucket_prefix', 'logforge-shared')
            bucket = f"{bucket_prefix}-{customer_id}" if customer_id else bucket_prefix
        else:
            bucket = backend_config.get('bucket', f'{customer_id}-logforge-cold' if customer_id else 'logforge-cold')
            
        # Build credentials
        credentials = StorageCredentials(
            access_key=backend_config.get('access_key', os.getenv('AWS_ACCESS_KEY_ID')),
            secret_key=backend_config.get('secret_key', os.getenv('AWS_SECRET_ACCESS_KEY')),
            role_arn=backend_config.get('role_arn'),
            external_id=backend_config.get('external_id')
        )
        
        return StorageEndpoint(
            backend=StorageBackend.S3,
            region=region,
            bucket=bucket,
            endpoint_url=endpoint_url,
            credentials=credentials,
            kms_key_id=backend_config.get('kms_key_id')
        )
    
    def _build_gcs_endpoint(self, deployment_type: DeploymentType, region: str,
                           cold_config: Dict[str, Any], customer_id: Optional[str]) -> StorageEndpoint:
        """Build GCS storage endpoint"""
        gcs_config = cold_config.get('backends', {}).get('gcs', {})
        
        if deployment_type == DeploymentType.DEDICATED:
            backend_config = gcs_config.get('dedicated', {})
        else:
            backend_config = gcs_config.get('shared', {})
            
        if not backend_config.get('enabled', False):
            raise ValueError(f"GCS backend not enabled for deployment type: {deployment_type}")
            
        # Build bucket name  
        if deployment_type == DeploymentType.SHARED:
            bucket_prefix = backend_config.get('bucket_prefix', 'logforge-shared-gcs')
            bucket = f"{bucket_prefix}-{customer_id}" if customer_id else bucket_prefix
        else:
            bucket = backend_config.get('bucket', f'{customer_id}-logforge-cold' if customer_id else 'logforge-cold')
            
        credentials = StorageCredentials(
            service_account_key=backend_config.get('service_account_key'),
            project_id=backend_config.get('project_id')
        )
        
        return StorageEndpoint(
            backend=StorageBackend.GCS,
            region=region,
            bucket=bucket,
            credentials=credentials
        )
    
    def _build_azure_endpoint(self, deployment_type: DeploymentType, region: str,
                             cold_config: Dict[str, Any], customer_id: Optional[str]) -> StorageEndpoint:
        """Build Azure Blob storage endpoint"""
        azure_config = cold_config.get('backends', {}).get('azure', {})
        
        if deployment_type == DeploymentType.DEDICATED:
            backend_config = azure_config.get('dedicated', {})
        else:
            backend_config = azure_config.get('shared', {})
            
        if not backend_config.get('enabled', False):
            raise ValueError(f"Azure backend not enabled for deployment type: {deployment_type}")
            
        # Build container name
        if deployment_type == DeploymentType.SHARED:
            container_prefix = backend_config.get('container_prefix', 'logforge-shared')
            container = f"{container_prefix}-{customer_id}" if customer_id else container_prefix
        else:
            container = backend_config.get('container', f'{customer_id}-logforge-cold' if customer_id else 'logforge-cold')
            
        credentials = StorageCredentials(
            account_name=backend_config.get('account_name'),
            secret_key=backend_config.get('account_key'),
            connection_string=backend_config.get('connection_string')
        )
        
        return StorageEndpoint(
            backend=StorageBackend.AZURE,
            region=region,
            bucket=container,  # Using bucket field for container name
            credentials=credentials
        )
    
    def _build_minio_endpoint(self, deployment_type: DeploymentType, region: str,
                             cold_config: Dict[str, Any], customer_id: Optional[str]) -> StorageEndpoint:
        """Build MinIO storage endpoint"""
        minio_config = cold_config.get('backends', {}).get('minio', {})
        
        if not minio_config.get('enabled', False):
            raise ValueError("MinIO backend not enabled")
            
        # Use shared bucket with tenant path isolation for cost efficiency
        bucket = minio_config.get('bucket', 'logforge')
        
        # Get endpoint URL and ensure it has proper protocol
        endpoint_url = minio_config.get('endpoint', 'http://minio:9000')
        
        # Fix endpoint URL if it's missing protocol
        if endpoint_url and not endpoint_url.startswith(('http://', 'https://')):
            # Add http:// prefix for local MinIO
            endpoint_url = f"http://{endpoint_url}"
            logger.warning(f"Fixed MinIO endpoint URL to include protocol: {endpoint_url}")
        
        credentials = StorageCredentials(
            access_key=minio_config.get('access_key', 'minio'),
            secret_key=minio_config.get('secret_key', 'minio123')
        )
        
        logger.info(f"MinIO endpoint configured: endpoint={endpoint_url}, bucket={bucket}, customer_id={customer_id}")
        
        return StorageEndpoint(
            backend=StorageBackend.MINIO,
            region=region,
            bucket=bucket,
            endpoint_url=endpoint_url,
            credentials=credentials,
            encryption_enabled=minio_config.get('secure', False)
        )
    
    def get_storage_client(self, customer_id: Optional[str] = None):
        """Get storage client for customer"""
        endpoint = self.get_storage_endpoint(customer_id)
        
        client_key = f"{customer_id or 'default'}_{endpoint.backend.value}"
        
        if client_key not in self._storage_clients:
            if endpoint.backend == StorageBackend.S3:
                self._storage_clients[client_key] = self._create_s3_client(endpoint)
            elif endpoint.backend == StorageBackend.GCS:
                self._storage_clients[client_key] = self._create_gcs_client(endpoint)
            elif endpoint.backend == StorageBackend.AZURE:
                self._storage_clients[client_key] = self._create_azure_client(endpoint)
            elif endpoint.backend == StorageBackend.MINIO:
                client = self._create_s3_client(endpoint)  # MinIO uses S3 API
                # Ensure bucket exists for MinIO
                self._ensure_bucket_exists(client, endpoint.bucket)
                self._storage_clients[client_key] = client
                
        return self._storage_clients[client_key]
    
    def _create_s3_client(self, endpoint: StorageEndpoint):
        """Create S3 client with proper credentials"""
        session = boto3.Session()
        
        if endpoint.credentials and endpoint.credentials.role_arn:
            # Use STS to assume role
            sts_client = session.client('sts')
            response = sts_client.assume_role(
                RoleArn=endpoint.credentials.role_arn,
                RoleSessionName=f'logforge-{endpoint.region}',
                ExternalId=endpoint.credentials.external_id
            )
            
            credentials = response['Credentials']
            return session.client(
                's3',
                region_name=endpoint.region,
                endpoint_url=endpoint.endpoint_url,
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
        else:
            # Use direct credentials
            return session.client(
                's3',
                region_name=endpoint.region,
                endpoint_url=endpoint.endpoint_url,
                aws_access_key_id=endpoint.credentials.access_key if endpoint.credentials else None,
                aws_secret_access_key=endpoint.credentials.secret_key if endpoint.credentials else None
            )
    
    def _create_gcs_client(self, endpoint: StorageEndpoint):
        """Create GCS client"""
        # This would require google-cloud-storage library
        # Implementation would be added when GCS support is needed
        raise NotImplementedError("GCS client not implemented yet")
    
    def _create_azure_client(self, endpoint: StorageEndpoint):
        """Create Azure client"""
        # This would require azure-storage-blob library
        # Implementation would be added when Azure support is needed  
        raise NotImplementedError("Azure client not implemented yet")
    
    def _ensure_bucket_exists(self, s3_client, bucket_name: str):
        """Ensure bucket exists, create if it doesn't"""
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
        except Exception as e:
            # Handle both 404 (NoSuchBucket) and other bucket-not-found errors
            if 'NoSuchBucket' in str(e) or '404' in str(e) or 'Not Found' in str(e):
                try:
                    # Create bucket - for MinIO, no location constraint needed
                    s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Successfully created bucket {bucket_name}")
                except Exception as create_error:
                    logger.error(f"Failed to create bucket {bucket_name}: {str(create_error)}")
                    raise
            else:
                logger.error(f"Error checking bucket {bucket_name}: {str(e)}")
                raise
    
    def _merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries"""
        result = base_config.copy()
        for key, value in override_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_compliance_retention_days(self, customer_id: Optional[str] = None) -> int:
        """Get compliance-specific retention period"""
        customer_config = self.config.get('customers', {}).get(customer_id, {}) if customer_id else {}
        deployment = customer_config.get('deployment', self.config['storage']['deployment'])
        compliance_tier = deployment.get('compliance_tier', 'standard')
        
        lifecycle_config = self.config['storage'].get('lifecycle', {})
        compliance_retention = lifecycle_config.get('compliance_retention', {})
        
        return compliance_retention.get(compliance_tier, lifecycle_config.get('delete_after_days', 365))
    
    def is_encryption_required(self, customer_id: Optional[str] = None) -> bool:
        """Check if encryption is required for customer"""
        customer_config = self.config.get('customers', {}).get(customer_id, {}) if customer_id else {}
        deployment = customer_config.get('deployment', self.config['storage']['deployment'])
        compliance_tier = deployment.get('compliance_tier', 'standard')
        
        # All compliance tiers require encryption
        return compliance_tier != 'standard'


# FastAPI dependency for extracting customer ID from headers
from fastapi import Header, HTTPException

def get_customer_id(x_customer_id: str = Header(default="default", alias="X-Customer-ID")) -> str:
    """Extract customer ID from request header"""
    if not x_customer_id or x_customer_id == "default":
        return "default"
    return x_customer_id