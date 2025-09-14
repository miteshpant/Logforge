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
            
            query = """
            INSERT INTO sigma_rules_mt (
                id, customer_id, title, description, severity, status, author, date,
                tags, attack_techniques, kill_chain_phases, logsource, detection,
                references, falsepositives, enabled, created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(title)s, %(description)s, %(severity)s, %(status)s,
                %(author)s, %(date)s, %(tags)s, %(attack_techniques)s, %(kill_chain_phases)s,
                %(logsource)s, %(detection)s, %(references)s, %(falsepositives)s,
                %(enabled)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": rule_id,
                "customer_id": rule_data.get("customer_id", "default"),
                "title": rule_data.get("title", ""),
                "description": rule_data.get("description", ""),
                "severity": rule_data.get("severity", "medium"),
                "status": rule_data.get("status", "active"),
                "author": rule_data.get("author", "logforge"),
                "date": rule_data.get("date", datetime.now(timezone.utc).strftime("%Y/%m/%d")),
                "tags": json.dumps(rule_data.get("tags", [])),
                "attack_techniques": json.dumps([t.value if hasattr(t, 'value') else str(t) for t in rule_data.get("attack_techniques", [])]),
                "kill_chain_phases": json.dumps(rule_data.get("kill_chain_phases", [])),
                "logsource": json.dumps(rule_data.get("logsource", {})),
                "detection": json.dumps(rule_data.get("detection", {})),
                "references": json.dumps(rule_data.get("references", [])),
                "falsepositives": json.dumps(rule_data.get("falsepositives", [])),
                "enabled": rule_data.get("enabled", True),
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
            
            # Process results to parse JSON fields
            processed_rules = []
            for rule in results:
                processed_rule = dict(rule)
                
                # Parse JSON fields
                for json_field in ["tags", "attack_techniques", "kill_chain_phases", "logsource", "detection", "references", "falsepositives"]:
                    if processed_rule.get(json_field):
                        try:
                            processed_rule[json_field] = json.loads(processed_rule[json_field])
                        except (json.JSONDecodeError, TypeError):
                            processed_rule[json_field] = []
                
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
                processed_rule = dict(result)
                
                # Parse JSON fields
                for json_field in ["tags", "attack_techniques", "kill_chain_phases", "logsource", "detection", "references", "falsepositives"]:
                    if processed_rule.get(json_field):
                        try:
                            processed_rule[json_field] = json.loads(processed_rule[json_field])
                        except (json.JSONDecodeError, TypeError):
                            processed_rule[json_field] = []
                
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
            ORDER BY timestamp DESC
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
            # Build dynamic update query
            set_clauses = []
            params = {"event_id": event_id, "customer_id": customer_id, "updated_at": datetime.now(timezone.utc)}
            
            for field, value in updates.items():
                if field in ["status", "assigned_to", "kill_chain_phase"]:
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
                elif field == "investigation_notes":
                    set_clauses.append("investigation_notes = %(investigation_notes)s")
                    params["investigation_notes"] = json.dumps(value)
            
            if not set_clauses:
                return False
            
            query = f"""
            UPDATE security_events_mt 
            SET {', '.join(set_clauses)}, updated_at = %(updated_at)s
            WHERE id = %(event_id)s AND customer_id = %(customer_id)s
            """
            
            await self.db.execute_query(query, params)
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
                id, customer_id, indicator_type, value, threat_type, severity,
                confidence, source, description, tags, first_seen, last_seen,
                created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(indicator_type)s, %(value)s, %(threat_type)s,
                %(severity)s, %(confidence)s, %(source)s, %(description)s, %(tags)s,
                %(first_seen)s, %(last_seen)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": indicator_id,
                "customer_id": indicator_data.get("customer_id", "default"),
                "indicator_type": indicator_data.get("indicator_type", "unknown"),
                "value": indicator_data.get("value", ""),
                "threat_type": json.dumps(indicator_data.get("threat_type", [])),
                "severity": indicator_data.get("severity", "medium"),
                "confidence": indicator_data.get("confidence", 50),
                "source": indicator_data.get("source", "unknown"),
                "description": indicator_data.get("description"),
                "tags": json.dumps(indicator_data.get("tags", [])),
                "first_seen": indicator_data.get("first_seen", datetime.now(timezone.utc)),
                "last_seen": indicator_data.get("last_seen", datetime.now(timezone.utc)),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
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