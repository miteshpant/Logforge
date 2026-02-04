"""
Alert management API endpoints - M3 core functionality
"""

import time
import structlog
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

from services.alert_service import AlertService
from tenant_dependencies import MiddlewareTenant

router = APIRouter(prefix="/v1/alerts")

# Initialize alert service
alert_service = AlertService()

def setup_dependencies(alert_engine):
    """Setup dependencies from main app"""
    # The alert service handles the engine internally, so we don't need to inject it
    # This function exists to satisfy the dependency injection system
    pass

class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    filters: Optional[List[Dict[str, Any]]] = None
    notification_channels: Optional[List[str]] = None
    severity: Optional[str] = None

class AlertStatusUpdate(BaseModel):
    notes: Optional[str] = None

# Alert Rules Management

@router.post("/rules")
async def create_alert_rule(rule_request: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Create a new alert rule"""
    try:
        # Add customer ID to rule data
        rule_data = rule_request.copy()
        rule_data["customer_id"] = customer_id
        
        # Use AlertService to create rule
        created_rule = await alert_service.create_alert_rule(rule_data)
        
        return created_rule
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert rule: {str(e)}")

@router.get("/rules")
async def list_alert_rules(
    enabled: Optional[bool] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    customer_id: str = MiddlewareTenant
):
    """List alert rules for the customer"""
    try:
        # Server-side pagination: query only the needed records from DB
        result = await alert_service.list_alert_rules_paginated(
            customer_id, enabled, severity, limit, offset
        )

        return {
            "rules": result["rules"],
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alert rules: {str(e)}")

@router.get("/rules/{rule_id}")
async def get_alert_rule(rule_id: str, customer_id: str = MiddlewareTenant):
    """Get a specific alert rule"""
    try:
        rule = await alert_service.get_alert_rule(rule_id, customer_id)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        return rule
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert rule: {str(e)}")

@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str, 
    update_request: AlertRuleUpdateRequest, 
    customer_id: str = MiddlewareTenant
):
    """Update an existing alert rule"""
    try:
        # Update rule using AlertService
        update_data = {k: v for k, v in update_request.model_dump().items() if v is not None}
        rule = await alert_service.update_alert_rule(rule_id, customer_id, update_data)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        return rule
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert rule: {str(e)}")

@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str, customer_id: str = MiddlewareTenant):
    """Delete an alert rule"""
    try:
        success = await alert_service.delete_alert_rule(rule_id, customer_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        return {
            "status": "deleted",
            "rule_id": rule_id,
            "customer_id": customer_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete alert rule: {str(e)}")

@router.post("/rules/{rule_id}/test")
async def test_alert_rule(rule_id: str, test_data: Optional[Dict[str, Any]] = None, customer_id: str = MiddlewareTenant):
    """Test an alert rule against sample data"""
    try:
        # Test rule using AlertService
        test_result = await alert_service.test_alert_rule(rule_id, customer_id)
        
        return {
            "rule_id": rule_id,
            "would_trigger": test_result.get("would_trigger", False),
            "matched_count": test_result.get("query_result_count", 0),
            "evaluation_time_ms": test_result.get("evaluation_time_ms", 0),
            "sample_matches": test_result.get("sample_matches", []),
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test alert rule: {str(e)}")

# Alert Instance Management

@router.get("")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    customer_id: str = MiddlewareTenant
):
    """List alerts for the customer, optionally filtered by time range"""
    try:
        # Server-side pagination: query only the needed records from DB
        result = await alert_service.list_alert_instances(
            customer_id, status, severity, limit, offset,
            start_time, end_time
        )

        return {
            "alerts": result["alerts"],
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")

@router.get("/stats")
async def alert_engine_stats(customer_id: str = MiddlewareTenant):
    """Get detailed alert engine statistics"""
    try:
        stats = await alert_service.get_alert_stats(customer_id)

        return {
            "rules": {
                "total": stats.get("total_rules", 0),
                "enabled": stats.get("enabled_rules", 0),
                "disabled": stats.get("disabled_rules", 0)
            },
            "alerts": {
                "active": stats.get("active_alerts", 0),
                "acknowledged": stats.get("acknowledged_alerts", 0),
                "resolved": stats.get("resolved_alerts", 0),
                "total_fired": stats.get("total_alerts_fired", 0)
            },
            "notifications": {
                "sent": stats.get("notifications_sent", 0),
                "failed": stats.get("notifications_failed", 0)
            },
            "performance": {
                "avg_evaluation_time_ms": stats.get("avg_evaluation_time_ms", 0),
                "last_evaluation": stats.get("last_evaluation")
            },
            "customer_id": customer_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert engine stats: {str(e)}")

@router.get("/stats/overview")
async def get_alert_overview_stats(
    start_time: str,
    end_time: str,
    customer_id: str = MiddlewareTenant
):
    """
    Get alert statistics grouped by severity and status within a time range

    Returns alert counts grouped by:
    - Severity (critical, high, medium, low)
    - Status (active/triggered, acknowledged, resolved)

    Query params:
    - start_time: ISO format datetime string
    - end_time: ISO format datetime string
    """
    try:
        # Get alert overview statistics
        overview = await alert_service.get_alert_overview_stats(
            customer_id=customer_id,
            start_time=start_time,
            end_time=end_time
        )

        return overview

    except Exception as e:
        logger.error(f"Failed to get alert overview stats: {e}", customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get alert overview stats: {str(e)}")

@router.get("/health")
async def alert_engine_health(customer_id: str = MiddlewareTenant):
    """Get alert engine health and status"""
    try:
        health = await alert_service.get_alert_health()
        
        return {
            "status": health.get("status", "unknown"),
            "active_rules": health.get("active_rules", 0),
            "active_alerts": health.get("active_alerts", 0),
            "last_evaluation": health.get("last_evaluation"),
            "customer_id": customer_id,
            "checked_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert engine health: {str(e)}")

@router.get("/{alert_id}")
async def get_alert(alert_id: str, customer_id: str = MiddlewareTenant):
    """Get a specific alert instance"""
    try:
        alert = await alert_service.get_alert_instance(alert_id, customer_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return alert
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")

@router.get("/rules/{rule_id}/instances")
async def list_alert_instances_by_rule(
    rule_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    customer_id: str = MiddlewareTenant
):
    """Get all alert instances for a specific rule"""
    try:
        # Validate limit parameter
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
        
        # Validate status parameter if provided
        if status and status not in ["active", "triggered", "acknowledged", "resolved", "suppressed"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be one of: active, triggered, acknowledged, resolved, suppressed")
        
        # Get alert instances for the rule
        instances = await alert_service.list_alert_instances_by_rule(rule_id, customer_id, status, limit)
        
        return {
            "rule_id": rule_id,
            "customer_id": customer_id,
            "instances": instances,
            "total": len(instances),
            "status_filter": status,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert instances for rule {rule_id}: {str(e)}")

class BulkUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None
    filter_status: Optional[str] = None

@router.put("/rules/{rule_id}/instances/bulk-update")
async def bulk_update_alert_instances_by_rule(
    rule_id: str,
    update_request: BulkUpdateRequest,
    request: Request,
    customer_id: str = MiddlewareTenant
):
    """Bulk update status of all alert instances for a specific rule"""
    try:
        # Validate status parameter
        valid_statuses = ["triggered", "acknowledged", "resolved"]
        if update_request.status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status: {update_request.status}. Must be one of: {valid_statuses}"
            )
        
        # Validate filter_status parameter if provided
        if update_request.filter_status and update_request.filter_status not in ["active", "triggered", "acknowledged", "resolved"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid filter_status: {update_request.filter_status}. Must be one of: active, triggered, acknowledged, resolved"
            )
        
        # Get user information from JWT token in request state
        user = getattr(request.state, 'user', None)
        user_identifier = user.email if user and user.email else user.id if user else "api-user"
        
        # Perform bulk update
        result = await alert_service.bulk_update_alert_instances_by_rule(
            rule_id=rule_id,
            customer_id=customer_id,
            status=update_request.status,
            notes=update_request.notes,
            filter_status=update_request.filter_status,
            updated_by=user_identifier
        )
        
        return {
            "status": "success",
            "rule_id": rule_id,
            "customer_id": customer_id,
            "updated_count": result["updated_count"],
            "instances_updated": result["instances_updated"],
            "filter_status": result["filter_status"],
            "new_status": result["status"],
            "updated_by": result["updated_by"],
            "notes": update_request.notes,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk update alert instances for rule {rule_id}: {str(e)}")

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    customer_id: str = MiddlewareTenant,
    status_update: Optional[AlertStatusUpdate] = None
):
    """Acknowledge an active alert"""
    try:
        # Get user information from JWT token in request state
        user = getattr(request.state, 'user', None)
        user_identifier = user.email if user and user.email else user.id if user else "api-user"
        
        success = await alert_service.acknowledge_alert(alert_id, customer_id, user_identifier)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "status": "acknowledged",
            "alert_id": alert_id,
            "customer_id": customer_id,
            "acknowledged_by": user_identifier,
            "acknowledged_at": datetime.now(timezone.utc),
            "notes": status_update.notes if status_update else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")

@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: Request,
    customer_id: str = MiddlewareTenant,
    status_update: Optional[AlertStatusUpdate] = None
):
    """Resolve an active or acknowledged alert"""
    try:
        # Get user information from JWT token in request state
        user = getattr(request.state, 'user', None)
        user_identifier = user.email if user and user.email else user.id if user else "api-user"
        
        notes = (status_update.notes if status_update else None) or "Resolved via API"
        success = await alert_service.resolve_alert(
            alert_id,
            customer_id,
            user_identifier,
            notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "status": "resolved",
            "alert_id": alert_id,
            "customer_id": customer_id,
            "resolved_by": user_identifier,
            "resolved_at": datetime.now(timezone.utc),
            "notes": status_update.notes or "Resolved via API"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")

# Notification Channels Management (M3)

@router.get("/notifications/channels")
async def list_notification_channels(customer_id: str = MiddlewareTenant):
    """List notification channels"""
    try:
        channels = await alert_service.list_notification_channels(customer_id)
        
        return {
            "channels": channels,
            "total": len(channels),
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list notification channels: {str(e)}")

@router.post("/notifications/channels")
async def create_notification_channel(channel_request: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Create notification channel"""
    try:
        # Add customer ID to channel data
        channel_data = channel_request.copy()
        channel_data["customer_id"] = customer_id
        
        # Create channel using AlertService
        result = await alert_service.create_notification_channel(channel_data)
        
        return {
            "status": "created",
            "channel": result,
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create notification channel: {str(e)}")

@router.put("/notifications/channels/{channel_id}")
async def update_notification_channel(
    channel_id: str,
    channel_update: Dict[str, Any],
    customer_id: str = MiddlewareTenant
):
    """Update a notification channel (enable/disable, config changes)"""
    try:
        channel_update["customer_id"] = customer_id
        result = await alert_service.update_notification_channel(channel_id, customer_id, channel_update)
        if not result:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return {"status": "updated", "channel_id": channel_id, "customer_id": customer_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update notification channel: {str(e)}")

@router.delete("/notifications/channels/{channel_id}")
async def delete_notification_channel(
    channel_id: str,
    customer_id: str = MiddlewareTenant
):
    """Delete a notification channel"""
    try:
        result = await alert_service.delete_notification_channel(channel_id, customer_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return {"status": "deleted", "channel_id": channel_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete notification channel: {str(e)}")

@router.post("/notifications/channels/{channel_id}/test")
async def test_notification_channel(
    channel_id: str,
    customer_id: str = MiddlewareTenant
):
    """Send a test notification through a channel"""
    try:
        result = await alert_service.test_notification_channel(channel_id, customer_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return {"status": "test_sent", "channel_id": channel_id, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test notification channel: {str(e)}")

# Webhook Integrations (M3)

@router.get("/integrations/webhooks")
async def list_webhooks(customer_id: str = MiddlewareTenant):
    """List webhook integrations"""
    try:
        webhooks = await alert_service.list_webhook_integrations(customer_id)
        
        return {
            "webhooks": webhooks,
            "total": len(webhooks),
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")

@router.post("/integrations/webhooks")
async def create_webhook(webhook_request: Dict[str, Any], customer_id: str = MiddlewareTenant):
    """Create webhook integration"""
    try:
        # Add customer ID to webhook data
        webhook_data = webhook_request.copy()
        webhook_data["customer_id"] = customer_id
        
        # Create webhook using AlertService
        result = await alert_service.create_webhook_integration(webhook_data)
        
        return {
            "status": "created", 
            "webhook": result,
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")


def format_sse_message(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format data as Server-Sent Events message"""
    message = ""
    if event_id:
        message += f"id: {event_id}\n"
    message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data)}\n\n"
    return message


@router.get("/events/stream")
async def stream_alerts(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time alert events"""
    try:
        async def generate_alerts():
            while True:
                try:
                    # Get recent alerts using the existing alert service
                    alerts = await alert_service.list_alert_instances(
                        customer_id=customer_id,
                        status=None
                    )
                    
                    # Filter for recent alerts (last 10 minutes) and limit to 20
                    recent_alerts = [
                        alert for alert in alerts
                        if datetime.fromisoformat(alert.get('created_at', '1970-01-01')) > 
                           datetime.now() - timedelta(minutes=10)
                    ][:20]  # Limit to 20 most recent alerts
                    
                    if recent_alerts:
                        yield format_sse_message("alerts", recent_alerts)
                    
                    await asyncio.sleep(20)  # Update every 20 seconds
                    
                except Exception as e:
                    logger.error("Error streaming alerts", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Alerts streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_alerts(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start alerts stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start alerts stream: {str(e)}")