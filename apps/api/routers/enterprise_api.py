"""
M7 Enterprise API Router - Enterprise Readiness Endpoints
Provides 22 enterprise endpoints for authentication, RBAC, compliance, and integrations
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Header
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from services.enterprise_service import EnterpriseService
from authn_authz_middleware import get_current_user

# Create router
router = APIRouter(prefix="/v1/enterprise", tags=["enterprise"])

# Pydantic Models for Request/Response Validation

# Authentication Models
class OIDCConfigRequest(BaseModel):
    provider_name: str = Field(..., description="Name of the OIDC provider")
    provider_type: str = Field(..., description="Type of provider (auth0, keycloak, etc.)")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: Optional[str] = Field(None, description="OAuth client secret")
    domain: str = Field(..., description="Provider domain")
    scopes: List[str] = Field(default=["openid", "profile", "email"], description="OAuth scopes")
    enabled: bool = Field(default=True, description="Enable this provider")

class APIKeyRequest(BaseModel):
    name: str = Field(..., description="API key name")
    description: str = Field(default="", description="API key description")
    permissions: List[str] = Field(..., description="Scoped permissions")
    expires_at: Optional[str] = Field(None, description="Expiration datetime ISO string")
    rate_limit: Optional[int] = Field(None, description="Rate limit per hour")
    ip_whitelist: Optional[List[str]] = Field(None, description="IP whitelist")

class MFASetupRequest(BaseModel):
    user_id: str = Field(..., description="User ID for MFA setup")
    mfa_type: str = Field(..., description="MFA type (totp, sms, hardware)")
    backup_codes: bool = Field(default=True, description="Generate backup codes")
    phone_number: Optional[str] = Field(None, description="Phone number for SMS")

# RBAC Models
class CustomRoleRequest(BaseModel):
    name: str = Field(..., description="Role name")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="List of permissions")
    inherits_from: Optional[str] = Field(None, description="Parent role for inheritance")

class UserRoleAssignment(BaseModel):
    roles: List[str] = Field(..., description="List of role names to assign")
    effective_date: Optional[str] = Field(None, description="When roles take effect")

# Multi-Tenancy Models
class TenantRequest(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant display name")
    tier: str = Field(default="professional", description="Service tier")
    data_residency: str = Field(..., description="Geographic data location")
    compliance_requirements: List[str] = Field(default=[], description="Required compliance frameworks")
    retention_policy: Optional[Dict[str, int]] = Field(None, description="Data retention policies")
    resource_limits: Optional[Dict[str, Any]] = Field(None, description="Resource quotas and limits")

class TenantSettingsUpdate(BaseModel):
    data_residency: Optional[str] = Field(None, description="Data residency location")
    compliance_requirements: Optional[List[str]] = Field(None, description="Compliance frameworks")
    retention_policy: Optional[Dict[str, int]] = Field(None, description="Retention settings")
    security_settings: Optional[Dict[str, Any]] = Field(None, description="Security configuration")

class LegalHoldRequest(BaseModel):
    case_id: str = Field(..., description="Legal case identifier")
    custodian: str = Field(..., description="Legal custodian email")
    reason: str = Field(..., description="Reason for legal hold")
    date_range: Dict[str, str] = Field(..., description="Date range for preservation")
    scope: Dict[str, Any] = Field(..., description="Data scope and filters")

# Integration Models
class IntegrationConfig(BaseModel):
    """Base model for integration configuration - specific fields vary by type"""
    enabled: bool = Field(default=True, description="Enable this integration")
    notification_types: Optional[List[str]] = Field(None, description="Types of notifications")

class SlackIntegrationConfig(IntegrationConfig):
    webhook_url: str = Field(..., description="Slack webhook URL")
    channel: str = Field(..., description="Default Slack channel")
    bot_token: str = Field(..., description="Slack bot token")

# Administration Models  
class BackupPolicyRequest(BaseModel):
    policy_name: str = Field(..., description="Backup policy name")
    schedule: str = Field(..., description="Backup schedule (hourly, daily, weekly)")
    retention_days: int = Field(..., description="Backup retention period")
    storage_location: str = Field(..., description="Backup storage location")
    encryption: bool = Field(default=True, description="Enable encryption")
    compression: bool = Field(default=True, description="Enable compression")
    components: List[str] = Field(..., description="Components to backup")
    disaster_recovery: Dict[str, Any] = Field(..., description="DR configuration")

# Authentication & Authorization Endpoints (6 endpoints)

@router.post("/auth/api-keys")
async def generate_api_key(
    request: APIKeyRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Generate scoped API key with service account"""
    try:
        enterprise_service = EnterpriseService()
        # Pass current user ID as created_by
        result = await enterprise_service.generate_api_key(
            customer_id,
            request.model_dump(),
            created_by_user_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/api-keys")
async def list_api_keys(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all API keys for tenant"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.list_api_keys(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Revoke an active API key"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.revoke_api_key(customer_id, key_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tenants")
async def list_tenants(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all customer tenants"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.list_tenants(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tenants")
async def create_tenant(
    request: TenantRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Create new customer tenant"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.create_tenant(customer_id, request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/tenants/{tenant_id}/settings")
async def update_tenant_settings(
    tenant_id: str,
    request: TenantSettingsUpdate,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Update tenant configuration and settings"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.update_tenant_settings(customer_id, tenant_id, request.model_dump(exclude_unset=True))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Frameworks EnterpriseService.generate_compliance_report() implements.
SUPPORTED_COMPLIANCE_FRAMEWORKS = ("sox", "gdpr", "pci_dss", "hipaa")


@router.get("/compliance/reports")
async def generate_compliance_report(
    compliance_framework: str = Query(..., description="Compliance framework"),
    period_start: str = Query(..., description="Report period start"),
    period_end: str = Query(..., description="Report period end"),
    sections: List[str] = Query(default=["access_controls", "audit_trail", "data_integrity"], description="Report sections"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Generate a compliance report for one framework.

    `compliance_framework` is one of sox, gdpr, pci_dss or hipaa
    (case-insensitive). Unsupported frameworks and malformed or inverted
    periods return 400.
    """
    # Bad input is a 400, not a 500: the UI used to send "SOC2", get a 500,
    # and show an empty Frameworks tab.
    if compliance_framework.lower() not in SUPPORTED_COMPLIANCE_FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=(f"Unsupported compliance framework: {compliance_framework}. "
                    f"Supported: {', '.join(SUPPORTED_COMPLIANCE_FRAMEWORKS)}"),
        )
    try:
        start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="period_start and period_end must be ISO-8601 timestamps")
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail="period_end must be after period_start")
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.generate_compliance_report(customer_id, compliance_framework, start_dt, end_dt, sections)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compliance/retention-policies")
async def get_retention_policies(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get data retention policies for tenant"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_retention_policies(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compliance/legal-holds")
async def get_legal_holds(
    status: Optional[str] = Query(None, description="Filter by status: active, released"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get all legal holds for tenant"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_legal_holds(customer_id, status)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compliance/legal-hold")
async def create_legal_hold(
    request: LegalHoldRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Create legal hold for data preservation"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.create_legal_hold(customer_id, request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-logs")
async def get_audit_logs(
    start_time: Optional[str] = Query(None, description="Start time filter"),
    end_time: Optional[str] = Query(None, description="End time filter"),
    user_id: Optional[str] = Query(None, description="User ID filter"),
    action_types: Optional[List[str]] = Query(None, description="Action type filter"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Retrieve audit logs with filtering"""
    try:
        filters = {}
        if start_time:
            filters["start_time"] = start_time
        if end_time:
            filters["end_time"] = end_time
        if user_id:
            filters["user_id"] = user_id
        if action_types:
            filters["action_types"] = action_types
            
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_audit_logs(customer_id, filters)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enterprise Integration Endpoints (3 endpoints)

@router.get("/usage/billing")
async def get_usage_billing(
    period_start: str = Query(..., description="Billing period start"),
    period_end: str = Query(..., description="Billing period end"),
    breakdown: List[str] = Query(default=["storage", "ingestion", "queries", "alerts"], description="Cost breakdown categories"),
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get billing metrics and usage analytics"""
    try:
        start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_usage_billing(customer_id, start_dt, end_dt, breakdown)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/health")
async def get_enterprise_system_health(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get enterprise system health and diagnostics"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_system_health(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/configure")
async def configure_backup_policy(
    request: BackupPolicyRequest,
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Configure backup and disaster recovery policies"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.configure_backup_policy(customer_id, request.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enterprise Metrics & Status Endpoints

@router.get("/metrics")
async def get_enterprise_metrics(
    customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get enterprise-wide metrics and KPIs"""
    try:
        enterprise_service = EnterpriseService()
        result = await enterprise_service.get_enterprise_metrics(customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@router.get("/health")
async def enterprise_health():
    """Enterprise module health check"""
    return {
        "status": "healthy",
        "module": "enterprise",
        "version": "1.0.0",
        "features": ["api_keys", "multi_tenancy", "compliance", "governance"],
        "endpoints_count": sum(1 for r in router.routes if getattr(r, "include_in_schema", True)),
        "timestamp": datetime.now().isoformat()
    }


# -- retired routes ---------------------------------------------------------------------
# The Enterprise RBAC, OIDC-config, MFA-setup and integrations routes are superseded.
# They answer 410 Gone with their successor, and are left out of the API spec.

_RETIRED = {
    "auth/oidc/configure": "/v1/sso/providers",
    "auth/providers": "/v1/sso/providers",
    "auth/mfa/setup": "/v1/auth/mfa (setup, confirm, delete)",
    "rbac/users/{user_id}/roles": "/v1/users/{user_id}/roles",
    "rbac/permissions": "/v1/auth/access",
    "rbac/roles": "/v1/roles/custom",
    "rbac/roles/{role_id}": "/v1/roles/custom/{id}",
    "integrations": "/v1/integrations",
    "integrations/{rest:path}": "/v1/integrations",
}


def _retired(successor: str):
    async def gone():
        raise HTTPException(status_code=410, detail=f"This route was retired; use {successor}")
    return gone


for _path, _successor in _RETIRED.items():
    router.add_api_route(f"/{_path}", _retired(_successor), methods=["GET", "POST", "PUT", "DELETE"],
                         include_in_schema=False, status_code=410)

