"""
High-Performance Write Buffer Service

Batches log writes to ClickHouse to amortize network overhead.
Instead of 40ms per log, batching 100 logs takes ~50ms total.

Performance characteristics:
- Single log: 40ms (flushes on timeout)
- 100 logs: ~50ms (batched insert)
- 1000 logs: ~100ms (batched insert)

Buffer Strategy:
- Flush when buffer reaches size threshold (default: 100 logs)
- Flush on time interval (default: 100ms) to prevent stale data
- Separate buffers per customer for tenant isolation
- Separate buffers for raw vs normalized tables
"""

import asyncio
import threading
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BufferConfig:
    """Configuration for write buffer behavior"""
    max_buffer_size: int = 100  # Flush when buffer reaches this size
    flush_interval_ms: int = 100  # Flush at least this often (milliseconds)
    max_retry_attempts: int = 3  # Retry failed flushes
    retry_delay_ms: int = 50  # Delay between retries


@dataclass
class BufferStats:
    """Statistics for monitoring buffer performance"""
    total_logs_buffered: int = 0
    total_logs_flushed: int = 0
    total_flushes: int = 0
    total_flush_time_ms: float = 0.0
    flush_by_size: int = 0  # Flushes triggered by size threshold
    flush_by_time: int = 0  # Flushes triggered by time interval
    flush_errors: int = 0
    avg_batch_size: float = 0.0
    avg_flush_time_ms: float = 0.0

    def update_averages(self):
        if self.total_flushes > 0:
            self.avg_batch_size = self.total_logs_flushed / self.total_flushes
            self.avg_flush_time_ms = self.total_flush_time_ms / self.total_flushes


@dataclass
class CustomerBuffer:
    """Buffer for a single customer's logs"""
    customer_id: str
    raw_logs: List[Dict[str, Any]] = field(default_factory=list)
    normalized_logs: List[Dict[str, Any]] = field(default_factory=list)
    last_flush_time: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)


