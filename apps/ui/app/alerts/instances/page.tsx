'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  MessageSquare,
  UserCheck,
  XCircle,
  ChevronRight,
  Filter,
  Search,
  RefreshCw,
  ExternalLink,
  Zap,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Activity
} from 'lucide-react'

interface AlertInstance {
  id: string
  rule_id: string
  rule_name: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: 'triggered' | 'acknowledged' | 'resolved' | 'suppressed'
  triggered_at: string
  acknowledged_at?: string
  resolved_at?: string
  acknowledged_by?: string
  resolved_by?: string
  trigger_data: {
    matched_count: number
    sample_values: any[]
    threshold?: number
    actual_value?: number
  }
  related_logs_count: number
  related_traces_count: number
  notes: string[]
}


const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
}

const STATUS_COLORS: Record<string, string> = {
  triggered: 'bg-red-500/20 text-red-400',
  acknowledged: 'bg-yellow-500/20 text-yellow-400',
  resolved: 'bg-green-500/20 text-green-400',
  suppressed: 'bg-gray-500/20 text-gray-400'
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  triggered: <AlertTriangle className="w-4 h-4" />,
  acknowledged: <Eye className="w-4 h-4" />,
  resolved: <CheckCircle className="w-4 h-4" />,
  suppressed: <XCircle className="w-4 h-4" />
}

