/**
 * Alerts API Module
 *
 * APIs for alert rules, instances, channels, and management
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface Alert {
  id: string
  rule_id: string
  rule_name: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'active' | 'resolved' | 'silenced' | 'acknowledged'
  triggered_at: string
  resolved_at?: string
  trigger_count: number
  description: string
  labels?: Record<string, string>
  annotations?: Record<string, string>
  triggered_by?: string
  resolution_notes?: string
}

export interface AlertRule {
  id: string
  name: string
  description: string
  query: string
  condition: string
  threshold: number
  severity: 'low' | 'medium' | 'high' | 'critical'
  enabled: boolean
  channels: string[]
  time_window: string
  evaluation_interval: string
  labels?: Record<string, string>
  annotations?: Record<string, string>
  created_at: string
  updated_at: string
}

export interface AlertChannel {
  id: string
  name: string
  type: 'email' | 'slack' | 'pagerduty' | 'webhook' | 'teams'
  config: Record<string, any>
  enabled: boolean
  created_at: string
}

export interface AlertTemplate {
  id: string
  name: string
  description: string
  template_type: 'error_rate' | 'latency' | 'resource' | 'custom'
  default_config: {
    query: string
    condition: string
    threshold: number
    time_window: string
  }
}

export interface AlertStats {
  total_alerts: number
  active_alerts: number
  critical_alerts: number
  alerts_today: number
  top_triggered_rules: Array<{
    rule_name: string
    trigger_count: number
  }>
}

// ========== API FUNCTIONS ==========

/**
 * List all alerts
 */
export async function listAlerts(params?: {
  status?: string
  severity?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<{ alerts: Alert[]; total: number }>> {
  return apiClient.get('/v1/alerts', params)
}

/**
 * Get alert by ID
 */
export async function getAlert(alertId: string): Promise<ApiResponse<Alert>> {
  return apiClient.get<Alert>(`/v1/alerts/${alertId}`)
}

/**
 * Acknowledge alert
 */
export async function acknowledgeAlert(
  alertId: string,
  notes?: string
): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/alerts/${alertId}/acknowledge`, { notes })
}

/**
 * Resolve alert
 */
export async function resolveAlert(
  alertId: string,
  resolutionNotes?: string
): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/alerts/${alertId}/resolve`, {
    resolution_notes: resolutionNotes,
  })
}

/**
 * Silence alert
 */
export async function silenceAlert(
  alertId: string,
  duration: string,
  reason?: string
): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/alerts/${alertId}/silence`, { duration, reason })
}

/**
 * List alert rules
 */
export async function listRules(): Promise<
  ApiResponse<{ rules: AlertRule[] }>
> {
  return apiClient.get('/v1/alerts/rules')
}

/**
 * Get alert rule
 */
export async function getRule(ruleId: string): Promise<ApiResponse<AlertRule>> {
  return apiClient.get<AlertRule>(`/v1/alerts/rules/${ruleId}`)
}

/**
 * Create alert rule
 */
export async function createRule(
  rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at'>
): Promise<ApiResponse<AlertRule>> {
  return apiClient.post<AlertRule>('/v1/alerts/rules', rule)
}

/**
 * Update alert rule
 */
export async function updateRule(
  ruleId: string,
  rule: Partial<AlertRule>
): Promise<ApiResponse<AlertRule>> {
  return apiClient.put<AlertRule>(`/v1/alerts/rules/${ruleId}`, rule)
}

/**
 * Delete alert rule
 */
export async function deleteRule(ruleId: string): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/alerts/rules/${ruleId}`)
}

/**
 * Toggle alert rule status
 */
export async function toggleRule(ruleId: string): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/alerts/rules/${ruleId}/toggle`)
}

/**
 * Test alert rule
 */
export async function testRule(
  rule: Partial<AlertRule>
): Promise<ApiResponse<{ success: boolean; matches: number; sample_events: any[] }>> {
  return apiClient.post('/v1/alerts/rules/test', rule)
}

/**
 * List alert channels
 */
export async function listChannels(): Promise<
  ApiResponse<{ channels: AlertChannel[] }>
> {
  return apiClient.get('/v1/alerts/channels')
}

/**
 * Create alert channel
 */
export async function createChannel(
  channel: Omit<AlertChannel, 'id' | 'created_at'>
): Promise<ApiResponse<AlertChannel>> {
  return apiClient.post<AlertChannel>('/v1/alerts/channels', channel)
}

/**
 * Update alert channel
 */
export async function updateChannel(
  channelId: string,
  channel: Partial<AlertChannel>
): Promise<ApiResponse<AlertChannel>> {
  return apiClient.put<AlertChannel>(`/v1/alerts/channels/${channelId}`, channel)
}

/**
 * Delete alert channel
 */
export async function deleteChannel(
  channelId: string
): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/alerts/channels/${channelId}`)
}

/**
 * Test alert channel
 */
export async function testChannel(
  channelId: string
): Promise<ApiResponse<{ success: boolean; message: string }>> {
  return apiClient.post(`/v1/alerts/channels/${channelId}/test`)
}

/**
 * List alert templates
 */
export async function listTemplates(): Promise<
  ApiResponse<{ templates: AlertTemplate[] }>
> {
  return apiClient.get('/v1/alerts/templates')
}

/**
 * Get alert template
 */
export async function getTemplate(
  templateId: string
): Promise<ApiResponse<AlertTemplate>> {
  return apiClient.get<AlertTemplate>(`/v1/alerts/templates/${templateId}`)
}

/**
 * Get alert statistics
 */
export async function getStats(
  timeRange: string = '24h'
): Promise<ApiResponse<AlertStats>> {
  return apiClient.get<AlertStats>('/v1/alerts/stats', { time_range: timeRange })
}

/**
 * Get alerts overview stats (for centrum dashboard)
 */
export async function getAlertsOverviewStats(params: {
  start_time: string
  end_time: string
}): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/alerts/stats/overview', params)
}

/**
 * Bulk acknowledge alerts
 */
export async function bulkAcknowledge(
  alertIds: string[],
  notes?: string
): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/alerts/bulk/acknowledge', {
    alert_ids: alertIds,
    notes,
  })
}

/**
 * Bulk resolve alerts
 */
export async function bulkResolve(
  alertIds: string[],
  resolutionNotes?: string
): Promise<ApiResponse<void>> {
  return apiClient.post('/v1/alerts/bulk/resolve', {
    alert_ids: alertIds,
    resolution_notes: resolutionNotes,
  })
}

// Export all functions as a namespace
export const AlertsApi = {
  listAlerts,
  getAlert,
  acknowledgeAlert,
  resolveAlert,
  silenceAlert,
  listRules,
  getRule,
  createRule,
  updateRule,
  deleteRule,
  toggleRule,
  testRule,
  listChannels,
  createChannel,
  updateChannel,
  deleteChannel,
  testChannel,
  listTemplates,
  getTemplate,
  getStats,
  getAlertsOverviewStats,
  bulkAcknowledge,
  bulkResolve,
}

export default AlertsApi
