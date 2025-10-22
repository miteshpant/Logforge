"""
Alert Processor

Main alert processing engine that orchestrates rule matching and alert instance creation.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from ..cache.alert_rule_cache import AlertRuleCache
from ..matchers.threshold_matcher import ThresholdMatcher
from ..matchers.pattern_matcher import PatternMatcher
from ..matchers.anomaly_matcher import AnomalyMatcher
from models import LogEntry

logger = logging.getLogger(__name__)

class AlertProcessor:
    """
    Main alert processing engine that coordinates rule matching and alert generation.

    This processor handles the core alert matching workflow:
    1. Load alert rules from Redis cache
    2. Match rules against incoming log batches
    3. Create alert instances for matches
    4. Handle cooldown periods to prevent spam
    """

    def __init__(self, cache_manager: Optional[AlertRuleCache] = None):
        """
        Initialize alert processor with matchers and cache.

        Args:
            cache_manager: Alert rule cache manager (optional, will create if not provided)
        """
        self.cache_manager = cache_manager or AlertRuleCache()

        # Initialize all available matchers
        self.matchers = {
            'threshold': ThresholdMatcher(),
            'pattern': PatternMatcher(),
            'anomaly': AnomalyMatcher(),
            # Add more matchers as needed
            'frequency': ThresholdMatcher(),  # Reuse threshold for frequency rules
            'absence': PatternMatcher(),      # Reuse pattern for absence detection
            'sequence': PatternMatcher()      # Reuse pattern for sequence detection
        }

        logger.info(f"AlertProcessor initialized with {len(self.matchers)} matchers: {list(self.matchers.keys())}")

    async def process_log_batch(self, event_data: Dict[str, Any]) -> bool:
        """
        Process log batch for alert matching.

        This is the main entry point called by the alert event subscriber
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
                logger.error("No customer_id in event data for alert processing")
                return False

            if not logs_data:
                logger.debug(f"No logs to process for customer {customer_id}")
                return True

            # Convert log data to LogEntry objects if needed
            logs = await self._prepare_logs(logs_data)

            logger.info(f"🚨 Processing {len(logs)} logs for alert matching (customer: {customer_id})")

            # Get alert rules for customer from cache
            rules = await self.cache_manager.get_customer_rules(customer_id)

            if not rules:
                logger.debug(f"No alert rules found for customer {customer_id}")
                return True

            logger.debug(f"Evaluating {len(rules)} alert rules for customer {customer_id}")

            # Process each rule against the logs
            matches_found = 0
            for rule in rules:
                try:
                    if await self._process_single_rule(rule, logs, customer_id):
                        matches_found += 1
                except Exception as e:
                    logger.error(f"Error processing rule {rule.get('id')}: {e}")
                    continue

            logger.info(f"🎯 Alert processing complete: {matches_found} rules matched for customer {customer_id}")
            return True

        except Exception as e:
            logger.error(f"Error in alert batch processing: {e}")
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

    async def _process_single_rule(self, rule: Dict[str, Any], logs: List[LogEntry], customer_id: str) -> bool:
        """
        Process a single alert rule against the log batch.

        Args:
            rule: Alert rule configuration
            logs: Log entries to match against
            customer_id: Customer/tenant ID

        Returns:
            bool: True if rule matched and alert was created
        """
        try:
            rule_id = rule.get('id')
            rule_type = rule.get('rule_type')
            rule_name = rule.get('name', 'Unknown Rule')

            # Check if rule is enabled
            if not rule.get('is_enabled', True):
                logger.debug(f"Skipping disabled rule {rule_id}")
                return False

            # Check cooldown period
            if await self._is_in_cooldown(rule_id):
                logger.debug(f"Rule {rule_id} is in cooldown period")
                return False

            # Get appropriate matcher for rule type
            matcher = self.matchers.get(rule_type)
            if not matcher:
                logger.error(f"No matcher available for rule type: {rule_type}")
                return False

            # Convert LogEntry objects to dictionaries for matching
            log_dicts = [self._logentry_to_dict(log) for log in logs]

            # Check if rule matches
            logger.debug(f"Evaluating rule {rule_id} ({rule_name}) of type {rule_type}")

            matches = await matcher.matches(log_dicts, rule)

            if matches:
                logger.info(f"🔥 Rule {rule_id} ({rule_name}) matched! Creating alert instance...")

                # Create alert instance
                success = await self._create_alert_instance(rule, log_dicts, matcher, customer_id)

                if success:
                    # Set cooldown period to prevent rapid firing
                    cooldown_minutes = rule.get('cooldown_minutes', 5)
                    await self.cache_manager.set_rule_cooldown(rule_id, cooldown_minutes)

                    logger.info(f"✅ Alert instance created for rule {rule_id}, cooldown set for {cooldown_minutes} minutes")
                    return True
                else:
                    logger.error(f"❌ Failed to create alert instance for rule {rule_id}")

            return False

        except Exception as e:
            logger.error(f"Error processing rule {rule.get('id')}: {e}")
            return False

    async def _is_in_cooldown(self, rule_id: str) -> bool:
        """
        Check if rule is currently in cooldown period.

        Args:
            rule_id: Rule ID to check

        Returns:
            bool: True if in cooldown, False otherwise
        """
        try:
            return await self.cache_manager.is_rule_in_cooldown(rule_id)
        except Exception as e:
            logger.error(f"Error checking cooldown for rule {rule_id}: {e}")
            return False  # Default to allowing rule execution

    async def _create_alert_instance(self, rule: Dict[str, Any], logs: List[Dict[str, Any]],
                                   matcher, customer_id: str) -> bool:
        """
        Create alert instance in database and update rule states.

        Args:
            rule: Alert rule that matched
            logs: Log entries that triggered the rule
            matcher: Matcher instance that detected the match
            customer_id: Customer/tenant ID

        Returns:
            bool: True if alert instance was created successfully
        """
        try:
            from dao.alert_dao import AlertDAO
            import uuid
            import json

            # Extract match data from the matcher
            match_data = await matcher.extract_match_data(logs, rule)

            # Log the enhanced condition evaluation for visibility
            condition_eval = None
            if "condition_evaluation" in match_data:
                condition_eval = match_data["condition_evaluation"]

            # Create alert instance directly in database
            alert_instance_id = str(uuid.uuid4())
            triggered_at = datetime.now(timezone.utc)

            alert_dao = AlertDAO()

            # Insert alert instance into database
            await alert_dao.save_alert_instance({
                'id': alert_instance_id,
                'rule_id': rule['id'],
                'status': 'triggered',
                'triggered_at': triggered_at,
                'trigger_data': json.dumps(match_data),
                'customer_id': customer_id
            })

            logger.info(f"📝 Alert instance {alert_instance_id} saved to database")

            # TODO: Add UI event publishing for real-time notifications when UI event system is ready
            # For now, just log the success

            logger.info(f"✅ Alert instance {alert_instance_id} created for rule {rule['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to create alert instance for rule {rule.get('id')}: {e}")
            return False

    def _logentry_to_dict(self, log_entry: LogEntry) -> Dict[str, Any]:
        """
        Convert LogEntry object to dictionary for matcher processing.

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

    async def handle_rule_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Handle alert rule CRUD events for cache updates.

        Args:
            event_type: Type of rule event (alert.rule.created, updated, etc.)
            event_data: Event data containing rule information

        Returns:
            bool: True if event was handled successfully
        """
        try:
            logger.debug(f"🔧 Handling rule event: {event_type}")

            # Delegate to cache manager for cache updates
            success = await self.cache_manager.handle_rule_event(event_type, event_data)

            if success:
                logger.debug(f"✅ Rule event {event_type} handled successfully")
            else:
                logger.error(f"❌ Failed to handle rule event {event_type}")

            return success

        except Exception as e:
            logger.error(f"Error handling rule event {event_type}: {e}")
            return False

    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get alert processing statistics.

        Returns:
            Dictionary with processing statistics
        """
        try:
            cache_stats = await self.cache_manager.get_cache_stats()

            return {
                "alert_processor": {
                    "matchers_available": list(self.matchers.keys()),
                    "matchers_count": len(self.matchers),
                    "cache_stats": cache_stats
                }
            }

        except Exception as e:
            logger.error(f"Error getting processing stats: {e}")
            return {"error": str(e)}
