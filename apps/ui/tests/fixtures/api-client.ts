import { Page } from '@playwright/test'
import { GLOBAL_CONFIG } from './index'

/**
 * Enterprise API Client for E2E Testing
 * 
 * Provides comprehensive API testing capabilities:
 * - All Logforge API endpoints (15+ services)
 * - Authentication and session management
 * - Real data validation (no mocks)
 * - Performance monitoring
 * - Error handling and retries
 */

export class ApiClient {
  constructor(private page: Page) {}

  /**
   * Make authenticated API request
   */
  async makeRequest<T = any>(
    endpoint: string,
    options: {
      method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
      body?: any
      headers?: Record<string, string>
      timeout?: number
    } = {}
  ): Promise<{
    success: boolean
    data?: T
    status: number
    headers: Record<string, string>
    timing: number
  }> {
    const startTime = Date.now()
    
    try {
      const response = await this.page.request.fetch(
        `${GLOBAL_CONFIG.API_BASE_URL}${endpoint}`,
        {
          method: options.method || 'GET',
          data: options.body,
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            ...options.headers
          },
          timeout: options.timeout || GLOBAL_CONFIG.TIMEOUT.MEDIUM
        }
      )

      const timing = Date.now() - startTime
      const responseHeaders: Record<string, string> = {}
      
      // Extract response headers
      for (const [key, value] of Object.entries(response.headers())) {
        responseHeaders[key] = value
      }

      let data: T | undefined
      try {
        data = await response.json()
      } catch {
        // Response may not be JSON
      }

      return {
        success: response.ok(),
        data,
        status: response.status(),
        headers: responseHeaders,
        timing
      }
    } catch (error) {
      return {
        success: false,
        status: 0,
        headers: {},
        timing: Date.now() - startTime
      }
    }
  }

  // ========== AUTHENTICATION API ==========
  
  async login(email: string, password: string) {
    return this.makeRequest('/v1/auth/login', {
      method: 'POST',
      body: { email, password }
    })
  }

  async logout() {
    return this.makeRequest('/v1/auth/logout', {
      method: 'POST'
    })
  }

  async getProfile() {
    return this.makeRequest('/v1/auth/profile')
  }

  // ========== DASHBOARD API ==========

  async getDashboards() {
    return this.makeRequest('/v1/dashboards')
  }

  async getDashboard(id: string) {
    return this.makeRequest(`/v1/dashboards/${id}`)
  }

  async getDashboardData(id: string, timeRange: string = '24h') {
    return this.makeRequest(`/v1/dashboards/${id}/data`, {
      method: 'POST',
      body: { time_range: timeRange }
    })
  }

  // ========== QUERY API ==========

  async executeQuery(query: {
    query_type: 'logs' | 'metrics' | 'traces'
    filters?: any
    limit?: number
    time_range?: string
  }) {
    return this.makeRequest('/v1/query/advanced', {
      method: 'POST',
      body: query,
      timeout: GLOBAL_CONFIG.TIMEOUT.LONG
    })
  }

  async getSavedQueries() {
    return this.makeRequest('/v1/query/saved')
  }

  // ========== SECURITY API ==========

  async getSecurityDashboard() {
    return this.makeRequest('/v1/security/dashboard')
  }

  async getSecurityEvents(params: {
    limit?: number
    severity?: string
    status?: string
    time_range?: string
  } = {}) {
    const queryParams = new URLSearchParams(params as Record<string, string>)
    return this.makeRequest(`/v1/security/events?${queryParams}`)
  }

  async getSigmaRules() {
    return this.makeRequest('/v1/security/sigma-rules')
  }

  async getThreatIntel() {
    return this.makeRequest('/v1/security/threat-intel')
  }

  async executeThreatHunt(campaign: any) {
    return this.makeRequest('/v1/security/threat-hunting', {
      method: 'POST',
      body: campaign
    })
  }

  // ========== ALERTS API ==========

  async getAlerts(params: {
    status?: string
    severity?: string
    limit?: number
  } = {}) {
    const queryParams = new URLSearchParams(params as Record<string, string>)
    return this.makeRequest(`/v1/alerts?${queryParams}`)
  }

  async getAlertRules() {
    return this.makeRequest('/v1/alerts/rules')
  }

  async createAlert(alert: any) {
    return this.makeRequest('/v1/alerts', {
      method: 'POST',
      body: alert
    })
  }

  async getAlertChannels() {
    return this.makeRequest('/v1/alerts/channels')
  }

  // ========== OBSERVABILITY API ==========

  async getTraces(params: {
    service?: string
    operation?: string
    limit?: number
    time_range?: string
  } = {}) {
    const queryParams = new URLSearchParams(params as Record<string, string>)
    return this.makeRequest(`/v1/observability/traces?${queryParams}`)
  }

  async getServiceMap() {
    return this.makeRequest('/v1/observability/service-map')
  }

  async getMetrics(params: {
    metric_name?: string
    service?: string
    time_range?: string
  } = {}) {
    const queryParams = new URLSearchParams(params as Record<string, string>)
    return this.makeRequest(`/v1/observability/metrics?${queryParams}`)
  }

  async getApmSummary() {
    return this.makeRequest('/v1/observability/apm/summary')
  }

  // ========== AI API ==========

  async queryAI(query: {
    query: string
    context?: string
    analysis_type?: string
  }) {
    return this.makeRequest('/v1/ai/query', {
      method: 'POST',
      body: query,
      timeout: GLOBAL_CONFIG.TIMEOUT.EXTRA_LONG
    })
  }

  async getRootCauseAnalysis(incident_id: string) {
    return this.makeRequest(`/v1/ai/rca/${incident_id}`)
  }

  async getAnomalyDetection(params: {
    time_range?: string
    service?: string
  } = {}) {
    const queryParams = new URLSearchParams(params as Record<string, string>)
    return this.makeRequest(`/v1/ai/anomaly-detection?${queryParams}`)
  }

  // ========== INGESTION API ==========

  async ingestLog(log: any) {
    return this.makeRequest('/v1/ingest/single', {
      method: 'POST',
      body: log
    })
  }

  async batchIngestLogs(logs: any[]) {
    return this.makeRequest('/v1/ingest/batch', {
      method: 'POST',
      body: { logs }
    })
  }

  // ========== USERS API ==========

  async getUsers() {
    return this.makeRequest('/v1/users')
  }

  async createUser(user: any) {
    return this.makeRequest('/v1/users', {
      method: 'POST',
      body: user
    })
  }

  // ========== TENANTS API ==========

  async getTenants() {
    return this.makeRequest('/v1/tenants')
  }

  async getTenantUsage(tenantId: string) {
    return this.makeRequest(`/v1/tenants/${tenantId}/usage`)
  }

  // ========== USAGE API ==========

  async getCurrentUsage() {
    return this.makeRequest('/v1/usage/current')
  }

  async getBillingEstimate() {
    return this.makeRequest('/v1/usage/billing/estimate')
  }

  // ========== STORAGE API ==========

  async getStorageInfo() {
    return this.makeRequest('/v1/storage/info')
  }

  async getRetentionPolicies() {
    return this.makeRequest('/v1/storage/retention')
  }

  // ========== ENTERPRISE API ==========

  async getComplianceReports() {
    return this.makeRequest('/v1/enterprise/compliance/reports')
  }

  async getAuditLogs() {
    return this.makeRequest('/v1/enterprise/audit-logs')
  }

  async getIntegrations() {
    return this.makeRequest('/v1/enterprise/integrations')
  }

  // ========== HEALTH CHECK ==========

  async healthCheck() {
    return this.makeRequest('/v1/health')
  }

  // ========== UTILITY METHODS ==========

  /**
   * Validate that response contains real data (not mocked)
   */
  validateRealData(data: any): boolean {
    if (!data) return false
    
    // Check for common mock patterns
    const dataStr = JSON.stringify(data).toLowerCase()
    const mockPatterns = ['mock', 'test', 'sample', 'demo', 'fake']
    
    return !mockPatterns.some(pattern => dataStr.includes(pattern))
  }

  /**
   * Wait for API to be ready
   */
  async waitForApiReady(timeout: number = 30000): Promise<boolean> {
    const startTime = Date.now()
    
    while (Date.now() - startTime < timeout) {
      try {
        const response = await this.healthCheck()
        if (response.success) {
          return true
        }
      } catch {
        // Continue waiting
      }
      
      await this.page.waitForTimeout(1000)
    }
    
    return false
  }

  /**
   * Measure API performance
   */
  async measurePerformance<T>(
    apiCall: () => Promise<T>
  ): Promise<{ result: T; timing: number; isPerformant: boolean }> {
    const startTime = Date.now()
    const result = await apiCall()
    const timing = Date.now() - startTime
    
    return {
      result,
      timing,
      isPerformant: timing <= GLOBAL_CONFIG.PERFORMANCE.API_RESPONSE_MAX
    }
  }
}