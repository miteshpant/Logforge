'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'

interface AffectedMetric {
  metric: string
  baseline: number
  current: number
  deviation: number
  contribution_score: number
}

interface DetectedAnomaly {
  anomaly_id: string
  detected_at: string
  title: string
  severity: string
  confidence: number
  affected_metrics: AffectedMetric[]
  correlation_score: number
  root_cause_hints: string[]
  recommended_actions: string[]
}

interface AnomalyStats {
  total_anomalies: number
  critical_anomalies: number
  active_investigations: number
  detection_accuracy: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  top_affected_services: string[]
  trend: string
}

interface AnalysisResult {
  anomaly_id: string
  analysis_id: string
  root_cause: {
    type: string
    confidence: number
    description: string
  }
  contributing_factors: Array<{ factor: string; impact: string }>
  recommended_actions: Array<{ action: string; priority: string }>
}

export default function AnomalyDetectionPage() {
  const { currentTimeRange } = useTimeRange()
  const [anomalies, setAnomalies] = useState<DetectedAnomaly[]>([])
  const [stats, setStats] = useState<AnomalyStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedAnomaly, setSelectedAnomaly] = useState<DetectedAnomaly | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)
  const [dismissingId, setDismissingId] = useState<string | null>(null)
  const [severityFilter, setSeverityFilter] = useState<string>('all')

  const fetchStats = async () => {
    try {
      const response = await apiClient.get<AnomalyStats>('/v1/ai/anomalies/stats', {
        time_range: currentTimeRange.value
      })
      const data = response?.data || response
      if (data && typeof data === 'object') {
        setStats(data as AnomalyStats)
      }
    } catch (err) {
      console.error('Failed to fetch anomaly stats:', err)
    }
  }

  const fetchAnomalies = async () => {
    setLoading(true)
    setError(null)

    try {
      const [detectRes] = await Promise.allSettled([
        apiClient.post<{ anomalies: DetectedAnomaly[]; total_detected: number }>('/v1/ai/anomalies/detect/multi-metric', {
          metrics: [
            { type: 'cpu_usage', service: 'payment-service', weight: 1.0 },
            { type: 'memory_usage', service: 'payment-service', weight: 0.9 },
            { type: 'error_rate', service: 'payment-service', weight: 0.8 },
            { type: 'latency_p99', service: 'api-gateway', weight: 0.85 },
            { type: 'request_rate', service: 'api-gateway', weight: 0.7 }
          ],
          time_range: currentTimeRange.value,
          correlation_threshold: 0.6,
          algorithms: ['z_score', 'isolation_forest']
        })
      ])

      if (detectRes.status === 'fulfilled') {
        const data = detectRes.value?.data || detectRes.value
        const detected = (data as any)?.anomalies || []
        setAnomalies(detected)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch anomalies')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnomalies()
    fetchStats()
  }, [currentTimeRange.value])

  const handleAnalyze = async (anomalyId: string) => {
    setAnalyzingId(anomalyId)
    try {
      const response = await apiClient.post<AnalysisResult>(`/v1/ai/anomalies/${anomalyId}/analyze`, {
        analysis_depth: 'comprehensive',
        include_similar_incidents: true,
        time_window_expansion: '1h'
      })
      const data = response?.data || response
      if (data) {
        setAnalysisResult(data as AnalysisResult)
      }
    } catch (err) {
      console.error('Failed to analyze anomaly:', err)
    } finally {
      setAnalyzingId(null)
    }
  }

  const handleDismiss = async (anomalyId: string) => {
    setDismissingId(anomalyId)
    try {
      await apiClient.post(`/v1/ai/anomalies/${anomalyId}/dismiss`, {
        reason: 'Reviewed and determined as expected behavior'
      })
      setAnomalies(prev => prev.filter(a => a.anomaly_id !== anomalyId))
      if (selectedAnomaly?.anomaly_id === anomalyId) {
        setSelectedAnomaly(null)
        setAnalysisResult(null)
      }
    } catch (err) {
      console.error('Failed to dismiss anomaly:', err)
      // Still remove from UI for responsiveness
      setAnomalies(prev => prev.filter(a => a.anomaly_id !== anomalyId))
    } finally {
      setDismissingId(null)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'text-red-400 bg-red-500/10 border-red-500/30'
      case 'high': return 'text-orange-400 bg-orange-500/10 border-orange-500/30'
      case 'medium': return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30'
      case 'low': return 'text-blue-400 bg-blue-500/10 border-blue-500/30'
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/30'
    }
  }

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing': return { icon: '\u2191', color: 'text-red-400' }
      case 'decreasing': return { icon: '\u2193', color: 'text-green-400' }
      default: return { icon: '\u2194', color: 'text-slate-400' }
    }
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString()
  }

  const filteredAnomalies = anomalies.filter(a =>
    severityFilter === 'all' || a.severity?.toLowerCase() === severityFilter
  )

  const trendInfo = getTrendIcon(stats?.trend || 'stable')

  return (
    <DashboardLayout>
      <div className="min-h-screen bg-gradient-to-br from-slate-800/80 to-slate-900/95 p-6">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <span className="text-4xl">🤖</span>
              Intelligent Anomaly Detection
            </h1>
            <p className="text-slate-400 mt-2">
              AI-powered multi-metric correlation and anomaly detection
            </p>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-white/5 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            <button
              onClick={() => { fetchAnomalies(); fetchStats() }}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg flex items-center gap-2 transition-colors"
            >
              <svg
                className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              {loading ? 'Detecting...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-900/20 border border-red-800 rounded-lg p-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-white/5 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Total Anomalies</h3>
              <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats?.total_anomalies ?? anomalies.length}</p>
            <div className="flex items-center gap-1 mt-1">
              <span className={`text-xs ${trendInfo.color}`}>{trendInfo.icon}</span>
              <p className="text-xs text-slate-500">{stats?.trend || 'stable'} trend</p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-white/5 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Critical</h3>
              <div className="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats?.critical_anomalies ?? anomalies.filter(a => a.severity === 'critical').length}</p>
            <p className="text-xs text-slate-500 mt-1">Require immediate attention</p>
          </div>

          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-white/5 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Investigations</h3>
              <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats?.active_investigations ?? 0}</p>
            <p className="text-xs text-slate-500 mt-1">Active investigations</p>
          </div>

          <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-white/5 rounded-lg p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-slate-400 text-sm font-medium">Accuracy</h3>
              <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <p className="text-3xl font-bold text-white">{stats?.detection_accuracy ?? 95}%</p>
            <p className="text-xs text-slate-500 mt-1">ML model confidence</p>
          </div>
        </div>

        {/* Category Breakdown & Top Services */}
        {stats && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* By Category */}
            {stats.by_category && Object.keys(stats.by_category).length > 0 && (
              <div className="bg-slate-800/50 border border-white/5 rounded-lg p-6">
                <h3 className="text-white font-semibold mb-4">Anomaly Categories</h3>
                <div className="space-y-3">
                  {Object.entries(stats.by_category).map(([category, count]) => {
                    const maxCount = Math.max(...Object.values(stats.by_category), 1)
                    const pct = (count / maxCount) * 100
                    return (
                      <div key={category}>
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="text-slate-300 capitalize">{category.replace(/_/g, ' ')}</span>
                          <span className="text-slate-400">{count}</span>
                        </div>
                        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Top Affected Services */}
            {stats.top_affected_services && stats.top_affected_services.length > 0 && (
              <div className="bg-slate-800/50 border border-white/5 rounded-lg p-6">
                <h3 className="text-white font-semibold mb-4">Top Affected Services</h3>
                <div className="space-y-2">
                  {stats.top_affected_services.map((service, idx) => (
                    <div
                      key={service}
                      className="flex items-center gap-3 p-3 bg-slate-900/50 rounded-lg border border-white/5"
                    >
                      <span className="text-slate-500 text-sm font-mono w-6">#{idx + 1}</span>
                      <div className="w-2 h-2 rounded-full bg-blue-500" />
                      <span className="text-slate-300 font-medium">{service}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Anomalies Table */}
        <div className="bg-slate-800/50 border border-white/5 rounded-lg overflow-hidden">
          <div className="p-6 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              Detected Anomalies
              {filteredAnomalies.length > 0 && (
                <span className="ml-2 text-sm font-normal text-slate-400">({filteredAnomalies.length})</span>
              )}
            </h2>
          </div>

          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="h-16 bg-slate-700/50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : filteredAnomalies.length === 0 ? (
            <div className="p-12 text-center">
              <svg className="w-12 h-12 text-slate-600 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-slate-400 font-medium">No anomalies detected</p>
              <p className="text-sm text-slate-500 mt-1">System is operating within normal parameters</p>
            </div>
          ) : (
            <div className="divide-y divide-white/5">
              {filteredAnomalies.map((anomaly) => (
                <div
                  key={anomaly.anomaly_id}
                  className={`p-4 hover:bg-slate-700/30 transition-colors cursor-pointer ${
                    selectedAnomaly?.anomaly_id === anomaly.anomaly_id ? 'bg-slate-700/40' : ''
                  }`}
                  onClick={() => {
                    setSelectedAnomaly(anomaly)
                    setAnalysisResult(null)
                  }}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(anomaly.severity)}`}>
                          {anomaly.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs text-slate-500">
                          {formatTimestamp(anomaly.detected_at)}
                        </span>
                        {anomaly.confidence && (
                          <span className="text-xs text-slate-500">
                            {Math.round(anomaly.confidence * 100)}% confidence
                          </span>
                        )}
                      </div>
                      <p className="text-white font-medium">{anomaly.title}</p>

                      {/* Affected Metrics */}
                      {anomaly.affected_metrics && anomaly.affected_metrics.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {anomaly.affected_metrics.slice(0, 3).map((m, idx) => (
                            <span key={idx} className="text-xs px-2 py-1 bg-slate-700 text-slate-300 rounded">
                              {m.metric}: {typeof m.current === 'number' ? m.current.toFixed(1) : m.current}
                              {typeof m.deviation === 'number' && (
                                <span className={m.deviation > 0 ? 'text-red-400' : 'text-green-400'}>
                                  {' '}({m.deviation > 0 ? '+' : ''}{m.deviation.toFixed(1)}%)
                                </span>
                              )}
                            </span>
                          ))}
                          {anomaly.affected_metrics.length > 3 && (
                            <span className="text-xs px-2 py-1 bg-slate-700 text-slate-500 rounded">
                              +{anomaly.affected_metrics.length - 3} more
                            </span>
                          )}
                        </div>
                      )}

                      {/* Root Cause Hints */}
                      {anomaly.root_cause_hints && anomaly.root_cause_hints.length > 0 && (
                        <p className="text-xs text-slate-500 mt-2 truncate">
                          Hint: {anomaly.root_cause_hints[0]}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleAnalyze(anomaly.anomaly_id) }}
                        disabled={analyzingId === anomaly.anomaly_id}
                        className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg transition-colors"
                      >
                        {analyzingId === anomaly.anomaly_id ? 'Analyzing...' : 'Analyze'}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDismiss(anomaly.anomaly_id) }}
                        disabled={dismissingId === anomaly.anomaly_id}
                        className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 text-slate-300 rounded-lg transition-colors"
                      >
                        {dismissingId === anomaly.anomaly_id ? 'Dismissing...' : 'Dismiss'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Analysis Detail Panel */}
        {selectedAnomaly && (
          <div className="mt-6 bg-slate-800/50 border border-white/5 rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Anomaly Detail</h3>
              <button
                onClick={() => { setSelectedAnomaly(null); setAnalysisResult(null) }}
                className="text-slate-400 hover:text-white"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Anomaly Info */}
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-2">Overview</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-500">Title</span>
                    <span className="text-sm text-white">{selectedAnomaly.title}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-500">Severity</span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(selectedAnomaly.severity)}`}>
                      {selectedAnomaly.severity?.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-500">Correlation Score</span>
                    <span className="text-sm text-white">{(selectedAnomaly.correlation_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-500">Detected</span>
                    <span className="text-sm text-white">{formatTimestamp(selectedAnomaly.detected_at)}</span>
                  </div>
                </div>

                {/* Recommended Actions */}
                {selectedAnomaly.recommended_actions && selectedAnomaly.recommended_actions.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-medium text-slate-400 mb-2">Recommended Actions</h4>
                    <div className="space-y-1">
                      {selectedAnomaly.recommended_actions.map((action, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-sm">
                          <span className="text-blue-400 mt-0.5">&#x2022;</span>
                          <span className="text-slate-300">{action}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Metric Details */}
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-2">Affected Metrics</h4>
                <div className="space-y-3">
                  {selectedAnomaly.affected_metrics?.map((metric, idx) => (
                    <div key={idx} className="p-3 bg-slate-900/50 rounded-lg border border-white/5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-white">{metric.metric}</span>
                        <span className="text-xs text-slate-500">
                          contribution: {(metric.contribution_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <span className="text-slate-500">Baseline</span>
                          <p className="text-slate-300">{typeof metric.baseline === 'number' ? metric.baseline.toFixed(2) : metric.baseline}</p>
                        </div>
                        <div>
                          <span className="text-slate-500">Current</span>
                          <p className="text-white font-medium">{typeof metric.current === 'number' ? metric.current.toFixed(2) : metric.current}</p>
                        </div>
                        <div>
                          <span className="text-slate-500">Deviation</span>
                          <p className={typeof metric.deviation === 'number' && metric.deviation > 0 ? 'text-red-400 font-medium' : 'text-green-400 font-medium'}>
                            {typeof metric.deviation === 'number' ? `${metric.deviation > 0 ? '+' : ''}${metric.deviation.toFixed(1)}%` : metric.deviation}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Deep Analysis Result */}
            {analysisResult && analysisResult.anomaly_id === selectedAnomaly.anomaly_id && (
              <div className="mt-6 pt-6 border-t border-white/5">
                <h4 className="text-sm font-medium text-slate-400 mb-3">Deep Analysis Result</h4>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Root Cause */}
                  <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <h5 className="text-sm font-medium text-blue-400 mb-2">Root Cause</h5>
                    <p className="text-sm text-slate-300">{analysisResult.root_cause?.description}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs text-slate-500">Type: {analysisResult.root_cause?.type}</span>
                      <span className="text-xs text-slate-500">Confidence: {((analysisResult.root_cause?.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </div>

                  {/* Contributing Factors */}
                  <div className="p-4 bg-slate-900/50 border border-white/5 rounded-lg">
                    <h5 className="text-sm font-medium text-slate-400 mb-2">Contributing Factors</h5>
                    <div className="space-y-1">
                      {analysisResult.contributing_factors?.map((factor, idx) => (
                        <div key={idx} className="flex items-center justify-between text-sm">
                          <span className="text-slate-300">{factor.factor}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            factor.impact === 'high' ? 'bg-red-500/10 text-red-400' :
                            factor.impact === 'medium' ? 'bg-yellow-500/10 text-yellow-400' :
                            'bg-blue-500/10 text-blue-400'
                          }`}>
                            {factor.impact}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Recommended Actions from Analysis */}
                {analysisResult.recommended_actions && analysisResult.recommended_actions.length > 0 && (
                  <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                    <h5 className="text-sm font-medium text-green-400 mb-2">Remediation Steps</h5>
                    <div className="space-y-2">
                      {analysisResult.recommended_actions.map((action, idx) => (
                        <div key={idx} className="flex items-start gap-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            action.priority === 'high' ? 'bg-red-500/20 text-red-400' :
                            action.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}>
                            P{idx + 1}
                          </span>
                          <span className="text-sm text-slate-300">{action.action}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
