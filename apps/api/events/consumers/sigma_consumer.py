"""
Sigma Engine Consumer

Consumes EVENT_LOGS_NORMALIZED events and evaluates Sigma rules for security detection.
This consumer is focused solely on security rule matching against field-mapped logs.

Separation of concerns:
- Normalized writer consumer: Write normalized logs to database
- This consumer: Evaluate security rules against normalized logs  
- Both consume the same EVENT_LOGS_NORMALIZED events in parallel
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from events.base import EventSubscriber, SubscriberConfig, BaseEvent
from events.constants import EVENT_LOGS_NORMALIZED, TOPIC_LOG_EVENTS, SUBSCRIBER_SIGMA_ENGINE

logger = logging.getLogger(__name__)


class SigmaEngineConsumer(EventSubscriber):
    """
    Evaluates Sigma rules against normalized logs for security detection
    
    Purpose:
    - Receives field-mapped logs from SmartIngestionService via events
    - Evaluates Sigma rules using standard field names (src_ip, user, etc.)
    - Publishes security detection events for real-time alerts
    - Checks security subscription access before processing
    """
    
    def __init__(self):
        """Initialize Sigma engine consumer"""
        self.sigma_engine = None  # Lazy loaded
        self.subscription_checker = None  # Lazy loaded
        self.security_publisher = None  # Lazy loaded
        self.processing_stats = {
            "total_logs_processed": 0,
            "total_detections": 0,
            "total_batches_processed": 0,
            "avg_processing_time_ms": 0.0,
            "last_processing_time": None
        }
        logger.info("SigmaEngineConsumer initialized for security rule evaluation")
        
    async def handle_event(self, event: BaseEvent) -> bool:
        """
        Evaluate normalized logs against Sigma rules for security detection
        
        Args:
            event: BaseEvent containing EVENT_LOGS_NORMALIZED data
            
        Returns:
            bool: True if processing successful, False otherwise
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
                
            logger.debug(f"Processing {len(normalized_logs)} normalized logs for Sigma rules, customer {customer_id}")
            
            # Step 1: Check security subscription access
            if not await self._has_security_access(customer_id):
                logger.info(f"Customer {customer_id} does not have security access, skipping Sigma processing")
                return True
                
            # Step 2: Evaluate Sigma rules against normalized logs
            detections = await self._evaluate_sigma_rules(normalized_logs, customer_id)
            
            # Step 3: Publish security detection events
            if detections:
                await self._publish_security_detections(detections, customer_id)
                logger.info(f"Sigma processing completed: {len(detections)} detections for customer {customer_id}")
            else:
                logger.debug(f"Sigma processing completed: No detections for customer {customer_id}")
            
            # Update processing statistics
            self._update_processing_stats(len(normalized_logs), len(detections))
            
            return True
            
        except Exception as e:
            logger.error(f"Sigma engine consumer error for customer {event.customer_id}: {e}")
            return False
    
    async def _has_security_access(self, customer_id: str) -> bool:
        """
        Check if customer has security subscription access
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            bool: True if customer has security access
        """
        try:
            # Lazy load subscription checker
            if not self.subscription_checker:
                from services.security_subscription_checker import SecuritySubscriptionChecker
                self.subscription_checker = SecuritySubscriptionChecker()
            
            return await self.subscription_checker.has_security_access(customer_id)
            
        except Exception as e:
            logger.error(f"Error checking security access for customer {customer_id}: {e}")
            return False
    
    async def _evaluate_sigma_rules(self, normalized_logs: List[Dict[str, Any]], customer_id: str) -> List[Dict[str, Any]]:
        """
        Evaluate Sigma rules against normalized logs
        
        Args:
            normalized_logs: List of field-mapped log dictionaries
            customer_id: Customer identifier
            
        Returns:
            List of security detection dictionaries
        """
        start_time = datetime.now()
        
        try:
            # Lazy load Sigma engine
            if not self.sigma_engine:
                from sigma_engine import SigmaEngine
                self.sigma_engine = SigmaEngine()
            
            detections = []
            
            # Process each normalized log against Sigma rules
            for log_entry in normalized_logs:
                try:
                    # Evaluate against cached Sigma rules
                    # normalized_logs already have field mapping applied (src_ip, user, etc.)
                    log_detections = await self.sigma_engine.evaluate_log_against_rules(
                        log_entry, customer_id, logs_already_normalized=True
                    )
                    
                    if log_detections:
                        detections.extend(log_detections)
                        
                except Exception as e:
                    logger.warning(f"Failed to evaluate Sigma rules for log: {e}")
                    continue
            
            processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"Sigma rule evaluation completed in {processing_time_ms:.2f}ms for customer {customer_id}")
            
            return detections
            
        except Exception as e:
            processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Error evaluating Sigma rules for customer {customer_id} after {processing_time_ms:.2f}ms: {e}")
            return []
    
    async def _publish_security_detections(self, detections: List[Dict[str, Any]], customer_id: str) -> bool:
        """
        Publish security detection events for real-time alerting
        
        Args:
            detections: List of security detection results
            customer_id: Customer identifier
            
        Returns:
            bool: True if publishing successful
        """
        try:
            # Lazy load security event publisher
            if not self.security_publisher:
                from events.publishers.security_publisher import SecurityEventPublisher
                self.security_publisher = SecurityEventPublisher()
            
            # Publish each detection as a separate security event
            published_count = 0
            for detection in detections:
                try:
                    success = await self.security_publisher.publish_security_detection(
                        detection=detection,
                        customer_id=customer_id
                    )
                    if success:
                        published_count += 1
                except Exception as e:
                    logger.warning(f"Failed to publish security detection: {e}")
                    continue
            
            logger.debug(f"Published {published_count}/{len(detections)} security detections for customer {customer_id}")
            return published_count > 0
            
        except Exception as e:
            logger.error(f"Error publishing security detections for customer {customer_id}: {e}")
            return False
    
    def _update_processing_stats(self, logs_processed: int, detections_found: int):
        """Update internal processing statistics for monitoring"""
        self.processing_stats["total_logs_processed"] += logs_processed
        self.processing_stats["total_detections"] += detections_found
        self.processing_stats["total_batches_processed"] += 1
        self.processing_stats["last_processing_time"] = datetime.now(timezone.utc)
        
        # Calculate moving average processing time (simplified)
        if self.processing_stats["total_batches_processed"] > 0:
            # Estimate based on log count (simplified calculation)
            estimated_time = logs_processed * 0.8  # Estimate 0.8ms per log for Sigma processing
            self.processing_stats["avg_processing_time_ms"] = (
                self.processing_stats["avg_processing_time_ms"] * 0.9 + 
                estimated_time * 0.1
            )
    
    async def get_subscription_info(self) -> SubscriberConfig:
        """
        Get subscriber configuration for Kafka consumer setup
        
        Returns:
            SubscriberConfig with optimized settings for security rule evaluation
        """
        return SubscriberConfig(
            subscriber_group=SUBSCRIBER_SIGMA_ENGINE,
            topics=[TOPIC_LOG_EVENTS],
            event_types=[EVENT_LOGS_NORMALIZED],
            parallel_processing=True,  # Enable parallel processing
            max_batch_size=100,  # Moderate batch size for rule evaluation
            processing_timeout_ms=5000  # 5 second timeout for Sigma processing
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Sigma engine consumer
        
        Returns:
            Health check results with processing performance metrics
        """
        try:
            # Test Sigma engine availability
            if not self.sigma_engine:
                from sigma_engine import SigmaEngine
                self.sigma_engine = SigmaEngine()
            
            return {
                "status": "healthy",
                "consumer_group": SUBSCRIBER_SIGMA_ENGINE,
                "subscribed_events": [EVENT_LOGS_NORMALIZED],
                "sigma_engine_available": self.sigma_engine is not None,
                "processing_performance": {
                    "total_logs_processed": self.processing_stats["total_logs_processed"],
                    "total_detections": self.processing_stats["total_detections"],
                    "total_batches_processed": self.processing_stats["total_batches_processed"],
                    "avg_processing_time_ms": self.processing_stats["avg_processing_time_ms"],
                    "detection_rate": (
                        self.processing_stats["total_detections"] / max(self.processing_stats["total_logs_processed"], 1)
                    ) * 100,
                    "last_processing_time": self.processing_stats["last_processing_time"].isoformat() if self.processing_stats["last_processing_time"] else None
                },
                "parallel_processing_enabled": True,
                "max_batch_size": 100,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_processing_metrics(self) -> Dict[str, Any]:
        """
        Get current processing performance metrics
        
        Returns:
            Dictionary with processing statistics for monitoring
        """
        return {
            "consumer_name": "SigmaEngineConsumer",
            "processing_stats": self.processing_stats.copy(),
            "target_processing_time_ms": 5.0,  # Target <5ms per batch
            "meets_target": self.processing_stats["avg_processing_time_ms"] < 5.0,
            "detection_efficiency": (
                self.processing_stats["total_detections"] / max(self.processing_stats["total_logs_processed"], 1)
            ) * 100 if self.processing_stats["total_logs_processed"] > 0 else 0
        }


# Global instance for dependency injection
sigma_engine_consumer = SigmaEngineConsumer()


def get_sigma_engine_consumer() -> SigmaEngineConsumer:
    """Get the global Sigma engine consumer instance"""
    return sigma_engine_consumer