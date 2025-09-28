"""
Security Analytics DAO - Database Operations for Security Analytics, SIEM, and Threat Intelligence
Handles Sigma rules, security events, threat intelligence indicators, and MITRE ATT&CK data
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
import uuid

from database_layer import DatabaseLayer

logger = structlog.get_logger(__name__)

class SecurityDAO:
    """Data Access Object for Security Analytics and SIEM"""
    
    def __init__(self):
        self.db = DatabaseLayer("SecurityDAO", "security-dao-service-key")
    
    # Sigma Rules Operations
    
    async def save_sigma_rule(self, rule_data: Dict[str, Any]) -> str:
        """Save Sigma rule to database"""
        try:
            rule_id = rule_data.get("id", str(uuid.uuid4()))
            
            # Validate required fields
            if not rule_data.get("title"):
                raise ValueError("Rule title is required")
            
            if not rule_data.get("logsource"):
                raise ValueError("Rule logsource is required")
            
            if not rule_data.get("detection"):
                raise ValueError("Rule detection logic is required")
            
            # Validate severity level (ClickHouse enum constraint)
            severity = rule_data.get("severity", "medium")
            valid_severities = ["low", "medium", "high", "critical"]
            if severity not in valid_severities:
                logger.warning(f"Invalid severity '{severity}', defaulting to 'medium'")
                severity = "medium"
            
            # Build rule content JSON from the various rule components
            rule_content = {
                "logsource": rule_data.get("logsource", {}),
                "detection": rule_data.get("detection", {}),
                "references": rule_data.get("references", []),
                "falsepositives": rule_data.get("falsepositives", []),
                "tags": rule_data.get("tags", []),
                "kill_chain_phases": rule_data.get("kill_chain_phases", []),
                "author": rule_data.get("author", "logforge"),
                "date": rule_data.get("date", datetime.now(timezone.utc).strftime("%Y/%m/%d"))
            }
            
            # Validate detection logic format
            if not isinstance(rule_content["detection"], dict):
                raise ValueError("Detection logic must be a dictionary")
            
            query = """
            INSERT INTO sigma_rules_mt (
                id, customer_id, name, description, rule_content, mitre_techniques,
                severity, is_enabled, created_by, created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(name)s, %(description)s, %(rule_content)s,
                %(mitre_techniques)s, %(severity)s, %(is_enabled)s, %(created_by)s,
                %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": rule_id,
                "customer_id": rule_data.get("customer_id", "default"),
                "name": rule_data.get("title", ""),  # Map title to name
                "description": rule_data.get("description", ""),
                "rule_content": json.dumps(rule_content),
                "mitre_techniques": rule_data.get("attack_techniques", []),
                "severity": severity,  # Use validated severity
                "is_enabled": 1 if rule_data.get("enabled", True) else 0,
                "created_by": rule_data.get("author", "logforge"),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Sigma rule saved: {rule_id}")
            
            return rule_id
            
        except Exception as e:
            logger.error(f"Failed to save Sigma rule: {e}")
            raise
    
    async def get_sigma_rules(self, customer_id: str = None) -> List[Dict[str, Any]]:
        """Get Sigma rules from database"""
        try:
            if customer_id:
                query = """
                SELECT * FROM sigma_rules_mt 
                WHERE customer_id = %(customer_id)s OR customer_id = 'default'
                ORDER BY created_at DESC
                """
                params = {"customer_id": customer_id}
            else:
                query = "SELECT * FROM sigma_rules_mt ORDER BY created_at DESC"
                params = {}
            
            results = await self.db.fetch_all(query, params)
            
            # Process results to map to expected API format
            processed_rules = []
            for rule in results:
                # Parse rule_content JSON
                rule_content = {}
                try:
                    if rule.get("rule_content"):
                        rule_content = json.loads(rule["rule_content"])
                except (json.JSONDecodeError, TypeError):
                    rule_content = {}
                
                # Map database columns to API response format
                processed_rule = {
                    "id": rule["id"],
                    "title": rule["name"],  # Map name back to title
                    "description": rule["description"],
                    "severity": rule["severity"],
                    "status": "active" if rule["is_enabled"] else "inactive",
                    "author": rule["created_by"],
                    "date": rule_content.get("date", rule["created_at"].strftime("%Y/%m/%d") if rule.get("created_at") else ""),
                    "enabled": bool(rule["is_enabled"]),
                    "attack_techniques": rule.get("mitre_techniques", []),
                    "tags": rule_content.get("tags", []),
                    "kill_chain_phases": rule_content.get("kill_chain_phases", []),
                    "logsource": rule_content.get("logsource", {}),
                    "detection": rule_content.get("detection", {}),
                    "references": rule_content.get("references", []),
                    "falsepositives": rule_content.get("falsepositives", []),
                    "created_at": rule["created_at"],
                    "updated_at": rule["updated_at"],
                    "customer_id": rule["customer_id"]
                }
                
                processed_rules.append(processed_rule)
            
            return processed_rules
            
        except Exception as e:
            logger.error(f"Failed to get Sigma rules: {e}")
            raise
    
    async def get_sigma_rule_by_id(self, rule_id: str, customer_id: str = None) -> Optional[Dict[str, Any]]:
        """Get specific Sigma rule by ID"""
        try:
            if customer_id:
                query = """
                SELECT * FROM sigma_rules_mt 
                WHERE id = %(rule_id)s AND (customer_id = %(customer_id)s OR customer_id = 'default')
                """
                params = {"rule_id": rule_id, "customer_id": customer_id}
            else:
                query = "SELECT * FROM sigma_rules_mt WHERE id = %(rule_id)s"
                params = {"rule_id": rule_id}
            
            result = await self.db.fetch_one(query, params)
            
            if result:
                # Parse rule_content JSON
                rule_content = {}
                try:
                    if result.get("rule_content"):
                        rule_content = json.loads(result["rule_content"])
                except (json.JSONDecodeError, TypeError):
                    rule_content = {}
                
                # Map database columns to API response format
                processed_rule = {
                    "id": result["id"],
                    "title": result["name"],  # Map name back to title
                    "description": result["description"],
                    "severity": result["severity"],
                    "status": "active" if result["is_enabled"] else "inactive",
                    "author": result["created_by"],
                    "date": rule_content.get("date", result["created_at"].strftime("%Y/%m/%d") if result.get("created_at") else ""),
                    "enabled": bool(result["is_enabled"]),
                    "attack_techniques": result.get("mitre_techniques", []),
                    "tags": rule_content.get("tags", []),
                    "kill_chain_phases": rule_content.get("kill_chain_phases", []),
                    "logsource": rule_content.get("logsource", {}),
                    "detection": rule_content.get("detection", {}),
                    "references": rule_content.get("references", []),
                    "falsepositives": rule_content.get("falsepositives", []),
                    "created_at": result["created_at"],
                    "updated_at": result["updated_at"],
                    "customer_id": result["customer_id"]
                }
                
                return processed_rule
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get Sigma rule {rule_id}: {e}")
            raise
    
    # Security Events Operations
    
    async def save_security_event(self, event_data: Dict[str, Any]) -> str:
        """Save security event to database"""
        try:
            event_id = event_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO security_events_mt (
                id, customer_id, rule_id, rule_title, severity, status,
                timestamp, event_data, matched_fields, attack_techniques,
                kill_chain_phase, assigned_to, investigation_notes, artifacts,
                source_logs, created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(rule_id)s, %(rule_title)s, %(severity)s, %(status)s,
                %(timestamp)s, %(event_data)s, %(matched_fields)s, %(attack_techniques)s,
                %(kill_chain_phase)s, %(assigned_to)s, %(investigation_notes)s, %(artifacts)s,
                %(source_logs)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": event_id,
                "customer_id": event_data.get("customer_id", "default"),
                "rule_id": event_data.get("rule_id", ""),
                "rule_title": event_data.get("rule_title", ""),
                "severity": event_data.get("severity", "medium"),
                "status": event_data.get("status", "triggered"),
                "timestamp": event_data.get("timestamp", datetime.now(timezone.utc)),
                "event_data": json.dumps(event_data.get("event_data", {})),
                "matched_fields": json.dumps(event_data.get("matched_fields", {})),
                "attack_techniques": json.dumps([t.value if hasattr(t, 'value') else str(t) for t in event_data.get("attack_techniques", [])]),
                "kill_chain_phase": event_data.get("kill_chain_phase"),
                "assigned_to": event_data.get("assigned_to"),
                "investigation_notes": json.dumps(event_data.get("investigation_notes", [])),
                "artifacts": json.dumps(event_data.get("artifacts", [])),
                "source_logs": json.dumps(event_data.get("source_logs", [])),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Security event saved: {event_id}")
            
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to save security event: {e}")
            raise
    
    async def get_security_events(self, customer_id: str, limit: int = 100, severity: str = None, status: str = None) -> List[Dict[str, Any]]:
        """Get security events from database"""
        try:
            # Build query with filters
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id, "limit": limit}
            
            if severity:
                where_clauses.append("severity = %(severity)s")
                params["severity"] = severity
            
            if status:
                where_clauses.append("status = %(status)s")
                params["status"] = status
            
            query = f"""
            SELECT * FROM security_events_mt 
            WHERE {' AND '.join(where_clauses)}
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Process results to parse JSON fields
            processed_events = []
            for event in results:
                processed_event = dict(event)
                
                # Parse JSON fields
                for json_field in ["event_data", "matched_fields", "attack_techniques", "investigation_notes", "artifacts", "source_logs"]:
                    if processed_event.get(json_field):
                        try:
                            processed_event[json_field] = json.loads(processed_event[json_field])
                        except (json.JSONDecodeError, TypeError):
                            processed_event[json_field] = [] if json_field in ["investigation_notes", "artifacts", "source_logs", "attack_techniques"] else {}
                
                processed_events.append(processed_event)
            
            return processed_events
            
        except Exception as e:
            logger.error(f"Failed to get security events: {e}")
            raise
    
    async def update_security_event(self, event_id: str, customer_id: str, updates: Dict[str, Any]) -> bool:
        """Update security event"""
        try:
            # First check if the event exists
            check_query = """
            SELECT COUNT(*) as count FROM security_events_mt 
            WHERE id = %(event_id)s AND customer_id = %(customer_id)s
            """
            check_params = {"event_id": event_id, "customer_id": customer_id}
            
            result = await self.db.fetch_one(check_query, check_params)
            if not result or result.get("count", 0) == 0:
                logger.debug(f"Security event not found: {event_id}")
                return False  # Event doesn't exist
            
            # Build dynamic update query using ClickHouse ALTER TABLE syntax
            set_clauses = []
            params = {"event_id": event_id, "customer_id": customer_id, "updated_at": datetime.now(timezone.utc)}
            
            for field, value in updates.items():
                if field in ["status", "assigned_to", "kill_chain_phase"]:
                    set_clauses.append(f"{field} = '{value}'")
                elif field == "investigation_notes":
                    set_clauses.append(f"investigation_notes = '{json.dumps(value)}'")
            
            if not set_clauses:
                return False
            
            # Add updated_at to set_clauses (format for ClickHouse DateTime64)
            updated_at_str = params['updated_at'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Remove timezone and limit to 3 decimal places
            set_clauses.append(f"updated_at = '{updated_at_str}'")
            
            # Use ClickHouse ALTER TABLE UPDATE syntax
            query = f"""
            ALTER TABLE security_events_mt 
            UPDATE {', '.join(set_clauses)}
            WHERE id = '{event_id}' AND customer_id = '{customer_id}'
            """
            
            await self.db.execute_query(query, {})
            logger.debug(f"Security event updated: {event_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update security event {event_id}: {e}")
            raise
    
    # Threat Intelligence Operations
    
    async def save_threat_intel_indicator(self, indicator_data: Dict[str, Any]) -> str:
        """Save threat intelligence indicator to database"""
        try:
            indicator_id = indicator_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO threat_intel_mt (
                id, customer_id, indicator_type, indicator_value, threat_type, 
                confidence_score, source, first_seen, last_seen, tags, context, is_active
            ) VALUES (
                %(id)s, %(customer_id)s, %(indicator_type)s, %(indicator_value)s, %(threat_type)s,
                %(confidence_score)s, %(source)s, %(first_seen)s, %(last_seen)s, %(tags)s, %(context)s, %(is_active)s
            )
            """
            
             # Map the threat_type to the database enum values
            threat_type_value = indicator_data.get("threat_type", ["malware"])
            if isinstance(threat_type_value, list) and threat_type_value:
                threat_type_enum = threat_type_value[0]  # Use first value for enum
            else:
                threat_type_enum = "malware"
            
            # Ensure threat_type is valid enum
            valid_threat_types = ["malware", "c2", "phishing", "scanning", "bot"]
            if threat_type_enum not in valid_threat_types:
                threat_type_enum = "malware"
            
            # Map indicator_type to valid enum
            indicator_type_value = indicator_data.get("indicator_type", "domain")
            valid_indicator_types = ["domain", "ip", "hash", "url", "email", "filename"]
            if indicator_type_value not in valid_indicator_types:
                indicator_type_value = "domain"
            
            params = {
                "id": indicator_id,
                "customer_id": indicator_data.get("customer_id", "default"),
                "indicator_type": indicator_type_value,
                "indicator_value": indicator_data.get("value", indicator_data.get("indicator_value", "")),
                "threat_type": threat_type_enum,  # Use enum value, not JSON array
                "confidence_score": min(100, max(0, indicator_data.get("confidence", 50))),  # Ensure 0-100 range
                "source": indicator_data.get("source", "logforge-default"),
                "first_seen": indicator_data.get("first_seen", datetime.now(timezone.utc)),
                "last_seen": indicator_data.get("last_seen", datetime.now(timezone.utc)),
                "tags": indicator_data.get("tags", []),  # ClickHouse Array(String) type
                "context": json.dumps(indicator_data.get("description", "")),  # Use context for additional data
                "is_active": 1  # Default to active
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Threat intel indicator saved: {indicator_id}")
            
            return indicator_id
            
        except Exception as e:
            logger.error(f"Failed to save threat intel indicator: {e}")
            raise
    
    async def get_threat_intel_indicators(self, customer_id: str = None, indicator_type: str = None) -> List[Dict[str, Any]]:
        """Get threat intelligence indicators from database"""
        try:
            where_clauses = []
            params = {}
            
            if customer_id:
                where_clauses.append("(customer_id = %(customer_id)s OR customer_id = 'default')")
                params["customer_id"] = customer_id
            
            if indicator_type:
                where_clauses.append("indicator_type = %(indicator_type)s")
                params["indicator_type"] = indicator_type
            
            if where_clauses:
                query = f"SELECT * FROM threat_intel_mt WHERE {' AND '.join(where_clauses)} ORDER BY last_seen DESC"
            else:
                query = "SELECT * FROM threat_intel_mt ORDER BY last_seen DESC"
            
            results = await self.db.fetch_all(query, params)
            
            # Process results to parse JSON fields
            processed_indicators = []
            for indicator in results:
                processed_indicator = dict(indicator)
                
                # Parse JSON fields
                for json_field in ["threat_type", "tags"]:
                    if processed_indicator.get(json_field):
                        try:
                            processed_indicator[json_field] = json.loads(processed_indicator[json_field])
                        except (json.JSONDecodeError, TypeError):
                            processed_indicator[json_field] = []
                
                processed_indicators.append(processed_indicator)
            
            return processed_indicators
            
        except Exception as e:
            logger.error(f"Failed to get threat intel indicators: {e}")
            raise