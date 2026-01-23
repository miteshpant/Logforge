/**
 * Security API Module
 *
 * APIs for security events, Sigma rules, threat intelligence, threat hunting
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface SecurityEvent {
  id: string
  event_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'open' | 'investigating' | 'resolved' | 'false_positive'
  timestamp: string
  source: string
  description: string
  indicators: {
    ips?: string[]
    domains?: string[]
    hashes?: string[]
    users?: string[]
  }
  mitre_tactics?: string[]
  mitre_techniques?: string[]
  sigma_rule_id?: string
  raw_log?: Record<string, any>
  assigned_to?: string
  resolution_notes?: string
}

export interface SigmaRule {
  id: string
  title: string
  description: string
  author?: string
  status: 'stable' | 'experimental' | 'deprecated'
  level: 'low' | 'medium' | 'high' | 'critical'
  logsource: {
    category?: string
    product?: string
    service?: string
  }
  detection: Record<string, any>
  falsepositives?: string[]
  tags?: string[]
  references?: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ThreatIntelIndicator {
  id: string
  type: 'ip' | 'domain' | 'hash' | 'email' | 'url'
  value: string
  threat_type: string
  confidence: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  first_seen: string
  last_seen: string
  tags?: string[]
  sources?: string[]
  context?: Record<string, any>
}

export interface SecurityDashboard {
  summary: {
    total_events: number
    critical_events: number
    open_investigations: number
    sigma_rules_active: number
  }
  recent_events: SecurityEvent[]
  top_threats: Array<{
    threat_type: string
    count: number
    severity: string
  }>
  mitre_coverage: Array<{
    tactic: string
    technique_count: number
  }>
}

export interface ThreatHuntingCampaign {
  id: string
  name: string
  description: string
  hypothesis: string
  status: 'planning' | 'active' | 'completed' | 'cancelled'
  created_by: string
  created_at: string
  completed_at?: string
  findings: Array<{
    finding_id: string
    description: string
    severity: string
    indicators: Record<string, any>
  }>
  hunt_query: string
  time_range: string
}

// ========== API FUNCTIONS ==========

/**
 * Get security dashboard overview
 */
export async function getSecurityDashboard(params?: {
  time_range?: string
}): Promise<ApiResponse<SecurityDashboard>> {
  return apiClient.get<SecurityDashboard>('/v1/security/dashboard', params)
}

/**
 * List security events
 */
export async function listSecurityEvents(params?: {
  severity?: string
  status?: string
  event_type?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<{ events: SecurityEvent[]; total: number }>> {
  return apiClient.get('/v1/security/events', params)
}

/**
 * Get security event by ID
 */
export async function getSecurityEvent(
  eventId: string
): Promise<ApiResponse<SecurityEvent>> {
  return apiClient.get<SecurityEvent>(`/v1/security/events/${eventId}`)
}

/**
 * Update security event status
 */
export async function updateEventStatus(
  eventId: string,
  status: SecurityEvent['status'],
  notes?: string
): Promise<ApiResponse<void>> {
  return apiClient.put(`/v1/security/events/${eventId}/status`, {
    status,
    resolution_notes: notes,
  })
}

/**
 * List Sigma rules
 */
export async function listSigmaRules(): Promise<
  ApiResponse<{ rules: SigmaRule[] }>
> {
  return apiClient.get('/v1/security/sigma-rules')
}

/**
 * Get Sigma rule by ID
 */
export async function getSigmaRule(
  ruleId: string
): Promise<ApiResponse<SigmaRule>> {
  return apiClient.get<SigmaRule>(`/v1/security/sigma-rules/${ruleId}`)
}

/**
 * Create Sigma rule
 */
export async function createSigmaRule(
  rule: Omit<SigmaRule, 'id' | 'created_at' | 'updated_at'>
): Promise<ApiResponse<SigmaRule>> {
  return apiClient.post<SigmaRule>('/v1/security/sigma-rules', rule)
}

/**
 * Update Sigma rule
 */
export async function updateSigmaRule(
  ruleId: string,
  rule: Partial<SigmaRule>
): Promise<ApiResponse<SigmaRule>> {
  return apiClient.put<SigmaRule>(`/v1/security/sigma-rules/${ruleId}`, rule)
}

/**
 * Delete Sigma rule
 */
export async function deleteSigmaRule(
  ruleId: string
): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/security/sigma-rules/${ruleId}`)
}

/**
 * Toggle Sigma rule status
 */
export async function toggleSigmaRule(
  ruleId: string
): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/security/sigma-rules/${ruleId}/toggle`)
}

