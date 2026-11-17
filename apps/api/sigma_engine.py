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
from correlation import CorrelationRule, CorrelationRuleError, get_correlation_store, parse_timespan
from events.publishers.security_publisher import SecurityEventPublisher
from events.constants import EVENT_SECURITY_DETECTION_TRIGGERED
from services.high_performance_normalizer import normalize_log_fast

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


@dataclass
class CountCondition:
    """Parsed count condition from Sigma rule"""
    threshold: int
    operator: str  # 'gt', 'gte', 'lt', 'lte', 'eq'
    group_by: Optional[List[str]] = None  # Fields to group by (e.g., ['src_ip'])
    timeframe: Optional[str] = None  # e.g., '5m', '1h'

    @staticmethod
    def parse(condition: str) -> Optional['CountCondition']:
        """
        Parse a count condition string.

        Supported forms:

        Logforge-native:
            - "selection | count() > 10"
            - "selection | count(by=['src_ip']) > 5"
            - "selection | count(by=[\"src_ip\"]) > 5"

        Standard Sigma aggregation (ENH-015):
            - "count(selection) >= 10 by src_ip"
            - "selection | count() > 5 by src_ip, user"

        The standard form previously returned None, so a rule using it fell
        through to the SIMPLE evaluation path and never fired. That is how
        `packages/rules/brute_force_detection.yml` -- a shipped rule -- came to
        be silently dead.
        """
        import re

        # Pattern for count conditions.
        # Accepts an optional argument inside count(...) -- either the
        # Logforge `by=[...]` form or a bare selection name as in standard
        # Sigma -- followed by a comparison, then an optional trailing
        # `by field1, field2`.
        count_pattern = (
            r'count\s*\(\s*(?:by\s*=\s*\[(?P<by_list>[^\]]+)\]|(?P<arg>[^)]*))?\s*\)'
            r'\s*(?P<op>>=|<=|==|>|<|=)\s*(?P<threshold>\d+)'
            r'(?:\s+by\s+(?P<by_fields>[A-Za-z0-9_.,\s]+))?'
        )

        match = re.search(count_pattern, condition, re.IGNORECASE)
        if not match:
            return None

        group_by_str = match.group("by_list")
        trailing_by = match.group("by_fields")
        op_str = match.group("op")
        threshold_str = match.group("threshold")

        # Parse group_by fields
        group_by = None
        if group_by_str:
            # Remove quotes and split by comma
            fields = re.findall(r'["\']([^"\']+)["\']', group_by_str)
            if fields:
                group_by = fields
        elif trailing_by:
            # Standard Sigma: `... >= 10 by src_ip, user`
            fields = [f.strip() for f in trailing_by.split(",") if f.strip()]
            if fields:
                group_by = fields

        # Map operators
        op_map = {
            '>': 'gt',
            '>=': 'gte',
            '<': 'lt',
            '<=': 'lte',
            '==': 'eq',
            '=': 'eq'
        }
        operator = op_map.get(op_str, 'gt')

        return CountCondition(
            threshold=int(threshold_str),
            operator=operator,
            group_by=group_by
        )

    def check_threshold(self, count: int) -> bool:
        """Check if a count meets the threshold condition"""
        if self.operator == 'gt':
            return count > self.threshold
        elif self.operator == 'gte':
            return count >= self.threshold
        elif self.operator == 'lt':
            return count < self.threshold
        elif self.operator == 'lte':
            return count <= self.threshold
        elif self.operator == 'eq':
            return count == self.threshold
        return False


