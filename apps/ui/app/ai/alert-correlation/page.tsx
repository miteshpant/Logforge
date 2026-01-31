'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Bell,
  BellOff,
  AlertTriangle,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Shield,
  Link2,
  Layers,
  Copy,
  BarChart3,
  Clock,
  Gauge,
  XCircle,
  CheckCircle,
  ArrowUpRight,
  ArrowDownRight,
  Lightbulb,
  Loader2,
  Server,
  Filter
} from 'lucide-react'

interface CorrelationSummary {
  fatigue_score?: number
  correlated_groups_count?: number
  duplicate_percentage?: number
  noise_reduction?: number
  total_alerts?: number
  suppressed_count?: number
}

interface FatigueScoreResponse {
  score: number
  level?: string
  contributing_factors?: Array<{
    factor: string
    impact: number
    description?: string
  }>
  recommendations?: string[]
  trend?: string
}

interface CorrelatedGroup {
  group_id: string
  root_alert?: {
    id: string
    name: string
    severity: string
    triggered_at: string
    service?: string
  }
  member_alerts?: Array<{
    id: string
    name: string
    severity: string
    triggered_at: string
    service?: string
  }>
  correlation_score?: number
  common_services?: string[]
  pattern_type?: string
  alert_count?: number
}

interface DuplicateGroup {
  pattern?: string
  rule_name?: string
  count: number
  suppressible?: number
  sample_alert_id?: string
  services?: string[]
}

interface DuplicatesResponse {
  groups?: DuplicateGroup[]
  duplicates?: DuplicateGroup[]
  total_duplicates?: number
  noise_reduction_pct?: number
}

interface AlertTrend {
  timestamp: string
  total?: number
  critical?: number
  high?: number
  medium?: number
  low?: number
}

interface TrendsResponse {
  data_points?: AlertTrend[]
  trends?: AlertTrend[]
  overall_trend?: string
  change_percentage?: number
}

