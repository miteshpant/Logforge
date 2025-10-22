"""
Anomaly Matcher

Matches anomaly-based alert rules using statistical analysis and trend detection.
"""

import statistics
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
import logging

from .base_matcher import BaseAlertMatcher

logger = logging.getLogger(__name__)

class AnomalyMatcher(BaseAlertMatcher):
    """
    Matches anomaly-based alert rules using statistical methods.
    
    Supports various anomaly detection methods:
    - Statistical: Z-score and standard deviation based detection
    - Rate-based: Sudden spikes or drops in event rates
    - Trend: Unexpected trends over time periods
    - Baseline: Comparison against historical baselines
    
    Example rule configuration:
    {
        "rule_type": "anomaly",
        "condition_config": {
            "anomaly_type": "statistical",  # statistical, rate, trend, baseline
            "field": "response_time",  # Field to analyze (for value-based anomalies)
            "method": "zscore",  # zscore, stddev, iqr
            "threshold": 2.0,  # Number of standard deviations
            "baseline_window_hours": 24,  # Historical window for baseline
            "detection_window_minutes": 5,  # Current window for detection
            "min_samples": 10  # Minimum samples needed for analysis
        }
    }
    """
    
    def __init__(self):
        """Initialize anomaly matcher with baseline cache."""
        super().__init__()
        self._baseline_cache = {}  # Cache for baseline calculations
    
    def get_rule_type(self) -> str:
        """Return the rule type this matcher handles."""
        return "anomaly"
    
    async def matches(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> bool:
        """
        Check if logs show anomalous behavior according to the rule.
        
        Args:
            logs: List of log entries to analyze
            rule: Alert rule configuration
            
        Returns:
            bool: True if anomaly is detected, False otherwise
        """
        try:
            if not self._validate_rule_config(rule):
                return False
            
            condition_config = self._parse_rule_condition(rule)
            
            # Check if this is a nested condition (new format) or simple anomaly (old format)
            if 'operator' in condition_config and condition_config.get('operator') in ['AND', 'OR', 'NOT']:
                # New nested condition format - use base matcher evaluation
                self.logger.debug(f"Evaluating anomaly rule {rule.get('id')} with nested conditions")
                condition_result = self._evaluate_nested_condition(logs, condition_config)
                return condition_result.get('matched', False)
            else:
                # Old simple anomaly format - use legacy anomaly logic
                anomaly_type = condition_config.get('anomaly_type', 'statistical')
                
                self.logger.debug(f"Evaluating anomaly rule {rule.get('id')} with type {anomaly_type}")
                
                # Filter logs by basic criteria first
                filtered_logs = self._filter_logs_by_condition(logs, condition_config)
                
                if not filtered_logs:
                    return False
                
                if anomaly_type == 'statistical':
                    return await self._evaluate_statistical_anomaly(filtered_logs, condition_config)
                elif anomaly_type == 'rate':
                    return await self._evaluate_rate_anomaly(filtered_logs, condition_config)
                elif anomaly_type == 'trend':
                    return await self._evaluate_trend_anomaly(filtered_logs, condition_config)
                elif anomaly_type == 'baseline':
                    return await self._evaluate_baseline_anomaly(filtered_logs, condition_config, rule.get('customer_id'))
                else:
                    self.logger.error(f"Unknown anomaly type: {anomaly_type}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating anomaly rule {rule.get('id')}: {e}")
            return False
    
    async def _evaluate_statistical_anomaly(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate statistical anomalies using Z-score or standard deviation methods.
        
        Args:
            logs: Log entries to analyze
            condition: Anomaly condition configuration
            
        Returns:
            bool: True if statistical anomaly is detected
        """
        try:
            field = condition.get('field')
            method = condition.get('method', 'zscore')
            threshold = condition.get('threshold', 2.0)
            min_samples = condition.get('min_samples', 10)
            
            if not field:
                # For count-based anomalies, analyze log frequency over time
                return await self._evaluate_count_anomaly(logs, condition)
            
            # Extract numeric values from the specified field
            values = []
            for log in logs:
                try:
                    value = self._extract_numeric_value(log, field)
                    if value is not None:
                        values.append(value)
                except:
                    continue
            
            if len(values) < min_samples:
                self.logger.debug(f"Insufficient samples for statistical analysis: {len(values)} < {min_samples}")
                return False
            
            # Apply statistical method
            if method == 'zscore':
                return self._detect_zscore_anomaly(values, threshold)
            elif method == 'stddev':
                return self._detect_stddev_anomaly(values, threshold)
            elif method == 'iqr':
                return self._detect_iqr_anomaly(values, threshold)
            else:
                self.logger.error(f"Unknown statistical method: {method}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating statistical anomaly: {e}")
            return False
    
    async def _evaluate_rate_anomaly(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate rate-based anomalies (sudden spikes or drops in event rates).
        
        Args:
            logs: Log entries to analyze
            condition: Anomaly condition configuration
            
        Returns:
            bool: True if rate anomaly is detected
        """
        try:
            detection_window_minutes = condition.get('detection_window_minutes', 5)
            baseline_window_hours = condition.get('baseline_window_hours', 24)
            threshold = condition.get('threshold', 3.0)  # Multiple of normal rate
            
            # Split logs into baseline and detection windows
            now = datetime.now(timezone.utc)
            detection_cutoff = now - timedelta(minutes=detection_window_minutes)
            baseline_cutoff = now - timedelta(hours=baseline_window_hours)
            
            detection_logs = []
            baseline_logs = []
            
            for log in logs:
                log_time = self._parse_log_timestamp(log)
                if log_time >= detection_cutoff:
                    detection_logs.append(log)
                elif log_time >= baseline_cutoff:
                    baseline_logs.append(log)
            
            # Calculate rates
            detection_rate = len(detection_logs) / detection_window_minutes
            baseline_rate = len(baseline_logs) / (baseline_window_hours * 60) if baseline_logs else 0
            
            if baseline_rate == 0:
                # No baseline data, check for absolute spike
                return detection_rate > condition.get('absolute_threshold', 10)
            
            # Check for rate anomaly
            rate_ratio = detection_rate / baseline_rate
            is_anomaly = rate_ratio >= threshold or rate_ratio <= (1 / threshold)
            
            self.logger.debug(
                f"Rate anomaly check: current={detection_rate:.2f}/min, "
                f"baseline={baseline_rate:.2f}/min, ratio={rate_ratio:.2f}, "
                f"threshold={threshold}, anomaly={is_anomaly}"
            )
            
            return is_anomaly
            
        except Exception as e:
            self.logger.error(f"Error evaluating rate anomaly: {e}")
            return False
    
    async def _evaluate_trend_anomaly(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate trend-based anomalies (unexpected changes in trends).
        
        Args:
            logs: Log entries to analyze
            condition: Anomaly condition configuration
            
        Returns:
            bool: True if trend anomaly is detected
        """
        try:
            field = condition.get('field')
            window_minutes = condition.get('detection_window_minutes', 15)
            min_samples = condition.get('min_samples', 5)
            trend_threshold = condition.get('trend_threshold', 0.1)  # Minimum trend strength
            
            # Group logs by time buckets
            time_buckets = self._create_time_buckets(logs, window_minutes, bucket_size_minutes=1)
            
            if len(time_buckets) < min_samples:
                return False
            
            # Calculate trend values for each bucket
            trend_values = []
            for bucket_logs in time_buckets.values():
                if field:
                    # Trend in field values
                    values = []
                    for log in bucket_logs:
                        try:
                            value = self._extract_numeric_value(log, field)
                            if value is not None:
                                values.append(value)
                        except:
                            continue
                    bucket_value = statistics.mean(values) if values else 0
                else:
                    # Trend in log counts
                    bucket_value = len(bucket_logs)
                
                trend_values.append(bucket_value)
            
            # Calculate trend strength using linear regression slope
            trend_slope = self._calculate_trend_slope(trend_values)
            
            # Check if trend is significant
            is_anomaly = abs(trend_slope) > trend_threshold
            
            self.logger.debug(
                f"Trend anomaly check: slope={trend_slope:.4f}, "
                f"threshold={trend_threshold}, anomaly={is_anomaly}"
            )
            
            return is_anomaly
            
        except Exception as e:
            self.logger.error(f"Error evaluating trend anomaly: {e}")
            return False
    
    async def _evaluate_baseline_anomaly(self, logs: List[Dict[str, Any]], condition: Dict[str, Any], customer_id: str) -> bool:
        """
        Evaluate baseline comparison anomalies using historical data.
        
        Args:
            logs: Log entries to analyze
            condition: Anomaly condition configuration
            customer_id: Customer ID for baseline caching
            
        Returns:
            bool: True if baseline anomaly is detected
        """
        try:
            # This is a simplified implementation
            # In production, you would query historical data from the database
            field = condition.get('field')
            threshold = condition.get('threshold', 2.0)
            
            # For now, use the current logs as both baseline and detection
            # In production, you would split into historical baseline vs current detection window
            if field:
                values = []
                for log in logs:
                    try:
                        value = self._extract_numeric_value(log, field)
                        if value is not None:
                            values.append(value)
                    except:
                        continue
                
                if len(values) < 10:
                    return False
                
                # Use first 80% as baseline, last 20% as detection
                split_point = int(len(values) * 0.8)
                baseline_values = values[:split_point]
                detection_values = values[split_point:]
                
                if not baseline_values or not detection_values:
                    return False
                
                baseline_mean = statistics.mean(baseline_values)
                baseline_std = statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0
                
                if baseline_std == 0:
                    return False
                
                # Check if detection values are anomalous compared to baseline
                for value in detection_values:
                    z_score = abs(value - baseline_mean) / baseline_std
                    if z_score > threshold:
                        self.logger.debug(f"Baseline anomaly detected: value={value}, z_score={z_score}")
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating baseline anomaly: {e}")
            return False
    
    async def _evaluate_count_anomaly(self, logs: List[Dict[str, Any]], condition: Dict[str, Any]) -> bool:
        """
        Evaluate anomalies in log count frequency over time.
        
        Args:
            logs: Log entries to analyze
            condition: Anomaly condition configuration
            
        Returns:
            bool: True if count anomaly is detected
        """
        try:
            window_minutes = condition.get('detection_window_minutes', 15)
            threshold = condition.get('threshold', 2.0)
            
            # Create time buckets
            time_buckets = self._create_time_buckets(logs, window_minutes, bucket_size_minutes=1)
            
            # Get count for each bucket
            counts = [len(bucket_logs) for bucket_logs in time_buckets.values()]
            
            if len(counts) < 3:
                return False
            
            # Use Z-score to detect anomalous counts
            return self._detect_zscore_anomaly(counts, threshold)
            
        except Exception as e:
            self.logger.error(f"Error evaluating count anomaly: {e}")
            return False
    
    def _extract_numeric_value(self, log: Dict[str, Any], field: str) -> Optional[float]:
        """Extract numeric value from log field."""
        try:
            # Handle nested fields
            if '.' in field:
                parts = field.split('.')
                current = log
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                    else:
                        return None
                value = current
            else:
                value = log.get(field)
            
            if value is None:
                return None
            
            # Convert to float
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    # Try to extract number from string (e.g., "500ms")
                    import re
                    match = re.search(r'(\d+\.?\d*)', value)
                    return float(match.group(1)) if match else None
            
            return None
            
        except Exception:
            return None
    
    def _detect_zscore_anomaly(self, values: List[float], threshold: float) -> bool:
        """Detect anomalies using Z-score method."""
        try:
            if len(values) < 2:
                return False
            
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            
            if std == 0:
                return False
            
            # Check for outliers
            for value in values:
                z_score = abs(value - mean) / std
                if z_score > threshold:
                    self.logger.debug(f"Z-score anomaly: value={value}, z_score={z_score:.2f}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in Z-score anomaly detection: {e}")
            return False
    
    def _detect_stddev_anomaly(self, values: List[float], threshold: float) -> bool:
        """Detect anomalies using standard deviation method."""
        try:
            if len(values) < 2:
                return False
            
            mean = statistics.mean(values)
            std = statistics.stdev(values)
            
            # Check for values outside threshold * std from mean
            for value in values:
                if abs(value - mean) > threshold * std:
                    self.logger.debug(f"StdDev anomaly: value={value}, deviation={abs(value - mean):.2f}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in standard deviation anomaly detection: {e}")
            return False
    
    def _detect_iqr_anomaly(self, values: List[float], threshold: float) -> bool:
        """Detect anomalies using Interquartile Range (IQR) method."""
        try:
            if len(values) < 4:
                return False
            
            sorted_values = sorted(values)
            q1 = statistics.quantiles(sorted_values, n=4)[0]
            q3 = statistics.quantiles(sorted_values, n=4)[2]
            iqr = q3 - q1
            
            if iqr == 0:
                return False
            
            # Check for outliers beyond threshold * IQR
            lower_bound = q1 - threshold * iqr
            upper_bound = q3 + threshold * iqr
            
            for value in values:
                if value < lower_bound or value > upper_bound:
                    self.logger.debug(f"IQR anomaly: value={value}, bounds=[{lower_bound:.2f}, {upper_bound:.2f}]")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in IQR anomaly detection: {e}")
            return False
    
    def _create_time_buckets(self, logs: List[Dict[str, Any]], window_minutes: int, bucket_size_minutes: int) -> Dict[datetime, List[Dict]]:
        """Create time buckets for trend analysis."""
        try:
            buckets = defaultdict(list)
            
            for log in logs:
                log_time = self._parse_log_timestamp(log)
                # Round to bucket boundary
                bucket_time = log_time.replace(second=0, microsecond=0)
                bucket_time = bucket_time.replace(minute=(bucket_time.minute // bucket_size_minutes) * bucket_size_minutes)
                buckets[bucket_time].append(log)
            
            return dict(buckets)
            
        except Exception as e:
            self.logger.error(f"Error creating time buckets: {e}")
            return {}
    
    def _parse_log_timestamp(self, log: Dict[str, Any]) -> datetime:
        """Parse timestamp from log entry."""
        try:
            ts = log.get('ts')
            if isinstance(ts, datetime):
                return ts
            elif isinstance(ts, str):
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                return datetime.now(timezone.utc)
        except:
            return datetime.now(timezone.utc)
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate trend slope using simple linear regression."""
        try:
            n = len(values)
            if n < 2:
                return 0.0
            
            x_values = list(range(n))
            x_mean = statistics.mean(x_values)
            y_mean = statistics.mean(values)
            
            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
            denominator = sum((x - x_mean) ** 2 for x in x_values)
            
            return numerator / denominator if denominator != 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating trend slope: {e}")
            return 0.0
    
    async def _get_matching_logs(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get logs that contributed to the anomaly detection."""
        # For anomaly detection, all filtered logs are considered "matching"
        # since the anomaly is based on the aggregate behavior
        condition = self._parse_rule_condition(rule)
        return self._filter_logs_by_condition(logs, condition)
    
    async def _extract_specific_match_data(self, logs: List[Dict[str, Any]], rule: Dict[str, Any]) -> Dict[str, Any]:
        """Extract anomaly-specific match data."""
        try:
            condition = self._parse_rule_condition(rule)
            anomaly_type = condition.get('anomaly_type', 'statistical')
            
            matching_logs = await self._get_matching_logs(logs, rule)
            
            match_data = {
                "anomaly_type": anomaly_type,
                "method": condition.get('method'),
                "threshold": condition.get('threshold'),
                "analyzed_logs_count": len(matching_logs)
            }
            
            # Add type-specific data
            if anomaly_type == 'statistical':
                field = condition.get('field')
                if field:
                    values = []
                    for log in matching_logs:
                        try:
                            value = self._extract_numeric_value(log, field)
                            if value is not None:
                                values.append(value)
                        except:
                            continue
                    
                    if values:
                        match_data.update({
                            "field": field,
                            "values_count": len(values),
                            "mean": statistics.mean(values),
                            "std": statistics.stdev(values) if len(values) > 1 else 0,
                            "min": min(values),
                            "max": max(values)
                        })
                        
            elif anomaly_type == 'rate':
                detection_window = condition.get('detection_window_minutes', 5)
                match_data.update({
                    "detection_window_minutes": detection_window,
                    "events_in_window": len(matching_logs),
                    "rate_per_minute": len(matching_logs) / detection_window
                })
            
            return match_data
            
        except Exception as e:
            self.logger.error(f"Error extracting anomaly match data: {e}")
            return {"error": str(e)}