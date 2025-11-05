"""
Sigma Rule Matching Engine - Real-time log analysis against Sigma detection rules
Evaluates incoming logs against Sigma rules and generates security detection events
"""

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

# Import security analytics components
from security_analytics import SigmaRule, DetectionSeverity, SecurityDetection
from events.publishers.security_publisher import SecurityEventPublisher
from events.constants import EVENT_SECURITY_DETECTION_TRIGGERED
from field_mapper import normalize_log_for_sigma

logger = structlog.get_logger(__name__)


class MatchResult(str, Enum):
    """Sigma rule match result types"""
    MATCH = "match"
    NO_MATCH = "no_match"
    ERROR = "error"


@dataclass
class SigmaMatch:
    """Represents a successful Sigma rule match"""
    rule_id: str
    rule_title: str
    log_entry: Dict[str, Any]
    matched_fields: Dict[str, Any]
    severity: DetectionSeverity
    attack_techniques: List[str]
    kill_chain_phases: List[str]
    timestamp: datetime
    customer_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for event publishing"""
        return {
            "rule_id": self.rule_id,
            "rule_title": self.rule_title,
            "log_entry": self.log_entry,
            "matched_fields": self.matched_fields,
            "severity": self.severity.value,
            "attack_techniques": self.attack_techniques,
            "kill_chain_phases": self.kill_chain_phases,
            "timestamp": self.timestamp.isoformat(),
            "customer_id": self.customer_id
        }


class SigmaFieldMatcher:
    """Handles field-level matching for Sigma rule conditions"""

    @staticmethod
    def match_field(log_value: Any, rule_value: Any, operator: str = "eq") -> bool:
        """
        Match a log field value against a rule condition

        Args:
            log_value: Value from the log entry
            rule_value: Expected value from the Sigma rule
            operator: Matching operator (eq, contains, regex, etc.)

        Returns:
            bool: True if the field matches the condition
        """
        try:
            if log_value is None:
                return False

            # Convert both to strings for comparison
            log_str = str(log_value).lower()

            # Handle list of possible values in rule
            if isinstance(rule_value, list):
                return any(SigmaFieldMatcher.match_field(log_value, val, operator) for val in rule_value)

            rule_str = str(rule_value).lower()

            # Handle different operators
            if operator == "eq" or operator is None:
                return log_str == rule_str
            elif operator == "contains":
                return rule_str in log_str
            elif operator == "startswith":
                return log_str.startswith(rule_str)
            elif operator == "endswith":
                return log_str.endswith(rule_str)
            elif operator == "regex":
                try:
                    return bool(re.search(rule_str, log_str, re.IGNORECASE))
                except re.error:
                    logger.warning(f"Invalid regex pattern: {rule_str}")
                    return False
            elif operator == "gt":
                try:
                    return float(log_str) > float(rule_str)
                except (ValueError, TypeError):
                    return False
            elif operator == "gte":
                try:
                    return float(log_str) >= float(rule_str)
                except (ValueError, TypeError):
                    return False
            elif operator == "lt":
                try:
                    return float(log_str) < float(rule_str)
                except (ValueError, TypeError):
                    return False
            elif operator == "lte":
                try:
                    return float(log_str) <= float(rule_str)
                except (ValueError, TypeError):
                    return False
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        except Exception as e:
            logger.error(f"Error matching field {log_value} against {rule_value} with operator {operator}: {e}")
            return False


class SigmaConditionEvaluator:
    """Evaluates Sigma rule detection conditions"""

    def __init__(self):
        self.field_matcher = SigmaFieldMatcher()

    def evaluate_selection(self, log_entry: Dict[str, Any], selection: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate a selection block against a log entry

        Args:
            log_entry: The log entry to check
            selection: The selection criteria from the Sigma rule

        Returns:
            Tuple of (match_result, matched_fields)
        """
        matched_fields = {}

        try:
            for field_name, expected_value in selection.items():
                # Handle special field operators (e.g., "command_line|contains")
                if "|" in field_name:
                    base_field, operator = field_name.split("|", 1)
                else:
                    base_field = field_name
                    operator = "eq"

                # Get the actual field value from the log
                log_value = self._get_field_value(log_entry, base_field)

                # Check if the field matches
                if self.field_matcher.match_field(log_value, expected_value, operator):
                    matched_fields[field_name] = {
                        "log_value": log_value,
                        "expected_value": expected_value,
                        "operator": operator
                    }
                else:
                    # If any field doesn't match, the selection fails
                    return False, {}

            # All fields matched
            return True, matched_fields

        except Exception as e:
            logger.error(f"Error evaluating selection: {e}")
            return False, {}

    def _get_field_value(self, log_entry: Dict[str, Any], field_name: str) -> Any:
        """
        Get a field value from a log entry, supporting nested fields

        Args:
            log_entry: The log entry dictionary
            field_name: The field name (supports dot notation for nested fields)

        Returns:
            The field value or None if not found
        """
        try:
            # Handle nested field access (e.g., "user.name")
            if "." in field_name:
                current_value = log_entry
                for part in field_name.split("."):
                    if isinstance(current_value, dict) and part in current_value:
                        current_value = current_value[part]
                    else:
                        return None
                return current_value
            else:
                return log_entry.get(field_name)
        except Exception:
            return None


