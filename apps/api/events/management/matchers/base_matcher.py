"""
Base Matcher Interface

Abstract base class for alert rule matchers following the Alert Matching System Plan.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

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
            
            return {
                "rule_type": self.get_rule_type(),
                "rule_id": rule.get('id'),
                "rule_name": rule.get('name', 'Unknown Rule'),
                "matched_logs_count": len(matching_logs),
                "sample_logs": matching_logs[:5],  # First 5 matching logs as samples
                "time_window": {
                    "start": min([log.get('ts', datetime.now(timezone.utc)) for log in matching_logs]) if matching_logs else None,
                    "end": max([log.get('ts', datetime.now(timezone.utc)) for log in matching_logs]) if matching_logs else None
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