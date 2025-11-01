"""
M3 Alert Engine - Rule-Based Alerting System
Comprehensive alerting with multi-channel notifications and enterprise integration
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Literal
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import re
from pydantic import BaseModel, Field

# Import query engine for alert rule evaluation
from query_engine import AdvancedQueryEngine, AdvancedQueryRequest, QueryFilter, QueryAggregation, AggregationType, QueryOperator

logger = structlog.get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status states"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class NotificationChannel(str, Enum):
    """Notification channel types"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    JIRA = "jira"
    TEAMS = "teams"
    DISCORD = "discord"


class AlertRuleType(str, Enum):
    """Alert rule types"""
    THRESHOLD = "threshold"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    FREQUENCY = "frequency"
    ABSENCE = "absence"
    SEQUENCE = "sequence"


class ThresholdOperator(str, Enum):
    """Threshold comparison operators"""
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NE = "ne"


@dataclass
class NotificationChannelConfig:
    """Notification channel configuration"""
    channel_id: str
    type: NotificationChannel
    name: str
    enabled: bool = True
    config: Dict[str, Any] = None
    customer_id: Optional[str] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class AlertCondition:
    """Alert rule condition"""
    field: str
    operator: ThresholdOperator
    value: Union[str, int, float]
    aggregation: Optional[str] = "count"  # count, avg, sum, min, max
    time_window: Optional[str] = "5m"  # 1m, 5m, 15m, 1h, etc.


@dataclass
class AlertRule:
    """Alert rule definition"""
    rule_id: str
    name: str
    description: str
    customer_id: str
    severity: AlertSeverity
    rule_type: AlertRuleType
    enabled: bool = True
    conditions: List[AlertCondition] = None
    filters: List[QueryFilter] = None
    notification_channels: List[str] = None
    tags: List[str] = None
    evaluation_interval: str = "1m"
    cooldown_period: str = "5m"
    max_alerts_per_hour: int = 10
    created_at: datetime = None
    updated_at: datetime = None
    created_by: Optional[str] = None

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
        if self.filters is None:
            self.filters = []
        if self.notification_channels is None:
            self.notification_channels = []
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class AlertInstance:
    """Individual alert instance"""
    alert_id: str
    rule_id: str
    customer_id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    trigger_data: Dict[str, Any] = None
    notification_count: int = 0
    last_notification_at: Optional[datetime] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.trigger_data is None:
            self.trigger_data = {}
        if self.tags is None:
            self.tags = []


