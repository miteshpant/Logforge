"""
Customer-Based Partitioning
Hash-based partition assignment using customer ID for event distribution
"""

import hashlib
import os
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


def load_event_config():
    """Load event configuration from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "events.yml")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Get environment-specific overrides
        env = os.getenv('ENVIRONMENT', 'development')
        if env in config:
            # Merge environment-specific config
            for section, values in config[env].items():
                if section in config:
                    if isinstance(config[section], dict) and isinstance(values, dict):
                        # Deep merge for nested dictionaries like topics
                        for key, value in values.items():
                            if key in config[section] and isinstance(config[section][key], dict) and isinstance(value, dict):
                                config[section][key].update(value)
                            else:
                                config[section][key] = value
                    else:
                        config[section].update(values)
        
        return config
    
    except Exception as e:
        logger.error(f"Failed to load event config: {e}")
        # Return environment-appropriate default config
        env = os.getenv('ENVIRONMENT', 'development')
        if env == 'development':
            return {
                "topics": {
                    "usage-events": {"partitions": 10},
                    "alert-events": {"partitions": 5},
                    "log-events": {"partitions": 10},
                    "tenant-events": {"partitions": 20},
                    "ui-realtime-events": {"partitions": 20},
                    "system-events": {"partitions": 10}
                }
            }
        else:
            # Production defaults
            return {
                "topics": {
                    "usage-events": {"partitions": 100},
                    "alert-events": {"partitions": 50},
                    "log-events": {"partitions": 100},
                    "tenant-events": {"partitions": 20},
                    "ui-realtime-events": {"partitions": 200},
                    "system-events": {"partitions": 10}
                }
            }


@dataclass
class PartitionInfo:
    """Information about partition assignment"""
    partition: int
    total_partitions: int
    customer_id: str
    topic: str


class CustomerPartitionManager:
    """Advanced customer-based partitioning for events across multiple topics"""
    
    def __init__(self):
        self.config = load_event_config()
        self.topics_config = self.config.get("topics", {})
        self._partition_cache: Dict[str, Dict[str, int]] = {}  # topic -> {customer_id -> partition}
        
        logger.info("CustomerPartitionManager initialized")
    
    def get_partition(self, customer_id: str, topic: str = "system-events") -> int:
        """Get partition number for a customer using consistent hashing"""
        if not customer_id:
            # Default partition for empty customer_id
            return 0
        
        # Check cache first
        if topic in self._partition_cache and customer_id in self._partition_cache[topic]:
            return self._partition_cache[topic][customer_id]
        
        # Get partition count for topic
        num_partitions = self._get_topic_partitions(topic)
        
        # Use SHA256 hash for consistent partitioning
        hash_input = f"{customer_id}:{topic}"
        hash_value = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
        
        # Convert first 16 characters to int and mod by partition count
        partition = int(hash_value[:16], 16) % num_partitions
        
        # Cache the result
        if topic not in self._partition_cache:
            self._partition_cache[topic] = {}
        self._partition_cache[topic][customer_id] = partition
        
        logger.debug(
            "Customer assigned to partition",
            customer_id=customer_id,
            topic=topic,
            partition=partition,
            total_partitions=num_partitions
        )
        
        return partition
    
    def get_partition_info(self, customer_id: str, topic: str = "system-events") -> PartitionInfo:
        """Get detailed partition information"""
        partition = self.get_partition(customer_id, topic)
        total_partitions = self._get_topic_partitions(topic)
        
        return PartitionInfo(
            partition=partition,
            total_partitions=total_partitions,
            customer_id=customer_id,
            topic=topic
        )
    
    def _get_topic_partitions(self, topic: str) -> int:
        """Get number of partitions for a topic"""
        # First try to find by topic name
        for topic_key, topic_config in self.topics_config.items():
            topic_name = topic_config.get("name", topic_key)
            if topic_name == topic or topic_key == topic:
                return topic_config.get("partitions", 10)
        
        # Default partitions
        return 10
    
    def get_customers_for_partition(self, topic: str, partition: int) -> List[str]:
        """Get list of customers assigned to a specific partition"""
        if topic not in self._partition_cache:
            return []
        
        customers = []
        for customer_id, assigned_partition in self._partition_cache[topic].items():
            if assigned_partition == partition:
                customers.append(customer_id)
        
        return customers
    
    def get_partition_distribution(self, topic: str) -> Dict[int, int]:
        """Get distribution of customers across partitions for a topic"""
        if topic not in self._partition_cache:
            return {}
        
        distribution = {}
        for customer_id, partition in self._partition_cache[topic].items():
            distribution[partition] = distribution.get(partition, 0) + 1
        
        return distribution
    
    def rebalance_customer(self, customer_id: str, topic: str, target_partition: Optional[int] = None) -> int:
        """Rebalance a customer to a different partition (for load balancing)"""
        if target_partition is None:
            # Use hash-based assignment
            return self.get_partition(customer_id, topic)
        
        # Validate target partition
        num_partitions = self._get_topic_partitions(topic)
        if target_partition >= num_partitions:
            raise ValueError(f"Target partition {target_partition} exceeds topic partition count {num_partitions}")
        
        # Update cache
        if topic not in self._partition_cache:
            self._partition_cache[topic] = {}
        
        old_partition = self._partition_cache[topic].get(customer_id)
        self._partition_cache[topic][customer_id] = target_partition
        
        logger.info(
            "Customer rebalanced",
            customer_id=customer_id,
            topic=topic,
            old_partition=old_partition,
            new_partition=target_partition
        )
        
        return target_partition
    
    def clear_cache(self, topic: Optional[str] = None):
        """Clear partition cache for a topic or all topics"""
        if topic:
            if topic in self._partition_cache:
                del self._partition_cache[topic]
                logger.info("Partition cache cleared", topic=topic)
        else:
            self._partition_cache.clear()
            logger.info("All partition caches cleared")
    
    def get_cache_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about partition cache"""
        stats = {}
        
        for topic, customer_partitions in self._partition_cache.items():
            total_customers = len(customer_partitions)
            partition_counts = {}
            
            for partition in customer_partitions.values():
                partition_counts[partition] = partition_counts.get(partition, 0) + 1
            
            stats[topic] = {
                "total_customers": total_customers,
                "unique_partitions": len(partition_counts),
                "total_partitions": self._get_topic_partitions(topic),
                "partition_distribution": partition_counts
            }
        
        return stats
    
    def update_topic_partitions(self, topic: str, new_partition_count: int):
        """Update partition count for a topic (for scaling)"""
        # Find topic config
        for topic_key, topic_config in self.topics_config.items():
            topic_name = topic_config.get("name", topic_key)
            if topic_name == topic or topic_key == topic:
                old_count = topic_config.get("partitions", 10)
                topic_config["partitions"] = new_partition_count
                
                # Clear cache to force recalculation
                self.clear_cache(topic)
                
                logger.info(
                    "Topic partition count updated",
                    topic=topic,
                    old_count=old_count,
                    new_count=new_partition_count
                )
                break


# Legacy class for backward compatibility
class TenantPartitioner:
    """Legacy tenant-based partitioner - deprecated, use CustomerPartitionManager"""
    
    def __init__(self, num_partitions: int = 3):
        self.num_partitions = num_partitions
        self._manager = CustomerPartitionManager()
        logger.warning("TenantPartitioner is deprecated, use CustomerPartitionManager instead")
    
    def get_partition(self, tenant_id: str) -> int:
        """Get partition using new manager"""
        return self._manager.get_partition(tenant_id, "system-events") % self.num_partitions
    
    def update_partition_count(self, new_count: int):
        """Update partition count"""
        self.num_partitions = new_count


# Global instances
customer_partition_manager = CustomerPartitionManager()

# Legacy global instance for backward compatibility
tenant_partitioner = TenantPartitioner()