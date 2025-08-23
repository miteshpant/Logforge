#!/usr/bin/env python3
"""
ClickHouse Storage Configuration Generator
Generates dynamic storage policies based on deployment type and cloud backend
"""

import os
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from pathlib import Path

class StorageConfigGenerator:
    def __init__(self, config_path: str = "config/storage-config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load storage configuration from YAML"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # Return default configuration
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Default configuration for development"""
        return {
            'storage': {
                'deployment': {'type': 'shared', 'region': 'us-east-1'},
                'cold': {
                    'enabled': True,
                    'backend': 's3',
                    'backends': {
                        's3': {
                            'shared': {
                                'enabled': True,
                                'bucket_prefix': 'logforge-dev',
                                'region': 'us-east-1'
                            }
                        }
                    }
                }
            }
        }
    
    def generate_clickhouse_storage_xml(self, customer_id: Optional[str] = None) -> str:
        """Generate ClickHouse storage configuration XML"""
        
        # Get customer-specific config if provided
        storage_config = self.config['storage']
        if customer_id and customer_id in self.config.get('customers', {}):
            customer_config = self.config['customers'][customer_id]
            # Merge customer config with defaults
            storage_config = self._merge_configs(storage_config, customer_config)
        
        # Create XML root
        root = ET.Element('clickhouse')
        storage_configuration = ET.SubElement(root, 'storage_configuration')
        
        # Generate disks configuration
        disks = ET.SubElement(storage_configuration, 'disks')
        self._generate_disks(disks, storage_config, customer_id)
        
        # Generate policies configuration
        policies = ET.SubElement(storage_configuration, 'policies')
        self._generate_policies(policies, storage_config)
        
        # Pretty print XML
        self._indent_xml(root)
        return ET.tostring(root, encoding='unicode')
    
    def _generate_disks(self, disks_elem: ET.Element, config: Dict[str, Any], customer_id: Optional[str]):
        """Generate disk configurations for different backends"""
        cold_config = config.get('cold', {})
        backend = cold_config.get('backend', 's3')
        deployment_type = config.get('deployment', {}).get('type', 'shared')
        
        if backend == 's3':
            self._generate_s3_disk(disks_elem, cold_config, deployment_type, customer_id)
        elif backend == 'gcs':
            self._generate_gcs_disk(disks_elem, cold_config, deployment_type, customer_id)
        elif backend == 'azure':
            self._generate_azure_disk(disks_elem, cold_config, deployment_type, customer_id)
        elif backend == 'minio':
            self._generate_minio_disk(disks_elem, cold_config, deployment_type, customer_id)
    
    def _generate_s3_disk(self, disks_elem: ET.Element, cold_config: Dict[str, Any], 
                         deployment_type: str, customer_id: Optional[str]):
        """Generate S3 disk configuration"""
        s3_config = cold_config.get('backends', {}).get('s3', {})
        
        # Determine which S3 config to use
        if deployment_type == 'fedramp':
            s3_backend_config = s3_config.get('fedramp', {})
            disk_name = 'fedramp_s3_disk'
        elif deployment_type == 'dedicated':
            s3_backend_config = s3_config.get('dedicated', {})
            disk_name = f'{customer_id}_s3_disk' if customer_id else 'dedicated_s3_disk'
        else:
            s3_backend_config = s3_config.get('shared', {})
            disk_name = 'shared_s3_disk'
        
        if not s3_backend_config.get('enabled', False):
            return
            
        s3_disk = ET.SubElement(disks_elem, disk_name)
        
        # Basic S3 configuration
        ET.SubElement(s3_disk, 'type').text = 's3'
        
        # Bucket configuration
        if deployment_type == 'shared':
            bucket_name = f"{s3_backend_config.get('bucket_prefix', 'logforge-shared')}-{customer_id}" if customer_id else s3_backend_config.get('bucket_prefix', 'logforge-shared')
        else:
            bucket_name = s3_backend_config.get('bucket', f'{customer_id}-logforge-cold' if customer_id else 'logforge-cold')
            
        # Endpoint and region
        if 'endpoint' in s3_backend_config:
            endpoint_url = f"{s3_backend_config['endpoint']}/{bucket_name}/"
        else:
            region = s3_backend_config.get('region', 'us-east-1')
            if deployment_type == 'fedramp':
                endpoint_url = f'https://s3.{region}.amazonaws.com/{bucket_name}/'
            else:
                endpoint_url = f'https://s3.{region}.amazonaws.com/{bucket_name}/'
        
        ET.SubElement(s3_disk, 'endpoint').text = endpoint_url
        
        # Authentication
        if 'role_arn' in s3_backend_config:
            # Use IAM role
            ET.SubElement(s3_disk, 'use_environment_credentials').text = 'true'
        else:
            # Use access keys
            ET.SubElement(s3_disk, 'access_key_id').text = s3_backend_config.get('access_key', os.getenv('AWS_ACCESS_KEY_ID', 'minio'))
            ET.SubElement(s3_disk, 'secret_access_key').text = s3_backend_config.get('secret_key', os.getenv('AWS_SECRET_ACCESS_KEY', 'minio123'))
            ET.SubElement(s3_disk, 'use_environment_credentials').text = 'false'
        
        # Additional S3 settings
        ET.SubElement(s3_disk, 'region').text = s3_backend_config.get('region', 'us-east-1')
        ET.SubElement(s3_disk, 'path_style_access').text = 'true' if deployment_type == 'shared' else 'false'
        ET.SubElement(s3_disk, 'metadata_path').text = f'/var/lib/clickhouse/disks/{disk_name}/'
        
    def _generate_gcs_disk(self, disks_elem: ET.Element, cold_config: Dict[str, Any], 
                          deployment_type: str, customer_id: Optional[str]):
        """Generate GCS disk configuration"""
        gcs_config = cold_config.get('backends', {}).get('gcs', {})
        
        if deployment_type == 'dedicated':
            gcs_backend_config = gcs_config.get('dedicated', {})
            disk_name = f'{customer_id}_gcs_disk' if customer_id else 'dedicated_gcs_disk'
        else:
            gcs_backend_config = gcs_config.get('shared', {})
            disk_name = 'shared_gcs_disk'
            
        if not gcs_backend_config.get('enabled', False):
            return
            
        # Note: ClickHouse doesn't have native GCS support
        # This would need to be implemented via S3-compatible interface or custom solution
        # For now, we'll document this as a future enhancement
        pass
    
    def _generate_azure_disk(self, disks_elem: ET.Element, cold_config: Dict[str, Any], 
                           deployment_type: str, customer_id: Optional[str]):
        """Generate Azure disk configuration"""
        # Similar to GCS, Azure Blob would need custom implementation
        pass
    
    def _generate_minio_disk(self, disks_elem: ET.Element, cold_config: Dict[str, Any], 
                           deployment_type: str, customer_id: Optional[str]):
        """Generate MinIO disk configuration for on-premises deployments"""
        minio_config = cold_config.get('backends', {}).get('minio', {})
        
        if not minio_config.get('enabled', False):
            return
            
        minio_disk = ET.SubElement(disks_elem, 'minio_disk')
        ET.SubElement(minio_disk, 'type').text = 's3'
        ET.SubElement(minio_disk, 'endpoint').text = f"{minio_config.get('endpoint', 'http://minio:9000')}/{minio_config.get('bucket', 'logforge')}/"
        ET.SubElement(minio_disk, 'access_key_id').text = minio_config.get('access_key', 'minio')
        ET.SubElement(minio_disk, 'secret_access_key').text = minio_config.get('secret_key', 'minio123')
        ET.SubElement(minio_disk, 'use_environment_credentials').text = 'false'
        ET.SubElement(minio_disk, 'path_style_access').text = 'true'
        ET.SubElement(minio_disk, 'metadata_path').text = '/var/lib/clickhouse/disks/minio/'
    
    def _generate_policies(self, policies_elem: ET.Element, config: Dict[str, Any]):
        """Generate storage policies"""
        deployment_type = config.get('deployment', {}).get('type', 'shared')
        
        # Default policy for hot/cold tiering
        default_policy = ET.SubElement(policies_elem, 'default_policy')
        volumes = ET.SubElement(default_policy, 'volumes')
        
        # Hot volume (local disk)
        hot_volume = ET.SubElement(volumes, 'hot')
        ET.SubElement(hot_volume, 'disk').text = 'default'
        
        # Cold volume (cloud storage)
        cold_volume = ET.SubElement(volumes, 'cold')
        if deployment_type == 'fedramp':
            ET.SubElement(cold_volume, 'disk').text = 'fedramp_s3_disk'
        elif deployment_type == 'dedicated':
            ET.SubElement(cold_volume, 'disk').text = 'dedicated_s3_disk'
        else:
            ET.SubElement(cold_volume, 'disk').text = 'shared_s3_disk'
            
        # Policy settings
        ET.SubElement(default_policy, 'move_factor').text = '0.1'
        ET.SubElement(default_policy, 'prefer_not_to_merge').text = 'true'
    
    def _merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries"""
        result = base_config.copy()
        for key, value in override_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def _indent_xml(self, elem: ET.Element, level: int = 0):
        """Pretty print XML with proper indentation"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent_xml(child, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

def main():
    """Generate storage configuration for different deployment scenarios"""
    generator = StorageConfigGenerator()
    
    # Generate configurations for different scenarios
    scenarios = [
        ('shared', None),
        ('dedicated', 'enterprise_customer'),
        ('fedramp', 'gov_agency'),
    ]
    
    for deployment_type, customer_id in scenarios:
        print(f"\n=== {deployment_type.upper()} Deployment Configuration ===")
        if customer_id:
            print(f"Customer: {customer_id}")
        
        config_xml = generator.generate_clickhouse_storage_xml(customer_id)
        print(config_xml)
        
        # Save to file
        output_path = Path(f"infra/docker/clickhouse/config.d/{deployment_type}_storage.xml")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(config_xml)

if __name__ == '__main__':
    main()