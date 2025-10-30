"""
Sigma Rule Processor

Main sigma rule processing engine that orchestrates rule matching and security event creation.
Mirrors the alert processor pattern for sigma rule evaluation.
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid

from ..cache.sigma_rule_cache import SigmaRuleCache
from models import LogEntry
from sigma_engine import SigmaRuleEngine

logger = logging.getLogger(__name__)


class SigmaProcessor:
    """
    Main sigma rule processing engine that coordinates rule matching and security event generation.

    This processor handles the core sigma rule matching workflow:
    1. Check if customer has security analytics subscription
    2. Load sigma rules from Redis cache (default + customer-specific)
    3. Match rules against incoming log batches
    4. Create security events for matches
    5. Publish events for billing and streaming
    """

    def __init__(self, cache_manager: Optional[SigmaRuleCache] = None):
        """
        Initialize sigma processor with cache and engine.

        Args:
            cache_manager: Sigma rule cache manager (optional, will create if not provided)
        """
        self.cache_manager = cache_manager or SigmaRuleCache()
        self.sigma_engine = SigmaRuleEngine()
        
        logger.info("SigmaProcessor initialized with sigma rule engine")

    async def process_log_batch(self, event_data: Dict[str, Any]) -> bool:
        """
        Process log batch for sigma rule matching.

        This is the main entry point called by the security event subscriber
        when a logs.batch.ingested event is received.

        Args:
            event_data: Log ingestion event data containing logs and metadata

        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            customer_id = event_data.get('customer_id')
            logs_data = event_data.get('logs', [])

            if not customer_id:
                logger.error("No customer_id in event data for sigma processing")
                return False

            if not logs_data:
                logger.debug(f"No logs to process for sigma matching (customer: {customer_id})")
                return True

            # Check if customer has security analytics access
            has_access = await self._check_security_access(customer_id)
            if not has_access:
                logger.debug(f"Customer {customer_id} does not have security analytics access - skipping sigma processing")
                return True

            # Convert log data to LogEntry objects if needed
            logs = await self._prepare_logs(logs_data)

            logger.info(f"🔍 Processing {len(logs)} logs for sigma rule matching (customer: {customer_id})")

            # Get sigma rules for customer from cache (default + customer-specific)
            rules = await self.cache_manager.get_customer_rules(customer_id, include_defaults=True)

            if not rules:
                logger.debug(f"No sigma rules found for customer {customer_id}")
                return True

            logger.debug(f"Evaluating {len(rules)} sigma rules for customer {customer_id}")

            # Convert logs to dict format for sigma engine
            log_dicts = [self._logentry_to_dict(log) for log in logs]

            # Process rules using sigma engine
            matches = await self.sigma_engine.evaluate_logs_against_rules(log_dicts, rules, customer_id)

            # Create security events for each match
            events_created = 0
            for match in matches:
                try:
                    if await self._create_security_event(match, customer_id):
                        events_created += 1
                except Exception as e:
                    logger.error(f"Error creating security event for match {match.rule_id}: {e}")
                    continue

            logger.info(f"🛡️ Sigma processing complete: {len(matches)} matches found, {events_created} security events created for customer {customer_id}")
            return True

        except Exception as e:
            logger.error(f"Error in sigma batch processing: {e}")
            return False

    async def _check_security_access(self, customer_id: str) -> bool:
        """Check if customer has security analytics access"""
        try:
            from security_subscription_checker import security_subscription_checker
            return await security_subscription_checker.has_security_analytics_access(customer_id)
        except Exception as e:
            logger.error(f"Error checking security access for {customer_id}: {e}")
            return False

    async def _prepare_logs(self, logs_data: List[Any]) -> List[LogEntry]:
        """
        Convert logs data to LogEntry objects.

        Args:
            logs_data: Raw log data from event

        Returns:
            List of LogEntry objects
        """
        logs = []

        for log_data in logs_data:
            try:
                if isinstance(log_data, dict):
                    # Convert dict to LogEntry
                    log_entry = LogEntry(**log_data)
                    logs.append(log_entry)
                elif isinstance(log_data, LogEntry):
                    logs.append(log_data)
                else:
                    logger.warning(f"Unknown log data type: {type(log_data)}")
            except Exception as e:
                logger.error(f"Failed to convert log data to LogEntry: {e}")
                continue

        return logs

    def _logentry_to_dict(self, log_entry: LogEntry) -> Dict[str, Any]:
        """
        Convert LogEntry object to dictionary for sigma engine processing.

        Args:
            log_entry: LogEntry object

        Returns:
            Dictionary representation of the log entry
        """
        try:
            if hasattr(log_entry, 'model_dump'):
                return log_entry.model_dump(mode='json')
            elif hasattr(log_entry, '__dict__'):
                return log_entry.__dict__
            else:
                logger.warning(f"Unknown LogEntry type: {type(log_entry)}")
                return {}
        except Exception as e:
            logger.error(f"Error converting LogEntry to dict: {e}")
            return {}

    async def _create_security_event(self, match, customer_id: str) -> bool:
        """
        Create security event in database for billing and tracking.

        Args:
            match: SigmaMatch object containing detection details
            customer_id: Customer/tenant ID

        Returns:
            bool: True if security event was created successfully
        """
        try:
            # Create security event ID
            event_id = str(uuid.uuid4())
            
            # Prepare event data
            event_data = {
                'id': event_id,
                'customer_id': customer_id,
                'rule_id': match.rule_id,
                'event_type': 'sigma_detection',
                'severity': match.severity.value if hasattr(match.severity, 'value') else str(match.severity),
                'title': f"Security Detection: {match.rule_title}",
                'description': f"Sigma rule {match.rule_id} triggered by log activity",
                'attack_techniques': json.dumps(match.attack_techniques),
                'kill_chain_phases': json.dumps(match.kill_chain_phases),
                'artifact_data': json.dumps(match.log_entry),
                'matched_fields': json.dumps(match.matched_fields),
                'status': 'open',
                'created_at': match.timestamp,
                'updated_at': match.timestamp
            }

            # Insert into security_events_mt table for billing
            await self._insert_security_event(event_data)

            # Publish security event for streaming API
            await self._publish_security_event(event_data)

            logger.info(f"📝 Security event {event_id} created for rule {match.rule_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create security event for rule {match.rule_id}: {e}")
            return False

    async def _insert_security_event(self, event_data: Dict[str, Any]) -> bool:
        """Insert security event into database"""
        try:
            from database_layer import DatabaseLayer
            import os
            service_key = os.getenv('SIGMA_PROCESSOR_KEY', 'sigma-processor-service-key')
            database = DatabaseLayer("SigmaProcessor", service_key)

            await database.execute_update(
                f"""
                INSERT INTO security_events_mt (
                    id, customer_id, rule_id, event_type, severity, title, description,
                    attack_techniques, kill_chain_phases, artifact_data, matched_fields,
                    status, created_at, updated_at
                ) VALUES (
                    '{event_data["id"]}',
                    '{event_data["customer_id"]}',
                    '{event_data["rule_id"]}',
                    '{event_data["event_type"]}',
                    '{event_data["severity"]}',
                    '{event_data["title"].replace("'", "''")}',
                    '{event_data["description"].replace("'", "''")}',
                    '{event_data["attack_techniques"]}',
                    '{event_data["kill_chain_phases"]}',
                    '{event_data["artifact_data"]}',
                    '{event_data["matched_fields"]}',
                    '{event_data["status"]}',
                    '{event_data["created_at"].isoformat()}',
                    '{event_data["updated_at"].isoformat()}'
                )
                """
            )
            return True

        except Exception as e:
            logger.error(f"Error inserting security event {event_data['id']}: {e}")
            return False

    async def _publish_security_event(self, event_data: Dict[str, Any]) -> bool:
        """Publish security event for streaming API"""
        try:
            # Import here to avoid circular dependency
            from events.publishers.security_publisher import SecurityEventPublisher
            import sys
            import os

            # Add the API root to the path to import dependencies
            api_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            if api_root not in sys.path:
                sys.path.append(api_root)

            import dependencies

            # Use global event publisher manager
            if not dependencies.event_publisher_manager:
                logger.warning("Event publisher manager not available for security event publishing")
                return False

            security_publisher = SecurityEventPublisher(dependencies.event_publisher_manager)

            # Publish security detection event
            success = await security_publisher.publish_security_detection_triggered(
                customer_id=event_data["customer_id"],
                detection_data=event_data
            )

            if success:
                logger.info(f"🔔 Security event published for streaming API: {event_data['id']}")
            else:
                logger.warning(f"⚠️ Failed to publish security event for streaming: {event_data['id']}")

            return success

        except Exception as e:
            logger.error(f"Error publishing security event {event_data['id']}: {e}")
            return False

    async def handle_rule_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Handle sigma rule CRUD events for cache updates.

        Args:
            event_type: Type of rule event (security.sigma.rule.created, updated, etc.)
            event_data: Event data containing rule information

        Returns:
            bool: True if event was handled successfully
        """
        try:
            logger.debug(f"🔧 Handling sigma rule event: {event_type}")

            # Delegate to cache manager for cache updates
            success = await self.cache_manager.handle_rule_event(event_type, event_data)

            if success:
                logger.debug(f"✅ Sigma rule event {event_type} handled successfully")
            else:
                logger.error(f"❌ Failed to handle sigma rule event {event_type}")

            return success

        except Exception as e:
            logger.error(f"Error handling sigma rule event {event_type}: {e}")
            return False

    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get sigma processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        try:
            cache_stats = await self.cache_manager.get_cache_stats()

            return {
                "sigma_processor": {
                    "engine_available": self.sigma_engine is not None,
                    "cache_stats": cache_stats
                }
            }

        except Exception as e:
            logger.error(f"Error getting sigma processing stats: {e}")
            return {"error": str(e)}


# Singleton instance for use across the application
sigma_processor = SigmaProcessor()