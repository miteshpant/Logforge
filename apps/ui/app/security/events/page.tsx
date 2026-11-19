'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createCase } from '@/lib/api/cases'
import { threatBadge, ThreatSummary } from '@/lib/intelFormat'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import {
  ShieldAlert,
  Search,
  Filter,
  CheckCircle,
  AlertCircle,
  Clock,
  User,
  FileText,
  ChevronRight,
  X,
  MessageSquare,
  ExternalLink,
  Target,
  Microscope,
  CheckSquare,
  Square,
  Loader2
} from 'lucide-react'

interface SecurityEvent {
  id: string
  rule_id: string
  rule_title: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  status: 'triggered' | 'investigating' | 'resolved' | 'false_positive'
  timestamp: string
  event_data: Record<string, unknown>
  matched_fields: Record<string, unknown>
  attack_techniques: string[]
  kill_chain_phase?: string
  assigned_to?: string
  investigation_notes: string[]
  artifacts: string[]
  threat?: ThreatSummary | null
}

export default function SecurityEventsPage() {
  const { getApiTimeRange, refreshTrigger } = useTimeRange()
  const router = useRouter()
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [isActionLoading, setIsActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  useEffect(() => { setActionError(null) }, [selectedEvent?.id])
  const [newNote, setNewNote] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [isBulkLoading, setIsBulkLoading] = useState(false)
  const [investigationData, setInvestigationData] = useState<Record<string, any>>({})

  const loadEvents = async () => {
    try {
      setIsLoading(true)
      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.get<SecurityEvent[]>('/v1/security/events', {
        start_time,
        end_time,
        limit: 200,
        severity: severityFilter !== 'all' ? severityFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined
      })

      const data = response?.data || response
      if (Array.isArray(data)) {
        setEvents(data)
      } else if (data?.events && Array.isArray(data.events)) {
        setEvents(data.events)
      } else {
        setEvents([])
      }
    } catch (error) {
      console.error('Failed to load security events:', error)
      setEvents([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadEvents()
  }, [severityFilter, statusFilter, refreshTrigger])

  // Deep link (AI answer citations): ?alert=<id> opens that alert.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('alert')
    if (!id || selectedEvent) return
    const match = events.find(e => e.id === id)
    if (match) setSelectedEvent(match)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events])

  // Run an event action and reflect it only once the API confirms it.
  const runEventAction = async (
    eventId: string,
    action: 'acknowledge' | 'investigate' | 'resolve' | 'false-positive',
    body: Record<string, unknown>,
    status: SecurityEvent['status'],
  ) => {
    setIsActionLoading(true)
    setActionError(null)
    try {
      // Rejects with ApiError if the API refuses the action (caught below).
      const response = await apiClient.post(`/v1/security/${eventId}/${action}`, body)
      if (action === 'investigate' && response.data) {
        setInvestigationData(prev => ({ ...prev, [eventId]: response.data }))
      }
      await loadEvents()
      if (selectedEvent?.id === eventId) {
        setSelectedEvent(prev => prev ? { ...prev, status } : null)
      }
      setNewNote('')
    } catch (error) {
      console.error(`Failed to ${action} event:`, error)
      // Keep the event as it was and keep the note so the user can retry.
      setActionError(error instanceof Error ? error.message : `Failed to ${action} event`)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleAcknowledge = (eventId: string) =>
    runEventAction(eventId, 'acknowledge', { notes: newNote || undefined }, 'investigating')

  const handleCreateCase = async (event: SecurityEvent) => {
    try {
      setIsActionLoading(true)
      setActionError(null)
      const created = await createCase({ title: event.rule_title || 'Security alert', alert_ids: [event.id] })
      router.push(`/security/cases/${created.id}`)
    } catch (error: any) {
      setActionError(error?.message || 'Failed to create a case')
      setIsActionLoading(false)
    }
  }

  const handleResolve = (eventId: string) =>
    runEventAction(eventId, 'resolve', {
      resolution_notes: newNote || 'Resolved - no further action required'
    }, 'resolved')

  const handleFalsePositive = (eventId: string) =>
    runEventAction(eventId, 'false-positive', {
      resolution_notes: newNote || 'Marked as false positive'
    }, 'false_positive')

  const handleInvestigate = (eventId: string) =>
    runEventAction(eventId, 'investigate', { notes: newNote || undefined }, 'investigating')

  const toggleSelection = (eventId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(eventId)) {
        next.delete(eventId)
      } else {
        next.add(eventId)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredEvents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredEvents.map(e => e.id)))
    }
  }

  const handleBulkAction = async (action: 'acknowledge' | 'resolve' | 'false-positive') => {
    if (selectedIds.size === 0) return
    setIsBulkLoading(true)
    try {
      const promises = Array.from(selectedIds).map(id => {
        const endpoint = `/v1/security/${id}/${action}`
        return apiClient.post(endpoint, {
          notes: `Bulk ${action} action`
        }).catch(() => null)
      })
      await Promise.allSettled(promises)
      await loadEvents()
      setSelectedIds(new Set())
    } catch (error) {
      console.error(`Bulk ${action} failed:`, error)
    } finally {
      setIsBulkLoading(false)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-500/10 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/10 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
      case 'low': return 'bg-blue-500/10 text-blue-400 border-blue-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'triggered': return 'bg-red-500/10 text-red-400 border-red-500/30'
      case 'investigating': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
      case 'resolved': return 'bg-green-500/10 text-green-400 border-green-500/30'
      case 'false_positive': return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'triggered': return <AlertCircle className="w-4 h-4" />
      case 'investigating': return <Clock className="w-4 h-4" />
      case 'resolved': return <CheckCircle className="w-4 h-4" />
      case 'false_positive': return <X className="w-4 h-4" />
      default: return <AlertCircle className="w-4 h-4" />
    }
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleString()
  }

  const filteredEvents = events.filter(event => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        event.rule_title.toLowerCase().includes(query) ||
        event.id.toLowerCase().includes(query) ||
        event.attack_techniques.some(t => t.toLowerCase().includes(query))
      )
    }
    return true
  })

  const eventCounts = {
    triggered: events.filter(e => e.status === 'triggered').length,
    investigating: events.filter(e => e.status === 'investigating').length,
    resolved: events.filter(e => e.status === 'resolved').length,
    false_positive: events.filter(e => e.status === 'false_positive').length
  }

  return (
    <DashboardLayout>
      <div className="flex h-[calc(100vh-120px)]">
        {/* Events List */}
        <div className={`${selectedEvent ? 'w-1/2' : 'w-full'} flex flex-col border-r border-white/5`}>
          {/* Header */}
          <div className="p-6 border-b border-white/5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h1 className="text-2xl font-bold text-white">Security Events</h1>
                <p className="text-slate-400 mt-1">
                  Investigate and respond to security incidents
                </p>
              </div>
              <button
                onClick={loadEvents}
                disabled={isLoading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isLoading ? 'Loading...' : 'Refresh'}
              </button>
            </div>

            {/* Status Summary */}
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === 'all'
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-800/30 text-slate-300 hover:bg-white/5'
                }`}
              >
                All ({events.length})
              </button>
              <button
                onClick={() => setStatusFilter('triggered')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === 'triggered'
                    ? 'bg-red-600 text-white'
                    : 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                }`}
              >
                New ({eventCounts.triggered})
              </button>
              <button
                onClick={() => setStatusFilter('investigating')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === 'investigating'
                    ? 'bg-yellow-600 text-white'
                    : 'bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30'
                }`}
              >
                Investigating ({eventCounts.investigating})
              </button>
              <button
                onClick={() => setStatusFilter('resolved')}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === 'resolved'
                    ? 'bg-green-600 text-white'
                    : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                }`}
              >
                Resolved ({eventCounts.resolved})
              </button>
            </div>

            {/* Search and Filter */}
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search events..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500 placeholder-slate-500"
                />
              </div>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="px-4 py-2 bg-slate-800/50 text-white border border-white/10 rounded-lg focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {/* Bulk Actions Bar */}
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-3 mt-3 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <span className="text-sm font-medium text-blue-400">
                  {selectedIds.size} selected
                </span>
                <div className="flex gap-2 ml-auto">
                  <button
                    onClick={() => handleBulkAction('acknowledge')}
                    disabled={isBulkLoading}
                    className="px-3 py-1.5 bg-yellow-500 hover:bg-yellow-600 text-white rounded text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {isBulkLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Acknowledge All'}
                  </button>
                  <button
                    onClick={() => handleBulkAction('resolve')}
                    disabled={isBulkLoading}
                    className="px-3 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    Resolve All
                  </button>
                  <button
                    onClick={() => handleBulkAction('false-positive')}
                    disabled={isBulkLoading}
                    className="px-3 py-1.5 bg-slate-500 hover:bg-slate-600 text-white rounded text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    False Positive All
                  </button>
                  <button
                    onClick={() => setSelectedIds(new Set())}
                    className="px-3 py-1.5 text-slate-400 hover:bg-white/5 rounded text-sm transition-colors"
                  >
                    Clear
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Events List */}
          <div className="flex-1 overflow-y-auto bg-slate-800/50">
            {isLoading ? (
              <div className="p-6 space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-20 bg-slate-800/50 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : filteredEvents.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <ShieldAlert className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-400">No security events found</p>
                </div>
              </div>
            ) : (
              <div className="p-4 space-y-2">
                {filteredEvents.map(event => (
                  <div
                    key={event.id}
                    data-testid="security-event-row"
                    onClick={() => setSelectedEvent(event)}
                    className={`p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-lg border cursor-pointer transition-all ${
                      selectedEvent?.id === event.id
                        ? 'border-blue-500 ring-2 ring-blue-500/20'
                        : selectedIds.has(event.id)
                        ? 'border-blue-500/30 bg-blue-500/10'
                        : 'border-white/5 hover:border-blue-500/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleSelection(event.id) }}
                        className="mt-0.5 flex-shrink-0"
                      >
                        {selectedIds.has(event.id)
                          ? <CheckSquare className="w-4 h-4 text-blue-500" />
                          : <Square className="w-4 h-4 text-slate-300 hover:text-slate-400" />
                        }
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(event.severity)}`}>
                            {event.severity.toUpperCase()}
                          </span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded border flex items-center gap-1 ${getStatusColor(event.status)}`}>
                            {getStatusIcon(event.status)}
                            {event.status.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="font-medium text-white truncate">{event.rule_title}</p>
                        {threatBadge(event.threat) && (
                          <p data-testid="intel-badge" className="mt-1 inline-block px-2 py-0.5 rounded border border-red-500/40 bg-red-500/10 text-xs text-red-300">
                            {threatBadge(event.threat)}
                          </p>
                        )}
                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTimestamp(event.timestamp)}
                          </span>
                          {event.assigned_to && (
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {event.assigned_to}
                            </span>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="w-5 h-5 text-slate-400" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Event Details Panel */}
        {selectedEvent && (
          <div className="w-1/2 flex flex-col bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl">
            {/* Detail Header */}
            <div className="p-6 border-b border-white/5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getSeverityColor(selectedEvent.severity)}`}>
                      {selectedEvent.severity.toUpperCase()}
                    </span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded border flex items-center gap-1 ${getStatusColor(selectedEvent.status)}`}>
                      {getStatusIcon(selectedEvent.status)}
                      {selectedEvent.status.replace('_', ' ')}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white">{selectedEvent.rule_title}</h2>
                  <p className="text-sm text-slate-400 mt-1">Event ID: {selectedEvent.id}</p>
                </div>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="p-2 hover:bg-white/5 rounded-lg"
                >
                  <X className="w-5 h-5 text-slate-400" />
                </button>
              </div>
            </div>

            {/* Detail Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {actionError && (
                <div role="alert" data-testid="event-action-error" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">
                  {actionError}
                </div>
              )}
              <button
                data-testid="create-case-from-alert"
                onClick={() => handleCreateCase(selectedEvent)}
                disabled={isActionLoading}
                className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                Create case from this alert
              </button>
              {/* Quick Actions */}
              {selectedEvent.status !== 'resolved' && selectedEvent.status !== 'false_positive' && (
                <div className="p-4 bg-slate-800/50 rounded-lg border border-white/5">
                  <h3 className="text-sm font-semibold text-white mb-3">Quick Actions</h3>
                  <div className="flex gap-2">
                    {selectedEvent.status === 'triggered' && (
                      <>
                        <button
                          onClick={() => handleAcknowledge(selectedEvent.id)}
                          disabled={isActionLoading}
                          className="flex-1 px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                        >
                          Acknowledge
                        </button>
                        <button
                          onClick={() => handleInvestigate(selectedEvent.id)}
                          disabled={isActionLoading}
                          className="flex-1 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
                        >
                          <Microscope className="w-4 h-4" />
                          Investigate
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => handleResolve(selectedEvent.id)}
                      disabled={isActionLoading}
                      className="flex-1 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                      Resolve
                    </button>
                    <button
                      onClick={() => handleFalsePositive(selectedEvent.id)}
                      disabled={isActionLoading}
                      className="flex-1 px-4 py-2 bg-slate-500 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                      False Positive
                    </button>
                  </div>
                </div>
              )}

              {/* Investigation Results */}
              {investigationData[selectedEvent.id] && (
                <div className="p-4 bg-purple-500/10 rounded-lg border border-purple-500/30">
                  <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Microscope className="w-4 h-4 text-purple-400" />
                    Investigation Results
                  </h3>
                  <pre className="p-3 bg-slate-900 text-green-400 rounded-lg text-xs overflow-x-auto max-h-48">
                    {JSON.stringify(investigationData[selectedEvent.id], null, 2)}
                  </pre>
                </div>
              )}

              {/* Event Details */}
              <div>
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Event Details
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-sm text-slate-400">Timestamp</span>
                    <span className="text-sm font-medium text-white">{formatTimestamp(selectedEvent.timestamp)}</span>
                  </div>
                  <div className="flex justify-between p-3 bg-slate-800/50 rounded-lg">
                    <span className="text-sm text-slate-400">Rule ID</span>
                    <span className="text-sm font-medium text-white">{selectedEvent.rule_id}</span>
                  </div>
                  {selectedEvent.kill_chain_phase && (
                    <div className="flex justify-between p-3 bg-slate-800/50 rounded-lg">
                      <span className="text-sm text-slate-400">Kill Chain Phase</span>
                      <span className="text-sm font-medium text-white">{selectedEvent.kill_chain_phase}</span>
                    </div>
                  )}
                  {selectedEvent.assigned_to && (
                    <div className="flex justify-between p-3 bg-slate-800/50 rounded-lg">
                      <span className="text-sm text-slate-400">Assigned To</span>
                      <span className="text-sm font-medium text-white">{selectedEvent.assigned_to}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* MITRE ATT&CK Techniques */}
              {selectedEvent.attack_techniques?.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    MITRE ATT&CK Techniques
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedEvent.attack_techniques.map(tech => (
                      <a
                        key={tech}
                        href={`https://attack.mitre.org/techniques/${tech}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition-colors"
                      >
                        {tech}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Matched Fields */}
              {Object.keys(selectedEvent.matched_fields || {}).length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-white mb-3">Matched Fields</h3>
                  <pre className="p-4 bg-slate-900 text-green-400 rounded-lg text-sm overflow-x-auto">
                    {JSON.stringify(selectedEvent.matched_fields, null, 2)}
                  </pre>
                </div>
              )}

              {/* Event Data */}
              {Object.keys(selectedEvent.event_data || {}).length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-white mb-3">Raw Event Data</h3>
                  <pre className="p-4 bg-slate-900 text-green-400 rounded-lg text-sm overflow-x-auto max-h-64">
                    {JSON.stringify(selectedEvent.event_data, null, 2)}
                  </pre>
                </div>
              )}

              {/* Investigation Notes */}
              <div>
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Investigation Notes
                </h3>
                <div className="space-y-2">
                  {selectedEvent.investigation_notes?.length > 0 ? (
                    selectedEvent.investigation_notes.map((note, idx) => (
                      <div key={idx} className="p-3 bg-slate-800/50 rounded-lg text-sm text-slate-300">
                        {note}
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-slate-400 italic">No investigation notes yet</p>
                  )}
                </div>

                {/* Add Note */}
                <div className="mt-3">
                  <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Add investigation note..."
                    className="w-full p-3 bg-slate-800/50 text-white border border-white/10 rounded-lg text-sm focus:outline-none focus:border-blue-500 resize-none placeholder-slate-500"
                    rows={3}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}

