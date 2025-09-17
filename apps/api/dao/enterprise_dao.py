"""
Enterprise DAO - Data Access Operations for Enterprise Management

Handles database operations for:
- Authentication providers (OIDC, SAML, LDAP)
- API key management
- Role-based access control (RBAC)
- Multi-tenant configuration
- Compliance and audit logging
- Enterprise integrations
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from database_layer import DatabaseLayer


class EnterpriseDAO:
    """Data Access Object for enterprise operations"""

    def __init__(self):
        self.db = DatabaseLayer("EnterpriseDAO", "enterprise-dao-service-key")

    # ==========================================
    # AUTHENTICATION PROVIDER OPERATIONS
    # ==========================================

    async def save_auth_provider(self, provider_data: Dict[str, Any]) -> str:
        """Save authentication provider configuration"""
        query = """
        INSERT INTO auth_providers_mt (
            id, provider_type, name, config, is_enabled, is_default,
            user_mapping, group_mapping, created_at, updated_at, customer_id
        ) VALUES (
            %(id)s, %(provider_type)s, %(name)s, %(config)s, %(is_enabled)s, %(is_default)s,
            %(user_mapping)s, %(group_mapping)s, %(created_at)s, %(updated_at)s, %(customer_id)s
        )
        """

        params = {
            'id': provider_data['id'],
            'provider_type': provider_data['provider_type'],
            'name': provider_data['name'],
            'config': json.dumps(provider_data['config']),
            'is_enabled': provider_data.get('is_enabled', 1),
            'is_default': provider_data.get('is_default', 0),
            'user_mapping': json.dumps(provider_data.get('user_mapping', {})),
            'group_mapping': json.dumps(provider_data.get('group_mapping', {})),
            'created_at': provider_data['created_at'],
            'updated_at': provider_data['updated_at'],
            'customer_id': provider_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return provider_data['id']

    async def get_auth_providers(self, customer_id: str, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Get authentication providers for customer"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}

        if enabled_only:
            where_conditions.append("is_enabled = 1")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, provider_type, name, config, is_enabled, is_default,
               user_mapping, group_mapping, created_at, updated_at
        FROM auth_providers_mt
        WHERE {where_clause}
        ORDER BY is_default DESC, name ASC
        """

        results = await self.db.fetch_all(query, params)

        # Parse JSON fields
        providers = []
        for result in results:
            provider = dict(result)
            provider['config'] = json.loads(provider['config'])
            provider['user_mapping'] = json.loads(provider['user_mapping'])
            provider['group_mapping'] = json.loads(provider['group_mapping'])
            providers.append(provider)

        return providers

    async def get_auth_provider_by_id(self, provider_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get authentication provider by ID"""
        query = """
        SELECT id, provider_type, name, config, is_enabled, is_default,
               user_mapping, group_mapping, created_at, updated_at
        FROM auth_providers_mt
        WHERE customer_id = %(customer_id)s AND id = %(provider_id)s
        """

        params = {'customer_id': customer_id, 'provider_id': provider_id}
        result = await self.db.fetch_one(query, params)

        if result:
            provider = dict(result)
            provider['config'] = json.loads(provider['config'])
            provider['user_mapping'] = json.loads(provider['user_mapping'])
            provider['group_mapping'] = json.loads(provider['group_mapping'])
            return provider

        return None

    async def update_auth_provider(self, provider_id: str, updates: Dict[str, Any],
                                 customer_id: str) -> bool:
        """Update authentication provider"""
        set_clauses = []
        params = {'customer_id': customer_id, 'provider_id': provider_id}

        for key, value in updates.items():
            if key in ['name', 'is_enabled', 'is_default']:
                set_clauses.append(f"{key} = %({key})s")
                params[key] = value
            elif key in ['config', 'user_mapping', 'group_mapping']:
                set_clauses.append(f"{key} = %({key})s")
                params[key] = json.dumps(value)

        if not set_clauses:
            return False

        set_clauses.append("updated_at = now64(3)")

        query = f"""
        ALTER TABLE auth_providers_mt
        UPDATE {', '.join(set_clauses)}
        WHERE customer_id = %(customer_id)s AND id = %(provider_id)s
        """

        await self.db.execute_query(query, params)
        return True

    async def delete_auth_provider(self, provider_id: str, customer_id: str) -> bool:
        """Delete authentication provider"""
        query = """
        ALTER TABLE auth_providers_mt
        DELETE WHERE customer_id = %(customer_id)s AND id = %(provider_id)s
        """

        params = {'customer_id': customer_id, 'provider_id': provider_id}
        await self.db.execute_query(query, params)
        return True

    # ==========================================
    # API KEY OPERATIONS
    # ==========================================

    async def create_api_key(self, key_data: Dict[str, Any]) -> str:
        """Create new API key"""
        query = """
        INSERT INTO api_keys_enterprise_mt (
            id, name, key_hash, tenant_id, created_by, permissions,
            rate_limit, expires_at, last_used, usage_count, is_active,
            created_at, updated_at, customer_id
        ) VALUES (
            %(id)s, %(name)s, %(key_hash)s, %(tenant_id)s, %(created_by)s, %(permissions)s,
            %(rate_limit)s, %(expires_at)s, %(last_used)s, %(usage_count)s, %(is_active)s,
            %(created_at)s, %(updated_at)s, %(customer_id)s
        )
        """

        params = {
            'id': key_data['id'],
            'name': key_data['name'],
            'key_hash': key_data['key_hash'],
            'tenant_id': key_data['tenant_id'],
            'created_by': key_data['created_by'],
            'permissions': key_data['permissions'],
            'rate_limit': key_data.get('rate_limit', 1000),
            'expires_at': key_data.get('expires_at'),
            'last_used': key_data.get('last_used'),
            'usage_count': key_data.get('usage_count', 0),
            'is_active': key_data.get('is_active', 1),
            'created_at': key_data['created_at'],
            'updated_at': key_data['updated_at'],
            'customer_id': key_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return key_data['id']

    async def get_api_keys(self, customer_id: str, tenant_id: Optional[str] = None,
                         active_only: bool = True) -> List[Dict[str, Any]]:
        """Get API keys for customer/tenant"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}

        if tenant_id:
            where_conditions.append("tenant_id = %(tenant_id)s")
            params['tenant_id'] = tenant_id

        if active_only:
            where_conditions.append("is_active = 1")
            where_conditions.append("(expires_at IS NULL OR expires_at > now64(3))")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, name, tenant_id, created_by, permissions, rate_limit,
               expires_at, last_used, usage_count, is_active, created_at
        FROM api_keys_enterprise_mt
        WHERE {where_clause}
        ORDER BY created_at DESC
        """

        results = await self.db.fetch_all(query, params)
        return [dict(result) for result in results]

    async def get_api_key_by_hash(self, key_hash: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get API key by hash for authentication"""
        query = """
        SELECT id, name, tenant_id, created_by, permissions, rate_limit,
               expires_at, last_used, usage_count, is_active
        FROM api_keys_enterprise_mt
        WHERE customer_id = %(customer_id)s AND key_hash = %(key_hash)s
          AND is_active = 1 AND (expires_at IS NULL OR expires_at > now64(3))
        """

        params = {'customer_id': customer_id, 'key_hash': key_hash}
        result = await self.db.fetch_one(query, params)

        return dict(result) if result else None

    async def update_api_key_usage(self, key_id: str, customer_id: str) -> bool:
        """Update API key last used timestamp and usage count"""
        query = """
        ALTER TABLE api_keys_enterprise_mt
        UPDATE last_used = now64(3), usage_count = usage_count + 1
        WHERE customer_id = %(customer_id)s AND id = %(key_id)s
        """

        params = {'customer_id': customer_id, 'key_id': key_id}
        await self.db.execute_query(query, params)
        return True

    async def revoke_api_key(self, key_id: str, customer_id: str) -> bool:
        """Revoke API key"""
        query = """
        ALTER TABLE api_keys_enterprise_mt
        UPDATE is_active = 0, updated_at = now64(3)
        WHERE customer_id = %(customer_id)s AND id = %(key_id)s
        """

        params = {'customer_id': customer_id, 'key_id': key_id}
        await self.db.execute_query(query, params)
        return True

    # ==========================================
    # MFA OPERATIONS
    # ==========================================

    async def create_mfa_setup(self, mfa_data: Dict[str, Any]) -> str:
        """Create MFA setup record"""
        query = """
        INSERT INTO mfa_setups_mt (
            user_id, mfa_type, config, backup_codes, is_verified, customer_id
        ) VALUES (
            %(user_id)s, %(mfa_type)s, %(config)s, %(backup_codes)s, %(is_verified)s, %(customer_id)s
        )
        """

        params = {
            'user_id': mfa_data['user_id'],
            'mfa_type': mfa_data['mfa_type'],
            'config': json.dumps(mfa_data['config']),
            'backup_codes': mfa_data.get('backup_codes', []),
            'is_verified': 0,  # Always start as unverified
            'customer_id': mfa_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return f"{mfa_data['user_id']}_{mfa_data['mfa_type']}"

    async def get_mfa_setups(self, customer_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get MFA setups for customer/user"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}

        if user_id:
            where_conditions.append("user_id = %(user_id)s")
            params['user_id'] = user_id

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT user_id, mfa_type, config, backup_codes, is_verified, created_at, verified_at
        FROM mfa_setups_mt
        WHERE {where_clause}
        ORDER BY created_at DESC
        """

        results = await self.db.fetch_all(query, params)

        # Parse JSON fields
        mfa_setups = []
        for result in results:
            mfa_setup = dict(result)
            mfa_setup['config'] = json.loads(mfa_setup['config'])
            mfa_setups.append(mfa_setup)

        return mfa_setups

    async def update_mfa_verification(self, user_id: str, mfa_type: str, customer_id: str) -> bool:
        """Update MFA setup verification status"""
        query = """
        ALTER TABLE mfa_setups_mt
        UPDATE is_verified = 1, verified_at = now64(3)
        WHERE customer_id = %(customer_id)s AND user_id = %(user_id)s AND mfa_type = %(mfa_type)s
        """

        params = {'customer_id': customer_id, 'user_id': user_id, 'mfa_type': mfa_type}
        await self.db.execute_query(query, params)
        return True

    # ==========================================
    # TENANT OPERATIONS
    # ==========================================

    async def create_tenant(self, tenant_data: Dict[str, Any]) -> str:
        """Create new tenant"""
        # Convert feature_flags to proper ClickHouse Map format
        feature_flags = tenant_data.get('feature_flags', {})
        # Convert to ClickHouse map() function format: map('key1', 'value1', 'key2', 'value2', ...)
        map_args = []
        for k, v in feature_flags.items():
            map_args.extend([str(k), str(v)])
        
        # Build the map function call
        if map_args:
            feature_flags_expr = f"map({', '.join(repr(arg) for arg in map_args)})"
        else:
            feature_flags_expr = "map()"

        # Use raw SQL for the map expression
        query = f"""
        INSERT INTO tenants_mt (
            id, organization_name, domain, subscription_tier, status, 
            billing_email, admin_contact, region, compliance_requirements, 
            feature_flags, customer_id
        ) VALUES (
            %(id)s, %(organization_name)s, %(domain)s, %(subscription_tier)s, %(status)s,
            %(billing_email)s, %(admin_contact)s, %(region)s, %(compliance_requirements)s,
            {feature_flags_expr}, %(customer_id)s
        )
        """

        params = {
            'id': tenant_data['id'],
            'organization_name': tenant_data['name'],
            'domain': tenant_data.get('domain', f"{tenant_data['name'].lower().replace(' ', '-')}.com"),
            'subscription_tier': tenant_data.get('tier', 'professional'),
            'status': tenant_data.get('status', 'active'),
            'billing_email': tenant_data.get('billing_email', ''),
            'admin_contact': tenant_data.get('admin_contact', ''),
            'region': tenant_data.get('region', 'us-east-1'),
            'compliance_requirements': tenant_data.get('compliance_requirements', []),
            'customer_id': tenant_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return tenant_data['id']

    async def get_tenants(self, customer_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get tenants for customer"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}

        if active_only:
            where_conditions.append("status = 'active'")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, organization_name, domain, subscription_tier, status, created_at, updated_at,
               billing_email, admin_contact, region, compliance_requirements, feature_flags
        FROM tenants_mt
        WHERE {where_clause}
        ORDER BY created_at DESC
        """

        results = await self.db.fetch_all(query, params)

        # Return tenants with proper field mapping
        tenants = []
        for result in results:
            tenant = dict(result)
            # Map database fields to API response fields
            tenant['name'] = tenant['organization_name']
            tenant['tier'] = tenant['subscription_tier']
            tenant['contact_info'] = {
                'billing_email': tenant['billing_email'],
                'admin_contact': tenant['admin_contact']
            }
            tenant['settings'] = {
                'region': tenant['region'],
                'compliance_requirements': tenant['compliance_requirements'],
                'feature_flags': tenant['feature_flags']
            }
            # Remove database-specific fields from response
            del tenant['organization_name']
            del tenant['subscription_tier']
            del tenant['billing_email']
            del tenant['admin_contact']
            del tenant['region']
            del tenant['compliance_requirements']
            del tenant['feature_flags']
            tenants.append(tenant)

        return tenants

    async def get_tenant_by_id(self, tenant_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant by ID"""
        query = """
        SELECT id, organization_name, domain, subscription_tier, status, created_at, updated_at,
               billing_email, admin_contact, region, compliance_requirements, feature_flags
        FROM tenants_mt
        WHERE customer_id = %(customer_id)s AND id = %(tenant_id)s
        """

        params = {'customer_id': customer_id, 'tenant_id': tenant_id}
        result = await self.db.fetch_one(query, params)

        if result:
            tenant = dict(result)
            # Map database fields to API response fields
            tenant['name'] = tenant['organization_name']
            tenant['tier'] = tenant['subscription_tier']
            tenant['contact_info'] = {
                'billing_email': tenant['billing_email'],
                'admin_contact': tenant['admin_contact']
            }
            tenant['settings'] = {
                'region': tenant['region'],
                'compliance_requirements': tenant['compliance_requirements'],
                'feature_flags': tenant['feature_flags']
            }
            # Remove database-specific fields from response
            del tenant['organization_name']
            del tenant['subscription_tier']
            del tenant['billing_email']
            del tenant['admin_contact']
            del tenant['region']
            del tenant['compliance_requirements']
            del tenant['feature_flags']
            return tenant

        return None

    async def update_tenant_settings(self, tenant_id: str, updates: Dict[str, Any],
                                   customer_id: str) -> bool:
        """Update tenant settings"""
        set_clauses = []
        params = {'customer_id': customer_id, 'tenant_id': tenant_id}

        # Map API fields to database fields
        field_mapping = {
            'name': 'organization_name',
            'tier': 'subscription_tier',
            'status': 'status',
            'domain': 'domain',
            'billing_email': 'billing_email',
            'admin_contact': 'admin_contact',
            'region': 'region',
            'compliance_requirements': 'compliance_requirements',
            'feature_flags': 'feature_flags'
        }

        for key, value in updates.items():
            # Handle nested settings/contact_info updates
            if key == 'settings':
                for setting_key, setting_value in value.items():
                    if setting_key in field_mapping:
                        db_field = field_mapping[setting_key]
                        set_clauses.append(f"{db_field} = %({setting_key})s")
                        params[setting_key] = setting_value
            elif key == 'contact_info':
                for contact_key, contact_value in value.items():
                    if contact_key in field_mapping:
                        db_field = field_mapping[contact_key]
                        set_clauses.append(f"{db_field} = %({contact_key})s")
                        params[contact_key] = contact_value
            elif key in field_mapping:
                db_field = field_mapping[key]
                set_clauses.append(f"{db_field} = %({key})s")
                params[key] = value

        if not set_clauses:
            return False

        set_clauses.append("updated_at = now64(3)")

        query = f"""
        ALTER TABLE tenants_mt
        UPDATE {', '.join(set_clauses)}
        WHERE customer_id = %(customer_id)s AND id = %(tenant_id)s
        """

        await self.db.execute_query(query, params)
        return True

    # ==========================================
    # COMPLIANCE OPERATIONS
    # ==========================================

    async def create_legal_hold(self, hold_data: Dict[str, Any]) -> str:
        """Create legal hold record"""
        query = """
        INSERT INTO enterprise_compliance_mt (
            id, type, case_id, custodian, reason, date_range,
            scope, status, created_at, updated_at, customer_id
        ) VALUES (
            %(id)s, 'legal_hold', %(case_id)s, %(custodian)s, %(reason)s, %(date_range)s,
            %(scope)s, %(status)s, %(created_at)s, %(updated_at)s, %(customer_id)s
        )
        """

        params = {
            'id': hold_data['id'],
            'case_id': hold_data['case_id'],
            'custodian': hold_data['custodian'],
            'reason': hold_data['reason'],
            'date_range': json.dumps(hold_data['date_range']),
            'scope': json.dumps(hold_data['scope']),
            'status': hold_data.get('status', 'active'),
            'created_at': hold_data['created_at'],
            'updated_at': hold_data['updated_at'],
            'customer_id': hold_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return hold_data['id']

    async def get_compliance_records(self, customer_id: str, record_type: Optional[str] = None,
                                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get compliance records"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id, 'limit': limit}

        if record_type:
            where_conditions.append("type = %(record_type)s")
            params['record_type'] = record_type

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, type, case_id, custodian, reason, date_range,
               scope, status, created_at, updated_at
        FROM enterprise_compliance_mt
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """

        results = await self.db.fetch_all(query, params)

        # Parse JSON fields
        records = []
        for result in results:
            record = dict(result)
            if record.get('date_range'):
                record['date_range'] = json.loads(record['date_range'])
            if record.get('scope'):
                record['scope'] = json.loads(record['scope'])
            records.append(record)

        return records

    # ==========================================
    # ENTERPRISE INTEGRATION OPERATIONS
    # ==========================================

    async def save_integration_config(self, config_data: Dict[str, Any]) -> str:
        """Save enterprise integration configuration"""
        query = """
        INSERT INTO enterprise_integrations_mt (
            id, integration_type, name, config, is_enabled, health_status,
            last_health_check, created_at, updated_at, customer_id
        ) VALUES (
            %(id)s, %(integration_type)s, %(name)s, %(config)s, %(is_enabled)s, %(health_status)s,
            %(last_health_check)s, %(created_at)s, %(updated_at)s, %(customer_id)s
        )
        """

        params = {
            'id': config_data['id'],
            'integration_type': config_data['integration_type'],
            'name': config_data['name'],
            'config': json.dumps(config_data['config']),
            'is_enabled': config_data.get('is_enabled', 1),
            'health_status': config_data.get('health_status', 'unknown'),
            'last_health_check': config_data.get('last_health_check'),
            'created_at': config_data['created_at'],
            'updated_at': config_data['updated_at'],
            'customer_id': config_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return config_data['id']

    async def get_integrations(self, customer_id: str, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Get enterprise integrations"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id}

        if enabled_only:
            where_conditions.append("is_enabled = 1")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, integration_type, name, config, is_enabled, health_status,
               last_health_check, created_at, updated_at
        FROM enterprise_integrations_mt
        WHERE {where_clause}
        ORDER BY integration_type, name
        """

        results = await self.db.fetch_all(query, params)

        # Parse JSON fields
        integrations = []
        for result in results:
            integration = dict(result)
            integration['config'] = json.loads(integration['config'])
            integrations.append(integration)

        return integrations

    async def get_integration_by_type(self, integration_type: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get integration by type"""
        query = """
        SELECT id, integration_type, name, config, is_enabled, health_status,
               last_health_check, created_at, updated_at
        FROM enterprise_integrations_mt
        WHERE customer_id = %(customer_id)s AND integration_type = %(integration_type)s
        """

        params = {'customer_id': customer_id, 'integration_type': integration_type}
        result = await self.db.fetch_one(query, params)

        if result:
            integration = dict(result)
            integration['config'] = json.loads(integration['config'])
            return integration

        return None

    async def update_integration_health(self, integration_id: str, health_status: str,
                                      customer_id: str) -> bool:
        """Update integration health status"""
        query = """
        ALTER TABLE enterprise_integrations_mt
        UPDATE health_status = %(health_status)s, last_health_check = now64(3), updated_at = now64(3)
        WHERE customer_id = %(customer_id)s AND id = %(integration_id)s
        """

        params = {
            'customer_id': customer_id,
            'integration_id': integration_id,
            'health_status': health_status
        }

        await self.db.execute_query(query, params)
        return True

    # ==========================================
    # AUDIT LOG OPERATIONS
    # ==========================================

    async def create_audit_log(self, audit_data: Dict[str, Any]) -> str:
        """Create audit log entry"""
        query = """
        INSERT INTO enterprise_audit_logs_mt (
            id, user_id, tenant_id, action_type, resource_type, resource_id,
            details, ip_address, user_agent, timestamp, customer_id
        ) VALUES (
            %(id)s, %(user_id)s, %(tenant_id)s, %(action_type)s, %(resource_type)s, %(resource_id)s,
            %(details)s, %(ip_address)s, %(user_agent)s, %(timestamp)s, %(customer_id)s
        )
        """

        params = {
            'id': audit_data['id'],
            'user_id': audit_data['user_id'],
            'tenant_id': audit_data.get('tenant_id'),
            'action_type': audit_data['action_type'],
            'resource_type': audit_data['resource_type'],
            'resource_id': audit_data.get('resource_id'),
            'details': json.dumps(audit_data.get('details', {})),
            'ip_address': audit_data.get('ip_address', 'unknown'),
            'user_agent': audit_data.get('user_agent', ''),
            'timestamp': audit_data['timestamp'],
            'customer_id': audit_data['customer_id']
        }

        await self.db.execute_query(query, params)
        return audit_data['id']

    async def get_audit_logs(self, customer_id: str, filters: Dict[str, Any],
                           limit: int = 1000) -> List[Dict[str, Any]]:
        """Get audit logs with filters"""
        where_conditions = ["customer_id = %(customer_id)s"]
        params = {'customer_id': customer_id, 'limit': limit}

        if filters.get('user_id'):
            where_conditions.append("user_id = %(user_id)s")
            params['user_id'] = filters['user_id']

        if filters.get('tenant_id'):
            where_conditions.append("tenant_id = %(tenant_id)s")
            params['tenant_id'] = filters['tenant_id']

        if filters.get('action_types'):
            where_conditions.append("action_type IN %(action_types)s")
            params['action_types'] = filters['action_types']

        if filters.get('start_time'):
            where_conditions.append("timestamp >= parseDateTime64BestEffort(%(start_time)s)")
            params['start_time'] = filters['start_time']

        if filters.get('end_time'):
            where_conditions.append("timestamp <= parseDateTime64BestEffort(%(end_time)s)")
            params['end_time'] = filters['end_time']

        where_clause = " AND ".join(where_conditions)

        query = f"""
        SELECT id, user_id, tenant_id, action_type, resource_type, resource_id,
               details, ip_address, user_agent, timestamp
        FROM enterprise_audit_logs_mt
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT %(limit)s
        """

        results = await self.db.fetch_all(query, params)

        # Parse JSON fields
        logs = []
        for result in results:
            log = dict(result)
            log['details'] = json.loads(log['details'])
            logs.append(log)

        return logs

    # ==========================================
    # USAGE & BILLING OPERATIONS
    # ==========================================

    async def get_usage_billing_data(self, customer_id: str, start_time: datetime,
                                   end_time: datetime) -> Dict[str, Any]:
        """Get usage and billing data for period"""
        query = """
        SELECT
            tenant_id,
            billing_feature,
            sum(cost_credits) as total_credits,
            count(*) as total_requests,
            sum(response_size_bytes) as total_bytes,
            avg(processing_time_ms) as avg_processing_time
        FROM api_usage_mt
        WHERE customer_id = %(customer_id)s
          AND request_timestamp >= %(start_time)s
          AND request_timestamp <= %(end_time)s
        GROUP BY tenant_id, billing_feature
        ORDER BY tenant_id, billing_feature
        """

        params = {
            'customer_id': customer_id,
            'start_time': start_time,
            'end_time': end_time
        }

        results = await self.db.fetch_all(query, params)

        # Aggregate by tenant and feature
        usage_by_tenant = {}
        total_usage = {
            'total_credits': 0,
            'total_requests': 0,
            'total_bytes': 0
        }

        for result in results:
            tenant_id = result['tenant_id']
            feature = result['billing_feature']

            if tenant_id not in usage_by_tenant:
                usage_by_tenant[tenant_id] = {}

            usage_by_tenant[tenant_id][feature] = {
                'credits': result['total_credits'],
                'requests': result['total_requests'],
                'bytes': result['total_bytes'],
                'avg_processing_time': result['avg_processing_time']
            }

            total_usage['total_credits'] += result['total_credits']
            total_usage['total_requests'] += result['total_requests']
            total_usage['total_bytes'] += result['total_bytes']

        return {
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'total_usage': total_usage,
            'usage_by_tenant': usage_by_tenant
        }

    # ==========================================
    # SYSTEM HEALTH OPERATIONS
    # ==========================================

    async def get_enterprise_health_metrics(self, customer_id: str) -> Dict[str, Any]:
        """Get enterprise system health metrics"""
        # Get basic counts
        counts_query = """
        SELECT
            (SELECT count(*) FROM tenants_mt WHERE customer_id = %(customer_id)s AND status = 'active') as active_tenants,
            (SELECT count(*) FROM api_keys_enterprise_mt WHERE customer_id = %(customer_id)s AND is_active = 1) as active_api_keys,
            (SELECT count(*) FROM auth_providers_mt WHERE customer_id = %(customer_id)s AND is_enabled = 1) as enabled_auth_providers,
            (SELECT count(*) FROM enterprise_integrations_mt WHERE customer_id = %(customer_id)s AND is_enabled = 1) as enabled_integrations
        """

        params = {'customer_id': customer_id}
        counts = await self.db.fetch_one(counts_query, params)

        # Get recent activity
        activity_query = """
        SELECT
            count(*) as total_audit_events,
            countIf(timestamp >= now64(3) - INTERVAL 24 HOUR) as recent_audit_events
        FROM enterprise_audit_logs_mt
        WHERE customer_id = %(customer_id)s
        """

        activity = await self.db.fetch_one(activity_query, params)

        return {
            'tenant_metrics': {
                'active_tenants': counts['active_tenants'],
                'active_api_keys': counts['active_api_keys']
            },
            'auth_metrics': {
                'enabled_providers': counts['enabled_auth_providers']
            },
            'integration_metrics': {
                'enabled_integrations': counts['enabled_integrations']
            },
            'activity_metrics': {
                'total_audit_events': activity['total_audit_events'],
                'recent_audit_events': activity['recent_audit_events']
            },
            'health_timestamp': datetime.utcnow().isoformat()
        }
