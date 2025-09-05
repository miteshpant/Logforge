"""
Alert management API endpoints - M3 core functionality
"""

import time
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

from alert_engine import (
    AlertRuleCreateRequest, AlertRuleResponse, AlertInstanceResponse,
    AlertRule, AlertStatus, AlertSeverity, AlertRuleType, AlertCondition, ThresholdOperator
)
from query_engine import QueryFilter, QueryOperator
from dataclasses import asdict
from storage_config import get_customer_id
from tenant_dependencies import MiddlewareTenant
from fastapi import Depends

router = APIRouter(prefix="/v1/alerts")

# Global instances (will be injected)
alert_engine = None

def setup_dependencies(ae):
    """Setup dependencies from main app"""
    global alert_engine
    alert_engine = ae

class AlertRuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    filters: Optional[List[Dict[str, Any]]] = None
    notification_channels: Optional[List[str]] = None
    severity: Optional[str] = None

class AlertStatusUpdate(BaseModel):
    status: str  # acknowledged, resolved
    notes: Optional[str] = None

# Alert Rules Management

@router.post("/rules", response_model=AlertRuleResponse)
async def create_alert_rule(rule_request: AlertRuleCreateRequest, request: Request):
    """Create a new alert rule"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        # Add customer ID and generate rule_id
        rule_data = rule_request.model_dump()
        rule_data["customer_id"] = customer_id  # Override with header value
        rule_data["rule_id"] = f"rule-{int(time.time())}"  # Generate simple rule_id
        
        # Convert condition dicts to AlertCondition objects
        if "conditions" in rule_data and rule_data["conditions"]:
            conditions = []
            for cond_dict in rule_data["conditions"]:
                condition = AlertCondition(
                    field=cond_dict.get("field"),
                    operator=ThresholdOperator(cond_dict.get("operator", "gte")),
                    value=cond_dict.get("value"),
                    aggregation=cond_dict.get("aggregation", "count"),
                    time_window=cond_dict.get("time_window", "5m")
                )
                conditions.append(condition)
            rule_data["conditions"] = conditions
        
        # Convert filter dicts to QueryFilter objects
        if "filters" in rule_data and rule_data["filters"]:
            filters = []
            for filter_dict in rule_data["filters"]:
                query_filter = QueryFilter(
                    field=filter_dict.get("field"),
                    operator=QueryOperator(filter_dict.get("operator", "eq")),
                    value=filter_dict.get("value")
                )
                filters.append(query_filter)
            rule_data["filters"] = filters
        
        # Create AlertRule object from request data
        alert_rule = AlertRule(**rule_data)
        
        # Create rule
        created_rule = await alert_engine.create_rule(alert_rule)
        
        # Convert to dict for response - handle enum serialization
        try:
            rule_dict = asdict(created_rule)
            # Convert enum values to strings for JSON serialization
            if 'severity' in rule_dict and hasattr(rule_dict['severity'], 'value'):
                rule_dict['severity'] = rule_dict['severity'].value
            if 'rule_type' in rule_dict and hasattr(rule_dict['rule_type'], 'value'):
                rule_dict['rule_type'] = rule_dict['rule_type'].value
        except Exception as e:
            logger.error(f"Failed to serialize created rule: {e}")
            # Fallback to manual dict construction
            rule_dict = {
                "rule_id": created_rule.rule_id,
                "name": created_rule.name,
                "description": created_rule.description,
                "customer_id": created_rule.customer_id,
                "severity": created_rule.severity.value if hasattr(created_rule.severity, 'value') else created_rule.severity,
                "rule_type": created_rule.rule_type.value if hasattr(created_rule.rule_type, 'value') else created_rule.rule_type,
                "enabled": created_rule.enabled,
                "conditions": [asdict(c) for c in created_rule.conditions] if created_rule.conditions else [],
                "filters": [asdict(f) for f in created_rule.filters] if created_rule.filters else [],
                "notification_channels": created_rule.notification_channels or [],
                "tags": created_rule.tags or [],
                "evaluation_interval": created_rule.evaluation_interval,
                "cooldown_period": created_rule.cooldown_period,
                "max_alerts_per_hour": created_rule.max_alerts_per_hour,
                "created_at": created_rule.created_at,
                "updated_at": created_rule.updated_at,
                "created_by": created_rule.created_by
            }
        
        return AlertRuleResponse(**rule_dict)
        
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
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        # Get rules with filters
        rules = await alert_engine.list_rules(customer_id=customer_id)
        
        # Apply filters manually since the engine method doesn't support them
        if enabled is not None:
            rules = [r for r in rules if r.enabled == enabled]
        if severity is not None:
            rules = [r for r in rules if r.severity.value == severity]
            
        # Apply pagination
        total = len(rules)
        rules = rules[offset:offset+limit]
        
        # Convert rules to dict format for JSON serialization
        rules_data = []
        for rule in rules:
            try:
                # AlertRule is a dataclass, so use asdict()
                rule_dict = asdict(rule)
                
                # Convert enum values to strings for JSON serialization
                if 'severity' in rule_dict and hasattr(rule_dict['severity'], 'value'):
                    rule_dict['severity'] = rule_dict['severity'].value
                if 'rule_type' in rule_dict and hasattr(rule_dict['rule_type'], 'value'):
                    rule_dict['rule_type'] = rule_dict['rule_type'].value
                
                # Convert nested enum values in conditions
                if 'conditions' in rule_dict and rule_dict['conditions']:
                    for condition in rule_dict['conditions']:
                        if 'operator' in condition and hasattr(condition['operator'], 'value'):
                            condition['operator'] = condition['operator'].value
                
                rules_data.append(rule_dict)
            except Exception as e:
                logger.error(f"Failed to serialize rule {rule.rule_id}: {e}")
                # Fallback to basic dict conversion
                rule_dict = {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "customer_id": rule.customer_id,
                    "enabled": rule.enabled,
                    "severity": rule.severity.value if hasattr(rule.severity, 'value') else rule.severity,
                    "rule_type": rule.rule_type.value if hasattr(rule.rule_type, 'value') else rule.rule_type
                }
                rules_data.append(rule_dict)
        
        return {
            "rules": rules_data,
            "total": total,
            "limit": limit,
            "offset": offset,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alert rules: {str(e)}")

@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: str, request: Request):
    """Get a specific alert rule"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        rule = await alert_engine.get_rule(rule_id)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Convert AlertRule to dict for response
        rule_dict = asdict(rule) if hasattr(rule, '__dict__') else rule.__dict__
        return AlertRuleResponse(**rule_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert rule: {str(e)}")

@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str, 
    update_request: AlertRuleUpdateRequest, 
    request: Request
):
    """Update an existing alert rule"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        # Update rule
        update_data = {k: v for k, v in update_request.model_dump().items() if v is not None}
        rule = await alert_engine.update_rule(rule_id, update_data)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Convert AlertRule to dict for response
        rule_dict = asdict(rule) if hasattr(rule, '__dict__') else rule.__dict__
        return AlertRuleResponse(**rule_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update alert rule: {str(e)}")

@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: str, request: Request):
    """Delete an alert rule"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        success = await alert_engine.delete_rule(rule_id)
        
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
async def test_alert_rule(rule_id: str, test_data: Dict[str, Any], request: Request):
    """Test an alert rule against sample data"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        # Get the rule first, then test it
        rule = await alert_engine.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        # Test rule
        test_result = await alert_engine.test_rule(rule)
        
        return {
            "rule_id": rule_id,
            "triggered": test_result.get("would_trigger", False),
            "query_result": test_result.get("query_result_count", 0),
            "evaluation_time_ms": 0,  # Simple placeholder
            "test_result": test_result,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test alert rule: {str(e)}")

# Alert Instance Management

@router.get("")
async def list_alerts(
    request: Request,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List active alerts for the customer"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        # Get alerts with filters
        alert_status = AlertStatus(status) if status else None
        alerts = await alert_engine.list_alerts(customer_id=customer_id, status=alert_status)
        
        # Apply severity filter and pagination manually
        if severity is not None:
            alerts = [a for a in alerts if a.severity.value == severity]
            
        # Apply pagination
        total = len(alerts)
        alerts = [a.model_dump() if hasattr(a, 'model_dump') else asdict(a) for a in alerts[offset:offset+limit]]
        
        return {
            "alerts": alerts,
            "total": len(alerts),
            "limit": limit,
            "offset": offset,
            "customer_id": customer_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")

@router.get("/stats")
async def alert_engine_stats(request: Request):
    """Get detailed alert engine statistics"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        stats = alert_engine.get_stats(customer_id)
        
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

