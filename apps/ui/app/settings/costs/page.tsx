'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
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

const generateMockUsageStats = (): UsageStat[] => [
  {
    label: 'Log Ingestion',
    value: 2.4,
    unit: 'TB',
    cost: 1200,
    trend: 12,
    breakdown: [
      { name: 'api-gateway', value: 0.8, cost: 400 },
      { name: 'payment-service', value: 0.5, cost: 250 },
      { name: 'auth-service', value: 0.4, cost: 200 },
      { name: 'order-service', value: 0.3, cost: 150 },
      { name: 'Other', value: 0.4, cost: 200 }
    ]
  },
  {
    label: 'Trace Storage',
    value: 850,
    unit: 'GB',
    cost: 425,
    trend: 8,
    breakdown: [
      { name: 'payment-service', value: 320, cost: 160 },
      { name: 'api-gateway', value: 280, cost: 140 },
      { name: 'order-service', value: 150, cost: 75 },
      { name: 'Other', value: 100, cost: 50 }
    ]
  },
  {
    label: 'Metrics',
    value: 45,
    unit: 'M series',
    cost: 225,
    trend: -3,
    breakdown: [
      { name: 'Infrastructure', value: 20, cost: 100 },
      { name: 'Application', value: 15, cost: 75 },
      { name: 'Custom', value: 10, cost: 50 }
    ]
  },
  {
    label: 'Security Events',
    value: 125,
    unit: 'M events',
    cost: 312,
    trend: 25,
    breakdown: [
      { name: 'Authentication', value: 80, cost: 200 },
      { name: 'Network', value: 30, cost: 75 },
      { name: 'File Access', value: 15, cost: 37 }
    ]
  }
]

const generateMockAlerts = (): CostAlert[] => [
  {
    id: '1',
    type: 'warning',
    message: 'Log ingestion approaching 80% of budget',
    metric: 'log_ingestion_gb',
    threshold: 3000,
    current: 2400,
    triggered_at: new Date(Date.now() - 7200000).toISOString()
  },
  {
    id: '2',
    type: 'critical',
    message: 'Security events exceeded daily quota',
    metric: 'security_events',
    threshold: 100000000,
    current: 125000000,
    triggered_at: new Date(Date.now() - 3600000).toISOString()
  }
]

