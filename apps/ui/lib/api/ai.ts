/**
 * AI API Module
 *
 * APIs for anomaly detection, RCA, natural language queries, predictions,
 * alert correlation, ML model management - Phase 3: AI Leadership
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

// Phase 3: Predictive Analytics types
export interface ForecastResponse {
  metric: string
  time_range: string
  forecast_horizon: string
  historical: Array<{ timestamp: string; value: number }>
  forecast: Array<{ timestamp: string; predicted_value: number; lower_bound: number; upper_bound: number }>
  trend: { direction: string; slope: number; confidence: number }
}

export interface SLABreachPrediction {
  services_at_risk: Array<{
    service: string
    current_error_rate: number
    predicted_breach_time: string
    confidence: number
    trend: string
    hours_until_breach: number
  }>
  total_at_risk: number
  sla_threshold: number
}

export interface CapacityPlanningResponse {
  daily_growth_rate: number
  current_daily_volume: number
  projected_30d_volume: number
  days_until_capacity: number
  top_growing_services: Array<{
    service: string
    daily_volume: number
    growth_rate: number
  }>
}

export interface WhatIfResponse {
  scenario_type: string
  baseline: Record<string, any>
  projected: Record<string, any>
  impact_summary: string
}

// Phase 3: Alert Correlation types
export interface AlertCorrelationGroup {
  group_id: string
  root_alert: Record<string, any>
  member_alerts: Array<Record<string, any>>
  correlation_score: number
  common_services: string[]
  suggested_root_cause: string
}

export interface AlertFatigueScore {
  fatigue_score: number
  alerts_per_hour: number
  duplicate_rate: number
  acknowledgment_rate: number
  avg_resolution_hours: number
  contributing_factors: string[]
  recommendations: string[]
}

export interface AlertTrend {
  time_series: Array<{
    timestamp: string
    total: number
    by_severity: Record<string, number>
  }>
  trend_direction: string
  period_comparison: { current: number; previous: number; change_percent: number }
}

// Phase 3: ML Model types
export interface ModelHealth {
  model_id: string
  name: string
  description: string
  status: string
  accuracy: number
  false_positive_rate: number
  false_negative_rate: number
  sample_count: number
  last_trained: string | null
  hours_since_training: number | null
  drift_score: number
  data_quality: string
  baseline_count: number
  needs_retraining: boolean
}

export interface BaselineVisualization {
  model_id: string
  baseline_type: string
  statistics: {
    mean: number
    std_dev: number
    min: number
    max: number
    p50: number
    p95: number
    p99: number
    sample_count: number
  }
  bands: {
    normal: { lower: number; upper: number }
    warning: { lower: number; upper: number }
    critical: { lower: number; upper: number }
  }
  accuracy: number
  last_trained: string
  is_active: number
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

// ========== PHASE 3: PREDICTIVE ANALYTICS ==========

/**
 * Get trend forecast for a metric
 */
export async function getForecast(params?: {
  metric?: string
  time_range?: string
  forecast_horizon?: string
}): Promise<ApiResponse<ForecastResponse>> {
  return apiClient.get('/v1/ai/predictions/forecast', params)
}

/**
 * Get capacity planning data
 */
export async function getCapacityPlanning(params?: {
  time_range?: string
}): Promise<ApiResponse<CapacityPlanningResponse>> {
  return apiClient.get('/v1/ai/predictions/capacity', params)
}

/**
 * Get SLA breach predictions
 */
export async function getSLABreachPredictions(params?: {
  time_range?: string
  sla_threshold?: number
}): Promise<ApiResponse<SLABreachPrediction>> {
  return apiClient.get('/v1/ai/predictions/sla-breach', params)
}

/**
 * Run what-if scenario
 */
export async function runWhatIfScenario(params: {
  scenario_type: string
  parameters: Record<string, any>
}): Promise<ApiResponse<WhatIfResponse>> {
  return apiClient.post('/v1/ai/predictions/what-if', params)
}

/**
 * Get predictions summary
 */
