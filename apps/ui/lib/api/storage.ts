/**
 * Storage API Client
 * 15+ endpoints for storage management, archival, and optimization
 * Based on: /docs/wiki/knowledge_base/devDocs/Storage-Router-API-Documentation.md
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Storage types
export interface StorageInfo {
  tenant_id: string
  total_storage_gb: number
  used_storage_gb: number
  available_storage_gb: number
  storage_usage_percentage: number
  hot_storage_gb: number
  cold_storage_gb: number
  archived_storage_gb: number
  compression_ratio: number
  retention_policy: RetentionPolicy
  last_updated: string
}

export interface RetentionPolicy {
  hot_retention_days: number
  cold_retention_days: number
  archive_retention_days: number
  auto_delete_after_days: number
  compliance_hold: boolean
  legal_hold_enabled: boolean
}

export interface StorageLocation {
  id: string
  name: string
  type: 'hot' | 'cold' | 'archive'
  provider: 'clickhouse' | 's3' | 'gcs' | 'azure' | 'minio'
  region: string
  bucket_name?: string
  connection_status: 'connected' | 'disconnected' | 'error'
  capacity_gb: number
  used_gb: number
  latency_ms: number
  cost_per_gb: number
}

export interface StorageStats {
  tenant_id: string
  period: string
  ingestion_volume_gb: number
  compression_savings_gb: number
  tiering_savings_gb: number
  total_cost: number
  cost_breakdown: {
    hot_storage_cost: number
    cold_storage_cost: number
    archive_cost: number
    data_transfer_cost: number
  }
  performance_metrics: {
    avg_query_latency_ms: number
    cache_hit_rate: number
    compression_rate: number
  }
}

export interface ArchiveJob {
  id: string
  tenant_id: string
  job_type: 'archive' | 'restore' | 'delete'
  status: 'pending' | 'running' | 'completed' | 'failed'
  source_location: string
  target_location?: string
  data_size_gb: number
  progress_percentage: number
  estimated_completion: string
  created_at: string
  completed_at?: string
  error_message?: string
}

export interface DataLifecycleRule {
  id: string
  name: string
  tenant_id: string
  conditions: {
    age_days?: number
    log_level?: string[]
    service_name?: string[]
    size_threshold_gb?: number
  }
  actions: {
    move_to_cold?: boolean
    move_to_archive?: boolean
    delete?: boolean
    compress?: boolean
  }
  enabled: boolean
  created_at: string
  last_executed: string
  records_processed: number
}

// Storage API client
export class StorageApi {
  /**
   * Get Storage Information
   * GET /v1/storage/{tenant_id}/info
   */
  static async getStorageInfo(tenantId: string): Promise<ApiResponse<StorageInfo>> {
    return apiClient.get(`/v1/storage/${tenantId}/info`)
  }

  /**
   * Get Storage Statistics
   * GET /v1/storage/{tenant_id}/stats
   */
  static async getStorageStats(tenantId: string, params?: {
    period?: 'daily' | 'weekly' | 'monthly'
    start_date?: string
    end_date?: string
  }): Promise<ApiResponse<StorageStats>> {
    return apiClient.get(`/v1/storage/${tenantId}/stats`, { params })
  }

  /**
   * Update Retention Policy
   * PUT /v1/storage/{tenant_id}/retention
   */
  static async updateRetentionPolicy(
    tenantId: string, 
    retentionPolicy: Partial<RetentionPolicy>
  ): Promise<ApiResponse<RetentionPolicy>> {
    return apiClient.put(`/v1/storage/${tenantId}/retention`, retentionPolicy)
  }

  /**
   * List Storage Locations
   * GET /v1/storage/{tenant_id}/locations
   */
  static async getStorageLocations(tenantId: string): Promise<ApiResponse<StorageLocation[]>> {
    return apiClient.get(`/v1/storage/${tenantId}/locations`)
  }

  /**
   * Add Storage Location
   * POST /v1/storage/{tenant_id}/locations
   */
  static async addStorageLocation(tenantId: string, locationData: {
    name: string
    type: 'hot' | 'cold' | 'archive'
    provider: 'clickhouse' | 's3' | 'gcs' | 'azure' | 'minio'
    region: string
    bucket_name?: string
    credentials: Record<string, string>
  }): Promise<ApiResponse<StorageLocation>> {
    return apiClient.post(`/v1/storage/${tenantId}/locations`, locationData)
  }

  /**
   * Update Storage Location
   * PUT /v1/storage/{tenant_id}/locations/{location_id}
   */
  static async updateStorageLocation(
    tenantId: string, 
    locationId: string, 
    updates: Partial<StorageLocation>
  ): Promise<ApiResponse<StorageLocation>> {
    return apiClient.put(`/v1/storage/${tenantId}/locations/${locationId}`, updates)
  }

  /**
   * Delete Storage Location
   * DELETE /v1/storage/{tenant_id}/locations/{location_id}
   */
  static async deleteStorageLocation(tenantId: string, locationId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/storage/${tenantId}/locations/${locationId}`)
  }

  /**
   * Test Storage Location Connection
   * POST /v1/storage/{tenant_id}/locations/{location_id}/test
   */
  static async testStorageConnection(tenantId: string, locationId: string): Promise<ApiResponse<{
    connection_status: 'success' | 'failed'
    latency_ms: number
    error_message?: string
    last_tested: string
  }>> {
    return apiClient.post(`/v1/storage/${tenantId}/locations/${locationId}/test`)
  }

  /**
   * Create Archive Job
   * POST /v1/storage/{tenant_id}/archive
   */
  static async createArchiveJob(tenantId: string, archiveData: {
    job_type: 'archive' | 'restore' | 'delete'
    source_location: string
    target_location?: string
    filters?: {
      start_date?: string
      end_date?: string
      log_levels?: string[]
      services?: string[]
    }
  }): Promise<ApiResponse<ArchiveJob>> {
    return apiClient.post(`/v1/storage/${tenantId}/archive`, archiveData)
  }

  /**
   * List Archive Jobs
   * GET /v1/storage/{tenant_id}/archive/jobs
   */
  static async listArchiveJobs(tenantId: string, params?: {
    status?: string
    job_type?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<ArchiveJob>> {
    return apiClient.getPaginated(`/v1/storage/${tenantId}/archive/jobs`, params)
  }

  /**
   * Get Archive Job Status
   * GET /v1/storage/{tenant_id}/archive/jobs/{job_id}
   */
  static async getArchiveJob(tenantId: string, jobId: string): Promise<ApiResponse<ArchiveJob>> {
    return apiClient.get(`/v1/storage/${tenantId}/archive/jobs/${jobId}`)
  }

  /**
   * Cancel Archive Job
   * DELETE /v1/storage/{tenant_id}/archive/jobs/{job_id}
   */
  static async cancelArchiveJob(tenantId: string, jobId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/storage/${tenantId}/archive/jobs/${jobId}`)
  }

  /**
   * List Data Lifecycle Rules
   * GET /v1/storage/{tenant_id}/lifecycle-rules
   */
  static async getLifecycleRules(tenantId: string): Promise<ApiResponse<DataLifecycleRule[]>> {
    return apiClient.get(`/v1/storage/${tenantId}/lifecycle-rules`)
  }

  /**
   * Create Data Lifecycle Rule
   * POST /v1/storage/{tenant_id}/lifecycle-rules
   */
  static async createLifecycleRule(
    tenantId: string, 
    ruleData: Omit<DataLifecycleRule, 'id' | 'created_at' | 'last_executed' | 'records_processed'>
  ): Promise<ApiResponse<DataLifecycleRule>> {
    return apiClient.post(`/v1/storage/${tenantId}/lifecycle-rules`, ruleData)
  }

  /**
   * Update Data Lifecycle Rule
   * PUT /v1/storage/{tenant_id}/lifecycle-rules/{rule_id}
   */
  static async updateLifecycleRule(
    tenantId: string, 
    ruleId: string, 
    updates: Partial<DataLifecycleRule>
  ): Promise<ApiResponse<DataLifecycleRule>> {
    return apiClient.put(`/v1/storage/${tenantId}/lifecycle-rules/${ruleId}`, updates)
  }

  /**
   * Delete Data Lifecycle Rule
   * DELETE /v1/storage/{tenant_id}/lifecycle-rules/{rule_id}
   */
  static async deleteLifecycleRule(tenantId: string, ruleId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/storage/${tenantId}/lifecycle-rules/${ruleId}`)
  }

  /**
   * Execute Lifecycle Rule
   * POST /v1/storage/{tenant_id}/lifecycle-rules/{rule_id}/execute
   */
  static async executeLifecycleRule(tenantId: string, ruleId: string): Promise<ApiResponse<{
    execution_id: string
    records_processed: number
    estimated_completion: string
  }>> {
    return apiClient.post(`/v1/storage/${tenantId}/lifecycle-rules/${ruleId}/execute`)
  }

  /**
   * Optimize Storage
   * POST /v1/storage/{tenant_id}/optimize
   */
  static async optimizeStorage(tenantId: string, options?: {
    compress_old_data?: boolean
    defragment_tables?: boolean
    update_statistics?: boolean
  }): Promise<ApiResponse<{
    optimization_id: string
    estimated_completion: string
    expected_space_savings_gb: number
  }>> {
    return apiClient.post(`/v1/storage/${tenantId}/optimize`, options)
  }

  /**
   * Get Storage Recommendations
   * GET /v1/storage/{tenant_id}/recommendations
   */
  static async getStorageRecommendations(tenantId: string): Promise<ApiResponse<Array<{
    type: 'cost_optimization' | 'performance' | 'retention' | 'archival'
    title: string
    description: string
    potential_savings_gb?: number
    potential_cost_savings?: number
    implementation_effort: 'low' | 'medium' | 'high'
    action_required: string
  }>>> {
    return apiClient.get(`/v1/storage/${tenantId}/recommendations`)
  }

  /**
   * Export Storage Report
   * POST /v1/storage/{tenant_id}/export
   */
  static async exportStorageReport(tenantId: string, params: {
    format: 'csv' | 'pdf' | 'json'
    include_locations: boolean
    include_lifecycle_rules: boolean
    include_archive_history: boolean
  }): Promise<ApiResponse<{
    report_id: string
    download_url: string
    expires_at: string
  }>> {
    return apiClient.post(`/v1/storage/${tenantId}/export`, params)
  }

  /**
   * Stream Storage Metrics
   * Stream: /v1/storage/{tenant_id}/stream
   */
  static async streamStorageMetrics(
    tenantId: string,
    onUpdate: (metrics: {
      storage_used_gb: number
      ingestion_rate_mb_per_minute: number
      query_latency_ms: number
      timestamp: string
    }) => void,
    onError?: (error: Error) => void
  ): Promise<() => void> {
    return apiClient.getStream(
      `/v1/storage/${tenantId}/stream`,
      onUpdate,
      onError
    )
  }
}

export default StorageApi