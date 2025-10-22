"""
Base Matcher Interface

Abstract base class for alert rule matchers following the Alert Matching System Plan.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from constants.alert_constants import (
    ComparisonOperator, LogicalOperator, MAX_CONDITION_DEPTH,
    COMPARISON_OPERATORS, LOGICAL_OPERATORS
)

logger = logging.getLogger(__name__)

class BaseAlertMatcher(ABC):
    """
    Base interface for alert rule matchers.

    All alert matchers must implement this interface to ensure consistent
    behavior across different rule types (threshold, pattern, anomaly, etc.).
    """

    def __init__(self):
        """Initialize base matcher."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def matches(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> bool:
        """
        Check if logs match the alert rule.

        Args:
            logs: List of log entries to check against the rule
            rule: Alert rule configuration dictionary

        Returns:
            bool: True if logs match the rule criteria, False otherwise
        """
        pass

    @abstractmethod
    def get_rule_type(self) -> str:
        """
        Return the rule type this matcher handles.

        Returns:
            str: Rule type identifier (e.g., 'threshold', 'pattern', 'anomaly')
        """
        pass

    async def extract_match_data(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract data about the match for alert instance creation.

        This method provides additional context about why the rule matched,
        which logs triggered it, and relevant metrics for the alert instance.

        Args:
            logs: List of log entries that matched
            rule: Alert rule configuration

        Returns:
            Dict containing match details for alert instance
        """
        try:
            matching_logs = await self._get_matching_logs(logs, rule)

            # Parse rule condition for enhanced evaluation
            condition_evaluation = None
            human_readable_condition = "No condition specified"

            try:
                condition_config = self._parse_rule_condition(rule)
                if condition_config:
                    # Evaluate condition and get detailed results
                    condition_evaluation = self._evaluate_nested_condition(logs, condition_config)
                    human_readable_condition = condition_evaluation.get("human_readable", "Complex condition")
            except Exception as e:
                self.logger.warning(f"Failed to evaluate condition for rule {rule.get('id')}: {e}")
                condition_evaluation = {
                    "matched": True,
                    "matched_logs": logs,
                    "human_readable": f"Condition evaluation error: {e}",
                    "evaluation_details": {"error": str(e)}
                }

            return {
                "rule_type": self.get_rule_type(),
                "rule_id": rule.get('id'),
                "rule_name": rule.get('name', 'Unknown Rule'),
                "matched_logs_count": len(matching_logs),
                "time_window": {
                    "start": min([log.get('ts', datetime.now(timezone.utc)) for log in matching_logs]) if matching_logs else None,
                    "end": max([log.get('ts', datetime.now(timezone.utc)) for log in matching_logs]) if matching_logs else None
                },
                "condition_evaluation": {
                    "human_readable": human_readable_condition,
                    "matched": condition_evaluation.get("matched", True) if condition_evaluation else True,
                    "matched_logs_count": len(condition_evaluation.get("matched_logs", [])) if condition_evaluation else len(matching_logs),
                    "evaluation_details": condition_evaluation.get("evaluation_details", {}) if condition_evaluation else {}
                },
                "match_details": await self._extract_specific_match_data(logs, rule),
                "triggered_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            self.logger.error(f"Failed to extract match data for rule {rule.get('id')}: {e}")
            return {
                "rule_type": self.get_rule_type(),
                "rule_id": rule.get('id'),
                "error": str(e),
                "triggered_at": datetime.now(timezone.utc).isoformat()
            }

    async def _get_matching_logs(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get the specific logs that matched the rule criteria.

        Default implementation returns all logs. Subclasses should override
        to return only the logs that actually triggered the rule.

        Args:
            logs: All log entries
            rule: Alert rule configuration

        Returns:
            List of logs that matched the rule
        """
        return logs

    async def _extract_specific_match_data(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract matcher-specific data about the match.

        Subclasses should override this to provide specific details
        about why the rule matched (e.g., threshold values, patterns found).

        Args:
            logs: Log entries that matched
            rule: Alert rule configuration

        Returns:
            Dict with matcher-specific match details
        """
        return {}

    def _parse_rule_condition(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and validate rule condition configuration.

        Args:
            rule: Alert rule configuration

        Returns:
            Dict with parsed condition parameters

        Raises:
            ValueError: If rule condition is invalid
        """
        condition_config = rule.get('condition_config', {})

        if not condition_config:
            raise ValueError(f"No condition_config found in rule {rule.get('id')}")

        # Handle JSON string format
        if isinstance(condition_config, str):
            import json
            try:
                condition_config = json.loads(condition_config)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in condition_config for rule {rule.get('id')}: {e}")

        return condition_config

    def _filter_logs_by_condition(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filter logs based on basic condition criteria.

        Handles common filtering like field values, time ranges, etc.

        Args:
            logs: Log entries to filter
            condition: Condition configuration

        Returns:
            Filtered list of logs
        """
        try:
            filtered_logs = logs

            # Filter by field value if specified
            if 'field' in condition and 'value' in condition:
                field = condition['field']
                expected_value = condition['value']

                filtered_logs = [
                    log for log in filtered_logs
                    if log.get(field) == expected_value
                ]

                self.logger.debug(f"Filtered by {field}={expected_value}: {len(filtered_logs)} logs remain")

            # Filter by level if specified
            if 'level' in condition:
                expected_level = condition['level']
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('level', '').lower() == expected_level.lower()
                ]

                self.logger.debug(f"Filtered by level={expected_level}: {len(filtered_logs)} logs remain")

            # Filter by service if specified
            if 'service' in condition:
                expected_service = condition['service']
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get('service') == expected_service
                ]

                self.logger.debug(f"Filtered by service={expected_service}: {len(filtered_logs)} logs remain")

            return filtered_logs

        except Exception as e:
            self.logger.error(f"Error filtering logs: {e}")
            return logs  # Return unfiltered logs on error

    def _evaluate_nested_condition(self, logs: List[Dict[str, Any]], condition: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """
        Evaluate nested conditions with AND/OR/NOT logic.

        Args:
            logs: Log entries to evaluate against
            condition: Condition configuration (can be nested)
            depth: Current recursion depth (max 3)

        Returns:
            Dict with evaluation results including matched logs and human-readable explanation
        """
        if depth > MAX_CONDITION_DEPTH:
            raise ValueError(f"Maximum condition nesting depth ({MAX_CONDITION_DEPTH}) exceeded")

        try:
            operator = condition.get('operator', '').upper()

            if operator == LogicalOperator.AND or operator == LogicalOperator.OR:
                return self._evaluate_logical_condition(logs, condition, depth)
            elif operator == LogicalOperator.NOT:
                return self._evaluate_not_condition(logs, condition, depth)
            else:
                # Simple field condition
                return self._evaluate_simple_condition(logs, condition)

        except Exception as e:
            self.logger.error(f"Error evaluating nested condition: {e}")
            return {
                "matched": False,
                "matched_logs": [],
                "human_readable": f"Error evaluating condition: {e}",
                "evaluation_details": {"error": str(e)}
            }

    def _evaluate_logical_condition(self, logs: List[Dict[str, Any]], condition: Dict[str, Any], depth: int) -> Dict[str, Any]:
        """Evaluate AND/OR logical conditions."""
        operator = condition.get('operator', '').upper()
        sub_conditions = condition.get('conditions', [])

        if not sub_conditions:
            return {
                "matched": False,
                "matched_logs": [],
                "human_readable": f"Empty {operator} condition",
                "evaluation_details": {"operator": operator, "sub_results": []}
            }

        sub_results = []
        human_parts = []
        all_matched_logs = set()

        for i, sub_condition in enumerate(sub_conditions):
            result = self._evaluate_nested_condition(logs, sub_condition, depth + 1)
            sub_results.append({
                "index": i,
                "matched": result["matched"],
                "human_readable": result["human_readable"],
                "matched_count": len(result["matched_logs"])
            })
            human_parts.append(f"({result['human_readable']})")

            if result["matched"]:
                all_matched_logs.update([id(log) for log in result["matched_logs"]])

        # Apply AND/OR logic
        if operator == LogicalOperator.AND:
            matched = all(result["matched"] for result in sub_results)
            human_readable = f" AND ".join(human_parts)
        else:  # OR
            matched = any(result["matched"] for result in sub_results)
            human_readable = f" OR ".join(human_parts)

        # Get actual log objects that matched
        matched_logs = [log for log in logs if id(log) in all_matched_logs] if matched else []

        return {
            "matched": matched,
            "matched_logs": matched_logs,
            "human_readable": human_readable,
            "evaluation_details": {
                "operator": operator,
                "sub_results": sub_results,
                "total_matched_logs": len(matched_logs)
            }
        }

    def _evaluate_not_condition(self, logs: List[Dict[str, Any]], condition: Dict[str, Any], depth: int) -> Dict[str, Any]:
        """Evaluate NOT logical condition."""
        sub_condition = condition.get('condition', {})

        if not sub_condition:
            return {
                "matched": False,
                "matched_logs": [],
                "human_readable": "Empty NOT condition",
                "evaluation_details": {"operator": "NOT", "sub_result": None}
            }

        result = self._evaluate_nested_condition(logs, sub_condition, depth + 1)

        # NOT inverts the result
        matched = not result["matched"]
        human_readable = f"NOT ({result['human_readable']})"

        # For NOT conditions, matched logs are those that DON'T match the sub-condition
        if matched:
            excluded_log_ids = set([id(log) for log in result["matched_logs"]])
            matched_logs = [log for log in logs if id(log) not in excluded_log_ids]
        else:
            matched_logs = []

        return {
            "matched": matched,
            "matched_logs": matched_logs,
            "human_readable": human_readable,
            "evaluation_details": {
                "operator": "NOT",
                "sub_result": {
                    "matched": result["matched"],
                    "human_readable": result["human_readable"],
                    "matched_count": len(result["matched_logs"])
                },
                "inverted_result": matched,
                "total_matched_logs": len(matched_logs)
            }
        }

    def _evaluate_simple_condition(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate simple field-based condition."""
        field = condition.get('field')
        operator = condition.get('operator', ComparisonOperator.EQ)
        value = condition.get('value')

        if not field:
            return {
                "matched": False,
                "matched_logs": [],
                "human_readable": "Missing field in condition",
                "evaluation_details": {"error": "Missing field"}
            }

        matched_logs = []

        for log in logs:
            if self._evaluate_single_log_condition(log, field, operator, value):
                matched_logs.append(log)

        human_readable = f"{field} {operator} '{value}'"

        return {
            "matched": len(matched_logs) > 0,
            "matched_logs": matched_logs,
            "human_readable": human_readable,
            "evaluation_details": {
                "field": field,
                "operator": operator,
                "value": value,
                "matched_count": len(matched_logs)
            }
        }

    def _evaluate_single_log_condition(self, log: Dict[str, Any], field: str, operator: str, value: Any) -> bool:
        """Evaluate a single condition against a single log entry."""
        log_value = log.get(field)

        if log_value is None:
            return False

        try:
            if operator == ComparisonOperator.EQ:
                return str(log_value).lower() == str(value).lower()
            elif operator == ComparisonOperator.NE:
                return str(log_value).lower() != str(value).lower()
            elif operator == ComparisonOperator.GT:
                return float(log_value) > float(value)
            elif operator == ComparisonOperator.GTE:
                return float(log_value) >= float(value)
            elif operator == ComparisonOperator.LT:
                return float(log_value) < float(value)
            elif operator == ComparisonOperator.LTE:
                return float(log_value) <= float(value)
            elif operator == ComparisonOperator.CONTAINS:
                return str(value).lower() in str(log_value).lower()
            elif operator == ComparisonOperator.STARTS_WITH:
                return str(log_value).lower().startswith(str(value).lower())
            elif operator == ComparisonOperator.ENDS_WITH:
                return str(log_value).lower().endswith(str(value).lower())
            elif operator == ComparisonOperator.IN:
                return log_value in (value if isinstance(value, list) else [value])
            elif operator == ComparisonOperator.NOT_IN:
                return log_value not in (value if isinstance(value, list) else [value])
            elif operator == ComparisonOperator.REGEX:
                import re
                return bool(re.search(str(value), str(log_value), re.IGNORECASE))
            else:
                self.logger.warning(f"Unknown operator: {operator}")
                return False

        except (ValueError, TypeError) as e:
            self.logger.debug(f"Error comparing {log_value} {operator} {value}: {e}")
            return False

    def _validate_rule_config(self, rule: Dict[str, Any]) -> bool:
        """
        Validate that rule configuration is valid for this matcher.

        Args:
            rule: Alert rule configuration

        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Check basic rule structure
            if not rule.get('id'):
                self.logger.error("Rule missing required 'id' field")
                return False

            if rule.get('rule_type') != self.get_rule_type():
                self.logger.error(f"Rule type mismatch: expected {self.get_rule_type()}, got {rule.get('rule_type')}")
                return False

            if not rule.get('condition_config'):
                self.logger.error(f"Rule {rule.get('id')} missing condition_config")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating rule config: {e}")
            return False
