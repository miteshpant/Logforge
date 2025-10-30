"""
MITRE Rule Loader - Production System Integration
Loads all 286 MITRE ATT&CK rules for tenants using existing infrastructure
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog

from mitre_metadata_generator import generate_production_metadata, MitreTechniqueMetadata
from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)


class MitreRuleLoader:
    """Production-ready MITRE rule loader using existing infrastructure"""
    
    def __init__(self):
        self.database = DatabaseLayer()
        
    async def initialize_mitre_rules_for_tenant(self, customer_id: str) -> int:
        """
        Load all 286 MITRE rules for a specific tenant (idempotent)
        
        Args:
            customer_id: Tenant ID
            
        Returns:
            int: Number of new rules loaded
        """
        try:
            logger.info(f"🎯 Loading MITRE rules for tenant {customer_id}")
            
            # Generate all 286 technique metadata
            metadata = generate_production_metadata()
            loaded_count = 0
            
            for technique_id, meta in metadata.items():
                rule_id = f"mitre_{technique_id.lower()}"
                
                # Check if rule already exists for this tenant (idempotent)
                existing = await self._get_tenant_rule(customer_id, rule_id)
                
                if not existing:
                    # Create new MITRE rule
                    sigma_rule = self._create_sigma_rule_from_metadata(
                        rule_id=rule_id,
                        customer_id=customer_id,
                        technique_id=technique_id,
                        metadata=meta
                    )
                    
                    await self._insert_sigma_rule(sigma_rule)
                    loaded_count += 1
                    
                    if loaded_count % 50 == 0:
                        logger.info(f"📊 Loaded {loaded_count}/286 rules for tenant {customer_id}")
                else:
                    # Optionally update existing rule if metadata changed
                    await self._update_rule_if_needed(existing, meta)
            
            logger.info(f"✅ Completed: {loaded_count} new MITRE rules loaded for tenant {customer_id}")
            return loaded_count
            
        except Exception as e:
            logger.error(f"❌ Error loading MITRE rules for tenant {customer_id}: {e}")
            raise
    
    async def initialize_mitre_rules_for_all_tenants(self) -> Dict[str, int]:
        """
        Load MITRE rules for all active tenants
        
        Returns:
            Dict mapping customer_id to number of rules loaded
        """
        try:
            logger.info("🚀 Starting MITRE rule initialization for all tenants...")
            
            # Get all active tenants
            active_tenants = await self._get_all_active_tenants()
            logger.info(f"📋 Found {len(active_tenants)} active tenants")
            
            results = {}
            total_loaded = 0
            
            for tenant in active_tenants:
                customer_id = tenant.get("customer_id") or tenant.get("id")
                if not customer_id:
                    logger.warning(f"Skipping tenant with no ID: {tenant}")
                    continue
                
                loaded_count = await self.initialize_mitre_rules_for_tenant(customer_id)
                results[customer_id] = loaded_count
                total_loaded += loaded_count
            
            logger.info(f"🎉 MITRE rule initialization complete!")
            logger.info(f"📊 Summary: {total_loaded} total rules loaded across {len(results)} tenants")
            logger.info(f"📈 Average: {total_loaded / len(results):.1f} new rules per tenant")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in bulk MITRE rule initialization: {e}")
            raise
    
    async def verify_mitre_coverage(self, customer_id: str) -> Dict[str, Any]:
        """
        Verify MITRE rule coverage for a tenant
        
        Args:
            customer_id: Tenant ID
            
        Returns:
            Dict with coverage statistics
        """
        try:
            # Count existing MITRE rules for tenant
            existing_rules = await self._count_tenant_mitre_rules(customer_id)
            
            # Expected count is 286 (all MITRE Enterprise techniques)
            expected_count = 286
            coverage_percentage = (existing_rules / expected_count) * 100
            
            # Get rule breakdown by severity
            rule_breakdown = await self._get_rule_breakdown_by_severity(customer_id)
            
            return {
                "customer_id": customer_id,
                "mitre_rules_loaded": existing_rules,
                "expected_rules": expected_count,
                "coverage_percentage": coverage_percentage,
                "is_complete": existing_rules >= expected_count,
                "rule_breakdown": rule_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error verifying MITRE coverage for tenant {customer_id}: {e}")
            return {
                "customer_id": customer_id,
                "error": str(e),
                "is_complete": False
            }
    
    def _create_sigma_rule_from_metadata(
        self, 
        rule_id: str, 
        customer_id: str, 
        technique_id: str, 
        metadata: MitreTechniqueMetadata
    ) -> Dict[str, Any]:
        """Create sigma rule dictionary from MITRE metadata"""
        
        # Generate Sigma detection logic
        detection_logic = self._generate_sigma_detection_logic(metadata)
        
        # Create comprehensive rule
        sigma_rule = {
            "id": rule_id,
            "customer_id": customer_id,
            "title": f"MITRE {technique_id}: {metadata.name}",
            "description": metadata.description,
            "detection": detection_logic,
            "attack_techniques": [technique_id],
            "severity": metadata.severity,
            "enabled": True,
            "tags": self._generate_rule_tags(metadata),
            "logsource": self._generate_logsource(metadata.platforms),
            "kill_chain_phases": metadata.kill_chain_phases,
            "data_sources": metadata.data_sources,
            "log_fields": metadata.log_fields,
            "detection_patterns": metadata.detection_patterns,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        return sigma_rule
    
    def _generate_sigma_detection_logic(self, metadata: MitreTechniqueMetadata) -> Dict[str, Any]:
        """Generate Sigma detection logic from metadata"""
        
        # Create basic selection criteria based on metadata
        selection = {}
        
        # Add field-based selection criteria
        if "process_name" in metadata.log_fields:
            selection["process_name"] = metadata.detection_patterns[0] if metadata.detection_patterns else "*"
        
        if "command_line" in metadata.log_fields:
            selection["command_line|contains"] = self._extract_command_patterns(metadata.detection_patterns)
        
        if "event_id" in metadata.log_fields and "Windows" in metadata.platforms:
            # Common Windows event IDs for process creation
            selection["event_id"] = [4688, 1]  # Security log and Sysmon
        
        # Create detection structure
        detection = {
            "selection": selection,
            "condition": "selection"
        }
        
        return detection
    
    def _extract_command_patterns(self, detection_patterns: List[str]) -> List[str]:
        """Extract command line patterns from detection patterns"""
        patterns = []
        
        for pattern in detection_patterns:
            if "powershell" in pattern.lower():
                patterns.extend(["powershell.exe", "pwsh.exe", "-enc", "-command"])
            elif "wmi" in pattern.lower():
                patterns.extend(["wmic", "Get-WmiObject", "Invoke-WmiMethod"])
            elif "registry" in pattern.lower():
                patterns.extend(["reg.exe", "regedit", "Set-ItemProperty"])
            elif "scheduled" in pattern.lower():
                patterns.extend(["schtasks", "at.exe", "New-ScheduledTask"])
            else:
                # Generic suspicious patterns
                patterns.extend(["cmd.exe", "suspicious"])
        
        return patterns[:5]  # Limit to 5 patterns
    
    def _generate_rule_tags(self, metadata: MitreTechniqueMetadata) -> List[str]:
        """Generate tags for the sigma rule"""
        tags = ["mitre_attack"]
        tags.extend(metadata.tactics)
        tags.extend(metadata.platforms)
        tags.append(f"severity_{metadata.severity}")
        return tags
    
    def _generate_logsource(self, platforms: List[str]) -> Dict[str, Any]:
        """Generate logsource configuration"""
        if "Windows" in platforms:
            return {
                "product": "windows",
                "service": "security"
            }
        elif "Linux" in platforms:
            return {
                "product": "linux",
                "service": "syslog"
            }
        elif "Cloud" in platforms:
            return {
                "product": "aws",
                "service": "cloudtrail"
            }
        else:
            return {
                "product": "generic",
                "service": "system"
            }
    
    async def _get_tenant_rule(self, customer_id: str, rule_id: str) -> Optional[Dict[str, Any]]:
        """Check if rule already exists for tenant"""
        try:
            result = await self.database.execute(
                f"""
                SELECT id, customer_id, title, enabled, created_at
                FROM sigma_rules_mt 
                WHERE customer_id = '{customer_id}' AND id = '{rule_id}'
                LIMIT 1
                """
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error checking existing rule {rule_id} for tenant {customer_id}: {e}")
            return None
    
    async def _insert_sigma_rule(self, sigma_rule: Dict[str, Any]) -> bool:
        """Insert sigma rule into database"""
        try:
            # Convert complex fields to JSON strings
            detection_json = json.dumps(sigma_rule["detection"])
            tags_json = json.dumps(sigma_rule["tags"])
            attack_techniques_json = json.dumps(sigma_rule["attack_techniques"])
            logsource_json = json.dumps(sigma_rule["logsource"])
            kill_chain_phases_json = json.dumps(sigma_rule["kill_chain_phases"])
            data_sources_json = json.dumps(sigma_rule["data_sources"])
            log_fields_json = json.dumps(sigma_rule["log_fields"])
            detection_patterns_json = json.dumps(sigma_rule["detection_patterns"])
            
            await self.database.execute(
                f"""
                INSERT INTO sigma_rules_mt (
                    id, customer_id, title, description, detection, attack_techniques,
                    severity, enabled, tags, logsource, kill_chain_phases, 
                    data_sources, log_fields, detection_patterns, created_at, updated_at
                ) VALUES (
                    '{sigma_rule["id"]}',
                    '{sigma_rule["customer_id"]}',
                    '{sigma_rule["title"].replace("'", "''")}',
                    '{sigma_rule["description"].replace("'", "''")}',
                    '{detection_json}',
                    '{attack_techniques_json}',
                    '{sigma_rule["severity"]}',
                    {sigma_rule["enabled"]},
                    '{tags_json}',
                    '{logsource_json}',
                    '{kill_chain_phases_json}',
                    '{data_sources_json}',
                    '{log_fields_json}',
                    '{detection_patterns_json}',
                    now(),
                    now()
                )
                """
            )
            return True
        except Exception as e:
            logger.error(f"Error inserting sigma rule {sigma_rule['id']}: {e}")
            return False
    
    async def _update_rule_if_needed(self, existing_rule: Dict[str, Any], metadata: MitreTechniqueMetadata) -> bool:
        """Update existing rule if metadata has changed"""
        # For now, we'll skip updates to avoid complexity
        # In production, you might want to compare metadata versions
        return False
    
    async def _get_all_active_tenants(self) -> List[Dict[str, Any]]:
        """Get all active tenants from database"""
        try:
            # This assumes you have a tenants table or can get tenants from subscriptions
            result = await self.database.execute(
                """
                SELECT DISTINCT customer_id as id, customer_id
                FROM tenant_subscriptions_mt 
                WHERE status = 'active'
                ORDER BY customer_id
                """
            )
            return result
        except Exception as e:
            logger.warning(f"Could not get tenants from subscriptions, trying alternative: {e}")
            # Fallback: get tenants from sigma_rules table
            try:
                result = await self.database.execute(
                    """
                    SELECT DISTINCT customer_id as id, customer_id
                    FROM sigma_rules_mt 
                    ORDER BY customer_id
                    LIMIT 100
                    """
                )
                return result
            except Exception as e2:
                logger.error(f"Could not get tenants from any source: {e2}")
                return []
    
    async def _count_tenant_mitre_rules(self, customer_id: str) -> int:
        """Count MITRE rules for a tenant"""
        try:
            result = await self.database.execute(
                f"""
                SELECT count(*) as rule_count
                FROM sigma_rules_mt 
                WHERE customer_id = '{customer_id}' 
                AND id LIKE 'mitre_%'
                """
            )
            return result[0]["rule_count"] if result else 0
        except Exception as e:
            logger.error(f"Error counting MITRE rules for tenant {customer_id}: {e}")
            return 0
    
    async def _get_rule_breakdown_by_severity(self, customer_id: str) -> Dict[str, int]:
        """Get rule count breakdown by severity"""
        try:
            result = await self.database.execute(
                f"""
                SELECT severity, count(*) as rule_count
                FROM sigma_rules_mt 
                WHERE customer_id = '{customer_id}' 
                AND id LIKE 'mitre_%'
                GROUP BY severity
                ORDER BY severity
                """
            )
            return {row["severity"]: row["rule_count"] for row in result}
        except Exception as e:
            logger.error(f"Error getting rule breakdown for tenant {customer_id}: {e}")
            return {}


# Singleton instance for production use
mitre_rule_loader = MitreRuleLoader()


async def initialize_mitre_rules_system() -> Dict[str, Any]:
    """
    Initialize MITRE rules for all tenants (main entry point)
    
    Returns:
        Dict with initialization results
    """
    try:
        logger.info("🚀 Starting MITRE Rule System Initialization...")
        
        # Load rules for all tenants
        results = await mitre_rule_loader.initialize_mitre_rules_for_all_tenants()
        
        # Calculate summary statistics
        total_tenants = len(results)
        total_rules_loaded = sum(results.values())
        
        summary = {
            "status": "success",
            "total_tenants": total_tenants,
            "total_rules_loaded": total_rules_loaded,
            "average_rules_per_tenant": total_rules_loaded / total_tenants if total_tenants > 0 else 0,
            "tenant_results": results
        }
        
        logger.info("🎉 MITRE Rule System Initialization Complete!")
        logger.info(f"📊 {total_rules_loaded} rules loaded across {total_tenants} tenants")
        
        return summary
        
    except Exception as e:
        logger.error(f"❌ MITRE Rule System Initialization Failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "total_tenants": 0,
            "total_rules_loaded": 0
        }


async def verify_mitre_coverage_for_tenant(customer_id: str) -> Dict[str, Any]:
    """
    Verify MITRE rule coverage for a specific tenant
    
    Args:
        customer_id: Tenant ID
        
    Returns:
        Dict with coverage verification results
    """
    return await mitre_rule_loader.verify_mitre_coverage(customer_id)


if __name__ == "__main__":
    # Test initialization
    async def test_initialization():
        print("🧪 Testing MITRE Rule Loader...")
        
        # Test with a sample tenant
        test_customer_id = "test_tenant_001"
        
        # Load rules for test tenant
        loaded_count = await mitre_rule_loader.initialize_mitre_rules_for_tenant(test_customer_id)
        print(f"✅ Loaded {loaded_count} rules for test tenant")
        
        # Verify coverage
        coverage = await mitre_rule_loader.verify_mitre_coverage(test_customer_id)
        print(f"📊 Coverage: {coverage}")
        
        print("🎉 Test complete!")
    
    # Run test
    asyncio.run(test_initialization())