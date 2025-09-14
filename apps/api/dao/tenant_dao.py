"""
Tenant Data Access Object (DAO)
Handles all database operations for tenant management
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog

from database_layer import DatabaseLayer
from constants.database_constants import (
    TENANTS_TABLE, TENANT_CONFIGS_TABLE, TENANT_QUOTAS_TABLE,
    STATUS_ACTIVE, STATUS_INACTIVE
)

logger = structlog.get_logger()

class TenantDAO:
    """Data Access Object for Tenant operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("TenantDAO", "tenant-dao-service-key")
    
    async def create_tenant(self, tenant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new tenant in database"""
        try:
            # Allow override of tenant ID for special cases (like default tenant)
            tenant_id = tenant_data.get('id', str(uuid.uuid4()))
            
            db_tenant_data = {
                'id': tenant_id,
                'organization_name': tenant_data['organization_name'],
                'domain': tenant_data['domain'],
                'subscription_tier': tenant_data['subscription_tier'],
                'status': tenant_data.get('status', STATUS_ACTIVE),
                'billing_email': tenant_data['billing_email'],
                'admin_contact': tenant_data['admin_contact'],
                'region': tenant_data.get('region', 'us-east-1'),
                'compliance_requirements': tenant_data.get('compliance_requirements', []),
                'feature_flags': tenant_data.get('feature_flags', {}),
                'customer_id': tenant_data.get('customer_id', tenant_id),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {TENANTS_TABLE} 
                   (id, organization_name, domain, subscription_tier, status, billing_email, 
                    admin_contact, region, compliance_requirements, feature_flags, customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(organization_name)s, %(domain)s, %(subscription_tier)s, %(status)s,
                   %(billing_email)s, %(admin_contact)s, %(region)s, %(compliance_requirements)s, 
                   %(feature_flags)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_tenant_data
            )
            
            logger.info("Tenant created in database", tenant_id=tenant_id, organization=tenant_data['organization_name'])
            return {'id': tenant_id, **db_tenant_data}
            
        except Exception as e:
            logger.error("Failed to create tenant in database", error=str(e))
            raise e
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID from database"""
        try:
            result = await self.db.execute_query(
                f"SELECT * FROM {TENANTS_TABLE} WHERE id = %(tenant_id)s",
                {"tenant_id": tenant_id}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get tenant by ID", error=str(e), tenant_id=tenant_id)
            return None
    
    async def get_tenant_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get tenant by domain from database"""
        try:
            result = await self.db.execute_query(
                f"SELECT * FROM {TENANTS_TABLE} WHERE domain = %(domain)s",
                {"domain": domain}
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error("Failed to get tenant by domain", error=str(e), domain=domain)
            return None
    
    async def update_tenant(self, tenant_id: str, update_data: Dict[str, Any]) -> bool:
        """Update tenant in database"""
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            
            # Build dynamic update query
            set_clauses = []
            params = {'tenant_id': tenant_id}
            
            for field, value in update_data.items():
                if field != 'id':  # Don't update ID
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
                
            query = f"UPDATE {TENANTS_TABLE} SET {', '.join(set_clauses)} WHERE id = %(tenant_id)s"
            await self.db.execute_query(query, params)
            
            logger.info("Tenant updated in database", tenant_id=tenant_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update tenant", error=str(e), tenant_id=tenant_id)
            return False
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant from database"""
        try:
            await self.db.execute_query(
                f"DELETE FROM {TENANTS_TABLE} WHERE id = %(tenant_id)s",
                {"tenant_id": tenant_id}
            )
            
            logger.info("Tenant deleted from database", tenant_id=tenant_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete tenant", error=str(e), tenant_id=tenant_id)
            return False
    
    async def list_tenants(self, limit: int = 50, offset: int = 0, 
                          status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tenants with pagination and filtering"""
        try:
            query = f"SELECT * FROM {TENANTS_TABLE} WHERE 1=1"
            params = {'limit': limit, 'offset': offset}
            
            if status_filter:
                query += " AND status = %(status)s"
                params['status'] = status_filter
            
            query += " ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s"
            
            result = await self.db.execute_query(query, params)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to list tenants", error=str(e))
            return []
    
    async def count_tenants(self, status_filter: Optional[str] = None) -> int:
        """Count total tenants with optional filtering"""
        try:
            query = f"SELECT COUNT(*) as count FROM {TENANTS_TABLE} WHERE 1=1"
            params = {}
            
            if status_filter:
                query += " AND status = %(status)s"
                params['status'] = status_filter
            
            result = await self.db.execute_query(query, params)
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error("Failed to count tenants", error=str(e))
            return 0
    
    # Tenant Quotas Operations
    async def create_tenant_quota(self, quota_data: Dict[str, Any]) -> str:
        """Create tenant quota in database"""
        try:
            quota_id = str(uuid.uuid4())
            
            db_quota_data = {
                'id': quota_id,
                'tenant_id': quota_data['tenant_id'],
                'quota_type': quota_data['quota_type'],
                'quota_limit': quota_data['quota_limit'],
                'quota_used': quota_data.get('quota_used', 0),
                'reset_period': quota_data.get('reset_period', 'monthly'),
                'customer_id': quota_data.get('customer_id', quota_data['tenant_id']),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {TENANT_QUOTAS_TABLE} 
                   (id, tenant_id, quota_type, quota_limit, quota_used, reset_period, customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(tenant_id)s, %(quota_type)s, %(quota_limit)s, %(quota_used)s, 
                   %(reset_period)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_quota_data
            )
            
            return quota_id
            
        except Exception as e:
            logger.error("Failed to create tenant quota", error=str(e))
            raise e
    
    async def get_tenant_quotas(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all quotas for a tenant"""
        try:
            result = await self.db.execute_query(
                f"SELECT * FROM {TENANT_QUOTAS_TABLE} WHERE tenant_id = %(tenant_id)s",
                {"tenant_id": tenant_id}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get tenant quotas", error=str(e))
            return []
    
    async def update_tenant_quota(self, tenant_id: str, quota_type: str, quota_data: Dict[str, Any]) -> bool:
        """Update specific tenant quota"""
        try:
            quota_data['updated_at'] = datetime.now(timezone.utc)
            
            set_clauses = []
            params = {'tenant_id': tenant_id, 'quota_type': quota_type}
            
            for field, value in quota_data.items():
                if field not in ['id', 'tenant_id', 'quota_type']:
                    set_clauses.append(f"{field} = %({field})s")
                    params[field] = value
            
            if not set_clauses:
                return False
                
            query = f"""UPDATE {TENANT_QUOTAS_TABLE} SET {', '.join(set_clauses)} 
                       WHERE tenant_id = %(tenant_id)s AND quota_type = %(quota_type)s"""
            
            await self.db.execute_query(query, params)
            return True
            
        except Exception as e:
            logger.error("Failed to update tenant quota", error=str(e))
            return False
    
    # Tenant Configs Operations
    async def create_tenant_config(self, config_data: Dict[str, Any]) -> str:
        """Create tenant configuration in database"""
        try:
            config_id = str(uuid.uuid4())
            
            db_config_data = {
                'id': config_id,
                'tenant_id': config_data['tenant_id'],
                'config_key': config_data['config_key'],
                'config_value': config_data['config_value'],
                'config_type': config_data.get('config_type', 'string'),
                'created_by': config_data.get('created_by', 'system'),
                'customer_id': config_data.get('customer_id', config_data['tenant_id']),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            await self.db.execute_query(
                f"""INSERT INTO {TENANT_CONFIGS_TABLE} 
                   (id, tenant_id, config_key, config_value, config_type, created_by, customer_id, created_at, updated_at)
                   VALUES (%(id)s, %(tenant_id)s, %(config_key)s, %(config_value)s, %(config_type)s, 
                   %(created_by)s, %(customer_id)s, %(created_at)s, %(updated_at)s)""",
                db_config_data
            )
            
            return config_id
            
        except Exception as e:
            logger.error("Failed to create tenant config", error=str(e))
            raise e
    
    async def get_tenant_configs(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all configurations for a tenant"""
        try:
            result = await self.db.execute_query(
                f"SELECT * FROM {TENANT_CONFIGS_TABLE} WHERE tenant_id = %(tenant_id)s",
                {"tenant_id": tenant_id}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get tenant configs", error=str(e))
            return []
    
    async def update_tenant_config(self, tenant_id: str, config_key: str, config_value: str) -> bool:
        """Update specific tenant configuration"""
        try:
            await self.db.execute_query(
                f"""UPDATE {TENANT_CONFIGS_TABLE} 
                   SET config_value = %(config_value)s, updated_at = %(updated_at)s
                   WHERE tenant_id = %(tenant_id)s AND config_key = %(config_key)s""",
                {
                    "tenant_id": tenant_id,
                    "config_key": config_key,
                    "config_value": config_value,
                    "updated_at": datetime.now(timezone.utc)
                }
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to update tenant config", error=str(e))
            return False