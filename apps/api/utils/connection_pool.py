"""
Database Connection Pool

Centralized connection pooling for ClickHouse and HTTP clients.
Significantly reduces connection overhead and improves performance.
"""

import os
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import clickhouse_connect
import httpx
import structlog

logger = structlog.get_logger(__name__)


class ClickHousePool:
    """
    ClickHouse connection pool singleton.

    Provides shared client instances to reduce connection overhead.
    Each service gets a cached client instance instead of creating new connections.
    """

    _instance: Optional['ClickHousePool'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._default_client: Optional[Any] = None
        self._config = {
            'host': os.getenv('CLICKHOUSE_HOST', 'clickhouse'),
            'port': int(os.getenv('CLICKHOUSE_PORT', '8123')),
            'username': os.getenv('CLICKHOUSE_USER', 'logforge'),
            'password': os.getenv('CLICKHOUSE_PASSWORD', 'logforge123'),
            'database': os.getenv('CLICKHOUSE_DATABASE', 'logforge'),
        }
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> 'ClickHousePool':
        """Get singleton instance with thread-safe initialization."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        """Initialize the default shared client."""
        if self._initialized:
            return

        try:
            self._default_client = clickhouse_connect.get_client(
                **self._config,
                # Connection pool settings
                compress=True,  # Enable compression
                send_receive_timeout=30,  # 30 second timeout
            )
            self._initialized = True
            logger.info(
                "ClickHouse connection pool initialized",
                host=self._config['host'],
                database=self._config['database']
            )
        except Exception as e:
            logger.error("Failed to initialize ClickHouse pool", error=str(e))
            raise

    def get_client(self, service_name: str = "default") -> Any:
        """
        Get a ClickHouse client for a service.

        Returns the shared default client for efficiency.
        Service name is used for logging/metrics only.
        """
        if not self._initialized or not self._default_client:
            raise RuntimeError("ClickHouse pool not initialized. Call get_instance() first.")

        return self._default_client

    async def health_check(self) -> Dict[str, Any]:
        """Check connection pool health."""
        try:
            if not self._default_client:
                return {"status": "unhealthy", "error": "No client initialized"}

            # Execute simple query to verify connection
            result = self._default_client.command("SELECT 1")

            return {
                "status": "healthy",
                "connected": True,
                "host": self._config['host'],
                "database": self._config['database']
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }

    async def close(self):
        """Close all connections in the pool."""
        if self._default_client:
            try:
                self._default_client.close()
                logger.info("ClickHouse connection pool closed")
            except Exception as e:
                logger.error("Error closing ClickHouse pool", error=str(e))

        self._default_client = None
        self._initialized = False


class HTTPClientPool:
    """
    HTTP client pool for external API calls.

    Provides shared httpx.AsyncClient instances with connection pooling.
    """

    _instance: Optional['HTTPClientPool'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._default_client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> 'HTTPClientPool':
        """Get singleton instance."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        """Initialize the default shared HTTP client."""
        if self._initialized:
            return

        # Create default client with connection pooling
        self._default_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            ),
            http2=True,  # Enable HTTP/2 for better performance
        )
        self._initialized = True
        logger.info("HTTP client pool initialized")

    def get_client(self, name: str = "default") -> httpx.AsyncClient:
        """Get an HTTP client from the pool."""
        if not self._initialized or not self._default_client:
            raise RuntimeError("HTTP client pool not initialized")
        return self._default_client

    @asynccontextmanager
    async def request_context(self, name: str = "default"):
        """Context manager for HTTP requests with automatic error handling."""
        client = self.get_client(name)
        try:
            yield client
        except httpx.TimeoutException as e:
            logger.warning("HTTP request timeout", client=name, error=str(e))
            raise
        except httpx.HTTPError as e:
            logger.error("HTTP request error", client=name, error=str(e))
            raise

    async def close(self):
        """Close all HTTP clients."""
        if self._default_client:
            await self._default_client.aclose()
            logger.info("HTTP client pool closed")

        for name, client in self._clients.items():
            await client.aclose()

        self._clients.clear()
        self._default_client = None
        self._initialized = False


# Global pool instances (initialized lazily)
_clickhouse_pool: Optional[ClickHousePool] = None
_http_pool: Optional[HTTPClientPool] = None


async def get_clickhouse_pool() -> ClickHousePool:
    """Get the global ClickHouse connection pool."""
    global _clickhouse_pool
    if _clickhouse_pool is None:
        _clickhouse_pool = await ClickHousePool.get_instance()
    return _clickhouse_pool


async def get_http_pool() -> HTTPClientPool:
    """Get the global HTTP client pool."""
    global _http_pool
    if _http_pool is None:
        _http_pool = await HTTPClientPool.get_instance()
    return _http_pool


async def initialize_pools():
    """Initialize all connection pools at application startup."""
    await get_clickhouse_pool()
    await get_http_pool()
    logger.info("All connection pools initialized")


async def close_pools():
    """Close all connection pools at application shutdown."""
    global _clickhouse_pool, _http_pool

    if _clickhouse_pool:
        await _clickhouse_pool.close()
        _clickhouse_pool = None

    if _http_pool:
        await _http_pool.close()
        _http_pool = None

    logger.info("All connection pools closed")