class SigmaRuleEngine:
    """Main Sigma Rule Matching Engine with Subscription Integration"""

    def __init__(self):
        self.condition_evaluator = SigmaConditionEvaluator()
        self.security_publisher = None  # Initialize later when needed
        # Import here to avoid circular imports
        from services.subscription_service import SubscriptionService
        self.subscription_service = SubscriptionService()

    def _get_security_publisher(self):
        """Lazy initialization of security publisher"""
        if self.security_publisher is None:
            try:
                # Import dependencies to get the publisher manager
                import sys
                import os
                api_root = os.path.dirname(os.path.abspath(__file__))
                if api_root not in sys.path:
                    sys.path.append(api_root)

                import dependencies
                if dependencies.event_publisher_manager:
                    self.security_publisher = SecurityEventPublisher(dependencies.event_publisher_manager)
                else:
                    logger.warning("Event publisher manager not available for security events")
                    return None
            except Exception as e:
                logger.error(f"Failed to initialize security publisher: {e}")
                return None
        return self.security_publisher

    async def evaluate_logs_against_rules(
        self,
        logs: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        customer_id: str,
        logs_normalized: bool = False
    ) -> List[SigmaMatch]:
        """
        Evaluate a batch of logs against Sigma rules

        Args:
            logs: List of log entries to evaluate
            rules: List of Sigma rule dictionaries
            customer_id: Customer/tenant ID
            logs_already_normalized: If True, logs are already normalized (skip re-normalization)

        Returns:
            List of SigmaMatch objects for rules that matched
        """
        matches = []

        try:
            logger.debug(f"🔍 Evaluating {len(logs)} logs against {len(rules)} Sigma rules for customer {customer_id}")
            logger.debug(f"🔄 Logs already normalized: {logs_normalized}")

            # Debug: Log sample of what we're processing
            if logs:
                sample_log = logs[0]
                logger.debug(f"🔍 Sample log entry: {json.dumps(sample_log, default=str)}")

            if rules:
                sample_rule = rules[0]
                logger.debug(f"🔍 Sample rule: {sample_rule.get('id', 'unknown')} - {sample_rule.get('title', 'unknown')}")
                logger.debug(f"🔍 Sample rule detection: {json.dumps(sample_rule.get('detection', {}), default=str)}")

            # Handle normalized vs raw logs
            if logs_normalized:
                # Logs are already normalized - use them directly
                logger.debug(f"✅ Using already normalized logs (no re-normalization needed)")
                normalized_logs = [(log_entry, log_entry) for log_entry in logs]
            else:
                # Legacy path: normalize logs here (for backward compatibility)
                logger.debug(f"🔄 Normalizing logs for rule evaluation (legacy path)")
                normalized_logs = []
                for log_entry in logs:
                    normalized_log = normalize_log_for_sigma(log_entry)
                    normalized_logs.append((log_entry, normalized_log))

            logger.debug(f"🔄 Processing {len(normalized_logs)} logs for rule evaluation")
            if normalized_logs:
                sample_original = normalized_logs[0][0]
                sample_normalized = normalized_logs[0][1]
                logger.debug(f"🔍 Sample original: {json.dumps(sample_original, default=str)}")
                logger.debug(f"🔄 Sample normalized: {json.dumps(sample_normalized, default=str)}")

            for original_log, normalized_log in normalized_logs:
                for rule_dict in rules:
                    try:
                        # Convert rule dict to SigmaRule object if needed
                        if isinstance(rule_dict, dict):
                            rule = self._dict_to_sigma_rule(rule_dict)
                        else:
                            rule = rule_dict

                        # Evaluate the rule against the normalized log
                        match_result = await self._evaluate_rule_against_normalized_log(original_log, normalized_log, rule, customer_id)

                        if match_result:
                            matches.append(match_result)
                            logger.info(f"🚨 Sigma rule match: {rule.id} - {rule.title}")

                            # Publish security detection event
                            await self._publish_detection_event(match_result)

                    except Exception as e:
                        logger.error(f"Error evaluating rule {rule_dict.get('id', 'unknown')}: {e}")
                        continue

            logger.debug(f"✅ Sigma evaluation complete: {len(matches)} detections found")
            return matches

        except Exception as e:
            logger.error(f"Error in Sigma rule evaluation: {e}")
            return []

    async def _evaluate_rule_against_normalized_log(
        self,
        original_log: Dict[str, Any],
        normalized_log: Dict[str, Any],
        rule: SigmaRule,
        customer_id: str
    ) -> Optional[SigmaMatch]:
        """
        Evaluate a single Sigma rule against a pre-normalized log entry

        Args:
            original_log: The original log entry
            normalized_log: The normalized log entry
            rule: The Sigma rule to evaluate
            customer_id: Customer/tenant ID

        Returns:
            SigmaMatch if the rule matches, None otherwise
        """
        try:
            detection = rule.detection

            # Removed logsource matching - SIGMA rules should be generic across environments
            # Real filtering happens at selection level (event_type, status_code, etc.)

            # Evaluate the main selection
            selection = detection.get("selection", {})
            if not selection:
                logger.warning(f"Rule {rule.id} has no selection criteria")
                return None

            selection_match, matched_fields = self.condition_evaluator.evaluate_selection(normalized_log, selection)

            if not selection_match:
                return None

            # Check filter conditions (if any)
            filter_condition = detection.get("filter", {})
            if filter_condition:
                filter_match, _ = self.condition_evaluator.evaluate_selection(normalized_log, filter_condition)
                if filter_match:
                    # If filter matches, exclude this log (rule condition: "selection and not filter")
                    return None

            # Check condition logic
            condition = detection.get("condition", "selection")
            if not self._evaluate_condition_logic(condition, selection_match):
                return None

            # Create match result using normalized log (contains all the rich field data)
            match = SigmaMatch(
                rule_id=rule.id,
                rule_title=rule.title,
                log_entry=normalized_log,  # Use normalized_log which has all the fields (src_ip, user, host, etc.)
                matched_fields=matched_fields,
                severity=rule.severity,
                attack_techniques=[tech.value for tech in rule.attack_techniques],
                kill_chain_phases=rule.kill_chain_phases,
                timestamp=datetime.now(),
                customer_id=customer_id
            )

            return match

        except Exception as e:
            logger.error(f"Error evaluating rule {rule.id} against log: {e}")
            return None


    def _evaluate_condition_logic(self, condition: str, selection_match: bool) -> bool:
        """
        Evaluate the condition logic (for now, simplified)

        Args:
            condition: The condition string from the rule
            selection_match: Whether the selection matched

        Returns:
            bool: True if the condition is satisfied
        """
        # For now, we support simple conditions
        # Future enhancement: parse complex conditions like "count(selection) >= 10"

        if condition == "selection":
            return selection_match
        elif "and not filter" in condition:
            return selection_match  # Filter logic handled in _evaluate_rule_against_log
        else:
            # For complex conditions, default to selection match
            # TODO: Implement full condition parsing
            logger.debug(f"Complex condition not fully supported yet: {condition}")
            return selection_match

    def _dict_to_sigma_rule(self, rule_dict: Dict[str, Any]) -> SigmaRule:
        """
        Convert a rule dictionary to a SigmaRule object

        Args:
            rule_dict: Rule dictionary from database/cache

        Returns:
            SigmaRule object
        """
        # This is a simplified conversion - in a real implementation,
        # you'd want more robust parsing and validation
        from security_analytics import AttackTechnique

        # Parse attack techniques
        attack_techniques = []
        for tech_str in rule_dict.get("attack_techniques", []):
            try:
                if isinstance(tech_str, str) and hasattr(AttackTechnique, tech_str):
                    attack_techniques.append(getattr(AttackTechnique, tech_str))
            except Exception:
                pass

        return SigmaRule(
            id=rule_dict.get("id", "unknown"),
            title=rule_dict.get("title", "Unknown Rule"),
            description=rule_dict.get("description", ""),
            severity=DetectionSeverity(rule_dict.get("severity", "medium")),
            attack_techniques=attack_techniques,
            kill_chain_phases=rule_dict.get("kill_chain_phases", []),
            tags=rule_dict.get("tags", []),
            logsource=rule_dict.get("logsource", {}),
            detection=rule_dict.get("detection", {})
        )

    async def _publish_detection_event(self, match: SigmaMatch) -> None:
        """
        Publish a security detection event when a rule matches

        Args:
            match: The SigmaMatch containing detection details
        """
        logger.info(f"SIGMA MATCH IS {match}")
        try:
            # Create security detection
            detection = SecurityDetection(
                id=str(uuid.uuid4()),
                rule_id=match.rule_id,
                customer_id=match.customer_id,
                severity=match.severity,
                title=f"Security Detection: {match.rule_title}",
                description=f"Sigma rule {match.rule_id} triggered by log activity",
                attack_techniques=match.attack_techniques,
                kill_chain_phases=match.kill_chain_phases,
                artifact_data=match.log_entry,
                matched_fields=match.matched_fields,
                timestamp=match.timestamp,
                status="open"
            )

            # Publish the security detection triggered event
            security_publisher = self._get_security_publisher()
            if security_publisher:
                await security_publisher.publish_security_detection_triggered(
                    customer_id=match.customer_id,
                    detection_data=detection.to_dict()
                )
            else:
                logger.warning(f"Security publisher not available - skipping event publication for match {match.rule_id}")

            logger.info(f"🚨 Published security detection event for rule {match.rule_id}")

        except Exception as e:
            logger.error(f"Error publishing detection event: {e}")

    async def _get_cached_tenant_rules(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get tenant's sigma rules from Redis cache using existing infrastructure

        Args:
            customer_id: Tenant ID

        Returns:
            List of cached sigma rules for the tenant
        """
        try:
            # Import here to avoid circular imports
            from dependencies import get_sigma_rule_cache

            sigma_cache = get_sigma_rule_cache()
            if not sigma_cache:
                logger.warning(f"Sigma rule cache not available for tenant {customer_id}")
                return []

            # Get tenant's rules from cache (includes both tenant-specific and default rules)
            # The cache filtering by subscription is handled during cache save
            cached_rules = await sigma_cache.get_customer_rules(customer_id, include_defaults=True)

            logger.debug(f"Retrieved {len(cached_rules)} cached sigma rules for tenant {customer_id}")
            return cached_rules

        except Exception as e:
            logger.error(f"Error getting cached rules for tenant {customer_id}: {e}")
            return []

    async def evaluate_logs_for_tenant_with_subscription(
        self,
        logs: List[Dict[str, Any]],
        customer_id: str
    ) -> List[SigmaMatch]:
        """
        NEW: Subscription-aware log evaluation using existing Redis cache infrastructure

        Args:
            logs: List of log entries to evaluate
            customer_id: Customer/tenant ID

        Returns:
            List of SigmaMatch objects for rules that matched
        """
        try:
            # Check if tenant has security analytics access using subscription service
            subscription = await self.subscription_service.get_tenant_subscription(customer_id)
            if not subscription:
                logger.debug(f"No subscription found for tenant {customer_id}")
                return []

            # Check if subscription includes security features
            # Security features: ["*"] (all features) or ["security.*"] (security features)
            features = subscription.get("subscribed_features", "")
            has_security_access = (
                features == "['*']" or  # All features
                "security.*" in features or  # Security features
                "security" in features  # Legacy security access
            )

            if not has_security_access:
                logger.debug(f"No security features in subscription for tenant {customer_id}: {features}")
                return []

            # Get tenant's rules from existing Redis cache
            # Cache key: security:sigma:rules:{customer_id}
            tenant_rules = await self._get_cached_tenant_rules(customer_id)
            if not tenant_rules:
                logger.debug(f"No cached sigma rules found for tenant {customer_id}")
                return []

            # Use all available rules - pricing is per alert generated, not per rule
            filtered_rules = tenant_rules

            logger.debug(f"🔍 Evaluating {len(logs)} logs against {len(filtered_rules)}/{len(tenant_rules)} subscription-filtered rules for tenant {customer_id}")

            # Evaluate filtered rules against logs
            return await self.evaluate_logs_against_rules(logs, filtered_rules, customer_id)

        except Exception as e:
            logger.error(f"Error in subscription-aware sigma evaluation for {customer_id}: {e}")
            return []


# Singleton instance for use across the application
sigma_engine = SigmaRuleEngine()
