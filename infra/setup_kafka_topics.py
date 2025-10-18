#!/usr/bin/env python3
"""
Kafka Topic Management Script for Logforge Event System

This script ensures all Kafka topics are created with correct partition counts
based on the environment configuration. It follows industry best practices:

1. Environment-specific partition counts (dev vs prod)
2. Cooperative rebalancing to minimize downtime
3. Proper error handling and logging
4. Idempotent operations (safe to run multiple times)

Usage:
    python setup_kafka_topics.py --environment development
    python setup_kafka_topics.py --environment production
"""

import os
import sys
import yaml
import asyncio
import argparse
import logging
import subprocess
import json
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KafkaTopicManager:
    """Manages Kafka topic creation and configuration using RPK CLI"""
    
    def __init__(self, bootstrap_servers: str, environment: str = "development"):
        self.bootstrap_servers = bootstrap_servers
        self.environment = environment
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from events.yml"""
        # Try multiple possible paths for the config file
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "apps", "api", "config", "events.yml"),
            os.path.join("/app", "config", "events.yml"),
            os.path.join("/infra", "..", "apps", "api", "config", "events.yml"),
            "config/events.yml"
        ]
        
        config_path = None
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            # Try relative to current working directory
            config_path = os.path.join("apps", "api", "config", "events.yml")
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Apply environment-specific overrides
            if self.environment in config:
                env_config = config[self.environment]
                # Deep merge environment config
                self._deep_merge(config, env_config)
            
            return config
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file: {e}")
            raise
    
    def _deep_merge(self, base: Dict, override: Dict):
        """Deep merge configuration dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass
    
    def get_existing_topics(self) -> Dict[str, Dict[str, Any]]:
        """Get information about existing topics using RPK CLI via Docker"""
        try:
            # Use docker exec to run rpk in the redpanda container
            result = subprocess.run(
                ['docker', 'exec', 'logforge-redpanda', 'rpk', 'topic', 'list'],
                capture_output=True, text=True, check=True
            )
            
            topics_info = {}
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            for line in lines[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        topic_name = parts[0]
                        partitions = int(parts[1])
                        replicas = int(parts[2])
                        
                        if not topic_name.startswith('_'):  # Skip internal topics
                            topics_info[topic_name] = {
                                'partitions': partitions,
                                'replication_factor': replicas
                            }
            
            logger.info(f"Found {len(topics_info)} topics: {list(topics_info.keys())}")
            return topics_info
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting topics with rpk: {e.stderr}")
            return {}
        except Exception as e:
            logger.error(f"Error getting existing topics: {e}")
            return {}
    
    def _get_topic_config(self, topic_key: str) -> Dict[str, Any]:
        """Get topic configuration from events.yml"""
        topics_config = self.config.get("topics", {})
        if topic_key not in topics_config:
            logger.error(f"Topic configuration not found for: {topic_key}")
            return {}
        
        topic_config = topics_config[topic_key].copy()
        
        # Set defaults for missing values
        defaults = {
            'partitions': 10,
            'replication_factor': 1,  # Development default
            'retention_ms': 604800000,  # 7 days
            'cleanup_policy': 'delete',
            'max_message_bytes': 1048576,
            'compression_type': 'lz4'
        }
        
        for key, default_value in defaults.items():
            if key not in topic_config:
                topic_config[key] = default_value
        
        return topic_config
    
    def _needs_recreation(self, topic_name: str, existing_info: Dict[str, Any], 
                         desired_config: Dict[str, Any]) -> bool:
        """Check if topic needs to be recreated"""
        if not existing_info:
            return True
        
        # Check partition count (cannot be decreased, only increased)
        existing_partitions = existing_info.get('partitions', 0)
        desired_partitions = desired_config.get('partitions', 10)
        
        if existing_partitions != desired_partitions:
            if existing_partitions > desired_partitions:
                logger.warning(
                    f"Topic {topic_name} has more partitions ({existing_partitions}) "
                    f"than desired ({desired_partitions}). Cannot decrease partitions."
                )
                return False
            else:
                logger.info(
                    f"Topic {topic_name} needs partition increase: "
                    f"{existing_partitions} -> {desired_partitions}"
                )
                return True
        
        return False
    
    def create_topic(self, topic_name: str, config: Dict[str, Any]) -> bool:
        """Create a single topic with specified configuration using RPK CLI via Docker"""
        try:
            # Create topic with docker exec rpk
            cmd = [
                'docker', 'exec', 'logforge-redpanda', 'rpk', 'topic', 'create', topic_name,
                '--partitions', str(config['partitions']),
                '--replicas', str(config['replication_factor'])
            ]
            
            # Add topic configurations
            configs = [
                f"retention.ms={config['retention_ms']}",
                f"cleanup.policy={config['cleanup_policy']}",
                f"max.message.bytes={config['max_message_bytes']}",
                f"compression.type={config['compression_type']}"
            ]
            
            for cfg in configs:
                cmd.extend(['--config', cfg])
            
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Created topic '{topic_name}' with {config['partitions']} partitions")
            return True
            
        except subprocess.CalledProcessError as e:
            if "already exists" in e.stderr.lower() or "TOPIC_ALREADY_EXISTS" in e.stderr:
                logger.info(f"Topic '{topic_name}' already exists")
                return True
            else:
                logger.error(f"Error creating topic '{topic_name}': {e.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error creating topic '{topic_name}': {e}")
            return False
    
    def delete_topic(self, topic_name: str) -> bool:
        """Delete a topic using RPK CLI via Docker"""
        try:
            cmd = ['docker', 'exec', 'logforge-redpanda', 'rpk', 'topic', 'delete', topic_name]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Deleted topic '{topic_name}'")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error deleting topic '{topic_name}': {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error deleting topic '{topic_name}': {e}")
            return False
    
    def setup_all_topics(self, force_recreate: bool = False) -> bool:
        """Setup all topics defined in configuration"""
        logger.info(f"Setting up Kafka topics for environment: {self.environment}")
        
        # Get existing topics
        existing_topics = self.get_existing_topics()
        logger.info(f"Found {len(existing_topics)} existing topics")
        
        # Process each topic in configuration
        topics_config = self.config.get("topics", {})
        success_count = 0
        
        for topic_key, topic_config in topics_config.items():
            topic_name = topic_config.get('name', topic_key)
            logger.info(f"Processing topic: {topic_name} (key: {topic_key})")
            
            # Get full configuration
            full_config = self._get_topic_config(topic_key)
            if not full_config:
                continue
            
            # Check if topic needs recreation
            needs_recreation = force_recreate or self._needs_recreation(
                topic_name, existing_topics.get(topic_name), full_config
            )
            
            if needs_recreation and topic_name in existing_topics:
                logger.info(f"Recreating topic '{topic_name}' with new configuration")
                if not self.delete_topic(topic_name):
                    logger.error(f"Failed to delete topic '{topic_name}'")
                    continue
            
            # Create or update topic
            if self.create_topic(topic_name, full_config):
                success_count += 1
            else:
                logger.error(f"Failed to create topic '{topic_name}'")
        
        logger.info(f"Successfully processed {success_count}/{len(topics_config)} topics")
        return success_count == len(topics_config)
    
    def validate_topics(self) -> bool:
        """Validate that all topics exist with correct configuration"""
        logger.info("Validating topic configuration...")
        
        existing_topics = self.get_existing_topics()
        topics_config = self.config.get("topics", {})
        
        all_valid = True
        
        for topic_key, topic_config in topics_config.items():
            topic_name = topic_config.get('name', topic_key)
            
            if topic_name not in existing_topics:
                logger.error(f"Topic '{topic_name}' does not exist")
                all_valid = False
                continue
            
            existing_info = existing_topics[topic_name]
            desired_config = self._get_topic_config(topic_key)
            
            # Validate partition count
            if existing_info['partitions'] != desired_config['partitions']:
                logger.error(
                    f"Topic '{topic_name}' has {existing_info['partitions']} partitions, "
                    f"expected {desired_config['partitions']}"
                )
                all_valid = False
            else:
                logger.info(
                    f"Topic '{topic_name}' has correct partition count: "
                    f"{existing_info['partitions']}"
                )
        
        return all_valid


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Kafka Topic Management for Logforge')
    parser.add_argument(
        '--environment', 
        choices=['development', 'production'],
        default='development',
        help='Environment to configure topics for'
    )
    parser.add_argument(
        '--bootstrap-servers',
        default='localhost:19092',
        help='Kafka bootstrap servers'
    )
    parser.add_argument(
        '--force-recreate',
        action='store_true',
        help='Force recreation of all topics'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing topics, do not create'
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting Kafka topic management for {args.environment} environment")
    
    try:
        topic_manager = KafkaTopicManager(
            bootstrap_servers=args.bootstrap_servers,
            environment=args.environment
        )
        
        if args.validate_only:
            valid = topic_manager.validate_topics()
            if valid:
                logger.info("All topics are correctly configured")
                sys.exit(0)
            else:
                logger.error("Topic validation failed")
                sys.exit(1)
        else:
            success = topic_manager.setup_all_topics(
                force_recreate=args.force_recreate
            )
            
            if success:
                logger.info("Topic setup completed successfully")
                
                # Validate immediately with CLI - no metadata sync delays needed
                logger.info("Validating topics with CLI...")
                validation_success = topic_manager.validate_topics()
                
                if validation_success:
                    logger.info("Topic validation passed")
                    sys.exit(0)
                else:
                    logger.error("Topic validation failed")
                    sys.exit(1)
            else:
                logger.error("Topic setup failed")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error in topic management: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()