export default function AlertInstancesPage() {
  const { getApiTimeRange } = useTimeRange()
  const [instances, setInstances] = useState<AlertInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedInstance, setSelectedInstance] = useState<AlertInstance | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterSeverity, setFilterSeverity] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [alertStats, setAlertStats] = useState<any>(null)
  const [isLoadingStats, setIsLoadingStats] = useState(true)
  const [alertDetail, setAlertDetail] = useState<any>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)

  const loadAlertStats = useCallback(async () => {
    try {
      setIsLoadingStats(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get('/v1/alerts/stats', {
        start_time,
        end_time
      })

      const data = response?.data || response
      if (data) {
        setAlertStats(data)
      }
    } catch (error) {
      console.error('Failed to load alert stats:', error)
    } finally {
      setIsLoadingStats(false)
    }
  }, [getApiTimeRange])

  const loadAlertDetail = useCallback(async (alertId: string) => {
    try {
      setIsLoadingDetail(true)
      const response = await apiClient.get(`/v1/alerts/${alertId}`)
      const data = response?.data || response
      if (data) {
        setAlertDetail(data)
      }
    } catch (error) {
      console.error('Failed to load alert detail:', error)
      setAlertDetail(null)
    } finally {
      setIsLoadingDetail(false)
    }
  }, [])

  const loadInstances = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ alerts: AlertInstance[] }>('/v1/alerts', {
        start_time,
        end_time,
        status: filterStatus !== 'all' ? filterStatus : undefined,
        severity: filterSeverity !== 'all' ? filterSeverity : undefined,
        limit: 100
      })

      if (response?.data?.alerts && response.data.alerts.length > 0) {
        setInstances(response.data.alerts.map((alert: any) => ({
          id: alert.alert_id || alert.id,
          rule_id: alert.rule_id || '',
          rule_name: alert.rule_name || alert.title || alert.name || 'Unnamed Alert',
          severity: alert.severity || 'medium',
          status: alert.status || 'triggered',
          triggered_at: alert.triggered_at || alert.created_at || new Date().toISOString(),
          acknowledged_at: alert.acknowledged_at,
          resolved_at: alert.resolved_at,
          acknowledged_by: alert.acknowledged_by,
          resolved_by: alert.resolved_by,
          trigger_data: alert.trigger_data || { matched_count: 0, sample_values: [] },
          related_logs_count: alert.related_logs_count || 0,
          related_traces_count: alert.related_traces_count || 0,
          notes: alert.notes || []
        })))
      } else {
        setInstances([])
      }
    } catch (error) {
      console.error('Failed to load alert instances:', error)
      setInstances([])
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange, filterStatus, filterSeverity])

  useEffect(() => {
    loadInstances()
    loadAlertStats()
  }, [loadInstances, loadAlertStats])

  useEffect(() => {
    if (selectedInstance) {
      loadAlertDetail(selectedInstance.id)
    } else {
      setAlertDetail(null)
    }
  }, [selectedInstance?.id, loadAlertDetail])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    await loadInstances()
    setIsRefreshing(false)
  }

  const acknowledgeAlert = async (instanceId: string) => {
    try {
      await apiClient.post(`/v1/alerts/${instanceId}/acknowledge`)
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'acknowledged' as const, acknowledged_at: new Date().toISOString(), acknowledged_by: 'current-user' }
          : i
      ))
    } catch (error) {
      console.error('Failed to acknowledge alert:', error)
    }
  }

  const resolveAlert = async (instanceId: string) => {
    try {
      await apiClient.post(`/v1/alerts/${instanceId}/resolve`)
      setInstances(instances.map(i =>
        i.id === instanceId
          ? { ...i, status: 'resolved' as const, resolved_at: new Date().toISOString(), resolved_by: 'current-user' }
          : i
      ))
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    }
  }

  const filteredInstances = instances.filter(instance => {
    if (searchQuery && !instance.rule_name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    if (filterStatus !== 'all' && instance.status !== filterStatus) return false
    if (filterSeverity !== 'all' && instance.severity !== filterSeverity) return false
    return true
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  }

  const formatTimeAgo = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    if (hours > 0) return `${hours}h ${minutes % 60}m ago`
    return `${minutes}m ago`
  }

  const stats = {
    triggered: instances.filter(i => i.status === 'triggered').length,
    acknowledged: instances.filter(i => i.status === 'acknowledged').length,
    resolved: instances.filter(i => i.status === 'resolved').length,
    critical: instances.filter(i => i.severity === 'critical' && i.status !== 'resolved').length
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Alert Instances</h1>
            <p className="text-gray-400 mt-1">View and manage triggered alerts</p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-red-400 text-sm">Active Alerts</p>
                <p className="text-2xl font-bold text-white">{stats.triggered}</p>
              </div>
            </div>
          </div>
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-500/20 rounded-lg">
                <Eye className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <p className="text-yellow-400 text-sm">Acknowledged</p>
                <p className="text-2xl font-bold text-white">{stats.acknowledged}</p>
              </div>
            </div>
          </div>
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-green-400 text-sm">Resolved</p>
                <p className="text-2xl font-bold text-white">{stats.resolved}</p>
              </div>
            </div>
          </div>
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Zap className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <p className="text-red-400 text-sm">Critical (Active)</p>
                <p className="text-2xl font-bold text-white">{stats.critical}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Alert Analytics from API */}
        {alertStats && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-semibold text-white">Alert Analytics</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {alertStats.mean_time_to_acknowledge != null && (
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <p className="text-xs text-gray-400">MTTA</p>
                  <p className="text-lg font-bold text-white">
                    {typeof alertStats.mean_time_to_acknowledge === 'number'
                      ? `${Math.round(alertStats.mean_time_to_acknowledge / 60)}m`
                      : alertStats.mean_time_to_acknowledge}
                  </p>
                  <p className="text-[10px] text-gray-500">Mean time to ack</p>
                </div>
              )}
              {alertStats.mean_time_to_resolve != null && (
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <p className="text-xs text-gray-400">MTTR</p>
                  <p className="text-lg font-bold text-white">
                    {typeof alertStats.mean_time_to_resolve === 'number'
                      ? `${Math.round(alertStats.mean_time_to_resolve / 60)}m`
                      : alertStats.mean_time_to_resolve}
                  </p>
                  <p className="text-[10px] text-gray-500">Mean time to resolve</p>
                </div>
              )}
              {alertStats.alert_frequency != null && (
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <p className="text-xs text-gray-400">Frequency</p>
                  <p className="text-lg font-bold text-white flex items-center gap-1">
                    <Activity className="w-4 h-4 text-blue-400" />
                    {typeof alertStats.alert_frequency === 'number'
                      ? alertStats.alert_frequency.toFixed(1)
                      : alertStats.alert_frequency}
                  </p>
                  <p className="text-[10px] text-gray-500">alerts/hour</p>
                </div>
              )}
              {alertStats.noise_ratio != null && (
                <div className="p-3 bg-gray-900/50 rounded-lg">
                  <p className="text-xs text-gray-400">Noise Ratio</p>
                  <p className="text-lg font-bold text-white">
                    {typeof alertStats.noise_ratio === 'number'
                      ? `${(alertStats.noise_ratio * 100).toFixed(1)}%`
                      : alertStats.noise_ratio}
                  </p>
                  <p className="text-[10px] text-gray-500">False positives</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search alerts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="triggered">Triggered</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="resolved">Resolved</option>
            <option value="suppressed">Suppressed</option>
          </select>

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
          </select>
        </div>

        {/* Alert List */}
        <div className="space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          ) : filteredInstances.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 bg-gray-800/50 rounded-lg border border-gray-700">
              <Bell className="w-12 h-12 mb-4 opacity-50" />
              <p>No alerts found</p>
            </div>
          ) : (
            filteredInstances.map((instance) => (
              <div
                key={instance.id}
                className={`bg-gray-800/50 border rounded-lg p-4 hover:bg-gray-800/70 transition-colors cursor-pointer ${
                  instance.status === 'triggered' ? 'border-red-500/50' :
                  instance.status === 'acknowledged' ? 'border-yellow-500/50' :
                  'border-gray-700'
                }`}
                onClick={() => setSelectedInstance(instance)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className={`p-2 rounded-lg ${STATUS_COLORS[instance.status]}`}>
                      {STATUS_ICONS[instance.status]}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-white font-medium">{instance.rule_name}</h3>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${SEVERITY_COLORS[instance.severity]}`}>
                          {instance.severity.toUpperCase()}
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_COLORS[instance.status]}`}>
                          {instance.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTimeAgo(instance.triggered_at)}
                        </span>
                        {instance.trigger_data.threshold && (
                          <span className="flex items-center gap-1">
                            <TrendingUp className="w-3 h-3" />
                            {instance.trigger_data.actual_value} / {instance.trigger_data.threshold} threshold
                          </span>
                        )}
                        <span>{instance.related_logs_count} logs</span>
                        {instance.related_traces_count > 0 && (
                          <span>{instance.related_traces_count} traces</span>
                        )}
                      </div>
                      {instance.acknowledged_by && (
                        <p className="text-sm text-gray-500 mt-1">
                          Acknowledged by {instance.acknowledged_by}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {instance.status === 'triggered' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); acknowledgeAlert(instance.id) }}
                        className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30 transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                    {(instance.status === 'triggered' || instance.status === 'acknowledged') && (
                      <button
                        onClick={(e) => { e.stopPropagation(); resolveAlert(instance.id) }}
                        className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm hover:bg-green-500/30 transition-colors"
                      >
                        Resolve
                      </button>
                    )}
                    <ChevronRight className="w-5 h-5 text-gray-500" />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail Drawer */}
        {selectedInstance && (
          <div className="fixed inset-0 bg-black/50 z-50" onClick={() => setSelectedInstance(null)}>
            <div
              className="fixed right-0 top-0 h-full w-full max-w-xl bg-gray-900 border-l border-gray-700 overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-white">{selectedInstance.rule_name}</h2>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${SEVERITY_COLORS[selectedInstance.severity]}`}>
                        {selectedInstance.severity.toUpperCase()}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[selectedInstance.status]}`}>
                        {selectedInstance.status}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedInstance(null)}
                    className="text-gray-400 hover:text-white"
                  >
                    <XCircle className="w-6 h-6" />
                  </button>
                </div>

                {/* Timeline */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Timeline</h3>
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="p-1 bg-red-500/20 rounded">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                      </div>
                      <div>
                        <p className="text-white text-sm">Triggered</p>
                        <p className="text-gray-400 text-xs">{new Date(selectedInstance.triggered_at).toLocaleString()}</p>
                      </div>
                    </div>
                    {selectedInstance.acknowledged_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-1 bg-yellow-500/20 rounded">
                          <Eye className="w-4 h-4 text-yellow-400" />
                        </div>
                        <div>
                          <p className="text-white text-sm">Acknowledged by {selectedInstance.acknowledged_by}</p>
                          <p className="text-gray-400 text-xs">{new Date(selectedInstance.acknowledged_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                    {selectedInstance.resolved_at && (
                      <div className="flex items-start gap-3">
                        <div className="p-1 bg-green-500/20 rounded">
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        </div>
                        <div>
                          <p className="text-white text-sm">Resolved by {selectedInstance.resolved_by}</p>
                          <p className="text-gray-400 text-xs">{new Date(selectedInstance.resolved_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Trigger Data */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Trigger Details</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-800 p-3 rounded-lg">
                      <p className="text-gray-400 text-sm">Matched Events</p>
                      <p className="text-xl font-bold text-white">{selectedInstance.trigger_data.matched_count}</p>
                    </div>
                    {selectedInstance.trigger_data.threshold && (
                      <>
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-sm">Threshold</p>
                          <p className="text-xl font-bold text-white">{selectedInstance.trigger_data.threshold}</p>
                        </div>
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-sm">Actual Value</p>
                          <p className="text-xl font-bold text-red-400">{selectedInstance.trigger_data.actual_value}</p>
                        </div>
                      </>
                    )}
                    <div className="bg-gray-800 p-3 rounded-lg">
                      <p className="text-gray-400 text-sm">Related Logs</p>
                      <p className="text-xl font-bold text-white">{selectedInstance.related_logs_count}</p>
                    </div>
                  </div>
                </div>

                {/* Sample Values */}
                {selectedInstance.trigger_data.sample_values.length > 0 && (
                  <div className="border border-gray-700 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3">Sample Data</h3>
                    <pre className="bg-gray-800 p-3 rounded-lg text-sm text-gray-300 overflow-x-auto">
                      {JSON.stringify(selectedInstance.trigger_data.sample_values, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Notes */}
                <div className="border border-gray-700 rounded-lg p-4">
                  <h3 className="text-white font-medium mb-3">Investigation Notes</h3>
                  {selectedInstance.notes.length > 0 ? (
                    <div className="space-y-2">
                      {selectedInstance.notes.map((note, idx) => (
                        <div key={idx} className="bg-gray-800 p-3 rounded-lg text-sm text-gray-300">
                          {note}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm">No notes yet</p>
                  )}
                  <div className="mt-3">
                    <textarea
                      placeholder="Add a note..."
                      rows={2}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500"
                    />
                    <button className="mt-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm transition-colors">
                      Add Note
                    </button>
                  </div>
                </div>

                {/* Enhanced Detail from API */}
                {isLoadingDetail && (
                  <div className="flex items-center justify-center py-4">
                    <RefreshCw className="w-5 h-5 text-blue-400 animate-spin" />
                  </div>
                )}
                {alertDetail && !isLoadingDetail && (
                  <div className="border border-gray-700 rounded-lg p-4">
                    <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-blue-400" />
                      Extended Details
                    </h3>
                    <div className="space-y-2">
                      {alertDetail.description && (
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-xs mb-1">Description</p>
                          <p className="text-sm text-white">{alertDetail.description}</p>
                        </div>
                      )}
                      {alertDetail.runbook_url && (
                        <a
                          href={alertDetail.runbook_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 p-3 bg-blue-900/30 border border-blue-700/30 rounded-lg text-blue-400 text-sm hover:bg-blue-900/50 transition-colors"
                        >
                          <ExternalLink className="w-4 h-4" />
                          View Runbook
                        </a>
                      )}
                      {alertDetail.labels && Object.keys(alertDetail.labels).length > 0 && (
                        <div className="bg-gray-800 p-3 rounded-lg">
                          <p className="text-gray-400 text-xs mb-2">Labels</p>
                          <div className="flex flex-wrap gap-1.5">
                            {Object.entries(alertDetail.labels).map(([key, value]) => (
                              <span key={key} className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded text-xs">
                                {key}={String(value)}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3">
                  <a
                    href={`/observability/logs?alert_id=${selectedInstance.id}`}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    View Logs
                  </a>
                  <a
                    href={`/observability/traces?alert_id=${selectedInstance.id}`}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
                  >
                    <ExternalLink className="w-4 h-4" />
                    View Traces
                  </a>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
