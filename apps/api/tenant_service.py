"""
Tenant Service Engine
===================
Comprehensive multi-tenant lifecycle management for Logforge platform
"""

import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import structlog

from models import (
    Tenant, TenantCreate, TenantUpdate, TenantResponse, TenantListResponse,
    TenantStatsResponse, TenantUsageResponse, TenantHealthResponse,
    StorageConfig, StorageStatusResponse, TenantQuotas, TenantConfig,
    LegalHoldRequest, TenantType, TenantStatus, StorageBackendType
)

logger = structlog.get_logger()

@dataclass
class StorageCredentials:
    """Encrypted storage credentials"""
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    credentials_encrypted: bool = True

@dataclass
class LegalHold:
    """Legal hold entity"""
    hold_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    case_name: str = ""
    description: str = ""
    start_date: str = ""
    end_date: str = ""
    contact_person: str = ""
    contact_email: str = ""
    data_types: List[str] = field(default_factory=list)
    justification: str = ""
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class TenantService:
    """Core tenant service for multi-tenant lifecycle management"""
    
    def __init__(self):
        # In-memory storage for demo (replace with ClickHouse in production)
        self.tenants: Dict[str, Tenant] = {}
        self.storage_configs: Dict[str, StorageConfig] = {}
        self.tenant_quotas: Dict[str, TenantQuotas] = {}
        self.tenant_configs: Dict[str, TenantConfig] = {}
        self.legal_holds: Dict[str, List[LegalHold]] = {}
        self.usage_stats: Dict[str, Dict[str, Any]] = {}
        
        # Initialize with default tenant for backward compatibility
        self._create_default_tenant()
        
        logger.info("Tenant service initialized")
    
    def _create_default_tenant(self):
        """Create default tenant for backward compatibility"""
        default_tenant = Tenant(
            tenant_id="default",
            name="Default Organization",
            type=TenantType.ENTERPRISE,
            primary_contact_name="System Administrator",
            primary_contact_email="admin@logforge.local",
            industry="Technology",
            status=TenantStatus.ACTIVE
        )
        self.tenants["default"] = default_tenant
        
        # Default configurations
        self.tenant_quotas["default"] = TenantQuotas(
            monthly_log_limit=10000000,
            storage_limit_gb=1000,
            retention_days=90
        )
        
        self.tenant_configs["default"] = TenantConfig(
            timezone="UTC",
            data_residency="US",
            compliance_frameworks=["SOX"],
            encryption_required=True
        )
    
    async def create_tenant(self, tenant_data: TenantCreate) -> Tenant:
        """Create new tenant with UUID generation"""
        tenant_id = str(uuid.uuid4())
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=tenant_data.name,
            type=tenant_data.type,
            address=tenant_data.address or "",
            primary_contact_name=tenant_data.primary_contact_name,
            primary_contact_email=tenant_data.primary_contact_email,
            primary_contact_phone=tenant_data.primary_contact_phone or "",
            industry=tenant_data.industry or "",
            company_size=tenant_data.company_size,
            website=tenant_data.website or "",
            notes=tenant_data.notes or "",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        self.tenants[tenant_id] = tenant
        
        # Initialize default quotas and config
        self.tenant_quotas[tenant_id] = TenantQuotas()
        self.tenant_configs[tenant_id] = TenantConfig()
        self.usage_stats[tenant_id] = {
            "log_count_today": 0,
            "log_count_month": 0,
            "storage_used_gb": 0.0,
            "query_count": 0,
            "api_calls": 0
        }
        
        logger.info("Tenant created", tenant_id=tenant_id, name=tenant_data.name)
        return tenant
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)
    
    async def list_tenants(self, page: int = 1, page_size: int = 50, 
                          status_filter: Optional[TenantStatus] = None,
                          type_filter: Optional[TenantType] = None) -> TenantListResponse:
        """List tenants with pagination and filtering"""
        filtered_tenants = list(self.tenants.values())
        
        # Apply filters
        if status_filter:
            filtered_tenants = [t for t in filtered_tenants if t.status == status_filter]
        if type_filter:
            filtered_tenants = [t for t in filtered_tenants if t.type == type_filter]
        
        # Pagination
        total_count = len(filtered_tenants)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_tenants = filtered_tenants[start_idx:end_idx]
        
        tenant_responses = [
            TenantResponse(
                tenant_id=t.tenant_id,
                name=t.name,
                type=t.type,
                status=t.status,
                primary_contact_name=t.primary_contact_name,
                primary_contact_email=t.primary_contact_email,
                industry=t.industry,
                created_at=t.created_at,
                updated_at=t.updated_at
            ) for t in page_tenants
        ]
        
        return TenantListResponse(
            tenants=tenant_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
    
    async def update_tenant(self, tenant_id: str, updates: TenantUpdate) -> Optional[Tenant]:
        """Update tenant information"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None
        
        # Update fields that are provided
        update_data = updates.dict(exclude_unset=True)
        for field_name, value in update_data.items():
            if hasattr(tenant, field_name):
                setattr(tenant, field_name, value)
        
        tenant.updated_at = datetime.now(timezone.utc)
        
        logger.info("Tenant updated", tenant_id=tenant_id, updates=update_data)
        return tenant
    
    async def decommission_tenant(self, tenant_id: str, reason: str = "", 
                                 data_retention: str = "backup", 
                                 backup_required: bool = True) -> Dict[str, Any]:
        """Securely decommission tenant"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Update status to decommissioned
        tenant.status = TenantStatus.INACTIVE
        tenant.updated_at = datetime.now(timezone.utc)
        
        cleanup_tasks = []
        
        if backup_required and data_retention == "backup":
            cleanup_tasks.append("data_backup_initiated")
        
        if data_retention == "purge":
            cleanup_tasks.extend([
                "logs_purged",
                "storage_cleaned",
                "configurations_removed"
            ])
            # Remove from memory storage
            del self.tenants[tenant_id]
            if tenant_id in self.storage_configs:
                del self.storage_configs[tenant_id]
            if tenant_id in self.tenant_quotas:
                del self.tenant_quotas[tenant_id]
            if tenant_id in self.tenant_configs:
                del self.tenant_configs[tenant_id]
        
        logger.info("Tenant decommissioned", tenant_id=tenant_id, reason=reason)
        
        return {
            "status": "decommissioned",
            "tenant_id": tenant_id,
            "reason": reason,
            "cleanup_tasks": cleanup_tasks,
            "data_retention": data_retention,
            "decommissioned_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def configure_storage(self, tenant_id: str, storage_config: StorageConfig) -> Dict[str, Any]:
        """Configure storage backend for tenant"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Store encrypted credentials (mock encryption for demo)
        self.storage_configs[tenant_id] = storage_config
        
        # Mock storage setup based on backend type
        storage_setup = {
            "status": "configured",
            "tenant_id": tenant_id,
            "backend_type": storage_config.backend_type,
            "region": storage_config.region,
            "bucket_name": storage_config.bucket_name,
            "credentials_encrypted": True,
            "encryption_enabled": storage_config.encryption_enabled,
            "configured_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info("Storage configured", tenant_id=tenant_id, backend=storage_config.backend_type)
        return storage_setup
    
    async def test_storage_connection(self, tenant_id: str) -> Dict[str, Any]:
        """Test storage connectivity"""
        storage_config = self.storage_configs.get(tenant_id)
        if not storage_config:
            raise ValueError(f"No storage configuration for tenant {tenant_id}")
        
        # Mock connection test
        connection_result = {
            "tenant_id": tenant_id,
            "connection_status": "success",
            "backend_type": storage_config.backend_type,
            "latency_ms": 45.2,
            "last_tested": datetime.now(timezone.utc).isoformat(),
            "bucket_accessible": True,
            "write_test": "success",
            "read_test": "success"
        }
        
        logger.info("Storage connection tested", tenant_id=tenant_id, status="success")
        return connection_result
    
    async def get_storage_status(self, tenant_id: str) -> StorageStatusResponse:
        """Get storage status and usage"""
        storage_config = self.storage_configs.get(tenant_id)
        quotas = self.tenant_quotas.get(tenant_id, TenantQuotas())
        usage = self.usage_stats.get(tenant_id, {})
        
        if not storage_config:
            raise ValueError(f"No storage configuration for tenant {tenant_id}")
        
        return StorageStatusResponse(
            tenant_id=tenant_id,
            backend_type=storage_config.backend_type,
            storage_used_gb=usage.get("storage_used_gb", 0.0),
            storage_limit_gb=quotas.storage_limit_gb,
            health_status="healthy",
            connection_status="connected",
            last_backup=datetime.now(timezone.utc)
        )
    
    async def get_tenant_usage(self, tenant_id: str) -> TenantUsageResponse:
        """Get tenant usage and billing data"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        usage = self.usage_stats.get(tenant_id, {})
        
        return TenantUsageResponse(
            tenant_id=tenant_id,
            log_count_today=usage.get("log_count_today", 0),
            log_count_month=usage.get("log_count_month", 0),
            storage_used_gb=usage.get("storage_used_gb", 0.0),
            query_count=usage.get("query_count", 0),
            api_calls=usage.get("api_calls", 0),
            billing_period=f"{datetime.now().strftime('%Y-%m')}"
        )
    
    async def get_tenant_quotas(self, tenant_id: str) -> TenantQuotas:
        """Get tenant quotas"""
        quotas = self.tenant_quotas.get(tenant_id)
        if not quotas:
            raise ValueError(f"No quotas found for tenant {tenant_id}")
        return quotas
    
    async def update_tenant_quotas(self, tenant_id: str, quotas: TenantQuotas) -> TenantQuotas:
        """Update tenant quotas"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        self.tenant_quotas[tenant_id] = quotas
        
        logger.info("Tenant quotas updated", tenant_id=tenant_id, quotas=quotas.dict())
        return quotas
    
    async def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        """Get tenant configuration"""
        config = self.tenant_configs.get(tenant_id)
        if not config:
            raise ValueError(f"No configuration found for tenant {tenant_id}")
        return config
    
    async def update_tenant_config(self, tenant_id: str, config: TenantConfig) -> TenantConfig:
        """Update tenant configuration"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        self.tenant_configs[tenant_id] = config
        
        logger.info("Tenant config updated", tenant_id=tenant_id, config=config.dict())
        return config
    
    async def get_compliance_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get compliance status and reporting"""
        tenant = self.tenants.get(tenant_id)
        config = self.tenant_configs.get(tenant_id, TenantConfig())
        
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Mock compliance scoring
        compliance_data = {
            "tenant_id": tenant_id,
            "compliance_score": 85,
            "frameworks": config.compliance_frameworks,
            "violations": [],
            "last_audit": "2024-08-15T10:00:00Z",
            "next_audit": "2024-11-15T10:00:00Z",
            "controls_validated": 45,
            "controls_total": 50,
            "risk_level": "low"
        }
        
        return compliance_data
    
    async def create_legal_hold(self, tenant_id: str, hold_request: LegalHoldRequest) -> Dict[str, Any]:
        """Create legal hold for data preservation"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        legal_hold = LegalHold(
            tenant_id=tenant_id,
            case_name=hold_request.case_name,
            description=hold_request.description,
            start_date=hold_request.start_date,
            end_date=hold_request.end_date,
            contact_person=hold_request.contact_person,
            contact_email=hold_request.contact_email,
            data_types=hold_request.data_types,
            justification=hold_request.justification
        )
        
        if tenant_id not in self.legal_holds:
            self.legal_holds[tenant_id] = []
        
        self.legal_holds[tenant_id].append(legal_hold)
        
        logger.info("Legal hold created", tenant_id=tenant_id, case_name=hold_request.case_name)
        
        return {
            "hold_id": legal_hold.hold_id,
            "tenant_id": tenant_id,
            "case_name": legal_hold.case_name,
            "status": "active",
            "created_at": legal_hold.created_at.isoformat(),
            "preservation_active": True
        }
    
    async def get_tenant_health(self, tenant_id: str) -> TenantHealthResponse:
        """Get tenant health status"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Mock health metrics
        query_performance = {
            "avg_response_time_ms": 850.0,
            "p95_response_time_ms": 2100.0,
            "success_rate": 99.5,
            "queries_per_minute": 45
        }
        
        return TenantHealthResponse(
            tenant_id=tenant_id,
            status="healthy",
            ingestion_health="healthy",
            storage_health="healthy",
            query_performance=query_performance,
            last_activity=datetime.now(timezone.utc)
        )
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant performance metrics and analytics"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Mock comprehensive metrics
        metrics = {
            "tenant_id": tenant_id,
            "ingestion_rate": {
                "current_eps": 1250,
                "peak_eps": 5500,
                "avg_eps_24h": 2100
            },
            "query_performance": {
                "avg_latency_ms": 450.0,
                "p95_latency_ms": 1200.0,
                "p99_latency_ms": 2800.0,
                "success_rate": 99.2
            },
            "storage_efficiency": {
                "compression_ratio": 4.2,
                "hot_storage_gb": 25.5,
                "warm_storage_gb": 180.2,
                "cold_storage_gb": 850.0
            },
            "error_rates": {
                "ingestion_errors": 0.1,
                "query_errors": 0.3,
                "storage_errors": 0.05
            },
            "sla_compliance": {
                "uptime_percentage": 99.95,
                "query_sla_met": 98.5,
                "ingestion_sla_met": 99.8
            }
        }
        
        return metrics
    
    async def get_tenant_alerts(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant-specific alert configuration"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Mock alert configuration
        alerts_data = {
            "tenant_id": tenant_id,
            "alert_rules": [
                {
                    "rule_id": "rule-001",
                    "name": "High Error Rate",
                    "enabled": True,
                    "severity": "critical"
                },
                {
                    "rule_id": "rule-002", 
                    "name": "Storage Quota Warning",
                    "enabled": True,
                    "severity": "warning"
                }
            ],
            "notification_channels": [
                {
                    "channel_id": "email-001",
                    "type": "email",
                    "enabled": True
                },
                {
                    "channel_id": "slack-001",
                    "type": "slack",
                    "enabled": False
                }
            ],
            "escalation_policies": [
                {
                    "policy_id": "escalation-001",
                    "name": "Critical Incidents",
                    "steps": ["immediate", "15min", "1hour"]
                }
            ]
        }
        
        return alerts_data
    
    async def validate_tenant_uuid(self, tenant_id: str) -> bool:
        """Validate that tenant ID is a valid UUID and exists"""
        if not tenant_id:
            return False
        
        # Allow "default" for backward compatibility
        if tenant_id == "default":
            return True
        
        try:
            # Validate UUID format
            uuid.UUID(tenant_id)
            # Check if tenant exists
            return tenant_id in self.tenants
        except ValueError:
            return False
    
    async def get_tenant_by_uuid_or_default(self, tenant_id: Optional[str] = None) -> str:
        """Get valid tenant UUID or default"""
        if not tenant_id:
            return "default"
        
        if await self.validate_tenant_uuid(tenant_id):
            return tenant_id
        
        logger.warning("Invalid tenant UUID, using default", provided_id=tenant_id)
        return "default"
    
    async def track_usage(self, tenant_id: str, operation: str, count: int = 1):
        """Track tenant usage for billing"""
        if tenant_id not in self.usage_stats:
            self.usage_stats[tenant_id] = {
                "log_count_today": 0,
                "log_count_month": 0,
                "storage_used_gb": 0.0,
                "query_count": 0,
                "api_calls": 0
            }
        
        stats = self.usage_stats[tenant_id]
        
        if operation == "log_ingestion":
            stats["log_count_today"] += count
            stats["log_count_month"] += count
        elif operation == "query":
            stats["query_count"] += count
        elif operation == "api_call":
            stats["api_calls"] += count
        
        stats["api_calls"] += 1  # Every operation is an API call

# Global tenant service instance
tenant_service = TenantService()