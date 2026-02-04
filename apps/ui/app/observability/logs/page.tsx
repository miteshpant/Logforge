'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  Search,
  Filter,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Info,
  AlertTriangle,
  Bug,
  FileText,
  Clock,
  Server,
  Tag,
  X,
  Copy,
  ExternalLink,
  Columns,
  BarChart3,
  Save,
  FolderOpen,
  Trash2,
  CheckCircle,
  Loader2
} from 'lucide-react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  service: string
  message: string
  trace_id?: string
  span_id?: string
  metadata: Record<string, unknown>
}

interface LogStats {
  total: number
  by_level: Record<string, number>
  by_service: Record<string, number>
}

const LOG_LEVEL_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  debug: { bg: 'bg-slate-800/30', text: 'text-slate-400', icon: <Bug className="w-3 h-3" /> },
  info: { bg: 'bg-blue-500/20', text: 'text-blue-400', icon: <Info className="w-3 h-3" /> },
  warning: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', icon: <AlertTriangle className="w-3 h-3" /> },
  error: { bg: 'bg-red-500/20', text: 'text-red-400', icon: <AlertCircle className="w-3 h-3" /> },
  critical: { bg: 'bg-red-500/30', text: 'text-red-400', icon: <AlertCircle className="w-3 h-3" /> }
}

