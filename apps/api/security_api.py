"""
M4 Security Analytics API - REST endpoints for SIEM-lite functionality
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Query
from pydantic import BaseModel, Field
import structlog

from security_analytics import (
    SecurityAnalyticsEngine,
    SigmaRule,
    SecurityEvent,
    ThreatIntelIndicator,
    DetectionSeverity,
    DetectionStatus,
    AttackTechnique,
    get_security_analytics_engine
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/security", tags=["security-analytics"])

# Pydantic models for API requests/responses

class SigmaRuleRequest(BaseModel):
    title: str
    description: str
    severity: DetectionSeverity
    author: Optional[str] = "Logforge User"
    tags: Optional[List[str]] = []
    logsource: Dict[str, Any]
    detection: Dict[str, Any]
    attack_techniques: Optional[List[AttackTechnique]] = []
    kill_chain_phases: Optional[List[str]] = []
    references: Optional[List[str]] = []
    falsepositives: Optional[List[str]] = []
    enabled: bool = True

class SigmaRuleResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: DetectionSeverity
    status: str
    author: str
    date: str
    tags: List[str]
    attack_techniques: List[AttackTechnique]
    kill_chain_phases: List[str]
    logsource: Dict[str, Any]
    detection: Dict[str, Any]
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class SecurityEventResponse(BaseModel):
    id: str
    rule_id: str
    rule_title: str
    severity: DetectionSeverity
    status: DetectionStatus
    timestamp: str
    event_data: Dict[str, Any]
    matched_fields: Dict[str, Any]
    attack_techniques: List[AttackTechnique]
    kill_chain_phase: Optional[str] = None
    assigned_to: Optional[str] = None
    investigation_notes: List[str]
    artifacts: List[str]

class ThreatIntelResponse(BaseModel):
    id: str
    indicator_type: str
    value: str
    threat_type: List[str]
    severity: DetectionSeverity
    confidence: int
    source: str
    description: Optional[str] = None
    tags: List[str]
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

class ThreatHuntingRequest(BaseModel):
    time_range: Optional[str] = "24h"  # 1h, 24h, 7d, 30d
    severity_filter: Optional[List[DetectionSeverity]] = None
    rule_ids: Optional[List[str]] = None

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

async def run_background_threat_hunting():
    """Background task to run continuous threat hunting"""
    security_engine = get_security_analytics_engine()
    
    # This would run continuously in a production environment
    # For demo, we'll run it once for all test customers
    test_customers = ["test-customer", "demo-customer", "security-customer"]
    
    for customer_id in test_customers:
        try:
            events = await security_engine.run_threat_hunting(customer_id)
            if events:
                logger.info(f"Background threat hunting found {len(events)} events for customer {customer_id}")
        except Exception as e:
            logger.error(f"Error in background threat hunting for {customer_id}: {e}")

# API Endpoints

@router.get("/health")
async def security_health():
    """Security analytics health check"""
    security_engine = get_security_analytics_engine()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sigma_rules_count": len(security_engine.sigma_rules),
        "threat_intel_count": len(security_engine.threat_intel),
        "security_events_count": len(security_engine.security_events)
    }

@router.get("/dashboard")
async def get_security_dashboard(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    time_range: str = Query("24h", description="Time range: 1h, 24h, 7d, 30d")
) -> SecurityDashboardResponse:
    """Get security dashboard overview"""
    security_engine = get_security_analytics_engine()
    
    # Get recent events
    events = security_engine.get_security_events(customer_id, limit=100)
    
    # Filter by time range
    if time_range == "1h":
        cutoff = datetime.now() - timedelta(hours=1)
    elif time_range == "24h":
        cutoff = datetime.now() - timedelta(days=1)
    elif time_range == "7d":
        cutoff = datetime.now() - timedelta(days=7)
    else:  # 30d
        cutoff = datetime.now() - timedelta(days=30)
    
    recent_events = [e for e in events if datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')) > cutoff]
    
    # Calculate statistics
    events_by_severity = {}
    events_by_technique = {}
    
    for event in recent_events:
        # Count by severity
        severity = event.severity.value
        events_by_severity[severity] = events_by_severity.get(severity, 0) + 1
        
        # Count by attack technique
        for technique in event.attack_techniques:
            tech_name = technique.value
            events_by_technique[tech_name] = events_by_technique.get(tech_name, 0) + 1
    
    # Top rules by event count
    rule_counts = {}
    for event in recent_events:
        rule_counts[event.rule_id] = rule_counts.get(event.rule_id, 0) + 1
    
    top_rules = [
        {"rule_id": rule_id, "rule_title": security_engine.sigma_rules[rule_id].title, "count": count}
        for rule_id, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        if rule_id in security_engine.sigma_rules
    ]
    
    # Threat intel stats
    threat_intel_indicators = security_engine.get_threat_intel_indicators(customer_id)
    threat_intel_stats = {
        "total_indicators": len(threat_intel_indicators),
        "by_type": {},
        "by_severity": {}
    }
    
    for indicator in threat_intel_indicators:
        # By type
        ioc_type = indicator.indicator_type
        threat_intel_stats["by_type"][ioc_type] = threat_intel_stats["by_type"].get(ioc_type, 0) + 1
        
        # By severity
        severity = indicator.severity.value
        threat_intel_stats["by_severity"][severity] = threat_intel_stats["by_severity"].get(severity, 0) + 1
    
    return SecurityDashboardResponse(
        total_events=len(recent_events),
        events_by_severity=events_by_severity,
        events_by_technique=events_by_technique,
        top_rules=top_rules,
        recent_events=[
            SecurityEventResponse(
                id=e.id,
                rule_id=e.rule_id,
                rule_title=e.rule_title,
                severity=e.severity,
                status=e.status,
                timestamp=e.timestamp,
                event_data=e.event_data,
                matched_fields=e.matched_fields,
                attack_techniques=e.attack_techniques,
                kill_chain_phase=e.kill_chain_phase,
                assigned_to=e.assigned_to,
                investigation_notes=e.investigation_notes,
                artifacts=e.artifacts
            ) for e in recent_events[:10]
        ],
        threat_intel_stats=threat_intel_stats
    )

@router.get("/sigma-rules")
async def list_sigma_rules(
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> List[SigmaRuleResponse]:
    """List all Sigma detection rules"""
    security_engine = get_security_analytics_engine()
    rules = security_engine.get_sigma_rules(customer_id)
    
    return [
        SigmaRuleResponse(
            id=rule.id,
            title=rule.title,
            description=rule.description,
            severity=rule.severity,
            status=rule.status,
            author=rule.author,
            date=rule.date,
            tags=rule.tags,
            attack_techniques=rule.attack_techniques,
            kill_chain_phases=rule.kill_chain_phases,
            logsource=rule.logsource,
            detection=rule.detection,
            enabled=rule.enabled,
            created_at=rule.created_at,
            updated_at=rule.updated_at
        ) for rule in rules
    ]

@router.post("/sigma-rules")
async def create_sigma_rule(
    rule_request: SigmaRuleRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, str]:
    """Create a new Sigma detection rule"""
    security_engine = get_security_analytics_engine()
    
    # Generate rule ID
    import uuid
    rule_id = f"custom_{str(uuid.uuid4())[:8]}"
    
    rule = SigmaRule(
        id=rule_id,
        title=rule_request.title,
        description=rule_request.description,
        severity=rule_request.severity,
        author=rule_request.author,
        tags=rule_request.tags,
        logsource=rule_request.logsource,
        detection=rule_request.detection,
        attack_techniques=rule_request.attack_techniques,
        kill_chain_phases=rule_request.kill_chain_phases,
        references=rule_request.references,
        falsepositives=rule_request.falsepositives,
        enabled=rule_request.enabled
    )
    
    rule_id = await security_engine.add_sigma_rule(rule, customer_id)
    
    return {"message": f"Sigma rule created", "rule_id": rule_id}

@router.get("/sigma-rules/{rule_id}")
async def get_sigma_rule(
    rule_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> SigmaRuleResponse:
    """Get a specific Sigma rule"""
    security_engine = get_security_analytics_engine()
    
    if rule_id not in security_engine.sigma_rules:
        raise HTTPException(status_code=404, detail="Sigma rule not found")
    
    rule = security_engine.sigma_rules[rule_id]
    
    return SigmaRuleResponse(
        id=rule.id,
        title=rule.title,
        description=rule.description,
        severity=rule.severity,
        status=rule.status,
        author=rule.author,
        date=rule.date,
        tags=rule.tags,
        attack_techniques=rule.attack_techniques,
        kill_chain_phases=rule.kill_chain_phases,
        logsource=rule.logsource,
        detection=rule.detection,
        enabled=rule.enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at
    )

@router.post("/sigma-rules/{rule_id}/test")
async def test_sigma_rule(
    rule_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, Any]:
    """Test a Sigma rule against recent data"""
    security_engine = get_security_analytics_engine()
    
    if rule_id not in security_engine.sigma_rules:
        raise HTTPException(status_code=404, detail="Sigma rule not found")
    
    event = await security_engine.evaluate_sigma_rule(rule_id, customer_id)
    
    if event:
        # Enrich with threat intelligence
        enriched_event = await security_engine.enrich_with_threat_intel(event)
        
        return {
            "result": "triggered",
            "event": {
                "id": enriched_event.id,
                "severity": enriched_event.severity,
                "matched_fields": enriched_event.matched_fields,
                "source_logs_count": len(enriched_event.source_logs),
                "artifacts": enriched_event.artifacts
            }
        }
    else:
        return {"result": "no_match", "event": None}

@router.get("/events")
async def list_security_events(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    limit: int = Query(50, description="Maximum number of events to return"),
    severity: Optional[DetectionSeverity] = Query(None, description="Filter by severity"),
    status: Optional[DetectionStatus] = Query(None, description="Filter by status")
) -> List[SecurityEventResponse]:
    """List security events"""
    security_engine = get_security_analytics_engine()
    events = security_engine.get_security_events(customer_id, limit)
    
    # Apply filters
    if severity:
        events = [e for e in events if e.severity == severity]
    if status:
        events = [e for e in events if e.status == status]
    
    return [
        SecurityEventResponse(
            id=e.id,
            rule_id=e.rule_id,
            rule_title=e.rule_title,
            severity=e.severity,
            status=e.status,
            timestamp=e.timestamp,
            event_data=e.event_data,
            matched_fields=e.matched_fields,
            attack_techniques=e.attack_techniques,
            kill_chain_phase=e.kill_chain_phase,
            assigned_to=e.assigned_to,
            investigation_notes=e.investigation_notes,
            artifacts=e.artifacts
        ) for e in events
    ]

@router.put("/events/{event_id}/status")
async def update_event_status(
    event_id: str,
    new_status: DetectionStatus,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    assigned_to: Optional[str] = None,
    investigation_note: Optional[str] = None
) -> Dict[str, str]:
    """Update security event status"""
    security_engine = get_security_analytics_engine()
    
    if event_id not in security_engine.security_events:
        raise HTTPException(status_code=404, detail="Security event not found")
    
    event = security_engine.security_events[event_id]
    
    # Verify customer ownership
    if event.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update event
    event.status = new_status
    if assigned_to:
        event.assigned_to = assigned_to
    if investigation_note:
        event.investigation_notes.append(f"[{datetime.now().isoformat()}] {investigation_note}")
    
    return {"message": "Event status updated", "event_id": event_id}

@router.post("/threat-hunting")
async def run_threat_hunting(
    hunt_request: ThreatHuntingRequest,
    background_tasks: BackgroundTasks,
    customer_id: str = Header(..., alias="X-Customer-ID")
) -> Dict[str, Any]:
    """Run threat hunting across all detection rules"""
    security_engine = get_security_analytics_engine()
    
    # Run threat hunting
    events = await security_engine.run_threat_hunting(customer_id)
    
    # Filter events if requested
    if hunt_request.severity_filter:
        events = [e for e in events if e.severity in hunt_request.severity_filter]
    
    if hunt_request.rule_ids:
        events = [e for e in events if e.rule_id in hunt_request.rule_ids]
    
    return {
        "message": "Threat hunting completed",
        "events_found": len(events),
        "events": [
            {
                "id": e.id,
                "rule_title": e.rule_title,
                "severity": e.severity,
                "attack_techniques": [t.value for t in e.attack_techniques],
                "timestamp": e.timestamp
            } for e in events
        ]
    }

@router.get("/threat-intel")
async def list_threat_intel(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    indicator_type: Optional[str] = Query(None, description="Filter by indicator type")
) -> List[ThreatIntelResponse]:
    """List threat intelligence indicators"""
    security_engine = get_security_analytics_engine()
    indicators = security_engine.get_threat_intel_indicators(customer_id)
    
    # Apply filters
    if indicator_type:
        indicators = [i for i in indicators if i.indicator_type == indicator_type]
    
    return [
        ThreatIntelResponse(
            id=i.id,
            indicator_type=i.indicator_type,
            value=i.value,
            threat_type=i.threat_type,
            severity=i.severity,
            confidence=i.confidence,
            source=i.source,
            description=i.description,
            tags=i.tags,
            first_seen=i.first_seen,
            last_seen=i.last_seen
        ) for i in indicators
    ]

@router.post("/background-hunting")
async def start_background_hunting(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Start background threat hunting for all customers"""
    background_tasks.add_task(run_background_threat_hunting)
    return {"message": "Background threat hunting started"}

