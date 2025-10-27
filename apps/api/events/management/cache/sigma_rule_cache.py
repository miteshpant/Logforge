"""
Sigma Rule Cache Management

Manages Redis cache for Sigma security rules with event-driven updates.
Supports both customer-specific rules and default rules.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .redis_manager import RedisManager
from ...constants import (
    EVENT_SIGMA_RULE_CREATED,
    EVENT_SIGMA_RULE_UPDATED,
    EVENT_SIGMA_RULE_DELETED,
    EVENT_SIGMA_RULE_ENABLED,
    EVENT_SIGMA_RULE_DISABLED,
    SIGMA_RULE_CACHE_PREFIX,
    SIGMA_RULE_CACHE_METADATA_KEY,
    SIGMA_DEFAULT_RULES_CACHE_KEY
)

logger = logging.getLogger(__name__)

class SigmaRuleCache:
    """
    Manages Redis cache for Sigma security rules with event-driven updates.

    Cache Structure:
    - security:sigma:rules:{customer_id} → JSON array of customer-specific rule objects
    - security:sigma:default:rules → JSON array of default rule objects (shared across all customers)
    - security:sigma:cache:metadata → cache metadata
    """

    def __init__(self, redis_manager: Optional[RedisManager] = None):
        """
        Initialize Sigma rule cache manager.

        Args:
            redis_manager: Redis manager instance (optional, will create if not provided)
        """
        self.redis_manager = redis_manager or RedisManager()
        self.cache_prefix = SIGMA_RULE_CACHE_PREFIX
        self.metadata_key = SIGMA_RULE_CACHE_METADATA_KEY
        self.default_rules_key = SIGMA_DEFAULT_RULES_CACHE_KEY

    async def initialize_cache_from_db(self) -> bool:
        """
        Load all Sigma rules from database into Redis cache.
        This is typically run at startup or after cache invalidation.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from services.security_service import SecurityService

            logger.info("🔄 Initializing Sigma rule cache from database...")

            security_service = SecurityService()

            # Get all enabled Sigma rules (both customer-specific and default)
            all_rules = await security_service.get_sigma_rules(customer_id=None, enabled_only=True)

            # Separate default rules from customer-specific rules
            default_rules = []
            rules_by_customer = {}
            total_rules = 0

            logger.debug(f"🔍 DEBUG: Processing {len(all_rules)} rules from database")

            for rule in all_rules:
                customer_id = rule.get('customer_id')
                if customer_id:
                    # Customer-specific rule
                    if customer_id not in rules_by_customer:
                        rules_by_customer[customer_id] = []
                    rules_by_customer[customer_id].append(rule)
                    total_rules += 1
                    logger.info(f"total is now {total_rules}")
                else:
                    # Default rule (no customer_id)
                    default_rules.append(rule)
                    total_rules += 1

            # Cache default rules
            default_success = await self._cache_default_rules(default_rules)
            if default_success:
                logger.debug(f"✅ Cached {len(default_rules)} default Sigma rules")
            else:
                logger.error(f"❌ Failed to cache default Sigma rules")

            # Cache customer-specific rules
            successful_customers = 0
            for customer_id, rules in rules_by_customer.items():
                if await self._cache_customer_rules(customer_id, rules):
                    successful_customers += 1
                    logger.debug(f"✅ Cached {len(rules)} Sigma rules for customer {customer_id}")
                else:
                    logger.error(f"❌ Failed to cache Sigma rules for customer {customer_id}")

            # Update cache metadata
            metadata = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "total_customers": len(rules_by_customer),
                "total_rules": total_rules,
                "default_rules": len(default_rules),
                "successful_customers": successful_customers,
                "default_cache_success": default_success
            }

            await self.redis_manager.set(self.metadata_key, metadata)

            logger.info(f"✅ Sigma rule cache initialized: {total_rules} rules ({len(default_rules)} default, {successful_customers}/{len(rules_by_customer)} customers)")
            return default_success and successful_customers == len(rules_by_customer)

        except Exception as e:
            logger.error(f"❌ Failed to initialize Sigma rule cache: {e}")
            return False

    async def get_customer_rules(self, customer_id: str, include_defaults: bool = True) -> List[Dict[str, Any]]:
        """
        Get Sigma rules for a customer from cache, including default rules if requested.
        Fallback to DB if needed.

        Args:
            customer_id: Customer/tenant ID
            include_defaults: Whether to include default rules (defaults to True)

        Returns:
            List of rule dictionaries (customer rules + default rules if requested)
        """
        try:
            customer_cache_key = f"{self.cache_prefix}{customer_id}"

            # Get customer-specific rules from cache
            customer_rules = await self.redis_manager.get(customer_cache_key, default=[])

            # Get default rules from cache if requested
            default_rules = []
            if include_defaults:
                default_rules = await self.redis_manager.get(self.default_rules_key, default=[])

            # If we have cache hits, return combined rules
            if customer_rules or default_rules:
                combined_rules = customer_rules + default_rules
                logger.debug(f"✅ Cache hit: Retrieved {len(customer_rules)} customer + {len(default_rules)} default Sigma rules for customer {customer_id}")
                return combined_rules

            # Cache miss - fallback to database
            logger.debug(f"⚠️ Cache miss for customer {customer_id}, falling back to database")

            from services.security_service import SecurityService
            security_service = SecurityService()

            # Get customer rules from database
            db_customer_rules = await security_service.get_sigma_rules_for_customer(customer_id)

            # Get default rules from database if requested
            db_default_rules = []
            if include_defaults:
                db_default_rules = await security_service.get_default_sigma_rules()

            # Cache the rules for future requests
            if db_customer_rules:
                await self._cache_customer_rules(customer_id, db_customer_rules)
                logger.debug(f"📦 Cached {len(db_customer_rules)} customer Sigma rules for {customer_id} from DB fallback")

            if db_default_rules and include_defaults:
                await self._cache_default_rules(db_default_rules)
                logger.debug(f"📦 Cached {len(db_default_rules)} default Sigma rules from DB fallback")

            combined_db_rules = db_customer_rules + db_default_rules
            return combined_db_rules or []

        except Exception as e:
            logger.error(f"❌ Failed to get Sigma rules for customer {customer_id}: {e}")
            return []

    async def get_default_rules(self) -> List[Dict[str, Any]]:
        """
        Get default Sigma rules from cache, fallback to DB if needed.

        Returns:
            List of default rule dictionaries
        """
        try:
            # Try to get from cache first
            cached_rules = await self.redis_manager.get(self.default_rules_key, default=[])

            if cached_rules:
                logger.debug(f"✅ Cache hit: Retrieved {len(cached_rules)} default Sigma rules")
                return cached_rules

            # Cache miss - fallback to database
            logger.debug("⚠️ Cache miss for default rules, falling back to database")

            from services.security_service import SecurityService
            security_service = SecurityService()

            # Get default rules from database
            db_rules = await security_service.get_default_sigma_rules()

            # Cache the rules for future requests
            if db_rules:
                await self._cache_default_rules(db_rules)
                logger.debug(f"📦 Cached {len(db_rules)} default Sigma rules from DB fallback")

            return db_rules or []

        except Exception as e:
            logger.error(f"❌ Failed to get default Sigma rules: {e}")
            return []

    async def update_rule_cache(self, customer_id: Optional[str], rule_data: Dict[str, Any]) -> bool:
        """
        Update specific rule in cache for a customer or as a default rule.

        Args:
            customer_id: Customer/tenant ID (None for default rules)
            rule_data: Rule data dictionary

        Returns:
            bool: True if successful
        """
        try:
            rule_id = rule_data.get('id')

            if not rule_id:
                logger.error("No rule ID provided for cache update")
                return False

            if customer_id:
                # Customer-specific rule
                cache_key = f"{self.cache_prefix}{customer_id}"
                current_rules = await self.redis_manager.get(cache_key, default=[])

                # Find and update the rule
                rule_found = False
                for i, rule in enumerate(current_rules):
                    if rule.get('id') == rule_id:
                        current_rules[i] = rule_data
                        rule_found = True
                        break

                # If rule not found, add it
                if not rule_found:
                    current_rules.append(rule_data)
                    logger.debug(f"➕ Added new Sigma rule {rule_id} to cache for customer {customer_id}")
                else:
                    logger.debug(f"🔄 Updated Sigma rule {rule_id} in cache for customer {customer_id}")

                # Update cache
                success = await self.redis_manager.set(cache_key, current_rules)

            else:
                # Default rule
                current_rules = await self.redis_manager.get(self.default_rules_key, default=[])

                # Find and update the rule
                rule_found = False
                for i, rule in enumerate(current_rules):
                    if rule.get('id') == rule_id:
                        current_rules[i] = rule_data
                        rule_found = True
                        break

                # If rule not found, add it
                if not rule_found:
                    current_rules.append(rule_data)
                    logger.debug(f"➕ Added new default Sigma rule {rule_id} to cache")
                else:
                    logger.debug(f"🔄 Updated default Sigma rule {rule_id} in cache")

                # Update cache
                success = await self.redis_manager.set(self.default_rules_key, current_rules)

            if success:
                logger.debug(f"✅ Successfully updated Sigma rule cache")
            else:
                logger.error(f"❌ Failed to update Sigma rule cache")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to update Sigma rule cache: {e}")
            return False

    async def remove_rule_from_cache(self, customer_id: Optional[str], rule_id: str) -> bool:
        """
        Remove specific rule from cache for a customer or from default rules.

        Args:
            customer_id: Customer/tenant ID (None for default rules)
            rule_id: Rule ID to remove

        Returns:
            bool: True if successful
        """
        try:
            if customer_id:
                # Customer-specific rule
                cache_key = f"{self.cache_prefix}{customer_id}"
                current_rules = await self.redis_manager.get(cache_key, default=[])

                # Filter out the rule to be removed
                original_count = len(current_rules)
                current_rules = [rule for rule in current_rules if rule.get('id') != rule_id]

                if len(current_rules) < original_count:
                    # Update cache with filtered rules
                    success = await self.redis_manager.set(cache_key, current_rules)
                    logger.debug(f"🗑️ Removed Sigma rule {rule_id} from cache for customer {customer_id}")
                    return success
                else:
                    logger.debug(f"⚠️ Sigma rule {rule_id} not found in cache for customer {customer_id}")
                    return True  # Rule wasn't in cache anyway

            else:
                # Default rule
                current_rules = await self.redis_manager.get(self.default_rules_key, default=[])

                # Filter out the rule to be removed
                original_count = len(current_rules)
                current_rules = [rule for rule in current_rules if rule.get('id') != rule_id]

                if len(current_rules) < original_count:
                    # Update cache with filtered rules
                    success = await self.redis_manager.set(self.default_rules_key, current_rules)
                    logger.debug(f"🗑️ Removed default Sigma rule {rule_id} from cache")
                    return success
                else:
                    logger.debug(f"⚠️ Default Sigma rule {rule_id} not found in cache")
                    return True  # Rule wasn't in cache anyway

        except Exception as e:
            logger.error(f"❌ Failed to remove Sigma rule from cache: {e}")
            return False

    async def invalidate_customer_cache(self, customer_id: str) -> bool:
        """
        Remove customer's rules from cache (force refresh on next access).

        Args:
            customer_id: Customer/tenant ID

        Returns:
            bool: True if successful
        """
        try:
            cache_key = f"{self.cache_prefix}{customer_id}"
            deleted_count = await self.redis_manager.delete(cache_key)

            logger.debug(f"🧹 Invalidated Sigma rule cache for customer {customer_id} (deleted {deleted_count} keys)")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"❌ Failed to invalidate Sigma rule cache for customer {customer_id}: {e}")
            return False

    async def invalidate_default_cache(self) -> bool:
        """
        Remove default rules from cache (force refresh on next access).

        Returns:
            bool: True if successful
        """
        try:
            deleted_count = await self.redis_manager.delete(self.default_rules_key)

            logger.debug(f"🧹 Invalidated default Sigma rule cache (deleted {deleted_count} keys)")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"❌ Failed to invalidate default Sigma rule cache: {e}")
            return False

    async def handle_rule_event(self, event_type: str, rule_data: Dict[str, Any]) -> bool:
        """
        Handle rule CRUD events for cache updates.

        Args:
            event_type: Type of event (security.sigma.rule.created, updated, deleted, etc.)
            rule_data: Rule data from the event

        Returns:
            bool: True if successful
        """
        try:
            customer_id = rule_data.get('customer_id')  # None for default rules
            rule_id = rule_data.get('rule_id') or rule_data.get('id')
            actual_rule_data = rule_data.get('rule_data', rule_data)

            logger.debug(f"🔔 Handling Sigma rule event: {event_type} for customer {customer_id or 'default'}, rule {rule_id}")

            if event_type == EVENT_SIGMA_RULE_CREATED:
                return await self.update_rule_cache(customer_id, actual_rule_data)

            elif event_type == EVENT_SIGMA_RULE_UPDATED:
                return await self.update_rule_cache(customer_id, actual_rule_data)

            elif event_type == EVENT_SIGMA_RULE_DELETED:
                if rule_id:
                    return await self.remove_rule_from_cache(customer_id, rule_id)
                else:
                    logger.error("No rule_id provided for deletion event")
                    return False

            elif event_type in [EVENT_SIGMA_RULE_ENABLED, EVENT_SIGMA_RULE_DISABLED]:
                # Update the rule's enabled status
                actual_rule_data['enabled'] = (event_type == EVENT_SIGMA_RULE_ENABLED)
                return await self.update_rule_cache(customer_id, actual_rule_data)

            else:
                logger.warning(f"Unknown Sigma rule event type: {event_type}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to handle Sigma rule event {event_type}: {e}")
            return False

    async def _cache_customer_rules(self, customer_id: str, rules: List[Dict[str, Any]]) -> bool:
        """
        Internal method to cache rules for a specific customer.

        Args:
            customer_id: Customer/tenant ID
            rules: List of rule dictionaries

        Returns:
            bool: True if successful
        """
        try:
            cache_key = f"{self.cache_prefix}{customer_id}"
            # Filter only enabled rules for performance (handle both boolean and integer values)
            enabled_rules = [rule for rule in rules if rule.get('enabled') in (True, 1, '1')]
            logger.info(f"found {len(enabled_rules)} for {customer_id}")
            success = await self.redis_manager.set(cache_key, enabled_rules)

            if success:
                logger.debug(f"📦 Cached {len(enabled_rules)}/{len(rules)} enabled Sigma rules for customer {customer_id}")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to cache Sigma rules for customer {customer_id}: {e}")
            return False

    async def _cache_default_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """
        Internal method to cache default rules.

        Args:
            rules: List of default rule dictionaries

        Returns:
            bool: True if successful
        """
        try:
            # Filter only enabled rules for performance (handle both boolean and integer values)
            enabled_rules = [rule for rule in rules if rule.get('enabled') in (True, 1, '1')]

            success = await self.redis_manager.set(self.default_rules_key, enabled_rules)

            if success:
                logger.debug(f"📦 Cached {len(enabled_rules)}/{len(rules)} enabled default Sigma rules")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to cache default Sigma rules: {e}")
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and health information.

        Returns:
            Dictionary with cache statistics
        """
        try:
            # Get cache metadata
            metadata = await self.redis_manager.get(self.metadata_key, default={})

            # Count cached customers
            pattern = f"{self.cache_prefix}*"
            cached_keys = await self.redis_manager.scan_keys(pattern)
            cached_customers = len(cached_keys)

            # Check if default rules are cached
            default_rules_cached = await self.redis_manager.exists(self.default_rules_key)

            # Get Redis health
            redis_health = await self.redis_manager.health_check()

            return {
                "cache_status": "healthy" if redis_health.get("connected") else "unhealthy",
                "cached_customers": cached_customers,
                "default_rules_cached": default_rules_cached,
                "last_updated": metadata.get("last_updated"),
                "total_rules": metadata.get("total_rules", 0),
                "default_rules_count": metadata.get("default_rules", 0),
                "redis_health": redis_health
            }

        except Exception as e:
            logger.error(f"❌ Failed to get Sigma rule cache stats: {e}")
            return {
                "cache_status": "error",
                "error": str(e)
            }
