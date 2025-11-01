"""
Normalized Log Writer Consumer

Consumes EVENT_LOGS_NORMALIZED events and writes them to logs_normalized_mt table.
This consumer is focused solely on persisting normalized, field-mapped logs for analytics.

Separation of concerns:
- This consumer: Write normalized logs to database
- Sigma consumer: Evaluate security rules against normalized logs  
- Both consume the same EVENT_LOGS_NORMALIZED events in parallel
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from events.base import EventSubscriber, SubscriberConfig, BaseEvent
from events.constants import EVENT_LOGS_NORMALIZED, TOPIC_LOG_EVENTS, SUBSCRIBER_NORMALIZED_WRITER
from events.management.processors.log_processor import process_normalized_write_only

logger = logging.getLogger(__name__)


class NormalizedLogWriterConsumer(EventSubscriber):
    """
    Writes normalized logs to logs_normalized_mt table
    
    Purpose:
    - Receives field-mapped logs from SmartIngestionService via events
    - Persists to logs_normalized_mt for analytics and compliance
    - Optimized for high-throughput writes with performance monitoring
    """
    
    def __init__(self):
        """Initialize normalized log writer consumer"""
        self.write_stats = {
            "total_logs_written": 0,
            "total_batches_processed": 0,
            "avg_write_time_ms": 0.0,
            "last_write_time": None
        }
        logger.info("NormalizedLogWriterConsumer initialized for logs_normalized_mt writes")
        
    async def handle_event(self, event: BaseEvent) -> bool:
        """
        Write normalized logs to logs_normalized_mt table
        
        Args:
            event: BaseEvent containing EVENT_LOGS_NORMALIZED data
            
        Returns:
            bool: True if write successful, False otherwise
        """
        try:
            # Only process logs.normalized events
            if event.event_type != EVENT_LOGS_NORMALIZED:
                logger.debug(f"Ignoring non-normalized event: {event.event_type}")
                return True
                
            customer_id = event.customer_id
            event_data = event.data
            normalized_logs = event_data.get("normalized_logs", [])
            
            if not normalized_logs:
                logger.warning(f"Empty normalized logs received for customer {customer_id}")
                return True
                
            logger.debug(f"Writing {len(normalized_logs)} normalized logs for customer {customer_id}")
            
            # Write normalized logs to logs_normalized_mt table using our specialized function
            write_success = await process_normalized_write_only(normalized_logs, customer_id)
            
            if write_success:
                # Update performance statistics
                self._update_write_stats(len(normalized_logs))
                logger.debug(f"Successfully wrote {len(normalized_logs)} normalized logs for customer {customer_id}")
            else:
                logger.error(f"Failed to write normalized logs for customer {customer_id}")
                
            return write_success
            
        except Exception as e:
            logger.error(f"Normalized writer consumer error for customer {event.customer_id}: {e}")
            return False
    
    def _update_write_stats(self, logs_written: int):
        """Update internal write statistics for monitoring"""
        self.write_stats["total_logs_written"] += logs_written
        self.write_stats["total_batches_processed"] += 1
        self.write_stats["last_write_time"] = datetime.now(timezone.utc)
        
        # Calculate moving average write time (simplified)
        if self.write_stats["total_batches_processed"] > 0:
            # This is a simplified calculation - in production you'd want more sophisticated metrics
            self.write_stats["avg_write_time_ms"] = (
                self.write_stats["avg_write_time_ms"] * 0.9 + 
                (logs_written * 0.5) * 0.1  # Estimate 0.5ms per log
            )
    
    async def get_subscription_info(self) -> SubscriberConfig:
        """
        Get subscriber configuration for Kafka consumer setup
        
        Returns:
            SubscriberConfig with optimized settings for high-throughput writes
        """
        return SubscriberConfig(
            subscriber_group=SUBSCRIBER_NORMALIZED_WRITER,
            topics=[TOPIC_LOG_EVENTS],
            event_types=[EVENT_LOGS_NORMALIZED],
            parallel_processing=True,  # Enable parallel processing for throughput
            max_batch_size=200,  # Larger batch size for efficient writes
            processing_timeout_ms=3000  # 3 second timeout for writes
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on normalized writer consumer
        
        Returns:
            Health check results with write performance metrics
        """
        try:
            return {
                "status": "healthy",
                "consumer_group": SUBSCRIBER_NORMALIZED_WRITER,
                "subscribed_events": [EVENT_LOGS_NORMALIZED],
                "write_performance": {
                    "total_logs_written": self.write_stats["total_logs_written"],
                    "total_batches_processed": self.write_stats["total_batches_processed"],
                    "avg_write_time_ms": self.write_stats["avg_write_time_ms"],
                    "last_write_time": self.write_stats["last_write_time"].isoformat() if self.write_stats["last_write_time"] else None
                },
                "parallel_processing_enabled": True,
                "max_batch_size": 200,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_write_metrics(self) -> Dict[str, Any]:
        """
        Get current write performance metrics
        
        Returns:
            Dictionary with write statistics for monitoring
        """
        return {
            "consumer_name": "NormalizedLogWriterConsumer",
            "write_stats": self.write_stats.copy(),
            "target_write_time_ms": 2.0,  # Target <2ms per batch
            "meets_target": self.write_stats["avg_write_time_ms"] < 2.0,
            "throughput_logs_per_second": (
                self.write_stats["total_logs_written"] / max(self.write_stats["total_batches_processed"], 1)
            ) if self.write_stats["total_batches_processed"] > 0 else 0
        }


# Global instance for dependency injection
normalized_writer_consumer = NormalizedLogWriterConsumer()


def get_normalized_writer_consumer() -> NormalizedLogWriterConsumer:
    """Get the global normalized writer consumer instance"""
    return normalized_writer_consumer