@router.get("/mitre-attack/techniques")
async def list_attack_techniques() -> Dict[str, Dict[str, str]]:
    """List available MITRE ATT&CK techniques"""
    techniques = {
        # Initial Access
        "T1190": {"name": "Exploit Public-Facing Application", "tactic": "initial-access"},
        "T1078": {"name": "Valid Accounts", "tactic": "initial-access"},
        
        # Execution  
        "T1059": {"name": "Command and Scripting Interpreter", "tactic": "execution"},
        "T1053": {"name": "Scheduled Task/Job", "tactic": "execution"},
        
        # Persistence
        "T1543": {"name": "Create or Modify System Process", "tactic": "persistence"},
        "T1136": {"name": "Create Account", "tactic": "persistence"},
        
        # Privilege Escalation
        "T1068": {"name": "Exploitation for Privilege Escalation", "tactic": "privilege-escalation"},
        "T1055": {"name": "Process Injection", "tactic": "privilege-escalation"},
        
        # Defense Evasion
        "T1562": {"name": "Impair Defenses", "tactic": "defense-evasion"},
        "T1070": {"name": "Indicator Removal", "tactic": "defense-evasion"},
        
        # Credential Access
        "T1110": {"name": "Brute Force", "tactic": "credential-access"},
        "T1003": {"name": "OS Credential Dumping", "tactic": "credential-access"},
        
        # Discovery
        "T1083": {"name": "File and Directory Discovery", "tactic": "discovery"},
        "T1057": {"name": "Process Discovery", "tactic": "discovery"},
        
        # Lateral Movement
        "T1021": {"name": "Remote Services", "tactic": "lateral-movement"},
        "T1570": {"name": "Lateral Tool Transfer", "tactic": "lateral-movement"},
        
        # Collection
        "T1005": {"name": "Data from Local System", "tactic": "collection"},
        "T1039": {"name": "Data from Network", "tactic": "collection"},
        
        # Exfiltration
        "T1041": {"name": "Exfiltration Over C2 Channel", "tactic": "exfiltration"},
        "T1048": {"name": "Exfiltration Over Alternative Protocol", "tactic": "exfiltration"}
    }
    
    return techniques