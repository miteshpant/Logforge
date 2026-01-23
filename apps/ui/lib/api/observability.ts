/**
 * Observability API Module
 *
 * APIs for service maps, APM, distributed tracing, metrics, and observability
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface ServiceNode {
  name: string
  type: 'web' | 'database' | 'cache' | 'queue' | 'external' | 'service'
  health_status: 'healthy' | 'warning' | 'critical' | 'unknown'
  metrics: {
    request_rate: number
    error_rate: number
    avg_latency: number
    apdex_score: number
  }
  environment: string
  version?: string
  dependencies?: string[]
}

export interface ServiceMap {
  services: ServiceNode[]
  metrics: {
    total_services: number
    total_requests: number
    overall_error_rate: number
    avg_response_time: number
  }
  timestamp: string
}

export interface Span {
  span_id: string
  trace_id: string
  parent_span_id?: string
  operation_name: string
  service_name: string
  start_time: string
  duration: number
  tags?: Record<string, any>
  logs?: Array<{
    timestamp: string
    fields: Record<string, any>
  }>
  status: 'success' | 'error'
}

export interface Trace {
  id: string
  operation_name: string
  service_name: string
  start_time: string
  duration: number
  status: 'success' | 'error' | 'timeout'
  spans: Span[]
  error?: string
}

export interface ApmSummary {
  overview: {
    total_requests: number
    avg_response_time: number
    error_rate: number
    throughput: number
  }
  top_services: Array<{
    service_name: string
    request_count: number
    avg_latency: number
    error_rate: number
  }>
  performance_trends: Array<{
    timestamp: string
    avg_latency: number
    request_count: number
  }>
}

export interface ErrorAnalysis {
  error_id: string
  error_type: string
  message: string
  service_name: string
  occurrence_count: number
  affected_users: number
  first_seen: string
  last_seen: string
  resolution_status: 'open' | 'investigating' | 'resolved' | 'ignored'
  stack_trace?: string
}

// ========== API FUNCTIONS ==========

/**
 * Get service map with dependencies
 */
export async function getServiceMap(
  timeRange: string = '1h'
): Promise<ApiResponse<ServiceMap>> {
  return apiClient.get<ServiceMap>('/v1/observability/service-map', {
    time_range: timeRange,
  })
}

/**
 * List all services
 */
export async function listServices(): Promise<ApiResponse<ServiceNode[]>> {
  return apiClient.get<ServiceNode[]>('/v1/observability/services')
}

/**
 * Get service details
 */
export async function getServiceDetails(
  serviceName: string
): Promise<ApiResponse<ServiceNode>> {
  return apiClient.get<ServiceNode>(`/v1/observability/services/${serviceName}`)
}

/**
 * Get APM overview statistics
 */
export async function getApmOverview(params: {
  start_time?: string
  end_time?: string
}): Promise<ApiResponse<ApmSummary>> {
  return apiClient.get<ApmSummary>('/v1/observability/apm/overview/stats', params)
}

/**
 * Search distributed traces
 */
export async function searchTraces(params: {
  service?: string
  operation?: string
  min_duration?: number
  max_duration?: number
  status?: string
  time_range?: string
  limit?: number
}): Promise<ApiResponse<Trace[]>> {
  return apiClient.post<Trace[]>('/v1/observability/traces/search', params)
}

/**
 * Get trace by ID
 */
export async function getTrace(traceId: string): Promise<ApiResponse<Trace>> {
  return apiClient.get<Trace>(`/v1/observability/traces/${traceId}`)
}

/**
 * Get error analysis
 */
export async function getErrorAnalysis(params: {
  time_range?: string
  service?: string
  status?: string
  limit?: number
}): Promise<ApiResponse<ErrorAnalysis[]>> {
  return apiClient.get<ErrorAnalysis[]>('/v1/observability/errors/analysis', params)
}

/**
 * Update error status
 */
export async function updateErrorStatus(
  errorId: string,
  status: ErrorAnalysis['resolution_status'],
  notes?: string
): Promise<ApiResponse<void>> {
  return apiClient.put(`/v1/observability/errors/${errorId}/status`, {
    status,
    notes,
  })
}

/**
 * Get observability overview stats (for centrum dashboard)
 */
export async function getObservabilityStats(params: {
  start_time: string
  end_time: string
}): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/observability/overview/stats', params)
}

/**
 * Get slowest endpoints
 */
export async function getSlowestEndpoints(params: {
  limit?: number
  start_time?: string
  end_time?: string
}): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/observability/apm/slowest-endpoints', params)
}

/**
 * Get service dependencies
 */
export async function getServiceDependencies(
  serviceName: string
): Promise<ApiResponse<{
  upstream: string[]
  downstream: string[]
  dependency_graph: Record<string, string[]>
}>> {
  return apiClient.get(`/v1/observability/services/${serviceName}/dependencies`)
}

/**
 * Stream metrics via SSE
 * Returns a cleanup function to close the connection
 */
export async function streamMetrics(
  metricNames: string[],
  onMetric: (metric: {
    metric_name?: string
    value?: number
    labels?: Record<string, string>
    timestamp?: string
    [key: string]: any
  }) => void,
  onError?: (error: Error) => void
): Promise<() => void> {
  // Note: metric filtering would need to be done server-side
  // For now, we stream all metrics and filter client-side
  return apiClient.getStream(
    '/v1/stream/metrics',
    (data) => {
      // Filter by metric names if specified
      if (metricNames.length > 0 && data.metric_name) {
        if (!metricNames.includes(data.metric_name)) {
          return // Skip metrics not in our filter list
        }
      }
      onMetric(data)
    },
    onError
  )
}

/**
 * Stream traces via SSE
 * Returns a cleanup function to close the connection
 */
export async function streamTraces(
  onTrace: (trace: {
    trace_id?: string
    span_id?: string
    operation_name?: string
    service_name?: string
    duration_ms?: number
    status?: string
    timestamp?: string
    [key: string]: any
  }) => void,
  onError?: (error: Error) => void
): Promise<() => void> {
  return apiClient.getStream('/v1/stream/traces', onTrace, onError)
}

// Export all functions as a namespace
export const ObservabilityApi = {
  getServiceMap,
  listServices,
  getServiceDetails,
  getApmOverview,
  searchTraces,
  getTrace,
  getErrorAnalysis,
  updateErrorStatus,
  getObservabilityStats,
  getSlowestEndpoints,
  getServiceDependencies,
  streamMetrics,
  streamTraces,
}

export default ObservabilityApi
