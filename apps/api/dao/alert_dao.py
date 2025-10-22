"""
Alert Management DAO - Database Operations for Alert System
Handles alert rules, instances, and notification channels
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
import uuid

from database_layer import DatabaseLayer
from constants.database_constants import (
    ALERT_RULES_TABLE, ALERT_INSTANCES_TABLE, 
    NOTIFICATION_CHANNELS_TABLE, ALERT_RULE_STATES_TABLE
)

logger = structlog.get_logger(__name__)

class AlertDAO:
    """Data Access Object for Alert System"""
    
    def __init__(self):
        self.db = DatabaseLayer("AlertDAO", "alert-dao-service-key")
    
    # Alert Rules Operations
    
    async def save_alert_rule(self, rule_data: Dict[str, Any]) -> str:
        """Save alert rule to database"""
        try:
            rule_id = rule_data.get("rule_id", str(uuid.uuid4()))
            
            # Map API fields to database schema
            query = f"""
            INSERT INTO {ALERT_RULES_TABLE} (
                id, customer_id, name, description, rule_type,
                query, condition_config, notification_channels, severity,
                is_enabled, cooldown_minutes, created_at, updated_at, created_by
            ) VALUES (
                %(id)s, %(customer_id)s, %(name)s, %(description)s, %(rule_type)s,
                %(query)s, %(condition_config)s, %(notification_channels)s, %(severity)s,
                %(is_enabled)s, %(cooldown_minutes)s, %(created_at)s, %(updated_at)s, %(created_by)s
            )
            """
            
            # Handle condition_config - preserve nested structure if provided
            if "condition_config" in rule_data and rule_data["condition_config"]:
                # Use the provided nested condition_config structure
                if isinstance(rule_data["condition_config"], str):
                    # Already JSON string
                    condition_config = json.loads(rule_data["condition_config"])
                else:
                    # Dictionary structure
                    condition_config = rule_data["condition_config"]
                
                # Add metadata fields to existing config
                condition_config.setdefault("evaluation_interval", rule_data.get("evaluation_interval", 300))
                condition_config.setdefault("max_alerts_per_hour", rule_data.get("max_alerts_per_hour", 10))
                condition_config.setdefault("tags", rule_data.get("tags", []))
            else:
                # Legacy format: combine conditions and filters into condition_config JSON
                condition_config = {
                    "conditions": rule_data.get("conditions", []),
                    "filters": rule_data.get("filters", []),
                    "evaluation_interval": rule_data.get("evaluation_interval", 300),
                    "max_alerts_per_hour": rule_data.get("max_alerts_per_hour", 10),
                    "tags": rule_data.get("tags", [])
                }
            
            params = {
                "id": rule_id,
                "customer_id": rule_data["customer_id"],
                "name": rule_data["name"],
                "description": rule_data.get("description", ""),
                "rule_type": rule_data.get("rule_type", "threshold"),
                "query": rule_data.get("query", ""),  # Empty query for now
                "condition_config": json.dumps(condition_config),
                "notification_channels": rule_data.get("notification_channels", []),
                "severity": rule_data.get("severity", "medium"),
                "is_enabled": 1 if rule_data.get("enabled", True) else 0,
                "cooldown_minutes": max(1, rule_data.get("cooldown_period", 600) // 60),  # Convert seconds to minutes
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "created_by": rule_data.get("created_by", "system")
            }
            
            await self.db.execute_query(query, params)
            logger.info(f"Alert rule saved: {rule_id}")
            
            return rule_id
            
        except Exception as e:
            logger.error(f"Failed to save alert rule: {e}")
            raise
    
    async def get_alert_rule(self, rule_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get alert rule by ID"""
        try:
            query = f"""
            SELECT * FROM {ALERT_RULES_TABLE}
            WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
            """
            
            result = await self.db.fetch_one(query, {"rule_id": rule_id, "customer_id": customer_id})
            
            if result:
                # Parse condition_config JSON 
                condition_config = json.loads(result.get("condition_config", "{}"))
                
                # Map database fields to API response format
                result["rule_id"] = result["id"]
                
                # Check if this is a nested condition config (has operator) or legacy format
                if "operator" in condition_config:
                    # Nested condition format - preserve the structure
                    result["condition_config"] = condition_config
                    result["conditions"] = []  # Empty for backward compatibility
                    result["filters"] = []    # Empty for backward compatibility
                else:
                    # Legacy format - expand conditions and filters
                    result["conditions"] = condition_config.get("conditions", [])
                    result["filters"] = condition_config.get("filters", [])
                
                result["tags"] = condition_config.get("tags", [])
                result["evaluation_interval"] = condition_config.get("evaluation_interval", 300)
                result["max_alerts_per_hour"] = condition_config.get("max_alerts_per_hour", 10)
                result["enabled"] = bool(result.get("is_enabled", 0))
                result["cooldown_period"] = result.get("cooldown_minutes", 5) * 60  # Convert to seconds
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to get alert rule {rule_id}: {e}")
            raise
    
    async def list_alert_rules(self, customer_id: str, enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        """List alert rules for customer"""
        try:
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id}
            
            if enabled is not None:
                where_clauses.append("is_enabled = %(enabled)s")
                params["enabled"] = 1 if enabled else 0
            
            query = f"""
            SELECT * FROM {ALERT_RULES_TABLE}
            WHERE {' AND '.join(where_clauses)}
            ORDER BY created_at DESC
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Parse JSON fields and map to API format for each rule
            for rule in results:
                condition_config = json.loads(rule.get("condition_config", "{}"))
                
                # Map database fields to API response format
                rule["rule_id"] = rule["id"]
                rule["conditions"] = condition_config.get("conditions", [])
                rule["filters"] = condition_config.get("filters", [])
                rule["tags"] = condition_config.get("tags", [])
                rule["evaluation_interval"] = condition_config.get("evaluation_interval", 300)
                rule["max_alerts_per_hour"] = condition_config.get("max_alerts_per_hour", 10)
                rule["enabled"] = bool(rule.get("is_enabled", 0))
                rule["cooldown_period"] = rule.get("cooldown_minutes", 5) * 60  # Convert to seconds
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list alert rules for customer {customer_id}: {e}")
            raise
    
    async def get_all_alert_rules(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get all alert rules across all customers for cache initialization"""
        try:
            where_clauses = []
            params = {}
            
            if enabled_only:
                where_clauses.append("is_enabled = 1")
            
            where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            query = f"""
            SELECT * FROM {ALERT_RULES_TABLE}
            {where_clause}
            ORDER BY customer_id, created_at DESC
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Parse JSON fields and map to API format for each rule
            for rule in results:
                condition_config = json.loads(rule.get("condition_config", "{}"))
                
                # Map database fields to API response format
                rule["rule_id"] = rule["id"]
                rule["conditions"] = condition_config.get("conditions", [])
                rule["filters"] = condition_config.get("filters", [])
                rule["tags"] = condition_config.get("tags", [])
                rule["evaluation_interval"] = condition_config.get("evaluation_interval", 300)
                rule["max_alerts_per_hour"] = condition_config.get("max_alerts_per_hour", 10)
                rule["enabled"] = bool(rule.get("is_enabled", 0))
                rule["cooldown_period"] = rule.get("cooldown_minutes", 5) * 60  # Convert to seconds
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get all alert rules: {e}")
            raise
    
    async def update_alert_rule(self, rule_id: str, customer_id: str, updates: Dict[str, Any]) -> bool:
        """Update alert rule"""
        try:
            set_clauses = []
            params = {"rule_id": rule_id, "customer_id": customer_id}
            
            # Handle condition_config updates by merging with existing data
            if any(field in updates for field in ["conditions", "filters", "tags", "evaluation_interval", "max_alerts_per_hour"]):
                # Get existing rule directly from database to preserve condition_config
                existing_query = f"""
                SELECT condition_config FROM {ALERT_RULES_TABLE}
                WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
                """
                
                existing_result = await self.db.fetch_one(existing_query, {"rule_id": rule_id, "customer_id": customer_id})
                if existing_result:
                    existing_config = json.loads(existing_result.get("condition_config", "{}"))
                    
                    # Update condition_config fields
                    if "conditions" in updates:
                        existing_config["conditions"] = updates["conditions"]
                    if "filters" in updates:
                        existing_config["filters"] = updates["filters"]
                    if "tags" in updates:
                        existing_config["tags"] = updates["tags"]
                    if "evaluation_interval" in updates:
                        existing_config["evaluation_interval"] = updates["evaluation_interval"]
                    if "max_alerts_per_hour" in updates:
                        existing_config["max_alerts_per_hour"] = updates["max_alerts_per_hour"]
                    
                    set_clauses.append("condition_config = %(condition_config)s")
                    params["condition_config"] = json.dumps(existing_config)
            
            # Build SET clauses for direct field updates
            for field, value in updates.items():
                if field in ["conditions", "filters", "tags", "evaluation_interval", "max_alerts_per_hour"]:
                    # These are handled above in condition_config
                    continue
                elif field == "enabled":
                    field = "is_enabled"
                    value = 1 if value else 0
                elif field == "cooldown_period":
                    field = "cooldown_minutes"
                    value = max(1, value // 60)  # Convert seconds to minutes
                # All other fields (like severity, description, name, etc.) are passed through directly
                
                set_clauses.append(f"{field} = %({field})s")
                params[field] = value
            
            # Always update the updated_at timestamp
            set_clauses.append("updated_at = %(updated_at)s")
            params["updated_at"] = datetime.now(timezone.utc)
            
            if not set_clauses:
                return True  # No updates to apply
            
            query = f"""
            ALTER TABLE {ALERT_RULES_TABLE} UPDATE
            {', '.join(set_clauses)}
            WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
            SETTINGS mutations_sync = 2
            """
            
            await self.db.execute_query(query, params)
            logger.info(f"Alert rule updated: {rule_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update alert rule {rule_id}: {e}")
            raise
    
    async def delete_alert_rule(self, rule_id: str, customer_id: str) -> bool:
        """Delete alert rule"""
        try:
            query = f"""
            ALTER TABLE {ALERT_RULES_TABLE} DELETE
            WHERE id = %(rule_id)s AND customer_id = %(customer_id)s
            """
            
            await self.db.execute_query(query, {"rule_id": rule_id, "customer_id": customer_id})
            logger.info(f"Alert rule deleted: {rule_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete alert rule {rule_id}: {e}")
            raise
    
    # Alert Instances Operations
    
    async def save_alert_instance(self, alert_data: Dict[str, Any]) -> str:
        """Save alert instance to database"""
        try:
            alert_id = alert_data.get("alert_id", str(uuid.uuid4()))
            
            query = f"""
            INSERT INTO {ALERT_INSTANCES_TABLE} (
                id, rule_id, customer_id, status, triggered_at,
                acknowledged_at, resolved_at, acknowledged_by,
                trigger_data, resolution_data, escalation_level
            ) VALUES (
                %(id)s, %(rule_id)s, %(customer_id)s, %(status)s, %(triggered_at)s,
                %(acknowledged_at)s, %(resolved_at)s, %(acknowledged_by)s,
                %(trigger_data)s, %(resolution_data)s, %(escalation_level)s
            )
            """
            
            # Use provided trigger_data if available, otherwise create basic structure
            if "trigger_data" in alert_data and alert_data["trigger_data"]:
                # Use the rich trigger_data provided by the alert processor
                trigger_data_str = alert_data["trigger_data"]
                if isinstance(trigger_data_str, str):
                    # Already JSON string from alert processor
                    trigger_data_str = trigger_data_str
                else:
                    # Convert dict to JSON string
                    trigger_data_str = json.dumps(trigger_data_str)
            else:
                # Fallback to basic structure for backwards compatibility
                trigger_data = {
                    "title": alert_data.get("title", ""),
                    "message": alert_data.get("message", ""),
                    "severity": alert_data.get("severity", "medium"),
                    "details": alert_data.get("details", {})
                }
                trigger_data_str = json.dumps(trigger_data)
            
            params = {
                "id": alert_id,
                "rule_id": alert_data["rule_id"],
                "customer_id": alert_data["customer_id"],
                "status": alert_data.get("status", "triggered"),  # Database uses triggered instead of active
                "triggered_at": alert_data.get("triggered_at", datetime.now(timezone.utc)),
                "acknowledged_at": alert_data.get("acknowledged_at"),
                "resolved_at": alert_data.get("resolved_at"),
                "acknowledged_by": alert_data.get("acknowledged_by"),
                "trigger_data": trigger_data_str,
                "resolution_data": alert_data.get("resolution_notes"),
                "escalation_level": alert_data.get("escalation_level", 0)
            }
            
            await self.db.execute_query(query, params)
            logger.info(f"Alert instance saved: {alert_id}")
            
            return alert_id
            
        except Exception as e:
            logger.error(f"Failed to save alert instance: {e}")
            raise
    
    async def get_alert_instance(self, alert_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get alert instance by ID"""
        try:
            query = f"""
            SELECT * FROM {ALERT_INSTANCES_TABLE}
            WHERE id = %(alert_id)s AND customer_id = %(customer_id)s
            """
            
            result = await self.db.fetch_one(query, {"alert_id": alert_id, "customer_id": customer_id})
            
            if result:
                # Parse trigger_data JSON and expand it
                trigger_data = json.loads(result.get("trigger_data", "{}"))
                
                # Map database fields to API response format
                result["alert_id"] = result["id"]
                result["title"] = trigger_data.get("title", "")
                result["message"] = trigger_data.get("message", "")
                result["severity"] = trigger_data.get("severity", "medium")
                result["details"] = trigger_data.get("details", {})
                result["resolution_notes"] = result.get("resolution_data")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to get alert instance {alert_id}: {e}")
            raise
    
    async def list_alert_instances(self, customer_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List alert instances for customer"""
        try:
            where_clauses = ["customer_id = %(customer_id)s"]
            params = {"customer_id": customer_id}
            
            if status:
                # Map API status to database status
                if status == "active":
                    status = "triggered"
                where_clauses.append("status = %(status)s")
                params["status"] = status
            
            query = f"""
            SELECT * FROM {ALERT_INSTANCES_TABLE}
            WHERE {' AND '.join(where_clauses)}
            ORDER BY triggered_at DESC
            """
            
            results = await self.db.fetch_all(query, params)
            
            # Parse JSON fields and map field names for each alert
            for alert in results:
                trigger_data = json.loads(alert.get("trigger_data", "{}"))
                
                # Map database fields to API response format
                alert["alert_id"] = alert["id"]
                alert["title"] = trigger_data.get("title", "")
                alert["message"] = trigger_data.get("message", "")
                alert["severity"] = trigger_data.get("severity", "medium")
                alert["details"] = trigger_data.get("details", {})
                alert["resolution_notes"] = alert.get("resolution_data")
                
                # Map database status to API status
                if alert["status"] == "triggered":
                    alert["status"] = "active"
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list alert instances for customer {customer_id}: {e}")
            raise
    
    async def update_alert_status(self, alert_id: str, customer_id: str, status: str, 
                                 user: str, notes: Optional[str] = None) -> bool:
        """Update alert instance status"""
        try:
            updates = {"status": status}
            timestamp_field = None
            user_field = None
            
            if status == "acknowledged":
                timestamp_field = "acknowledged_at"
                user_field = "acknowledged_by"
            elif status == "resolved":
                timestamp_field = "resolved_at"
                # Note: No resolved_by field in database, only acknowledged_by
                if notes:
                    updates["resolution_data"] = notes
            
            if timestamp_field:
                updates[timestamp_field] = datetime.now(timezone.utc)
            if user_field:
                updates[user_field] = user
            
            set_clauses = [f"{field} = %({field})s" for field in updates.keys()]
            
            query = f"""
            ALTER TABLE {ALERT_INSTANCES_TABLE} UPDATE
            {', '.join(set_clauses)}
            WHERE id = %(alert_id)s AND customer_id = %(customer_id)s
            """
            
            params = {"alert_id": alert_id, "customer_id": customer_id, **updates}
            
            await self.db.execute_query(query, params)
            logger.info(f"Alert status updated: {alert_id} -> {status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update alert status {alert_id}: {e}")
            raise
    
    async def update_rule_state(self, rule_state_data: Dict[str, Any]) -> bool:
        """Update alert rule state statistics"""
        try:
            rule_id = rule_state_data["rule_id"]
            customer_id = rule_state_data["customer_id"]
            
            # Use ReplacingMergeTree INSERT which acts as upsert
            query = f"""
            INSERT INTO {ALERT_RULE_STATES_TABLE} (
                rule_id, last_evaluation, last_trigger, evaluation_count, 
                trigger_count, consecutive_failures, state_data, 
                created_at, updated_at, customer_id
            ) VALUES (
                %(rule_id)s, %(last_evaluation)s, %(last_trigger)s, 
                %(evaluation_count)s, %(trigger_count)s, %(consecutive_failures)s, 
                %(state_data)s, %(created_at)s, %(updated_at)s, %(customer_id)s
            )
            """
            
            # Set defaults for any missing fields
            current_time = datetime.now(timezone.utc)
            params = {
                "rule_id": rule_id,
                "customer_id": customer_id,
                "last_evaluation": rule_state_data.get("last_evaluation", current_time),
                "last_trigger": rule_state_data.get("last_trigger"),
                "evaluation_count": rule_state_data.get("evaluation_count", 1),
                "trigger_count": rule_state_data.get("trigger_count", 1),
                "consecutive_failures": rule_state_data.get("consecutive_failures", 0),
                "state_data": rule_state_data.get("state_data", "{}"),
                "created_at": rule_state_data.get("created_at", current_time),
                "updated_at": rule_state_data.get("updated_at", current_time)
            }
            
            await self.db.execute_query(query, params)
            logger.info(f"Rule state updated for rule {rule_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update rule state for rule {rule_state_data.get('rule_id')}: {e}")
            raise
    
    # Notification Channels Operations
    
    async def save_notification_channel(self, channel_data: Dict[str, Any]) -> str:
        """Save notification channel to database"""
        try:
            channel_id = channel_data.get("channel_id", str(uuid.uuid4()))
            
            query = f"""
            INSERT INTO {NOTIFICATION_CHANNELS_TABLE} (
                id, customer_id, name, channel_type, config,
                is_enabled, created_at, updated_at
            ) VALUES (
                %(id)s, %(customer_id)s, %(name)s, %(channel_type)s, %(config)s,
                %(is_enabled)s, %(created_at)s, %(updated_at)s
            )
            """
            
            params = {
                "id": channel_id,
                "customer_id": channel_data["customer_id"],
                "name": channel_data["name"],
                "channel_type": channel_data["type"],
                "config": json.dumps(channel_data.get("configuration", {})),
                "is_enabled": 1 if channel_data.get("enabled", True) else 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(query, params)
            logger.info(f"Notification channel saved: {channel_id}")
            
            return channel_id
            
        except Exception as e:
            logger.error(f"Failed to save notification channel: {e}")
            raise
    
    async def list_notification_channels(self, customer_id: str) -> List[Dict[str, Any]]:
        """List notification channels for customer"""
        try:
            query = f"""
            SELECT * FROM {NOTIFICATION_CHANNELS_TABLE}
            WHERE customer_id = %(customer_id)s
            ORDER BY created_at DESC
            """
            
            results = await self.db.fetch_all(query, {"customer_id": customer_id})
            
            # Parse JSON configuration and map field names for each channel
            for channel in results:
                channel["channel_id"] = channel["id"]
                channel["type"] = channel["channel_type"]
                channel["configuration"] = json.loads(channel.get("config", "{}"))
                channel["enabled"] = bool(channel.get("is_enabled", 0))
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to list notification channels for customer {customer_id}: {e}")
            raise
    
    # Statistics and Health Operations
    
    async def get_alert_stats(self, customer_id: str) -> Dict[str, Any]:
        """Get alert system statistics for customer"""
        try:
            # Get rule counts
            rules_query = f"""
            SELECT 
                COUNT(*) as total_rules,
                SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) as enabled_rules
            FROM {ALERT_RULES_TABLE}
            WHERE customer_id = %(customer_id)s
            """
            
            rules_stats = await self.db.fetch_one(rules_query, {"customer_id": customer_id})
            
            # Get alert counts by status
            alerts_query = f"""
            SELECT 
                status,
                COUNT(*) as count
            FROM {ALERT_INSTANCES_TABLE}
            WHERE customer_id = %(customer_id)s
            GROUP BY status
            """
            
            alerts_by_status = await self.db.fetch_all(alerts_query, {"customer_id": customer_id})
            
            # Format statistics
            stats = {
                "total_rules": rules_stats.get("total_rules", 0),
                "enabled_rules": rules_stats.get("enabled_rules", 0),
                "disabled_rules": rules_stats.get("total_rules", 0) - rules_stats.get("enabled_rules", 0),
                "active_alerts": 0,
                "acknowledged_alerts": 0,
                "resolved_alerts": 0,
                "total_alerts_fired": 0
            }
            
            for alert_stat in alerts_by_status:
                status = alert_stat["status"]
                count = alert_stat["count"]
                stats["total_alerts_fired"] += count
                
                # Map database status to API status for statistics
                if status == "triggered":
                    stats["active_alerts"] = count
                elif status == "acknowledged":
                    stats["acknowledged_alerts"] = count
                elif status == "resolved":
                    stats["resolved_alerts"] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get alert stats for customer {customer_id}: {e}")
            raise
    
    async def get_recent_alert_instances(self, customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alert instances for tenant alerts summary"""
        try:
            query = f"""
            SELECT 
                ai.id as alert_id,
                ar.name as rule_name,
                ar.severity,
                ai.triggered_at,
                ai.status,
                ai.trigger_data
            FROM {ALERT_INSTANCES_TABLE} ai
            LEFT JOIN {ALERT_RULES_TABLE} ar ON ai.rule_id = ar.id
            WHERE ai.customer_id = %(customer_id)s
            ORDER BY ai.triggered_at DESC
            LIMIT %(limit)s
            """
            
            results = await self.db.fetch_all(query, {"customer_id": customer_id, "limit": limit})
            
            # Format the results
            formatted_alerts = []
            for alert in results:
                # Map database status to API status
                status = alert["status"]
                if status == "triggered":
                    status = "active"
                
                formatted_alerts.append({
                    "rule_name": alert.get("rule_name", "Unknown Rule"),
                    "severity": alert.get("severity", "info"),
                    "triggered_at": alert.get("triggered_at", "").isoformat() if alert.get("triggered_at") else "",
                    "status": status
                })
            
            return formatted_alerts
            
        except Exception as e:
            logger.error(f"Failed to get recent alert instances for customer {customer_id}: {e}")
            return []
    
    async def get_escalation_policies(self, customer_id: str) -> Dict[str, Any]:
        """Get escalation policies configuration from alert rules data"""
        # Query alert rules to understand current escalation configuration
        query = f"""
        SELECT 
            COUNT() as total_rules,
            countIf(is_enabled = 1) as enabled_rules,
            arrayReduce('max', groupArray(cooldown_minutes)) as max_cooldown,
            arrayReduce('min', groupArray(cooldown_minutes)) as min_cooldown,
            groupUniqArray(severity) as severities
        FROM {ALERT_RULES_TABLE}
        WHERE customer_id = %(customer_id)s
        """
        
        result = await self.db.execute_query(query, {"customer_id": customer_id})
        
        if result:
            rule_stats = result[0]
            
            # Build escalation policy based on existing alert configuration
            return {
                "enabled": rule_stats.get("enabled_rules", 0) > 0,
                "rules_configured": rule_stats.get("total_rules", 0),
                "escalation_levels": list(rule_stats.get("severities", [])),
                "cooldown_config": {
                    "min_cooldown_minutes": rule_stats.get("min_cooldown", 5),
                    "max_cooldown_minutes": rule_stats.get("max_cooldown", 60)
                },
                "notification_flow": ["immediate", "escalation", "resolution"]
            }
        else:
            # No rules exist - return actual empty state
            return {
                "enabled": False,
                "rules_configured": 0,
                "escalation_levels": [],
                "cooldown_config": {
                    "min_cooldown_minutes": 5,
                    "max_cooldown_minutes": 60
                },
                "notification_flow": ["immediate", "escalation", "resolution"]
            }