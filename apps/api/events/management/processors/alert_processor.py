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
from constants.alert_constants import (
    DEFAULT_COOLDOWN_MINUTES, CRITICAL_SECURITY_COOLDOWN_MINUTES,
    SYSTEM_HEALTH_COOLDOWN_MINUTES, BUSINESS_METRICS_COOLDOWN_MINUTES,
    INFORMATIONAL_COOLDOWN_MINUTES, AlertSeverity
)

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
            cooldown_minutes = self._get_smart_cooldown(rule)
            if await self._is_in_cooldown(rule_id, customer_id, cooldown_minutes):
                logger.debug(f"Rule {rule_id} is in cooldown period")
                await self._update_rule_state(rule_id, customer_id, triggered=False, evaluation_success=True)
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
                    # Update rule state to track the successful trigger
                    await self._update_rule_state(rule_id, customer_id, triggered=True, evaluation_success=True)

                    logger.info(f"✅ Alert instance created for rule {rule_id}, cooldown active for {cooldown_minutes} minutes")
                    return True
                else:
                    logger.error(f"❌ Failed to create alert instance for rule {rule_id}")
                    await self._update_rule_state(rule_id, customer_id, triggered=False, evaluation_success=False)

            else:
                # Rule was evaluated but didn't match
                await self._update_rule_state(rule_id, customer_id, triggered=False, evaluation_success=True)

            return False

        except Exception as e:
            logger.error(f"Error processing rule {rule.get('id')}: {e}")
            return False

    async def _is_in_cooldown(self, rule_id: str, customer_id: str, cooldown_minutes: int) -> bool:
        """
        Check if rule is currently in cooldown period.

        Args:
            rule_id: Rule ID to check
            customer_id: Customer/tenant ID
            cooldown_minutes: Cooldown period in minutes

        Returns:
            bool: True if in cooldown, False otherwise
        """
        try:
            from dao.alert_dao import AlertDAO
            alert_dao = AlertDAO()
            return await alert_dao.is_rule_in_cooldown(rule_id, customer_id, cooldown_minutes)
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

            # TODO: Re-enable UI event publishing after fixing circular dependency
            await self._publish_ui_alert_event(
                alert_instance_id=alert_instance_id,
                rule=rule,
                match_data=match_data,
                customer_id=customer_id
            )
            logger.info(f"🔔 Alert instance {alert_instance_id} ready for UI notification")

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

    def _get_smart_cooldown(self, rule: Dict[str, Any]) -> int:
        """
        Determine appropriate cooldown period based on rule properties.

        Args:
            rule: Alert rule configuration

        Returns:
            int: Cooldown period in minutes
        """
        try:
            # Check if rule has explicit cooldown configured
            if 'cooldown_minutes' in rule:
                return max(1, rule['cooldown_minutes'])  # Minimum 1 minute

            # Smart cooldown based on severity
            severity = rule.get('severity', AlertSeverity.MEDIUM).lower()

            if severity == AlertSeverity.CRITICAL:
                return CRITICAL_SECURITY_COOLDOWN_MINUTES
            elif severity == AlertSeverity.HIGH:
                return SYSTEM_HEALTH_COOLDOWN_MINUTES
            elif severity == AlertSeverity.MEDIUM:
                return DEFAULT_COOLDOWN_MINUTES
            elif severity == AlertSeverity.LOW:
                return INFORMATIONAL_COOLDOWN_MINUTES
            else:
                # Additional logic based on rule type for fine-tuning
                rule_type = rule.get('rule_type', '')

                if rule_type in ['pattern', 'frequency']:
                    # Pattern and frequency rules tend to be more critical
                    return SYSTEM_HEALTH_COOLDOWN_MINUTES
                elif rule_type in ['anomaly', 'sequence']:
                    # Complex analysis rules might need longer cooldown
                    return BUSINESS_METRICS_COOLDOWN_MINUTES
                else:
                    return DEFAULT_COOLDOWN_MINUTES

        except Exception as e:
            logger.error(f"Error determining cooldown for rule {rule.get('id')}: {e}")
            return DEFAULT_COOLDOWN_MINUTES

    async def _update_rule_state(self, rule_id: str, customer_id: str, triggered: bool, evaluation_success: bool):
        """
        Update rule state tracking in database.

        Args:
            rule_id: Rule ID to update
            customer_id: Customer/tenant ID
            triggered: Whether the rule triggered an alert
            evaluation_success: Whether the evaluation completed successfully
        """
        try:
            from dao.alert_dao import AlertDAO
            import json

            alert_dao = AlertDAO()

            # Get current state to increment counters
            current_state = await alert_dao.get_rule_state(rule_id, customer_id)

            now = datetime.now(timezone.utc)

            # Build state update
            state_update = {
                'rule_id': rule_id,
                'customer_id': customer_id,
                'last_evaluation': now,
                'evaluation_count': (current_state.get('evaluation_count', 0) if current_state else 0) + 1,
                'consecutive_failures': 0 if evaluation_success else (current_state.get('consecutive_failures', 0) if current_state else 0) + 1,
                'updated_at': now
            }

            if triggered:
                state_update.update({
                    'last_trigger': now,
                    'trigger_count': (current_state.get('trigger_count', 0) if current_state else 0) + 1
                })

            # Add any additional state data
            state_data = current_state.get('state_data', {}) if current_state else {}
            state_data.update({
                'last_evaluation_result': 'triggered' if triggered else ('evaluated' if evaluation_success else 'failed'),
                'last_updated': now.isoformat()
            })

            state_update['state_data'] = json.dumps(state_data)

            # Set created_at for new states
            if not current_state:
                state_update['created_at'] = now

            # Save to database
            await alert_dao.update_rule_state(state_update)

            logger.debug(f"Rule state updated for {rule_id}: triggered={triggered}, eval_success={evaluation_success}")

        except Exception as e:
            logger.error(f"Failed to update rule state for {rule_id}: {e}")
            # Don't fail the main processing flow due to state tracking errors

    async def _publish_ui_alert_event(
        self,
        alert_instance_id: str,
        rule: Dict[str, Any],
        match_data: Dict[str, Any],
        customer_id: str
    ):
        """
        Publish UI event for real-time alert notifications.

        Args:
            alert_instance_id: ID of the created alert instance
            rule: Alert rule that triggered
            match_data: Data about the match from the matcher
            customer_id: Customer/tenant ID
        """
        try:
            logger.info(f"🚀 Starting UI alert event publishing for alert {alert_instance_id}")

            # Import here to avoid circular dependency
            from ...publishers.ui_publisher import UIEventPublisher
            import sys
            import os

            # Add the API root to the path to import dependencies
            api_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            if api_root not in sys.path:
                sys.path.append(api_root)

            import dependencies

            # Use getter function for more reliable access to the publisher manager
            publisher_manager = dependencies.get_event_publisher_manager()

            if not publisher_manager:
                # Try direct attribute access as fallback
                publisher_manager = dependencies.event_publisher_manager

            if not publisher_manager:
                logger.warning(
                    "⚠️ Event publisher manager not available - UI alert will not be streamed",
                    alert_id=alert_instance_id,
                    customer_id=customer_id
                )
                return

            # Check if publisher manager is started
            if not getattr(publisher_manager, 'is_started', False):
                logger.warning(
                    "⚠️ Event publisher manager not started - UI alert will not be streamed",
                    alert_id=alert_instance_id,
                    customer_id=customer_id
                )
                return

            logger.info(
                f"✅ Event publisher manager available and started, creating UI publisher",
                alert_id=alert_instance_id,
                publisher_started=publisher_manager.is_started
            )
            ui_publisher = UIEventPublisher(publisher_manager)

            # Prepare alert data for UI event
            alert_data = {
                "id": alert_instance_id,
                "severity": rule.get('severity', 'medium'),
                "trigger_data": match_data
            }

            # Prepare trigger context
            trigger_context = {
                "matched_logs_count": match_data.get("matched_logs_count", 0),
                "time_window": match_data.get("time_window", {}),
                "condition_evaluation": match_data.get("condition_evaluation", {})
            }

            # Publish UI alert triggered event
            logger.info(
                "📤 Publishing UI alert triggered event to Kafka",
                alert_id=alert_instance_id,
                customer_id=customer_id,
                rule_id=rule.get('id'),
                rule_name=rule.get('name'),
                severity=rule.get('severity')
            )

            success = await ui_publisher.publish_alert_triggered(
                customer_id=customer_id,
                alert_data=alert_data,
                rule_data=rule,
                trigger_context=trigger_context,
                correlation_id=None  # Could add correlation tracking here
            )

            if success:
                logger.info(
                    f"🔔 UI alert event published successfully for alert {alert_instance_id}",
                    customer_id=customer_id,
                    rule_id=rule.get('id'),
                    topic="ui-realtime-events"
                )
            else:
                logger.warning(
                    f"⚠️ Failed to publish UI alert event for alert {alert_instance_id}",
                    customer_id=customer_id,
                    rule_id=rule.get('id')
                )

        except Exception as e:
            logger.error(
                f"Error publishing UI alert event for alert {alert_instance_id}: {e}",
                alert_id=alert_instance_id,
                customer_id=customer_id,
                error=str(e),
                exc_info=True
            )
            # Don't fail the main alert creation flow due to UI event publishing errors