export async function getPredictionsSummary(): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/ai/predictions/summary')
}

// ========== PHASE 3: ALERT CORRELATION ==========

/**
 * Get correlated alert groups
 */
export async function getAlertCorrelationGroups(params?: {
  time_range?: string
  min_group_size?: number
}): Promise<ApiResponse<{ groups: AlertCorrelationGroup[]; total_groups: number }>> {
  return apiClient.get('/v1/alerts/correlation/groups', params)
}

/**
 * Get alert fatigue score
 */
export async function getAlertFatigueScore(): Promise<ApiResponse<AlertFatigueScore>> {
  return apiClient.get('/v1/alerts/correlation/fatigue-score')
}

/**
 * Get service dependency alerts
 */
export async function getServiceDependencyAlerts(): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/alerts/correlation/service-dependencies')
}

/**
 * Get duplicate alert detection
 */
export async function getDuplicateAlerts(params?: {
  time_range?: string
}): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/alerts/correlation/duplicates', params)
}

/**
 * Get alert trends
 */
export async function getAlertTrends(params?: {
  time_range?: string
  granularity?: string
}): Promise<ApiResponse<AlertTrend>> {
  return apiClient.get('/v1/alerts/correlation/trends', params)
}

/**
 * Get alert correlation summary
 */
export async function getAlertCorrelationSummary(): Promise<ApiResponse<any>> {
  return apiClient.get('/v1/alerts/correlation/summary')
}

// ========== PHASE 3: ML MODEL MANAGEMENT ==========

/**
 * Get model health status
 */
export async function getModelHealth(): Promise<
  ApiResponse<{ models: ModelHealth[]; summary: Record<string, any> }>
> {
  return apiClient.get('/v1/ai/models/health')
}

/**
 * Get baseline visualization data
 */
export async function getBaselineVisualization(params?: {
  service_name?: string
  metric_type?: string
}): Promise<ApiResponse<{ baselines: BaselineVisualization[]; total: number }>> {
  return apiClient.get('/v1/ai/models/baselines/visualization', params)
}

/**
 * Update anomaly thresholds
 */
export async function updateThresholds(params: {
  model_id: string
  thresholds: Record<string, any>
  reason?: string
}): Promise<ApiResponse<any>> {
  return apiClient.put('/v1/ai/models/thresholds', params)
}

/**
 * Retrain a model
 */
export async function retrainModel(params: {
  model_id: string
  training_days?: number
  force?: boolean
}): Promise<ApiResponse<any>> {
  return apiClient.post('/v1/ai/models/retrain', params)
}

/**
 * Get NL query history
 */
export async function getQueryHistory(params?: {
  limit?: number
}): Promise<ApiResponse<{ history: any[]; total: number }>> {
  return apiClient.get('/v1/ai/query/history', params)
}

/**
 * Submit query feedback
 */
export async function submitQueryFeedback(params: {
  query_id: string
  feedback_score: number
  feedback_notes?: string
}): Promise<ApiResponse<any>> {
  return apiClient.post('/v1/ai/query/feedback', params)
}

/**
 * Start AI investigation
 */
export async function startInvestigation(params: {
  title: string
  description: string
  incident_data: Record<string, any>
  context?: Record<string, any>
}): Promise<ApiResponse<any>> {
  return apiClient.post('/v1/ai/investigate', params)
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
  // Phase 3: Predictive Analytics
  getForecast,
  getCapacityPlanning,
  getSLABreachPredictions,
  runWhatIfScenario,
  getPredictionsSummary,
  // Phase 3: Alert Correlation
  getAlertCorrelationGroups,
  getAlertFatigueScore,
  getServiceDependencyAlerts,
  getDuplicateAlerts,
  getAlertTrends,
  getAlertCorrelationSummary,
  // Phase 3: ML Model Management
  getModelHealth,
  getBaselineVisualization,
  updateThresholds,
  retrainModel,
  // Phase 3: Investigation
  getQueryHistory,
  submitQueryFeedback,
  startInvestigation,
}

export default AiApi
