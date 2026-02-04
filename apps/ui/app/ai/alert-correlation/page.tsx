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

// Matches backend CorrelationSummaryResponse (nested structure)
interface CorrelationSummary {
  fatigue?: {
    fatigue_score?: number
    rating?: string
  }
  groups?: {
    total_groups?: number
  }
  duplicates?: {
    noise_reduction_percent?: number
    total_suppressible?: number
    total_alerts?: number
  }
}

// Matches backend FatigueScoreResponse
interface FatigueScoreResponse {
  fatigue_score: number
  rating?: string
  contributing_factors?: Array<{
    factor: string
    score_contribution: number
    description?: string
  }>
  recommendations?: string[]
}

// Matches backend AlertGroup / RootAlertDetail / MemberAlertDetail
interface CorrelatedGroup {
  group_id: string
  root_alert?: {
    alert_id: string
    rule_name: string
    severity: string
    triggered_at: string
  }
  member_alerts?: Array<{
    alert_id: string
    rule_name: string
    severity: string
    status?: string
    triggered_at: string
  }>
  correlation_score?: number
  common_services?: string[]
  suggested_root_cause?: string
  group_size?: number
}

// Matches backend DuplicateGroupDetail
interface DuplicateGroup {
  rule_id?: string
  rule_name?: string
  severity?: string
  total_count: number
  suppressible_count?: number
  first_fired?: string
  last_fired?: string
  span_minutes?: number
}

// Matches backend DuplicateDetectionResponse
interface DuplicatesResponse {
  duplicate_groups?: DuplicateGroup[]
  total_duplicate_groups?: number
  total_alerts?: number
  total_suppressible?: number
  noise_reduction_percent?: number
}

// Matches backend TimeBucket
interface AlertTrend {
  timestamp: string
  total?: number
  by_severity?: Record<string, number>
  by_status?: Record<string, number>
}