export default function AlertCorrelationPage() {
  const { getApiTimeRange } = useTimeRange()

  // Summary
  const [summary, setSummary] = useState<CorrelationSummary | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(true)

  // Fatigue Score
  const [fatigueScore, setFatigueScore] = useState<FatigueScoreResponse | null>(null)
  const [isLoadingFatigue, setIsLoadingFatigue] = useState(true)

  // Correlated Groups
  const [correlatedGroups, setCorrelatedGroups] = useState<CorrelatedGroup[]>([])
  const [isLoadingGroups, setIsLoadingGroups] = useState(true)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  // Duplicates
  const [duplicates, setDuplicates] = useState<DuplicatesResponse | null>(null)
  const [isLoadingDuplicates, setIsLoadingDuplicates] = useState(true)

  // Trends
  const [trends, setTrends] = useState<TrendsResponse | null>(null)
  const [isLoadingTrends, setIsLoadingTrends] = useState(true)

  const loadSummary = useCallback(async () => {
    try {
      setIsLoadingSummary(true)
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.get<CorrelationSummary>('/v1/alerts/correlation/summary', {
        start_time,
        end_time
      })
      const data = response?.data || response
      if (data) {
        setSummary(data as CorrelationSummary)
      }
    } catch (error) {
      console.error('Failed to load correlation summary:', error)
      setSummary(null)
    } finally {
      setIsLoadingSummary(false)
    }
  }, [getApiTimeRange])

  const loadFatigueScore = useCallback(async () => {
    try {
      setIsLoadingFatigue(true)
      const response = await apiClient.get<FatigueScoreResponse>('/v1/alerts/correlation/fatigue-score')
      const data = response?.data || response
      if (data) {
        setFatigueScore(data as FatigueScoreResponse)
      }
    } catch (error) {
      console.error('Failed to load fatigue score:', error)
      setFatigueScore(null)
    } finally {
      setIsLoadingFatigue(false)
    }
  }, [])

  const loadCorrelatedGroups = useCallback(async () => {
    try {
      setIsLoadingGroups(true)
      const response = await apiClient.get<{ groups: CorrelatedGroup[] }>('/v1/alerts/correlation/groups', {
        time_range: '24h'
      })
      const data = response?.data || response
      if (data?.groups) {
        setCorrelatedGroups(data.groups)
      } else if (Array.isArray(data)) {
        setCorrelatedGroups(data)
      } else {
        setCorrelatedGroups([])
      }
    } catch (error) {
      console.error('Failed to load correlated groups:', error)
      setCorrelatedGroups([])
    } finally {
      setIsLoadingGroups(false)
    }
  }, [])

  const loadDuplicates = useCallback(async () => {
    try {
      setIsLoadingDuplicates(true)
      const response = await apiClient.get<DuplicatesResponse>('/v1/alerts/correlation/duplicates')
      const data = response?.data || response
      if (data) {
        setDuplicates(data as DuplicatesResponse)
      }
    } catch (error) {
      console.error('Failed to load duplicates:', error)
      setDuplicates(null)
    } finally {
      setIsLoadingDuplicates(false)
    }
  }, [])

  const loadTrends = useCallback(async () => {
    try {
      setIsLoadingTrends(true)
      const response = await apiClient.get<TrendsResponse>('/v1/alerts/correlation/trends', {
        time_range: '7d'
      })
      const data = response?.data || response
      if (data) {
        setTrends(data as TrendsResponse)
      }
    } catch (error) {
      console.error('Failed to load alert trends:', error)
      setTrends(null)
    } finally {
      setIsLoadingTrends(false)
    }
  }, [])

  useEffect(() => {
    loadSummary()
    loadFatigueScore()
    loadCorrelatedGroups()
    loadDuplicates()
    loadTrends()
  }, [loadSummary, loadFatigueScore, loadCorrelatedGroups, loadDuplicates, loadTrends])

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }))
  }

  const getFatigueColor = (score: number) => {
    if (score < 30) return { bg: 'bg-green-500', text: 'text-green-700', label: 'Healthy', ring: 'ring-green-200' }
    if (score < 60) return { bg: 'bg-yellow-500', text: 'text-yellow-700', label: 'Moderate', ring: 'ring-yellow-200' }
    return { bg: 'bg-red-500', text: 'text-red-700', label: 'Critical', ring: 'ring-red-200' }
  }

  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-100 text-red-700 border-red-200',
      high: 'bg-orange-100 text-orange-700 border-orange-200',
      medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      low: 'bg-blue-100 text-blue-700 border-blue-200',
      info: 'bg-slate-100 text-slate-600 border-slate-200'
    }
    return colors[severity] || colors.info
  }

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString()
  }

  const getTrendIndicator = (direction?: string) => {
    if (direction === 'up' || direction === 'increasing') return <ArrowUpRight className="w-4 h-4 text-red-500" />
    if (direction === 'down' || direction === 'decreasing') return <ArrowDownRight className="w-4 h-4 text-green-500" />
    return <Minus className="w-4 h-4 text-slate-400" />
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Link2 className="w-7 h-7 text-indigo-500" />
              Smart Alert Correlation
            </h1>
            <p className="text-slate-600 mt-1">
              Reduce alert noise through intelligent correlation, deduplication, and fatigue detection
            </p>
          </div>
          <button
            onClick={() => { loadSummary(); loadFatigueScore(); loadCorrelatedGroups(); loadDuplicates(); loadTrends() }}
            className="flex items-center gap-2 px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh All
          </button>
        </div>

        {/* Summary Bar */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoadingSummary ? (
            [1, 2, 3, 4].map(i => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-24 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-24 mb-3" />
                <div className="h-7 bg-slate-200 rounded w-16" />
              </div>
            ))
          ) : (
            <>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <Gauge className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium">Fatigue Score</span>
                </div>
                <p className={`text-3xl font-bold ${
                  (summary?.fatigue_score ?? 0) >= 60 ? 'text-red-600' :
                  (summary?.fatigue_score ?? 0) >= 30 ? 'text-yellow-600' :
                  'text-green-600'
                }`}>
                  {summary?.fatigue_score ?? '--'}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium">Correlated Groups</span>
                </div>
                <p className="text-3xl font-bold text-slate-900">{summary?.correlated_groups_count ?? 0}</p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <Copy className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium">Duplicate %</span>
                </div>
                <p className="text-3xl font-bold text-slate-900">
                  {summary?.duplicate_percentage != null ? `${summary.duplicate_percentage.toFixed(1)}%` : '--'}
                </p>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 text-slate-600 mb-2">
                  <BellOff className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Noise Reduction</span>
                </div>
                <p className="text-3xl font-bold text-green-600">
                  {summary?.noise_reduction != null ? `${summary.noise_reduction.toFixed(1)}%` : '--'}
                </p>
              </div>
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Alert Fatigue Score */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Gauge className="w-5 h-5 text-orange-500" />
              Alert Fatigue Score
            </h2>

            {isLoadingFatigue ? (
              <div className="flex items-center justify-center h-48">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
              </div>
            ) : fatigueScore ? (
              <div className="space-y-5">
                {/* Large Score Display */}
                <div className="flex items-center justify-center">
                  <div className={`relative w-32 h-32 rounded-full flex items-center justify-center ring-8 ${getFatigueColor(fatigueScore.score).ring}`}>
                    <div className={`w-28 h-28 rounded-full flex flex-col items-center justify-center ${
                      fatigueScore.score < 30 ? 'bg-green-50' :
                      fatigueScore.score < 60 ? 'bg-yellow-50' :
                      'bg-red-50'
                    }`}>
                      <span className={`text-4xl font-bold ${getFatigueColor(fatigueScore.score).text}`}>
                        {fatigueScore.score}
                      </span>
                      <span className="text-xs text-slate-500">/ 100</span>
                    </div>
                  </div>
                </div>
                <p className={`text-center text-sm font-semibold ${getFatigueColor(fatigueScore.score).text}`}>
                  {getFatigueColor(fatigueScore.score).label}
                </p>

                {/* Contributing Factors */}
                {fatigueScore.contributing_factors && fatigueScore.contributing_factors.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-700 mb-2">Contributing Factors</h3>
                    <div className="space-y-2">
                      {fatigueScore.contributing_factors.map((factor, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg">
                          <span className="text-sm text-slate-700">{factor.factor}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  factor.impact > 0.7 ? 'bg-red-500' :
                                  factor.impact > 0.4 ? 'bg-yellow-500' :
                                  'bg-green-500'
                                }`}
                                style={{ width: `${factor.impact * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-500 w-8 text-right">
                              {Math.round(factor.impact * 100)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommendations */}
                {fatigueScore.recommendations && fatigueScore.recommendations.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-1">
                      <Lightbulb className="w-4 h-4 text-amber-500" />
                      Recommendations
                    </h3>
                    <div className="space-y-2">
                      {fatigueScore.recommendations.map((rec, idx) => (
                        <div key={idx} className="flex items-start gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg">
                          <CheckCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-amber-800">{rec}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <Gauge className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">No fatigue score data available</p>
              </div>
            )}
          </div>

          {/* Duplicate Detection */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Copy className="w-5 h-5 text-purple-500" />
              Duplicate Detection
            </h2>

            {isLoadingDuplicates ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-14 bg-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : duplicates ? (
              <div className="space-y-4">
                {/* Noise Reduction Stat */}
                {duplicates.noise_reduction_pct != null && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BellOff className="w-5 h-5 text-green-600" />
                      <span className="text-sm font-medium text-green-800">Noise Reduction</span>
                    </div>
                    <span className="text-xl font-bold text-green-700">{duplicates.noise_reduction_pct.toFixed(1)}%</span>
                  </div>
                )}

                {/* Duplicate Groups */}
                {(duplicates.groups || duplicates.duplicates) && (duplicates.groups || duplicates.duplicates)!.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200">
                          <th className="text-left py-2 px-2 text-slate-500 font-medium">Pattern / Rule</th>
                          <th className="text-right py-2 px-2 text-slate-500 font-medium">Count</th>
                          <th className="text-right py-2 px-2 text-slate-500 font-medium">Suppressible</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(duplicates.groups || duplicates.duplicates || []).map((group, idx) => (
                          <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                            <td className="py-2.5 px-2">
                              <span className="font-medium text-slate-800">
                                {group.rule_name || group.pattern || `Group ${idx + 1}`}
                              </span>
                              {group.services && group.services.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {group.services.map((svc, i) => (
                                    <span key={i} className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">
                                      {svc}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </td>
                            <td className="py-2.5 px-2 text-right font-mono text-slate-700">{group.count}</td>
                            <td className="py-2.5 px-2 text-right">
                              <span className="font-mono text-orange-600 font-medium">{group.suppressible ?? 0}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
                    <p className="text-slate-500 text-sm">No duplicate groups detected</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <Copy className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-500 text-sm">No duplicate data available</p>
              </div>
            )}
          </div>
        </div>

        {/* Correlated Alert Groups */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-500" />
            Correlated Alert Groups
          </h2>

          {isLoadingGroups ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-20 bg-slate-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : correlatedGroups.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No correlated alert groups found</p>
              <p className="text-slate-400 text-xs mt-1">Alerts will be grouped when correlated patterns are detected</p>
            </div>
          ) : (
            <div className="space-y-3">
              {correlatedGroups.map(group => (
                <div key={group.group_id} className="border border-slate-200 rounded-lg overflow-hidden">
                  {/* Group Header */}
                  <button
                    onClick={() => toggleGroup(group.group_id)}
                    className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {expandedGroups[group.group_id]
                        ? <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
                        : <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0" />
                      }
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {group.root_alert && (
                            <span className="font-medium text-slate-900 truncate">
                              {group.root_alert.name}
                            </span>
                          )}
                          {group.pattern_type && (
                            <span className="text-xs px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full">
                              {group.pattern_type}
                            </span>
                          )}
                          {group.root_alert?.severity && (
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityBadge(group.root_alert.severity)}`}>
                              {group.root_alert.severity}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          {group.common_services && group.common_services.length > 0 && (
                            <span className="text-xs text-slate-500 flex items-center gap-1">
                              <Server className="w-3 h-3" />
                              {group.common_services.join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      {group.correlation_score != null && (
                        <span className={`text-xs px-2.5 py-1 rounded-lg font-medium ${
                          group.correlation_score >= 0.8 ? 'bg-green-100 text-green-700' :
                          group.correlation_score >= 0.5 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {Math.round(group.correlation_score * 100)}% correlated
                        </span>
                      )}
                      <span className="text-sm text-slate-500">
                        {group.alert_count ?? (group.member_alerts?.length ?? 0) + 1} alerts
                      </span>
                    </div>
                  </button>

                  {/* Expanded Members */}
                  {expandedGroups[group.group_id] && (
                    <div className="border-t border-slate-200 bg-slate-50 p-4">
                      {/* Root Alert */}
                      {group.root_alert && (
                        <div className="mb-3">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Root Alert</p>
                          <div className="flex items-center gap-3 p-3 bg-white border border-indigo-200 rounded-lg">
                            <AlertTriangle className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900">{group.root_alert.name}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {group.root_alert.service && (
                                  <span className="text-xs text-slate-500">{group.root_alert.service}</span>
                                )}
                                <span className="text-xs text-slate-400">
                                  {formatTimestamp(group.root_alert.triggered_at)}
                                </span>
                              </div>
                            </div>
                            <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityBadge(group.root_alert.severity)}`}>
                              {group.root_alert.severity}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Member Alerts */}
                      {group.member_alerts && group.member_alerts.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                            Correlated Alerts ({group.member_alerts.length})
                          </p>
                          <div className="space-y-2">
                            {group.member_alerts.map(alert => (
                              <div key={alert.id} className="flex items-center gap-3 p-2.5 bg-white border border-slate-200 rounded-lg">
                                <Bell className="w-4 h-4 text-slate-400 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-slate-800">{alert.name}</p>
                                  <div className="flex items-center gap-2 mt-0.5">
                                    {alert.service && (
                                      <span className="text-xs text-slate-500">{alert.service}</span>
                                    )}
                                    <span className="text-xs text-slate-400">
                                      {formatTimestamp(alert.triggered_at)}
                                    </span>
                                  </div>
                                </div>
                                <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityBadge(alert.severity)}`}>
                                  {alert.severity}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Alert Trends */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-500" />
              Alert Trends (7 Day)
            </h2>
            <div className="flex items-center gap-2">
              {trends?.overall_trend && (
                <span className="flex items-center gap-1 text-sm text-slate-600">
                  {getTrendIndicator(trends.overall_trend)}
                  <span className="capitalize">{trends.overall_trend}</span>
                  {trends.change_percentage != null && (
                    <span className={`text-xs font-medium ${
                      trends.change_percentage > 0 ? 'text-red-500' : 'text-green-500'
                    }`}>
                      ({trends.change_percentage > 0 ? '+' : ''}{trends.change_percentage.toFixed(1)}%)
                    </span>
                  )}
                </span>
              )}
            </div>
          </div>

          {isLoadingTrends ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          ) : (trends?.data_points || trends?.trends) ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="text-left py-2 px-3 text-slate-500 font-medium">Time</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">Total</th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-red-500" />
                        Critical
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-orange-500" />
                        High
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-yellow-500" />
                        Medium
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-500 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        Low
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(trends.data_points || trends.trends || []).map((point, idx) => (
                    <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2 px-3 text-slate-700">{formatTimestamp(point.timestamp)}</td>
                      <td className="py-2 px-3 text-right font-mono font-medium text-slate-900">{point.total ?? '--'}</td>
                      <td className="py-2 px-3 text-right font-mono text-red-600">{point.critical ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-orange-600">{point.high ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-yellow-600">{point.medium ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-blue-600">{point.low ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12">
              <BarChart3 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500">No trend data available</p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
