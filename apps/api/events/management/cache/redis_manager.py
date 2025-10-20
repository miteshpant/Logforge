"""
Redis Manager

Centralized Redis connection and cache management for event-driven architecture.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from contextlib import asynccontextmanager

from app_config import load_config
from constants.database_constants import (
    REDIS_DEFAULT_HOST,
    REDIS_DEFAULT_PORT,
    REDIS_DEFAULT_DB,
    REDIS_DEFAULT_TIMEOUT,
    REDIS_MAX_CONNECTIONS,
    REDIS_SOCKET_TIMEOUT,
    REDIS_RETRY_ATTEMPTS
)

logger = logging.getLogger(__name__)

class RedisManager:
    """
    Centralized Redis connection manager for alert rule caching and event processing.
    
    Features:
    - Connection pooling for performance
    - Automatic reconnection on failures
    - JSON serialization for complex objects
    - TTL management for cache expiration
    - Health monitoring
    """
    
    def __init__(self, 
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 db: Optional[int] = None,
                 password: Optional[str] = None,
                 max_connections: Optional[int] = None,
                 socket_timeout: Optional[int] = None,
                 retry_attempts: Optional[int] = None):
        """
        Initialize Redis manager with connection parameters from config.
        
        Args:
            host: Redis server host (defaults to config value)
            port: Redis server port (defaults to config value)
            db: Database number (defaults to config value)
            password: Redis password if required
            max_connections: Maximum connections in pool (defaults to constant)
            socket_timeout: Socket timeout in seconds (defaults to constant)
            retry_attempts: Number of retry attempts on failure (defaults to constant)
        """
        # Load configuration
        config = load_config()
        
        self.host = host or config.get("redis_host", REDIS_DEFAULT_HOST)
        self.port = port or config.get("redis_port", REDIS_DEFAULT_PORT)
        self.db = db or config.get("redis_db", REDIS_DEFAULT_DB)
        self.password = password
        self.max_connections = max_connections or REDIS_MAX_CONNECTIONS
        self.socket_timeout = socket_timeout or REDIS_SOCKET_TIMEOUT
        self.retry_attempts = retry_attempts or REDIS_RETRY_ATTEMPTS
        
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._connected = False
        
    async def connect(self) -> bool:
        """
        Establish Redis connection with retry logic.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create connection pool
            self._pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                socket_timeout=self.socket_timeout,
                retry_on_timeout=True,
                decode_responses=True  # Automatically decode bytes to strings
            )
            
            # Create Redis client
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            self._connected = True
            
            logger.info(f"✅ Redis connected successfully to {self.host}:{self.port}/{self.db}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Close Redis connection and cleanup resources."""
        try:
            if self._client:
                await self._client.close()
            if self._pool:
                await self._pool.disconnect()
            self._connected = False
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
    
    @asynccontextmanager
    async def get_client(self):
        """
        Context manager for Redis client with automatic reconnection.
        
        Usage:
            async with redis_manager.get_client() as client:
                await client.set("key", "value")
        """
        if not self._connected or not self._client:
            await self.connect()
            
        if not self._connected:
            raise ConnectionError("Redis connection not available")
            
        try:
            yield self._client
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection lost, attempting reconnect: {e}")
            await self.connect()
            if self._connected:
                yield self._client
            else:
                raise ConnectionError("Redis reconnection failed")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform Redis health check.
        
        Returns:
            Health status information
        """
        try:
            async with self.get_client() as client:
                start_time = datetime.now()
                await client.ping()
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                info = await client.info()
                return {
                    "status": "healthy",
                    "connected": True,
                    "latency_ms": round(latency_ms, 2),
                    "memory_used": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "uptime_seconds": info.get("uptime_in_seconds", 0)
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "latency_ms": None
            }
    
    # Key-Value Operations
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a key-value pair with optional TTL.
        
        Args:
            key: Redis key
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            async with self.get_client() as client:
                # Serialize complex objects to JSON
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, default=str)
                
                if ttl:
                    return await client.setex(key, ttl, value)
                else:
                    return await client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value by key with JSON deserialization.
        
        Args:
            key: Redis key
            default: Default value if key not found
            
        Returns:
            Stored value or default
        """
        try:
            async with self.get_client() as client:
                value = await client.get(key)
                if value is None:
                    return default
                
                # Try to deserialize JSON
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            return default
    
    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys.
        
        Args:
            keys: Keys to delete
            
        Returns:
            Number of keys deleted
        """
        try:
            async with self.get_client() as client:
                return await client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE failed for keys {keys}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            async with self.get_client() as client:
                return bool(await client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key."""
        try:
            async with self.get_client() as client:
                return await client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key {key}: {e}")
            return False
    
    # Hash Operations (for structured data)
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field."""
        try:
            async with self.get_client() as client:
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, default=str)
                return await client.hset(key, field, value)
        except Exception as e:
            logger.error(f"Redis HSET failed for {key}.{field}: {e}")
            return False
    
    async def hget(self, key: str, field: str, default: Any = None) -> Any:
        """Get hash field value."""
        try:
            async with self.get_client() as client:
                value = await client.hget(key, field)
                if value is None:
                    return default
                
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
        except Exception as e:
            logger.error(f"Redis HGET failed for {key}.{field}: {e}")
            return default
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields."""
        try:
            async with self.get_client() as client:
                data = await client.hgetall(key)
                
                # Try to deserialize JSON values
                result = {}
                for field, value in data.items():
                    try:
                        result[field] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[field] = value
                        
                return result
        except Exception as e:
            logger.error(f"Redis HGETALL failed for key {key}: {e}")
            return {}
    
    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        try:
            async with self.get_client() as client:
                return await client.hdel(key, *fields)
        except Exception as e:
            logger.error(f"Redis HDEL failed for {key}.{fields}: {e}")
            return 0
    
    # List Operations (for queues)
    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to left of list."""
        try:
            async with self.get_client() as client:
                serialized = []
                for value in values:
                    if isinstance(value, (dict, list)):
                        serialized.append(json.dumps(value, default=str))
                    else:
                        serialized.append(str(value))
                return await client.lpush(key, *serialized)
        except Exception as e:
            logger.error(f"Redis LPUSH failed for key {key}: {e}")
            return 0
    
    async def rpop(self, key: str, default: Any = None) -> Any:
        """Pop value from right of list."""
        try:
            async with self.get_client() as client:
                value = await client.rpop(key)
                if value is None:
                    return default
                
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
        except Exception as e:
            logger.error(f"Redis RPOP failed for key {key}: {e}")
            return default
    
    # Pattern Operations
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        try:
            async with self.get_client() as client:
                return await client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern {pattern}: {e}")
            return []
    
    async def scan_keys(self, pattern: str = "*", count: int = 100) -> List[str]:
        """Efficiently scan keys matching pattern."""
        try:
            keys = []
            async with self.get_client() as client:
                cursor = 0
                while True:
                    cursor, batch = await client.scan(cursor, match=pattern, count=count)
                    keys.extend(batch)
                    if cursor == 0:
                        break
            return keys
        except Exception as e:
            logger.error(f"Redis SCAN failed for pattern {pattern}: {e}")
            return []
    
    # Utility Methods
    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = await self.scan_keys(pattern)
            if keys:
                return await self.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis FLUSH_PATTERN failed for {pattern}: {e}")
            return 0


# Global Redis manager instance
redis_manager = RedisManager()

async def get_redis_manager() -> RedisManager:
    """Get the global Redis manager instance."""
    return redis_manager

async def init_redis(**kwargs) -> RedisManager:
    """Initialize global Redis manager with optional override parameters."""
    global redis_manager
    redis_manager = RedisManager(**kwargs)
    await redis_manager.connect()
    return redis_manager

async def cleanup_redis():
    """Cleanup global Redis manager."""
    global redis_manager
    if redis_manager:
        await redis_manager.disconnect()