'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Bell,
  Plus,
  Search,
  Filter,
  MoreVertical,
  Play,
  Pause,
  Trash2,
  Edit,
  Copy,
  TestTube,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Zap,
  TrendingUp,
  Activity,
  Settings,
  ChevronDown,
  X
} from 'lucide-react'

// Types
interface AlertRule {
  id: string
  name: string
  description: string
  rule_type: 'threshold' | 'anomaly' | 'pattern' | 'frequency' | 'absence' | 'sequence'
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  enabled: boolean
  conditions: RuleCondition[]
  filters: RuleFilter[]
  notification_channels: string[]
  cooldown_period: number
  max_alerts_per_hour: number
  evaluation_interval: number
  last_triggered_at?: string
  trigger_count_24h: number
  created_at: string
  updated_at: string
  created_by: string
}

interface RuleCondition {
  field: string
  operator: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'ne' | 'contains' | 'regex'
  value: string | number
  aggregation?: 'count' | 'sum' | 'avg' | 'min' | 'max' | 'distinct'
  time_window?: string
}

interface RuleFilter {
  field: string
  operator: string
  value: string
}

interface NotificationChannel {
  id: string
  name: string
  type: 'email' | 'slack' | 'pagerduty' | 'webhook' | 'teams'
  enabled: boolean
}

interface AlertStats {
  total_rules: number
  enabled_rules: number
  triggered_24h: number
  by_severity: Record<string, number>
}


const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

const RULE_TYPE_ICONS: Record<string, React.ReactNode> = {
  threshold: <TrendingUp className="w-4 h-4" />,
  anomaly: <Activity className="w-4 h-4" />,
  pattern: <Zap className="w-4 h-4" />,
  frequency: <Clock className="w-4 h-4" />,
  absence: <XCircle className="w-4 h-4" />,
  sequence: <Settings className="w-4 h-4" />
}