// Matches backend AlertTrendResponse
interface TrendsResponse {
  time_series?: AlertTrend[]
  trend?: {
    direction?: string
    change_percent?: number
  }
  summary?: {
    total_alerts?: number
    total_buckets?: number
    peak_bucket?: string
    peak_count?: number
  }
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
    if (score < 30) return { bg: 'bg-green-500', text: 'text-green-400', label: 'Healthy', ring: 'ring-green-500/30' }
    if (score < 60) return { bg: 'bg-yellow-500', text: 'text-yellow-400', label: 'Moderate', ring: 'ring-yellow-500/30' }
    return { bg: 'bg-red-500', text: 'text-red-400', label: 'Critical', ring: 'ring-red-500/30' }
  }

  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'bg-red-500/20 text-red-400 border-red-500/30',
      high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      info: 'bg-slate-800/30 text-slate-400 border-white/5'
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
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Link2 className="w-7 h-7 text-indigo-500" />
              Smart Alert Correlation
            </h1>
            <p className="text-slate-400 mt-1">
              Reduce alert noise through intelligent correlation, deduplication, and fatigue detection
            </p>
          </div>
          <button
            onClick={() => { loadSummary(); loadFatigueScore(); loadCorrelatedGroups(); loadDuplicates(); loadTrends() }}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-slate-800/50/5 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh All
          </button>
        </div>

        {/* Summary Bar */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {isLoadingSummary ? (
            [1, 2, 3, 4].map(i => (
              <div key={i} className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5 h-24 animate-pulse">
                <div className="h-4 bg-slate-700 rounded w-24 mb-3" />
                <div className="h-7 bg-slate-700 rounded w-16" />
              </div>
            ))
          ) : (
            <>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Gauge className="w-4 h-4 text-orange-500" />
                  <span className="text-sm font-medium">Fatigue Score</span>
                </div>
                <p className={`text-3xl font-bold ${
                  (summary?.fatigue?.fatigue_score ?? 0) >= 60 ? 'text-red-600' :
                  (summary?.fatigue?.fatigue_score ?? 0) >= 30 ? 'text-yellow-600' :
                  'text-green-600'
                }`}>
                  {summary?.fatigue?.fatigue_score ?? '--'}
                </p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-medium">Correlated Groups</span>
                </div>
                <p className="text-3xl font-bold text-white">{summary?.groups?.total_groups ?? 0}</p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <Copy className="w-4 h-4 text-purple-500" />
                  <span className="text-sm font-medium">Duplicate %</span>
                </div>
                <p className="text-3xl font-bold text-white">
                  {summary?.duplicates?.total_alerts && summary.duplicates.total_suppressible != null
                    ? `${((summary.duplicates.total_suppressible / summary.duplicates.total_alerts) * 100).toFixed(1)}%`
                    : '--'}
                </p>
              </div>
              <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
                <div className="flex items-center gap-2 text-slate-400 mb-2">
                  <BellOff className="w-4 h-4 text-green-500" />
                  <span className="text-sm font-medium">Noise Reduction</span>
                </div>
                <p className="text-3xl font-bold text-green-600">
                  {summary?.duplicates?.noise_reduction_percent != null ? `${summary.duplicates.noise_reduction_percent.toFixed(1)}%` : '--'}
                </p>
              </div>
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Alert Fatigue Score */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
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
                  <div className={`relative w-32 h-32 rounded-full flex items-center justify-center ring-8 ${getFatigueColor(fatigueScore.fatigue_score).ring}`}>
                    <div className={`w-28 h-28 rounded-full flex flex-col items-center justify-center ${
                      fatigueScore.fatigue_score < 30 ? 'bg-green-500/10' :
                      fatigueScore.fatigue_score < 60 ? 'bg-yellow-500/10' :
                      'bg-red-500/10'
                    }`}>
                      <span className={`text-4xl font-bold ${getFatigueColor(fatigueScore.fatigue_score).text}`}>
                        {fatigueScore.fatigue_score}
                      </span>
                      <span className="text-xs text-slate-400">/ 100</span>
                    </div>
                  </div>
                </div>
                <p className={`text-center text-sm font-semibold ${getFatigueColor(fatigueScore.fatigue_score).text}`}>
                  {getFatigueColor(fatigueScore.fatigue_score).label}
                </p>

                {/* Contributing Factors */}
                {fatigueScore.contributing_factors && fatigueScore.contributing_factors.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-slate-300 mb-2">Contributing Factors</h3>
                    <div className="space-y-2">
                      {fatigueScore.contributing_factors.map((factor, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-800/50 rounded-lg">
                          <span className="text-sm text-slate-300">{factor.factor}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  factor.score_contribution > 0.7 ? 'bg-red-500' :
                                  factor.score_contribution > 0.4 ? 'bg-yellow-500' :
                                  'bg-green-500'
                                }`}
                                style={{ width: `${factor.score_contribution * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-slate-400 w-8 text-right">
                              {Math.round(factor.score_contribution * 100)}%
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
                    <h3 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1">
                      <Lightbulb className="w-4 h-4 text-amber-500" />
                      Recommendations
                    </h3>
                    <div className="space-y-2">
                      {fatigueScore.recommendations.map((rec, idx) => (
                        <div key={idx} className="flex items-start gap-2 p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                          <CheckCircle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-amber-300">{rec}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <Gauge className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">No fatigue score data available</p>
              </div>
            )}
          </div>

          {/* Duplicate Detection */}
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Copy className="w-5 h-5 text-purple-500" />
              Duplicate Detection
            </h2>

            {isLoadingDuplicates ? (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-14 bg-slate-800/30 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : duplicates ? (
              <div className="space-y-4">
                {/* Noise Reduction Stat */}
                {duplicates.noise_reduction_percent != null && (
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <BellOff className="w-5 h-5 text-green-400" />
                      <span className="text-sm font-medium text-green-300">Noise Reduction</span>
                    </div>
                    <span className="text-xl font-bold text-green-400">{duplicates.noise_reduction_percent.toFixed(1)}%</span>
                  </div>
                )}

                {/* Duplicate Groups */}
                {duplicates.duplicate_groups && duplicates.duplicate_groups.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/5">
                          <th className="text-left py-2 px-2 text-slate-400 font-medium">Rule</th>
                          <th className="text-right py-2 px-2 text-slate-400 font-medium">Count</th>
                          <th className="text-right py-2 px-2 text-slate-400 font-medium">Suppressible</th>
                        </tr>
                      </thead>
                      <tbody>
                        {duplicates.duplicate_groups.map((group, idx) => (
                          <tr key={idx} className="border-b border-white/5 hover:bg-slate-800/50/5">
                            <td className="py-2.5 px-2">
                              <span className="font-medium text-white">
                                {group.rule_name || `Group ${idx + 1}`}
                              </span>
                              {group.severity && (
                                <span className="ml-2 text-xs text-slate-400">{group.severity}</span>
                              )}
                            </td>
                            <td className="py-2.5 px-2 text-right font-mono text-slate-300">{group.total_count}</td>
                            <td className="py-2.5 px-2 text-right">
                              <span className="font-mono text-orange-400 font-medium">{group.suppressible_count ?? 0}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <CheckCircle className="w-8 h-8 text-green-400 mx-auto mb-2" />
                    <p className="text-slate-400 text-sm">No duplicate groups detected</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-10">
                <Copy className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">No duplicate data available</p>
              </div>
            )}
          </div>
        </div>

        {/* Correlated Alert Groups */}
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-500" />
            Correlated Alert Groups
          </h2>

          {isLoadingGroups ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-20 bg-slate-800/30 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : correlatedGroups.length === 0 ? (
            <div className="text-center py-12">
              <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No correlated alert groups found</p>
              <p className="text-slate-400 text-xs mt-1">Alerts will be grouped when correlated patterns are detected</p>
            </div>
          ) : (
            <div className="space-y-3">
              {correlatedGroups.map(group => (
                <div key={group.group_id} className="border border-white/5 rounded-lg overflow-hidden">
                  {/* Group Header */}
                  <button
                    onClick={() => toggleGroup(group.group_id)}
                    className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50/5 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {expandedGroups[group.group_id]
                        ? <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
                        : <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0" />
                      }
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {group.root_alert && (
                            <span className="font-medium text-white truncate">
                              {group.root_alert.rule_name}
                            </span>
                          )}
                          {group.suggested_root_cause && (
                            <span className="text-xs px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded-full">
                              {group.suggested_root_cause}
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
                            <span className="text-xs text-slate-400 flex items-center gap-1">
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
                          group.correlation_score >= 80 ? 'bg-green-500/20 text-green-400' :
                          group.correlation_score >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-slate-800/30 text-slate-400'
                        }`}>
                          {group.correlation_score}% correlated
                        </span>
                      )}
                      <span className="text-sm text-slate-400">
                        {group.group_size ?? (group.member_alerts?.length ?? 0) + 1} alerts
                      </span>
                    </div>
                  </button>

                  {/* Expanded Members */}
                  {expandedGroups[group.group_id] && (
                    <div className="border-t border-white/5 bg-slate-800/50 p-4">
                      {/* Root Alert */}
                      {group.root_alert && (
                        <div className="mb-3">
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Root Alert</p>
                          <div className="flex items-center gap-3 p-3 bg-slate-800/50 border border-indigo-500/20 rounded-lg">
                            <AlertTriangle className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-white">{group.root_alert.rule_name}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {group.common_services && group.common_services.length > 0 && (
                                  <span className="text-xs text-slate-400">{group.common_services.join(', ')}</span>
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
                          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
                            Correlated Alerts ({group.member_alerts.length})
                          </p>
                          <div className="space-y-2">
                            {group.member_alerts.map(alert => (
                              <div key={alert.alert_id} className="flex items-center gap-3 p-2.5 bg-slate-800/50 border border-white/5 rounded-lg">
                                <Bell className="w-4 h-4 text-slate-400 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-white">{alert.rule_name}</p>
                                  <div className="flex items-center gap-2 mt-0.5">
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
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-xl border border-white/5 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-500" />
              Alert Trends (7 Day)
            </h2>
            <div className="flex items-center gap-2">
              {trends?.trend?.direction && (
                <span className="flex items-center gap-1 text-sm text-slate-400">
                  {getTrendIndicator(trends.trend.direction)}
                  <span className="capitalize">{trends.trend.direction}</span>
                  {trends.trend.change_percent != null && (
                    <span className={`text-xs font-medium ${
                      trends.trend.change_percent > 0 ? 'text-red-500' : 'text-green-500'
                    }`}>
                      ({trends.trend.change_percent > 0 ? '+' : ''}{trends.trend.change_percent.toFixed(1)}%)
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
          ) : trends?.time_series && trends.time_series.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Time</th>
                    <th className="text-right py-2 px-3 text-slate-400 font-medium">Total</th>
                    <th className="text-right py-2 px-3 text-slate-400 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-red-500" />
                        Critical
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-400 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-orange-500" />
                        High
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-400 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-yellow-500" />
                        Medium
                      </span>
                    </th>
                    <th className="text-right py-2 px-3 text-slate-400 font-medium">
                      <span className="flex items-center justify-end gap-1">
                        <span className="w-2 h-2 rounded-full bg-blue-500" />
                        Low
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {trends.time_series.map((point, idx) => (
                    <tr key={idx} className="border-b border-white/5 hover:bg-slate-800/50/5">
                      <td className="py-2 px-3 text-slate-300">{formatTimestamp(point.timestamp)}</td>
                      <td className="py-2 px-3 text-right font-mono font-medium text-white">{point.total ?? '--'}</td>
                      <td className="py-2 px-3 text-right font-mono text-red-600">{point.by_severity?.critical ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-orange-600">{point.by_severity?.high ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-yellow-600">{point.by_severity?.medium ?? 0}</td>
                      <td className="py-2 px-3 text-right font-mono text-blue-600">{point.by_severity?.low ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-12">
              <BarChart3 className="w-10 h-10 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-400">No trend data available</p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
