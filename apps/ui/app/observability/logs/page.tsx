'use client'

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { createCase } from '@/lib/api/cases'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { parseLogsLink } from '@/lib/aiFormat'
import QueryBar from '@/components/query/QueryBar'
import FieldSidebar from '@/components/query/FieldSidebar'
import AddToDashboard from '@/components/query/AddToDashboard'
import QueryBuilder from '@/components/query/QueryBuilder'
import QueryResults from '@/components/query/QueryResults'
import { LOGQL_FIELDS } from '@/components/query/logqlSyntax'
import AskQueryBox from '@/components/ai/AskQueryBox'
import ExplainPanel from '@/components/ai/ExplainPanel'
import { addFilter } from '@/lib/fieldFormat'
import { useLiveTail } from '@/components/query/useLiveTail'
import {
  fetchLogs,
  fetchServiceNames,
  runLogQL,
  LogQLError,
  NormalizedLog,
  LogQLResult,
} from '@/components/query/logsApi'
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
  X,
  Copy,
  ExternalLink,
  Save,
  FolderOpen,
  Trash2,
  Loader2,
  Radio,
  ArrowUp,
  SlidersHorizontal,
  Terminal,
  ListTree,
  Sparkles,
} from 'lucide-react'

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
  critical: { bg: 'bg-red-500/30', text: 'text-red-400', icon: <AlertCircle className="w-3 h-3" /> },
}

/** Initial page size — smaller than the old 500 for faster first paint (LF-025). */
const PAGE_SIZE = 100

type SearchMode = 'filters' | 'logql'

const TAIL_STATUS_LABELS: Record<string, { label: string; dot: string }> = {
  connecting: { label: 'Connecting…', dot: 'bg-yellow-400 animate-pulse' },
  reconnecting: { label: 'Reconnecting…', dot: 'bg-yellow-400 animate-pulse' },
  live: { label: 'Live', dot: 'bg-green-400 animate-pulse' },
  unavailable: { label: 'Stream unavailable — retrying', dot: 'bg-red-400' },
}

