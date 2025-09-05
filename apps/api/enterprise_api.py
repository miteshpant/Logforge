"""
M7 Enterprise API Router - Enterprise Readiness Endpoints
Provides 22 enterprise endpoints for authentication, RBAC, compliance, and integrations
"""

from fastapi import APIRouter, HTTPException, Header, Query, Depends, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enterprise_engine import EnterpriseEngine, AuthProviderType, MFAType, TenantTier, ComplianceFramework, IntegrationType

# Initialize enterprise engine
enterprise_engine = EnterpriseEngine()

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

@router.post("/auth/oidc/configure")
async def configure_oidc_provider(
    request: OIDCConfigRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Configure OIDC authentication provider"""
    try:
        result = await enterprise_engine.configure_oidc_provider(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/providers")
async def list_auth_providers(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all authentication providers"""
    try:
        result = await enterprise_engine.list_auth_providers(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/api-keys")
async def generate_api_key(
    request: APIKeyRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Generate scoped API key for service integration"""
    try:
        result = await enterprise_engine.generate_api_key(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/api-keys")
async def list_api_keys(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all API keys for tenant"""
    try:
        result = await enterprise_engine.list_api_keys(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/auth/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Revoke an active API key"""
    try:
        result = await enterprise_engine.revoke_api_key(x_customer_id, key_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/mfa/setup")
async def setup_mfa(
    request: MFASetupRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Setup Multi-Factor Authentication for user"""
    try:
        result = await enterprise_engine.setup_mfa(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# RBAC & Permissions Endpoints (4 endpoints)

@router.get("/rbac/roles")
async def list_roles(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all available roles and permissions"""
    try:
        result = await enterprise_engine.list_roles(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rbac/roles")
async def create_custom_role(
    request: CustomRoleRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Create custom role with specific permissions"""
    try:
        result = await enterprise_engine.create_custom_role(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/rbac/users/{user_id}/roles")
async def assign_user_roles(
    user_id: str,
    request: UserRoleAssignment,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Assign roles to user"""
    try:
        result = await enterprise_engine.assign_user_roles(x_customer_id, user_id, request.roles)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rbac/permissions")
async def get_user_permissions(
    request: Request,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get effective permissions for current user"""
    try:
        # Get user ID from authentication context (JWT token)
        user = request.state.user
        x_user_id = user.id
        
        result = await enterprise_engine.get_user_permissions(x_customer_id, x_user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Multi-Tenancy & Compliance Endpoints (6 endpoints)

@router.get("/tenants")
async def list_tenants(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all customer tenants"""
    try:
        result = await enterprise_engine.list_tenants(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tenants")
async def create_tenant(
    request: TenantRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Create new customer tenant"""
    try:
        result = await enterprise_engine.create_tenant(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/tenants/{tenant_id}/settings")
async def update_tenant_settings(
    tenant_id: str,
    request: TenantSettingsUpdate,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Update tenant configuration and settings"""
    try:
        result = await enterprise_engine.update_tenant_settings(x_customer_id, tenant_id, request.dict(exclude_unset=True))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compliance/reports")
async def generate_compliance_report(
    compliance_framework: str = Query(..., description="Compliance framework"),
    period_start: str = Query(..., description="Report period start"),
    period_end: str = Query(..., description="Report period end"),
    sections: List[str] = Query(default=["access_controls", "audit_trail", "data_integrity"], description="Report sections"),
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Generate automated compliance report"""
    try:
        start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
        result = await enterprise_engine.generate_compliance_report(x_customer_id, compliance_framework, start_dt, end_dt, sections)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compliance/legal-hold")
async def create_legal_hold(
    request: LegalHoldRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Create legal hold for data preservation"""
    try:
        result = await enterprise_engine.create_legal_hold(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-logs")
async def get_audit_logs(
    start_time: Optional[str] = Query(None, description="Start time filter"),
    end_time: Optional[str] = Query(None, description="End time filter"),
    user_id: Optional[str] = Query(None, description="User ID filter"),
    action_types: Optional[List[str]] = Query(None, description="Action type filter"),
    x_customer_id: str = Header(..., alias="X-Customer-ID")
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
            
        result = await enterprise_engine.get_audit_logs(x_customer_id, filters)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enterprise Integration Endpoints (3 endpoints)

@router.get("/integrations")
async def list_integrations(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """List all available enterprise integrations"""
    try:
        result = await enterprise_engine.list_integrations(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/integrations/{integration_type}/configure")
async def configure_integration(
    integration_type: str,
    config: Dict[str, Any],
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Configure enterprise integration"""
    try:
        result = await enterprise_engine.configure_integration(x_customer_id, integration_type, config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/integrations/{integration_type}/status")
async def get_integration_health(
    integration_type: str,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Check integration health and connectivity"""
    try:
        result = await enterprise_engine.get_integration_health(x_customer_id, integration_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Administration & Governance Endpoints (3 endpoints)

@router.get("/usage/billing")
async def get_usage_billing(
    period_start: str = Query(..., description="Billing period start"),
    period_end: str = Query(..., description="Billing period end"),
    breakdown: List[str] = Query(default=["storage", "ingestion", "queries", "alerts"], description="Cost breakdown categories"),
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get billing metrics and usage analytics"""
    try:
        start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
        result = await enterprise_engine.get_usage_billing(x_customer_id, start_dt, end_dt, breakdown)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/health")
async def get_enterprise_system_health(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get enterprise system health and diagnostics"""
    try:
        result = await enterprise_engine.get_system_health(x_customer_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/configure")
async def configure_backup_policy(
    request: BackupPolicyRequest,
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Configure backup and disaster recovery policies"""
    try:
        result = await enterprise_engine.configure_backup_policy(x_customer_id, request.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enterprise Metrics & Status Endpoints

@router.get("/metrics")
async def get_enterprise_metrics(
    x_customer_id: str = Header(..., alias="X-Customer-ID")
):
    """Get enterprise-wide metrics and KPIs"""
    try:
        result = await enterprise_engine.get_enterprise_metrics(x_customer_id)
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
        "features": [
            "authentication", "authorization", "rbac", "multi_tenancy", 
            "compliance", "integrations", "governance"
        ],
        "endpoints_count": 22,
        "timestamp": datetime.now().isoformat()
    }