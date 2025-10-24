"""
UI Event Handler - Handles real-time UI events and webhook notifications
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from .base import EventHandler
from ..base import BaseEvent
from ..constants import (
    EVENT_UI_ALERT_TRIGGERED,
    EVENT_UI_ALERT_ACKNOWLEDGED,
    EVENT_UI_ALERT_RESOLVED,
    EVENT_UI_ALERT_COUNT_UPDATED,
    EVENT_UI_RULE_STATUS_CHANGED
)

logger = structlog.get_logger(__name__)


class UIEventHandler(EventHandler):
    """Handler for real-time UI events and webhook notifications"""

    def __init__(self):
        """Initialize UI event handler with webhook management."""
        self._webhook_cache = {}  # Cache for customer webhook configurations
        self._webhook_cache_ttl = {}  # TTL for webhook cache entries
        self.webhook_timeout = 10  # Webhook request timeout in seconds
        self.max_retries = 3  # Maximum webhook delivery retries

    async def handle(self, event: BaseEvent) -> bool:
        """Handle UI events and send webhook notifications"""
        logger.info(
            "Processing UI event",
            event_id=event.metadata.event_id,
            customer_id=event.customer_id,
            event_type=event.event_type
        )

        try:
            event_type = event.event_type
            
            if event_type == EVENT_UI_ALERT_TRIGGERED:
                return await self._handle_alert_triggered_event(event)
            elif event_type == EVENT_UI_ALERT_ACKNOWLEDGED:
                return await self._handle_alert_acknowledged_event(event)
            elif event_type == EVENT_UI_ALERT_RESOLVED:
                return await self._handle_alert_resolved_event(event)
            elif event_type == EVENT_UI_ALERT_COUNT_UPDATED:
                return await self._handle_alert_count_updated_event(event)
            elif event_type == EVENT_UI_RULE_STATUS_CHANGED:
                return await self._handle_rule_status_changed_event(event)
            else:
                logger.info(f"UI event type {event_type} received but not handled")
                return True

        except Exception as e:
            logger.error(f"Error handling UI event {event.event_type}: {e}")
            return False

    async def _handle_alert_triggered_event(self, event: BaseEvent) -> bool:
        """Handle ui.alert.triggered events for real-time notifications"""
        try:
            customer_id = event.customer_id
            event_data = event.data
            
            # Create webhook payload for alert triggered event
            webhook_payload = {
                "event_type": "alert_triggered",
                "timestamp": datetime.utcnow().isoformat(),
                "customer_id": customer_id,
                "alert": {
                    "id": event_data.get("alert_id"),
                    "rule_id": event_data.get("rule_id"),
                    "rule_name": event_data.get("rule_name"),
                    "rule_type": event_data.get("rule_type"),
                    "severity": event_data.get("severity"),
                    "title": event_data.get("title"),
                    "message": event_data.get("message"),
                    "triggered_at": event_data.get("triggered_at"),
                    "status": event_data.get("status"),
                    "trigger_summary": event_data.get("trigger_summary", {}),
                    "ui_metadata": event_data.get("ui_metadata", {})
                }
            }
            
            # Send to customer webhooks
            webhook_results = await self._send_to_customer_webhooks(
                customer_id, 
                webhook_payload, 
                webhook_type="alert"
            )
            
            logger.info(
                "Alert triggered UI event processed",
                customer_id=customer_id,
                alert_id=event_data.get("alert_id"),
                rule_name=event_data.get("rule_name"),
                severity=event_data.get("severity"),
                webhook_results=webhook_results
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling alert triggered UI event: {e}")
            return False

    async def _handle_alert_acknowledged_event(self, event: BaseEvent) -> bool:
        """Handle ui.alert.acknowledged events"""
        try:
            customer_id = event.customer_id
            event_data = event.data
            
            webhook_payload = {
                "event_type": "alert_acknowledged",
                "timestamp": datetime.utcnow().isoformat(),
                "customer_id": customer_id,
                "alert": {
                    "id": event_data.get("alert_id"),
                    "acknowledged_by": event_data.get("acknowledged_by"),
                    "acknowledged_at": event_data.get("acknowledged_at"),
                    "acknowledgment_notes": event_data.get("acknowledgment_notes"),
                    "status": event_data.get("status")
                }
            }
            
            webhook_results = await self._send_to_customer_webhooks(
                customer_id, 
                webhook_payload, 
                webhook_type="alert"
            )
            
            logger.info(
                "Alert acknowledged UI event processed",
                customer_id=customer_id,
                alert_id=event_data.get("alert_id"),
                acknowledged_by=event_data.get("acknowledged_by"),
                webhook_results=webhook_results
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling alert acknowledged UI event: {e}")
            return False

    async def _handle_alert_resolved_event(self, event: BaseEvent) -> bool:
        """Handle ui.alert.resolved events"""
        try:
            customer_id = event.customer_id
            event_data = event.data
            
            webhook_payload = {
                "event_type": "alert_resolved",
                "timestamp": datetime.utcnow().isoformat(),
                "customer_id": customer_id,
                "alert": {
                    "id": event_data.get("alert_id"),
                    "resolved_by": event_data.get("resolved_by"),
                    "resolved_at": event_data.get("resolved_at"),
                    "resolution_notes": event_data.get("resolution_notes"),
                    "status": event_data.get("status")
                }
            }
            
            webhook_results = await self._send_to_customer_webhooks(
                customer_id, 
                webhook_payload, 
                webhook_type="alert"
            )
            
            logger.info(
                "Alert resolved UI event processed",
                customer_id=customer_id,
                alert_id=event_data.get("alert_id"),
                resolved_by=event_data.get("resolved_by"),
                webhook_results=webhook_results
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling alert resolved UI event: {e}")
            return False

    async def _handle_alert_count_updated_event(self, event: BaseEvent) -> bool:
        """Handle ui.alert.count.updated events"""
        try:
            customer_id = event.customer_id
            event_data = event.data
            
            webhook_payload = {
                "event_type": "alert_count_updated",
                "timestamp": datetime.utcnow().isoformat(),
                "customer_id": customer_id,
                "alert_counts": {
                    "total_alerts": event_data.get("total_alerts", 0),
                    "active_alerts": event_data.get("active_alerts", 0),
                    "acknowledged_alerts": event_data.get("acknowledged_alerts", 0),
                    "resolved_alerts": event_data.get("resolved_alerts", 0),
                    "alert_counts": event_data.get("alert_counts", {}),
                    "updated_at": event_data.get("updated_at")
                }
            }
            
            # Send to UI-specific webhooks (lower priority)
            webhook_results = await self._send_to_customer_webhooks(
                customer_id, 
                webhook_payload, 
                webhook_type="ui"
            )
            
            logger.debug(
                "Alert count updated UI event processed",
                customer_id=customer_id,
                total_alerts=event_data.get("total_alerts"),
                webhook_results=webhook_results
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling alert count updated UI event: {e}")
            return False

    async def _handle_rule_status_changed_event(self, event: BaseEvent) -> bool:
        """Handle ui.rule.status.changed events"""
        try:
            customer_id = event.customer_id
            event_data = event.data
            
            webhook_payload = {
                "event_type": "rule_status_changed",
                "timestamp": datetime.utcnow().isoformat(),
                "customer_id": customer_id,
                "rule": {
                    "id": event_data.get("rule_id"),
                    "name": event_data.get("rule_name"),
                    "old_status": event_data.get("old_status"),
                    "new_status": event_data.get("new_status"),
                    "changed_by": event_data.get("changed_by"),
                    "changed_at": event_data.get("changed_at")
                }
            }
            
            webhook_results = await self._send_to_customer_webhooks(
                customer_id, 
                webhook_payload, 
                webhook_type="alert"
            )
            
            logger.info(
                "Rule status changed UI event processed",
                customer_id=customer_id,
                rule_id=event_data.get("rule_id"),
                rule_name=event_data.get("rule_name"),
                old_status=event_data.get("old_status"),
                new_status=event_data.get("new_status"),
                webhook_results=webhook_results
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling rule status changed UI event: {e}")
            return False

    async def _send_to_customer_webhooks(
        self, 
        customer_id: str, 
        payload: Dict[str, Any], 
        webhook_type: str = "alert"
    ) -> Dict[str, Any]:
        """Send webhook payload to customer-configured webhooks"""
        try:
            # Get customer webhook configurations
            webhooks = await self._get_customer_webhooks(customer_id, webhook_type)
            
            if not webhooks:
                logger.debug(f"No {webhook_type} webhooks configured for customer {customer_id}")
                return {"sent": 0, "failed": 0, "webhooks": []}
            
            # Send to all configured webhooks concurrently
            webhook_tasks = [
                self._send_webhook(webhook, payload, customer_id)
                for webhook in webhooks
            ]
            
            results = await asyncio.gather(*webhook_tasks, return_exceptions=True)
            
            # Analyze results
            sent_count = sum(1 for result in results if result is True)
            failed_count = len(results) - sent_count
            
            return {
                "sent": sent_count,
                "failed": failed_count,
                "total_webhooks": len(webhooks),
                "webhooks": [
                    {
                        "url": webhook.get("url", "unknown"),
                        "success": results[i] is True,
                        "error": str(results[i]) if results[i] is not True else None
                    }
                    for i, webhook in enumerate(webhooks)
                ]
            }
            
        except Exception as e:
            logger.error(f"Error sending webhooks to customer {customer_id}: {e}")
            return {"sent": 0, "failed": 0, "error": str(e)}

    async def _get_customer_webhooks(self, customer_id: str, webhook_type: str) -> List[Dict[str, Any]]:
        """Get webhook configurations for a customer (with caching)"""
        try:
            cache_key = f"{customer_id}:{webhook_type}"
            current_time = datetime.utcnow().timestamp()
            
            # Check cache first
            if cache_key in self._webhook_cache:
                cache_time = self._webhook_cache_ttl.get(cache_key, 0)
                if current_time - cache_time < 300:  # 5 minute cache
                    return self._webhook_cache[cache_key]
            
            # TODO: Implement database lookup for customer webhook configurations
            # For now, return example webhook configurations for testing
            webhooks = await self._fetch_customer_webhooks_from_db(customer_id, webhook_type)
            
            # Cache the results
            self._webhook_cache[cache_key] = webhooks
            self._webhook_cache_ttl[cache_key] = current_time
            
            return webhooks
            
        except Exception as e:
            logger.error(f"Error fetching webhooks for customer {customer_id}: {e}")
            return []

    async def _fetch_customer_webhooks_from_db(self, customer_id: str, webhook_type: str) -> List[Dict[str, Any]]:
        """Fetch webhook configurations from database"""
        # TODO: Implement actual database lookup
        # For now, return mock webhook configurations for development/testing
        
        if webhook_type == "alert":
            return [
                {
                    "id": f"webhook_alert_{customer_id}_1",
                    "url": f"https://hooks.example.com/customers/{customer_id}/alerts",
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {customer_id}_alert_token",
                        "X-Webhook-Type": "alert"
                    },
                    "enabled": True,
                    "event_types": ["alert_triggered", "alert_acknowledged", "alert_resolved", "rule_status_changed"]
                }
            ]
        elif webhook_type == "ui":
            return [
                {
                    "id": f"webhook_ui_{customer_id}_1", 
                    "url": f"https://ui.example.com/customers/{customer_id}/updates",
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {customer_id}_ui_token",
                        "X-Webhook-Type": "ui"
                    },
                    "enabled": True,
                    "event_types": ["alert_count_updated"]
                }
            ]
        
        return []

    async def _send_webhook(
        self, 
        webhook_config: Dict[str, Any], 
        payload: Dict[str, Any], 
        customer_id: str
    ) -> bool:
        """Send individual webhook with retries and authentication"""
        webhook_url = webhook_config.get("url")
        webhook_id = webhook_config.get("id", "unknown")
        
        if not webhook_url:
            logger.error(f"No URL configured for webhook {webhook_id}")
            return False
        
        # Check if webhook is enabled
        if not webhook_config.get("enabled", True):
            logger.debug(f"Webhook {webhook_id} is disabled")
            return True  # Don't consider this a failure
        
        # Check if this event type is supported by this webhook
        event_type = payload.get("event_type")
        supported_events = webhook_config.get("event_types", [])
        if supported_events and event_type not in supported_events:
            logger.debug(f"Webhook {webhook_id} doesn't support event type {event_type}")
            return True  # Not a failure
        
        for attempt in range(self.max_retries):
            try:
                headers = webhook_config.get("headers", {})
                method = webhook_config.get("method", "POST").upper()
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.webhook_timeout)) as session:
                    if method == "POST":
                        async with session.post(webhook_url, json=payload, headers=headers) as response:
                            if response.status < 400:
                                logger.debug(
                                    f"Webhook sent successfully",
                                    webhook_id=webhook_id,
                                    customer_id=customer_id,
                                    status_code=response.status,
                                    attempt=attempt + 1
                                )
                                return True
                            else:
                                response_text = await response.text()
                                logger.warning(
                                    f"Webhook failed with HTTP {response.status}",
                                    webhook_id=webhook_id,
                                    customer_id=customer_id,
                                    status_code=response.status,
                                    response_text=response_text[:200],
                                    attempt=attempt + 1
                                )
                    else:
                        logger.error(f"Unsupported webhook method: {method}")
                        return False
                        
            except aiohttp.ClientTimeout:
                logger.warning(
                    f"Webhook timeout (attempt {attempt + 1}/{self.max_retries})",
                    webhook_id=webhook_id,
                    customer_id=customer_id,
                    timeout=self.webhook_timeout
                )
            except Exception as e:
                logger.warning(
                    f"Webhook error (attempt {attempt + 1}/{self.max_retries}): {e}",
                    webhook_id=webhook_id,
                    customer_id=customer_id,
                    error=str(e)
                )
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait_time)
        
        logger.error(
            f"Webhook failed after {self.max_retries} attempts",
            webhook_id=webhook_id,
            customer_id=customer_id,
            webhook_url=webhook_url
        )
        return False