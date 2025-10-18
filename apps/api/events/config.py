"""
Simple Event Configuration
Reads from existing events.yml configuration file
"""

import os
import yaml
from dataclasses import dataclass
from typing import Dict, Optional
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class EventConfig:
    """Simple event system configuration"""
    
    # Kafka connection
    bootstrap_servers: str = "redpanda:9092"
    security_protocol: str = "PLAINTEXT"
    
    # Topic configuration
    topic_name: str = "log-ingestion-events"
    partitions: int = 3
    replication_factor: int = 1
    
    # Consumer configuration
    consumer_group: str = "logforge-ingestion"
    auto_offset_reset: str = "latest"
    
    # Producer configuration
    acks: str = "1"
    retries: int = 3

def load_event_config() -> EventConfig:
    """Load configuration from events.yml file"""
    config_path = "/app/config/events.yml"
    
    try:
        with open(config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
        
        # Get environment (default to development)
        environment = os.getenv("ENVIRONMENT", "development")
        
        # Extract Kafka configuration
        kafka_config = yaml_config.get("kafka", {})
        
        # Get environment-specific overrides
        env_config = yaml_config.get(environment, {})
        env_kafka = env_config.get("kafka", {})
        
        # Merge configurations (environment overrides base)
        final_kafka = {**kafka_config, **env_kafka}
        
        # Create configuration
        config = EventConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092"),
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            topic_name="log-ingestion-events",
            partitions=3,  # Simple partitioning for now
            replication_factor=1,  # Single broker setup
            acks=final_kafka.get("acks", "1"),
            retries=final_kafka.get("retries", 3)
        )
        
        logger.info("Event configuration loaded successfully", environment=environment)
        return config
        
    except Exception as e:
        logger.warning(f"Failed to load events.yml, using defaults: {e}")
        return EventConfig()

# Global configuration instance
event_config = load_event_config()