class SigmaFieldMatcher:
    """Handles field-level matching for Sigma rule conditions"""

    @staticmethod
    def _match_numeric_comparison(log_value: Any, rule_str: str) -> Optional[bool]:
        """
        Evaluate a comparison-style rule value such as ">1000000" (ENH-027).

        Returns:
            True/False if this IS a numeric comparison and it could be
            evaluated; None if the rule value is not a comparison, so the
            caller falls through to normal string matching.

        Returning None rather than False for non-comparisons matters: treating
        an ordinary value as a failed comparison would break every plain
        equality match.
        """
        match = re.match(r"^\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$", rule_str)
        if not match:
            return None

        operator_token, threshold_str = match.groups()

        try:
            numeric_log_value = float(str(log_value).strip())
        except (TypeError, ValueError):
            # The rule asks for a numeric comparison but the log value is not
            # numeric, so it cannot satisfy the condition.
            return False

        threshold = float(threshold_str)

        if operator_token == ">":
            return numeric_log_value > threshold
        if operator_token == ">=":
            return numeric_log_value >= threshold
        if operator_token == "<":
            return numeric_log_value < threshold
        return numeric_log_value <= threshold

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

            # ENH-039: the Sigma `|all` modifier. A list is normally an OR
            # ("any of these values"); `|all` makes it an AND ("every one of
            # these must be present").
            #
            # This matters for rules that need TWO conditions on the same
            # field -- e.g. "the process is w3wp.exe AND the command line
            # spawns a shell". Expressing that with two `command_line|contains`
            # keys is invalid YAML semantics: the duplicate mapping key is
            # silently discarded, leaving only the second condition. That
            # produced 11 broken selections in the content pack, one of which
            # degraded to "any cmd.exe" and fired on benign activity.
            require_all = False
            if operator and operator.endswith("|all"):
                require_all = True
                operator = operator[: -len("|all")] or "eq"

            # Handle list of values in rule
            if isinstance(rule_value, list):
                combine = all if require_all else any
                return combine(
                    SigmaFieldMatcher.match_field(log_value, val, operator)
                    for val in rule_value
                )

            rule_str = str(rule_value).lower()

            # ENH-027: numeric comparison values such as ">1000000" or "<=50".
            #
            # `packages/rules/data_exfiltration.yml` uses this Sigma idiom for
            # its size and duration thresholds. Without this branch the value
            # was compared as a LITERAL STRING, so `bytes_out: ">1000000"` only
            # matched a log whose bytes_out was the text ">1000000" -- meaning
            # the rule could never fire. Verified by its positive-sample test.
            if operator in ("eq", None):
                comparison = SigmaFieldMatcher._match_numeric_comparison(
                    log_value, rule_str
                )
                if comparison is not None:
                    return comparison

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
            if field_name in log_entry:
                return log_entry.get(field_name)
            # Ingestion keeps caller-supplied fields that aren't part of the
            # log model under `attrs`; rules name them as plain fields.
            attrs = log_entry.get("attrs")
            if isinstance(attrs, dict):
                return attrs.get(field_name)
            return None
        except Exception:
            return None


def _count_rule_name(rule_dict: Dict[str, Any]) -> str:
    return f"__count__:{rule_dict.get('id')}"


def _event_time(event: Dict[str, Any]) -> datetime:
    """The event's own timestamp (UTC), so windows follow event time; falls
    back to now for events without one."""
    from datetime import timezone

    for key in ("ts", "timestamp"):
        value = event.get(key)
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


