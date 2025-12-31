/**
 * Usage API Module
 *
 * APIs for usage statistics, billing, and storage management
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface UsageStats {
  data_ingested_gb: number
  data_stored_gb: number
  requests_count: number
  compute_hours: number
  estimated_cost: number
  period_start: string
  period_end: string
}

export interface StorageInfo {
  total_storage_gb: number
  used_storage_gb: number
  available_storage_gb: number
  retention_days: number
  compression_ratio: number
}

// ========== API FUNCTIONS ==========

/**
 * Get usage overview stats (for centrum dashboard)
 */
export async function getUsageOverviewStats(params: {
  start_time: string
  end_time: string
}): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/usage/overview/stats', params)
}

/**
 * Get current usage statistics
 */
export async function getCurrentUsage(): Promise<ApiResponse<UsageStats>> {
  return apiClient.get<UsageStats>('/v1/usage/current')
}

/**
 * Get billing estimate
 */
export async function getBillingEstimate(): Promise<
  ApiResponse<{
    current_period: UsageStats
    projected_cost: number
    cost_breakdown: Record<string, number>
  }>
> {
  return apiClient.get('/v1/usage/billing/estimate')
}

/**
 * Get storage information
 */
export async function getStorageInfo(): Promise<ApiResponse<StorageInfo>> {
  return apiClient.get<StorageInfo>('/v1/storage/info')
}

/**
 * Get retention policies
 */
export async function getRetentionPolicies(): Promise<
  ApiResponse<{
    policies: Array<{
      data_type: string
      retention_days: number
      compression_enabled: boolean
    }>
  }>
> {
  return apiClient.get('/v1/storage/retention')
}

// Export all functions as a namespace
export const UsageApi = {
  getUsageOverviewStats,
  getCurrentUsage,
  getBillingEstimate,
  getStorageInfo,
  getRetentionPolicies,
}

export default UsageApi
