"""
M4 Security Analytics API - REST endpoints for SIEM-lite functionality
Updated to use SecurityService/SecurityDAO pattern instead of in-memory storage
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog
import json

from services.security_service import SecurityService, AttackTechnique
from authn_authz_middleware import get_current_user
from models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/security", tags=["security-analytics"])

# Global security service instance
security_service = SecurityService()

# Pydantic models for API requests/responses

class SigmaRuleRequest(BaseModel):
    title: str
    description: str
    severity: str = "medium"  # critical, high, medium, low, info
    author: Optional[str] = "Logforge User"
    tags: Optional[List[str]] = []
    logsource: Dict[str, Any]
    detection: Dict[str, Any]
    attack_techniques: Optional[List[str]] = []  # MITRE ATT&CK technique IDs
    kill_chain_phases: Optional[List[str]] = []
    references: Optional[List[str]] = []
    falsepositives: Optional[List[str]] = []
    enabled: bool = True

class SigmaRuleResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    status: str
    author: str
    date: str
    enabled: bool
    attack_techniques: List[str]
    tags: List[str]

class SecurityEventResponse(BaseModel):
    id: str
    rule_id: str
    rule_title: str
    severity: str
    status: str
    timestamp: str
    event_data: Dict[str, Any]
    matched_fields: Dict[str, Any]
    attack_techniques: List[str]
    kill_chain_phase: Optional[str]
    assigned_to: Optional[str]
    investigation_notes: List[str]
    artifacts: List[str]

class ThreatIntelRequest(BaseModel):
    indicator_type: str  # ip, domain, url, hash, email, file
    value: str
    threat_type: List[str]  # malware, c2, phishing, scanning, etc.
    severity: str = "medium"
    confidence: int = Field(ge=0, le=100)
    source: str
    description: Optional[str] = None
    tags: List[str]

class ThreatIntelResponse(BaseModel):
    id: str
    indicator_type: str
    value: str
    threat_type: List[str]
    severity: str
    confidence: int
    source: str
    description: Optional[str]
    tags: List[str]
    first_seen: str
    last_seen: str

class ThreatHuntingRequest(BaseModel):
    time_range: Optional[str] = "24h"  # 1h, 24h, 7d, 30d
    severity_filter: Optional[List[str]] = None  # critical, high, medium, low
    rule_ids: Optional[List[str]] = None
    description: Optional[str] = "Threat hunting campaign"

# Security Event Status Management Models
class SecurityEventActionRequest(BaseModel):
    notes: Optional[str] = None

class SecurityEventResolveRequest(BaseModel):
    resolution_notes: str

class SecurityEventBulkResolveRequest(BaseModel):
    resolution_notes: str

class SecurityDashboardResponse(BaseModel):
    total_events: int
    events_by_severity: Dict[str, int]
    events_by_technique: Dict[str, int]
    top_rules: List[Dict[str, Any]]
    recent_events: List[SecurityEventResponse]
    threat_intel_stats: Dict[str, Any]

# Utility functions

def get_customer_id(x_customer_id: str = Header(...)) -> str:
    """Extract customer ID from header"""
    if not x_customer_id:
        raise HTTPException(status_code=400, detail="X-Customer-ID header required")
    return x_customer_id

async def execute_threat_hunting_background(campaign_id: str, customer_id: str):
    """Background task to execute threat hunting campaign"""
    try:
        logger.info(f"Starting background execution of campaign {campaign_id} for customer {customer_id}")
        
        success = await security_service.execute_threat_hunting_campaign(campaign_id, customer_id)
        
        if success:
            logger.info(f"Campaign {campaign_id} completed successfully")
        else:
            logger.warning(f"Campaign {campaign_id} failed")
            
    except Exception as e:
        logger.error(f"Error executing campaign {campaign_id} for {customer_id}: {e}")

async def run_background_threat_hunting():
    """Background task to run continuous threat hunting (legacy)"""
    # This would run continuously in a production environment
    # For demo, we'll run it once for all test customers
    test_customers = ["test-customer", "demo-customer", "security-customer"]
    
    for customer_id in test_customers:
        try:
            campaign_data = {
                "customer_id": customer_id,
                "description": "Background threat hunting campaign"
            }
            # Use new async implementation
            campaign_status = await security_service.start_threat_hunting_campaign(campaign_data)
            await security_service.execute_threat_hunting_campaign(
                campaign_status["campaign_id"], 
                customer_id
            )
            logger.info(f"Background threat hunting completed for customer {customer_id}")
        except Exception as e:
            logger.error(f"Error in background threat hunting for {customer_id}: {e}")

# API Endpoints

@router.get("/health")
async def security_health(customer_id: str = Header(..., alias="X-Customer-ID")):
    """Security analytics health check"""
    try:
        # Get counts from database
        rules = await security_service.get_sigma_rules(customer_id)
        events = await security_service.get_security_events(customer_id, limit=1)  # Just for count
        indicators = await security_service.get_threat_indicators(customer_id)
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "sigma_rules_count": len(rules),
            "threat_intel_count": len(indicators),
            "security_events_count": len(events),
            "database_connected": True
        }
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "database_connected": False
        }

@router.get("/dashboard")
async def get_security_dashboard(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    time_range: str = Query("24h", description="Time range: 1h, 24h, 7d, 30d")
) -> SecurityDashboardResponse:
    """Get security dashboard overview"""
    try:
        # Get dashboard data from SecurityService
        dashboard_data = await security_service.get_security_dashboard_data(customer_id)
        
        return SecurityDashboardResponse(
            total_events=dashboard_data["summary"]["total_events"],
            events_by_severity=dashboard_data["events_by_severity"],
            events_by_technique=dashboard_data["attack_techniques"],
            top_rules=dashboard_data["top_triggered_rules"],
            recent_events=[
                SecurityEventResponse(
                    id=e.get("id", ""),
                    rule_id=e.get("rule_id", ""),
                    rule_title=e.get("rule_title", ""),
                    severity=e.get("severity", "medium"),
                    status=e.get("status", "triggered"),
                    timestamp=e.get("timestamp", datetime.now().isoformat()),
                    event_data=e.get("event_data", {}),
                    matched_fields=e.get("matched_fields", {}),
                    attack_techniques=e.get("attack_techniques", []),
                    kill_chain_phase=e.get("kill_chain_phase"),
                    assigned_to=e.get("assigned_to"),
                    investigation_notes=e.get("investigation_notes", []),
                    artifacts=e.get("artifacts", [])
                ) for e in dashboard_data["recent_events"]
            ],
            threat_intel_stats={
                "total_indicators": dashboard_data["summary"]["threat_indicators"],
                "by_type": {},
                "by_severity": {}
            }
        )
    except Exception as e:
        logger.error(f"Failed to get security dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")

@router.get("/sigma-rules")
async def list_sigma_rules(
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> List[SigmaRuleResponse]:
    """List all Sigma detection rules"""
    try:
        rules = await security_service.get_sigma_rules(customer_id)
        
        return [
            SigmaRuleResponse(
                id=rule.get("id", ""),
                title=rule.get("title", ""),
                description=rule.get("description", ""),
                severity=rule.get("severity", "medium"),
                status=rule.get("status", "active"),
                author=rule.get("author", "logforge"),
                date=rule.get("date", ""),
                enabled=rule.get("enabled", True),
                attack_techniques=rule.get("attack_techniques", []),
                tags=rule.get("tags", [])
            ) for rule in rules
        ]
    except Exception as e:
        logger.error(f"Failed to list Sigma rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get rules: {str(e)}")

@router.post("/sigma-rules")
async def create_sigma_rule(
    rule_request: SigmaRuleRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, str]:
    """Create a new Sigma detection rule"""
    try:
        # Convert request to rule data
        rule_data = {
            "title": rule_request.title,
            "description": rule_request.description,
            "severity": rule_request.severity,
            "author": rule_request.author,
            "tags": rule_request.tags,
            "logsource": rule_request.logsource,
            "detection": rule_request.detection,
            "attack_techniques": rule_request.attack_techniques,
            "kill_chain_phases": rule_request.kill_chain_phases,
            "references": rule_request.references,
            "falsepositives": rule_request.falsepositives,
            "enabled": rule_request.enabled,
            "customer_id": customer_id
        }
        
        rule_id = await security_service.create_sigma_rule(rule_data)
        
        return {"message": "Sigma rule created", "rule_id": rule_id}
    except Exception as e:
        logger.error(f"Failed to create Sigma rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create rule: {str(e)}")

@router.get("/sigma-rules/{rule_id}")
async def get_sigma_rule(
    rule_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> SigmaRuleResponse:
    """Get a specific Sigma rule"""
    try:
        rule = await security_service.get_sigma_rule_by_id(rule_id, customer_id)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Sigma rule not found")
        
        return SigmaRuleResponse(
            id=rule.get("id", ""),
            title=rule.get("title", ""),
            description=rule.get("description", ""),
            severity=rule.get("severity", "medium"),
            status=rule.get("status", "active"),
            author=rule.get("author", "logforge"),
            date=rule.get("date", ""),
            enabled=rule.get("enabled", True),
            attack_techniques=rule.get("attack_techniques", []),
            tags=rule.get("tags", [])
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get Sigma rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get rule: {str(e)}")

@router.post("/sigma-rules/{rule_id}/test")
async def test_sigma_rule(
    rule_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, Any]:
    """Test a Sigma rule against sample data"""
    try:
        # Sample test data for rule evaluation
        test_data = {
            "event_type": "login_failed",
            "status_code": 401,
            "src_ip": "192.168.1.100",
            "user": "admin",
            "timestamp": datetime.now().isoformat()
        }
        
        result = await security_service.test_sigma_rule(rule_id, test_data)
        
        return {
            "result": "triggered" if result["matched"] else "no_match",
            "test_details": {
                "rule_id": result["rule_id"],
                "rule_title": result["rule_title"],
                "matched": result["matched"],
                "matched_fields": result["matched_fields"],
                "confidence": result["confidence"],
                "test_timestamp": result["test_timestamp"]
            }
        }
    except Exception as e:
        logger.error(f"Failed to test Sigma rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test rule: {str(e)}")

@router.put("/sigma-rules/{rule_id}")
async def update_sigma_rule(
    rule_id: str,
    rule_request: SigmaRuleRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, str]:
    """Update an existing Sigma detection rule"""
    try:
        # Convert request to rule data
        rule_data = {
            "title": rule_request.title,
            "description": rule_request.description,
            "severity": rule_request.severity,
            "author": rule_request.author,
            "tags": rule_request.tags,
            "logsource": rule_request.logsource,
            "detection": rule_request.detection,
            "attack_techniques": rule_request.attack_techniques,
            "kill_chain_phases": rule_request.kill_chain_phases,
            "references": rule_request.references,
            "falsepositives": rule_request.falsepositives,
            "enabled": rule_request.enabled
        }
        
        success = await security_service.update_sigma_rule(rule_id, rule_data, customer_id)
        
        if success:
            return {"message": "Sigma rule updated", "rule_id": rule_id}
        else:
            raise HTTPException(status_code=404, detail="Sigma rule not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update Sigma rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}")

@router.delete("/sigma-rules/{rule_id}")
async def delete_sigma_rule(
    rule_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, str]:
    """Delete a Sigma detection rule"""
    try:
        success = await security_service.delete_sigma_rule(rule_id, customer_id)
        
        if success:
            return {"message": "Sigma rule deleted", "rule_id": rule_id}
        else:
            raise HTTPException(status_code=404, detail="Sigma rule not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete Sigma rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete rule: {str(e)}")

@router.get("/events")
async def list_security_events(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
) -> List[SecurityEventResponse]:
    """List security events"""
    try:
        events = await security_service.get_security_events(
            customer_id=customer_id,
            limit=limit,
            severity=severity,
            status=status
        )
        
        return [
            SecurityEventResponse(
                id=event.get("id", ""),
                rule_id=event.get("rule_id", ""),
                rule_title=event.get("rule_title", ""),
                severity=event.get("severity", "medium"),
                status=event.get("status", "triggered"),
                timestamp=event.get("timestamp", datetime.now().isoformat()),
                event_data=event.get("event_data", {}),
                matched_fields=event.get("matched_fields", {}),
                attack_techniques=event.get("attack_techniques", []),
                kill_chain_phase=event.get("kill_chain_phase"),
                assigned_to=event.get("assigned_to"),
                investigation_notes=event.get("investigation_notes", []),
                artifacts=event.get("artifacts", [])
            ) for event in events
        ]
    except Exception as e:
        logger.error(f"Failed to list security events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")


# Security Event Status Management Endpoints

@router.post("/{detection_id}/acknowledge")
async def acknowledge_security_event(
    detection_id: str,
    request: SecurityEventActionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Acknowledge security event - assign to user and mark as investigating"""
    try:
        success = await security_service.acknowledge_security_event(
            detection_id=detection_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to acknowledge security event")
        
        return {"message": "Security event acknowledged successfully", "status": "investigating"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to acknowledge security event {detection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge event: {str(e)}")

@router.post("/{detection_id}/investigate")
async def investigate_security_event(
    detection_id: str,
    request: SecurityEventActionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Mark security event as under investigation"""
    try:
        success = await security_service.investigate_security_event(
            detection_id=detection_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update security event")
        
        return {"message": "Security event marked as investigating", "status": "investigating"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to investigate security event {detection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")

@router.post("/{detection_id}/resolve")
async def resolve_security_event(
    detection_id: str,
    request: SecurityEventResolveRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Resolve security event"""
    try:
        success = await security_service.resolve_security_event(
            detection_id=detection_id,
            customer_id=customer_id,
            user_id=current_user.id,
            resolution_notes=request.resolution_notes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to resolve security event")
        
        return {"message": "Security event resolved successfully", "status": "resolved"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resolve security event {detection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve event: {str(e)}")

@router.post("/{detection_id}/false-positive")
async def mark_false_positive(
    detection_id: str,
    request: SecurityEventResolveRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, str]:
    """Mark security event as false positive"""
    try:
        success = await security_service.mark_false_positive(
            detection_id=detection_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.resolution_notes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark as false positive")
        
        return {"message": "Security event marked as false positive", "status": "false_positive"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to mark false positive {detection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark as false positive: {str(e)}")

# Bulk operations for all events from a rule
@router.post("/rules/{rule_id}/acknowledge-all")
async def bulk_acknowledge_by_rule(
    rule_id: str,
    request: SecurityEventActionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Acknowledge all new events for a specific rule"""
    try:
        updated_count = await security_service.bulk_acknowledge_by_rule(
            rule_id=rule_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.notes
        )
        
        return {
            "message": f"Acknowledged {updated_count} security events for rule {rule_id}",
            "updated_count": updated_count,
            "status": "investigating"
        }
    except Exception as e:
        logger.error(f"Failed to bulk acknowledge by rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge events: {str(e)}")

@router.post("/rules/{rule_id}/investigate-all")
async def bulk_investigate_by_rule(
    rule_id: str,
    request: SecurityEventActionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mark all new events for a rule as investigating"""
    try:
        updated_count = await security_service.bulk_acknowledge_by_rule(  # Same as acknowledge
            rule_id=rule_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.notes
        )
        
        return {
            "message": f"Marked {updated_count} security events as investigating for rule {rule_id}",
            "updated_count": updated_count,
            "status": "investigating"
        }
    except Exception as e:
        logger.error(f"Failed to bulk investigate by rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to investigate events: {str(e)}")

@router.post("/rules/{rule_id}/resolve-all")
async def bulk_resolve_by_rule(
    rule_id: str,
    request: SecurityEventBulkResolveRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Resolve all new events for a specific rule"""
    try:
        updated_count = await security_service.bulk_resolve_by_rule(
            rule_id=rule_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.resolution_notes
        )
        
        return {
            "message": f"Resolved {updated_count} security events for rule {rule_id}",
            "updated_count": updated_count,
            "status": "resolved"
        }
    except Exception as e:
        logger.error(f"Failed to bulk resolve by rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve events: {str(e)}")

@router.post("/rules/{rule_id}/false-positive-all")
async def bulk_false_positive_by_rule(
    rule_id: str,
    request: SecurityEventBulkResolveRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Mark all new events for a rule as false positive"""
    try:
        updated_count = await security_service.bulk_false_positive_by_rule(
            rule_id=rule_id,
            customer_id=customer_id,
            user_id=current_user.id,
            notes=request.resolution_notes
        )
        
        return {
            "message": f"Marked {updated_count} security events as false positive for rule {rule_id}",
            "updated_count": updated_count,
            "status": "false_positive"
        }
    except Exception as e:
        logger.error(f"Failed to bulk false positive by rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to mark as false positive: {str(e)}")

# Get events by rule for verification
@router.get("/rules/{rule_id}/events")
async def get_events_by_rule(
    rule_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get events for a specific rule"""
    try:
        events = await security_service.get_events_by_rule(
            rule_id=rule_id,
            customer_id=customer_id,
            status_filter=status,
            limit=limit
        )
        
        return {
            "rule_id": rule_id,
            "events": events,
            "total_count": len(events),
            "status_filter": status
        }
    except Exception as e:
        logger.error(f"Failed to get events by rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")

@router.get("/{detection_id}/status")
async def get_security_event_status(
    detection_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get detailed security event status and investigation history"""
    try:
        event = await security_service.get_security_event_details(detection_id, customer_id)
        
        if not event:
            raise HTTPException(status_code=404, detail="Security event not found")
        
        return {
            "id": event.get("id"),
            "rule_id": event.get("rule_id"),
            "title": event.get("title"),
            "severity": event.get("severity"),
            "status": event.get("status"),
            "created_at": event.get("created_at"),
            "updated_at": event.get("updated_at"),
            "assigned_to": event.get("assigned_to"),
            "investigation_notes": event.get("investigation_notes", []),
            "mitre_techniques": event.get("mitre_techniques", []),
            "raw_log_data": event.get("raw_log_data", {}),
            "enrichment_data": event.get("enrichment_data", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get security event status {detection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get event status: {str(e)}")

@router.post("/threat-hunting")
async def start_threat_hunting(
    request: ThreatHuntingRequest,
    background_tasks: BackgroundTasks,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, Any]:
    """Start threat hunting campaign (returns immediately with campaign ID)"""
    try:
        campaign_data = {
            "customer_id": customer_id,
            "description": request.description,
            "time_range": request.time_range,
            "severity_filter": request.severity_filter,
            "rule_ids": request.rule_ids
        }
        
        # Start campaign (returns immediately)
        campaign_status = await security_service.start_threat_hunting_campaign(campaign_data)
        
        # Schedule background execution
        background_tasks.add_task(
            execute_threat_hunting_background, 
            campaign_status["campaign_id"], 
            customer_id
        )
        
        return campaign_status
    except Exception as e:
        logger.error(f"Failed to start threat hunting: {e}")
        raise HTTPException(status_code=500, detail=f"Threat hunting failed: {str(e)}")

@router.get("/threat-hunting/{campaign_id}")
async def get_threat_hunting_status(
    campaign_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, Any]:
    """Get threat hunting campaign status"""
    try:
        status = await security_service.get_campaign_status(campaign_id, customer_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/threat-hunting")
async def list_threat_hunting_campaigns(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """List customer's threat hunting campaigns"""
    try:
        campaigns = await security_service.get_customer_campaigns(customer_id, limit)
        
        return {
            "campaigns": campaigns,
            "total_count": len(campaigns)
        }
    except Exception as e:
        logger.error(f"Failed to list campaigns: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list campaigns: {str(e)}")

@router.get("/threat-intel")
async def list_threat_intel(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    indicator_type: Optional[str] = Query(None)
) -> List[ThreatIntelResponse]:
    """List threat intelligence indicators"""
    try:
        indicators = await security_service.get_threat_indicators(
            customer_id=customer_id,
            indicator_type=indicator_type
        )
        
        return [
            ThreatIntelResponse(
                id=indicator.get("id", ""),
                indicator_type=indicator.get("indicator_type", ""),
                value=indicator.get("value", ""),
                threat_type=indicator.get("threat_type", []),
                severity=indicator.get("severity", "medium"),
                confidence=indicator.get("confidence", 50),
                source=indicator.get("source", ""),
                description=indicator.get("description"),
                tags=indicator.get("tags", []),
                first_seen=indicator.get("first_seen", datetime.now().isoformat()),
                last_seen=indicator.get("last_seen", datetime.now().isoformat())
            ) for indicator in indicators
        ]
    except Exception as e:
        logger.error(f"Failed to list threat intelligence: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get indicators: {str(e)}")

@router.post("/background-hunting")
async def trigger_background_hunting(
    background_tasks: BackgroundTasks,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, str]:
    """Trigger background threat hunting"""
    try:
        background_tasks.add_task(run_background_threat_hunting)
        return {"message": "Background threat hunting triggered", "status": "scheduled"}
    except Exception as e:
        logger.error(f"Failed to trigger background hunting: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger hunting: {str(e)}")

@router.get("/mitre-attack/techniques")
async def list_mitre_techniques() -> Dict[str, Any]:
    """List MITRE ATT&CK techniques"""
    try:
        # Return available MITRE ATT&CK techniques from our enum
        techniques = []
        for technique in AttackTechnique:
            techniques.append({
                "id": technique.value,
                "name": technique.name,
                "description": f"MITRE ATT&CK Technique {technique.value}"
            })
        
        return {
            "techniques": techniques,
            "total_count": len(techniques),
            "framework_version": "v12.0"
        }
    except Exception as e:
        logger.error(f"Failed to list MITRE techniques: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get techniques: {str(e)}")


def format_sse_message(event_type: str, data: Any, event_id: Optional[str] = None) -> str:
    """Format data as Server-Sent Events message"""
    message = ""
    if event_id:
        message += f"id: {event_id}\n"
    message += f"event: {event_type}\n"
    message += f"data: {json.dumps(data)}\n\n"
    return message


@router.get("/events/stream")
async def stream_security_events(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Stream real-time security events"""
    try:
        async def generate_security_events():
            while True:
                try:
                    # Get recent security events
                    events = await security_service.get_security_events(
                        customer_id=customer_id,
                        limit=20,
                        status_filter=None
                    )
                    
                    # Filter for recent events (last 5 minutes)
                    recent_events = [
                        event for event in events
                        if datetime.fromisoformat(event.get('timestamp', '1970-01-01')) > 
                           datetime.now() - timedelta(minutes=5)
                    ]
                    
                    if recent_events:
                        yield format_sse_message("security_events", recent_events)
                    
                    await asyncio.sleep(15)  # Update every 15 seconds
                    
                except Exception as e:
                    logger.error("Error streaming security events", error=str(e), customer_id=customer_id)
                    yield format_sse_message("error", {"message": f"Security events streaming error: {str(e)}"})
                    break
        
        return StreamingResponse(
            generate_security_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, X-Customer-ID"
            }
        )
        
    except Exception as e:
        logger.error("Failed to start security events stream", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start security events stream: {str(e)}")


# Threat Hunting Rules Discovery Endpoint
@router.get("/threat-hunt/rules")
async def get_threat_hunt_rules(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get available threat hunting rules with pricing for customer"""
    try:
        # TODO: Get customer tier from user/tenant data - for now default to 'smb'
        customer_tier = "smb"  
        
        result = await security_service.get_threat_hunt_rules_with_pricing(
            customer_id=customer_id,
            customer_tier=customer_tier
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get threat hunt rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get threat hunt rules: {str(e)}")

# Initialize default security content on startup
@router.on_event("startup")
async def initialize_security_content():
    """Initialize default Sigma rules and threat intelligence"""
    try:
        await security_service.load_default_security_content("default")
        logger.info("Default security content initialized")
    except Exception as e:
        logger.error(f"Failed to initialize default security content: {e}")