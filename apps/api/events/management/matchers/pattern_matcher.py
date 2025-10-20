"""
Pattern Matcher

Matches pattern-based alert rules (e.g., specific log patterns, regex matching, keyword detection).
"""

import re
from typing import List, Dict, Any, Pattern
from datetime import datetime, timezone
import logging

from .base_matcher import BaseAlertMatcher

logger = logging.getLogger(__name__)

class PatternMatcher(BaseAlertMatcher):
    """
    Matches pattern-based alert rules.
    
    Supports various pattern matching strategies:
    - Regex patterns: Regular expression matching against log fields
    - Keyword matching: Simple keyword presence/absence
    - Phrase matching: Exact phrase matching with case sensitivity options
    - Multi-field patterns: Patterns across multiple log fields
    
    Example rule configuration:
    {
        "rule_type": "pattern",
        "condition_config": {
            "pattern_type": "regex",  # regex, keyword, phrase, multi_field
            "pattern": "error.*database.*timeout",
            "fields": ["msg", "error"],  # Fields to search in
            "case_sensitive": false,
            "match_type": "any",  # any, all (for multiple patterns)
            "patterns": ["error", "exception", "failed"]  # For multiple patterns
        }
    }
    """
    
    def __init__(self):
        """Initialize pattern matcher with compiled regex cache."""
        super().__init__()
        self._regex_cache = {}  # Cache compiled regex patterns
    
    def get_rule_type(self) -> str:
        """Return the rule type this matcher handles."""
        return "pattern"
    
    async def matches(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> bool:
        """
        Check if logs match the pattern rule.
        
        Args:
            logs: List of log entries to check
            rule: Alert rule configuration
            
        Returns:
            bool: True if pattern is found, False otherwise
        """
        try:
            if not self._validate_rule_config(rule):
                return False
            
            condition = self._parse_rule_condition(rule)
            pattern_type = condition.get('pattern_type', 'regex')
            
            self.logger.debug(f"Evaluating pattern rule {rule.get('id')} with type {pattern_type}")
            
            # Filter logs by basic criteria first
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            
            if not filtered_logs:
                return False
            
            if pattern_type == 'regex':
                return await self._evaluate_regex_pattern(filtered_logs, condition)
            elif pattern_type == 'keyword':
                return await self._evaluate_keyword_pattern(filtered_logs, condition)
            elif pattern_type == 'phrase':
                return await self._evaluate_phrase_pattern(filtered_logs, condition)
            elif pattern_type == 'multi_field':
                return await self._evaluate_multi_field_pattern(filtered_logs, condition)
            else:
                self.logger.error(f"Unknown pattern type: {pattern_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating pattern rule {rule.get('id')}: {e}")
            return False
    
    async def _evaluate_regex_pattern(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate regex pattern matching.
        
        Args:
            logs: Log entries to evaluate
            condition: Pattern condition configuration
            
        Returns:
            bool: True if regex pattern is found
        """
        try:
            pattern = condition.get('pattern')
            if not pattern:
                self.logger.error("No pattern specified for regex matching")
                return False
            
            # Get compiled regex with flags
            regex = self._get_compiled_regex(pattern, condition)
            fields = condition.get('fields', ['msg'])
            
            # Search for pattern in specified fields
            for log in logs:
                for field in fields:
                    field_value = self._get_field_value(log, field)
                    if field_value and regex.search(field_value):
                        self.logger.debug(f"Regex pattern '{pattern}' found in {field}: {field_value[:100]}...")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating regex pattern: {e}")
            return False
    
    async def _evaluate_keyword_pattern(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate keyword pattern matching.
        
        Args:
            logs: Log entries to evaluate
            condition: Pattern condition configuration
            
        Returns:
            bool: True if keywords are found according to match_type
        """
        try:
            # Support both single pattern and multiple patterns
            patterns = condition.get('patterns', [])
            single_pattern = condition.get('pattern')
            
            if single_pattern and single_pattern not in patterns:
                patterns.append(single_pattern)
            
            if not patterns:
                self.logger.error("No patterns specified for keyword matching")
                return False
            
            fields = condition.get('fields', ['msg'])
            case_sensitive = condition.get('case_sensitive', False)
            match_type = condition.get('match_type', 'any')  # any or all
            
            # Convert patterns to lowercase if case insensitive
            if not case_sensitive:
                patterns = [p.lower() for p in patterns]
            
            found_patterns = set()
            
            # Search for keywords in specified fields
            for log in logs:
                for field in fields:
                    field_value = self._get_field_value(log, field)
                    if not field_value:
                        continue
                    
                    if not case_sensitive:
                        field_value = field_value.lower()
                    
                    for pattern in patterns:
                        if pattern in field_value:
                            found_patterns.add(pattern)
                            self.logger.debug(f"Keyword '{pattern}' found in {field}")
                            
                            # For 'any' match type, we can return immediately
                            if match_type == 'any':
                                return True
            
            # For 'all' match type, check if all patterns were found
            if match_type == 'all':
                return len(found_patterns) == len(patterns)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating keyword pattern: {e}")
            return False
    
    async def _evaluate_phrase_pattern(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate exact phrase pattern matching.
        
        Args:
            logs: Log entries to evaluate
            condition: Pattern condition configuration
            
        Returns:
            bool: True if exact phrase is found
        """
        try:
            pattern = condition.get('pattern')
            if not pattern:
                self.logger.error("No pattern specified for phrase matching")
                return False
            
            fields = condition.get('fields', ['msg'])
            case_sensitive = condition.get('case_sensitive', False)
            
            search_pattern = pattern if case_sensitive else pattern.lower()
            
            # Search for exact phrase in specified fields
            for log in logs:
                for field in fields:
                    field_value = self._get_field_value(log, field)
                    if not field_value:
                        continue
                    
                    if not case_sensitive:
                        field_value = field_value.lower()
                    
                    if search_pattern in field_value:
                        self.logger.debug(f"Phrase '{pattern}' found in {field}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating phrase pattern: {e}")
            return False
    
    async def _evaluate_multi_field_pattern(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate multi-field pattern matching (patterns across different fields).
        
        Args:
            logs: Log entries to evaluate
            condition: Pattern condition configuration
            
        Returns:
            bool: True if multi-field pattern criteria are met
        """
        try:
            field_patterns = condition.get('field_patterns', {})
            if not field_patterns:
                self.logger.error("No field_patterns specified for multi-field matching")
                return False
            
            match_type = condition.get('match_type', 'all')  # all fields must match per log
            case_sensitive = condition.get('case_sensitive', False)
            
            # Check each log for multi-field pattern match
            for log in logs:
                field_matches = 0
                
                for field, pattern in field_patterns.items():
                    field_value = self._get_field_value(log, field)
                    if not field_value:
                        continue
                    
                    if not case_sensitive:
                        field_value = field_value.lower()
                        pattern = pattern.lower()
                    
                    # Check if pattern matches in this field
                    if isinstance(pattern, str):
                        if pattern in field_value:
                            field_matches += 1
                    elif isinstance(pattern, dict) and pattern.get('regex'):
                        # Support regex in multi-field patterns
                        try:
                            regex = self._get_compiled_regex(pattern['regex'], {'case_sensitive': case_sensitive})
                            if regex.search(field_value):
                                field_matches += 1
                        except:
                            continue
                
                # Check if match criteria are met for this log
                if match_type == 'all' and field_matches == len(field_patterns):
                    self.logger.debug(f"Multi-field pattern matched all {field_matches} fields")
                    return True
                elif match_type == 'any' and field_matches > 0:
                    self.logger.debug(f"Multi-field pattern matched {field_matches} fields")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating multi-field pattern: {e}")
            return False
    
    def _get_compiled_regex(self, pattern: str, condition: Dict[str, Any]) -> Pattern:
        """
        Get compiled regex pattern with appropriate flags, using cache.
        
        Args:
            pattern: Regex pattern string
            condition: Condition configuration for flags
            
        Returns:
            Compiled regex pattern
        """
        case_sensitive = condition.get('case_sensitive', False)
        
        # Create cache key
        cache_key = f"{pattern}:{case_sensitive}"
        
        if cache_key in self._regex_cache:
            return self._regex_cache[cache_key]
        
        # Compile regex with appropriate flags
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            compiled_regex = re.compile(pattern, flags)
            self._regex_cache[cache_key] = compiled_regex
            return compiled_regex
        except re.error as e:
            self.logger.error(f"Invalid regex pattern '{pattern}': {e}")
            # Return a pattern that never matches
            return re.compile(r'(?!.*)')
    
    def _get_field_value(self, log: Dict[str, Any], field: str) -> str:
        """
        Get string value from log field, handling nested fields and type conversion.
        
        Args:
            log: Log entry
            field: Field name (supports dot notation for nested fields)
            
        Returns:
            String value of the field, or empty string if not found
        """
        try:
            # Handle nested fields (e.g., "attrs.error_message")
            if '.' in field:
                parts = field.split('.')
                current = log
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return ""
                value = current
            else:
                value = log.get(field)
            
            # Convert to string
            if value is None:
                return ""
            elif isinstance(value, str):
                return value
            elif isinstance(value, (int, float, bool)):
                return str(value)
            elif isinstance(value, dict):
                # For dict values, search in the JSON representation
                import json
                return json.dumps(value)
            elif isinstance(value, list):
                # For list values, join with spaces
                return " ".join(str(item) for item in value)
            else:
                return str(value)
                
        except Exception as e:
            self.logger.debug(f"Error getting field value for {field}: {e}")
            return ""
    
    async def _get_matching_logs(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get the specific logs that matched the pattern criteria."""
        try:
            condition = self._parse_rule_condition(rule)
            pattern_type = condition.get('pattern_type', 'regex')
            
            # Filter logs by basic criteria first
            filtered_logs = self._filter_logs_by_condition(logs, condition)
            matching_logs = []
            
            for log in filtered_logs:
                # Check if this specific log matches the pattern
                if await self._log_matches_pattern(log, condition, pattern_type):
                    matching_logs.append(log)
            
            return matching_logs
            
        except Exception as e:
            self.logger.error(f"Error getting matching logs: {e}")
            return []
    
    async def _log_matches_pattern(self, log: Dict[str, Any], condition: Dict[str, Any], pattern_type: str) -> bool:
        """Check if a single log matches the pattern."""
        try:
            if pattern_type == 'regex':
                pattern = condition.get('pattern')
                if not pattern:
                    return False
                regex = self._get_compiled_regex(pattern, condition)
                fields = condition.get('fields', ['msg'])
                
                for field in fields:
                    field_value = self._get_field_value(log, field)
                    if field_value and regex.search(field_value):
                        return True
                        
            elif pattern_type in ['keyword', 'phrase']:
                patterns = condition.get('patterns', [])
                single_pattern = condition.get('pattern')
                
                if single_pattern and single_pattern not in patterns:
                    patterns.append(single_pattern)
                
                if not patterns:
                    return False
                
                fields = condition.get('fields', ['msg'])
                case_sensitive = condition.get('case_sensitive', False)
                
                for field in fields:
                    field_value = self._get_field_value(log, field)
                    if not field_value:
                        continue
                    
                    if not case_sensitive:
                        field_value = field_value.lower()
                        patterns = [p.lower() for p in patterns]
                    
                    for pattern in patterns:
                        if pattern in field_value:
                            return True
                            
            elif pattern_type == 'multi_field':
                field_patterns = condition.get('field_patterns', {})
                case_sensitive = condition.get('case_sensitive', False)
                
                field_matches = 0
                for field, pattern in field_patterns.items():
                    field_value = self._get_field_value(log, field)
                    if not field_value:
                        continue
                    
                    if not case_sensitive:
                        field_value = field_value.lower()
                        if isinstance(pattern, str):
                            pattern = pattern.lower()
                    
                    if isinstance(pattern, str) and pattern in field_value:
                        field_matches += 1
                
                match_type = condition.get('match_type', 'all')
                if match_type == 'all':
                    return field_matches == len(field_patterns)
                else:
                    return field_matches > 0
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking if log matches pattern: {e}")
            return False
    
    async def _extract_specific_match_data(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
        """Extract pattern-specific match data."""
        try:
            condition = self._parse_rule_condition(rule)
            pattern_type = condition.get('pattern_type', 'regex')
            
            matching_logs = await self._get_matching_logs(logs, rule)
            
            match_data = {
                "pattern_type": pattern_type,
                "fields_searched": condition.get('fields', ['msg']),
                "case_sensitive": condition.get('case_sensitive', False),
                "matching_logs_count": len(matching_logs)
            }
            
            if pattern_type == 'regex':
                match_data["regex_pattern"] = condition.get('pattern')
                
            elif pattern_type in ['keyword', 'phrase']:
                patterns = condition.get('patterns', [])
                single_pattern = condition.get('pattern')
                if single_pattern and single_pattern not in patterns:
                    patterns.append(single_pattern)
                
                match_data.update({
                    "patterns": patterns,
                    "match_type": condition.get('match_type', 'any')
                })
                
            elif pattern_type == 'multi_field':
                match_data.update({
                    "field_patterns": condition.get('field_patterns', {}),
                    "match_type": condition.get('match_type', 'all')
                })
            
            # Add sample matches
            if matching_logs:
                sample_matches = []
                for log in matching_logs[:3]:  # First 3 matching logs
                    log_sample = {
                        "timestamp": log.get('ts'),
                        "level": log.get('level'),
                        "service": log.get('service'),
                        "message_preview": self._get_field_value(log, 'msg')[:200]
                    }
                    sample_matches.append(log_sample)
                
                match_data["sample_matches"] = sample_matches
            
            return match_data
            
        except Exception as e:
            self.logger.error(f"Error extracting pattern match data: {e}")
            return {"error": str(e)}