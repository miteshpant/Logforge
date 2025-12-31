/**
 * Enterprise API Client
 * 20+ endpoints for enterprise features, compliance, and administration
 * Based on: /docs/wiki/knowledge_base/devDocs/Enterprise-Router-API-Documentation.md
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Enterprise types
export interface ComplianceFramework {
  id: string
  name: 'SOX' | 'GDPR' | 'HIPAA' | 'PCI-DSS' | 'SOC2' | 'ISO27001'
  description: string
  requirements: ComplianceRequirement[]
  compliance_score: number
  last_assessment: string
  next_assessment: string
  status: 'compliant' | 'non_compliant' | 'in_progress'
}

export interface ComplianceRequirement {
  id: string
  control_id: string
  title: string
  description: string
  status: 'compliant' | 'non_compliant' | 'partial' | 'not_applicable'
  evidence: string[]
  remediation_steps: string[]
  assigned_to?: string
  due_date?: string
}

export interface ComplianceReport {
  id: string
  framework: string
  tenant_id: string
  report_period: string
  generated_at: string
  compliance_score: number
  findings: ComplianceFinding[]
  recommendations: string[]
  status: 'draft' | 'final' | 'approved'
}

export interface ComplianceFinding {
  control_id: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  description: string
  evidence: any[]
  remediation_required: boolean
  estimated_effort: string
}

export interface AuditLog {
  id: string
  tenant_id: string
  user_id: string
  action: string
  resource: string
  resource_id: string
  timestamp: string
  ip_address: string
  user_agent: string
  result: 'success' | 'failure'
  details: Record<string, any>
}

export interface Integration {
  id: string
  name: string
  type: 'siem' | 'itsm' | 'communication' | 'analytics' | 'security'
  provider: string
  status: 'active' | 'inactive' | 'error' | 'configuring'
  configuration: Record<string, any>
  health_status: 'healthy' | 'degraded' | 'unhealthy'
  last_sync: string
  sync_frequency: string
  created_at: string
}

export interface SSOConfig {
  id: string
  tenant_id: string
  provider: 'saml' | 'oidc' | 'ldap'
  provider_name: string
  enabled: boolean
  configuration: {
    identity_provider_url?: string
    client_id?: string
    client_secret?: string
    certificate?: string
    attribute_mapping: Record<string, string>
  }
  default_role: string
  auto_provision_users: boolean
  created_at: string
  last_used: string
}

export interface BackupPolicy {
  id: string
  tenant_id: string
  name: string
  frequency: 'hourly' | 'daily' | 'weekly' | 'monthly'
  retention_days: number
  backup_location: string
  encryption_enabled: boolean
  compression_enabled: boolean
  status: 'active' | 'paused' | 'failed'
  last_backup: string
  next_backup: string
}

// Enterprise API client
export class EnterpriseApi {
  // Compliance Management
  /**
   * List Compliance Frameworks
   * GET /v1/enterprise/compliance/frameworks
   */
  static async getComplianceFrameworks(tenantId: string): Promise<ApiResponse<ComplianceFramework[]>> {
    return apiClient.get('/v1/enterprise/compliance/frameworks', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Get Compliance Framework Details
   * GET /v1/enterprise/compliance/frameworks/{framework_id}
   */
  static async getComplianceFramework(frameworkId: string): Promise<ApiResponse<ComplianceFramework>> {
    return apiClient.get(`/v1/enterprise/compliance/frameworks/${frameworkId}`)
  }

  /**
   * Update Compliance Requirement
   * PUT /v1/enterprise/compliance/requirements/{requirement_id}
   */
  static async updateComplianceRequirement(
    requirementId: string, 
    updates: Partial<ComplianceRequirement>
  ): Promise<ApiResponse<ComplianceRequirement>> {
    return apiClient.put(`/v1/enterprise/compliance/requirements/${requirementId}`, updates)
  }

  /**
   * Generate Compliance Report
   * POST /v1/enterprise/compliance/reports
   */
  static async generateComplianceReport(reportData: {
    framework: string
    tenant_id: string
    period: string
    include_evidence: boolean
  }): Promise<ApiResponse<ComplianceReport>> {
    return apiClient.post('/v1/enterprise/compliance/reports', reportData)
  }

  /**
   * List Compliance Reports
   * GET /v1/enterprise/compliance/reports
   */
  static async getComplianceReports(params?: {
    framework?: string
    status?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<ComplianceReport>> {
    return apiClient.getPaginated('/v1/enterprise/compliance/reports', params)
  }

  // Audit Logging
  /**
   * Get Audit Logs
   * GET /v1/enterprise/audit-logs
   */
  static async getAuditLogs(params?: {
    tenant_id?: string
    user_id?: string
    action?: string
    resource?: string
    start_date?: string
    end_date?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<AuditLog>> {
    return apiClient.getPaginated('/v1/enterprise/audit-logs', params)
  }

  /**
   * Export Audit Logs
   * POST /v1/enterprise/audit-logs/export
   */
  static async exportAuditLogs(params: {
    format: 'csv' | 'json' | 'syslog'
    tenant_id?: string
    start_date: string
    end_date: string
    filters?: Record<string, any>
  }): Promise<ApiResponse<{
    export_id: string
    download_url: string
    expires_at: string
  }>> {
    return apiClient.post('/v1/enterprise/audit-logs/export', params)
  }

  // SSO Configuration
  /**
   * List SSO Configurations
   * GET /v1/enterprise/sso/configs
   */
  static async getSSOConfigs(tenantId: string): Promise<ApiResponse<SSOConfig[]>> {
    return apiClient.get('/v1/enterprise/sso/configs', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Create SSO Configuration
   * POST /v1/enterprise/sso/configs
   */
  static async createSSOConfig(
    tenantId: string, 
    ssoData: Omit<SSOConfig, 'id' | 'created_at' | 'last_used'>
  ): Promise<ApiResponse<SSOConfig>> {
    return apiClient.post('/v1/enterprise/sso/configs', ssoData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update SSO Configuration
   * PUT /v1/enterprise/sso/configs/{config_id}
   */
  static async updateSSOConfig(configId: string, updates: Partial<SSOConfig>): Promise<ApiResponse<SSOConfig>> {
    return apiClient.put(`/v1/enterprise/sso/configs/${configId}`, updates)
  }

  /**
   * Test SSO Configuration
   * POST /v1/enterprise/sso/configs/{config_id}/test
   */
  static async testSSOConfig(configId: string): Promise<ApiResponse<{
    status: 'success' | 'failed'
    message: string
    test_details: Record<string, any>
  }>> {
    return apiClient.post(`/v1/enterprise/sso/configs/${configId}/test`)
  }

  // Integration Management
  /**
   * List Integrations
   * GET /v1/enterprise/integrations
   */
  static async getIntegrations(tenantId: string): Promise<ApiResponse<Integration[]>> {
    return apiClient.get('/v1/enterprise/integrations', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Create Integration
   * POST /v1/enterprise/integrations
   */
  static async createIntegration(
    tenantId: string, 
    integrationData: Omit<Integration, 'id' | 'created_at' | 'health_status' | 'last_sync'>
  ): Promise<ApiResponse<Integration>> {
    return apiClient.post('/v1/enterprise/integrations', integrationData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update Integration
   * PUT /v1/enterprise/integrations/{integration_id}
   */
  static async updateIntegration(integrationId: string, updates: Partial<Integration>): Promise<ApiResponse<Integration>> {
    return apiClient.put(`/v1/enterprise/integrations/${integrationId}`, updates)
  }

  /**
   * Test Integration
   * POST /v1/enterprise/integrations/{integration_id}/test
   */
  static async testIntegration(integrationId: string): Promise<ApiResponse<{
    status: 'success' | 'failed'
    latency_ms: number
    error_message?: string
    last_tested: string
  }>> {
    return apiClient.post(`/v1/enterprise/integrations/${integrationId}/test`)
  }

  /**
   * Sync Integration
   * POST /v1/enterprise/integrations/{integration_id}/sync
   */
  static async syncIntegration(integrationId: string): Promise<ApiResponse<{
    sync_id: string
    status: 'started' | 'completed' | 'failed'
    records_synced: number
  }>> {
    return apiClient.post(`/v1/enterprise/integrations/${integrationId}/sync`)
  }

  // Backup & Recovery
  /**
   * List Backup Policies
   * GET /v1/enterprise/backup/policies
   */
  static async getBackupPolicies(tenantId: string): Promise<ApiResponse<BackupPolicy[]>> {
    return apiClient.get('/v1/enterprise/backup/policies', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Create Backup Policy
   * POST /v1/enterprise/backup/policies
   */
  static async createBackupPolicy(
    tenantId: string, 
    policyData: Omit<BackupPolicy, 'id' | 'last_backup' | 'next_backup'>
  ): Promise<ApiResponse<BackupPolicy>> {
    return apiClient.post('/v1/enterprise/backup/policies', policyData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Execute Backup
   * POST /v1/enterprise/backup/execute/{policy_id}
   */
  static async executeBackup(policyId: string): Promise<ApiResponse<{
    backup_id: string
    status: 'started' | 'completed' | 'failed'
    estimated_completion: string
  }>> {
    return apiClient.post(`/v1/enterprise/backup/execute/${policyId}`)
  }

  /**
   * List Available Backups
   * GET /v1/enterprise/backup/list
   */
  static async listBackups(tenantId: string, params?: {
    policy_id?: string
    start_date?: string
    end_date?: string
  }): Promise<ApiResponse<Array<{
    backup_id: string
    policy_id: string
    created_at: string
    size_gb: number
    status: 'completed' | 'failed' | 'expired'
    retention_until: string
  }>>> {
    return apiClient.get('/v1/enterprise/backup/list', {
      params,
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Restore from Backup
   * POST /v1/enterprise/backup/restore/{backup_id}
   */
  static async restoreFromBackup(backupId: string, restoreOptions?: {
    target_location?: string
    selective_restore?: {
      date_range?: { start: string; end: string }
      services?: string[]
    }
  }): Promise<ApiResponse<{
    restore_id: string
    status: 'started' | 'completed' | 'failed'
    estimated_completion: string
  }>> {
    return apiClient.post(`/v1/enterprise/backup/restore/${backupId}`, restoreOptions)
  }

  // License & Feature Management
  /**
   * Get License Information
   * GET /v1/enterprise/license
   */
  static async getLicenseInfo(tenantId: string): Promise<ApiResponse<{
    license_key: string
    license_type: 'trial' | 'standard' | 'professional' | 'enterprise'
    features_enabled: string[]
    user_limit: number
    storage_limit_gb: number
    expires_at: string
    grace_period_days: number
    usage_metrics: Record<string, number>
  }>> {
    return apiClient.get('/v1/enterprise/license', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update License
   * PUT /v1/enterprise/license
   */
  static async updateLicense(tenantId: string, licenseKey: string): Promise<ApiResponse<{
    status: 'valid' | 'invalid' | 'expired'
    features_enabled: string[]
    effective_date: string
  }>> {
    return apiClient.put('/v1/enterprise/license', { license_key: licenseKey }, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  // Enterprise Analytics
  /**
   * Get Enterprise Metrics
   * GET /v1/enterprise/metrics
   */
  static async getEnterpriseMetrics(params?: {
    tenant_id?: string
    metric_type?: string
    period?: string
  }): Promise<ApiResponse<{
    tenant_metrics: Record<string, any>
    compliance_scores: Record<string, number>
    integration_health: Record<string, string>
    backup_status: Record<string, string>
    license_utilization: Record<string, number>
  }>> {
    return apiClient.get('/v1/enterprise/metrics', { params })
  }

  /**
   * Generate Enterprise Report
   * POST /v1/enterprise/reports
   */
  static async generateEnterpriseReport(reportData: {
    report_type: 'compliance' | 'security' | 'usage' | 'performance'
    tenant_id?: string
    period: string
    format: 'pdf' | 'csv' | 'json'
    include_recommendations: boolean
  }): Promise<ApiResponse<{
    report_id: string
    download_url: string
    expires_at: string
  }>> {
    return apiClient.post('/v1/enterprise/reports', reportData)
  }
}

export default EnterpriseApi