"""
Alert System Constants
Constants for alert rule conditions, operators, and matching logic
"""

# Comparison Operators
class ComparisonOperator:
    """Field comparison operators for alert conditions"""
    EQ = 'eq'                    # Equal to
    NE = 'ne'                    # Not equal to
    GT = 'gt'                    # Greater than
    GTE = 'gte'                  # Greater than or equal to
    LT = 'lt'                    # Less than
    LTE = 'lte'                  # Less than or equal to
    CONTAINS = 'contains'        # String contains
    STARTS_WITH = 'starts_with'  # String starts with
    ENDS_WITH = 'ends_with'      # String ends with
    IN = 'in'                    # Value in list
    NOT_IN = 'not_in'           # Value not in list
    REGEX = 'regex'             # Regular expression match

# Logical Operators
class LogicalOperator:
    """Logical operators for combining conditions"""
    AND = 'AND'
    OR = 'OR'
    NOT = 'NOT'

# Rule Types
class AlertRuleType:
    """Alert rule types supported by the system"""
    THRESHOLD = 'threshold'
    PATTERN = 'pattern'
    ANOMALY = 'anomaly'
    FREQUENCY = 'frequency'
    ABSENCE = 'absence'
    SEQUENCE = 'sequence'

# Alert Severities
class AlertSeverity:
    """Alert severity levels"""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

# Alert Statuses
class AlertStatus:
    """Alert instance status values"""
    TRIGGERED = 'triggered'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'
    SUPPRESSED = 'suppressed'

# Aggregation Functions
class AggregationFunction:
    """Aggregation functions for threshold rules"""
    COUNT = 'count'
    SUM = 'sum'
    AVG = 'avg'
    MIN = 'min'
    MAX = 'max'

# Threshold Types
class ThresholdType:
    """Types of threshold evaluations"""
    COUNT = 'count'      # Count of matching logs
    VALUE = 'value'      # Value from log field
    RATE = 'rate'        # Rate per time period

# Constants for validation
MAX_CONDITION_DEPTH = 3
DEFAULT_COOLDOWN_MINUTES = 5
DEFAULT_TIME_WINDOW_MINUTES = 5

# Valid operators lists for validation
COMPARISON_OPERATORS = [
    ComparisonOperator.EQ, ComparisonOperator.NE, 
    ComparisonOperator.GT, ComparisonOperator.GTE,
    ComparisonOperator.LT, ComparisonOperator.LTE,
    ComparisonOperator.CONTAINS, ComparisonOperator.STARTS_WITH, ComparisonOperator.ENDS_WITH,
    ComparisonOperator.IN, ComparisonOperator.NOT_IN, ComparisonOperator.REGEX
]

LOGICAL_OPERATORS = [
    LogicalOperator.AND, LogicalOperator.OR, LogicalOperator.NOT
]

ALERT_RULE_TYPES = [
    AlertRuleType.THRESHOLD, AlertRuleType.PATTERN, AlertRuleType.ANOMALY,
    AlertRuleType.FREQUENCY, AlertRuleType.ABSENCE, AlertRuleType.SEQUENCE
]

ALERT_SEVERITIES = [
    AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL
]

ALERT_STATUSES = [
    AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED, AlertStatus.SUPPRESSED
]

AGGREGATION_FUNCTIONS = [
    AggregationFunction.COUNT, AggregationFunction.SUM, AggregationFunction.AVG,
    AggregationFunction.MIN, AggregationFunction.MAX
]

THRESHOLD_TYPES = [
    ThresholdType.COUNT, ThresholdType.VALUE, ThresholdType.RATE
]