class AlertEngine:
    """M3 Alert Engine - Rule-based alerting system"""

    def __init__(self):
        self.query_engine = None
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, AlertInstance] = {}
        self.notification_channels: Dict[str, NotificationChannelConfig] = {}
        self.rule_states: Dict[str, Dict[str, Any]] = {}  # For stateful rules
        self.evaluation_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False

    async def start(self):
        """Start the alert engine"""
        logger.info("Starting M3 Alert Engine...")
        self.is_running = True

        # Load rules and channels from storage
        await self._load_configuration()

        # Start evaluation loops for all enabled rules
        for rule in self.rules.values():
            if rule.enabled:
                await self._start_rule_evaluation(rule)

        logger.info("M3 Alert Engine started successfully")

    async def stop(self):
        """Stop the alert engine"""
        logger.info("Stopping M3 Alert Engine...")
        self.is_running = False

        # Cancel all evaluation tasks
        for task in self.evaluation_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self.evaluation_tasks:
            await asyncio.gather(*self.evaluation_tasks.values(), return_exceptions=True)

        self.evaluation_tasks.clear()
        logger.info("M3 Alert Engine stopped")

    async def _load_configuration(self):
        """Load notification channels only - rules loaded on-demand per customer"""
        # Initialize with default notification channels
        await self._create_default_channels()
        
        # Initialize alert rule cache for on-demand loading
        from events.management.cache.alert_rule_cache import AlertRuleCache
        self.alert_rule_cache = AlertRuleCache()
        
        logger.info("AlertEngine configured for on-demand rule loading per customer")

    async def _create_default_channels(self):
        """Create default notification channels"""
        default_channels = [
            NotificationChannelConfig(
                channel_id="default-email",
                type=NotificationChannel.EMAIL,
                name="Default Email Notifications",
                config={
                    "smtp_host": "localhost",
                    "smtp_port": 587,
                    "from_address": "alerts@logforge.io",
                    "recipients": ["admin@logforge.io"]
                }
            ),
            NotificationChannelConfig(
                channel_id="default-webhook",
                type=NotificationChannel.WEBHOOK,
                name="Default Webhook",
                config={
                    "url": "https://hooks.logforge.io/alerts",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"}
                }
            )
        ]

        for channel in default_channels:
            self.notification_channels[channel.channel_id] = channel

        logger.info(f"Created {len(default_channels)} default notification channels")

    async def get_customer_rules(self, customer_id: str) -> List[AlertRule]:
        """Get alert rules for a customer using Redis cache with database fallback"""
        try:
            # Get rules from cache (with database fallback) - same approach as Sigma engine
            rules_data = await self.alert_rule_cache.get_customer_rules(customer_id)
            
            alert_rules = []
            for row in rules_data:
                try:
                    # Parse the condition_config JSON
                    condition_config = json.loads(row.get("condition_config", "{}"))

                    # Convert cache data to AlertRule object (same as before)
                    rule = AlertRule(
                        rule_id=row["id"],
                        name=row["name"],
                        description=row.get("description", ""),
                        customer_id=row["customer_id"],
                        severity=AlertSeverity(row.get("severity", "medium")),
                        rule_type=AlertRuleType(row.get("rule_type", "threshold")),
                        enabled=bool(row.get("is_enabled", 1)),
                        conditions=self._parse_conditions(condition_config.get("conditions", [])),
                        filters=condition_config.get("filters", []),
                        notification_channels=json.loads(row.get("notification_channels", "[]")) if isinstance(row.get("notification_channels"), str) else row.get("notification_channels", []),
                        tags=condition_config.get("tags", []),
                        evaluation_interval=str(condition_config.get("evaluation_interval", 300)) + "s",  # Convert to seconds format
                        cooldown_period=str(row.get("cooldown_minutes", 5)) + "m",  # Convert to minutes format
                        max_alerts_per_hour=condition_config.get("max_alerts_per_hour", 10),
                        created_at=row.get("created_at"),
                        updated_at=row.get("updated_at"),
                        created_by=row.get("created_by")
                    )
                    
                    alert_rules.append(rule)
                    
                except Exception as e:
                    logger.error(f"Failed to parse rule {row.get('id', 'unknown')}: {e}")
                    continue
                    
            logger.debug(f"✅ Loaded {len(alert_rules)} alert rules from cache for customer {customer_id}")
            return alert_rules
            
        except Exception as e:
            logger.error(f"Failed to get customer rules for {customer_id}: {e}")
            return []

    async def evaluate_customer_logs(self, customer_id: str, logs: List[Dict[str, Any]]) -> List[AlertInstance]:
        """Evaluate logs for a specific customer against their alert rules"""
        try:
            # Get rules for this customer from cache (on-demand)
            customer_rules = await self.get_customer_rules(customer_id)
            
            if not customer_rules:
                logger.debug(f"No alert rules found for customer {customer_id}")
                return []
                
            logger.debug(f"🔍 Evaluating {len(logs)} logs against {len(customer_rules)} alert rules for customer {customer_id}")
            
            triggered_alerts = []
            
            # Evaluate each rule against the logs
            for rule in customer_rules:
                if not rule.enabled:
                    continue
                    
                try:
                    # Check if rule should be triggered by these logs
                    should_trigger = await self._should_trigger_alert_for_logs(rule, logs)
                    
                    if should_trigger:
                        alert = await self._trigger_alert_for_logs(rule, logs)
                        if alert:
                            triggered_alerts.append(alert)
                            
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.name} for customer {customer_id}: {e}")
                    continue
                    
            logger.debug(f"✅ Triggered {len(triggered_alerts)} alerts for customer {customer_id}")
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Failed to evaluate customer logs for {customer_id}: {e}")
            return []

    def _parse_conditions(self, conditions_data):
        """Parse conditions from database format to AlertCondition objects"""
        parsed_conditions = []

        for condition in conditions_data:
            try:
                parsed_condition = AlertCondition(
                    field=condition.get("field", "*"),
                    operator=ThresholdOperator(condition.get("operator", "gt")),
                    value=condition.get("value", 0),
                    aggregation=condition.get("aggregation", "count"),
                    time_window=condition.get("time_window", "5m")
                )
                parsed_conditions.append(parsed_condition)
            except Exception as e:
                logger.warning(f"Failed to parse condition {condition}: {e}")

        return parsed_conditions

    async def reload_rules_from_database(self):
        """Reload rules from database and update running evaluations"""
        try:
            logger.info("Reloading alert rules from database...")

            # Stop all current evaluation tasks
            for task in self.evaluation_tasks.values():
                task.cancel()
            self.evaluation_tasks.clear()

            # Clear current rules
            self.rules.clear()

            # Reload from database
            await self._load_rules_from_database()

            # Restart evaluation loops for enabled rules
            if self.is_running:
                for rule in self.rules.values():
                    if rule.enabled:
                        await self._start_rule_evaluation(rule)

            logger.info(f"Successfully reloaded {len(self.rules)} alert rules")

        except Exception as e:
            logger.error(f"Failed to reload rules from database: {e}")

    async def _create_example_rules(self):
        """Create example alert rules for different scenarios"""
        example_rules = [
            AlertRule(
                rule_id="high-error-rate",
                name="High Error Rate Alert",
                description="Triggers when error rate exceeds threshold",
                customer_id="default",
                severity=AlertSeverity.CRITICAL,
                rule_type=AlertRuleType.THRESHOLD,
                conditions=[
                    AlertCondition(
                        field="is_error",
                        operator=ThresholdOperator.GT,
                        value=10,
                        aggregation="count",
                        time_window="5m"
                    )
                ],
                filters=[
                    QueryFilter(field="level", operator="eq", value="ERROR")
                ],
                notification_channels=["default-email", "default-webhook"],
                tags=["error-monitoring", "critical"]
            ),
            AlertRule(
                rule_id="failed-login-attempts",
                name="Failed Login Attempts",
                description="Multiple failed login attempts detected",
                customer_id="default",
                severity=AlertSeverity.HIGH,
                rule_type=AlertRuleType.FREQUENCY,
                conditions=[
                    AlertCondition(
                        field="http_status",
                        operator=ThresholdOperator.GTE,
                        value=5,
                        aggregation="count",
                        time_window="10m"
                    )
                ],
                filters=[
                    QueryFilter(field="http_status", operator="eq", value="401"),
                    QueryFilter(field="service", operator="eq", value="auth-service")
                ],
                notification_channels=["default-email"],
                tags=["security", "authentication"]
            ),
            AlertRule(
                rule_id="slow-response-time",
                name="Slow Response Time Alert",
                description="API response time exceeding acceptable threshold",
                customer_id="default",
                severity=AlertSeverity.MEDIUM,
                rule_type=AlertRuleType.THRESHOLD,
                conditions=[
                    AlertCondition(
                        field="http_response_time_ms",
                        operator=ThresholdOperator.GT,
                        value=5000,
                        aggregation="avg",
                        time_window="15m"
                    )
                ],
                filters=[
                    QueryFilter(field="http_method", operator="ne", value=""),
                    QueryFilter(field="http_status", operator="lt", value="500")
                ],
                notification_channels=["default-webhook"],
                tags=["performance", "api"]
            )
        ]

        for rule in example_rules:
            self.rules[rule.rule_id] = rule

        logger.info(f"Created {len(example_rules)} example alert rules")

    async def _start_rule_evaluation(self, rule: AlertRule):
        """Start evaluation loop for a specific rule"""
        if rule.rule_id in self.evaluation_tasks:
            # Cancel existing task
            self.evaluation_tasks[rule.rule_id].cancel()

        # Start new evaluation task
        task = asyncio.create_task(self._evaluate_rule_loop(rule))
        self.evaluation_tasks[rule.rule_id] = task

        logger.info(f"Started evaluation loop for rule: {rule.name}")

    async def _evaluate_rule_loop(self, rule: AlertRule):
        """Continuous evaluation loop for a rule"""
        interval_seconds = self._parse_interval(rule.evaluation_interval)

        while self.is_running and rule.enabled:
            try:
                await self._evaluate_rule(rule)
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
                await asyncio.sleep(interval_seconds)

    async def _evaluate_rule(self, rule: AlertRule):
        """Evaluate a single alert rule"""
        try:
            # Initialize query engine if needed
            if not self.query_engine:
                from query_engine import get_query_engine
                self.query_engine = get_query_engine()

            # Build query from rule conditions and filters
            query_request = await self._build_query_from_rule(rule)

            # Execute query
            result = await self.query_engine.execute_query(query_request)

            # Check if alert should be triggered
            should_trigger = await self._should_trigger_alert(rule, result)

            if should_trigger:
                await self._trigger_alert(rule, result)
            else:
                await self._check_alert_resolution(rule)

        except Exception as e:
            logger.error(f"Failed to evaluate rule {rule.name}: {e}")

    async def _build_query_from_rule(self, rule: AlertRule) -> AdvancedQueryRequest:
        """Build query request from alert rule"""
        # Determine time window from conditions
        time_window = "5m"  # default
        if rule.conditions:
            time_window = rule.conditions[0].time_window

        window_seconds = self._parse_interval(time_window)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(seconds=window_seconds)

        # Build aggregations from conditions
        aggregations = []
        for condition in rule.conditions:
            agg_type = condition.aggregation or "count"
            field = condition.field if condition.field != "*" else "*"

            aggregations.append(QueryAggregation(
                type=AggregationType(agg_type),
                field=field
            ))

        # Convert filter dicts to QueryFilter objects
        query_filters = []
        for filter_dict in rule.filters or []:
            if isinstance(filter_dict, dict):
                query_filter = QueryFilter(
                    field=filter_dict.get("field"),
                    operator=QueryOperator(filter_dict.get("operator", "eq")),
                    value=filter_dict.get("value")
                )
                query_filters.append(query_filter)
            else:
                # Already a QueryFilter object
                query_filters.append(filter_dict)

        # Add customer_id filter if not already present
        has_customer_filter = any(f.field == "customer_id" for f in query_filters if hasattr(f, 'field'))
        if not has_customer_filter:
            query_filters.append(QueryFilter(
                field="customer_id",
                operator=QueryOperator.EQ,
                value=rule.customer_id
            ))

        return AdvancedQueryRequest(
            start_time=start_time,
            end_time=end_time,
            filters=query_filters,
            aggregations=aggregations,
            limit=1000
        )

    async def _should_trigger_alert(self, rule: AlertRule, query_result: Any) -> bool:
        """Determine if alert should be triggered based on rule conditions"""
        if not rule.conditions:
            return False

        # Check cooldown period
        if await self._is_in_cooldown(rule):
            return False

        # Check rate limiting
        if await self._is_rate_limited(rule):
            return False

        # Evaluate conditions
        for condition in rule.conditions:
            if not await self._evaluate_condition(condition, query_result):
                return False

        return True

    async def _evaluate_condition(self, condition: AlertCondition, query_result: Any) -> bool:
        """Evaluate a single alert condition"""
        try:
            # Extract value from query result based on aggregation
            actual_value = self._extract_metric_value(query_result, condition)

            # Debug logging
            logger.info(f"Condition evaluation - field: {condition.field}, aggregation: {condition.aggregation}, actual_value: {actual_value}, operator: {condition.operator}, threshold: {condition.value}")

            # Compare with threshold
            result = self._compare_values(actual_value, condition.operator, condition.value)
            logger.info(f"Condition result: {result}")

            return result

        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

    def _extract_metric_value(self, query_result: Any, condition: AlertCondition) -> float:
        """Extract metric value from query result"""
        # Extract value from aggregation results
        if hasattr(query_result, 'aggregations') and query_result.aggregations:
            # aggregations is a dict, not a list
            aggs = query_result.aggregations

            # For count(*) aggregation, look for count_all key
            if condition.aggregation == 'count' and condition.field == '*':
                if 'count_all' in aggs:
                    return float(aggs['count_all'])

            # Look for matching field aggregation
            expected_key = f"{condition.aggregation}_{condition.field.replace('*', 'all')}"
            if expected_key in aggs:
                return float(aggs[expected_key])

        # Fallback - use total result count
        if hasattr(query_result, 'total_count'):
            return float(query_result.total_count)

        return 0.0

    def _compare_values(self, actual: float, operator: ThresholdOperator, expected: Union[str, int, float]) -> bool:
        """Compare actual value with expected using operator"""
        expected_float = float(expected)

        if operator == ThresholdOperator.GT:
            return actual > expected_float
        elif operator == ThresholdOperator.GTE:
            return actual >= expected_float
        elif operator == ThresholdOperator.LT:
            return actual < expected_float
        elif operator == ThresholdOperator.LTE:
            return actual <= expected_float
        elif operator == ThresholdOperator.EQ:
            return actual == expected_float
        elif operator == ThresholdOperator.NE:
            return actual != expected_float

        return False

    async def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Check if rule is in cooldown period"""
        rule_state = self.rule_states.get(rule.rule_id, {})
        last_trigger = rule_state.get('last_trigger_time')

        if not last_trigger:
            return False

        cooldown_seconds = self._parse_interval(rule.cooldown_period)
        return (datetime.utcnow() - last_trigger).total_seconds() < cooldown_seconds

    async def _is_rate_limited(self, rule: AlertRule) -> bool:
        """Check if rule is rate limited"""
        rule_state = self.rule_states.get(rule.rule_id, {})
        alerts_this_hour = rule_state.get('alerts_this_hour', 0)
        hour_start = rule_state.get('hour_start', datetime.utcnow().replace(minute=0, second=0, microsecond=0))

        # Reset counter if new hour
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        if current_hour > hour_start:
            alerts_this_hour = 0
            rule_state['hour_start'] = current_hour
            rule_state['alerts_this_hour'] = 0
            self.rule_states[rule.rule_id] = rule_state

        return alerts_this_hour >= rule.max_alerts_per_hour

    async def _trigger_alert(self, rule: AlertRule, query_result: Any):
        """Trigger an alert for the given rule"""
        alert_id = str(uuid.uuid4())

        alert = AlertInstance(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            customer_id=rule.customer_id,
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            triggered_at=datetime.utcnow(),
            trigger_data=self._build_alert_context(query_result),
            tags=rule.tags
        )

        # Store alert
        self.active_alerts[alert_id] = alert

        # Update rule state
        rule_state = self.rule_states.get(rule.rule_id, {})
        rule_state['last_trigger_time'] = datetime.utcnow()
        rule_state['alerts_this_hour'] = rule_state.get('alerts_this_hour', 0) + 1
        self.rule_states[rule.rule_id] = rule_state

        # Send notifications
        await self._send_notifications(alert, rule)

        logger.warning(f"Alert triggered: {rule.name} (ID: {alert_id})")

    def _build_alert_context(self, query_result: Any) -> Dict[str, Any]:
        """Build context data for the alert"""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "query_total": getattr(query_result, 'total', 0),
            "execution_time_ms": getattr(query_result, 'execution_time_ms', 0)
        }

        # Add aggregation results if available
        if hasattr(query_result, 'aggregations'):
            context['aggregations'] = query_result.aggregations

        return context

    async def _send_notifications(self, alert: AlertInstance, rule: AlertRule):
        """Send notifications for an alert"""
        for channel_id in rule.notification_channels:
            channel = self.notification_channels.get(channel_id)
            if not channel or not channel.enabled:
                continue

            try:
                await self._send_notification(alert, channel)
                alert.notification_count += 1
                alert.last_notification_at = datetime.utcnow()
            except Exception as e:
                logger.error(f"Failed to send notification via {channel.name}: {e}")

    async def _send_notification(self, alert: AlertInstance, channel: NotificationChannelConfig):
        """Send notification via specific channel"""
        message = self._format_alert_message(alert)

        if channel.type == NotificationChannel.EMAIL:
            await self._send_email_notification(alert, channel, message)
        elif channel.type == NotificationChannel.SLACK:
            await self._send_slack_notification(alert, channel, message)
        elif channel.type == NotificationChannel.WEBHOOK:
            await self._send_webhook_notification(alert, channel, message)
        elif channel.type == NotificationChannel.PAGERDUTY:
            await self._send_pagerduty_notification(alert, channel, message)
        else:
            logger.warning(f"Unsupported notification channel: {channel.type}")

    def _format_alert_message(self, alert: AlertInstance) -> str:
        """Format alert message for notifications"""
        return f"""
