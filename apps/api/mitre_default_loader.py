"""
MITRE Default Rules Loader
Loads all 286 MITRE ATT&CK techniques as default sigma rules into database and Redis cache
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
import structlog

from mitre_metadata_generator import generate_production_metadata
from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)


class MitreDefaultLoader:
    """Loads MITRE ATT&CK techniques as default sigma rules"""
    
    def __init__(self):
        import os
        service_key = os.getenv('MITRE_DEFAULT_LOADER_KEY', 'mitre-default-loader-service-key')
        self.database = DatabaseLayer("MitreDefaultLoader", service_key)
    
    async def load_default_mitre_rules(self) -> Dict[str, Any]:
        """
        Load all 286 MITRE ATT&CK techniques as default sigma rules
        
        Returns:
            Dict with loading results
        """
        try:
            logger.info("🚀 Loading default MITRE rules into database...")
            
            # Generate metadata for all 286 techniques
            metadata = generate_production_metadata()
            logger.info(f"📊 Generated metadata for {len(metadata)} MITRE techniques")
            
            # Skip clearing - use idempotent insertion instead
            logger.info("🔄 Using idempotent rule insertion (no deletion needed)")
            
            # Load each technique as a default sigma rule
            loaded_count = 0
            failed_count = 0
            
            for technique_id, meta in metadata.items():
                try:
                    rule_id = f"mitre_default_{technique_id.lower()}"
                    
                    # Create sigma rule from metadata
                    sigma_rule = self._create_default_sigma_rule(rule_id, technique_id, meta)
                    
                    # Insert into database
                    success = await self._insert_default_sigma_rule(sigma_rule)
                    
                    if success:
                        loaded_count += 1
                        if loaded_count % 50 == 0:
                            logger.info(f"📈 Loaded {loaded_count}/{len(metadata)} default rules...")
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to load rule for {technique_id}: {e}")
                    failed_count += 1
                    continue
            
            # Refresh Redis cache
            logger.info("💾 Refreshing Redis cache with default rules...")
            cache_success = await self._refresh_default_cache()
            
            result = {
                "status": "success",
                "total_techniques": len(metadata),
                "rules_loaded": loaded_count,
                "rules_failed": failed_count,
                "cache_refreshed": cache_success,
                "success_rate": (loaded_count / len(metadata)) * 100 if metadata else 0
            }
            
            logger.info(f"✅ Default MITRE rules loading complete: {loaded_count}/{len(metadata)} rules loaded ({result['success_rate']:.1f}% success)")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to load default MITRE rules: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "rules_loaded": 0,
                "rules_failed": 0
            }
    
    def _create_default_sigma_rule(self, rule_id: str, technique_id: str, metadata) -> Dict[str, Any]:
        """Create a default sigma rule from MITRE metadata"""
        
        # Generate detection logic
        detection_logic = self._generate_detection_logic(metadata)
        
        # Create rule dictionary matching sigma_rules_mt schema
        rule_content = {
            "detection": detection_logic,
            "tags": self._generate_tags(metadata),
            "logsource": self._generate_logsource(metadata.platforms),
            "kill_chain_phases": metadata.kill_chain_phases,
            "data_sources": metadata.data_sources,
            "log_fields": metadata.log_fields,
            "detection_patterns": metadata.detection_patterns
        }
        
        rule = {
            "id": rule_id,
            "customer_id": None,  # NULL for default rules
            "name": f"MITRE {technique_id}: {metadata.name}",
            "description": metadata.description,
            "rule_content": json.dumps(rule_content),
            "mitre_techniques": [technique_id],
            "severity": metadata.severity,
            "is_enabled": True,
            "false_positive_rate": 0.1,  # Default value
            "created_by": "system",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        return rule
    
    def _generate_detection_logic(self, metadata) -> Dict[str, Any]:
        """Generate basic sigma detection logic from metadata"""
        
        selection = {}
        
        # Generate selection based on log fields and detection patterns
        if "process_name" in metadata.log_fields:
            # Look for suspicious process names from detection patterns
            process_patterns = []
            for pattern in metadata.detection_patterns:
                if "powershell" in pattern.lower():
                    process_patterns.extend(["powershell.exe", "pwsh.exe"])
                elif "wmi" in pattern.lower():
                    process_patterns.extend(["wmic.exe", "wmiprvse.exe"])
                elif "cmd" in pattern.lower():
                    process_patterns.append("cmd.exe")
            
            if process_patterns:
                selection["process_name"] = process_patterns[:3]  # Limit to 3
        
        if "command_line" in metadata.log_fields:
            # Add command line patterns
            cmd_patterns = []
            for pattern in metadata.detection_patterns:
                if "powershell" in pattern.lower():
                    cmd_patterns.extend(["-enc", "-command", "DownloadString", "IEX"])
                elif "wmi" in pattern.lower():
                    cmd_patterns.extend(["Get-WmiObject", "Invoke-WmiMethod"])
                elif "registry" in pattern.lower():
                    cmd_patterns.extend(["reg add", "Set-ItemProperty"])
            
            if cmd_patterns:
                selection["command_line|contains"] = cmd_patterns[:3]
        
        if "event_id" in metadata.log_fields and "Windows" in metadata.platforms:
            # Common Windows event IDs for security monitoring
            selection["event_id"] = [4688, 4624, 4625, 1]  # Process creation, logon events, Sysmon
        
        # If no specific patterns, create a generic selection
        if not selection:
            if "process_name" in metadata.log_fields:
                selection["process_name|contains"] = "suspicious"
            elif "message" in metadata.log_fields:
                selection["message|contains"] = metadata.name.lower().split()[0]  # First word of technique name
            else:
                selection["msg|contains"] = "security"
        
        return {
            "selection": selection,
            "condition": "selection"
        }
    
    def _generate_tags(self, metadata) -> List[str]:
        """Generate tags for the sigma rule"""
        tags = ["mitre_attack", "default_rule"]
        tags.extend(metadata.tactics)
        tags.extend(metadata.platforms)
        tags.append(f"severity_{metadata.severity}")
        return tags
    
    def _generate_logsource(self, platforms: List[str]) -> Dict[str, Any]:
        """Generate logsource configuration"""
        if "Windows" in platforms:
            return {"product": "windows", "service": "security"}
        elif "Linux" in platforms:
            return {"product": "linux", "service": "syslog"}
        elif "Cloud" in platforms:
            return {"product": "aws", "service": "cloudtrail"}
        else:
            return {"product": "generic", "service": "system"}
    
    async def _clear_existing_default_rules(self) -> bool:
        """Clear existing default MITRE rules for idempotent loading"""
        try:
            # Delete existing default rules
            await self.database.execute_update(
                """
                DELETE FROM sigma_rules_mt 
                WHERE customer_id IS NULL 
                AND id LIKE 'mitre_default_%'
                """
            )
            logger.info("🧹 Cleared existing default MITRE rules")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing existing default rules: {e}")
            return False
    
    async def _insert_default_sigma_rule(self, rule: Dict[str, Any]) -> bool:
        """Insert a default sigma rule into database using new schema (idempotent)"""
        try:
            # Check if rule already exists to avoid duplicates
            existing = await self.database.execute_query(
                f"SELECT id FROM sigma_rules_mt WHERE id = '{rule['id']}' AND customer_id IS NULL"
            )
            
            if existing:
                logger.debug(f"Rule {rule['id']} already exists - skipping insertion")
                return True  # Not an error, just already exists
            # Convert mitre_techniques to proper ClickHouse array format
            # For array of strings, use format: ['value1', 'value2']
            techniques = rule["mitre_techniques"]
            if isinstance(techniques, list):
                mitre_techniques_str = "[" + ", ".join([f"'{t}'" for t in techniques]) + "]"
            else:
                mitre_techniques_str = "[]"
            
            # Escape quotes in strings
            name_escaped = rule["name"].replace("'", "''")
            description_escaped = rule["description"].replace("'", "''")
            rule_content_escaped = rule["rule_content"].replace("'", "''")
            
            await self.database.execute_update(
                f"""
                INSERT INTO sigma_rules_mt (
                    id, customer_id, name, description, rule_content, mitre_techniques,
                    severity, is_enabled, false_positive_rate, created_by, created_at, updated_at
                ) VALUES (
                    '{rule["id"]}',
                    NULL,
                    '{name_escaped}',
                    '{description_escaped}',
                    '{rule_content_escaped}',
                    {mitre_techniques_str},
                    '{rule["severity"]}',
                    {1 if rule["is_enabled"] else 0},
                    {rule["false_positive_rate"]},
                    '{rule["created_by"]}',
                    now(),
                    now()
                )
                """
            )
            return True
            
        except Exception as e:
            logger.error(f"Error inserting default rule {rule['id']}: {e}")
            return False
    
    async def _refresh_default_cache(self) -> bool:
        """Refresh Redis cache with default rules"""
        try:
            from dependencies import get_sigma_rule_cache
            
            sigma_cache = get_sigma_rule_cache()
            if not sigma_cache:
                logger.warning("Sigma rule cache not available")
                return False
            
            # Force refresh of default rules cache
            await sigma_cache.invalidate_default_cache()
            
            # Get default rules from database and cache them
            default_rules = await self._get_default_rules_from_db()
            if default_rules:
                await sigma_cache._cache_default_rules(default_rules)
                logger.info(f"✅ Cached {len(default_rules)} default rules in Redis")
                return True
            else:
                logger.warning("No default rules found to cache")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing default cache: {e}")
            return False
    
    async def _get_default_rules_from_db(self) -> List[Dict[str, Any]]:
        """Get default rules from database"""
        try:
            result = await self.database.execute_query(
                """
                SELECT id, customer_id, name, description, rule_content, mitre_techniques,
                       severity, is_enabled, false_positive_rate, created_by, created_at, updated_at
                FROM sigma_rules_mt 
                WHERE customer_id IS NULL 
                AND is_enabled = 1
                ORDER BY id
                """
            )
            
            # Convert result to list of dictionaries
            rules = []
            for row in result:
                rule_dict = dict(row)
                
                # Parse JSON fields for new schema
                try:
                    # Parse the rule_content JSON which contains the sigma rule definition
                    if rule_dict["rule_content"]:
                        content = json.loads(rule_dict["rule_content"])
                        rule_dict["detection"] = content.get("detection", {})
                        rule_dict["tags"] = content.get("tags", [])
                        rule_dict["logsource"] = content.get("logsource", {})
                        rule_dict["kill_chain_phases"] = content.get("kill_chain_phases", [])
                        rule_dict["data_sources"] = content.get("data_sources", [])
                        rule_dict["log_fields"] = content.get("log_fields", [])
                        rule_dict["detection_patterns"] = content.get("detection_patterns", [])
                    
                    # Map new schema fields to expected format
                    rule_dict["title"] = rule_dict["name"]  # For backward compatibility
                    rule_dict["attack_techniques"] = rule_dict["mitre_techniques"]
                    rule_dict["enabled"] = bool(rule_dict["is_enabled"])
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON fields for rule {rule_dict['id']}: {e}")
                    continue
                
                rules.append(rule_dict)
            
            return rules
            
        except Exception as e:
            logger.error(f"Error getting default rules from database: {e}")
            return []
    
    async def verify_default_rules(self) -> Dict[str, Any]:
        """Verify that default rules are properly loaded"""
        try:
            # Check database
            db_count = await self.database.execute_query(
                "SELECT count(*) as count FROM sigma_rules_mt WHERE customer_id IS NULL"
            )
            db_rules_count = db_count[0]["count"] if db_count else 0
            
            # Check Redis cache
            cache_count = 0
            try:
                from dependencies import get_sigma_rule_cache
                sigma_cache = get_sigma_rule_cache()
                if sigma_cache:
                    default_rules = await sigma_cache.get_default_rules()
                    cache_count = len(default_rules)
            except Exception as e:
                logger.error(f"Error checking cache: {e}")
            
            return {
                "database_rules": db_rules_count,
                "cached_rules": cache_count,
                "expected_rules": 286,
                "database_complete": db_rules_count >= 286,
                "cache_complete": cache_count >= 286,
                "system_ready": db_rules_count >= 286 and cache_count >= 286
            }
            
        except Exception as e:
            logger.error(f"Error verifying default rules: {e}")
            return {
                "error": str(e),
                "system_ready": False
            }


# Singleton instance
mitre_default_loader = MitreDefaultLoader()


async def load_mitre_default_rules() -> Dict[str, Any]:
    """
    Main entry point to load default MITRE rules
    
    Returns:
        Dict with loading results
    """
    return await mitre_default_loader.load_default_mitre_rules()


async def verify_mitre_default_rules() -> Dict[str, Any]:
    """
    Verify that default MITRE rules are loaded
    
    Returns:
        Dict with verification results
    """
    return await mitre_default_loader.verify_default_rules()


if __name__ == "__main__":
    # Test loading default rules
    async def test_default_loading():
        print("🧪 Testing MITRE Default Rules Loader...")
        
        # Load default rules
        result = await load_mitre_default_rules()
        print(f"✅ Loading result: {result}")
        
        # Verify rules
        verification = await verify_mitre_default_rules()
        print(f"📊 Verification: {verification}")
        
        print("🎉 Test complete!")
    
    # Run test
    asyncio.run(test_default_loading())