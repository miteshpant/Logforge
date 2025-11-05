"""
Security Event Handler - Handles Sigma rule events and security-related events
"""

from typing import List, Dict, Any
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_LOGS_NORMALIZED,
    EVENT_SIGMA_RULE_CREATED,
    EVENT_SIGMA_RULE_UPDATED,
    EVENT_SIGMA_RULE_DELETED,
    EVENT_SIGMA_RULE_ENABLED,
    EVENT_SIGMA_RULE_DISABLED,
    EVENT_SECURITY_DETECTION_TRIGGERED,
    EVENT_SECURITY_DETECTION_RESOLVED,
    EVENT_SECURITY_DETECTION_ACKNOWLEDGED,
    EVENT_SECURITY_DETECTION_FALSE_POSITIVE
)

logger = structlog.get_logger(__name__)


class SecurityEventHandler(EventHandler):
    """Handler for security-related events and Sigma rule management"""

    def __init__(self):
        """Initialize security event handler with Sigma rule cache processor."""
        from ..management.cache.sigma_rule_cache import SigmaRuleCache
        self.sigma_rule_cache = SigmaRuleCache()

    async def handle(self, event: BaseEvent) -> bool:
        """Handle security events"""
        logger.info(
            "Processing security event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        try:
            event_type = event.event_type
            event_data = {
                'customer_id': event.customer_id,
                'rule_id': event.data.get('rule_id') or event.data.get('id'),
                **event.data
            }

            if event_type == EVENT_LOGS_NORMALIZED:
                return await self._handle_normalized_logs_event(event_data)
            elif event_type.startswith("security.sigma.rule."):
                return await self._handle_sigma_rule_event(event_type, event_data)
            elif event_type.startswith("security.detection."):
                return await self._handle_security_detection_event(event_type, event_data)
            else:
                logger.info(f"Security event type {event_type} received")
                return True

        except Exception as e:
            logger.error(f"Error handling security event {event.event_type}: {e}")
            return False

    async def _handle_normalized_logs_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle logs.normalized events for Sigma rule matching."""
        try:
            customer_id = event_data.get('customer_id')
            normalized_logs = event_data.get('normalized_logs', [])

            logger.info(f"🛡️ Processing normalized logs for Sigma rule matching: {len(normalized_logs)} logs from customer {customer_id}")

            # Get Sigma rules for this customer (including default rules)
            sigma_rules = await self.sigma_rule_cache.get_customer_rules(customer_id, include_defaults=True)

            if not sigma_rules:
                logger.debug(f"No Sigma rules found for customer {customer_id}, skipping security analysis")
                return True

            logger.debug(f"📋 Found {len(sigma_rules)} Sigma rules for customer {customer_id}")

            # Process normalized logs through Sigma rule matching
            # Use normalized logs instead of raw logs for better field mapping support
            event_data_for_sigma = {
                'customer_id': customer_id,
                'logs': normalized_logs,  # Use normalized logs with field mapping
                'field_mapping_applied': event_data.get('field_mapping_applied', True),
                'normalization_time_ms': event_data.get('normalization_time_ms', 0)
            }

            detections_count = await self._process_logs_with_sigma_rules(event_data_for_sigma, sigma_rules)

            logger.debug(f"✅ Sigma rule processing completed for customer {customer_id}: {detections_count} detections")
            return True

        except Exception as e:
            logger.error(f"Error handling normalized logs event for Sigma rules: {e}")
            return False

    async def _handle_sigma_rule_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle Sigma rule CRUD events for cache management."""
        try:
            rule_id = event_data.get('rule_id') or event_data.get('id')
            customer_id = event_data.get('customer_id')  # None for default rules

            logger.info(f"🔧 SecurityEventHandler received Sigma rule event {event_type} for rule {rule_id} (customer: {customer_id or 'default'})")
            logger.debug(f"🔧 Event data keys: {list(event_data.keys())}")

            # Delegate to Sigma rule cache for cache updates
            success = await self.sigma_rule_cache.handle_rule_event(event_type, event_data)

            if success:
                logger.info(f"✅ Sigma rule event {event_type} processed successfully for rule {rule_id}")
            else:
                logger.error(f"❌ Failed to process Sigma rule event {event_type} for rule {rule_id}")

            return success

        except Exception as e:
            logger.error(f"Error handling Sigma rule event {event_type} for rule {rule_id}: {e}")
            return False

    async def _handle_security_detection_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle security detection lifecycle events."""
        try:
            rule_id = event_data.get('rule_id')
            customer_id = event_data.get('customer_id')
            severity = event_data.get('severity', 'unknown')
            detection_id = event_data.get('detection_id') or event_data.get('id')

            logger.info(f"🚨 Security detection event: {event_type}, rule {rule_id}, severity {severity} (customer: {customer_id})")

            if event_type == EVENT_SECURITY_DETECTION_TRIGGERED:
                logger.debug(f"🚨 New security detection triggered: {detection_id}")

                # Save the security detection to database for persistence
                await self._save_security_detection_to_database(event_data)

            elif event_type == EVENT_SECURITY_DETECTION_RESOLVED:
                actual_status = event_data.get("status", "resolved")
                logger.debug(f"✅ Security detection status changed: {detection_id} -> {actual_status}")
                # Event handler should NOT update database - only process for streaming/notifications

            elif event_type == EVENT_SECURITY_DETECTION_ACKNOWLEDGED:
                actual_status = event_data.get("status", "investigating")
                logger.debug(f"👁️ Security detection acknowledged: {detection_id} -> {actual_status}")
                # Event handler should NOT update database - only process for streaming/notifications

            elif event_type == EVENT_SECURITY_DETECTION_FALSE_POSITIVE:
                actual_status = event_data.get("status", "false_positive")
                logger.debug(
                    f"👁️ Security detection marked false-positive: {detection_id} -> {actual_status}")

            return True

        except Exception as e:
            logger.error(f"Error handling security detection event {event_type}: {e}")
            return False

    async def _process_logs_with_sigma_rules(self, event_data: Dict[str, Any], sigma_rules: List[Dict[str, Any]]) -> int:
        """
        Process logs with Sigma rules to detect security events using the SigmaRuleEngine.

        Args:
            event_data: Log batch event data
            sigma_rules: List of Sigma rules to match against

        Returns:
            int: Number of detections found
        """
        try:
            logs = event_data.get('logs', [])
            customer_id = event_data.get('customer_id')

            if not logs or not sigma_rules:
                logger.debug(f"📭 No logs or rules to process for customer {customer_id}")
                return 0

            logger.info(f"🛡️ Processing {len(logs)} logs with {len(sigma_rules)} Sigma rules for customer {customer_id}")

            # Import the Sigma engine
            from sigma_engine import sigma_engine

            # Evaluate logs against Sigma rules (logs are already normalized from EVENT_LOGS_NORMALIZED)
            matches = await sigma_engine.evaluate_logs_against_rules(logs, sigma_rules, customer_id, logs_normalized=True)

            detections_count = len(matches)

            if detections_count > 0:
                logger.info(f"🚨 Found {detections_count} security detections for customer {customer_id}")
                for match in matches:
                    logger.info(f"🔍 Detection: {match.rule_id} - {match.rule_title} (severity: {match.severity.value})")
            else:
                logger.debug(f"✅ No security detections found for customer {customer_id}")

            return detections_count

        except Exception as e:
            logger.error(f"Error processing logs with Sigma rules: {e}")
            return 0

    async def _save_security_detection_to_database(self, event_data: Dict[str, Any]) -> bool:
        """Save security detection to database with enhanced enrichment data."""
        try:
            import json
            from datetime import datetime, timezone
            from services.security_service import SecurityService
            security_service = SecurityService()

            # Transform event data for database storage
            # The actual event structure uses: detection_id, rule_name, triggered_at
            rule_title = event_data.get("rule_name") or "Unknown Rule"  # rule_name can be None
            rule_id = event_data.get("rule_id")
            customer_id = event_data.get("customer_id")

            if not rule_title or rule_title == "None":
                # If rule_name is missing, try to get it from rule_id by looking up the rule
                try:
                    if rule_id:
                        # Try to get rule title from Sigma rule cache
                        sigma_rules = await self.sigma_rule_cache.get_customer_rules(customer_id, include_defaults=True)
                        for rule in sigma_rules:
                            if rule.get("id") == rule_id:
                                rule_title = rule.get("title", f"Rule {rule_id[:8]}")
                                break
                        else:
                            rule_title = f"Rule {rule_id[:8]}"  # Fallback to rule ID prefix
                except Exception:
                    rule_title = f"Rule {event_data.get('rule_id', 'unknown')[:8]}"
            # Raw log data: Store the normalized log that triggered the detection
            artifact_data = event_data.get("enrichment_data", {})
            matched_fields = event_data.get("matched_fields", {})

            # If artifact_data is empty, reconstruct log data from matched_fields
            if not artifact_data and matched_fields:
                reconstructed_log = {}
                for field, match_info in matched_fields.items():
                    if isinstance(match_info, dict) and "log_value" in match_info:
                        reconstructed_log[field] = match_info["log_value"]
                artifact_data = reconstructed_log

            raw_log_data = {
                "normalized_log": artifact_data,
                "source_format": "json",
                "field_mapping_applied": True,
                "log_source": {
                    "host": artifact_data.get("host") or artifact_data.get("hostname"),
                    "service": artifact_data.get("service"),
                    "event_type": artifact_data.get("event_type"),
                    "src_ip" : artifact_data.get("src_ip")
                }
            }

            # Simplified enrichment data using normalized log and matched fields
            enrichment_data = {
                "detection_metadata": {
                    "detection_id": event_data.get("detection_id"),
                    "rule_engine": "sigma",
                    "detection_confidence": event_data.get("confidence", 0.85),
                    "triggered_at": event_data.get("triggered_at")
                },
                "rule_details": {
                    "rule_id": rule_id,
                    "rule_title": rule_title,
                    "rule_severity": event_data.get("severity", "medium")
                },
                "matched_conditions": event_data.get("matched_fields", {}),
                "normalized_log_data": artifact_data,
                "threat_context": {
                    "attack_techniques": event_data.get("attack_techniques", []),
                    "kill_chain_phases": event_data.get("kill_chain_phases", []),
                    "network_indicators": {
                        "src_ip": artifact_data.get("src_ip"),
                        "user": artifact_data.get("user"),
                        "host": artifact_data.get("host") or artifact_data.get("hostname"),
                        "service": artifact_data.get("service"),
                        "event_type": artifact_data.get("event_type"),
                        "status_code": artifact_data.get("status_code")
                    }
                },
                "threat_intelligence_correlation": await self._correlate_with_threat_intel(artifact_data, customer_id)
            }

            # Enhanced MITRE ATT&CK techniques with sub-techniques
            mitre_techniques = []
            attack_techniques = event_data.get("attack_techniques", [])
            for technique in attack_techniques:
                if isinstance(technique, str):
                    mitre_techniques.append(technique)
                elif isinstance(technique, dict):
                    # Support for detailed technique mapping
                    technique_id = technique.get("id") or technique.get("technique_id")
                    if technique_id:
                        mitre_techniques.append(technique_id)

            detection_data = {
                "id": event_data.get("detection_id"),  # Actual field is detection_id, not id
                "customer_id": customer_id,
                "rule_id": rule_id,
                "rule_title": rule_title,  # Use the resolved rule title
                "severity": event_data.get("severity", "medium"),
                "status": "triggered",
                "timestamp": event_data.get("triggered_at"),  # Actual field is triggered_at, not timestamp
                "event_data": event_data,  # Store full event data for backward compatibility
                "matched_fields": event_data.get("matched_fields", {}),
                "attack_techniques": mitre_techniques,
                "kill_chain_phase": None,  # Could be derived from attack_techniques
                "assigned_to": None,
                "investigation_notes": [],
                "artifacts": [],
                "source_logs": [],
                # Enhanced fields for threat hunting
                "raw_log_data": json.dumps(raw_log_data, default=str),
                "enrichment_data": json.dumps(enrichment_data, default=str),
                "mitre_techniques": mitre_techniques
            }

            event_id = await security_service.create_security_event(detection_data)
            logger.info(f"💾 Enhanced security detection saved to database: {event_id} with {len(mitre_techniques)} MITRE techniques")

            return True

        except Exception as e:
            logger.error(f"Failed to save enhanced security detection to database: {e}")
            return False

    async def _correlate_with_threat_intel(self, event_data: Dict[str, Any], customer_id: str) -> Dict[str, Any]:
        """Correlate detection with threat intelligence indicators."""
        try:
            from services.security_service import SecurityService

            security_service = SecurityService()
            correlation_results = {
                "ioc_matches": [],
                "threat_score": 0,
                "threat_categories": [],
                "related_campaigns": [],
                "attribution": None,
                "confidence_score": 0.0
            }

            # Get threat intelligence indicators for this customer
            try:
                threat_indicators = await security_service.get_threat_indicators(customer_id)
            except Exception as e:
                logger.warning(f"Could not retrieve threat intel for customer {customer_id}: {e}")
                threat_indicators = []

            # Extract potential IOCs from the detection event
            potential_iocs = {
                "ip_addresses": [],
                "domains": [],
                "urls": [],
                "file_hashes": [],
                "email_addresses": []
            }

            # Extract from artifact_data (the original log)
            artifact_data = event_data.get("artifact_data", {})
            original_log = event_data.get("original_log", {})
            normalized_log = event_data.get("normalized_log", {})

            # Combine all data sources for IOC extraction
            all_data = {**artifact_data, **original_log, **normalized_log}

            # Extract IP addresses
            for key in ["src_ip", "dst_ip", "client_ip", "remote_ip", "source_ip", "destination_ip"]:
                if key in all_data and all_data[key]:
                    potential_iocs["ip_addresses"].append(all_data[key])

            # Extract domains and URLs
            for key in ["domain", "hostname", "url", "referer", "user_agent"]:
                if key in all_data and all_data[key]:
                    value = str(all_data[key])
                    # Simple domain extraction (can be enhanced)
                    if "." in value and not value.startswith("http"):
                        potential_iocs["domains"].append(value)
                    elif value.startswith("http"):
                        potential_iocs["urls"].append(value)

            # Extract file hashes
            for key in ["file_hash", "md5", "sha1", "sha256", "hash"]:
                if key in all_data and all_data[key]:
                    potential_iocs["file_hashes"].append(all_data[key])

            # Correlate with threat intelligence
            total_matches = 0
            threat_score = 0

            for indicator in threat_indicators:
                indicator_value = indicator.get("value", "").lower()
                indicator_type = indicator.get("indicator_type", "")

                matched = False

                # Check IP addresses
                if indicator_type == "ip" and indicator_value in [ip.lower() for ip in potential_iocs["ip_addresses"]]:
                    matched = True

                # Check domains
                elif indicator_type == "domain" and indicator_value in [domain.lower() for domain in potential_iocs["domains"]]:
                    matched = True

                # Check URLs
                elif indicator_type == "url":
                    for url in potential_iocs["urls"]:
                        if indicator_value in url.lower():
                            matched = True
                            break

                # Check file hashes
                elif indicator_type in ["hash", "md5", "sha1", "sha256"] and indicator_value in [h.lower() for h in potential_iocs["file_hashes"]]:
                    matched = True

                if matched:
                    total_matches += 1
                    confidence = indicator.get("confidence", 50)
                    severity_weight = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(indicator.get("severity", "medium"), 2)

                    match_info = {
                        "indicator_id": indicator.get("id"),
                        "indicator_type": indicator_type,
                        "indicator_value": indicator_value,
                        "threat_type": indicator.get("threat_type", []),
                        "severity": indicator.get("severity", "medium"),
                        "confidence": confidence,
                        "source": indicator.get("source", "unknown"),
                        "description": indicator.get("description"),
                        "first_seen": indicator.get("first_seen"),
                        "last_seen": indicator.get("last_seen")
                    }

                    correlation_results["ioc_matches"].append(match_info)
                    threat_score += severity_weight * (confidence / 100)

                    # Add threat categories
                    for threat_type in indicator.get("threat_type", []):
                        if threat_type not in correlation_results["threat_categories"]:
                            correlation_results["threat_categories"].append(threat_type)

            # Calculate overall threat and confidence scores
            correlation_results["threat_score"] = min(int(threat_score), 100)
            correlation_results["confidence_score"] = min(total_matches * 0.2, 1.0) if total_matches > 0 else 0.0

            # Generate attribution and campaign info (placeholder for future enhancement)
            if total_matches > 0:
                correlation_results["attribution"] = f"Matched {total_matches} threat indicators"
                if "apt" in str(correlation_results["threat_categories"]).lower():
                    correlation_results["related_campaigns"] = ["APT activity detected"]
                elif "ransomware" in str(correlation_results["threat_categories"]).lower():
                    correlation_results["related_campaigns"] = ["Ransomware campaign"]

            logger.debug(f"🕵️ Threat intelligence correlation: {total_matches} matches, score: {threat_score}")
            return correlation_results

        except Exception as e:
            logger.error(f"Error correlating with threat intelligence: {e}")
            return {
                "ioc_matches": [],
                "threat_score": 0,
                "threat_categories": [],
                "related_campaigns": [],
                "attribution": None,
                "confidence_score": 0.0,
                "error": str(e)
            }


    def get_supported_event_types(self) -> List[str]:
        """Support security events and log events for Sigma rule matching"""
        return [
            EVENT_LOGS_NORMALIZED,             # Process normalized logs for Sigma rule matching
            EVENT_SIGMA_RULE_CREATED,          # Sigma rule creation
            EVENT_SIGMA_RULE_UPDATED,          # Sigma rule updates
            EVENT_SIGMA_RULE_DELETED,          # Sigma rule deletion
            EVENT_SIGMA_RULE_ENABLED,          # Sigma rule enablement
            EVENT_SIGMA_RULE_DISABLED,         # Sigma rule disablement
            EVENT_SECURITY_DETECTION_TRIGGERED, # Security detection triggered
            EVENT_SECURITY_DETECTION_RESOLVED,  # Security detection resolved
            EVENT_SECURITY_DETECTION_ACKNOWLEDGED, # Security detection acknowledged
            EVENT_SECURITY_DETECTION_FALSE_POSITIVE # Security detection marked false_positive
        ]

    def get_handler_name(self) -> str:
        """Get handler name"""
        return "security_handler"