🚨 ALERT: {alert.name}

Severity: {alert.severity.value.upper()}
Status: {alert.status.value}
Customer: {alert.customer_id}
Triggered: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

Description: {alert.description}

Alert ID: {alert.alert_id}
Rule ID: {alert.rule_id}

Context: {json.dumps(alert.trigger_data, indent=2)}
"""

    async def _send_email_notification(self, alert: AlertInstance, channel: NotificationChannelConfig, message: str):
        """Send email notification (placeholder implementation)"""
        # In a real implementation, this would use SMTP
        logger.info(f"EMAIL notification sent for alert {alert.alert_id} via {channel.name}")

    async def _send_slack_notification(self, alert: AlertInstance, channel: NotificationChannelConfig, message: str):
        """Send Slack notification (placeholder implementation)"""
        # In a real implementation, this would use Slack API
        logger.info(f"SLACK notification sent for alert {alert.alert_id} via {channel.name}")

    async def _send_webhook_notification(self, alert: AlertInstance, channel: NotificationChannelConfig, message: str):
        """Send webhook notification (placeholder implementation)"""
        # In a real implementation, this would make HTTP requests
        logger.info(f"WEBHOOK notification sent for alert {alert.alert_id} via {channel.name}")

    async def _send_pagerduty_notification(self, alert: AlertInstance, channel: NotificationChannelConfig, message: str):
        """Send PagerDuty notification (placeholder implementation)"""
        # In a real implementation, this would use PagerDuty Events API
        logger.info(f"PAGERDUTY notification sent for alert {alert.alert_id} via {channel.name}")

    async def _check_alert_resolution(self, rule: AlertRule):
        """Check if any active alerts for this rule should be resolved"""
        rule_alerts = [alert for alert in self.active_alerts.values()
                      if alert.rule_id == rule.rule_id and alert.status == AlertStatus.ACTIVE]

        for alert in rule_alerts:
            # In a more sophisticated implementation, we'd re-evaluate conditions
            # For now, we'll implement a simple time-based resolution
            time_since_trigger = (datetime.utcnow() - alert.triggered_at).total_seconds()

            # Auto-resolve after 1 hour if conditions are no longer met
            if time_since_trigger > 3600:
                await self._resolve_alert(alert.alert_id, "Auto-resolved: conditions no longer met")

    async def _resolve_alert(self, alert_id: str, resolution_reason: str):
        """Resolve an active alert"""
        alert = self.active_alerts.get(alert_id)
        if not alert or alert.status != AlertStatus.ACTIVE:
            return

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.trigger_data['resolution_reason'] = resolution_reason

        logger.info(f"Alert resolved: {alert.name} (ID: {alert_id}) - {resolution_reason}")

    def _parse_interval(self, interval: str) -> int:
        """Parse interval string to seconds"""
        if not interval:
            return 60  # default 1 minute

        interval = interval.lower().strip()

        if interval.endswith('s'):
            return int(interval[:-1])
        elif interval.endswith('m'):
            return int(interval[:-1]) * 60
        elif interval.endswith('h'):
            return int(interval[:-1]) * 3600
        elif interval.endswith('d'):
            return int(interval[:-1]) * 86400
        else:
            # Assume minutes if no unit
            return int(interval) * 60

    # Public API methods

    async def create_rule(self, rule: AlertRule) -> AlertRule:
        """Create a new alert rule"""
        rule.rule_id = rule.rule_id or str(uuid.uuid4())
        rule.created_at = datetime.utcnow()
        rule.updated_at = datetime.utcnow()

        self.rules[rule.rule_id] = rule

        if rule.enabled and self.is_running:
            await self._start_rule_evaluation(rule)

        logger.info(f"Created alert rule: {rule.name}")
        return rule

    async def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> Optional[AlertRule]:
        """Update an existing alert rule"""
        rule = self.rules.get(rule_id)
        if not rule:
            return None

        # Update fields
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()

        # Restart evaluation if rule is enabled
        if rule.enabled and self.is_running:
            await self._start_rule_evaluation(rule)
        elif not rule.enabled and rule_id in self.evaluation_tasks:
            # Stop evaluation for disabled rule
            self.evaluation_tasks[rule_id].cancel()
            del self.evaluation_tasks[rule_id]

        logger.info(f"Updated alert rule: {rule.name}")
        return rule

    async def delete_rule(self, rule_id: str) -> bool:
        """Delete an alert rule"""
        if rule_id not in self.rules:
            return False

        # Stop evaluation
        if rule_id in self.evaluation_tasks:
            self.evaluation_tasks[rule_id].cancel()
            del self.evaluation_tasks[rule_id]

        # Remove rule
        rule = self.rules.pop(rule_id)

        # Clean up rule state
        self.rule_states.pop(rule_id, None)

        logger.info(f"Deleted alert rule: {rule.name}")
        return True

    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule by ID"""
        return self.rules.get(rule_id)

    async def list_rules(self, customer_id: Optional[str] = None) -> List[AlertRule]:
        """List alert rules, optionally filtered by customer"""
        rules = list(self.rules.values())

        if customer_id:
            rules = [rule for rule in rules if rule.customer_id == customer_id]

        return rules

    async def get_alert(self, alert_id: str) -> Optional[AlertInstance]:
        """Get alert instance by ID"""
        return self.active_alerts.get(alert_id)

    async def list_alerts(self, customer_id: Optional[str] = None, status: Optional[AlertStatus] = None) -> List[AlertInstance]:
        """List alerts with optional filters"""
        alerts = list(self.active_alerts.values())

        if customer_id:
            alerts = [alert for alert in alerts if alert.customer_id == customer_id]

        if status:
            alerts = [alert for alert in alerts if alert.status == status]

        return alerts

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        alert = self.active_alerts.get(alert_id)
        if not alert or alert.status != AlertStatus.ACTIVE:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by

        logger.info(f"Alert acknowledged: {alert.name} by {acknowledged_by}")
        return True

    async def resolve_alert(self, alert_id: str, resolved_by: str, reason: str = "") -> bool:
        """Manually resolve an alert"""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        await self._resolve_alert(alert_id, f"Manually resolved by {resolved_by}: {reason}")
        return True

    async def test_rule(self, rule: AlertRule) -> Dict[str, Any]:
        """Test an alert rule without triggering notifications"""
        try:
            # Initialize query engine if needed
            if not self.query_engine:
                from query_engine import get_query_engine
                self.query_engine = get_query_engine()

            query_request = await self._build_query_from_rule(rule)
            logger.info(f"Alert test query: start={query_request.start_time}, end={query_request.end_time}, filters={[f'{f.field}={f.value}' for f in query_request.filters]}")
            result = await self.query_engine.execute_query(query_request)
            logger.info(f"Query result: aggregations={getattr(result, 'aggregations', None)}, total_count={getattr(result, 'total_count', None)}")
            should_trigger = await self._should_trigger_alert(rule, result)

            return {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "would_trigger": should_trigger,
                "query_result_count": getattr(result, 'total_count', 0),
                "evaluation_time": datetime.utcnow().isoformat(),
                "conditions_evaluated": len(rule.conditions)
            }
        except Exception as e:
            return {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "error": str(e),
                "would_trigger": False
            }

    def get_health(self) -> Dict[str, Any]:
        """Get alert engine health status"""
        return {
            "status": "running" if self.is_running else "stopped",
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.rules),
            "last_evaluation": datetime.now().isoformat(),
            "engine_uptime": "healthy"
        }

    def get_stats(self, customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed alert engine statistics"""
        # Filter by customer if provided
        customer_rules = [r for r in self.rules.values() if not customer_id or r.customer_id == customer_id]
        customer_alerts = [a for a in self.active_alerts.values() if not customer_id or a.customer_id == customer_id]

        enabled_rules = len([r for r in customer_rules if r.enabled])
        disabled_rules = len([r for r in customer_rules if not r.enabled])

        active_alerts = len([a for a in customer_alerts if a.status == AlertStatus.ACTIVE])
        acknowledged_alerts = len([a for a in customer_alerts if a.status == AlertStatus.ACKNOWLEDGED])
        resolved_alerts = len([a for a in customer_alerts if a.status == AlertStatus.RESOLVED])

        return {
            "total_rules": len(customer_rules),
            "enabled_rules": enabled_rules,
            "disabled_rules": disabled_rules,
            "active_alerts": active_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "resolved_alerts": resolved_alerts,
            "total_alerts_fired": len(customer_alerts),
            "notifications_sent": sum(a.notification_count for a in customer_alerts),
            "notifications_failed": 0,  # Would track failures in real implementation
            "avg_evaluation_time_ms": 45.2,  # Would calculate from actual metrics
            "last_evaluation": datetime.now().isoformat()
        }


# Pydantic models for API

class AlertRuleCreateRequest(BaseModel):
    """Request model for creating alert rules"""
    name: str = Field(..., description="Alert rule name")
    description: str = Field(..., description="Alert rule description")
    customer_id: Optional[str] = Field(None, description="Customer ID (auto-injected from headers)")
    severity: AlertSeverity = Field(..., description="Alert severity")
    rule_type: AlertRuleType = Field(..., description="Rule type")
    enabled: bool = Field(True, description="Whether rule is enabled")
    conditions: List[Dict[str, Any]] = Field([], description="Alert conditions")
    filters: List[Dict[str, Any]] = Field([], description="Query filters")
    notification_channels: List[str] = Field([], description="Notification channel IDs")
    tags: List[str] = Field([], description="Rule tags")
    evaluation_interval: str = Field("1m", description="Evaluation interval")
    cooldown_period: str = Field("5m", description="Cooldown period")
    max_alerts_per_hour: int = Field(10, description="Max alerts per hour")


class AlertRuleResponse(BaseModel):
    """Response model for alert rules"""
    rule_id: str
    name: str
    description: str
    customer_id: str
    severity: AlertSeverity
    rule_type: AlertRuleType
    enabled: bool
    conditions: List[Dict[str, Any]]
    filters: List[Dict[str, Any]]
    notification_channels: List[str]
    tags: List[str]
    evaluation_interval: str
    cooldown_period: str
    max_alerts_per_hour: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]


class AlertInstanceResponse(BaseModel):
    """Response model for alert instances"""
    alert_id: str
    rule_id: str
    customer_id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    resolved_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    trigger_data: Dict[str, Any]
    notification_count: int
    last_notification_at: Optional[datetime]
    tags: List[str]


# Global alert engine instance
alert_engine = AlertEngine()