export default function LogExplorerPage() {
  const { getApiTimeRange } = useTimeRange()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [stats, setStats] = useState<LogStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [levelFilter, setLevelFilter] = useState<string[]>([])
  const [serviceFilter, setServiceFilter] = useState<string>('all')
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set())
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)
  const [isLiveMode, setIsLiveMode] = useState(false)
  const [services, setServices] = useState<string[]>([])
  const [savedQueries, setSavedQueries] = useState<any[]>([])
  const [showSavedQueries, setShowSavedQueries] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveQueryName, setSaveQueryName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [queryValidation, setQueryValidation] = useState<{ valid: boolean; message?: string } | null>(null)

  const loadSavedQueries = useCallback(async () => {
    try {
      const response = await apiClient.get('/v1/query/saved')
      const data = response?.data || response
      if (Array.isArray(data)) {
        setSavedQueries(data)
      } else if (data?.queries && Array.isArray(data.queries)) {
        setSavedQueries(data.queries)
      }
    } catch (error) {
      console.error('Failed to load saved queries:', error)
    }
  }, [])

  const saveCurrentQuery = async () => {
    if (!saveQueryName.trim()) return
    try {
      setIsSaving(true)
      await apiClient.post('/v1/query/saved', {
        name: saveQueryName,
        query: searchQuery,
        filters: {
          levels: levelFilter,
          service: serviceFilter
        }
      })
      await loadSavedQueries()
      setShowSaveDialog(false)
      setSaveQueryName('')
    } catch (error) {
      console.error('Failed to save query:', error)
    } finally {
      setIsSaving(false)
    }
  }

  const deleteSavedQuery = async (queryId: string) => {
    try {
      await apiClient.delete(`/v1/query/saved/${queryId}`)
      setSavedQueries(prev => prev.filter(q => q.id !== queryId))
    } catch (error) {
      console.error('Failed to delete saved query:', error)
    }
  }

  const applySavedQuery = (query: any) => {
    if (query.query) setSearchQuery(query.query)
    if (query.filters?.levels) setLevelFilter(query.filters.levels)
    if (query.filters?.service) setServiceFilter(query.filters.service)
    setShowSavedQueries(false)
  }

  const validateQuery = async () => {
    if (!searchQuery.trim()) {
      setQueryValidation(null)
      return
    }
    try {
      const response = await apiClient.post('/v1/query/validate', {
        query: searchQuery
      })
      const data = response?.data || response
      setQueryValidation(data)
    } catch (error) {
      setQueryValidation({ valid: false, message: 'Validation failed' })
    }
  }

  const exportViaAPI = async () => {
    try {
      setIsExporting(true)
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.post('/v1/export', {
        start_time,
        end_time,
        format: 'csv',
        query: searchQuery || undefined,
        filters: {
          levels: levelFilter.length > 0 ? levelFilter : undefined,
          service: serviceFilter !== 'all' ? serviceFilter : undefined
        }
      })
      const data = response?.data || response
      if (data?.download_url) {
        window.open(data.download_url, '_blank')
      } else if (typeof data === 'string') {
        const blob = new Blob([data], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `logs-export-${new Date().toISOString()}.csv`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (error) {
      console.error('API export failed, falling back to client export:', error)
      exportLogs()
    } finally {
      setIsExporting(false)
    }
  }

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<{ logs: LogEntry[]; stats: LogStats }>('/v1/logs', {
        start_time,
        end_time,
        search: searchQuery || undefined,
        level: levelFilter.length > 0 ? levelFilter.join(',') : undefined,
        service: serviceFilter !== 'all' ? serviceFilter : undefined,
        limit: 500
      })

      const data = response?.data || response
      if (data?.logs) {
        setLogs(data.logs)
        if (data.stats) {
          setStats(data.stats)
        } else {
          setStats(calculateStats(data.logs))
        }
        const uniqueServices = new Set<string>()
        data.logs.forEach((log: LogEntry) => uniqueServices.add(log.service))
        setServices(Array.from(uniqueServices))
      } else if (Array.isArray(data)) {
        setLogs(data)
        setStats(calculateStats(data))
        const uniqueServices = new Set<string>()
        data.forEach((log: LogEntry) => uniqueServices.add(log.service))
        setServices(Array.from(uniqueServices))
      } else {
        setLogs([])
        setStats({ total: 0, by_level: {}, by_service: {} })
      }
    } catch (error) {
      console.error('Failed to load logs:', error)
      setLogs([])
      setStats({ total: 0, by_level: {}, by_service: {} })
    } finally {
      setIsLoading(false)
    }
  }, [getApiTimeRange, searchQuery, levelFilter, serviceFilter])

  useEffect(() => {
    loadLogs()
    loadSavedQueries()
  }, [loadLogs, loadSavedQueries])

  // Live mode polling
  useEffect(() => {
    if (!isLiveMode) return

    const interval = setInterval(() => {
      loadLogs()
    }, 5000)

    return () => clearInterval(interval)
  }, [isLiveMode, loadLogs])

  const toggleLogExpansion = (logId: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev)
      if (next.has(logId)) {
        next.delete(logId)
      } else {
        next.add(logId)
      }
      return next
    })
  }

  const toggleLevelFilter = (level: string) => {
    setLevelFilter(prev => {
      if (prev.includes(level)) {
        return prev.filter(l => l !== level)
      }
      return [...prev, level]
    })
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleString()
  }

  const formatRelativeTime = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime()
    if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const exportLogs = () => {
    const csvContent = [
      ['Timestamp', 'Level', 'Service', 'Message', 'Trace ID'].join(','),
      ...logs.map(log => [
        log.timestamp,
        log.level,
        log.service,
        `"${log.message.replace(/"/g, '""')}"`,
        log.trace_id || ''
      ].join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString()}.csv`
    a.click()
  }

  const filteredLogs = logs.filter(log => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        log.message.toLowerCase().includes(query) ||
        log.service.toLowerCase().includes(query) ||
        log.trace_id?.toLowerCase().includes(query) ||
        JSON.stringify(log.metadata).toLowerCase().includes(query)
      )
    }
    return true
  })

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-120px)] flex flex-col">
        {/* Controls Bar */}
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => setIsLiveMode(!isLiveMode)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isLiveMode
                ? 'bg-green-500 text-white'
                : 'bg-slate-800/30 text-slate-300 hover:bg-white/10'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${isLiveMode ? 'bg-white animate-pulse' : 'bg-slate-400'}`} />
            {isLiveMode ? 'Live' : 'Live Mode'}
          </button>

          {/* Saved Queries */}
          <div className="relative">
            <button
              onClick={() => setShowSavedQueries(!showSavedQueries)}
              className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5"
            >
              <FolderOpen className="w-4 h-4" />
              Saved Queries
              {savedQueries.length > 0 && (
                <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">
                  {savedQueries.length}
                </span>
              )}
            </button>
            {showSavedQueries && (
              <div className="absolute top-full mt-1 left-0 w-72 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl border border-white/5 rounded-2xl shadow-xl z-50 max-h-64 overflow-y-auto">
                {savedQueries.length === 0 ? (
                  <div className="p-4 text-center text-sm text-slate-400">
                    No saved queries yet
                  </div>
                ) : (
                  savedQueries.map(q => (
                    <div
                      key={q.id}
                      className="flex items-center justify-between px-4 py-2.5 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-0"
                    >
                      <button
                        onClick={() => applySavedQuery(q)}
                        className="flex-1 text-left"
                      >
                        <p className="text-sm font-medium text-white">{q.name}</p>
                        {q.query && <p className="text-xs text-slate-400 truncate">{q.query}</p>}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteSavedQuery(q.id) }}
                        className="p-1 text-slate-400 hover:text-red-500 ml-2"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Save Current Query */}
          {searchQuery && (
            <div className="relative">
              <button
                onClick={() => setShowSaveDialog(!showSaveDialog)}
                className="flex items-center gap-2 px-3 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5"
              >
                <Save className="w-4 h-4" />
                Save
              </button>
              {showSaveDialog && (
                <div className="absolute top-full mt-1 left-0 w-64 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl border border-white/5 rounded-2xl shadow-xl z-50 p-3">
                  <input
                    type="text"
                    placeholder="Query name..."
                    value={saveQueryName}
                    onChange={(e) => setSaveQueryName(e.target.value)}
                    className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm bg-slate-800/50 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 mb-2"
                    autoFocus
                    onKeyDown={(e) => e.key === 'Enter' && saveCurrentQuery()}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={saveCurrentQuery}
                      disabled={!saveQueryName.trim() || isSaving}
                      className="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                    >
                      {isSaving ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Save'}
                    </button>
                    <button
                      onClick={() => setShowSaveDialog(false)}
                      className="px-3 py-1.5 text-slate-400 hover:bg-white/5 rounded text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <button
            onClick={exportViaAPI}
            disabled={isExporting}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5 disabled:opacity-50"
          >
            {isExporting
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Download className="w-4 h-4" />
            }
            Export
          </button>
          <button
            onClick={loadLogs}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 ml-auto"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Query Validation Feedback */}
        {queryValidation && (
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg mb-4 text-sm ${
            queryValidation.valid
              ? 'bg-green-500/10 text-green-400 border border-green-500/30'
              : 'bg-red-500/10 text-red-400 border border-red-500/30'
          }`}>
            {queryValidation.valid
              ? <CheckCircle className="w-4 h-4" />
              : <AlertCircle className="w-4 h-4" />
            }
            {queryValidation.message || (queryValidation.valid ? 'Query is valid' : 'Invalid query')}
          </div>
        )}

        {/* Stats Bar */}
        {stats && (
          <div className="flex gap-4 mb-4">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/30 rounded-lg">
              <FileText className="w-4 h-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-300">{stats.total.toLocaleString()} logs</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/20 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-red-400">{(stats.by_level.error || 0) + (stats.by_level.critical || 0)} errors</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/20 rounded-lg">
              <AlertTriangle className="w-4 h-4 text-yellow-600" />
              <span className="text-sm font-medium text-yellow-400">{stats.by_level.warning || 0} warnings</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 rounded-lg">
              <Server className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium text-blue-400">{Object.keys(stats.by_service).length} services</span>
            </div>
          </div>
        )}

        {/* Search and Filters */}
        <div className="flex gap-4 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search logs by message, service, trace ID, or metadata..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setQueryValidation(null) }}
              onBlur={validateQuery}
              className="w-full pl-10 pr-4 py-2 border border-white/10 rounded-lg bg-slate-800/50 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Level Filter */}
          <div className="flex items-center gap-1 px-2 py-1 bg-slate-800/30 rounded-lg">
            {Object.entries(LOG_LEVEL_STYLES).map(([level, style]) => (
              <button
                key={level}
                onClick={() => toggleLevelFilter(level)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  levelFilter.length === 0 || levelFilter.includes(level)
                    ? `${style.bg} ${style.text}`
                    : 'bg-transparent text-slate-400'
                }`}
              >
                {style.icon}
                {level}
              </button>
            ))}
          </div>

          {/* Service Filter */}
          <select
            value={serviceFilter}
            onChange={(e) => setServiceFilter(e.target.value)}
            className="px-4 py-2 border border-white/10 rounded-lg bg-slate-800/50 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Services</option>
            {services.map(service => (
              <option key={service} value={service}>{service}</option>
            ))}
          </select>
        </div>

        {/* Log List */}
        <div className="flex-1 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/5 shadow-xl overflow-hidden flex flex-col">
          {/* Table Header */}
          <div className="flex items-center gap-4 px-4 py-2 bg-slate-800/50 border-b border-white/5 text-xs font-semibold text-slate-400 uppercase">
            <div className="w-8" />
            <div className="w-40">Timestamp</div>
            <div className="w-20">Level</div>
            <div className="w-32">Service</div>
            <div className="flex-1">Message</div>
            <div className="w-24">Trace</div>
          </div>

          {/* Log Entries */}
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center">
                <RefreshCw className="w-8 h-8 text-slate-300 animate-spin mx-auto mb-3" />
                <p className="text-slate-400">Loading logs...</p>
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400">No logs found</p>
                <p className="text-sm text-slate-400 mt-1">Try adjusting your filters</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {filteredLogs.map(log => {
                  const isExpanded = expandedLogs.has(log.id)
                  const levelStyle = LOG_LEVEL_STYLES[log.level] || LOG_LEVEL_STYLES.info

                  return (
                    <div key={log.id} className="hover:bg-white/5">
                      {/* Log Row */}
                      <div
                        className="flex items-center gap-4 px-4 py-2 cursor-pointer"
                        onClick={() => toggleLogExpansion(log.id)}
                      >
                        <div className="w-8">
                          {Object.keys(log.metadata).length > 0 && (
                            isExpanded
                              ? <ChevronDown className="w-4 h-4 text-slate-400" />
                              : <ChevronRight className="w-4 h-4 text-slate-400" />
                          )}
                        </div>
                        <div className="w-40 text-xs text-slate-400 font-mono">
                          <div>{formatTimestamp(log.timestamp)}</div>
                          <div className="text-slate-400">{formatRelativeTime(log.timestamp)}</div>
                        </div>
                        <div className="w-20">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${levelStyle.bg} ${levelStyle.text}`}>
                            {levelStyle.icon}
                            {log.level}
                          </span>
                        </div>
                        <div className="w-32">
                          <span className="text-sm text-slate-300 truncate block">{log.service}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm truncate ${log.level === 'error' || log.level === 'critical' ? 'text-red-400' : 'text-slate-300'}`}>
                            {log.message}
                          </p>
                        </div>
                        <div className="w-24">
                          {log.trace_id && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                copyToClipboard(log.trace_id!)
                              }}
                              className="text-xs font-mono text-blue-400 hover:text-blue-300 flex items-center gap-1"
                            >
                              {log.trace_id.slice(0, 8)}...
                              <Copy className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && Object.keys(log.metadata).length > 0 && (
                        <div className="px-4 pb-4 pl-12">
                          <div className="p-4 bg-slate-900 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-slate-400">Metadata</span>
                              <button
                                onClick={() => copyToClipboard(JSON.stringify(log.metadata, null, 2))}
                                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                              >
                                <Copy className="w-3 h-3" />
                                Copy
                              </button>
                            </div>
                            <pre className="text-xs text-green-400 overflow-x-auto">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          </div>

                          {/* Quick Actions */}
                          <div className="flex gap-2 mt-3">
                            {log.trace_id && (
                              <a
                                href={`/observability/traces?trace_id=${log.trace_id}`}
                                className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-lg text-xs font-medium hover:bg-purple-500/30"
                              >
                                <ExternalLink className="w-3 h-3" />
                                View Trace
                              </a>
                            )}
                            <button
                              onClick={() => setSearchQuery(`service:${log.service}`)}
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-800/30 text-slate-300 rounded-lg text-xs font-medium hover:bg-white/10"
                            >
                              <Filter className="w-3 h-3" />
                              Filter by Service
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Log Detail Panel */}
        {selectedLog && (
          <div className="fixed inset-y-0 right-0 w-1/2 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border-l border-white/5 z-50 overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-white">Log Details</h3>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="p-2 hover:bg-white/5 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Details */}
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-400">Timestamp</label>
                  <p className="text-sm text-white font-mono">{selectedLog.timestamp}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-400">Level</label>
                  <p className={`text-sm font-medium ${LOG_LEVEL_STYLES[selectedLog.level]?.text}`}>
                    {selectedLog.level.toUpperCase()}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-400">Service</label>
                  <p className="text-sm text-white">{selectedLog.service}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-400">Message</label>
                  <p className="text-sm text-white">{selectedLog.message}</p>
                </div>
                {selectedLog.trace_id && (
                  <div>
                    <label className="text-xs text-slate-400">Trace ID</label>
                    <p className="text-sm text-white font-mono">{selectedLog.trace_id}</p>
                  </div>
                )}
                <div>
                  <label className="text-xs text-slate-400">Metadata</label>
                  <pre className="mt-2 p-4 bg-slate-900 text-green-400 rounded-lg text-xs overflow-x-auto">
                    {JSON.stringify(selectedLog.metadata, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

// Mock data generators
function calculateStats(logs: LogEntry[]): LogStats {
  const stats: LogStats = {
    total: logs.length,
    by_level: {},
    by_service: {}
  }

  logs.forEach(log => {
    stats.by_level[log.level] = (stats.by_level[log.level] || 0) + 1
    stats.by_service[log.service] = (stats.by_service[log.service] || 0) + 1
  })

  return stats
}
