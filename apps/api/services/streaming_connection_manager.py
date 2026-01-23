"""
Streaming Connection Manager - Manages SSE connections for graceful shutdown

This manager tracks all active streaming connections and provides a shutdown
mechanism to gracefully close them when the server is shutting down.
"""

import asyncio
from typing import Dict, Set, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class StreamingConnectionManager:
    """
    Singleton manager for SSE streaming connections.

    Provides:
    - Connection tracking with unique IDs
    - Global shutdown event for graceful termination
    - Connection statistics
    """

    _instance: Optional['StreamingConnectionManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._connections: Dict[str, dict] = {}
        self._shutdown_event = asyncio.Event()
        self._connection_counter = 0
        logger.info("StreamingConnectionManager initialized")

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Get the shutdown event that connections should monitor"""
        return self._shutdown_event

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()

    def register_connection(self, stream_type: str, customer_id: str) -> str:
        """
        Register a new streaming connection.

        Args:
            stream_type: Type of stream (alerts, metrics, traces, security, etc.)
            customer_id: Customer ID for the connection

        Returns:
            Unique connection ID
        """
        self._connection_counter += 1
        connection_id = f"{stream_type}_{customer_id}_{self._connection_counter}"

        self._connections[connection_id] = {
            "stream_type": stream_type,
            "customer_id": customer_id,
            "connected_at": datetime.now().isoformat(),
            "status": "active"
        }

        logger.info(
            f"Streaming connection registered: {connection_id} "
            f"(total_active={len(self._connections)})"
        )

        return connection_id

    def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister a streaming connection (called when connection closes).

        Args:
            connection_id: The connection ID to remove
        """
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.info(
                f"Streaming connection unregistered: {connection_id} "
                f"(total_active={len(self._connections)})"
            )

    def get_active_connections(self) -> Dict[str, dict]:
        """Get all active connections"""
        return self._connections.copy()

    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self._connections)

    def get_connections_by_type(self, stream_type: str) -> Dict[str, dict]:
        """Get connections filtered by stream type"""
        return {
            cid: info for cid, info in self._connections.items()
            if info["stream_type"] == stream_type
        }

    async def shutdown(self, timeout: float = 5.0) -> None:
        """
        Signal all connections to shut down gracefully.

        Args:
            timeout: Maximum time to wait for connections to close (seconds)
        """
        active_count = len(self._connections)
        logger.info(
            f"Initiating streaming shutdown with {active_count} active connections "
            f"(timeout={timeout}s)"
        )

        # Set the shutdown event - all streaming generators should check this
        self._shutdown_event.set()

        # Wait for connections to close with timeout
        start_time = asyncio.get_event_loop().time()
        while len(self._connections) > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                remaining = len(self._connections)
                logger.warning(
                    f"Shutdown timeout reached with {remaining} connections still active. "
                    f"Force closing remaining connections."
                )
                # Clear remaining connections (they'll be forcefully terminated)
                self._connections.clear()
                break

            # Brief wait before checking again
            await asyncio.sleep(0.1)

        logger.info("Streaming connection manager shutdown complete")

    def reset(self) -> None:
        """Reset the manager state (primarily for testing)"""
        self._connections.clear()
        self._shutdown_event.clear()
        self._connection_counter = 0
        logger.info("StreamingConnectionManager reset")


# Singleton instance getter
def get_streaming_connection_manager() -> StreamingConnectionManager:
    """Get the singleton streaming connection manager instance"""
    return StreamingConnectionManager()
