"""
Security Subscription Checker - Integration with Existing Subscription Service
Checks tenant access to security analytics features using existing infrastructure
"""

from typing import Optional, List, Dict, Any
import structlog

from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)


class SecuritySubscriptionChecker:
    """Checks security feature access using existing subscription infrastructure"""
    
    # Map existing subscription plans to security capabilities
    PLAN_SECURITY_FEATURES = {
        # Starter plans - no security analytics
        "starter": {
            "security_analytics": False,
            "max_security_rules": 0,
            "included_severities": []
        },
        "basic": {
            "security_analytics": False,
            "max_security_rules": 0,
            "included_severities": []
        },
        
        # Professional plans - basic security
        "professional": {
            "security_analytics": True,
            "max_security_rules": 100,
            "included_severities": ["high", "critical"]
        },
        "standard": {
            "security_analytics": True,
            "max_security_rules": 150,
            "included_severities": ["medium", "high", "critical"]
        },
        
        # Enterprise plans - full security
        "premium": {
            "security_analytics": True,
            "max_security_rules": 250,
            "included_severities": ["low", "medium", "high", "critical"]
        },
        "enterprise": {
            "security_analytics": True,
            "max_security_rules": 286,  # All MITRE rules
            "included_severities": ["low", "medium", "high", "critical"]
        }
    }
    
    # Security feature billing rates (per detection event)
    SECURITY_BILLING_RATES = {
        "professional": {"cost_per_event": 0.10, "included_events": 1000},
        "standard": {"cost_per_event": 0.08, "included_events": 2000},
        "premium": {"cost_per_event": 0.05, "included_events": 5000},
        "enterprise": {"cost_per_event": 0.02, "included_events": 20000}
    }
    
    def __init__(self):
        import os
        service_key = os.getenv('SECURITY_SUBSCRIPTION_CHECKER_KEY', 'security-subscription-checker-service-key')
        self.database = DatabaseLayer("SecuritySubscriptionChecker", service_key)
    
    async def has_security_analytics_access(self, customer_id: str) -> bool:
        """
        Check if tenant has security analytics in their subscription
        
        Args:
            customer_id: Tenant ID
            
        Returns:
            bool: True if tenant has security analytics access
        """
        try:
            subscription = await self._get_tenant_subscription(customer_id)
            
            if not subscription:
                logger.debug(f"No subscription found for tenant {customer_id}")
                return False
            
            # Use correct field names from subscription data
            tier = subscription.get("subscription_tier", "").lower()  
            status = subscription.get("status", "").lower()
            features = subscription.get("subscribed_features", "")
            
            # Check if subscription is active
            if status != "active":
                logger.debug(f"Inactive subscription for tenant {customer_id}: {status}")
                return False
            
            # Check if subscription includes security features
            # Features can be: "['*']" (all features) or contain "security.*"
            if features == "['*']":
                logger.debug(f"Customer {customer_id} has ALL features access: {features}")
                return True
                
            if "security.*" in features or "security" in features:
                logger.debug(f"Customer {customer_id} has explicit security features: {features}")
                return True
            
            # Fallback to tier-based check using existing mapping
            plan_features = self.PLAN_SECURITY_FEATURES.get(tier, {})
            has_access = plan_features.get("security_analytics", False)
            
            logger.info(f"Security access for tenant {customer_id}: tier={tier}, features={features}, has_access={has_access}")
            return has_access
            
        except Exception as e:
            logger.error(f"Error checking security access for tenant {customer_id}: {e}")
            return False
    
    async def get_security_tier(self, customer_id: str) -> Optional[str]:
        """
        Get security subscription tier for tenant
        
        Args:
            customer_id: Tenant ID
            
        Returns:
            Optional[str]: Security tier ('basic', 'advanced', 'enterprise') or None
        """
        try:
            subscription = await self._get_tenant_subscription(customer_id)
            
            if not subscription:
                return None
            
            plan = subscription.get("plan", "").lower()
            
            # Map subscription plans to security tiers
            if plan in ["enterprise", "premium"]:
                return "enterprise"
            elif plan in ["professional", "standard"]:
                return "advanced"
            elif plan in ["basic", "starter"]:
                return "basic"
            else:
                logger.warning(f"Unknown subscription plan for tenant {customer_id}: {plan}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting security tier for tenant {customer_id}: {e}")
            return None
    
    async def get_allowed_security_rules(self, customer_id: str) -> Dict[str, Any]:
        """
        Get allowed security rules configuration for tenant
        
        Args:
            customer_id: Tenant ID
            
        Returns:
            Dict with rule limits and allowed severities
        """
        try:
            subscription = await self._get_tenant_subscription(customer_id)
            
            if not subscription:
                return {
                    "max_rules": 0,
                    "allowed_severities": [],
                    "has_access": False
                }
            
            plan = subscription.get("plan", "").lower()
            plan_features = self.PLAN_SECURITY_FEATURES.get(plan, {})
            
            return {
                "max_rules": plan_features.get("max_security_rules", 0),
                "allowed_severities": plan_features.get("included_severities", []),
                "has_access": plan_features.get("security_analytics", False),
                "plan": plan
            }
            
        except Exception as e:
            logger.error(f"Error getting security rules config for tenant {customer_id}: {e}")
            return {
                "max_rules": 0,
                "allowed_severities": [],
                "has_access": False,
                "error": str(e)
            }
    
    async def filter_rules_by_subscription(
        self, 
        customer_id: str, 
        rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter security rules based on tenant's subscription
        
        Args:
            customer_id: Tenant ID
            rules: List of sigma rules
            
        Returns:
            List of filtered rules based on subscription
        """
        try:
            # Get subscription limits
            rule_config = await self.get_allowed_security_rules(customer_id)
            
            if not rule_config["has_access"]:
                logger.debug(f"No security access for tenant {customer_id}")
                return []
            
            max_rules = rule_config["max_rules"]
            allowed_severities = rule_config["allowed_severities"]
            
            # Filter by severity
            severity_filtered = []
            for rule in rules:
                rule_severity = rule.get("severity", "").lower()
                if rule_severity in allowed_severities:
                    severity_filtered.append(rule)
            
            # Limit by max rules (prioritize by severity)
            severity_priority = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            
            sorted_rules = sorted(
                severity_filtered,
                key=lambda r: severity_priority.get(r.get("severity", "").lower(), 0),
                reverse=True
            )
            
            # Apply rule limit
            final_rules = sorted_rules[:max_rules] if max_rules > 0 else sorted_rules
            
            logger.debug(
                f"Filtered rules for tenant {customer_id}: "
                f"{len(rules)} → {len(severity_filtered)} → {len(final_rules)} "
                f"(plan: {rule_config.get('plan', 'unknown')})"
            )
            
            return final_rules
            
        except Exception as e:
            logger.error(f"Error filtering rules for tenant {customer_id}: {e}")
            return []
    
    async def calculate_security_billing(
        self, 
        customer_id: str, 
        event_count: int, 
        billing_period: str
    ) -> Dict[str, Any]:
        """
        Calculate security feature billing for tenant
        
        Args:
            customer_id: Tenant ID
            event_count: Number of security events generated
            billing_period: Billing period (e.g., "2025-01")
            
        Returns:
            Dict with billing calculation
        """
        try:
            subscription = await self._get_tenant_subscription(customer_id)
            
            if not subscription:
                return {
                    "customer_id": customer_id,
                    "billing_period": billing_period,
                    "total_events": event_count,
                    "billable_events": 0,
                    "total_cost": 0.0,
                    "error": "No subscription found"
                }
            
            plan = subscription.get("plan", "").lower()
            billing_config = self.SECURITY_BILLING_RATES.get(plan, {})
            
            if not billing_config:
                return {
                    "customer_id": customer_id,
                    "billing_period": billing_period,
                    "total_events": event_count,
                    "billable_events": 0,
                    "total_cost": 0.0,
                    "error": f"No billing config for plan: {plan}"
                }
            
            # Calculate billable events
            included_events = billing_config["included_events"]
            cost_per_event = billing_config["cost_per_event"]
            
            billable_events = max(0, event_count - included_events)
            total_cost = billable_events * cost_per_event
            
            return {
                "customer_id": customer_id,
                "billing_period": billing_period,
                "subscription_plan": plan,
                "total_events": event_count,
                "included_events": included_events,
                "billable_events": billable_events,
                "cost_per_event": cost_per_event,
                "total_cost": round(total_cost, 2),
                "has_security_access": self.PLAN_SECURITY_FEATURES.get(plan, {}).get("security_analytics", False)
            }
            
        except Exception as e:
            logger.error(f"Error calculating security billing for tenant {customer_id}: {e}")
            return {
                "customer_id": customer_id,
                "billing_period": billing_period,
                "total_events": event_count,
                "billable_events": 0,
                "total_cost": 0.0,
                "error": str(e)
            }
    
    async def get_security_usage_summary(self, customer_id: str, period: str) -> Dict[str, Any]:
        """
        Get security feature usage summary for tenant
        
        Args:
            customer_id: Tenant ID
            period: Period in YYYY-MM format
            
        Returns:
            Dict with usage summary
        """
        try:
            # Count security events for the period
            period_filter = period.replace("-", "")
            
            result = await self.database.execute(
                f"""
                SELECT 
                    count(*) as total_events,
                    severity,
                    count(*) as events_by_severity
                FROM security_events_mt 
                WHERE customer_id = '{customer_id}'
                AND toYYYYMM(created_at) = '{period_filter}'
                AND event_type = 'sigma_detection'
                GROUP BY severity
                """
            )
            
            total_events = sum(row["total_events"] for row in result)
            events_by_severity = {row["severity"]: row["events_by_severity"] for row in result}
            
            # Get billing calculation
            billing = await self.calculate_security_billing(customer_id, total_events, period)
            
            # Get subscription info
            subscription_config = await self.get_allowed_security_rules(customer_id)
            
            return {
                "customer_id": customer_id,
                "period": period,
                "total_security_events": total_events,
                "events_by_severity": events_by_severity,
                "billing": billing,
                "subscription": subscription_config,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error getting security usage summary for tenant {customer_id}: {e}")
            return {
                "customer_id": customer_id,
                "period": period,
                "error": str(e),
                "status": "error"
            }
    
    async def _get_tenant_subscription(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant subscription from existing subscription table"""
        try:
            result = await self.database.execute_query(
                f"""
                SELECT customer_id, subscription_tier, status, subscribed_features, created_at, updated_at
                FROM tenant_subscriptions_mt 
                WHERE customer_id = '{customer_id}'
                AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error fetching subscription for tenant {customer_id}: {e}")
            return None


# Singleton instance for production use
security_subscription_checker = SecuritySubscriptionChecker()


async def check_security_access(customer_id: str) -> bool:
    """
    Quick check if tenant has security analytics access
    
    Args:
        customer_id: Tenant ID
        
    Returns:
        bool: True if tenant has access
    """
    return await security_subscription_checker.has_security_analytics_access(customer_id)


async def get_filtered_security_rules(customer_id: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get security rules filtered by tenant subscription
    
    Args:
        customer_id: Tenant ID
        rules: List of security rules
        
    Returns:
        List of filtered rules
    """
    return await security_subscription_checker.filter_rules_by_subscription(customer_id, rules)


async def calculate_security_cost(customer_id: str, event_count: int, period: str) -> Dict[str, Any]:
    """
    Calculate security billing cost for tenant
    
    Args:
        customer_id: Tenant ID
        event_count: Number of security events
        period: Billing period
        
    Returns:
        Dict with billing calculation
    """
    return await security_subscription_checker.calculate_security_billing(customer_id, event_count, period)


if __name__ == "__main__":
    # Test the subscription checker
    import asyncio
    
    async def test_subscription_checker():
        print("🧪 Testing Security Subscription Checker...")
        
        test_customer_id = "test_tenant_001"
        
        # Test access check
        has_access = await check_security_access(test_customer_id)
        print(f"✅ Security access: {has_access}")
        
        # Test tier
        tier = await security_subscription_checker.get_security_tier(test_customer_id)
        print(f"✅ Security tier: {tier}")
        
        # Test rule limits
        rule_config = await security_subscription_checker.get_allowed_security_rules(test_customer_id)
        print(f"✅ Rule config: {rule_config}")
        
        print("🎉 Test complete!")
    
    # Run test
    asyncio.run(test_subscription_checker())