export default function AlertRulesPage() {
  const { getApiTimeRange } = useTimeRange()
  const [rules, setRules] = useState<AlertRule[]>([])
  const [channels, setChannels] = useState<NotificationChannel[]>([])
  const [stats, setStats] = useState<AlertStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedRule, setSelectedRule] = useState<AlertRule | null>(null)
  const [showTestModal, setShowTestModal] = useState(false)
  const [testingRuleId, setTestingRuleId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<any>(null)

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const [rulesRes, channelsRes] = await Promise.allSettled([
        apiClient.get<{ rules: AlertRule[] }>('/v1/alerts/rules', { start_time, end_time }),
        apiClient.get<{ channels: NotificationChannel[] }>('/v1/alerts/notifications/channels')
      ])

      const loadedRules: AlertRule[] = rulesRes.status === 'fulfilled' && rulesRes.value?.data?.rules
        ? rulesRes.value.data.rules
        : rulesRes.status === 'fulfilled' && Array.isArray(rulesRes.value?.data)
          ? rulesRes.value.data
          : []

      setRules(loadedRules)

      if (channelsRes.status === 'fulfilled' && channelsRes.value?.data?.channels) {
        setChannels(channelsRes.value.data.channels)
      } else if (channelsRes.status === 'fulfilled' && Array.isArray(channelsRes.value?.data)) {
        setChannels(channelsRes.value.data)
      } else {
        setChannels([])
      }

      const statsData: AlertStats = {
        total_rules: loadedRules.length,
        enabled_rules: loadedRules.filter(r => r.enabled).length,
        triggered_24h: loadedRules.reduce((sum, r) => sum + (r.trigger_count_24h || 0), 0),
        by_severity: loadedRules.reduce((acc, r) => {
          acc[r.severity] = (acc[r.severity] || 0) + 1
          return acc
        }, {} as Record<string, number>)
      }
      setStats(statsData)

    } catch (error) {
      console.error('Failed to load alert rules:', error)
      setRules([])
      setChannels([])
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange])

  useEffect(() => {
    loadData()
  }, [loadData])

  const toggleRuleEnabled = async (ruleId: string) => {
    const rule = rules.find(r => r.id === ruleId)
    if (!rule) return

    try {
      await apiClient.patch(`/v1/alerts/rules/${ruleId}`, {
        enabled: !rule.enabled
      })
      setRules(rules.map(r =>
        r.id === ruleId ? { ...r, enabled: !r.enabled } : r
      ))
    } catch (error) {
      console.error('Failed to toggle rule:', error)
    }
  }

  const deleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return

    try {
      await apiClient.delete(`/v1/alerts/rules/${ruleId}`)
      setRules(rules.filter(r => r.id !== ruleId))
    } catch (error) {
      console.error('Failed to delete rule:', error)
    }
  }

  const testRule = async (ruleId: string) => {
    setTestingRuleId(ruleId)
    setShowTestModal(true)
    setTestResult(null)

    try {
      const result = await apiClient.post(`/v1/alerts/rules/${ruleId}/test`)
      setTestResult(result.data)
    } catch (error) {
      console.error('Failed to test rule:', error)
      setTestResult({
        would_trigger: false,
        matched_count: 0,
        sample_matches: [],
        evaluation_time_ms: 0,
        error: 'Failed to test rule. Please try again.'
      })
    }
  }

  const filteredRules = rules.filter(rule => {
    if (searchQuery && !rule.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !rule.description.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    if (filterSeverity !== 'all' && rule.severity !== filterSeverity) return false
    if (filterType !== 'all' && rule.rule_type !== filterType) return false
    if (filterStatus === 'enabled' && !rule.enabled) return false
    if (filterStatus === 'disabled' && rule.enabled) return false
    return true
  })

  const formatTimeAgo = (timestamp: string | undefined) => {
    if (!timestamp) return 'Never'
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Alert Rules</h1>
            <p className="text-gray-400 mt-1">Configure and manage alerting rules</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Rule
          </button>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <Bell className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Total Rules</p>
                  <p className="text-2xl font-bold text-white">{stats.total_rules}</p>
                </div>
              </div>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Enabled</p>
                  <p className="text-2xl font-bold text-white">{stats.enabled_rules}</p>
                </div>
              </div>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-500/20 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Triggered (24h)</p>
                  <p className="text-2xl font-bold text-white">{stats.triggered_24h}</p>
                </div>
              </div>
            </div>
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/20 rounded-lg">
                  <Zap className="w-5 h-5 text-red-400" />
                </div>
                <div>
                  <p className="text-gray-400 text-sm">Critical Rules</p>
                  <p className="text-2xl font-bold text-white">{stats.by_severity.critical || 0}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search rules..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </select>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Types</option>
            <option value="threshold">Threshold</option>
            <option value="anomaly">Anomaly</option>
            <option value="pattern">Pattern</option>
            <option value="frequency">Frequency</option>
            <option value="absence">Absence</option>
            <option value="sequence">Sequence</option>
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="enabled">Enabled</option>
            <option value="disabled">Disabled</option>
          </select>
        </div>

        {/* Rules List */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : filteredRules.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400">
              <Bell className="w-12 h-12 mb-4 opacity-50" />
              <p>No alert rules found</p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 text-blue-400 hover:text-blue-300"
              >
                Create your first rule
              </button>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Rule</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Severity</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Last Triggered</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">24h Count</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Channels</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {filteredRules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-gray-700/30 transition-colors">
                    <td className="px-4 py-4">
                      <button
                        onClick={() => toggleRuleEnabled(rule.id)}
                        className={`p-2 rounded-lg transition-colors ${
                          rule.enabled
                            ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                            : 'bg-gray-600/20 text-gray-500 hover:bg-gray-600/30'
                        }`}
                        title={rule.enabled ? 'Disable rule' : 'Enable rule'}
                      >
                        {rule.enabled ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <div>
                        <p className="text-white font-medium">{rule.name}</p>
                        <p className="text-gray-400 text-sm">{rule.description}</p>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2 text-gray-300">
                        {RULE_TYPE_ICONS[rule.rule_type]}
                        <span className="capitalize">{rule.rule_type}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${SEVERITY_COLORS[rule.severity]}`}>
                        {rule.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-gray-400">
                      {formatTimeAgo(rule.last_triggered_at)}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`font-medium ${rule.trigger_count_24h > 10 ? 'text-orange-400' : 'text-gray-300'}`}>
                        {rule.trigger_count_24h}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-1">
                        {rule.notification_channels.slice(0, 2).map((channelId, idx) => {
                          const channel = channels.find(c => c.id === channelId)
                          return (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300"
                              title={channel?.name || channelId}
                            >
                              {channel?.type || 'channel'}
                            </span>
                          )
                        })}
                        {rule.notification_channels.length > 2 && (
                          <span className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-400">
                            +{rule.notification_channels.length - 2}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => testRule(rule.id)}
                          className="p-2 text-gray-400 hover:text-blue-400 hover:bg-gray-700 rounded transition-colors"
                          title="Test rule"
                        >
                          <TestTube className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setSelectedRule(rule)}
                          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                          title="Edit rule"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                          title="Duplicate rule"
                        >
                          <Copy className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteRule(rule.id)}
                          className="p-2 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Test Result Modal */}
        {showTestModal && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-lg mx-4">
              <div className="flex items-center justify-between p-4 border-b border-gray-700">
                <h3 className="text-lg font-semibold text-white">Rule Test Result</h3>
                <button
                  onClick={() => setShowTestModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4">
                {testResult === null ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    <span className="ml-3 text-gray-400">Testing rule...</span>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className={`flex items-center gap-3 p-4 rounded-lg ${
                      testResult.would_trigger
                        ? 'bg-orange-500/20 border border-orange-500/30'
                        : 'bg-green-500/20 border border-green-500/30'
                    }`}>
                      {testResult.would_trigger ? (
                        <AlertTriangle className="w-6 h-6 text-orange-400" />
                      ) : (
                        <CheckCircle className="w-6 h-6 text-green-400" />
                      )}
                      <div>
                        <p className={`font-medium ${testResult.would_trigger ? 'text-orange-400' : 'text-green-400'}`}>
                          {testResult.would_trigger ? 'Rule Would Trigger' : 'Rule Would Not Trigger'}
                        </p>
                        <p className="text-sm text-gray-400">
                          Based on current data
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-gray-700/30 p-3 rounded-lg">
                        <p className="text-gray-400 text-sm">Matched Events</p>
                        <p className="text-xl font-bold text-white">{testResult.matched_count}</p>
                      </div>
                      <div className="bg-gray-700/30 p-3 rounded-lg">
                        <p className="text-gray-400 text-sm">Evaluation Time</p>
                        <p className="text-xl font-bold text-white">{testResult.evaluation_time_ms}ms</p>
                      </div>
                    </div>

                    {testResult.sample_matches && testResult.sample_matches.length > 0 && (
                      <div>
                        <p className="text-gray-400 text-sm mb-2">Sample Matches</p>
                        <div className="bg-gray-900 rounded-lg p-3 max-h-32 overflow-y-auto">
                          {testResult.sample_matches.map((match: any, idx: number) => (
                            <div key={idx} className="text-sm text-gray-300 font-mono">
                              {match.message || JSON.stringify(match)}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-3 p-4 border-t border-gray-700">
                <button
                  onClick={() => setShowTestModal(false)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Create Rule Modal Placeholder */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-gray-700">
                <h3 className="text-lg font-semibold text-white">Create Alert Rule</h3>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Rule Name</label>
                  <input
                    type="text"
                    placeholder="e.g., High Error Rate Alert"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    placeholder="Describe what this rule monitors..."
                    rows={2}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Rule Type</label>
                    <select className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500">
                      <option value="threshold">Threshold</option>
                      <option value="anomaly">Anomaly Detection</option>
                      <option value="pattern">Pattern Match</option>
                      <option value="frequency">Frequency</option>
                      <option value="absence">Absence</option>
                      <option value="sequence">Sequence</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Severity</label>
                    <select className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500">
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                      <option value="info">Info</option>
                    </select>
                  </div>
                </div>

                {/* Condition Builder */}
                <div className="border border-gray-600 rounded-lg p-4">
                  <h4 className="text-white font-medium mb-3">Conditions</h4>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <select className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                        <option>error_rate</option>
                        <option>latency_p99</option>
                        <option>request_count</option>
                        <option>cpu_usage</option>
                        <option>memory_usage</option>
                      </select>
                      <select className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                        <option value="gt">&gt; Greater than</option>
                        <option value="gte">&gt;= Greater or equal</option>
                        <option value="lt">&lt; Less than</option>
                        <option value="lte">&lt;= Less or equal</option>
                        <option value="eq">= Equal</option>
                        <option value="ne">!= Not equal</option>
                      </select>
                      <input
                        type="number"
                        placeholder="Value"
                        className="w-24 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm"
                      />
                      <span className="text-gray-400 text-sm">over</span>
                      <select className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                        <option value="1m">1 minute</option>
                        <option value="5m">5 minutes</option>
                        <option value="15m">15 minutes</option>
                        <option value="1h">1 hour</option>
                      </select>
                    </div>
                  </div>
                  <button className="mt-3 text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1">
                    <Plus className="w-4 h-4" /> Add condition
                  </button>
                </div>

                {/* Notification Channels */}
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Notification Channels</label>
                  <div className="flex flex-wrap gap-2">
                    {channels.map(channel => (
                      <label key={channel.id} className="flex items-center gap-2 px-3 py-2 bg-gray-700 rounded-lg cursor-pointer hover:bg-gray-600 transition-colors">
                        <input type="checkbox" className="rounded border-gray-500" />
                        <span className="text-white text-sm">{channel.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Advanced Settings */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Cooldown Period</label>
                    <select className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white">
                      <option value="60">1 minute</option>
                      <option value="300">5 minutes</option>
                      <option value="600">10 minutes</option>
                      <option value="1800">30 minutes</option>
                      <option value="3600">1 hour</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Max Alerts per Hour</label>
                    <input
                      type="number"
                      defaultValue={10}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white"
                    />
                  </div>
                </div>
              </div>
              <div className="flex justify-end gap-3 p-4 border-t border-gray-700">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
                  Create Rule
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
