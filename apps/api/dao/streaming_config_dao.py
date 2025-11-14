"""
Streaming Configuration Data Access Object
Handles database operations for streaming configurations
"""

import structlog
from typing import Dict, Any, Optional, List
from database_layer import DatabaseLayer
from constants.streaming_config import VALID_STREAMING_CONFIG_TYPES

logger = structlog.get_logger(__name__)


class StreamingConfigDAO:
    """Data Access Object for streaming configurations"""
    
    def __init__(self):
        self.db = DatabaseLayer("StreamingConfigDAO", "streaming-config-service-key")
    
    async def get_all_streaming_configs(self) -> List[Dict[str, Any]]:
        """Get all streaming configurations from database"""
        query = """
        SELECT customer_id, config_key, config_value, created_at, updated_at, created_by
        FROM tenant_configs_mt 
        WHERE config_key IN %(config_keys)s
        AND config_type = 'json'
        ORDER BY customer_id, config_key
        """
        
        result = await self.db.execute_query(query, {
            "config_keys": VALID_STREAMING_CONFIG_TYPES
        })
        
        return result if result else []
    
    async def get_customer_streaming_config(self, customer_id: str, config_key: str) -> Optional[Dict[str, Any]]:
        """Get specific streaming configuration for a customer"""
        query = """
        SELECT customer_id, config_key, config_value, created_at, updated_at, created_by
        FROM tenant_configs_mt 
        WHERE customer_id = %(customer_id)s
        AND config_key = %(config_key)s
        AND config_type = 'json'
        LIMIT 1
        """
        
        result = await self.db.execute_query(query, {
            "customer_id": customer_id,
            "config_key": config_key
        })
        
        return result[0] if result else None
    
    async def get_customer_all_streaming_configs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all streaming configurations for a specific customer"""
        query = """
        SELECT customer_id, config_key, config_value, created_at, updated_at, created_by
        FROM tenant_configs_mt 
        WHERE customer_id = %(customer_id)s
        AND config_key IN %(config_keys)s
        AND config_type = 'json'
        ORDER BY config_key
        """
        
        result = await self.db.execute_query(query, {
            "customer_id": customer_id,
            "config_keys": VALID_STREAMING_CONFIG_TYPES
        })
        
        return result if result else []
    
    async def create_streaming_config(
        self, 
        customer_id: str, 
        config_key: str, 
        config_value: str, 
        created_by: str
    ) -> bool:
        """Create new streaming configuration"""
        try:
            import uuid
            config_id = str(uuid.uuid4())
            
            # INSERT query for tenant_configs_mt
            query = """
            INSERT INTO tenant_configs_mt (
                id, tenant_id, config_key, config_value, config_type, created_by, customer_id
            ) VALUES (
                %(id)s, %(tenant_id)s, %(config_key)s, %(config_value)s, %(config_type)s, %(created_by)s, %(customer_id)s
            )
            """
            
            await self.db.execute_query(query, {
                "id": config_id,
                "tenant_id": customer_id,
                "config_key": config_key,
                "config_value": config_value,
                "config_type": "json",
                "created_by": created_by,
                "customer_id": customer_id
            })
            
            logger.info(f"Created streaming config: {customer_id}:{config_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create streaming config: {e}")
            return False
    
    async def update_streaming_config(
        self, 
        customer_id: str, 
        config_key: str, 
        config_value: str
    ) -> bool:
        """Update existing streaming configuration"""
        try:
            query = """
            ALTER TABLE tenant_configs_mt UPDATE 
                config_value = %(config_value)s,
                updated_at = now64(3)
            WHERE customer_id = %(customer_id)s 
            AND config_key = %(config_key)s
            AND config_type = 'json'
            """
            
            await self.db.execute_update(query, {
                "customer_id": customer_id,
                "config_key": config_key,
                "config_value": config_value
            })
            
            logger.info(f"Updated streaming config: {customer_id}:{config_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update streaming config: {e}")
            return False
    
    async def upsert_streaming_config(
        self, 
        customer_id: str, 
        config_key: str, 
        config_value: str, 
        created_by: str
    ) -> bool:
        """Create or update streaming configuration"""
        try:
            # Check if config exists
            existing = await self.get_customer_streaming_config(customer_id, config_key)
            
            if existing:
                # Update existing
                return await self.update_streaming_config(customer_id, config_key, config_value)
            else:
                # Create new
                return await self.create_streaming_config(customer_id, config_key, config_value, created_by)
                
        except Exception as e:
            logger.error(f"Failed to upsert streaming config: {e}")
            return False
    
    async def delete_streaming_config(self, customer_id: str, config_key: str) -> bool:
        """Delete streaming configuration"""
        try:
            query = """
            ALTER TABLE tenant_configs_mt DELETE 
            WHERE customer_id = %(customer_id)s 
            AND config_key = %(config_key)s
            AND config_type = 'json'
            """
            
            await self.db.execute_update(query, {
                "customer_id": customer_id,
                "config_key": config_key
            })
            
            logger.info(f"Deleted streaming config: {customer_id}:{config_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete streaming config: {e}")
            return False
    
    async def config_exists(self, customer_id: str, config_key: str) -> bool:
        """Check if streaming configuration exists"""
        query = """
        SELECT 1
        FROM tenant_configs_mt 
        WHERE customer_id = %(customer_id)s
        AND config_key = %(config_key)s
        AND config_type = 'json'
        LIMIT 1
        """
        
        result = await self.db.execute_query(query, {
            "customer_id": customer_id,
            "config_key": config_key
        })
        
        return len(result) > 0