"""
Event Processing Module for Logforge Event-Driven Architecture

This module now serves as a compatibility layer, importing functions from the
modular event management system. All functions have been moved to specialized
processors while maintaining the same API for backward compatibility.

Migration from direct database processing to event-driven processing with modular architecture.
"""

# Import all functions from the modular event management system
from events.management import (
    log_set_config as set_config,
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

# Re-export all functions to maintain backward compatibility
__all__ = [
    'set_config',
    'process_log_batch_with_client',
    'process_log_batch_internal',
    'process_log_batch',
    'track_usage_stats',
    'update_tenant_quotas',
    'track_ingestion_metrics',
    'handle_log_ingestion_event',
    'track_usage_with_cost_calculation',
    'update_tenant_quota_only'
]