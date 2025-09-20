"""
Compliance Data Access Object (DAO)
Handles all database operations for compliance management
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import structlog

from database_layer import DatabaseLayer

logger = structlog.get_logger()

class ComplianceDAO:
    """Data Access Object for Compliance operations"""
    
    def __init__(self):
        self.db = DatabaseLayer("TenantDAO", "tenant-dao-service-key")
    
    async def get_compliance_frameworks(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get compliance frameworks for a tenant from compliance reports"""
        try:
            result = await self.db.execute_query(
                """SELECT DISTINCT report_type, status, generated_at 
                   FROM compliance_reports_mt 
                   WHERE customer_id = %(tenant_id)s 
                   ORDER BY generated_at DESC""",
                {"tenant_id": tenant_id}
            )
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            logger.error("Failed to get compliance frameworks", error=str(e))
            return []
    
    async def get_audit_logs_status(self, tenant_id: str) -> bool:
        """Check if audit logging is enabled for tenant"""
        try:
            # Check if there are any recent compliance reports (indicates audit logging is active)
            result = await self.db.execute_query(
                """SELECT count() as count FROM compliance_reports_mt 
                   WHERE customer_id = %(tenant_id)s 
                   AND generated_at >= now() - INTERVAL 90 DAY""",
                {"tenant_id": tenant_id}
            )
            
            return result[0]['count'] > 0 if result else False
            
        except Exception as e:
            logger.error("Failed to check audit logs status", error=str(e))
            return False
    
    async def get_data_classification(self, tenant_id: str) -> Dict[str, Any]:
        """Get data classification settings for tenant"""
        try:
            # For now, return standard classification based on compliance frameworks
            frameworks = await self.get_compliance_frameworks(tenant_id)
            
            # Determine data types based on active compliance frameworks
            sensitive_data_types = ["PII", "internal"]
            classification_rules = ["automatic"]
            retention_policies = {"internal": "7_years"}
            
            # Add specific data types based on compliance frameworks
            for framework in frameworks:
                framework_type = framework.get('report_type', '')
                if framework_type == 'gdpr':
                    sensitive_data_types.extend(["personal_data", "special_categories"])
                    retention_policies["personal_data"] = "varies_by_purpose"
                elif framework_type == 'hipaa':
                    sensitive_data_types.append("medical")
                    retention_policies["medical"] = "6_years"
                elif framework_type == 'pci_dss':
                    sensitive_data_types.append("financial")
                    retention_policies["financial"] = "7_years"
            
            return {
                "sensitive_data_types": list(set(sensitive_data_types)),
                "classification_rules": classification_rules,
                "retention_policies": retention_policies
            }
            
        except Exception as e:
            logger.error("Failed to get data classification", error=str(e))
            return {
                "sensitive_data_types": ["PII", "internal"],
                "classification_rules": ["automatic"],
                "retention_policies": {"internal": "7_years"}
            }
    
    async def get_privacy_settings(self, tenant_id: str) -> Dict[str, Any]:
        """Get privacy settings for tenant"""
        try:
            frameworks = await self.get_compliance_frameworks(tenant_id)
            
            # Default privacy settings
            privacy_settings = {
                "data_anonymization": False,
                "consent_management": False,
                "right_to_deletion": False,
                "data_portability": False
            }
            
            # Enable settings based on compliance frameworks
            for framework in frameworks:
                framework_type = framework.get('report_type', '')
                if framework_type in ['gdpr', 'ccpa']:
                    privacy_settings.update({
                        "data_anonymization": True,
                        "consent_management": True,
                        "right_to_deletion": True,
                        "data_portability": True
                    })
                elif framework_type == 'hipaa':
                    privacy_settings.update({
                        "data_anonymization": True,
                        "consent_management": True
                    })
            
            return privacy_settings
            
        except Exception as e:
            logger.error("Failed to get privacy settings", error=str(e))
            return {
                "data_anonymization": False,
                "consent_management": False,
                "right_to_deletion": False,
                "data_portability": False
            }
    
    async def get_compliance_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get overall compliance status for tenant"""
        try:
            frameworks = await self.get_compliance_frameworks(tenant_id)
            audit_logs_enabled = await self.get_audit_logs_status(tenant_id)
            data_classification = await self.get_data_classification(tenant_id)
            privacy_settings = await self.get_privacy_settings(tenant_id)
            
            # Build compliance frameworks list
            framework_names = []
            certifications = {}
            last_audit_date = None
            
            for framework in frameworks:
                framework_type = framework.get('report_type', '').upper()
                if framework_type:
                    framework_names.append(framework_type)
                    certifications[framework_type] = {
                        "status": "compliant" if framework.get('status') == 'completed' else "pending",
                        "last_reviewed": framework.get('generated_at', '').isoformat() if framework.get('generated_at') else None
                    }
                    
                    # Track most recent audit date
                    if framework.get('generated_at'):
                        if not last_audit_date or framework['generated_at'] > last_audit_date:
                            last_audit_date = framework['generated_at']
            
            # Calculate compliance score based on active frameworks and their status
            total_frameworks = len(frameworks)
            compliant_frameworks = sum(1 for f in frameworks if f.get('status') == 'completed')
            compliance_score = int((compliant_frameworks / total_frameworks * 100)) if total_frameworks > 0 else 0
            
            return {
                "tenant_id": tenant_id,
                "compliance_frameworks": framework_names,
                "audit_logs_enabled": audit_logs_enabled,
                "data_classification": data_classification,
                "privacy_settings": privacy_settings,
                "last_audit_date": last_audit_date.isoformat() if last_audit_date else None,
                "compliance_score": compliance_score,
                "violations": [],  # Would need additional table for violations
                "certifications": certifications,
                "next_audit_due": None  # Would calculate based on framework requirements
            }
            
        except Exception as e:
            logger.error("Failed to get compliance status", error=str(e))
            raise e
    
    async def create_legal_hold(self, tenant_id: str, legal_hold_data: Dict[str, Any]) -> str:
        """Create legal hold request in database"""
        try:
            hold_id = str(uuid.uuid4())
            
            # Handle both old format (case_id, custodian) and new format (case_name, contact_person)
            case_id = legal_hold_data.get('case_name', legal_hold_data.get('case_id', ''))
            custodian = legal_hold_data.get('contact_person', legal_hold_data.get('custodian', ''))
            reason = legal_hold_data.get('justification', legal_hold_data.get('description', legal_hold_data.get('reason', '')))
            
            # Format date range from start_date/end_date or date_range object
            if 'start_date' in legal_hold_data and 'end_date' in legal_hold_data:
                date_range = {
                    'start_date': legal_hold_data['start_date'],
                    'end_date': legal_hold_data['end_date']
                }
            else:
                date_range = legal_hold_data.get('date_range', {})
            
            # Build scope from available data
            scope = {
                'contact_email': legal_hold_data.get('contact_email', ''),
                'data_types': legal_hold_data.get('data_types', [])
            }
            scope.update(legal_hold_data.get('scope', {}))
            
            db_hold_data = {
                'id': hold_id,
                'type': 'legal_hold',
                'case_id': case_id,
                'custodian': custodian,
                'reason': reason,
                'date_range': str(date_range),
                'scope': str(scope),
                'status': 'active',
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'customer_id': tenant_id
            }
            
            await self.db.execute_query(
                """INSERT INTO enterprise_compliance_mt 
                   (id, type, case_id, custodian, reason, date_range, scope, status, created_at, updated_at, customer_id)
                   VALUES (%(id)s, %(type)s, %(case_id)s, %(custodian)s, %(reason)s, %(date_range)s, %(scope)s, %(status)s, %(created_at)s, %(updated_at)s, %(customer_id)s)""",
                db_hold_data
            )
            
            logger.info("Legal hold created", tenant_id=tenant_id, hold_id=hold_id)
            return hold_id
            
        except Exception as e:
            logger.error("Failed to create legal hold", error=str(e))
            raise e
    
    async def get_legal_hold(self, tenant_id: str, hold_id: str) -> Optional[Dict[str, Any]]:
        """Get legal hold by ID"""
        try:
            result = await self.db.execute_query(
                """SELECT * FROM enterprise_compliance_mt 
                   WHERE id = %(hold_id)s AND customer_id = %(tenant_id)s AND type = 'legal_hold'""",
                {"hold_id": hold_id, "tenant_id": tenant_id}
            )
            
            return dict(result[0]) if result else None
            
        except Exception as e:
            logger.error("Failed to get legal hold", error=str(e))
            return None
    
    async def create_compliance_report(self, tenant_id: str, report_type: str, period_start: datetime, period_end: datetime) -> str:
        """Create compliance report entry"""
        try:
            report_id = str(uuid.uuid4())
            
            db_report_data = {
                'id': report_id,
                'report_type': report_type.lower(),
                'period_start': period_start,
                'period_end': period_end,
                'status': 'generating',
                'report_data': '',
                'generated_by': 'system',
                'generated_at': datetime.now(timezone.utc),
                'file_path': None,
                'customer_id': tenant_id
            }
            
            await self.db.execute_query(
                """INSERT INTO compliance_reports_mt 
                   (id, report_type, period_start, period_end, status, report_data, generated_by, generated_at, file_path, customer_id)
                   VALUES (%(id)s, %(report_type)s, %(period_start)s, %(period_end)s, %(status)s, %(report_data)s, %(generated_by)s, %(generated_at)s, %(file_path)s, %(customer_id)s)""",
                db_report_data
            )
            
            logger.info("Compliance report created", tenant_id=tenant_id, report_id=report_id, report_type=report_type)
            return report_id
            
        except Exception as e:
            logger.error("Failed to create compliance report", error=str(e))
            raise e