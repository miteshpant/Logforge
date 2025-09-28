"""
Billing Service - Usage-Based Cost Calculation
Handles bill generation using YAML pricing configuration and real database usage
"""

import yaml
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

class BillingService:
    """Service for calculating usage-based billing costs"""
    
    def __init__(self):
        """Initialize billing service with pricing configuration"""
        self.pricing_config = self._load_pricing_config()
        
    def _load_pricing_config(self) -> Dict[str, Any]:
        """Load pricing configuration from YAML file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'pricing.yml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
                logger.info("Pricing configuration loaded successfully", version=config.get('pricing_version'))
                return config
        except Exception as e:
            logger.error("Failed to load pricing configuration", error=str(e))
            raise Exception(f"Pricing configuration not available: {str(e)}")
    
    async def calculate_bill(self, tenant_id: str, subscription_tier: str, usage_data: Dict[str, Any], 
                           promo_code: Optional[str] = None) -> Dict[str, Any]:
        """Calculate total bill amount based on real usage data and YAML pricing"""
        try:
            # Get base subscription fee
            base_fee = self._get_base_fee(subscription_tier)
            
            # Calculate usage charges from real database data
            usage_charges = self._calculate_usage_charges(usage_data)
            
            # Apply tier-based discount
            tier_discount = self._get_tier_discount(subscription_tier, usage_charges)
            
            # Apply promo code discount if provided
            promo_discount = 0.0
            if promo_code:
                promo_discount = self._calculate_promo_discount(promo_code, base_fee + usage_charges, subscription_tier)
            
            # Calculate totals
            subtotal = base_fee + usage_charges
            total_discount = tier_discount + promo_discount
            minimum_charge = self.pricing_config.get('billing', {}).get('minimum_charge', 5.00)
            total_amount = max(subtotal - total_discount, minimum_charge)
            
            bill_details = {
                "tenant_id": tenant_id,
                "subscription_tier": subscription_tier,
                "billing_breakdown": {
                    "base_fee": round(base_fee, 2),
                    "usage_charges": round(usage_charges, 2),
                    "subtotal": round(subtotal, 2),
                    "tier_discount": round(tier_discount, 2),
                    "promo_discount": round(promo_discount, 2),
                    "total_discount": round(total_discount, 2),
                    "total_amount": round(total_amount, 2)
                },
                "usage_details": self._format_usage_details(usage_data),
                "currency": self.pricing_config.get("currency", "USD"),
                "promo_code": promo_code if promo_code else None
            }
            
            logger.info("Bill calculated successfully", 
                       tenant_id=tenant_id, 
                       total_amount=total_amount,
                       tier=subscription_tier,
                       usage_charges=usage_charges,
                       base_fee=base_fee)
            
            return bill_details
            
        except Exception as e:
            logger.error("Failed to calculate bill", error=str(e), tenant_id=tenant_id)
            raise Exception(f"Bill calculation failed: {str(e)}")
    
    def _get_base_fee(self, subscription_tier: str) -> float:
        """Get base subscription fee for tier from YAML config"""
        tier_config = self.pricing_config.get("subscription_tiers", {}).get(subscription_tier)
        if not tier_config:
            raise Exception(f"Unknown subscription tier: {subscription_tier}")
        return tier_config.get("base_fee", 0.0)
    
    def _calculate_usage_charges(self, usage_data: Dict[str, Any]) -> float:
        """Calculate usage-based charges from real database usage data"""
        total_usage_cost = 0.0
        feature_pricing = self.pricing_config.get("feature_pricing", {})
        
        # Calculate ingestion charges (GB ingested)
        ingestion_gb = usage_data.get("ingestion_gb", 0)
        if ingestion_gb > 0:
            ingestion_price = feature_pricing.get("ingestion.basic", {}).get("base_price", 0.50)
            ingestion_cost = ingestion_gb * ingestion_price
            total_usage_cost += ingestion_cost
            logger.debug("Ingestion cost calculated", gb=ingestion_gb, unit_price=ingestion_price, cost=ingestion_cost)
        
        # Calculate storage charges (GB stored)
        storage_gb = usage_data.get("storage_gb", 0)
        if storage_gb > 0:
            storage_price = feature_pricing.get("storage.hot", {}).get("base_price", 0.10)
            storage_cost = storage_gb * storage_price
            total_usage_cost += storage_cost
            logger.debug("Storage cost calculated", gb=storage_gb, unit_price=storage_price, cost=storage_cost)
        
        # Calculate API call charges (per 1000 calls)
        api_calls = usage_data.get("api_calls", 0)
        if api_calls > 0:
            api_price = feature_pricing.get("api.calls", {}).get("base_price", 1.50)
            api_cost = (api_calls / 1000.0) * api_price
            total_usage_cost += api_cost
            logger.debug("API cost calculated", calls=api_calls, unit_price=api_price, cost=api_cost)
        
        # Calculate query charges (per 1000 queries)
        query_count = usage_data.get("query_count", 0)
        if query_count > 0:
            query_price = feature_pricing.get("queries.basic", {}).get("base_price", 2.00)
            query_cost = (query_count / 1000.0) * query_price
            total_usage_cost += query_cost
            logger.debug("Query cost calculated", queries=query_count, unit_price=query_price, cost=query_cost)
        
        return total_usage_cost
    
    def _get_tier_discount(self, subscription_tier: str, usage_charges: float) -> float:
        """Calculate tier-based discount on usage charges"""
        tier_discounts = self.pricing_config.get("tier_discounts", {})
        tier_config = tier_discounts.get(subscription_tier, {})
        
        discount_percent = tier_config.get("discount_percent", 0)
        discount_amount = (usage_charges * discount_percent) / 100.0
        
        # Check for volume discounts
        volume_discounts = tier_config.get("volume_discounts", [])
        for volume_tier in sorted(volume_discounts, key=lambda x: x.get("threshold", 0), reverse=True):
            threshold = volume_tier.get("threshold", 0)
            if usage_charges >= threshold:
                volume_discount_percent = volume_tier.get("discount_percent", 0)
                discount_amount = max(discount_amount, (usage_charges * volume_discount_percent) / 100.0)
                logger.debug("Volume discount applied", threshold=threshold, discount_percent=volume_discount_percent)
                break
        
        return discount_amount
    
    def _calculate_promo_discount(self, promo_code: str, subtotal: float, subscription_tier: str) -> float:
        """Calculate promotional code discount from YAML config"""
        promo_codes = self.pricing_config.get("promo_codes", {})
        promo_config = promo_codes.get(promo_code.upper())
        
        if not promo_config:
            logger.warning("Invalid promo code", code=promo_code)
            return 0.0
        
        # Check if promo code is applicable to this tier
        applicable_tiers = promo_config.get("applicable_tiers", [])
        if applicable_tiers and subscription_tier not in applicable_tiers:
            logger.warning("Promo code not applicable to tier", code=promo_code, tier=subscription_tier)
            return 0.0
        
        # Check if promo code is still valid
        valid_until = promo_config.get("valid_until")
        if valid_until:
            try:
                expiry_date = datetime.strptime(valid_until, "%Y-%m-%d")
                if datetime.now() > expiry_date:
                    logger.warning("Promo code expired", code=promo_code, expiry=valid_until)
                    return 0.0
            except ValueError:
                logger.error("Invalid promo code expiry date format", code=promo_code, expiry=valid_until)
                return 0.0
        
        discount_percent = promo_config.get("discount_percent", 0)
        discount_amount = (subtotal * discount_percent) / 100.0
        
        logger.info("Promo code applied", 
                   code=promo_code, 
                   discount_percent=discount_percent,
                   discount_amount=discount_amount)
        
        return discount_amount
    
    def _format_usage_details(self, usage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format usage data for detailed bill breakdown"""
        details = []
        
        # Add each usage item with pricing details
        ingestion_gb = usage_data.get("ingestion_gb", 0)
        if ingestion_gb > 0:
            ingestion_price = self.pricing_config.get("feature_pricing", {}).get("ingestion.basic", {}).get("base_price", 0.50)
            details.append({
                "description": "Log Ingestion",
                "quantity": ingestion_gb,
                "unit": "GB",
                "unit_price": ingestion_price,
                "total_cost": round(ingestion_gb * ingestion_price, 4)
            })
        
        storage_gb = usage_data.get("storage_gb", 0)
        if storage_gb > 0:
            storage_price = self.pricing_config.get("feature_pricing", {}).get("storage.hot", {}).get("base_price", 0.10)
            details.append({
                "description": "Hot Storage",
                "quantity": storage_gb,
                "unit": "GB",
                "unit_price": storage_price,
                "total_cost": round(storage_gb * storage_price, 4)
            })
        
        api_calls = usage_data.get("api_calls", 0)
        if api_calls > 0:
            api_price = self.pricing_config.get("feature_pricing", {}).get("api.calls", {}).get("base_price", 1.50)
            api_units = api_calls / 1000.0
            details.append({
                "description": "API Calls",
                "quantity": api_calls,
                "unit": "calls",
                "unit_price": f"${api_price}/1000 calls",
                "total_cost": round(api_units * api_price, 4)
            })
        
        query_count = usage_data.get("query_count", 0)
        if query_count > 0:
            query_price = self.pricing_config.get("feature_pricing", {}).get("queries.basic", {}).get("base_price", 2.00)
            query_units = query_count / 1000.0
            details.append({
                "description": "Search Queries",
                "quantity": query_count,
                "unit": "queries",
                "unit_price": f"${query_price}/1000 queries",
                "total_cost": round(query_units * query_price, 4)
            })
        
        return details
    
    def validate_promo_code(self, promo_code: str, subscription_tier: str) -> Dict[str, Any]:
        """Validate promo code and return discount information"""
        promo_codes = self.pricing_config.get("promo_codes", {})
        promo_config = promo_codes.get(promo_code.upper())
        
        if not promo_config:
            return {"valid": False, "error": "Invalid promo code"}
        
        # Check tier applicability
        applicable_tiers = promo_config.get("applicable_tiers", [])
        if applicable_tiers and subscription_tier not in applicable_tiers:
            return {"valid": False, "error": f"Promo code not applicable to {subscription_tier} tier"}
        
        # Check expiry
        valid_until = promo_config.get("valid_until")
        if valid_until:
            try:
                expiry_date = datetime.strptime(valid_until, "%Y-%m-%d")
                if datetime.now() > expiry_date:
                    return {"valid": False, "error": "Promo code has expired"}
            except ValueError:
                return {"valid": False, "error": "Invalid promo code configuration"}
        
        return {
            "valid": True,
            "discount_percent": promo_config.get("discount_percent", 0),
            "description": promo_config.get("description", ""),
            "valid_until": valid_until
        }

# Global billing service instance
billing_service = BillingService()