/**
 * Test Sigma rule
 */
export async function testSigmaRule(
  rule: Partial<SigmaRule>
): Promise<ApiResponse<{ success: boolean; matches: number; sample_events: any[] }>> {
  return apiClient.post('/v1/security/sigma-rules/test', rule)
}

/**
 * Get threat intelligence feed
 */
export async function getThreatIntel(params?: {
  type?: string
  severity?: string
  limit?: number
}): Promise<ApiResponse<{ indicators: ThreatIntelIndicator[] }>> {
  return apiClient.get('/v1/security/threat-intel', params)
}

/**
 * Check threat indicator
 */
export async function checkIndicator(indicator: {
  type: string
  value: string
}): Promise<ApiResponse<{ is_threat: boolean; indicator?: ThreatIntelIndicator }>> {
  return apiClient.post('/v1/security/threat-intel/check', indicator)
}

/**
 * List threat hunting campaigns
 */
export async function listThreatHunts(): Promise<
  ApiResponse<{ campaigns: ThreatHuntingCampaign[] }>
> {
  return apiClient.get('/v1/security/threat-hunting')
}

/**
 * Get threat hunting campaign
 */
export async function getThreatHunt(
  campaignId: string
): Promise<ApiResponse<ThreatHuntingCampaign>> {
  return apiClient.get<ThreatHuntingCampaign>(
    `/v1/security/threat-hunting/${campaignId}`
  )
}

/**
 * Create threat hunting campaign
 */
export async function createThreatHunt(
  campaign: Omit<
    ThreatHuntingCampaign,
    'id' | 'created_at' | 'findings' | 'completed_at'
  >
): Promise<ApiResponse<ThreatHuntingCampaign>> {
  return apiClient.post<ThreatHuntingCampaign>(
    '/v1/security/threat-hunting',
    campaign
  )
}

/**
 * Execute threat hunt
 */
export async function executeThreatHunt(
  campaignId: string
): Promise<ApiResponse<{ campaign_id: string; status: string; events_found: number }>> {
  return apiClient.post(`/v1/security/threat-hunting/${campaignId}/execute`)
}

/**
 * Get MITRE ATT&CK coverage
 */
export async function getMitreCoverage(): Promise<
  ApiResponse<{
    total_techniques: number
    covered_techniques: number
    coverage_percentage: number
    tactics: Array<{
      tactic: string
      techniques: Array<{
        technique_id: string
        technique_name: string
        coverage: boolean
      }>
    }>
  }>
> {
  return apiClient.get('/v1/security/mitre-coverage')
}

/**
 * Stream security events via SSE
 * Returns a cleanup function to close the connection
 */
export async function streamSecurityEvents(
  onEvent: (event: {
    id?: string
    event_type?: string
    rule_id?: string
    rule_name?: string
    severity?: string
    description?: string
    timestamp?: string
    matched_fields?: Record<string, any>
    attack_techniques?: string[]
    mitre_technique?: string
    source_ip?: string
    target_ip?: string
    [key: string]: any
  }) => void,
  onError?: (error: Error) => void,
  options?: {
    severity?: string[]
  }
): Promise<() => void> {
  return apiClient.getStream(
    '/v1/stream/security',
    (data) => {
      // Apply severity filter if specified
      if (options?.severity && data.severity) {
        if (!options.severity.includes(data.severity)) {
          return // Skip events that don't match severity filter
        }
      }
      onEvent(data)
    },
    onError
  )
}

// Export all functions as a namespace
export const SecurityApi = {
  getSecurityDashboard,
  listSecurityEvents,
  getSecurityEvent,
  updateEventStatus,
  listSigmaRules,
  getSigmaRule,
  createSigmaRule,
  updateSigmaRule,
  deleteSigmaRule,
  toggleSigmaRule,
  testSigmaRule,
  getThreatIntel,
  checkIndicator,
  listThreatHunts,
  getThreatHunt,
  createThreatHunt,
  executeThreatHunt,
  getMitreCoverage,
  streamSecurityEvents,
}

export default SecurityApi
