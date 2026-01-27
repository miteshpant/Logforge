"""
Streaming Configuration Service
Manages streaming configurations in Redis with database synchronization via DAO
"""

import json
import structlog
from typing import Dict, Any, Optional
from dao.streaming_config_dao import StreamingConfigDAO
from events.management.cache.redis_manager import get_redis_manager
from constants.streaming_config import (
    STREAMING_CONFIG_MAP, REDIS_DEFAULT_STREAMING_CONFIG_KEY,
    get_customer_streaming_config_key, VALID_STREAMING_CONFIG_TYPES
)

logger = structlog.get_logger(__name__)


class StreamingConfigService:
    """Service for managing streaming configurations with Redis caching"""
    
    def __init__(self):
        self.dao = StreamingConfigDAO()
        self.redis = None  # Will be initialized async
    
    async def _ensure_redis_connection(self):
        """Ensure Redis connection is established"""
        if self.redis is None:
            self.redis = await get_redis_manager()
    
    async def load_all_configs_to_redis(self) -> bool:
        """Load all streaming configurations from database to Redis on startup"""
        try:
            await self._ensure_redis_connection()
            logger.info("Loading streaming configurations from database to Redis")
            
            # Load default configurations first
            await self._load_default_configs()
            
            # Load all customer configurations from database via DAO
            configs = await self.dao.get_all_streaming_configs()
            
            for config in configs:
                await self._store_config_in_redis(
                    customer_id=config['customer_id'],
                    config_key=config['config_key'],
                    config_value=config['config_value']
                )
            
            logger.info(f"Loaded {len(configs)} streaming configurations to Redis")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load streaming configurations to Redis: {e}")
            return False
    
    async def get_streaming_config(self, customer_id: str, event_type: str) -> Dict[str, Any]:
        """Get streaming configuration for a customer and event type"""
        try:
            await self._ensure_redis_connection()
            
            # Check if we have this event type mapping
            if event_type not in STREAMING_CONFIG_MAP:
                logger.warning(f"Unknown event type for streaming config: {event_type}")
                return {}
            
            # Try to get customer-specific config from Redis
            redis_key = get_customer_streaming_config_key(customer_id, event_type)
            logger.info(f"Redis lookup: key={redis_key}, redis_connected={self.redis is not None}")
            
            config_data = await self.redis.get(redis_key)
            logger.info(f"Redis result: found={config_data is not None}, type={type(config_data).__name__}")
            
            if config_data:
                # Handle both string and dict responses from Redis
                if isinstance(config_data, dict):
                    config = config_data  # Already parsed
                else:
                    config = json.loads(config_data)  # Parse JSON string
                    
                logger.info(f"Found custom streaming config for {customer_id}:{event_type}")
                return config
            
            # Fall back to default configuration
            defaults = STREAMING_CONFIG_MAP[event_type]["defaults"]
            logger.info(f"Using default streaming config for {customer_id}:{event_type}")
            return defaults
            
        except Exception as e:
            logger.error(f"Error getting streaming config for {customer_id}:{event_type}: {e}")
            # Return defaults if Redis fails
            return STREAMING_CONFIG_MAP.get(event_type, {}).get("defaults", {})
    
    async def set_streaming_config(
        self, 
        customer_id: str, 
        config_key: str, 
        config: Dict[str, Any], 
        created_by: str
    ) -> bool:
        """Set streaming configuration for a customer"""
        try:
            # Validate config key
            if config_key not in VALID_STREAMING_CONFIG_TYPES:
                raise ValueError(f"Invalid config key: {config_key}")
            
            # Get event type from config key
            event_type = self._get_event_type_from_config_key(config_key)
            if not event_type:
                raise ValueError(f"Could not map config key to event type: {config_key}")
            
            # Merge with defaults to ensure all fields are present
            defaults = STREAMING_CONFIG_MAP[event_type]["defaults"]
            merged_config = {**defaults, **config}
            
            # Validate configuration
            self._validate_streaming_config(merged_config, event_type)
            
            # Store in database via DAO
            config_json = json.dumps(merged_config)
            success = await self.dao.upsert_streaming_config(
                customer_id, config_key, config_json, created_by
            )
            
            if not success:
                raise Exception("Failed to store config in database")
            
            # Store in Redis
            await self._store_config_in_redis(customer_id, config_key, config_json)
            
            logger.info(f"Set streaming config for {customer_id}:{config_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set streaming config for {customer_id}:{config_key}: {e}")
            raise
    
    async def delete_streaming_config(self, customer_id: str, config_key: str) -> bool:
        """Delete streaming configuration for a customer (falls back to defaults)"""
        try:
            # Delete from database via DAO
            success = await self.dao.delete_streaming_config(customer_id, config_key)
            
            if success:
                # Delete from Redis
                await self._ensure_redis_connection()
                event_type = self._get_event_type_from_config_key(config_key)
                if event_type:
                    redis_key = get_customer_streaming_config_key(customer_id, event_type)
                    await self.redis.delete(redis_key)
                
                logger.info(f"Deleted streaming config for {customer_id}:{config_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete streaming config for {customer_id}:{config_key}: {e}")
            return False
    
    async def get_customer_streaming_config_from_db(
        self, 
        customer_id: str, 
        config_key: str
    ) -> Optional[Dict[str, Any]]:
        """Get streaming configuration from database (bypassing Redis)"""
        try:
            config_data = await self.dao.get_customer_streaming_config(customer_id, config_key)
            
            if config_data:
                return {
                    "config": json.loads(config_data['config_value']),
                    "created_at": config_data['created_at'],
                    "updated_at": config_data['updated_at'],
                    "created_by": config_data['created_by']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get config from DB for {customer_id}:{config_key}: {e}")
            return None
    
    async def get_all_customer_configs(self, customer_id: str) -> Dict[str, Any]:
        """Get all streaming configurations for a customer"""
        try:
            configs = {}

            for event_type in STREAMING_CONFIG_MAP.keys():
                config = await self.get_streaming_config(customer_id, event_type)
                configs[event_type] = config

            return configs

        except Exception as e:
            logger.error(f"Failed to get all configs for customer {customer_id}: {e}")
            return {}

    async def get_all_customer_configs_with_defaults_info(
        self,
        customer_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all streaming configurations with info about which use defaults.

        Performance optimized: single batch query to DB instead of N+1 queries.

        Returns:
            {
                "configs": {event_type: config_dict, ...},
                "using_defaults": {event_type: bool, ...}
            }
        """
        try:
            configs = {}
            using_defaults = {}

            # Single batch query to get all custom configs for this customer
            custom_configs = await self.dao.get_all_customer_configs_batch(customer_id)

            # Build a lookup of config_key -> config_data
            custom_config_lookup = {}
            for config in custom_configs:
                custom_config_lookup[config['config_key']] = config

            # Process each event type
            for event_type, mapping in STREAMING_CONFIG_MAP.items():
                config_key = mapping["config_key"]

                # Check if customer has custom config
                if config_key in custom_config_lookup:
                    # Customer has custom config
                    custom = custom_config_lookup[config_key]
                    configs[event_type] = json.loads(custom['config_value'])
                    using_defaults[event_type] = False
                else:
                    # Use defaults
                    configs[event_type] = mapping["defaults"]
                    using_defaults[event_type] = True

            return {
                "configs": configs,
                "using_defaults": using_defaults
            }

        except Exception as e:
            logger.error(f"Failed to get all configs with defaults info for {customer_id}: {e}")
            # Fall back to returning defaults for all
            configs = {et: m["defaults"] for et, m in STREAMING_CONFIG_MAP.items()}
            using_defaults = {et: True for et in STREAMING_CONFIG_MAP.keys()}
            return {"configs": configs, "using_defaults": using_defaults}
    
    # Private methods
    
    async def _load_default_configs(self):
        """Load default configurations into Redis"""
        try:
            for event_type, mapping in STREAMING_CONFIG_MAP.items():
                default_config = mapping["defaults"]
                config_json = json.dumps(default_config)
                
                # Store default config in Redis
                redis_key = f"{REDIS_DEFAULT_STREAMING_CONFIG_KEY}:{event_type}"
                await self.redis.set(redis_key, config_json)
                
            logger.info("Loaded default streaming configurations to Redis")
            
        except Exception as e:
            logger.error(f"Failed to load default configs: {e}")
            raise
    
    async def _store_config_in_redis(self, customer_id: str, config_key: str, config_json: str):
        """Store configuration in Redis"""
        await self._ensure_redis_connection()
        event_type = self._get_event_type_from_config_key(config_key)
        
        if event_type:
            redis_key = get_customer_streaming_config_key(customer_id, event_type)
            await self.redis.set(redis_key, config_json)
    
    def _get_event_type_from_config_key(self, config_key: str) -> Optional[str]:
        """Map config_key to event_type"""
        for event_type, mapping in STREAMING_CONFIG_MAP.items():
            if mapping["config_key"] == config_key:
                return event_type
        return None
    
    def _validate_streaming_config(self, config: Dict[str, Any], event_type: str):
        """Validate streaming configuration"""
        # Basic validation
        if not isinstance(config.get("enabled"), bool):
            raise ValueError("'enabled' must be a boolean")
        
        if not (0.0 <= config.get("sample_rate", 0) <= 1.0):
            raise ValueError("'sample_rate' must be between 0.0 and 1.0")
        
        if not isinstance(config.get("max_events_per_minute"), int):
            raise ValueError("'max_events_per_minute' must be an integer")
        
        # Event-specific validation
        if event_type == "metrics.batch.ingested":
            if config.get("min_value_change_threshold", 0) < 0:
                raise ValueError("'min_value_change_threshold' must be >= 0")
        
        elif event_type == "traces.batch.ingested":
            if config.get("min_duration_ms", 0) < 0:
                raise ValueError("'min_duration_ms' must be >= 0")


# Global service instance
_streaming_config_service = None

def get_streaming_config_service() -> StreamingConfigService:
    """Get singleton streaming config service instance"""
    global _streaming_config_service
    if _streaming_config_service is None:
        _streaming_config_service = StreamingConfigService()
    return _streaming_config_service