export default function LogExplorerPage() {
  const { getApiTimeRange, refreshTrigger, setTimeRange } = useTimeRange()

  // --- Mode -----------------------------------------------------------------
  const [mode, setMode] = useState<SearchMode>('filters')

  // --- Simple filter mode (LF-025 pagination) -------------------------------
  const [logs, setLogs] = useState<NormalizedLog[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const router = useRouter()
  const [caseError, setCaseError] = useState<string | null>(null)

  // ?q= pre-fills the filter (links from case evidence).
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q')
    if (q) setSearchQuery(q)
  }, [])

  const createCaseFromSearch = async () => {
    const ref = (mode === 'logql' ? logqlQuery : searchQuery).trim() || (serviceFilter !== 'all' ? `service:${serviceFilter}` : '*')
    try {
      setCaseError(null)
      const created = await createCase({
        title: `Investigation: ${ref}`.slice(0, 300),
        evidence: [{ kind: 'search', ref, title: 'Log Explorer search' }],
      })
      router.push(`/security/cases/${created.id}`)
    } catch (error: any) {
      setCaseError(error?.message || 'Failed to create a case')
    }
  }
  const [levelFilter, setLevelFilter] = useState<string[]>([])
  const [serviceFilter, setServiceFilter] = useState<string>('all')

  // --- LogQL mode (LF-023) --------------------------------------------------
  const [logqlQuery, setLogqlQuery] = useState('')
  const [showFields, setShowFields] = useState(false)
  const [showAddToDashboard, setShowAddToDashboard] = useState(false)
  const [showBuilder, setShowBuilder] = useState(false)
  const [catalogueFields, setCatalogueFields] = useState<string[]>([])
  const [logqlResult, setLogqlResult] = useState<LogQLResult | null>(null)
  const [logqlSyntaxError, setLogqlSyntaxError] = useState<string | null>(null)
  const [logqlRunError, setLogqlRunError] = useState<string | null>(null)
  const [isRunningQuery, setIsRunningQuery] = useState(false)

  // --- Live tail (LF-024) ---------------------------------------------------
  const [isTailing, setIsTailing] = useState(false)
  const [pausedTailLogs, setPausedTailLogs] = useState<NormalizedLog[] | null>(null)
  const tail = useLiveTail({
    service: serviceFilter !== 'all' ? serviceFilter : undefined,
    level: levelFilter.length === 1 ? levelFilter[0] : undefined,
  })

  // --- Shared ---------------------------------------------------------------
  const [services, setServices] = useState<string[]>([])
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set())
  const [selectedLog, setSelectedLog] = useState<NormalizedLog | null>(null)
  const [savedQueries, setSavedQueries] = useState<any[]>([])
  const [showSavedQueries, setShowSavedQueries] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveQueryName, setSaveQueryName] = useState('')
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const listRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const logqlRunRef = useRef<() => void>(() => {})

  // ---------------------------------------------------------------------------
  // Data loading — simple filter mode
  // ---------------------------------------------------------------------------

  const buildLogsParams = useCallback(
    (offset: number) => {
      const { start_time, end_time } = getApiTimeRange()
      return {
        start_time,
        end_time,
        // /v1/logs matches `level` exactly, so only send it when a single
        // level is selected; multi-level selections filter client-side.
        level: levelFilter.length === 1 ? levelFilter[0] : undefined,
        service: serviceFilter !== 'all' ? serviceFilter : undefined,
        limit: PAGE_SIZE,
        offset,
      }
    },
    [getApiTimeRange, levelFilter, serviceFilter]
  )

  const loadLogs = useCallback(async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      const page = await fetchLogs(buildLogsParams(0))
      setLogs(page.logs)
      setTotal(page.total)
      setHasMore(page.hasMore)
    } catch (error: any) {
      console.error('Failed to load logs:', error)
      setLogs([])
      setTotal(null)
      setHasMore(false)
      setLoadError(error?.response?.data?.detail || error?.message || 'Failed to load logs')
    } finally {
      setIsLoading(false)
    }
  }, [buildLogsParams])

  const loadMore = useCallback(async () => {
    if (isLoadingMore || isLoading || !hasMore) return
    try {
      setIsLoadingMore(true)
      const page = await fetchLogs(buildLogsParams(logs.length))
      // Appending below the fold preserves the scroll position naturally.
      setLogs(prev => [...prev, ...page.logs])
      setTotal(page.total)
      setHasMore(page.total !== null ? logs.length + page.logs.length < page.total : page.logs.length >= PAGE_SIZE)
    } catch (error: any) {
      console.error('Failed to load more logs:', error)
      setLoadError(error?.response?.data?.detail || error?.message || 'Failed to load more logs')
    } finally {
      setIsLoadingMore(false)
    }
  }, [buildLogsParams, logs.length, hasMore, isLoading, isLoadingMore])

  // Infinite scroll: fetch the next page when the sentinel becomes visible.
  useEffect(() => {
    if (mode !== 'filters' || isTailing) return
    const sentinel = sentinelRef.current
    const rootEl = listRef.current
    if (!sentinel || !rootEl) return

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) loadMore()
      },
      { root: rootEl, rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [mode, isTailing, loadMore])

  // ---------------------------------------------------------------------------
  // LogQL execution
  // ---------------------------------------------------------------------------

  const runQuery = useCallback(async () => {
    if (!logqlQuery.trim() || isRunningQuery) return
    try {
      setIsRunningQuery(true)
      setLogqlSyntaxError(null)
      setLogqlRunError(null)
      const result = await runLogQL(logqlQuery, getApiTimeRange())
      setLogqlResult(result)
    } catch (error: any) {
      if (error instanceof LogQLError && error.isSyntaxError) {
        // Render the parser message verbatim, keeping the input intact.
        setLogqlSyntaxError(error.message)
      } else {
        setLogqlRunError(error?.message || 'Query failed')
      }
    } finally {
      setIsRunningQuery(false)
    }
  }, [logqlQuery, isRunningQuery, getApiTimeRange])
  logqlRunRef.current = runQuery

  // A drafted or suggested query (Phase 9): switch to LogforgeQL, fill it in and run it.
  const useDraftedQuery = useCallback((query: string) => {
    setMode('logql')
    setLogqlQuery(query)
    setLogqlSyntaxError(null)
    requestAnimationFrame(() => requestAnimationFrame(() => logqlRunRef.current()))
  }, [])

  // Deep links (AI answer citations): ?logql=<LogforgeQL>&since=24h, or &from=<iso>&to=<iso>.
  useEffect(() => {
    const link = parseLogsLink(window.location.search)
    if (!link) return
    if (link.start && link.end) {
      setTimeRange({ label: 'From link', value: 'custom', startTime: link.start, endTime: link.end, isCustom: true })
    }
    setMode('logql')
    setLogqlQuery(link.query)
    // Run it only when the link came from Logforge itself (an AI citation);
    // a link from elsewhere fills in the query and waits for Run.
    let sameOrigin = false
    try { sameOrigin = !!document.referrer && new URL(document.referrer).origin === window.location.origin } catch {}
    if (sameOrigin) requestAnimationFrame(() => requestAnimationFrame(() => logqlRunRef.current()))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---------------------------------------------------------------------------
  // Saved queries (existing API, extended with mode + LogQL text)
  // ---------------------------------------------------------------------------

  const loadSavedQueries = useCallback(async () => {
    try {
      const response = await apiClient.get('/v1/query/saved')
      const data = (response as any)?.data ?? response
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
        query: mode === 'logql' ? logqlQuery : searchQuery,
        filters: {
          mode,
          levels: levelFilter,
          service: serviceFilter,
        },
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
    if (query.filters?.mode === 'logql') {
      setMode('logql')
      setLogqlQuery(query.query || '')
      setLogqlSyntaxError(null)
      setLogqlRunError(null)
      // Run after state settles so the bar shows the query being executed.
      requestAnimationFrame(() => logqlRunRef.current())
    } else {
      setMode('filters')
      if (query.query) setSearchQuery(query.query)
      if (query.filters?.levels) setLevelFilter(query.filters.levels)
      if (query.filters?.service) setServiceFilter(query.filters.service)
    }
    setShowSavedQueries(false)
  }

  // ---------------------------------------------------------------------------
  // Export
  // ---------------------------------------------------------------------------

  const exportLogs = useCallback((rows: NormalizedLog[]) => {
    const csvContent = [
      ['Timestamp', 'Level', 'Service', 'Message', 'Trace ID'].join(','),
      ...rows.map(log =>
        [
          log.timestamp,
          log.level,
          log.service,
          `"${log.message.replace(/"/g, '""')}"`,
          log.trace_id || '',
        ].join(',')
      ),
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [])

  // ---------------------------------------------------------------------------
  // Effects
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (mode === 'filters' && !isTailing) loadLogs()
  }, [mode, isTailing, loadLogs, refreshTrigger])

  useEffect(() => {
    loadSavedQueries()
  }, [loadSavedQueries])

  // Service names for the dropdown and LogQL autocomplete — fetched live.
  useEffect(() => {
    let cancelled = false
    fetchServiceNames()
      .then(names => {
        if (!cancelled && names.length > 0) setServices(names)
      })
      .catch(error => console.error('Failed to load service names:', error))
    return () => {
      cancelled = true
    }
  }, [])

  // Live tail lifecycle.
  const toggleTail = () => {
    if (isTailing) {
      tail.stop()
      setIsTailing(false)
      setPausedTailLogs(null)
    } else {
      setPausedTailLogs(null)
      tail.start()
      setIsTailing(true)
      listRef.current?.scrollTo({ top: 0 })
    }
  }

  // Pause-on-scroll: freeze the visible tail when the user scrolls down.
  const handleListScroll = () => {
    if (!isTailing) return
    const el = listRef.current
    if (!el) return
    if (el.scrollTop > 40 && pausedTailLogs === null) {
      setPausedTailLogs(tail.logs)
    } else if (el.scrollTop <= 40 && pausedTailLogs !== null) {
      setPausedTailLogs(null)
    }
  }

  const resumeTail = () => {
    setPausedTailLogs(null)
    listRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // ---------------------------------------------------------------------------
  // Derived display data
  // ---------------------------------------------------------------------------

  const sourceLogs: NormalizedLog[] = isTailing
    ? pausedTailLogs ?? tail.logs
    : mode === 'logql'
      ? logqlResult?.logs ?? []
      : logs

  const displayedLogs = useMemo(() => {
    let result = sourceLogs
    if (mode === 'filters' || isTailing) {
      if (levelFilter.length > 0) {
        result = result.filter(log => levelFilter.includes(log.level))
      }
      if (isTailing && serviceFilter !== 'all') {
        result = result.filter(log => log.service === serviceFilter)
      }
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        result = result.filter(
          log =>
            log.message.toLowerCase().includes(query) ||
            log.service.toLowerCase().includes(query) ||
            log.trace_id?.toLowerCase().includes(query) ||
            JSON.stringify(log.metadata || {}).toLowerCase().includes(query)
        )
      }
    }
    return result
  }, [sourceLogs, mode, isTailing, levelFilter, serviceFilter, searchQuery])

  const stats: LogStats = useMemo(() => {
    const computed: LogStats = { total: 0, by_level: {}, by_service: {} }
    displayedLogs.forEach(log => {
      computed.by_level[log.level] = (computed.by_level[log.level] || 0) + 1
      computed.by_service[log.service] = (computed.by_service[log.service] || 0) + 1
    })
    computed.total =
      !isTailing && mode === 'filters' && total !== null
        ? total
        : !isTailing && mode === 'logql' && logqlResult
          ? logqlResult.totalCount
          : displayedLogs.length
    return computed
  }, [displayedLogs, isTailing, mode, total, logqlResult])

  const newWhilePaused =
    pausedTailLogs !== null ? Math.max(0, tail.logs.length - pausedTailLogs.length) : 0

  const aggregationEntries =
    mode === 'logql' && !isTailing && logqlResult
      ? Object.entries(logqlResult.aggregations)
      : []

  const showListLoading = !isTailing && mode === 'filters' && isLoading
  const showQueryTable =
    mode === 'logql' && !isTailing && !!logqlResult &&
    (logqlResult.resultType === 'table' || logqlResult.resultType === 'timechart')
  const tailStatus = TAIL_STATUS_LABELS[tail.status]

  const toggleLogExpansion = (logId: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev)
      if (next.has(logId)) next.delete(logId)
      else next.add(logId)
      return next
    })
  }

  const toggleLevelFilter = (level: string) => {
    setLevelFilter(prev =>
      prev.includes(level) ? prev.filter(l => l !== level) : [...prev, level]
    )
  }

  const formatTimestamp = (ts: string) => new Date(ts).toLocaleString()

  const formatRelativeTime = (ts: string) => {
    const diff = Date.now() - new Date(ts).getTime()
    if (diff < 60000) return `${Math.max(0, Math.floor(diff / 1000))}s ago`
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-120px)] flex flex-col">
        {/* Controls Bar (wraps: LogQL mode adds Builder and Add to dashboard) */}
        <div className="flex flex-wrap items-center gap-3 mb-4 [&>button]:whitespace-nowrap">
          {/* Mode toggle: simple filters <-> LogforgeQL (LF-023 item 5) */}
          <div className="flex items-center bg-slate-800/30 rounded-lg p-1">
            <button
              onClick={() => setMode('filters')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                mode === 'filters' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/5'
              }`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Filters
            </button>
            <button
              onClick={() => setMode('logql')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                mode === 'logql' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/5'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              LogQL
            </button>
          </div>

          {mode === 'logql' && (
            <button
              data-testid="builder-toggle"
              onClick={() => setShowBuilder(v => !v)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                showBuilder ? 'bg-blue-600 text-white' : 'bg-slate-800/30 text-slate-300 hover:bg-white/10'
              }`}
              title="Build a query from a form"
            >
              Builder
            </button>
          )}

          {/* Field explorer (Phase 5) */}
          <button
            data-testid="fields-toggle"
            onClick={() => setShowFields(v => !v)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              showFields ? 'bg-blue-600 text-white' : 'bg-slate-800/30 text-slate-300 hover:bg-white/10'
            }`}
            title="Explore the fields in your logs"
          >
            <ListTree className="w-4 h-4" />
            Fields
          </button>

          {/* Live tail toggle (LF-024) */}
          <button
            onClick={toggleTail}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isTailing
                ? 'bg-green-500 text-white'
                : 'bg-slate-800/30 text-slate-300 hover:bg-white/10'
            }`}
            title="Stream newly ingested logs in real time"
          >
            <Radio className={`w-4 h-4 ${isTailing ? 'animate-pulse' : ''}`} />
            Live tail
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
                      <button onClick={() => applySavedQuery(q)} className="flex-1 text-left">
                        <p className="text-sm font-medium text-white flex items-center gap-1.5">
                          {q.filters?.mode === 'logql' && (
                            <Terminal className="w-3 h-3 text-blue-400" />
                          )}
                          {q.name}
                        </p>
                        {q.query && <p className="text-xs text-slate-400 truncate font-mono">{q.query}</p>}
                      </button>
                      <button
                        onClick={e => {
                          e.stopPropagation()
                          deleteSavedQuery(q.id)
                        }}
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
          {(mode === 'logql' ? logqlQuery : searchQuery) && (
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
                    onChange={e => setSaveQueryName(e.target.value)}
                    className="w-full px-3 py-2 border border-white/10 rounded-lg text-sm bg-slate-800/50 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 mb-2"
                    autoFocus
                    onKeyDown={e => e.key === 'Enter' && saveCurrentQuery()}
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
            onClick={() => {
              setIsExporting(true)
              try {
                exportLogs(displayedLogs)
              } finally {
                setIsExporting(false)
              }
            }}
            disabled={isExporting || displayedLogs.length === 0}
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5 disabled:opacity-50"
          >
            {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Export
          </button>

          <button
            data-testid="create-case-from-search"
            onClick={createCaseFromSearch}
            title="Open a case with this search pinned as evidence"
            className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5"
          >
            Create case
          </button>
          {caseError && <span role="alert" className="text-sm text-red-400">{caseError}</span>}

          {mode === 'logql' && (
            <button
              data-testid="add-to-dashboard"
              onClick={() => setShowAddToDashboard(true)}
              disabled={!logqlQuery.trim()}
              title="Make this query a dashboard panel"
              className="flex items-center gap-2 px-4 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5 disabled:opacity-50"
            >
              Add to dashboard
            </button>
          )}
          {showAddToDashboard && (
            <AddToDashboard
              query={logqlQuery}
              result={logqlResult?.resultType
                ? { resultType: logqlResult.resultType, columns: logqlResult.columns, rows: logqlResult.rows }
                : null}
              onClose={() => setShowAddToDashboard(false)}
            />
          )}

          <button
            data-testid="logs-refresh"
            onClick={() => (mode === 'logql' ? runQuery() : loadLogs())}
            disabled={isTailing || (mode === 'logql' ? isRunningQuery : isLoading)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 ml-auto"
          >
            <RefreshCw
              className={`w-4 h-4 ${(mode === 'logql' ? isRunningQuery : isLoading) ? 'animate-spin' : ''}`}
            />
            Refresh
          </button>
        </div>

        {/* Live tail status banner */}
        {isTailing && tailStatus && (
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-lg mb-4 text-sm border ${
              tail.status === 'unavailable'
                ? 'bg-red-500/10 text-red-400 border-red-500/30'
                : tail.status === 'live'
                  ? 'bg-green-500/10 text-green-400 border-green-500/30'
                  : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${tailStatus.dot}`} />
            <span>{tailStatus.label}</span>
            {tail.status === 'unavailable' && tail.error && (
              <span className="text-xs opacity-75 font-mono truncate">({tail.error})</span>
            )}
            <span className="ml-auto text-xs opacity-75">
              {tail.logs.length.toLocaleString()} lines buffered (cap 2,000)
            </span>
          </div>
        )}

        {/* Ask in plain English (Phase 9): drafts a LogforgeQL query to run or edit */}
        <AskQueryBox onUse={useDraftedQuery} />

        {/* Query input area */}
        {mode === 'logql' ? (
          <div className="mb-4">
            <QueryBar
              value={logqlQuery}
              onChange={value => {
                setLogqlQuery(value)
                setLogqlSyntaxError(null)
              }}
              onRun={runQuery}
              isRunning={isRunningQuery}
              syntaxError={logqlSyntaxError}
              services={services}
              fields={catalogueFields}
            />
            {logqlRunError && (
              <div className="flex items-center gap-2 px-3 py-2 mt-2 rounded-lg text-sm bg-red-500/10 text-red-400 border border-red-500/30">
                <AlertCircle className="w-4 h-4" />
                {logqlRunError}
              </div>
            )}
            {logqlResult && !logqlSyntaxError && !logqlRunError && (
              <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {logqlResult.executionTimeMs !== null
                    ? `${logqlResult.executionTimeMs.toFixed(1)} ms`
                    : 'completed'}
                </span>
                <span>{logqlResult.totalCount.toLocaleString()} matching</span>
                {logqlResult.hasMore && (
                  <span className="text-yellow-400">
                    Results truncated — narrow the range or add `| limit`
                  </span>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Filter loaded logs by message, service, trace ID, or metadata..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
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
              onChange={e => setServiceFilter(e.target.value)}
              className="px-4 py-2 border border-white/10 rounded-lg bg-slate-800/50 text-white focus:outline-none focus:border-blue-500"
            >
              <option value="all">All Services</option>
              {services.map(service => (
                <option key={service} value={service}>
                  {service}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Load error (honest failure state, never silent) */}
        {loadError && mode === 'filters' && !isTailing && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg mb-4 text-sm bg-red-500/10 text-red-400 border border-red-500/30">
            <AlertCircle className="w-4 h-4" />
            {loadError}
            <button onClick={loadLogs} className="ml-auto underline hover:text-red-300">
              Retry
            </button>
          </div>
        )}

        {/* Stats Bar (log counts; not shown for table and timechart results) */}
        <div className={`${showQueryTable ? 'hidden' : 'flex'} gap-4 mb-4`}>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/30 rounded-lg">
            <FileText className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-300">
              {stats.total.toLocaleString()} logs
            </span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/20 rounded-lg">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <span className="text-sm font-medium text-red-400">
              {(stats.by_level.error || 0) + (stats.by_level.critical || 0)} errors
            </span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/20 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-yellow-600" />
            <span className="text-sm font-medium text-yellow-400">
              {stats.by_level.warning || 0} warnings
            </span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/20 rounded-lg">
            <Server className="w-4 h-4 text-blue-500" />
            <span className="text-sm font-medium text-blue-400">
              {Object.keys(stats.by_service).length} services
            </span>
          </div>
          {/* Truncation indicator (LF-025: never silent) */}
          {!isTailing && mode === 'filters' && total !== null && logs.length < total && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/30 rounded-lg">
              <span className="text-sm text-slate-400">
                Showing {logs.length.toLocaleString()} of {total.toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {/* Aggregation results (LogQL `stats` queries) */}
        {aggregationEntries.length > 0 && (
          <div className="mb-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/5 shadow-xl p-4">
            <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Aggregations</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {aggregationEntries.map(([key, value]) => (
                <div key={key} className="p-3 bg-slate-800/50 rounded-lg">
                  <p className="text-xs text-slate-400 font-mono truncate">{key}</p>
                  <p className="text-lg font-semibold text-white font-mono">
                    {typeof value === 'number' || typeof value === 'string'
                      ? String(value)
                      : JSON.stringify(value)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Query builder (Phase 6) */}
        {mode === 'logql' && showBuilder && (
          <QueryBuilder
            fields={Array.from(new Set([...LOGQL_FIELDS, ...catalogueFields]))}
            onClose={() => setShowBuilder(false)}
            onUse={(query) => {
              setLogqlQuery(query)
              setShowBuilder(false)
              requestAnimationFrame(() => logqlRunRef.current())
            }}
          />
        )}

        {/* Table and timechart results (Phase 6) */}
        {showQueryTable && logqlResult && (
          <QueryResults
            resultType={logqlResult.resultType as 'table' | 'timechart'}
            columns={logqlResult.columns}
            rows={logqlResult.rows}
            truncated={logqlResult.truncated}
          />
        )}

        {/* Log List */}
        <div className={`${showQueryTable ? 'hidden' : ''} flex-1 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/5 shadow-xl overflow-hidden flex flex-col relative`}>
          {/* Table Header */}
          <div className="flex items-center gap-4 px-4 py-2 bg-slate-800/50 border-b border-white/5 text-xs font-semibold text-slate-400 uppercase">
            <div className="w-8" />
            <div className="w-40">Timestamp</div>
            <div className="w-20">Level</div>
            <div className="w-32">Service</div>
            <div className="flex-1">Message</div>
            <div className="w-24">Trace</div>
          </div>

          {/* New-lines-while-paused affordance */}
          {isTailing && newWhilePaused > 0 && (
            <button
              onClick={resumeTail}
              className="absolute top-12 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-full text-sm font-medium shadow-lg"
            >
              <ArrowUp className="w-4 h-4" />
              {newWhilePaused.toLocaleString()} new — resume
            </button>
          )}

          {/* Log Entries */}
          <div ref={listRef} onScroll={handleListScroll} className="flex-1 overflow-y-auto">
            {showListLoading ? (
              <div className="p-8 text-center">
                <RefreshCw className="w-8 h-8 text-slate-300 animate-spin mx-auto mb-3" />
                <p className="text-slate-400">Loading logs...</p>
              </div>
            ) : displayedLogs.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                <p className="text-slate-400">
                  {isTailing
                    ? tail.status === 'live'
                      ? 'Waiting for new logs...'
                      : 'No logs streamed yet'
                    : mode === 'logql' && !logqlResult
                      ? 'Run a LogforgeQL query to see results'
                      : 'No logs found'}
                </p>
                {!isTailing && (
                  <p className="text-sm text-slate-400 mt-1">
                    {mode === 'logql'
                      ? 'Try an example from the syntax reference (? button)'
                      : 'Try adjusting your filters'}
                  </p>
                )}
              </div>
            ) : (
              <>
                <div className="divide-y divide-white/5">
                  {displayedLogs.map(log => {
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
                            {Object.keys(log.metadata || {}).length > 0 &&
                              (isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-slate-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-slate-400" />
                              ))}
                          </div>
                          <div className="w-40 text-xs text-slate-400 font-mono">
                            <div>{formatTimestamp(log.timestamp)}</div>
                            <div className="text-slate-400">{formatRelativeTime(log.timestamp)}</div>
                          </div>
                          <div className="w-20">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${levelStyle.bg} ${levelStyle.text}`}
                            >
                              {levelStyle.icon}
                              {log.level}
                            </span>
                          </div>
                          <div className="w-32">
                            <span className="text-sm text-slate-300 truncate block">{log.service}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <p
                              className={`text-sm truncate ${
                                log.level === 'error' || log.level === 'critical'
                                  ? 'text-red-400'
                                  : 'text-slate-300'
                              }`}
                            >
                              {log.message}
                            </p>
                          </div>
                          <button
                            data-testid="log-explain"
                            onClick={e => {
                              e.stopPropagation()
                              setSelectedLog(log)
                            }}
                            title="Explain this event"
                            className="flex items-center gap-1 px-2 py-0.5 rounded border border-white/10 text-xs text-slate-300 hover:bg-white/10 shrink-0"
                          >
                            <Sparkles className="w-3 h-3 text-blue-300" />
                            Explain
                          </button>
                          <div className="w-24">
                            {log.trace_id && (
                              <button
                                onClick={e => {
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
                        {isExpanded && Object.keys(log.metadata || {}).length > 0 && (
                          <div className="px-4 pb-4 pl-12">
                            <div className="p-4 bg-slate-900 rounded-lg">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400">Metadata</span>
                                <button
                                  onClick={() =>
                                    copyToClipboard(JSON.stringify(log.metadata || {}, null, 2))
                                  }
                                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                >
                                  <Copy className="w-3 h-3" />
                                  Copy
                                </button>
                              </div>
                              <pre className="text-xs text-green-400 overflow-x-auto">
                                {JSON.stringify(log.metadata || {}, null, 2)}
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
                                onClick={() => {
                                  if (mode === 'logql') {
                                    setLogqlQuery(`| where service = "${log.service}"`)
                                  } else {
                                    setServiceFilter(log.service)
                                  }
                                }}
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

                {/* Pagination footer (LF-025) */}
                {!isTailing && mode === 'filters' && (
                  <div className="py-3 text-center">
                    {isLoadingMore ? (
                      <div className="flex items-center justify-center gap-2 text-sm text-slate-400">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Loading more...
                      </div>
                    ) : hasMore ? (
                      <button
                        onClick={loadMore}
                        className="px-4 py-1.5 text-sm text-blue-400 hover:text-blue-300 border border-white/10 rounded-lg hover:bg-white/5"
                      >
                        Load more
                        {total !== null &&
                          ` (${(total - logs.length).toLocaleString()} remaining)`}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">
                        End of results
                        {total !== null && ` — ${total.toLocaleString()} total`}
                      </span>
                    )}
                    {/* Infinite-scroll sentinel */}
                    <div ref={sentinelRef} className="h-px" />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Log Detail Panel */}
        {selectedLog && (
          <div className="fixed inset-y-0 right-0 w-1/2 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border-l border-white/5 z-50 overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-white">Log Details</h3>
                <button onClick={() => setSelectedLog(null)} className="p-2 hover:bg-white/5 rounded-lg">
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
                <ExplainPanel log={selectedLog} onUseQuery={query => { setSelectedLog(null); useDraftedQuery(query) }} />
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
      {showFields && (
        <FieldSidebar
          window={(() => {
            const { start_time, end_time } = getApiTimeRange()
            const hours = Math.ceil((new Date(end_time).getTime() - new Date(start_time).getTime()) / 3600000)
            return `${Math.min(744, Math.max(1, hours || 24))}h`
          })()}
          onClose={() => setShowFields(false)}
          onFields={setCatalogueFields}
          onFilter={(field, value, exclude, type) => {
            setMode('logql')
            setLogqlQuery(current => addFilter(current, field, value, exclude, type))
            requestAnimationFrame(() => logqlRunRef.current())
          }}
        />
      )}
    </DashboardLayout>
  )
}
