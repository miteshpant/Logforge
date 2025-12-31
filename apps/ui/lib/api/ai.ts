/**
 * AI API Module
 *
 * APIs for anomaly detection, RCA, natural language queries, predictions
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface Anomaly {
  id: string
  anomaly_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  detected_at: string
  service?: string
  metric_name?: string
  baseline_value?: number
  current_value?: number
  deviation_score?: number
  confidence: number
  description: string
  affected_entities?: string[]
  recommended_actions?: string[]
  status: 'open' | 'investigating' | 'resolved' | 'false_positive'
}

export interface AnomalyDetectionRequest {
  metrics: Array<{
    type: string
    service: string
    weight: number
  }>
  time_range: string
  correlation_threshold: number
  algorithms: string[]
}

export interface AnomalyDetectionResponse {
  anomalies: Anomaly[]
  total_detected: number
  algorithm_used: string
  detection_time_ms: number
  summary: {
    critical: number
    high: number
    medium: number
    low: number
  }
}

export interface RootCauseAnalysis {
  id: string
  incident_id: string
  status: 'analyzing' | 'completed' | 'failed'
  root_cause?: {
    type: string
    description: string
    confidence: number
    evidence: Array<{
      timestamp: string
      event: string
      correlation_score: number
    }>
  }
  contributing_factors?: Array<{
    factor: string
    impact: number
    description: string
  }>
  timeline: Array<{
    timestamp: string
    event_type: string
    description: string
  }>
  recommendations?: string[]
  analysis_time_ms?: number
}

export interface NaturalLanguageQuery {
  query: string
  context?: string
  analysis_type?: 'logs' | 'metrics' | 'traces' | 'security'
}

export interface NaturalLanguageResponse {
  query_id: string
  interpretation: string
  generated_query: string
  results: any
  suggestions: string[]
  confidence: number
}

export interface Prediction {
  prediction_type: string
  target_metric: string
  predictions: Array<{
    timestamp: string
    predicted_value: number
    confidence_interval: {
      lower: number
      upper: number
    }
  }>
  accuracy_score: number
  model_used: string
}

// ========== API FUNCTIONS ==========

/**
 * Detect anomalies using multi-metric correlation
 */
export async function detectAnomalies(
  request: AnomalyDetectionRequest
): Promise<ApiResponse<AnomalyDetectionResponse>> {
  return apiClient.post<AnomalyDetectionResponse>(
    '/api/ai/anomalies/detect/multi-metric',
    request
  )
}

/**
 * Get anomaly detection history
 */
export async function getAnomalyHistory(params?: {
  time_range?: string
  severity?: string
  status?: string
  limit?: number
}): Promise<ApiResponse<{ anomalies: Anomaly[]; total: number }>> {
  return apiClient.get('/v1/ai/anomalies/history', params)
}

/**
 * Get anomaly by ID
 */
export async function getAnomaly(
  anomalyId: string
): Promise<ApiResponse<Anomaly>> {
  return apiClient.get<Anomaly>(`/v1/ai/anomalies/${anomalyId}`)
}

/**
 * Provide feedback on anomaly (true/false positive)
 */
export async function feedbackAnomaly(
  anomalyId: string,
  feedback: {
    is_valid: boolean
    notes?: string
  }
): Promise<ApiResponse<void>> {
  return apiClient.post(`/v1/ai/anomalies/${anomalyId}/feedback`, feedback)
}

/**
 * Perform root cause analysis on an incident
 */
export async function analyzeRootCause(incident: {
  incident_id: string
  start_time: string
  end_time: string
  affected_services: string[]
  symptoms: string[]
}): Promise<ApiResponse<RootCauseAnalysis>> {
  return apiClient.post<RootCauseAnalysis>('/v1/ai/rca/analyze', incident)
}

/**
 * Get RCA result by incident ID
 */
export async function getRootCauseAnalysis(
  incidentId: string
): Promise<ApiResponse<RootCauseAnalysis>> {
  return apiClient.get<RootCauseAnalysis>(`/v1/ai/rca/${incidentId}`)
}

/**
 * Query logs/metrics using natural language
 */
export async function queryNaturalLanguage(
  query: NaturalLanguageQuery
): Promise<ApiResponse<NaturalLanguageResponse>> {
  return apiClient.post<NaturalLanguageResponse>('/v1/ai/query', query)
}

/**
 * Get query suggestions based on context
 */
export async function getQuerySuggestions(params?: {
  context?: string
  limit?: number
}): Promise<ApiResponse<{ suggestions: string[] }>> {
  return apiClient.get('/v1/ai/query/suggestions', params)
}

/**
 * Predict resource usage
 */
export async function predictResourceUsage(params: {
  metric: string
  service?: string
  time_horizon: string
}): Promise<ApiResponse<Prediction>> {
  return apiClient.post<Prediction>('/v1/ai/predict/resource-usage', params)
}

/**
 * Predict future anomalies
 */
export async function predictAnomalies(params: {
  service?: string
  metric?: string
  time_horizon: string
}): Promise<ApiResponse<Prediction>> {
  return apiClient.post<Prediction>('/v1/ai/predict/anomalies', params)
}

/**
 * Get AI model performance metrics
 */
export async function getModelPerformance(): Promise<
  ApiResponse<{
    models: Array<{
      model_name: string
      accuracy: number
      precision: number
      recall: number
      f1_score: number
      last_trained: string
    }>
  }>
> {
  return apiClient.get('/v1/ai/models/performance')
}

/**
 * Train or retrain AI model
 */
export async function trainModel(params: {
  model_type: string
  training_data_range: string
  hyperparameters?: Record<string, any>
}): Promise<ApiResponse<{ job_id: string; status: string }>> {
  return apiClient.post('/v1/ai/models/train', params)
}

// Export all functions as a namespace
export const AiApi = {
  detectAnomalies,
  getAnomalyHistory,
  getAnomaly,
  feedbackAnomaly,
  analyzeRootCause,
  getRootCauseAnalysis,
  queryNaturalLanguage,
  getQuerySuggestions,
  predictResourceUsage,
  predictAnomalies,
  getModelPerformance,
  trainModel,
}

export default AiApi
