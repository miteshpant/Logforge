'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Database,
  Activity,
  Clock,
  AlertTriangle,
  BarChart3,
  PieChart,
  ArrowRight,
  Download,
  RefreshCw,
  Calendar,
  Users,
  Zap,
  HardDrive,
  Cloud,
  Filter
} from 'lucide-react'

interface UsageStat {
  label: string
  value: number
  unit: string
  cost: number
  trend: number
  breakdown?: { name: string; value: number; cost: number }[]
}

interface CostAlert {
  id: string
  type: 'warning' | 'critical'
  message: string
  metric: string
  threshold: number
  current: number
  triggered_at: string
}

interface CostRecommendation {
  id: string
  title: string
  description: string
  potential_savings: number
  effort: 'low' | 'medium' | 'high'
  category: string
}

export default function CostAnalyticsPage() {
  const { tenant } = useAuth()
  const { getApiTimeRange } = useTimeRange()
  const [usageStats, setUsageStats] = useState<UsageStat[]>([])
  const [alerts, setAlerts] = useState<CostAlert[]>([])
  const [recommendations, setRecommendations] = useState<CostRecommendation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedPeriod, setSelectedPeriod] = useState('month')
  const [expandedStat, setExpandedStat] = useState<string | null>(null)
  const [currentUsage, setCurrentUsage] = useState<any>(null)
  const [costBreakdown, setCostBreakdown] = useState<any>(null)
  const [billingEstimate, setBillingEstimate] = useState<any>(null)

  const loadData = useCallback(async () => {
    if (!tenant?.id) return

    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const [usageRes, costRes, billingRes, trendsRes] = await Promise.allSettled([
        apiClient.get(`/v1/usage/current/${tenant.id}`),
        apiClient.get(`/v1/costs/breakdown/${tenant.id}`),
        apiClient.get(`/v1/billing/estimate/${tenant.id}`),
        apiClient.get('/v1/analytics/usage-trends', { start_time, end_time })
      ])

      // Process current usage - backend returns {api_calls, feature_breakdown, cost_estimate, billing_period}
      if (usageRes.status === 'fulfilled' && usageRes.value?.data) {
        setCurrentUsage(usageRes.value.data)
        const usage = usageRes.value.data
        const stats: UsageStat[] = []

        // Build stats from feature_breakdown dict if available
        if (usage.feature_breakdown && typeof usage.feature_breakdown === 'object') {
          const breakdown = usage.feature_breakdown
          const featureCosts = billingRes.status === 'fulfilled' ? billingRes.value?.data?.feature_costs || {} : {}

          Object.entries(breakdown).forEach(([feature, count]) => {
            stats.push({
              label: feature.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
              value: count as number,
              unit: 'calls',
              cost: featureCosts[feature] || 0,
              trend: 0,
              breakdown: []
            })
          })
        }

        // Also add total API calls as a stat
        if (usage.api_calls && stats.length === 0) {
          stats.push({
            label: 'API Calls',
            value: usage.api_calls,
            unit: 'calls',
            cost: usage.cost_estimate || 0,
            trend: 0,
            breakdown: []
          })
        }

        if (stats.length > 0) {
          setUsageStats(stats)
        }
      }

      // Process cost breakdown
      if (costRes.status === 'fulfilled' && costRes.value?.data) {
        setCostBreakdown(costRes.value.data)
      }

      // Process billing estimate
      if (billingRes.status === 'fulfilled' && billingRes.value?.data) {
        setBillingEstimate(billingRes.value.data)
      }

    } catch (error) {
      console.error('Failed to load cost data:', error)
    } finally {
      setIsLoading(false)
    }
  }, [tenant?.id, getApiTimeRange])

  useEffect(() => {
    loadData()
  }, [loadData, selectedPeriod])

  const totalCost = usageStats.reduce((sum, stat) => sum + stat.cost, 0)
  const totalSavings = recommendations.reduce((sum, rec) => sum + rec.potential_savings, 0)

  const formatCurrency = (amount: number) => {
    if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`
    return `$${amount.toFixed(0)}`
  }

  const formatTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ago`
    const minutes = Math.floor(diff / 60000)
    return `${minutes}m ago`
  }

  const formatValue = (value: number, unit: string) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    return value.toFixed(1)
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Cost Analytics</h1>
            <p className="text-slate-400 mt-1">Monitor usage, control spending, and optimize costs</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="px-3 py-2 bg-slate-800 border border-white/10 rounded-lg text-white"
            >
              <option value="day">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="quarter">This Quarter</option>
            </select>
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
              <Download className="w-4 h-4" />
              Export Report
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-blue-600/20 to-blue-800/20 border border-blue-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-blue-500/20 rounded-lg">
                    <DollarSign className="w-6 h-6 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Total Spend (MTD)</p>
                    <p className="text-2xl font-bold text-white">
                      {totalCost > 0 ? formatCurrency(totalCost) : billingEstimate?.total_estimated_cost ? formatCurrency(billingEstimate.total) : '$0'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-green-600/20 to-green-800/20 border border-green-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-green-500/20 rounded-lg">
                    <Zap className="w-6 h-6 text-green-400" />
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Potential Savings</p>
                    <p className="text-2xl font-bold text-white">
                      {totalSavings > 0 ? formatCurrency(totalSavings) : '$0'}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      {recommendations.length} recommendations
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-600/20 to-purple-800/20 border border-purple-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-purple-500/20 rounded-lg">
                    <HardDrive className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Data Ingested</p>
                    <p className="text-2xl font-bold text-white">
                      {currentUsage?.total_ingested_gb
                        ? `${currentUsage.total_ingested_gb.toFixed(1)} GB`
                        : usageStats.length > 0
                          ? `${usageStats.reduce((sum, s) => sum + s.value, 0).toFixed(1)} ${usageStats[0]?.unit || 'GB'}`
                          : '0 GB'
                      }
                    </p>
                    {currentUsage?.quota_percent && (
                      <p className={`text-xs flex items-center gap-1 mt-1 ${
                        currentUsage.quota_percent > 80 ? 'text-yellow-400' : 'text-green-400'
                      }`}>
                        {currentUsage.quota_percent.toFixed(0)}% of quota
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-orange-600/20 to-orange-800/20 border border-orange-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-orange-500/20 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-orange-400" />
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Budget Alerts</p>
                    <p className="text-2xl font-bold text-white">{alerts.length}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {alerts.filter(a => a.type === 'critical').length} critical
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Usage Breakdown */}
              <div className="xl:col-span-2 rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Usage Breakdown</h2>
                </div>

                {usageStats.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-48 text-slate-400">
                    <BarChart3 className="w-12 h-12 mb-4 opacity-50" />
                    <p className="text-sm">No usage data available</p>
                    <p className="text-xs text-slate-500 mt-1">Usage data will appear as you ingest logs, traces, and metrics</p>
                  </div>
                ) : (
                  <>
                    {/* Usage Stats Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {usageStats.map((stat) => (
                        <div
                          key={stat.label}
                          onClick={() => setExpandedStat(expandedStat === stat.label ? null : stat.label)}
                          className={`p-3 rounded-lg border cursor-pointer transition-all ${
                            expandedStat === stat.label
                              ? 'bg-blue-500/10 border-blue-500/30'
                              : 'bg-slate-700/50 border-white/10 hover:border-white/20'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm text-slate-400">{stat.label}</span>
                            {stat.trend !== 0 && (
                              <span className={`text-xs flex items-center gap-0.5 ${
                                stat.trend > 0 ? 'text-red-400' : 'text-green-400'
                              }`}>
                                {stat.trend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {Math.abs(stat.trend)}%
                              </span>
                            )}
                          </div>
                          <div className="flex items-baseline gap-1">
                            <span className="text-xl font-bold text-white">{formatValue(stat.value, stat.unit)}</span>
                            <span className="text-sm text-slate-500">{stat.unit}</span>
                          </div>
                          {stat.cost > 0 && (
                            <p className="text-sm text-blue-400 mt-1">{formatCurrency(stat.cost)}</p>
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Expanded Breakdown */}
                    {expandedStat && (
                      <div className="mt-4 p-4 bg-slate-700/30 rounded-lg border border-white/10">
                        <h4 className="text-sm font-medium text-white mb-3">
                          {expandedStat} - Top Contributors
                        </h4>
                        {(() => {
                          const breakdown = usageStats.find(s => s.label === expandedStat)?.breakdown
                          if (!breakdown || breakdown.length === 0) {
                            return <p className="text-sm text-slate-500">No breakdown data available</p>
                          }
                          return (
                            <div className="space-y-2">
                              {breakdown.map((item, idx) => (
                                <div key={idx} className="flex items-center gap-3">
                                  <span className="text-sm text-slate-400 w-32 truncate">{item.name}</span>
                                  <div className="flex-1 h-2 bg-slate-600 rounded-full overflow-hidden">
                                    <div
                                      className="h-full bg-blue-500 rounded-full"
                                      style={{
                                        width: `${(item.cost / (usageStats.find(s => s.label === expandedStat)?.cost || 1)) * 100}%`
                                      }}
                                    />
                                  </div>
                                  <span className="text-sm text-white w-16 text-right">{formatCurrency(item.cost)}</span>
                                </div>
                              ))}
                            </div>
                          )
                        })()}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Right Column */}
              <div className="space-y-6">
                {/* Budget Alerts */}
                <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white">Budget Alerts</h2>
                    {alerts.length > 0 && (
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        alerts.some(a => a.type === 'critical')
                          ? 'bg-red-500/20 text-red-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {alerts.length} Active
                      </span>
                    )}
                  </div>

                  {alerts.length === 0 ? (
                    <div className="text-center py-8 text-slate-400">
                      <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No budget alerts</p>
                      <p className="text-xs text-slate-500 mt-1">Configure cost alerts to get notified about spending</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {alerts.map((alert) => (
                        <div
                          key={alert.id}
                          className={`p-3 rounded-lg border ${
                            alert.type === 'critical'
                              ? 'bg-red-500/10 border-red-500/30'
                              : 'bg-yellow-500/10 border-yellow-500/30'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <AlertTriangle className={`w-4 h-4 mt-0.5 ${
                              alert.type === 'critical' ? 'text-red-400' : 'text-yellow-400'
                            }`} />
                            <div className="flex-1">
                              <p className="text-sm text-white">{alert.message}</p>
                              <div className="flex items-center gap-2 mt-2">
                                <div className="flex-1 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      alert.type === 'critical' ? 'bg-red-500' : 'bg-yellow-500'
                                    }`}
                                    style={{ width: `${Math.min((alert.current / alert.threshold) * 100, 100)}%` }}
                                  />
                                </div>
                                <span className="text-xs text-slate-400">
                                  {((alert.current / alert.threshold) * 100).toFixed(0)}%
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 mt-1">
                                {formatTimeAgo(alert.triggered_at)}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Cost Optimization Recommendations */}
                <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white">Optimization Tips</h2>
                    {totalSavings > 0 && (
                      <span className="text-sm text-green-400">
                        Save {formatCurrency(totalSavings)}/mo
                      </span>
                    )}
                  </div>

                  {recommendations.length === 0 ? (
                    <div className="text-center py-8 text-slate-400">
                      <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No optimization recommendations</p>
                      <p className="text-xs text-slate-500 mt-1">Recommendations will appear based on your usage patterns</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recommendations.map((rec) => (
                        <div
                          key={rec.id}
                          className="p-3 bg-slate-700/50 border border-white/10 rounded-lg hover:border-white/20 transition-colors cursor-pointer"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <p className="text-sm font-medium text-white">{rec.title}</p>
                              <p className="text-xs text-slate-400 mt-1">{rec.description}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-bold text-green-400">
                                {formatCurrency(rec.potential_savings)}
                              </p>
                              <span className={`text-xs px-1.5 py-0.5 rounded ${
                                rec.effort === 'low' ? 'bg-green-500/20 text-green-400' :
                                rec.effort === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                                'bg-red-500/20 text-red-400'
                              }`}>
                                {rec.effort} effort
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Cost Breakdown Table */}
            {costBreakdown && costBreakdown.teams && costBreakdown.teams.length > 0 && (
              <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Cost by Team</h2>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Team</th>
                        <th className="text-right px-4 py-3 text-sm font-medium text-slate-400">Logs</th>
                        <th className="text-right px-4 py-3 text-sm font-medium text-slate-400">Traces</th>
                        <th className="text-right px-4 py-3 text-sm font-medium text-slate-400">Metrics</th>
                        <th className="text-right px-4 py-3 text-sm font-medium text-slate-400">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {costBreakdown.teams.map((team: any) => {
                        const total = (team.logs || 0) + (team.traces || 0) + (team.metrics || 0)
                        return (
                          <tr key={team.name} className="hover:bg-white/[0.02]">
                            <td className="px-4 py-3 text-white font-medium">{team.name}</td>
                            <td className="px-4 py-3 text-right text-sm text-slate-300">{formatCurrency(team.logs || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm text-slate-300">{formatCurrency(team.traces || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm text-slate-300">{formatCurrency(team.metrics || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm font-medium text-white">{formatCurrency(total)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
