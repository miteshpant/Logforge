"""
Event Management Module

This module provides modular components for event-driven processing including:
- Processors: Core business logic for different event types
- Matchers: Alert rule matching and evaluation
- Handlers: Event handlers for database operations and notifications
- Cache: Redis-based caching for performance optimization
"""

# Import all processor functions
from .processors import (
    log_set_config,
    process_log_batch_with_client,
    process_log_batch_internal, 
    process_log_batch,
    track_ingestion_metrics,
    track_usage_stats,
    update_tenant_quotas,
    track_usage_with_cost_calculation,
    update_tenant_quota_only,
    handle_log_ingestion_event
)

# Import cache components
from .cache import RedisManager

__all__ = [
    # Log processor functions
    'log_set_config',
    'process_log_batch_with_client',
    'process_log_batch_internal', 
    'process_log_batch',
    'track_ingestion_metrics',
    
    # Usage processor functions
    'track_usage_stats',
    'update_tenant_quotas',
    'track_usage_with_cost_calculation',
    'update_tenant_quota_only',
    
    # Main event handler
    'handle_log_ingestion_event',
    
    # Cache
    'RedisManager',
]