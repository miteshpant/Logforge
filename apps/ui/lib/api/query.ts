/**
 * Query API Module
 *
 * APIs for advanced log queries, search, and filtering
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface QueryRequest {
  start_time: string
  end_time: string
  filters?: Array<{
    field: string
    operator: string
    value: any
  }>
  aggregations?: Array<{
    type: 'count' | 'sum' | 'avg' | 'min' | 'max' | 'unique' | 'cardinality'
    field: string
    alias: string
  }>
  group_by?: string[]
  limit?: number
  offset?: number
  sort?: Array<{
    field: string
    order: 'asc' | 'desc'
  }>
}

export interface QueryResponse {
  results: any[]
  total: number
  aggregations?: Record<string, any>
  execution_time_ms: number
  query_id?: string
}

export interface SavedQuery {
  id: string
  name: string
  description?: string
  query: QueryRequest
  created_by: string
  created_at: string
  updated_at: string
  tags?: string[]
}

// ========== API FUNCTIONS ==========

/**
 * Execute advanced query
 */
export async function executeAdvancedQuery(
  query: QueryRequest
): Promise<ApiResponse<QueryResponse>> {
  return apiClient.post<QueryResponse>('/v1/query/advanced', query)
}

/**
 * Get basic logs with simple filters
 */
export async function getLogs(params?: {
  service?: string
  level?: string
  limit?: number
  offset?: number
  start_time?: string
  end_time?: string
}): Promise<ApiResponse<{ logs: any[]; total: number }>> {
  return apiClient.get('/v1/logs', params)
}

/**
 * Search logs with full-text search
 */
export async function searchLogs(params: {
  query: string
  start_time?: string
  end_time?: string
  limit?: number
}): Promise<ApiResponse<{ logs: any[]; total: number }>> {
  return apiClient.post('/v1/query/search', params)
}

/**
 * List saved queries
 */
export async function listSavedQueries(): Promise<
  ApiResponse<{ queries: SavedQuery[] }>
> {
  return apiClient.get('/v1/query/saved')
}

/**
 * Create saved query
 */
export async function createSavedQuery(
  query: Omit<SavedQuery, 'id' | 'created_at' | 'updated_at'>
): Promise<ApiResponse<SavedQuery>> {
  return apiClient.post<SavedQuery>('/v1/query/saved', query)
}

/**
 * Get saved query
 */
export async function getSavedQuery(
  queryId: string
): Promise<ApiResponse<SavedQuery>> {
  return apiClient.get<SavedQuery>(`/v1/query/saved/${queryId}`)
}

/**
 * Execute saved query
 */
export async function executeSavedQuery(
  queryId: string,
  params?: {
    start_time?: string
    end_time?: string
  }
): Promise<ApiResponse<QueryResponse>> {
  return apiClient.post<QueryResponse>(`/v1/query/saved/${queryId}/execute`, params)
}

/**
 * Delete saved query
 */
export async function deleteSavedQuery(
  queryId: string
): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/query/saved/${queryId}`)
}

// Export all functions as a namespace
export const QueryApi = {
  executeAdvancedQuery,
  getLogs,
  searchLogs,
  listSavedQueries,
  createSavedQuery,
  getSavedQuery,
  executeSavedQuery,
  deleteSavedQuery,
}

export default QueryApi
