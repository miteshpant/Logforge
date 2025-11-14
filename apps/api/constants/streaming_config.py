"""
Streaming Configuration Constants and Default Values
"""

from typing import Dict, Any

# Streaming config keys for tenant_configs_mt table
STREAMING_CONFIG_METRICS_KEY = "streaming_metrics.batch.ingested"
STREAMING_CONFIG_TRACES_KEY = "streaming_traces.batch.ingested"

# Redis key patterns for streaming configs
REDIS_STREAMING_CONFIG_PREFIX = "streaming_config"
REDIS_DEFAULT_STREAMING_CONFIG_KEY = f"{REDIS_STREAMING_CONFIG_PREFIX}:default"

def get_customer_streaming_config_key(customer_id: str, event_type: str) -> str:
    """Generate Redis key for customer streaming config"""
    return f"{REDIS_STREAMING_CONFIG_PREFIX}:{customer_id}:{event_type}"

# Default streaming configurations
DEFAULT_METRICS_STREAMING_CONFIG = {
    "enabled": True,
    "sample_rate": 0.1,  # 10% sampling by default
    "min_metrics_count": 1,  # Stream if batch has 1+ metrics
    "include_services": [],  # Empty = all services
    "exclude_services": ["health-check", "internal-metrics"],
    "priority_metrics": ["cpu_usage", "memory_usage", "error_rate", "response_time"],
    "max_events_per_minute": 100,  # Rate limiting
    "include_errors_only": False,
    "min_value_change_threshold": 0.05  # Only stream if metric changed by 5%+
}

DEFAULT_TRACES_STREAMING_CONFIG = {
    "enabled": True,
    "sample_rate": 0.05,  # 5% sampling by default (traces are higher volume)
    "min_traces_count": 1,  # Stream if batch has 1+ traces
    "include_services": [],  # Empty = all services
    "exclude_services": ["health-check"],
    "min_duration_ms": 100,  # Only traces longer than 100ms
    "include_errors_only": False,  # Stream all traces, not just errors
    "max_events_per_minute": 50,  # Lower rate limit for traces
    "priority_operations": ["payment", "login", "checkout"],  # Always stream these
    "include_status": ["ok", "error"]  # Stream successful and failed traces
}

# Map event types to config keys and defaults
STREAMING_CONFIG_MAP = {
    "metrics.batch.ingested": {
        "config_key": STREAMING_CONFIG_METRICS_KEY,
        "defaults": DEFAULT_METRICS_STREAMING_CONFIG
    },
    "traces.batch.ingested": {
        "config_key": STREAMING_CONFIG_TRACES_KEY, 
        "defaults": DEFAULT_TRACES_STREAMING_CONFIG
    }
}

# Valid config types for validation
VALID_STREAMING_CONFIG_TYPES = [
    STREAMING_CONFIG_METRICS_KEY,
    STREAMING_CONFIG_TRACES_KEY
]