class SigmaRuleEngine:
    """Main Sigma Rule Matching Engine with Subscription Integration"""

    def __init__(self):
        self.condition_evaluator = SigmaConditionEvaluator()
        # Process-wide streaming state for correlation and count() rules.
        self.correlation_store = get_correlation_store()
        self.security_publisher = None  # Initialize later when needed
        # Import here to avoid circular imports
        from services.subscription_service import SubscriptionService
        self.subscription_service = SubscriptionService()

        # High-performance matcher for pre-compiled rules
        from services.high_performance_rule_matcher import get_high_performance_matcher
        self.hp_matcher = get_high_performance_matcher()
        self._compiled_customers: set = set()  # Track which customers have compiled rules

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
                # Legacy path: normalize logs using high-performance normalizer
                logger.debug(f"🔄 Normalizing logs for rule evaluation (legacy path with fast normalizer)")
                normalized_logs = []
                for log_entry in logs:
                    normalized_log = normalize_log_fast(log_entry, customer_id)
                    normalized_logs.append((log_entry, normalized_log))

            logger.debug(f"🔄 Processing {len(normalized_logs)} logs for rule evaluation")
            if normalized_logs:
                sample_original = normalized_logs[0][0]
                sample_normalized = normalized_logs[0][1]
                logger.debug(f"🔍 Sample original: {json.dumps(sample_original, default=str)}")
                logger.debug(f"🔄 Sample normalized: {json.dumps(sample_normalized, default=str)}")

            # Separate rules: correlation rules (Sigma correlation format),
            # count() rules and per-event rules.
            count_rules = []
            simple_rules = []
            correlation_dicts = []

            for rule_dict in rules:
                if rule_dict.get('correlation'):
                    correlation_dicts.append(rule_dict)
                    continue
                detection = rule_dict.get('detection', {})
                condition = detection.get('condition', 'selection')

                # Check if this is a count-based rule
                count_condition = CountCondition.parse(condition)
                if count_condition:
                    count_rules.append((rule_dict, count_condition))
                else:
                    simple_rules.append(rule_dict)

            correlation_rules, correlation_meta = self._compile_correlations(correlation_dicts, count_rules)

            for original_log, normalized_log in normalized_logs:
                # Names of the base rules this event matched (rule `name` and
                # id), fed to the correlation engine.
                matched_names = set()

                for rule_dict in simple_rules:
                    try:
                        # Convert rule dict to SigmaRule object if needed
                        if isinstance(rule_dict, dict):
                            rule = self._dict_to_sigma_rule(rule_dict)
                        else:
                            rule = rule_dict

                        # Evaluate the rule against the normalized log
                        match_result = await self._evaluate_rule_against_normalized_log(original_log, normalized_log, rule, customer_id)

                        if match_result:
                            matched_names.add(str(rule_dict.get('id')))
                            if rule_dict.get('name'):
                                matched_names.add(str(rule_dict['name']))
                            # `generate: false` base rules only feed correlations.
                            if rule_dict.get('generate') is False:
                                continue
                            matches.append(match_result)
                            logger.info(f"🚨 Sigma rule match: {rule.id} - {rule.title}")

                            # Publish security detection event
                            await self._publish_detection_event(match_result)

                    except Exception as e:
                        logger.error(f"Error evaluating rule {rule_dict.get('id', 'unknown')}: {e}")
                        continue

                # count() rules: the selection matched -> one event for their
                # windowed event_count correlation.
                for rule_dict, _ in count_rules:
                    selection = rule_dict.get('detection', {}).get('selection') or {}
                    if selection and self.condition_evaluator.evaluate_selection(normalized_log, selection)[0]:
                        matched_names.add(_count_rule_name(rule_dict))

                if correlation_rules and matched_names:
                    alerts = self.correlation_store.process(
                        customer_id, correlation_rules, normalized_log, matched_names,
                        _event_time(normalized_log))
                    for alert in alerts:
                        match = self._correlation_match(alert, correlation_meta.get(alert.rule.id, {}),
                                                        normalized_log, customer_id)
                        matches.append(match)
                        logger.info(f"🚨 Correlation match: {alert.rule.id} - {alert.rule.title} "
                                    f"(group={alert.group}, value={alert.value})")
                        await self._publish_detection_event(match)

            return matches

        except Exception as e:
            logger.error(f"Error in Sigma rule evaluation: {e}")
            return []

    def _compile_correlations(self, correlation_dicts, count_rules):
        """Correlation rules for this batch: the tenant's Sigma correlation
        rules, plus one windowed event_count per count() rule. Invalid rules
        are skipped with a warning; the rest still run."""
        compiled: List[CorrelationRule] = []
        meta: Dict[str, Dict[str, Any]] = {}
        for rule_dict in correlation_dicts:
            try:
                data = dict(rule_dict)
                data.setdefault("level", rule_dict.get("severity") or "medium")
                rule = CorrelationRule.from_dict(data)
            except CorrelationRuleError as e:
                logger.warning(f"Skipping correlation rule {rule_dict.get('id')}: {e}")
                continue
            compiled.append(rule)
            meta[rule.id] = rule_dict
        for rule_dict, count_condition in count_rules:
            if count_condition.operator not in ("gt", "gte", "eq"):
                logger.warning(f"Skipping count rule {rule_dict.get('id')}: "
                               f"'{count_condition.operator}' can't be evaluated on a stream")
                continue
            detection = rule_dict.get("detection", {})
            try:
                timespan = parse_timespan(detection.get("timeframe") or "5m")
            except CorrelationRuleError as e:
                logger.warning(f"Skipping count rule {rule_dict.get('id')}: {e}")
                continue
            rule = CorrelationRule(
                id=str(rule_dict.get("id")), title=str(rule_dict.get("title") or ""),
                level=str(rule_dict.get("severity") or "medium"), type="event_count",
                rules=[_count_rule_name(rule_dict)], group_by=list(count_condition.group_by or []),
                timespan=timespan, operator=count_condition.operator,
                threshold=float(count_condition.threshold), tags=list(rule_dict.get("tags") or []))
            compiled.append(rule)
            meta[rule.id] = rule_dict
        return compiled, meta

    def _correlation_match(self, alert, rule_dict, log_entry, customer_id) -> SigmaMatch:
        try:
            severity = DetectionSeverity(alert.rule.level)
        except ValueError:
            severity = DetectionSeverity.MEDIUM
        techniques = list(rule_dict.get("attack_techniques") or []) or alert.rule.techniques
        return SigmaMatch(
            rule_id=alert.rule.id,
            rule_title=alert.rule.title,
            log_entry=log_entry,
            matched_fields={"_correlation": {
                "type": alert.rule.type,
                "group": alert.group,
                "value": alert.value,
                "threshold": alert.rule.threshold,
                "operator": alert.rule.operator,
                "field": alert.rule.field,
                "rules": alert.rule.rules,
                "timespan_seconds": int(alert.rule.timespan.total_seconds()),
                "first_seen": alert.first_seen.isoformat(),
                "last_seen": alert.last_seen.isoformat(),
                "events": len(alert.events),
            }},
            severity=severity,
            attack_techniques=techniques,
            kill_chain_phases=list(rule_dict.get("kill_chain_phases") or []),
            timestamp=datetime.now(),
            customer_id=customer_id,
        )

    async def _evaluate_count_rule(
        self,
        normalized_logs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
        rule_dict: Dict[str, Any],
        count_condition: CountCondition,
        customer_id: str
    ) -> List[SigmaMatch]:
        """
        Evaluate a count-based Sigma rule against a batch of logs.

        This method:
        1. Finds all logs matching the selection criteria
        2. Groups them by the specified field(s) if group_by is set
        3. Checks if any group exceeds the count threshold
        4. Creates matches for groups that exceed the threshold

        Args:
            normalized_logs: List of (original_log, normalized_log) tuples
            rule_dict: The Sigma rule dictionary
            count_condition: The parsed count condition
            customer_id: Customer/tenant ID

        Returns:
            List of SigmaMatch objects for groups that exceeded the threshold
        """
        matches = []

        try:
            rule = self._dict_to_sigma_rule(rule_dict)
            detection = rule.detection
            selection = detection.get("selection", {})

            if not selection:
                return matches

            # Collect all logs that match the selection criteria
            matching_logs = []
            for original_log, normalized_log in normalized_logs:
                selection_match, matched_fields = self.condition_evaluator.evaluate_selection(normalized_log, selection)
                if selection_match:
                    matching_logs.append((original_log, normalized_log, matched_fields))

            logger.debug(f"📊 Count rule {rule.id}: {len(matching_logs)}/{len(normalized_logs)} logs match selection")

            if not matching_logs:
                return matches

            # Group logs by the group_by field(s) if specified
            if count_condition.group_by:
                # Group by specified fields
                groups: Dict[str, List[Tuple]] = {}
                for original_log, normalized_log, matched_fields in matching_logs:
                    # Build group key from group_by fields
                    key_parts = []
                    for field in count_condition.group_by:
                        field_value = self.condition_evaluator._get_field_value(normalized_log, field)
                        if field_value is None:
                            field_value = 'unknown'
                        key_parts.append(f"{field}={field_value}")
                    group_key = "|".join(key_parts)

                    if group_key not in groups:
                        groups[group_key] = []
                    groups[group_key].append((original_log, normalized_log, matched_fields))

                logger.debug(f"📊 Count rule {rule.id}: Grouped into {len(groups)} groups by {count_condition.group_by}")

                # Check each group against the threshold
                for group_key, group_logs in groups.items():
                    count = len(group_logs)
                    if count_condition.check_threshold(count):
                        # Use the last log in the group as the representative log
                        _, representative_log, matched_fields = group_logs[-1]

                        # Add count info to matched fields
                        matched_fields['_count'] = {
                            'value': count,
                            'threshold': count_condition.threshold,
                            'operator': count_condition.operator,
                            'group_by': count_condition.group_by,
                            'group_key': group_key
                        }

                        match = SigmaMatch(
                            rule_id=rule.id,
                            rule_title=rule.title,
                            log_entry=representative_log,
                            matched_fields=matched_fields,
                            severity=rule.severity,
                            attack_techniques=[tech.value for tech in rule.attack_techniques],
                            kill_chain_phases=rule.kill_chain_phases,
                            timestamp=datetime.now(),
                            customer_id=customer_id
                        )
                        matches.append(match)

                        logger.info(f"🚨 Count rule match: {rule.id} - {rule.title} (group={group_key}, count={count} > {count_condition.threshold})")

                        # Publish security detection event
                        await self._publish_detection_event(match)
            else:
                # No group_by - count all matching logs
                count = len(matching_logs)
                if count_condition.check_threshold(count):
                    # Use the last log as the representative log
                    _, representative_log, matched_fields = matching_logs[-1]

                    # Add count info to matched fields
                    matched_fields['_count'] = {
                        'value': count,
                        'threshold': count_condition.threshold,
                        'operator': count_condition.operator
                    }

                    match = SigmaMatch(
                        rule_id=rule.id,
                        rule_title=rule.title,
                        log_entry=representative_log,
                        matched_fields=matched_fields,
                        severity=rule.severity,
                        attack_techniques=[tech.value for tech in rule.attack_techniques],
                        kill_chain_phases=rule.kill_chain_phases,
                        timestamp=datetime.now(),
                        customer_id=customer_id
                    )
                    matches.append(match)

                    logger.info(f"🚨 Count rule match: {rule.id} - {rule.title} (total count={count} > {count_condition.threshold})")

                    # Publish security detection event
                    await self._publish_detection_event(match)
                else:
                    logger.debug(f"📊 Count rule {rule.id}: count={count} does not exceed threshold={count_condition.threshold}")

            return matches

        except Exception as e:
            logger.error(f"Error in count rule evaluation for {rule_dict.get('id', 'unknown')}: {e}")
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

            # ENH-015: evaluate EVERY selection block the rule defines, not just
            # `selection` and `filter`. A rule may define selection1/selection2/
            # filter_a/... and combine them arbitrarily in its condition, and
            # `1 of them` / `all of them` need the full set to resolve against.
            #
            # `condition` is the only reserved key in a Sigma detection block;
            # everything else is a named selection.
            selection_blocks = {
                name: block
                for name, block in detection.items()
                if name != "condition" and isinstance(block, (dict, list))
            }

            if not selection_blocks:
                logger.warning(f"Rule {rule.id} has no selection criteria")
                return None

            selection_results: Dict[str, bool] = {}
            matched_fields: Dict[str, Any] = {}

            for name, block in selection_blocks.items():
                block_match, block_fields = self.condition_evaluator.evaluate_selection(
                    normalized_log, block
                )
                selection_results[name] = block_match
                if block_match:
                    # Record which fields matched, namespaced by selection so a
                    # multi-selection rule produces attributable evidence.
                    for field_name, detail in block_fields.items():
                        matched_fields[f"{name}.{field_name}"] = detail

            # Check condition logic across all selections.
            condition = detection.get("condition", "selection")
            if not self._evaluate_condition_logic(
                condition, selection_results, rule_id=rule.id
            ):
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


    def _evaluate_condition_logic(
        self,
        condition: str,
        selection_results: Dict[str, bool],
        rule_id: str = "unknown",
    ) -> bool:
        """
        Evaluate a Sigma condition against pre-computed selection results.

        ENH-015: this previously implemented almost none of the Sigma grammar.
        `"and not filter"` returned `selection_match` while IGNORING the filter,
        so rules fired on exactly the traffic they were written to exclude; and
        every other condition -- `selection1 or selection2`, `1 of them`,
        `all of them`, any negation -- fell through to `return selection_match`.
        Detections were therefore wrong in both directions.

        Parsing now happens in `sigma_condition.py` against the real grammar.

        Args:
            condition: the rule's condition string.
            selection_results: {selection_name: matched} for every selection
                block the rule defines.
            rule_id: for diagnostics.

        Returns:
            bool: whether the condition is satisfied. An unparseable condition
            returns False -- a rule we cannot understand must never be treated
            as matching, because that would fabricate detections.
        """
        from sigma_condition import SigmaConditionError, evaluate_condition

        try:
            return evaluate_condition(condition, selection_results)
        except SigmaConditionError as exc:
            # Do not fire on a rule we cannot parse. Logged at error level so
            # broken rule content is visible rather than silently inert.
            logger.error(
                f"Cannot evaluate condition for rule {rule_id}: {exc}. "
                "Rule skipped (no detection emitted)."
            )
            return False

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

            # Use high-performance matcher with pre-compiled rules
            return await self._evaluate_logs_fast(logs, tenant_rules, customer_id)

        except Exception as e:
            logger.error(f"Error in subscription-aware sigma evaluation for {customer_id}: {e}")
            return []

    async def _evaluate_logs_fast(
        self,
        logs: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        customer_id: str
    ) -> List[SigmaMatch]:
        """
        HIGH-PERFORMANCE: Evaluate logs using pre-compiled rules.

        Optimizations:
        1. Rules compiled once per customer (not per-log)
        2. Pre-compiled regex patterns
        3. Field-based rule filtering (skip inapplicable rules)
        4. Pre-computed lowercase strings

        Expected: 10-50x faster than standard evaluation
        """
        matches = []
        start_time = time.time()

        try:
            # Compile rules for this customer if not already done
            if customer_id not in self._compiled_customers:
                compile_start = time.time()
                self.hp_matcher.compile_rules(rules, customer_id)
                self._compiled_customers.add(customer_id)
                compile_time_ms = (time.time() - compile_start) * 1000
                logger.info(f"⚡ Compiled {len(rules)} rules for customer {customer_id} in {compile_time_ms:.2f}ms")

            # Separate count rules (need batch processing) from simple rules
            count_rules = self.hp_matcher.get_count_rules(customer_id)
            has_count_rules = len(count_rules) > 0

            # FAST PATH: Evaluate simple rules using pre-compiled matcher
            for log in logs:
                log_matches = self.hp_matcher.match_log(log, customer_id)

                for compiled_rule, matched_fields in log_matches:
                    # Create SigmaMatch from compiled rule
                    match = SigmaMatch(
                        rule_id=compiled_rule.rule_id,
                        rule_title=compiled_rule.title,
                        log_entry=log,
                        matched_fields=matched_fields,
                        severity=DetectionSeverity(compiled_rule.severity),
                        attack_techniques=compiled_rule.attack_techniques,
                        kill_chain_phases=compiled_rule.kill_chain_phases,
                        timestamp=datetime.now(),
                        customer_id=customer_id
                    )
                    matches.append(match)

                    logger.info(f"🚨 FAST Sigma match: {compiled_rule.rule_id} - {compiled_rule.title}")

                    # Publish security detection event
                    await self._publish_detection_event(match)

            # BATCH PATH: Evaluate count-based rules if any
            if has_count_rules:
                for compiled_rule in count_rules:
                    count_matches = await self._evaluate_count_rule_fast(
                        logs, compiled_rule, customer_id
                    )
                    matches.extend(count_matches)

            # Log performance stats
            eval_time_ms = (time.time() - start_time) * 1000
            matcher_stats = self.hp_matcher.get_stats()

            logger.info(
                f"⚡ FAST evaluation completed: {len(logs)} logs, {len(matches)} matches "
                f"in {eval_time_ms:.2f}ms ({eval_time_ms/len(logs):.3f}ms/log) | "
                f"Rules skipped by field filter: {matcher_stats.get('rules_skipped_by_field_filter', 0)}"
            )

            return matches

        except Exception as e:
            logger.error(f"Error in fast sigma evaluation for {customer_id}: {e}")
            # Fallback to standard evaluation
            logger.warning(f"Falling back to standard evaluation for {customer_id}")
            return await self.evaluate_logs_against_rules(logs, rules, customer_id, logs_normalized=True)

    async def _evaluate_count_rule_fast(
        self,
        logs: List[Dict[str, Any]],
        compiled_rule,
        customer_id: str
    ) -> List[SigmaMatch]:
        """Evaluate a count-based rule using pre-compiled conditions."""
        matches = []

        try:
            # Get selection from compiled rule
            selection = compiled_rule.selections.get('selection')
            if not selection:
                return matches

            # Find logs matching the selection
            matching_logs = []
            for log in logs:
                # Check if log has required fields
                log_fields = self.hp_matcher.available_fields(log)
                if not selection.required_fields.issubset(log_fields):
                    continue

                # Evaluate selection conditions
                all_match = True
                matched_fields = {}

                for condition in selection.conditions:
                    log_value = self.hp_matcher._get_field_value(log, condition.field_name)
                    if not self.hp_matcher._match_condition(log_value, condition):
                        all_match = False
                        break
                    matched_fields[condition.field_name] = log_value

                if all_match:
                    matching_logs.append((log, matched_fields))

            if not matching_logs:
                return matches

            # Apply count logic
            threshold = compiled_rule.count_threshold or 0
            operator = compiled_rule.count_operator or 'gt'
            group_by = compiled_rule.count_group_by

            if group_by:
                # Group by specified fields
                from collections import defaultdict
                groups: Dict[str, List] = defaultdict(list)

                for log, matched_fields in matching_logs:
                    key_parts = [
                        f"{f}={self.hp_matcher._get_field_value(log, f) or 'unknown'}"
                        for f in group_by
                    ]
                    group_key = "|".join(key_parts)
                    groups[group_key].append((log, matched_fields))

                # Check each group
                for group_key, group_logs in groups.items():
                    count = len(group_logs)
                    if self._check_count_threshold(count, threshold, operator):
                        log, matched_fields = group_logs[-1]
                        matched_fields['_count'] = {
                            'value': count,
                            'threshold': threshold,
                            'operator': operator,
                            'group_key': group_key
                        }

                        match = SigmaMatch(
                            rule_id=compiled_rule.rule_id,
                            rule_title=compiled_rule.title,
                            log_entry=log,
                            matched_fields=matched_fields,
                            severity=DetectionSeverity(compiled_rule.severity),
                            attack_techniques=compiled_rule.attack_techniques,
                            kill_chain_phases=compiled_rule.kill_chain_phases,
                            timestamp=datetime.now(),
                            customer_id=customer_id
                        )
                        matches.append(match)
                        await self._publish_detection_event(match)

                        logger.info(f"🚨 Count rule match: {compiled_rule.rule_id} (group={group_key}, count={count})")
            else:
                # No group by - count all
                count = len(matching_logs)
                if self._check_count_threshold(count, threshold, operator):
                    log, matched_fields = matching_logs[-1]
                    matched_fields['_count'] = {
                        'value': count,
                        'threshold': threshold,
                        'operator': operator
                    }

                    match = SigmaMatch(
                        rule_id=compiled_rule.rule_id,
                        rule_title=compiled_rule.title,
                        log_entry=log,
                        matched_fields=matched_fields,
                        severity=DetectionSeverity(compiled_rule.severity),
                        attack_techniques=compiled_rule.attack_techniques,
                        kill_chain_phases=compiled_rule.kill_chain_phases,
                        timestamp=datetime.now(),
                        customer_id=customer_id
                    )
                    matches.append(match)
                    await self._publish_detection_event(match)

                    logger.info(f"🚨 Count rule match: {compiled_rule.rule_id} (count={count})")

            return matches

        except Exception as e:
            logger.error(f"Error evaluating count rule {compiled_rule.rule_id}: {e}")
            return []

    def _check_count_threshold(self, count: int, threshold: int, operator: str) -> bool:
        """Check if count meets threshold condition."""
        if operator == 'gt':
            return count > threshold
        elif operator == 'gte':
            return count >= threshold
        elif operator == 'lt':
            return count < threshold
        elif operator == 'lte':
            return count <= threshold
        elif operator == 'eq':
            return count == threshold
        return False

    def invalidate_compiled_rules(self, customer_id: str):
        """Invalidate compiled rules for a customer (call on rule cache update)."""
        if customer_id in self._compiled_customers:
            self.hp_matcher.clear_customer_rules(customer_id)
            self._compiled_customers.discard(customer_id)
            logger.info(f"Invalidated compiled rules for customer {customer_id}")


# Singleton instance for use across the application.
#
# ENH-004/ENH-010: constructing this at import time built a SubscriptionService
# -> SubscriptionDAO -> DatabaseLayer chain, opening a ClickHouse connection
# during `import sigma_engine`. That made the detection engine untestable
# without live infrastructure. It is now built on first use.
#
# Every consumer already imports this lazily inside a function
# (sigma_rule_cache.py:358/382, security_handler.py:182), so the PEP 562 module
# __getattr__ below keeps the `from sigma_engine import sigma_engine` spelling
# working unchanged.
_sigma_engine_instance: Optional["SigmaRuleEngine"] = None


def get_sigma_engine() -> "SigmaRuleEngine":
    """Get the shared SigmaRuleEngine, constructing it on first use."""
    global _sigma_engine_instance
    if _sigma_engine_instance is None:
        _sigma_engine_instance = SigmaRuleEngine()
    return _sigma_engine_instance


def __getattr__(name: str):
    """Preserve `from sigma_engine import sigma_engine` without connecting at import."""
    if name == "sigma_engine":
        return get_sigma_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
