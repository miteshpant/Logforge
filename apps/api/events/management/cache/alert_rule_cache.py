"""
Alert Rule Cache Management

Manages Redis cache for alert rules with event-driven updates.
Based on the Alert Matching System Plan specifications.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .redis_manager import RedisManager

logger = logging.getLogger(__name__)

class AlertRuleCache:
    """
    Manages Redis cache for alert rules with event-driven updates.
    
    Cache Structure:
    - alerts:rules:{customer_id} → JSON array of rule objects
    - alerts:cooldown:{rule_id} → timestamp (TTL-based)
    - alerts:cache:metadata → cache metadata
    """
    
    def __init__(self, redis_manager: Optional[RedisManager] = None):
        """
        Initialize alert rule cache manager.
        
        Args:
            redis_manager: Redis manager instance (optional, will create if not provided)
        """
        self.redis_manager = redis_manager or RedisManager()
        self.cache_prefix = "alerts:rules:"
        self.cooldown_prefix = "alerts:cooldown:"
        self.metadata_key = "alerts:cache:metadata"
        
    async def initialize_cache_from_db(self) -> bool:
        """
        Load all alert rules from database into Redis cache.
        This is typically run at startup or after cache invalidation.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from services.alert_service import AlertService
            
            logger.info("🔄 Initializing alert rule cache from database...")
            
            alert_service = AlertService()
            
            # Get all active tenants with alert rules
            all_rules = await alert_service.get_all_alert_rules()
            
            # Group rules by customer_id
            rules_by_customer = {}
            total_rules = 0
            
            for rule in all_rules:
                customer_id = rule.get('customer_id')
                if customer_id:
                    if customer_id not in rules_by_customer:
                        rules_by_customer[customer_id] = []
                    rules_by_customer[customer_id].append(rule)
                    total_rules += 1
            
            # Cache rules for each customer
            successful_customers = 0
            for customer_id, rules in rules_by_customer.items():
                if await self._cache_customer_rules(customer_id, rules):
                    successful_customers += 1
                    logger.debug(f"✅ Cached {len(rules)} rules for customer {customer_id}")
                else:
                    logger.error(f"❌ Failed to cache rules for customer {customer_id}")
            
            # Update cache metadata
            metadata = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "total_customers": len(rules_by_customer),
                "total_rules": total_rules,
                "successful_customers": successful_customers
            }
            
            await self.redis_manager.set(self.metadata_key, metadata)
            
            logger.info(f"✅ Alert rule cache initialized: {total_rules} rules for {successful_customers}/{len(rules_by_customer)} customers")
            return successful_customers == len(rules_by_customer)
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize alert rule cache: {e}")
            return False
    
    async def get_customer_rules(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get alert rules for a customer from cache, fallback to DB if needed.
        
        Args:
            customer_id: Customer/tenant ID
            
        Returns:
            List of rule dictionaries
        """
        try:
            cache_key = f"{self.cache_prefix}{customer_id}"
            
            # Try to get from cache first
            cached_rules = await self.redis_manager.get(cache_key, default=[])
            
            if cached_rules:
                logger.debug(f"✅ Cache hit: Retrieved {len(cached_rules)} rules for customer {customer_id}")
                return cached_rules
            
            # Cache miss - fallback to database
            logger.debug(f"⚠️ Cache miss for customer {customer_id}, falling back to database")
            
            from services.alert_service import AlertService
            alert_service = AlertService()
            
            # Get rules from database
            db_rules = await alert_service.get_alert_rules_for_customer(customer_id)
            
            # Cache the rules for future requests
            if db_rules:
                await self._cache_customer_rules(customer_id, db_rules)
                logger.debug(f"📦 Cached {len(db_rules)} rules for customer {customer_id} from DB fallback")
            
            return db_rules or []
            
        except Exception as e:
            logger.error(f"❌ Failed to get customer rules for {customer_id}: {e}")
            return []
    
    async def update_rule_cache(self, customer_id: str, rule_data: Dict[str, Any]) -> bool:
        """
        Update specific rule in cache for a customer.
        
        Args:
            customer_id: Customer/tenant ID
            rule_data: Rule data dictionary
            
        Returns:
            bool: True if successful
        """
        try:
            cache_key = f"{self.cache_prefix}{customer_id}"
            rule_id = rule_data.get('id')
            
            if not rule_id:
                logger.error("No rule ID provided for cache update")
                return False
            
            # Get current rules from cache
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
                logger.debug(f"➕ Added new rule {rule_id} to cache for customer {customer_id}")
            else:
                logger.debug(f"🔄 Updated rule {rule_id} in cache for customer {customer_id}")
            
            # Update cache
            success = await self.redis_manager.set(cache_key, current_rules)
            
            if success:
                logger.debug(f"✅ Successfully updated rule cache for customer {customer_id}")
            else:
                logger.error(f"❌ Failed to update rule cache for customer {customer_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to update rule cache for customer {customer_id}: {e}")
            return False
    
    async def remove_rule_from_cache(self, customer_id: str, rule_id: str) -> bool:
        """
        Remove specific rule from cache for a customer.
        
        Args:
            customer_id: Customer/tenant ID
            rule_id: Rule ID to remove
            
        Returns:
            bool: True if successful
        """
        try:
            cache_key = f"{self.cache_prefix}{customer_id}"
            
            # Get current rules from cache
            current_rules = await self.redis_manager.get(cache_key, default=[])
            
            # Filter out the rule to be removed
            original_count = len(current_rules)
            current_rules = [rule for rule in current_rules if rule.get('id') != rule_id]
            
            if len(current_rules) < original_count:
                # Update cache with filtered rules
                success = await self.redis_manager.set(cache_key, current_rules)
                logger.debug(f"🗑️ Removed rule {rule_id} from cache for customer {customer_id}")
                return success
            else:
                logger.debug(f"⚠️ Rule {rule_id} not found in cache for customer {customer_id}")
                return True  # Rule wasn't in cache anyway
                
        except Exception as e:
            logger.error(f"❌ Failed to remove rule from cache for customer {customer_id}: {e}")
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
            
            logger.debug(f"🧹 Invalidated cache for customer {customer_id} (deleted {deleted_count} keys)")
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"❌ Failed to invalidate cache for customer {customer_id}: {e}")
            return False
    
    async def handle_rule_event(self, event_type: str, rule_data: Dict[str, Any]) -> bool:
        """
        Handle rule CRUD events for cache updates.
        
        Args:
            event_type: Type of event (alert.rule.created, updated, deleted, etc.)
            rule_data: Rule data from the event
            
        Returns:
            bool: True if successful
        """
        try:
            customer_id = rule_data.get('customer_id')
            rule_id = rule_data.get('id')
            
            if not customer_id:
                logger.error(f"No customer_id in rule event data: {event_type}")
                return False
            
            logger.debug(f"🔔 Handling rule event: {event_type} for customer {customer_id}, rule {rule_id}")
            
            if event_type == "alert.rule.created":
                return await self.update_rule_cache(customer_id, rule_data)
                
            elif event_type == "alert.rule.updated":
                return await self.update_rule_cache(customer_id, rule_data)
                
            elif event_type == "alert.rule.deleted":
                if rule_id:
                    return await self.remove_rule_from_cache(customer_id, rule_id)
                else:
                    logger.error("No rule_id provided for deletion event")
                    return False
                    
            elif event_type in ["alert.rule.enabled", "alert.rule.disabled"]:
                # Update the rule's enabled status
                rule_data['is_enabled'] = (event_type == "alert.rule.enabled")
                return await self.update_rule_cache(customer_id, rule_data)
                
            else:
                logger.warning(f"Unknown rule event type: {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to handle rule event {event_type}: {e}")
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
            
            # Filter only enabled rules for performance
            enabled_rules = [rule for rule in rules if rule.get('is_enabled', False)]
            
            success = await self.redis_manager.set(cache_key, enabled_rules)
            
            if success:
                logger.debug(f"📦 Cached {len(enabled_rules)}/{len(rules)} enabled rules for customer {customer_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to cache rules for customer {customer_id}: {e}")
            return False
    
    async def set_rule_cooldown(self, rule_id: str, cooldown_minutes: int) -> bool:
        """
        Set cooldown period for a rule to prevent rapid firing.
        
        Args:
            rule_id: Rule ID
            cooldown_minutes: Cooldown period in minutes
            
        Returns:
            bool: True if successful
        """
        try:
            cooldown_key = f"{self.cooldown_prefix}{rule_id}"
            cooldown_seconds = cooldown_minutes * 60
            
            # Set with TTL (automatic expiration)
            success = await self.redis_manager.set(
                cooldown_key, 
                datetime.now(timezone.utc).isoformat(), 
                ttl=cooldown_seconds
            )
            
            if success:
                logger.debug(f"⏰ Set {cooldown_minutes}min cooldown for rule {rule_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Failed to set cooldown for rule {rule_id}: {e}")
            return False
    
    async def is_rule_in_cooldown(self, rule_id: str) -> bool:
        """
        Check if rule is currently in cooldown period.
        
        Args:
            rule_id: Rule ID
            
        Returns:
            bool: True if in cooldown, False otherwise
        """
        try:
            cooldown_key = f"{self.cooldown_prefix}{rule_id}"
            return await self.redis_manager.exists(cooldown_key)
            
        except Exception as e:
            logger.error(f"❌ Failed to check cooldown for rule {rule_id}: {e}")
            return False  # Default to allowing rule execution
    
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
            
            # Get Redis health
            redis_health = await self.redis_manager.health_check()
            
            return {
                "cache_status": "healthy" if redis_health.get("connected") else "unhealthy",
                "cached_customers": cached_customers,
                "last_updated": metadata.get("last_updated"),
                "total_rules": metadata.get("total_rules", 0),
                "redis_health": redis_health
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get cache stats: {e}")
            return {
                "cache_status": "error",
                "error": str(e)
            }