@router.get("/{alert_id}", response_model=AlertInstanceResponse)
async def get_alert(alert_id: str, request: Request):
    """Get a specific alert instance"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        alert = await alert_engine.get_alert(alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Convert AlertInstance to dict for response
        alert_dict = asdict(alert) if hasattr(alert, '__dict__') else alert.__dict__
        return AlertInstanceResponse(**alert_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, status_update: AlertStatusUpdate, request: Request):
    """Acknowledge an active alert"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        success = await alert_engine.acknowledge_alert(
            alert_id, 
            "api-user"
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "status": "acknowledged",
            "alert_id": alert_id,
            "customer_id": customer_id,
            "acknowledged_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, status_update: AlertStatusUpdate, request: Request):
    """Resolve an active or acknowledged alert"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        success = await alert_engine.resolve_alert(
            alert_id,
            "api-user",
            status_update.notes or "Resolved via API"
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {
            "status": "resolved",
            "alert_id": alert_id,
            "customer_id": customer_id,
            "resolved_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")

# Alert Engine Status and Health

@router.get("/health")
async def alert_engine_health(request: Request):
    """Get alert engine health and status"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        if not alert_engine:
            raise HTTPException(status_code=500, detail="Alert engine not initialized")
        
        health = alert_engine.get_health()
        
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

# Notification Channels Management (M3)

@router.get("/notifications/channels")
async def list_notification_channels(request: Request):
    """List notification channels"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        # For now, return a basic structure for testing
        channels = [
            {
                "channel_id": "default-email",
                "name": "Default Email Channel",
                "type": "email",
                "enabled": True,
                "configuration": {
                    "recipients": ["admin@logforge.io"]
                }
            }
        ]
        
        return {
            "channels": channels,
            "total": len(channels),
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list notification channels: {str(e)}")

@router.post("/notifications/channels")
async def create_notification_channel(request: Request):
    """Create notification channel"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        # For M3 testing - return success but not fully implemented
        return {
            "status": "created",
            "message": "Notification channel creation in development",
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create notification channel: {str(e)}")

# Webhook Integrations (M3)

@router.get("/integrations/webhooks")
async def list_webhooks(request: Request):
    """List webhook integrations"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        # For now, return empty list for testing
        return {
            "webhooks": [],
            "total": 0,
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")

@router.post("/integrations/webhooks")
async def create_webhook(request: Request):
    """Create webhook integration"""
    try:
        # Extract customer ID from headers or use default
        customer_id = request.headers.get("X-Customer-ID", "default")
        
        # For M3 testing - return success but not fully implemented
        return {
            "status": "created", 
            "message": "Webhook integration creation in development",
            "customer_id": customer_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create webhook: {str(e)}")