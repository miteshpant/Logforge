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
    
    async def update_sigma_rule(self, rule_id: str, rule_data: Dict[str, Any], customer_id: str = None) -> bool:
        """Update Sigma rule in database"""
        try:
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
            
            # Build ALTER TABLE UPDATE query with tenant isolation (ClickHouse syntax)
            if customer_id:
                query = """
                ALTER TABLE sigma_rules_mt UPDATE
                    name = %(name)s,
                    description = %(description)s,
                    rule_content = %(rule_content)s,
                    mitre_techniques = %(mitre_techniques)s,
                    severity = %(severity)s,
                    is_enabled = %(is_enabled)s,
                    updated_at = %(updated_at)s
                WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
                """
                params = {
                    "rule_id": rule_id,
                    "customer_id": customer_id,
                    "name": rule_data.get("title", ""),
                    "description": rule_data.get("description", ""),
                    "rule_content": json.dumps(rule_content),
                    "mitre_techniques": rule_data.get("attack_techniques", []),
                    "severity": severity,
                    "is_enabled": 1 if rule_data.get("enabled", True) else 0,
                    "updated_at": datetime.now(timezone.utc)
                }
            else:
                query = """
                ALTER TABLE sigma_rules_mt UPDATE
                    name = %(name)s,
                    description = %(description)s,
                    rule_content = %(rule_content)s,
                    mitre_techniques = %(mitre_techniques)s,
                    severity = %(severity)s,
                    is_enabled = %(is_enabled)s,
                    updated_at = %(updated_at)s
                WHERE id = %(rule_id)s
                """
                params = {
                    "rule_id": rule_id,
                    "name": rule_data.get("title", ""),
                    "description": rule_data.get("description", ""),
                    "rule_content": json.dumps(rule_content),
                    "mitre_techniques": rule_data.get("attack_techniques", []),
                    "severity": severity,
                    "is_enabled": 1 if rule_data.get("enabled", True) else 0,
                    "updated_at": datetime.now(timezone.utc)
                }
            
            # First check if the rule exists
            if customer_id:
                check_query = """
                SELECT COUNT(*) as count FROM sigma_rules_mt 
                WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
                """
                check_params = {"rule_id": rule_id, "customer_id": customer_id}
            else:
                check_query = "SELECT COUNT(*) as count FROM sigma_rules_mt WHERE id = %(rule_id)s"
                check_params = {"rule_id": rule_id}
            
            check_result = await self.db.fetch_one(check_query, check_params)
            if not check_result or check_result.get("count", 0) == 0:
                logger.warning(f"Sigma rule not found for update: {rule_id}")
                return False
            
            # Execute the update
            await self.db.execute_query(query, params)
            logger.debug(f"Sigma rule updated: {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Sigma rule {rule_id}: {e}")
            raise
    
    async def delete_sigma_rule(self, rule_id: str, customer_id: str = None) -> bool:
        """Delete Sigma rule from database (with tenant isolation)"""
        try:
            # First check if the rule exists
            if customer_id:
                check_query = """
                SELECT COUNT(*) as count FROM sigma_rules_mt 
                WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
                """
                check_params = {"rule_id": rule_id, "customer_id": customer_id}
            else:
                check_query = "SELECT COUNT(*) as count FROM sigma_rules_mt WHERE id = %(rule_id)s"
                check_params = {"rule_id": rule_id}
            
            check_result = await self.db.fetch_one(check_query, check_params)
            if not check_result or check_result.get("count", 0) == 0:
                logger.warning(f"Sigma rule not found for deletion: {rule_id}")
                return False
            
            # Build DELETE query with tenant isolation
            if customer_id:
                query = """
                DELETE FROM sigma_rules_mt 
                WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
                """
                params = {"rule_id": rule_id, "customer_id": customer_id}
            else:
                query = "DELETE FROM sigma_rules_mt WHERE id = %(rule_id)s"
                params = {"rule_id": rule_id}
            
            # Execute the delete using execute_query (ClickHouse accepts DELETE via query)
            await self.db.execute_query(query, params)
            logger.debug(f"Sigma rule deleted: {rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete Sigma rule {rule_id}: {e}")
            raise
    
    # Security Events Operations
    
    async def save_security_event(self, event_data: Dict[str, Any]) -> str:
        """Save security event to database"""
        try:
            event_id = event_data.get("id", str(uuid.uuid4()))
            
            query = """
            INSERT INTO security_events_mt (
                id, customer_id, rule_id, title, severity, status,
                event_type, description, raw_log_data, enrichment_data,
                mitre_techniques, assigned_to, investigation_notes, artifacts,
                created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(rule_id)s, %(title)s, %(severity)s, %(status)s,
                %(event_type)s, %(description)s, %(raw_log_data)s, %(enrichment_data)s,
                %(mitre_techniques)s, %(assigned_to)s, %(investigation_notes)s, %(artifacts)s,
                %(created_at)s, %(updated_at)s
            )
            """
            
            # Map status to ClickHouse enum
            status_value = event_data.get("status", "triggered")
            if status_value == "triggered":
                status_enum = "new"  # Map triggered to new
            else:
                status_enum = status_value
            
            params = {
                "id": event_id,
                "customer_id": event_data.get("customer_id", "default"),
                "rule_id": event_data.get("rule_id", ""),
                "title": event_data.get("rule_title", ""),
                "severity": event_data.get("severity", "medium"),
                "status": status_enum,  # Use enum-compatible value
                "event_type": "detection",  # All security events are detections
                "description": event_data.get("rule_title", "Security detection"),
                "raw_log_data": event_data.get("raw_log_data") or json.dumps(event_data.get("event_data", {})),
                "enrichment_data": event_data.get("enrichment_data") or json.dumps(event_data.get("matched_fields", {})),
                "mitre_techniques": [str(t) for t in event_data.get("attack_techniques", [])],
                "assigned_to": event_data.get("assigned_to"),
                "investigation_notes": [str(note) for note in event_data.get("investigation_notes", [])],
                "artifacts": [str(artifact) for artifact in event_data.get("artifacts", [])],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.debug(f"Security event saved: {event_id}")
            
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to save security event: {e}")
            raise
    
    async def get_security_events(
        self,
        customer_id: str,
        limit: int = 100,
        severity: str = None,
        status: str = None,
        start_time: str = None,
        end_time: str = None
    ) -> List[Dict[str, Any]]:
        """Get security events from database with optional time filtering"""
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

            # Add time filtering
            if start_time:
                where_clauses.append("created_at >= %(start_time)s")
                params["start_time"] = start_time

            if end_time:
                where_clauses.append("created_at <= %(end_time)s")
                params["end_time"] = end_time

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
    
    # Security Event Status Management Operations
    
    async def update_security_event_status(
        self,
        detection_id: str,
        customer_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        investigation_note: Optional[str] = None
    ) -> bool:
        """Update security event status using existing table fields"""
        try:
            # Build update query dynamically
            update_fields = ["status = %(status)s", "updated_at = now64(3)"]
            params = {"status": status, "detection_id": detection_id, "customer_id": customer_id}
            
            if assigned_to is not None:
                update_fields.append("assigned_to = %(assigned_to)s")
                params["assigned_to"] = assigned_to
            
            # Add investigation note to existing array
            if investigation_note:
                update_fields.append("investigation_notes = arrayConcat(investigation_notes, [%(investigation_note)s])")
                params["investigation_note"] = f"{datetime.now(timezone.utc).isoformat()}: {investigation_note}"
            
            query = f"""
            ALTER TABLE security_events_mt 
            UPDATE {', '.join(update_fields)}
            WHERE id = %(detection_id)s AND customer_id = %(customer_id)s
            """
            
            await self.db.execute_query(query, params)
            logger.debug(f"Security event status updated: {detection_id} -> {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update security event status: {e}")
            return False
    
    async def bulk_update_events_by_rule(
        self,
        rule_id: str,
        customer_id: str,
        status: str,
        assigned_to: Optional[str] = None,
        investigation_note: Optional[str] = None
    ) -> int:
        """Bulk update all events for a specific rule"""
        try:
            # First, count how many events will be updated (all events for the rule)
            count_query_before = """
            SELECT count() as count_to_update 
            FROM security_events_mt 
            WHERE rule_id = %(rule_id)s AND customer_id = %(customer_id)s
            """
            count_params_before = {
                "rule_id": rule_id,
                "customer_id": customer_id
            }
            
            count_results_before = await self.db.fetch_all(count_query_before, count_params_before)
            events_to_update = count_results_before[0]['count_to_update'] if count_results_before else 0
            
            if events_to_update == 0:
                logger.debug(f"No events found for rule {rule_id}")
                return 0
            
            # Now perform the update
            update_fields = ["status = %(status)s", "updated_at = now64(3)"]
            params = {
                "status": status,
                "rule_id": rule_id,
                "customer_id": customer_id
            }
            
            if assigned_to is not None:
                update_fields.append("assigned_to = %(assigned_to)s")
                params["assigned_to"] = assigned_to
            
            if investigation_note:
                update_fields.append("investigation_notes = arrayConcat(investigation_notes, [%(investigation_note)s])")
                params["investigation_note"] = f"{datetime.now(timezone.utc).isoformat()}: {investigation_note}"
            
            query = f"""
            ALTER TABLE security_events_mt 
            UPDATE {', '.join(update_fields)}
            WHERE rule_id = %(rule_id)s AND customer_id = %(customer_id)s
            """
            
            await self.db.execute_query(query, params)
            
            logger.debug(f"Bulk updated {events_to_update} events for rule {rule_id} to status {status}")
            return events_to_update
            
        except Exception as e:
            logger.error(f"Failed to bulk update events by rule: {e}")
            return 0
    
    async def get_security_event_by_id(
        self,
        detection_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get security event by ID for specific customer"""
        try:
            query = """
            SELECT * FROM security_events_mt 
            WHERE id = %(detection_id)s AND customer_id = %(customer_id)s
            LIMIT 1
            """
            
            result = await self.db.fetch_one(query, {
                "detection_id": detection_id,
                "customer_id": customer_id
            })
            
            if not result:
                return None
            
            # Parse JSON fields
            for json_field in ["raw_log_data", "enrichment_data"]:
                if result.get(json_field):
                    try:
                        result[json_field] = json.loads(result[json_field])
                    except (json.JSONDecodeError, TypeError):
                        result[json_field] = {}
            
            return dict(result)
            
        except Exception as e:
            logger.error(f"Failed to get security event: {e}")
            return None
    
    async def get_events_by_rule_id(
        self,
        rule_id: str,
        customer_id: str,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get events for a specific rule"""
        try:
            query = """
            SELECT * FROM security_events_mt 
            WHERE rule_id = %(rule_id)s AND customer_id = %(customer_id)s
            """
            params = {
                "rule_id": rule_id,
                "customer_id": customer_id,
                "limit": limit
            }
            
            if status_filter:
                query += " AND status = %(status_filter)s"
                params["status_filter"] = status_filter
            
            query += " ORDER BY created_at DESC LIMIT %(limit)s"
            
            results = await self.db.fetch_all(query, params)
            events = []
            
            for result in results:
                event_dict = dict(result)
                # Parse JSON fields
                for json_field in ["raw_log_data", "enrichment_data"]:
                    if event_dict.get(json_field):
                        try:
                            event_dict[json_field] = json.loads(event_dict[json_field])
                        except (json.JSONDecodeError, TypeError):
                            event_dict[json_field] = {}
                events.append(event_dict)
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events by rule: {e}")
            return []
    
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
            
            # Process results to parse JSON fields and format dates
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
                
                # Convert datetime fields to ISO strings
                for date_field in ["first_seen", "last_seen"]:
                    if processed_indicator.get(date_field):
                        date_value = processed_indicator[date_field]
                        if hasattr(date_value, 'isoformat'):
                            processed_indicator[date_field] = date_value.isoformat()
                
                # Ensure required fields for API response
                processed_indicator.setdefault("value", processed_indicator.get("indicator_value", ""))
                processed_indicator.setdefault("severity", "medium")
                
                processed_indicators.append(processed_indicator)
            
            return processed_indicators
            
        except Exception as e:
            logger.error(f"Failed to get threat intel indicators: {e}")
            raise
    
    # =================================================================
    # MIGRATION HELPER METHODS
    # =================================================================
    
    async def should_load_mitre_rules(self) -> bool:
        """Check if MITRE rules should be loaded based on migration status"""
        try:
            # Check if migration marker exists
            marker_query = """
                SELECT count() as count FROM system_migrations 
                WHERE migration_name = '003_seed_mitre_rules_marker'
            """
            
            marker_result = await self.db.execute_query(marker_query)
            
            if not marker_result or marker_result[0]["count"] == 0:
                # Migration marker doesn't exist - don't load
                logger.debug("MITRE migration marker not found")
                return False
            
            # Check if MITRE rules are already loaded
            rules_query = """
                SELECT count() as count FROM sigma_rules_mt 
                WHERE customer_id IS NULL AND id LIKE 'mitre_default_%'
            """
            
            rules_result = await self.db.execute_query(rules_query)
            existing_rules = rules_result[0]["count"] if rules_result else 0
            
            # Load rules if marker exists but rules are not loaded (or incomplete)
            should_load = existing_rules < 286
            
            logger.info(f"Migration check: marker exists, {existing_rules}/286 rules loaded, should_load={should_load}")
            return should_load
            
        except Exception as e:
            logger.error(f"Error checking MITRE migration status: {e}")
            return False
    
    async def mark_mitre_migration_completed(self) -> bool:
        """Mark MITRE rules migration as completed"""
        try:
            # Check if already marked as completed
            check_query = """
                SELECT count() as count FROM system_migrations 
                WHERE migration_name = '003_seed_mitre_rules_completed'
            """
            
            check_result = await self.db.execute_query(check_query)
            
            if check_result and check_result[0]["count"] > 0:
                logger.debug("MITRE migration already marked as completed")
                return True
            
            # Mark as completed
            insert_query = """
                INSERT INTO system_migrations (
                    migration_name, version, applied_at, description, status
                ) VALUES (
                    '003_seed_mitre_rules_completed', 
                    '1.0.0', 
                    now(), 
                    'MITRE rules seeding completed', 
                    'success'
                )
            """
            
            await self.db.execute_update(insert_query)
            logger.info("✅ MITRE rules migration marked as completed")
            return True
            
        except Exception as e:
            logger.error(f"Error marking MITRE migration as completed: {e}")
            return False
    
    async def get_mitre_rules_count(self) -> int:
        """Get count of loaded MITRE default rules"""
        try:
            query = """
                SELECT count() as count FROM sigma_rules_mt 
                WHERE customer_id IS NULL AND id LIKE 'mitre_default_%'
            """
            
            result = await self.db.execute_query(query)
            return result[0]["count"] if result else 0
            
        except Exception as e:
            logger.error(f"Error getting MITRE rules count: {e}")
            return 0
    
    # Threat Hunting Campaign Operations
    
    async def create_threat_hunting_campaign(self, campaign_data: Dict[str, Any]) -> str:
        """Create a new threat hunting campaign and return campaign ID"""
        try:
            campaign_id = campaign_data.get("id", f"hunt_{uuid.uuid4().hex[:8]}")
            
            query = """
                INSERT INTO threat_hunting_campaigns_mt (
                    id, customer_id, description, status, time_range, 
                    severity_filter, rule_ids, created_at, started_at, 
                    rules_evaluated, events_found, indicators_detected, 
                    progress_percentage, error_message
                ) VALUES (
                    %(id)s, %(customer_id)s, %(description)s, %(status)s, %(time_range)s,
                    %(severity_filter)s, %(rule_ids)s, %(created_at)s, %(started_at)s,
                    %(rules_evaluated)s, %(events_found)s, %(indicators_detected)s,
                    %(progress_percentage)s, %(error_message)s
                )
            """
            
            params = {
                "id": campaign_id,
                "customer_id": campaign_data.get("customer_id"),
                "description": campaign_data.get("description", "Threat hunting campaign"),
                "status": "started",
                "time_range": campaign_data.get("time_range", "24h"),
                "severity_filter": campaign_data.get("severity_filter", []),
                "rule_ids": campaign_data.get("rule_ids", []),
                "created_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc),
                "rules_evaluated": 0,
                "events_found": 0,
                "indicators_detected": 0,
                "progress_percentage": 0,
                "error_message": None
            }
            
            await self.db.execute_update(query, params)
            logger.info(f"Created threat hunting campaign: {campaign_id}")
            
            return campaign_id
            
        except Exception as e:
            logger.error(f"Failed to create threat hunting campaign: {e}")
            raise
    
    async def update_campaign_progress(self, campaign_id: str, progress_data: Dict[str, Any]) -> bool:
        """Update threat hunting campaign progress"""
        try:
            set_clauses = []
            params = {"campaign_id": campaign_id}
            
            if "progress_percentage" in progress_data:
                set_clauses.append("progress_percentage = %(progress_percentage)s")
                params["progress_percentage"] = progress_data["progress_percentage"]
            
            if "rules_evaluated" in progress_data:
                set_clauses.append("rules_evaluated = %(rules_evaluated)s")
                params["rules_evaluated"] = progress_data["rules_evaluated"]
            
            if "events_found" in progress_data:
                set_clauses.append("events_found = %(events_found)s")
                params["events_found"] = progress_data["events_found"]
            
            if "indicators_detected" in progress_data:
                set_clauses.append("indicators_detected = %(indicators_detected)s")
                params["indicators_detected"] = progress_data["indicators_detected"]
            
            if "status" in progress_data:
                set_clauses.append("status = %(status)s")
                params["status"] = progress_data["status"]
            
            if "error_message" in progress_data:
                set_clauses.append("error_message = %(error_message)s")
                params["error_message"] = progress_data["error_message"]
            
            if progress_data.get("status") == "completed":
                set_clauses.append("completed_at = %(completed_at)s")
                params["completed_at"] = datetime.now(timezone.utc)
            
            # Handle enhanced_results - store as JSON string
            if "enhanced_results" in progress_data:
                import json
                from datetime import datetime as dt
                
                def serialize_datetime(obj):
                    """JSON serializer for datetime objects"""
                    if isinstance(obj, dt):
                        return obj.isoformat()
                    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
                
                set_clauses.append("enhanced_results = %(enhanced_results)s")
                params["enhanced_results"] = json.dumps(progress_data["enhanced_results"], default=serialize_datetime)
            
            if not set_clauses:
                return True  # Nothing to update
            
            query = f"""
                ALTER TABLE threat_hunting_campaigns_mt 
                UPDATE {', '.join(set_clauses)}
                WHERE id = %(campaign_id)s
            """
            
            await self.db.execute_update(query, params)
            logger.debug(f"Updated campaign {campaign_id} progress")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update campaign progress: {e}")
            return False
    
    async def get_campaign_status(self, campaign_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get threat hunting campaign status"""
        try:
            query = """
                SELECT * FROM threat_hunting_campaigns_mt 
                WHERE id = %(campaign_id)s AND customer_id = %(customer_id)s
            """
            
            params = {
                "campaign_id": campaign_id,
                "customer_id": customer_id
            }
            
            result = await self.db.fetch_one(query, params)
            
            if not result:
                return None
            
            # Convert result to dict and process arrays
            campaign = dict(result)
            if campaign.get("severity_filter"):
                campaign["severity_filter"] = list(campaign["severity_filter"])
            if campaign.get("rule_ids"):
                campaign["rule_ids"] = list(campaign["rule_ids"])
            
            # Parse enhanced_results JSON if it exists
            if campaign.get("enhanced_results"):
                try:
                    campaign["enhanced_results"] = json.loads(campaign["enhanced_results"])
                except (json.JSONDecodeError, TypeError):
                    campaign["enhanced_results"] = None
            
            return campaign
            
        except Exception as e:
            logger.error(f"Failed to get campaign status: {e}")
            return None
    
    async def get_customer_campaigns(self, customer_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get customer's threat hunting campaigns"""
        try:
            query = """
                SELECT * FROM threat_hunting_campaigns_mt 
                WHERE customer_id = %(customer_id)s 
                ORDER BY created_at DESC 
                LIMIT %(limit)s
            """
            
            params = {
                "customer_id": customer_id,
                "limit": limit
            }
            
            results = await self.db.fetch_all(query, params)
            
            campaigns = []
            for campaign in results:
                campaign_dict = dict(campaign)
                if campaign_dict.get("severity_filter"):
                    campaign_dict["severity_filter"] = list(campaign_dict["severity_filter"])
                if campaign_dict.get("rule_ids"):
                    campaign_dict["rule_ids"] = list(campaign_dict["rule_ids"])
                campaigns.append(campaign_dict)
            
            return campaigns
            
        except Exception as e:
            logger.error(f"Failed to get customer campaigns: {e}")
            return []

    async def get_normalized_logs_for_hunting(
        self, 
        customer_id: str, 
        time_range_hours: int = 24, 
        severity_filter: List[str] = None,
        limit: int = 50000
    ) -> List[Dict[str, Any]]:
        """Get normalized logs for threat hunting from logs_normalized_mt table"""
        try:
            # Build base query
            where_conditions = ["customer_id = %(customer_id)s"]
            params = {
                "customer_id": customer_id,
                "limit": limit
            }
            
            # Add time range filter
            if time_range_hours:
                where_conditions.append("ts >= now() - INTERVAL %(hours)s HOUR")
                params["hours"] = time_range_hours
            
            # Add severity filter if provided
            if severity_filter:
                # Map severity to level field in logs_normalized_mt
                severity_conditions = []
                for i, severity in enumerate(severity_filter):
                    severity_key = f"severity_{i}"
                    severity_conditions.append(f"level = %({severity_key})s")
                    params[severity_key] = severity.upper()  # Assuming levels are uppercase
                
                if severity_conditions:
                    where_conditions.append(f"({' OR '.join(severity_conditions)})")
            
            query = f"""
                SELECT 
                    ts,
                    date,
                    hour,
                    host,
                    service,
                    level,
                    msg,
                    trace_id,
                    span_id,
                    status,
                    src_ip,
                    user_id,
                    severity_num,
                    facility,
                    ingested_at,
                    customer_id
                FROM logs_normalized_mt 
                WHERE {' AND '.join(where_conditions)}
                ORDER BY ts DESC 
                LIMIT %(limit)s
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Convert to list of dictionaries with standardized field names
            logs = []
            for row in results:
                log_dict = {
                    "timestamp": row["ts"],
                    "date": row["date"], 
                    "hour": row["hour"],
                    "host": row["host"],
                    "hostname": row["host"],  # Alias for compatibility
                    "service": row["service"],
                    "level": row["level"],
                    "severity": row["level"].lower() if row["level"] else "info",  # Normalized severity
                    "message": row["msg"],
                    "msg": row["msg"],
                    "trace_id": row["trace_id"],
                    "span_id": row["span_id"],
                    "status": row["status"],
                    "status_code": row["status"],  # Alias for compatibility
                    "src_ip": row["src_ip"],
                    "source_ip": row["src_ip"],  # Alias for compatibility
                    "user": row["user_id"], 
                    "user_id": row["user_id"],
                    "username": row["user_id"],  # Alias for compatibility
                    "severity_num": row["severity_num"],
                    "facility": row["facility"],
                    "ingested_at": row["ingested_at"],
                    "customer_id": row["customer_id"],
                    "created_at": row["ts"],  # For compatibility with existing code
                    
                    # Additional standardized fields for threat hunting
                    "event_data": {
                        "ts": row["ts"],
                        "host": row["host"],
                        "service": row["service"], 
                        "level": row["level"],
                        "msg": row["msg"],
                        "status": row["status"],
                        "src_ip": row["src_ip"],
                        "user": row["user_id"]
                    },
                    "matched_fields": {}  # Will be populated by rule evaluation
                }
                logs.append(log_dict)
            
            logger.info(f"Retrieved {len(logs)} normalized logs for threat hunting (customer: {customer_id}, time_range: {time_range_hours}h)")
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get normalized logs for hunting: {e}")
            return []

    async def get_security_events_by_rules(
        self, 
        customer_id: str,
        rule_ids: List[str] = None,
        time_range_hours: int = 24,
        severity_filter: List[str] = None,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """Get security events filtered by specific rules for efficient threat hunting"""
        try:
            # Build efficient query targeting specific rules
            where_conditions = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id, "limit": limit}
            
            # Rule ID filter (core of threat hunting efficiency)
            if rule_ids:
                rule_placeholders = []
                for i, rule_id in enumerate(rule_ids):
                    placeholder = f"rule_id_{i}"
                    rule_placeholders.append(f"%({placeholder})s")
                    params[placeholder] = rule_id
                where_conditions.append(f"rule_id IN ({', '.join(rule_placeholders)})")
            
            # Time range filter
            if time_range_hours:
                where_conditions.append("created_at >= now() - INTERVAL %(hours)s HOUR")
                params["hours"] = time_range_hours
            
            # Severity filter
            if severity_filter:
                severity_conditions = []
                for i, severity in enumerate(severity_filter):
                    severity_key = f"severity_{i}"
                    severity_conditions.append(f"severity = %({severity_key})s")
                    params[severity_key] = severity
                if severity_conditions:
                    where_conditions.append(f"({' OR '.join(severity_conditions)})")
            
            query = f"""
                SELECT 
                    id, rule_id, title, severity, status,
                    raw_log_data,      -- Original log for context
                    enrichment_data,   -- Matched fields and indicators
                    mitre_techniques,  -- Attack techniques
                    created_at, updated_at
                FROM security_events_mt 
                WHERE {' AND '.join(where_conditions)}
                ORDER BY created_at DESC 
                LIMIT %(limit)s
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Parse JSON fields for analysis
            processed_events = []
            for event in results:
                processed_event = dict(event)
                
                # Parse raw_log_data and enrichment_data for threat analysis
                for json_field in ["raw_log_data", "enrichment_data"]:
                    if processed_event.get(json_field):
                        try:
                            processed_event[json_field] = json.loads(processed_event[json_field])
                        except (json.JSONDecodeError, TypeError):
                            processed_event[json_field] = {}
                
                processed_events.append(processed_event)
            
            logger.info(f"Retrieved {len(processed_events)} security events for threat hunting (customer: {customer_id}, rules: {len(rule_ids) if rule_ids else 'all'})")
            return processed_events
            
        except Exception as e:
            logger.error(f"Failed to get security events by rules for hunting: {e}")
            return []