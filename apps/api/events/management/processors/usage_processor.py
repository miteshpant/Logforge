"""
Usage Processor

Handles usage tracking and cost calculation operations.
Moved functions exactly as-is from event_processing.py to preserve functionality.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

async def track_usage_stats(customer_id: str, feature: str, bytes_processed: int, cost: float) -> bool:
    """
    Track usage statistics and update tenant quotas
    
    Args:
        customer_id: Customer/tenant ID
        feature: Feature name (e.g., 'ingestion.basic', 'api.calls')
        bytes_processed: Number of bytes processed
        cost: Calculated cost for the usage
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from services.tenant_service import TenantService
        
        # Map feature to usage type
        usage_type_map = {
            'ingestion.basic': 'monthly_ingestion',
            'api.calls': 'api_calls',
            'queries.basic': 'queries'
        }
        
        usage_type = usage_type_map.get(feature, 'monthly_ingestion')
        
        tenant_service = TenantService()
        await track_usage_with_cost_calculation(
            tenant_service, customer_id, usage_type, bytes_processed
        )
        
        logger.debug(f"Usage tracked for customer {customer_id}: feature={feature}, bytes={bytes_processed}, cost={cost}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to track usage stats for customer {customer_id}: {e}")
        return False


async def update_tenant_quotas(customer_id: str, usage_delta: Dict[str, Any]) -> bool:
    """
    Update tenant quota usage
    
    Args:
        customer_id: Customer/tenant ID
        usage_delta: Dictionary containing usage changes
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from services.tenant_service import TenantService
        
        tenant_service = TenantService()
        
        # Extract relevant data from usage_delta
        bytes_processed = usage_delta.get('bytes_processed', 0)
        
        # Update quotas (this is handled within track_usage_with_cost_calculation)
        await track_usage_with_cost_calculation(
            tenant_service, customer_id, "monthly_ingestion", bytes_processed
        )
        
        logger.debug(f"Tenant quotas updated for customer {customer_id}: {usage_delta}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update tenant quotas for customer {customer_id}: {e}")
        return False


# Helper function for cost calculation (copied exactly from dependencies.py)
async def track_usage_with_cost_calculation(tenant_service, customer_id: str, usage_type: str, bytes_processed: int):
    """Track usage with proper cost calculation using actual bytes"""
    try:
        from services.subscription_service import SubscriptionService
        import json
        from datetime import datetime, timezone
        import uuid

        subscription_service = SubscriptionService()

        # Map usage type to feature name for pricing
        feature_map = {
            'monthly_ingestion': 'ingestion.basic',
            'api_calls': 'api.calls',
            'queries': 'queries.basic',
            'storage': 'storage.hot',
            'alerts': 'alerts.basic'
        }

        feature_name = feature_map.get(usage_type, usage_type)

        # Get the feature rate for this tenant
        feature_rate = await subscription_service.get_feature_rate(feature_name, tenant_id=customer_id)

        # Calculate cost based on actual bytes (convert to GB for ingestion)
        cost_calculated = 0.0
        rate_applied = 0.0

        logger.info(f"Debug cost calculation: feature_name={feature_name}, feature_rate={feature_rate}, bytes_processed={bytes_processed}")

        if feature_rate:
            if 'ingestion' in feature_name:
                # Convert bytes to GB for pricing calculation
                gb_ingested = bytes_processed / (1024 * 1024 * 1024)
                cost_calculated = feature_rate.base_rate * gb_ingested
                logger.info(f"Ingestion cost calc: gb_ingested={gb_ingested}, base_rate={feature_rate.base_rate}, cost={cost_calculated}")
            elif 'api.calls' in feature_name:
                # API calls: rate is per 1000 calls, convert to per-call rate
                per_call_rate = feature_rate.base_rate / 1000.0
                cost_calculated = per_call_rate * bytes_processed
                logger.info(f"API calls cost calc: per_call_rate={per_call_rate}, calls={bytes_processed}, cost={cost_calculated}")
            elif 'queries' in feature_name:
                # Queries: rate is per 1000 queries, convert to per-query rate
                per_query_rate = feature_rate.base_rate / 1000.0
                cost_calculated = per_query_rate * bytes_processed
                logger.info(f"Queries cost calc: per_query_rate={per_query_rate}, queries={bytes_processed}, cost={cost_calculated}")
            else:
                # For other features, bytes represent different units
                cost_calculated = feature_rate.base_rate * bytes_processed
                logger.info(f"Other cost calc: base_rate={feature_rate.base_rate}, bytes={bytes_processed}, cost={cost_calculated}")
            rate_applied = feature_rate.base_rate
        else:
            logger.warning(f"No feature rate found for {feature_name}, cost will be 0")

        # Update tenant quota directly (without creating duplicate usage record)
        await update_tenant_quota_only(tenant_service, customer_id, usage_type, 1)

        # Create detailed usage record with proper cost calculation
        usage_record = {
            'id': str(uuid.uuid4()),
            'tenant_id': customer_id,
            'customer_id': customer_id,
            'feature_name': feature_name,
            'usage_type': usage_type,
            'quantity': bytes_processed,  # Store actual bytes
            'timestamp': datetime.now(timezone.utc),
            'billing_period': datetime.now(timezone.utc).strftime('%Y-%m'),
            'cost_calculated': round(cost_calculated, 10) if cost_calculated > 0 else 0,
            'rate_applied': round(rate_applied, 6),
            'metadata': json.dumps({
                'original_usage_type': usage_type,
                'bytes_processed': bytes_processed,
                'gb_calculated': bytes_processed / (1024 * 1024 * 1024) if 'ingestion' in feature_name else 0
            }),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }

        # Insert usage record with cost calculation
        from dao.subscription_dao import SubscriptionDAO
        subscription_dao = SubscriptionDAO()
        await subscription_dao.create_usage_record(usage_record)

        logger.info(f"Usage tracked with accurate cost calculation: customer_id={customer_id}, feature={feature_name}, bytes_processed={bytes_processed}, cost={cost_calculated}, rate={rate_applied}")

    except Exception as e:
        logger.warning(f"Cost calculation failed in background: customer_id={customer_id}, usage_type={usage_type}, error={str(e)}")

async def update_tenant_quota_only(tenant_service, customer_id: str, usage_type: str, amount: int = 1):
    """Update tenant quota without creating usage record"""
    try:
        # Get current quota for this usage type
        db_quotas = await tenant_service.tenant_dao.get_tenant_quotas(customer_id)

        # Find the relevant quota and update usage
        for quota in db_quotas:
            if quota['quota_type'] == f"{usage_type}_quota" or quota['quota_type'] == usage_type:
                current_used = quota['current_usage']
                new_used = current_used + amount

                # Update usage in database
                await tenant_service.tenant_dao.update_tenant_quota(
                    customer_id,
                    quota['quota_type'],
                    {'current_usage': new_used}
                )
                logger.debug(f"Quota updated: customer_id={customer_id}, usage_type={usage_type}, amount={amount}")
                break

    except Exception as e:
        logger.warning(f"Failed to update quota: customer_id={customer_id}, usage_type={usage_type}, error={str(e)}")