class WriteBufferService:
    """
    High-performance write buffer for ClickHouse inserts.

    Batches logs per customer and flushes based on size or time thresholds.
    Thread-safe for concurrent writes from multiple event handlers.
    """

    def __init__(self, config: Optional[BufferConfig] = None):
        self.config = config or BufferConfig()
        self.buffers: Dict[str, CustomerBuffer] = {}
        self.stats = BufferStats()
        self._global_lock = threading.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._flush_callback: Optional[Callable] = None

        logger.info(
            "WriteBufferService initialized",
            max_buffer_size=self.config.max_buffer_size,
            flush_interval_ms=self.config.flush_interval_ms
        )

    def set_flush_callback(self, callback: Callable):
        """
        Set the callback function for flushing logs to ClickHouse.

        The callback should have signature:
            async def flush(customer_id: str, raw_logs: List, normalized_logs: List) -> bool
        """
        self._flush_callback = callback

    def _get_or_create_buffer(self, customer_id: str) -> CustomerBuffer:
        """Get or create a buffer for a customer (thread-safe)"""
        if customer_id not in self.buffers:
            with self._global_lock:
                if customer_id not in self.buffers:
                    self.buffers[customer_id] = CustomerBuffer(customer_id=customer_id)
        return self.buffers[customer_id]

    async def add_logs(
        self,
        customer_id: str,
        raw_logs: Optional[List[Dict[str, Any]]] = None,
        normalized_logs: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Add logs to the buffer for a customer.

        Automatically flushes if buffer size threshold is reached.

        Args:
            customer_id: Customer/tenant ID
            raw_logs: Raw log entries for logs_raw_mt table
            normalized_logs: Normalized log entries for logs_normalized_mt table

        Returns:
            True if logs were added successfully
        """
        buffer = self._get_or_create_buffer(customer_id)
        should_flush = False

        with buffer.lock:
            if raw_logs:
                buffer.raw_logs.extend(raw_logs)
                self.stats.total_logs_buffered += len(raw_logs)

            if normalized_logs:
                buffer.normalized_logs.extend(normalized_logs)
                # Don't double-count if both raw and normalized provided
                if not raw_logs:
                    self.stats.total_logs_buffered += len(normalized_logs)

            # Check if we need to flush by size
            total_buffered = len(buffer.raw_logs) + len(buffer.normalized_logs)
            if total_buffered >= self.config.max_buffer_size:
                should_flush = True
                self.stats.flush_by_size += 1

        if should_flush:
            await self._flush_customer_buffer(customer_id)

        return True

    async def add_log(
        self,
        customer_id: str,
        raw_log: Optional[Dict[str, Any]] = None,
        normalized_log: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a single log to the buffer (convenience method).
        """
        raw_logs = [raw_log] if raw_log else None
        normalized_logs = [normalized_log] if normalized_log else None
        return await self.add_logs(customer_id, raw_logs, normalized_logs)

    async def _flush_customer_buffer(self, customer_id: str) -> bool:
        """Flush a specific customer's buffer to ClickHouse"""
        buffer = self.buffers.get(customer_id)
        if not buffer:
            return True

        raw_to_flush = []
        normalized_to_flush = []

        with buffer.lock:
            if not buffer.raw_logs and not buffer.normalized_logs:
                return True  # Nothing to flush

            # Move logs out of buffer
            raw_to_flush = buffer.raw_logs.copy()
            normalized_to_flush = buffer.normalized_logs.copy()
            buffer.raw_logs.clear()
            buffer.normalized_logs.clear()
            buffer.last_flush_time = time.time()

        if not raw_to_flush and not normalized_to_flush:
            return True

        # Perform the flush
        start_time = time.time()
        success = False

        try:
            if self._flush_callback:
                success = await self._flush_callback(
                    customer_id,
                    raw_to_flush,
                    normalized_to_flush
                )
            else:
                # Default: use the built-in flush logic
                success = await self._default_flush(
                    customer_id,
                    raw_to_flush,
                    normalized_to_flush
                )

            flush_time_ms = (time.time() - start_time) * 1000
            total_flushed = len(raw_to_flush) + len(normalized_to_flush)

            if success:
                self.stats.total_logs_flushed += total_flushed
                self.stats.total_flushes += 1
                self.stats.total_flush_time_ms += flush_time_ms
                self.stats.update_averages()

                logger.info(
                    f"Buffer flush completed",
                    customer_id=customer_id,
                    raw_count=len(raw_to_flush),
                    normalized_count=len(normalized_to_flush),
                    flush_time_ms=f"{flush_time_ms:.2f}",
                    avg_per_log_ms=f"{flush_time_ms/total_flushed:.3f}" if total_flushed > 0 else "N/A"
                )
            else:
                self.stats.flush_errors += 1
                # Put logs back in buffer for retry
                with buffer.lock:
                    buffer.raw_logs = raw_to_flush + buffer.raw_logs
                    buffer.normalized_logs = normalized_to_flush + buffer.normalized_logs
                logger.error(f"Buffer flush failed for customer {customer_id}, logs returned to buffer")

            return success

        except Exception as e:
            self.stats.flush_errors += 1
            logger.error(f"Buffer flush error for customer {customer_id}: {e}")
            # Put logs back in buffer
            with buffer.lock:
                buffer.raw_logs = raw_to_flush + buffer.raw_logs
                buffer.normalized_logs = normalized_to_flush + buffer.normalized_logs
            return False

    async def _default_flush(
        self,
        customer_id: str,
        raw_logs: List[Dict[str, Any]],
        normalized_logs: List[Dict[str, Any]]
    ) -> bool:
        """Default flush implementation using log_processor"""
        try:
            from events.management.processors.log_processor import (
                process_dual_write_batch,
                process_normalized_write_only
            )

            if raw_logs and normalized_logs:
                # Dual write
                return await process_dual_write_batch(raw_logs, normalized_logs, customer_id)
            elif normalized_logs:
                # Normalized only
                return await process_normalized_write_only(normalized_logs, customer_id)
            elif raw_logs:
                # Raw only (less common)
                from events.management.processors.log_processor import process_log_batch_with_client
                from models import LogEntry
                log_entries = [LogEntry(**log) for log in raw_logs]
                return await process_log_batch_with_client(log_entries, customer_id)

            return True

        except Exception as e:
            logger.error(f"Default flush failed: {e}")
            return False

    async def flush_all(self) -> Dict[str, bool]:
        """Flush all customer buffers"""
        results = {}
        customer_ids = list(self.buffers.keys())

        for customer_id in customer_ids:
            results[customer_id] = await self._flush_customer_buffer(customer_id)

        return results

    async def start_periodic_flush(self):
        """Start the background periodic flush task"""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush_loop())
        logger.info("Periodic flush task started")

    async def stop_periodic_flush(self):
        """Stop the background periodic flush task and flush remaining logs"""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush_all()
        logger.info("Periodic flush task stopped, final flush completed")

    async def _periodic_flush_loop(self):
        """Background loop that flushes buffers periodically"""
        flush_interval_sec = self.config.flush_interval_ms / 1000.0

        while self._running:
            try:
                await asyncio.sleep(flush_interval_sec)

                current_time = time.time()
                customers_to_flush = []

                # Find buffers that need time-based flush
                for customer_id, buffer in self.buffers.items():
                    with buffer.lock:
                        has_data = buffer.raw_logs or buffer.normalized_logs
                        time_since_flush = current_time - buffer.last_flush_time
                        needs_flush = has_data and (time_since_flush * 1000) >= self.config.flush_interval_ms

                    if needs_flush:
                        customers_to_flush.append(customer_id)
                        self.stats.flush_by_time += 1

                # Flush identified buffers
                for customer_id in customers_to_flush:
                    await self._flush_customer_buffer(customer_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        self.stats.update_averages()

        # Calculate current buffer sizes
        current_buffered = 0
        buffer_counts = {}
        for customer_id, buffer in self.buffers.items():
            with buffer.lock:
                count = len(buffer.raw_logs) + len(buffer.normalized_logs)
                current_buffered += count
                if count > 0:
                    buffer_counts[customer_id] = count

        return {
            "config": {
                "max_buffer_size": self.config.max_buffer_size,
                "flush_interval_ms": self.config.flush_interval_ms
            },
            "stats": {
                "total_logs_buffered": self.stats.total_logs_buffered,
                "total_logs_flushed": self.stats.total_logs_flushed,
                "total_flushes": self.stats.total_flushes,
                "flush_by_size": self.stats.flush_by_size,
                "flush_by_time": self.stats.flush_by_time,
                "flush_errors": self.stats.flush_errors,
                "avg_batch_size": round(self.stats.avg_batch_size, 2),
                "avg_flush_time_ms": round(self.stats.avg_flush_time_ms, 2)
            },
            "current_state": {
                "logs_in_buffer": current_buffered,
                "active_customers": len(buffer_counts),
                "buffer_counts_by_customer": buffer_counts
            },
            "performance": {
                "estimated_throughput_per_sec": round(
                    self.stats.avg_batch_size / (self.stats.avg_flush_time_ms / 1000)
                    if self.stats.avg_flush_time_ms > 0 else 0,
                    2
                )
            }
        }


# Global singleton instance
_write_buffer_instance: Optional[WriteBufferService] = None


def get_write_buffer() -> WriteBufferService:
    """Get the global write buffer instance"""
    global _write_buffer_instance
    if _write_buffer_instance is None:
        _write_buffer_instance = WriteBufferService()
    return _write_buffer_instance


async def init_write_buffer(config: Optional[BufferConfig] = None) -> WriteBufferService:
    """Initialize and start the write buffer service"""
    global _write_buffer_instance
    _write_buffer_instance = WriteBufferService(config)
    await _write_buffer_instance.start_periodic_flush()
    return _write_buffer_instance


async def shutdown_write_buffer():
    """Gracefully shutdown the write buffer (flushes remaining logs)"""
    global _write_buffer_instance
    if _write_buffer_instance:
        await _write_buffer_instance.stop_periodic_flush()
        _write_buffer_instance = None