const generateMockRecommendations = (): CostRecommendation[] => [
  {
    id: '1',
    title: 'Enable log sampling for debug logs',
    description: 'api-gateway sends 40% debug logs. Sampling at 10% could reduce ingestion costs.',
    potential_savings: 280,
    effort: 'low',
    category: 'logs'
  },
  {
    id: '2',
    title: 'Reduce trace retention for non-error traces',
    description: 'Keep error traces for 30 days, reduce successful traces to 7 days.',
    potential_savings: 150,
    effort: 'medium',
    category: 'traces'
  },
  {
    id: '3',
    title: 'Archive cold metrics to S3',
    description: 'Metrics older than 90 days can be archived for 80% cost reduction.',
    potential_savings: 45,
    effort: 'medium',
    category: 'metrics'
  },
  {
    id: '4',
    title: 'Consolidate duplicate security rules',
    description: '15 overlapping Sigma rules are generating duplicate events.',
    potential_savings: 78,
    effort: 'low',
    category: 'security'
  }
]

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function CostAnalyticsPage() {
  const [usageStats, setUsageStats] = useState<UsageStat[]>([])
  const [alerts, setAlerts] = useState<CostAlert[]>([])
  const [recommendations, setRecommendations] = useState<CostRecommendation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedPeriod, setSelectedPeriod] = useState('month')
  const [expandedStat, setExpandedStat] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [selectedPeriod])

  const loadData = async () => {
    try {
      setIsLoading(true)
      const [usageRes, alertsRes, recsRes] = await Promise.all([
        apiClient.get('/v1/usage/stats', { period: selectedPeriod }).catch(() => null),
        apiClient.get('/v1/usage/alerts').catch(() => null),
        apiClient.get('/v1/usage/recommendations').catch(() => null)
      ])

      setUsageStats(usageRes?.data?.stats || generateMockUsageStats())
      setAlerts(alertsRes?.data?.alerts || generateMockAlerts())
      setRecommendations(recsRes?.data?.recommendations || generateMockRecommendations())
    } catch (error) {
      console.error('Failed to load cost data:', error)
      setUsageStats(generateMockUsageStats())
      setAlerts(generateMockAlerts())
      setRecommendations(generateMockRecommendations())
    } finally {
      setIsLoading(false)
    }
  }

  const totalCost = usageStats.reduce((sum, stat) => sum + stat.cost, 0)
  const totalSavings = recommendations.reduce((sum, rec) => sum + rec.potential_savings, 0)

  // Generate mock historical data for chart
  const generateHistoricalData = () => {
    const data = []
    const now = new Date()
    for (let i = 11; i >= 0; i--) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
      data.push({
        month: MONTHS[date.getMonth()],
        logs: 800 + Math.random() * 500,
        traces: 300 + Math.random() * 200,
        metrics: 150 + Math.random() * 100,
        security: 200 + Math.random() * 150
      })
    }
    return data
  }

  const historicalData = generateHistoricalData()
  const maxValue = Math.max(...historicalData.map(d => d.logs + d.traces + d.metrics + d.security))

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

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Cost Analytics</h1>
            <p className="text-gray-400 mt-1">Monitor usage, control spending, and optimize costs</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
            >
              <option value="day">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="quarter">This Quarter</option>
            </select>
            <button
              onClick={loadData}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
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
                    <p className="text-gray-400 text-sm">Total Spend (MTD)</p>
                    <p className="text-2xl font-bold text-white">{formatCurrency(totalCost)}</p>
                    <p className="text-xs text-green-400 flex items-center gap-1 mt-1">
                      <TrendingUp className="w-3 h-3" />
                      12% vs last month
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
                    <p className="text-gray-400 text-sm">Potential Savings</p>
                    <p className="text-2xl font-bold text-white">{formatCurrency(totalSavings)}</p>
                    <p className="text-xs text-gray-400 mt-1">
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
                    <p className="text-gray-400 text-sm">Data Ingested</p>
                    <p className="text-2xl font-bold text-white">3.4 TB</p>
                    <p className="text-xs text-yellow-400 flex items-center gap-1 mt-1">
                      <TrendingUp className="w-3 h-3" />
                      78% of quota
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-orange-600/20 to-orange-800/20 border border-orange-500/30 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-orange-500/20 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-orange-400" />
                  </div>
                  <div>
                    <p className="text-gray-400 text-sm">Budget Alerts</p>
                    <p className="text-2xl font-bold text-white">{alerts.length}</p>
                    <p className="text-xs text-red-400 mt-1">
                      {alerts.filter(a => a.type === 'critical').length} critical
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Usage Breakdown */}
              <div className="xl:col-span-2 bg-gray-800/50 border border-gray-700 rounded-lg p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">Usage Breakdown</h2>
                  <div className="flex items-center gap-2">
                    {['logs', 'traces', 'metrics', 'security'].map((cat, idx) => (
                      <span key={cat} className="flex items-center gap-1 text-xs text-gray-400">
                        <span className={`w-2 h-2 rounded-full ${
                          idx === 0 ? 'bg-blue-500' :
                          idx === 1 ? 'bg-green-500' :
                          idx === 2 ? 'bg-purple-500' :
                          'bg-orange-500'
                        }`}></span>
                        {cat.charAt(0).toUpperCase() + cat.slice(1)}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Stacked Bar Chart */}
                <div className="h-48 flex items-end gap-1">
                  {historicalData.map((d, idx) => {
                    const total = d.logs + d.traces + d.metrics + d.security
                    const height = (total / maxValue) * 100
                    return (
                      <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                        <div
                          className="w-full rounded-t relative group cursor-pointer"
                          style={{ height: `${height}%` }}
                        >
                          <div className="absolute inset-x-0 bottom-0 bg-blue-500/80 rounded-t transition-all group-hover:bg-blue-400" style={{ height: `${(d.logs / total) * 100}%` }}></div>
                          <div className="absolute inset-x-0 bg-green-500/80 transition-all group-hover:bg-green-400" style={{ bottom: `${(d.logs / total) * 100}%`, height: `${(d.traces / total) * 100}%` }}></div>
                          <div className="absolute inset-x-0 bg-purple-500/80 transition-all group-hover:bg-purple-400" style={{ bottom: `${((d.logs + d.traces) / total) * 100}%`, height: `${(d.metrics / total) * 100}%` }}></div>
                          <div className="absolute inset-x-0 top-0 bg-orange-500/80 rounded-t transition-all group-hover:bg-orange-400" style={{ height: `${(d.security / total) * 100}%` }}></div>

                          {/* Tooltip */}
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                            <div className="bg-gray-900 border border-gray-700 rounded-lg p-2 text-xs whitespace-nowrap">
                              <p className="text-white font-medium mb-1">{d.month}</p>
                              <p className="text-blue-400">Logs: ${d.logs.toFixed(0)}</p>
                              <p className="text-green-400">Traces: ${d.traces.toFixed(0)}</p>
                              <p className="text-purple-400">Metrics: ${d.metrics.toFixed(0)}</p>
                              <p className="text-orange-400">Security: ${d.security.toFixed(0)}</p>
                              <p className="text-gray-400 mt-1 pt-1 border-t border-gray-700">Total: ${total.toFixed(0)}</p>
                            </div>
                          </div>
                        </div>
                        <span className="text-[10px] text-gray-500">{d.month}</span>
                      </div>
                    )
                  })}
                </div>

                {/* Usage Stats Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
                  {usageStats.map((stat) => (
                    <div
                      key={stat.label}
                      onClick={() => setExpandedStat(expandedStat === stat.label ? null : stat.label)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        expandedStat === stat.label
                          ? 'bg-blue-500/10 border-blue-500/30'
                          : 'bg-gray-700/50 border-gray-600 hover:border-gray-500'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-400">{stat.label}</span>
                        <span className={`text-xs flex items-center gap-0.5 ${
                          stat.trend > 0 ? 'text-red-400' : 'text-green-400'
                        }`}>
                          {stat.trend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {Math.abs(stat.trend)}%
                        </span>
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="text-xl font-bold text-white">{stat.value}</span>
                        <span className="text-sm text-gray-500">{stat.unit}</span>
                      </div>
                      <p className="text-sm text-blue-400 mt-1">{formatCurrency(stat.cost)}</p>
                    </div>
                  ))}
                </div>

                {/* Expanded Breakdown */}
                {expandedStat && (
                  <div className="mt-4 p-4 bg-gray-700/30 rounded-lg border border-gray-600">
                    <h4 className="text-sm font-medium text-white mb-3">
                      {expandedStat} - Top Contributors
                    </h4>
                    <div className="space-y-2">
                      {usageStats.find(s => s.label === expandedStat)?.breakdown?.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <span className="text-sm text-gray-400 w-32 truncate">{item.name}</span>
                          <div className="flex-1 h-2 bg-gray-600 rounded-full overflow-hidden">
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
                  </div>
                )}
              </div>

              {/* Right Column */}
              <div className="space-y-6">
                {/* Budget Alerts */}
                <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white">Budget Alerts</h2>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      alerts.some(a => a.type === 'critical')
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {alerts.length} Active
                    </span>
                  </div>

                  {alerts.length === 0 ? (
                    <div className="text-center py-8 text-gray-400">
                      <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">No budget alerts</p>
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
                                <div className="flex-1 h-1.5 bg-gray-600 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      alert.type === 'critical' ? 'bg-red-500' : 'bg-yellow-500'
                                    }`}
                                    style={{ width: `${Math.min((alert.current / alert.threshold) * 100, 100)}%` }}
                                  />
                                </div>
                                <span className="text-xs text-gray-400">
                                  {((alert.current / alert.threshold) * 100).toFixed(0)}%
                                </span>
                              </div>
                              <p className="text-xs text-gray-500 mt-1">
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
                <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold text-white">Optimization Tips</h2>
                    <span className="text-sm text-green-400">
                      Save {formatCurrency(totalSavings)}/mo
                    </span>
                  </div>

                  <div className="space-y-3">
                    {recommendations.map((rec) => (
                      <div
                        key={rec.id}
                        className="p-3 bg-gray-700/50 border border-gray-600 rounded-lg hover:border-gray-500 transition-colors cursor-pointer"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <p className="text-sm font-medium text-white">{rec.title}</p>
                            <p className="text-xs text-gray-400 mt-1">{rec.description}</p>
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

                  <button className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-500/30 rounded-lg transition-colors">
                    View All Recommendations
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Cost by Team/Project */}
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">Cost by Team</h2>
                <button className="flex items-center gap-2 text-sm text-gray-400 hover:text-white">
                  <Filter className="w-4 h-4" />
                  Filter
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left px-4 py-3 text-sm font-medium text-gray-400">Team</th>
                      <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Logs</th>
                      <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Traces</th>
                      <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Metrics</th>
                      <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">Total</th>
                      <th className="text-right px-4 py-3 text-sm font-medium text-gray-400">vs Budget</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {[
                      { name: 'Platform Team', logs: 480, traces: 180, metrics: 90, budget: 800, icon: '🔧' },
                      { name: 'Payments Team', logs: 320, traces: 160, metrics: 45, budget: 500, icon: '💳' },
                      { name: 'Security Team', logs: 200, traces: 25, metrics: 30, budget: 300, icon: '🛡️' },
                      { name: 'Mobile Team', logs: 120, traces: 40, metrics: 35, budget: 250, icon: '📱' },
                      { name: 'Data Team', logs: 80, traces: 20, metrics: 25, budget: 150, icon: '📊' },
                    ].map((team) => {
                      const total = team.logs + team.traces + team.metrics
                      const budgetPct = (total / team.budget) * 100
                      return (
                        <tr key={team.name} className="hover:bg-gray-700/30">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span>{team.icon}</span>
                              <span className="text-white font-medium">{team.name}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right text-sm text-gray-300">{formatCurrency(team.logs)}</td>
                          <td className="px-4 py-3 text-right text-sm text-gray-300">{formatCurrency(team.traces)}</td>
                          <td className="px-4 py-3 text-right text-sm text-gray-300">{formatCurrency(team.metrics)}</td>
                          <td className="px-4 py-3 text-right text-sm font-medium text-white">{formatCurrency(total)}</td>
                          <td className="px-4 py-3 text-right">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              budgetPct > 100 ? 'bg-red-500/20 text-red-400' :
                              budgetPct > 80 ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-green-500/20 text-green-400'
                            }`}>
                              {budgetPct.toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
