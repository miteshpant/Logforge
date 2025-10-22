"""
Threshold Matcher

Matches threshold-based alert rules (e.g., error count > 10, response time > 500ms).
"""

from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from .base_matcher import BaseAlertMatcher

logger = logging.getLogger(__name__)

class ThresholdMatcher(BaseAlertMatcher):
    """
    Matches threshold-based alert rules.
    
    Supports various threshold operations:
    - Count thresholds: Number of logs matching criteria exceeds threshold
    - Value thresholds: Numeric field values exceed threshold
    - Rate thresholds: Rate of occurrence over time period
    
    Example rule configuration:
    {
        "rule_type": "threshold",
        "condition_config": {
            "field": "level",
            "value": "error", 
            "threshold": 10,
            "operator": "gt",  # gt, gte, lt, lte, eq, ne
            "time_window_minutes": 5,
            "threshold_type": "count"  # count, value, rate
        }
    }
    """
    
    def get_rule_type(self) -> str:
        """Return the rule type this matcher handles."""
        return "threshold"
    
    async def matches(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> bool:
        """
        Check if logs match the threshold rule.
        
        Args:
            logs: List of log entries to check
            rule: Alert rule configuration
            
        Returns:
            bool: True if threshold is exceeded, False otherwise
        """
        try:
            if not self._validate_rule_config(rule):
                return False
            
            condition_config = self._parse_rule_condition(rule)
            
            # Check if this is a nested condition (new format) or simple threshold (old format)
            if 'operator' in condition_config and condition_config.get('operator') in ['AND', 'OR', 'NOT']:
                # New nested condition format - use base matcher evaluation
                self.logger.debug(f"Evaluating threshold rule {rule.get('id')} with nested conditions")
                condition_result = self._evaluate_nested_condition(logs, condition_config)
                
                # For threshold rules with nested conditions, we just check if any logs match the condition
                # The threshold logic can be added here if needed (e.g., minimum count of matching logs)
                return condition_result.get('matched', False)
            else:
                # Old simple threshold format - use legacy threshold logic
                threshold_type = condition_config.get('threshold_type', 'count')
                
                self.logger.debug(f"Evaluating threshold rule {rule.get('id')} with type {threshold_type}")
                
                if threshold_type == 'count':
                    return await self._evaluate_count_threshold(logs, condition_config)
                elif threshold_type == 'value':
                    return await self._evaluate_value_threshold(logs, condition_config)
                elif threshold_type == 'rate':
                    return await self._evaluate_rate_threshold(logs, condition_config)
                else:
                    self.logger.error(f"Unknown threshold type: {threshold_type}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating threshold rule {rule.get('id')}: {e}")
            return False
    
    async def _evaluate_count_threshold(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate count-based threshold (e.g., error count > 10).
        
        Args:
            logs: Log entries to evaluate
            condition: Threshold condition configuration
            
        Returns:
            bool: True if count threshold is exceeded
        """
        try:
            # Filter logs based on condition criteria
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            
            # Apply time window if specified
            time_window_minutes = condition.get('time_window_minutes')
            if time_window_minutes:
                filtered_logs = self._filter_logs_by_time_window(filtered_logs, time_window_minutes)
            
            actual_count = len(filtered_logs)
            threshold = condition.get('threshold', 0)
            operator = condition.get('operator', 'gt')
            
            result = self._compare_values(actual_count, threshold, operator)
            
            self.logger.debug(
                f"Count threshold evaluation: {actual_count} {operator} {threshold} = {result} "
                f"(filtered from {len(logs)} logs, time_window={time_window_minutes}min)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error evaluating count threshold: {e}")
            return False
    
    async def _evaluate_value_threshold(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate value-based threshold (e.g., response_time > 500).
        
        Args:
            logs: Log entries to evaluate
            condition: Threshold condition configuration
            
        Returns:
            bool: True if value threshold is exceeded
        """
        try:
            threshold_field = condition.get('threshold_field')
            if not threshold_field:
                self.logger.error("No threshold_field specified for value threshold")
                return False
            
            # Filter logs based on basic condition criteria
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            
            # Apply time window if specified
            time_window_minutes = condition.get('time_window_minutes')
            if time_window_minutes:
                filtered_logs = self._filter_logs_by_time_window(filtered_logs, time_window_minutes)
            
            # Extract numeric values from the threshold field
            values = []
            for log in filtered_logs:
                try:
                    value = self._extract_numeric_value(log, threshold_field)
                    if value is not None:
                        values.append(value)
                except (ValueError, TypeError):
                    continue
            
            if not values:
                self.logger.debug(f"No numeric values found for field {threshold_field}")
                return False
            
            # Apply aggregation function
            aggregation = condition.get('aggregation', 'max')
            aggregated_value = self._aggregate_values(values, aggregation)
            
            threshold = condition.get('threshold', 0)
            operator = condition.get('operator', 'gt')
            
            result = self._compare_values(aggregated_value, threshold, operator)
            
            self.logger.debug(
                f"Value threshold evaluation: {aggregation}({threshold_field})={aggregated_value} {operator} {threshold} = {result} "
                f"(from {len(values)} values, {len(filtered_logs)} logs)"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error evaluating value threshold: {e}")
            return False
    
    async def _evaluate_rate_threshold(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate rate-based threshold (e.g., errors per minute > 5).
        
        Args:
            logs: Log entries to evaluate
            condition: Threshold condition configuration
            
        Returns:
            bool: True if rate threshold is exceeded
        """
        try:
            time_window_minutes = condition.get('time_window_minutes', 5)
            
            # Filter logs based on condition criteria
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            
            # Apply time window
            windowed_logs = self._filter_logs_by_time_window(filtered_logs, time_window_minutes)
            
            # Calculate rate (events per minute)
            event_count = len(windowed_logs)
            rate = event_count / time_window_minutes if time_window_minutes > 0 else 0
            
            threshold = condition.get('threshold', 0)
            operator = condition.get('operator', 'gt')
            
            result = self._compare_values(rate, threshold, operator)
            
            self.logger.debug(
                f"Rate threshold evaluation: {event_count} events / {time_window_minutes} min = {rate:.2f} {operator} {threshold} = {result}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error evaluating rate threshold: {e}")
            return False
    
    def _filter_logs_by_time_window(self, logs: List[Dict[str, Any]], time_window_minutes: int) -> List[Dict[str, Any]]:
        """
        Filter logs to only include those within the specified time window.
        
        Args:
            logs: Log entries to filter
            time_window_minutes: Time window in minutes from now
            
        Returns:
            Filtered list of logs within time window
        """
        try:
            if time_window_minutes <= 0:
                return logs
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)
            
            windowed_logs = []
            for log in logs:
                log_time = log.get('ts')
                
                # Convert string timestamps to datetime if needed
                if isinstance(log_time, str):
                    try:
                        log_time = datetime.fromisoformat(log_time.replace('Z', '+00:00'))
                    except:
                        continue
                elif not isinstance(log_time, datetime):
                    continue
                
                if log_time >= cutoff_time:
                    windowed_logs.append(log)
            
            self.logger.debug(f"Time window filter: {len(windowed_logs)}/{len(logs)} logs within {time_window_minutes} minutes")
            return windowed_logs
            
        except Exception as e:
            self.logger.error(f"Error filtering logs by time window: {e}")
            return logs
    
    def _extract_numeric_value(self, log: Dict[str, Any], field: str) -> float:
        """
        Extract numeric value from log field, handling various formats.
        
        Args:
            log: Log entry
            field: Field name to extract value from
            
        Returns:
            float: Numeric value
            
        Raises:
            ValueError: If value cannot be converted to float
        """
        value = log.get(field)
        
        if value is None:
            raise ValueError(f"Field {field} not found in log")
        
        # Handle nested fields (e.g., "attrs.response_time")
        if '.' in field:
            parts = field.split('.')
            current = log
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    raise ValueError(f"Cannot access nested field {field}")
            value = current
        
        # Convert to float
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Try to extract numeric value from string
            try:
                return float(value)
            except ValueError:
                # Handle units (e.g., "500ms", "2.5s")
                import re
                match = re.search(r'(\d+\.?\d*)', value)
                if match:
                    return float(match.group(1))
                else:
                    raise ValueError(f"Cannot extract numeric value from {value}")
        else:
            raise ValueError(f"Cannot convert {type(value)} to numeric value")
    
    def _aggregate_values(self, values: List[float], aggregation: str) -> float:
        """
        Apply aggregation function to list of values.
        
        Args:
            values: List of numeric values
            aggregation: Aggregation function (max, min, avg, sum, count)
            
        Returns:
            float: Aggregated value
        """
        if not values:
            return 0.0
        
        if aggregation == 'max':
            return max(values)
        elif aggregation == 'min':
            return min(values)
        elif aggregation == 'avg' or aggregation == 'average':
            return sum(values) / len(values)
        elif aggregation == 'sum':
            return sum(values)
        elif aggregation == 'count':
            return float(len(values))
        else:
            self.logger.warning(f"Unknown aggregation function {aggregation}, using max")
            return max(values)
    
    def _compare_values(self, actual: float, threshold: float, operator: str) -> bool:
        """
        Compare actual value with threshold using specified operator.
        
        Args:
            actual: Actual value
            threshold: Threshold value to compare against
            operator: Comparison operator (gt, gte, lt, lte, eq, ne)
            
        Returns:
            bool: Result of comparison
        """
        if operator == 'gt':
            return actual > threshold
        elif operator == 'gte':
            return actual >= threshold
        elif operator == 'lt':
            return actual < threshold
        elif operator == 'lte':
            return actual <= threshold
        elif operator == 'eq':
            return actual == threshold
        elif operator == 'ne':
            return actual != threshold
        else:
            self.logger.warning(f"Unknown operator {operator}, using gt")
            return actual > threshold
    
    async def _get_matching_logs(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get the specific logs that matched the threshold criteria."""
        try:
            condition = self._parse_rule_condition(rule)
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            
            # Apply time window if specified
            time_window_minutes = condition.get('time_window_minutes')
            if time_window_minutes:
                filtered_logs = self._filter_logs_by_time_window(filtered_logs, time_window_minutes)
            
            return filtered_logs
            
        except Exception as e:
            self.logger.error(f"Error getting matching logs: {e}")
            return []
    
    async def _extract_specific_match_data(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
        """Extract threshold-specific match data."""
        try:
            condition = self._parse_rule_condition(rule)
            threshold_type = condition.get('threshold_type', 'count')
            
            matching_logs = await self._get_matching_logs(logs, rule)
            
            match_data = {
                "threshold_type": threshold_type,
                "threshold_value": condition.get('threshold'),
                "operator": condition.get('operator', 'gt'),
                "time_window_minutes": condition.get('time_window_minutes'),
                "matching_logs_count": len(matching_logs)
            }
            
            if threshold_type == 'count':
                match_data["actual_count"] = len(matching_logs)
                
            elif threshold_type == 'value':
                threshold_field = condition.get('threshold_field')
                aggregation = condition.get('aggregation', 'max')
                
                values = []
                for log in matching_logs:
                    try:
                        value = self._extract_numeric_value(log, threshold_field)
                        if value is not None:
                            values.append(value)
                    except:
                        continue
                
                if values:
                    match_data.update({
                        "threshold_field": threshold_field,
                        "aggregation": aggregation,
                        "actual_value": self._aggregate_values(values, aggregation),
                        "value_count": len(values),
                        "values_sample": values[:10]  # First 10 values
                    })
                    
            elif threshold_type == 'rate':
                time_window = condition.get('time_window_minutes', 5)
                rate = len(matching_logs) / time_window if time_window > 0 else 0
                match_data.update({
                    "actual_rate": rate,
                    "rate_unit": "events_per_minute"
                })
            
            return match_data
            
        except Exception as e:
            self.logger.error(f"Error extracting threshold match data: {e}")
            return {"error": str(e)}