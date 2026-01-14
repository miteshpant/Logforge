'use client'

import { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, AlertCircle, CheckCircle, Clock, Layers, ArrowUpDown } from 'lucide-react'
import type { Trace } from '@/app/observability/traces/page'

interface TraceTableProps {
  traces: Trace[]
  selectedTrace: Trace | null
  onTraceSelect: (trace: Trace) => void
  isLoading: boolean
}

type SortField = 'root_service' | 'root_operation' | 'duration' | 'span_count' | 'status' | 'start_time'
type SortDirection = 'asc' | 'desc'

export default function TraceTable({
  traces,
  selectedTrace,
  onTraceSelect,
  isLoading
}: TraceTableProps) {
  const [sortField, setSortField] = useState<SortField>('start_time')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  // Calculate P50, P95, P99 for duration color coding
  const durationStats = useMemo(() => {
    if (traces.length === 0) return { p50: 0, p95: 0, p99: 0 }

    const durations = traces.map(t => t.duration).sort((a, b) => a - b)
    const p50Index = Math.floor(durations.length * 0.5)
    const p95Index = Math.floor(durations.length * 0.95)
    const p99Index = Math.floor(durations.length * 0.99)

    return {
      p50: durations[p50Index] || 0,
      p95: durations[p95Index] || 0,
      p99: durations[p99Index] || 0
    }
  }, [traces])

  // Sort traces
  const sortedTraces = useMemo(() => {
    return [...traces].sort((a, b) => {
      let aVal: any = a[sortField]
      let bVal: any = b[sortField]

      // Handle string comparisons
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
        bVal = bVal.toLowerCase()
      }

      if (sortDirection === 'asc') {
        return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      } else {
        return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
      }
    })
  }, [traces, sortField, sortDirection])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const formatDuration = (microseconds: number) => {
    const ms = microseconds / 1000
    if (ms < 1) return `${microseconds.toFixed(0)}μs`
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatTime = (microseconds: number) => {
    const date = new Date(microseconds / 1000)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()

    if (diffMs < 60000) return 'Just now'
    if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)} min ago`
    if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)} hr ago`
    return date.toLocaleDateString()
  }

  const getDurationColor = (duration: number) => {
    if (duration >= durationStats.p99) return 'text-red-400 bg-red-500/10'
    if (duration >= durationStats.p95) return 'text-orange-400 bg-orange-500/10'
    if (duration >= durationStats.p50) return 'text-yellow-400 bg-yellow-500/10'
    return 'text-emerald-400 bg-emerald-500/10'
  }

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <th
      className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider cursor-pointer hover:text-white transition-colors group"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        {sortField === field ? (
          sortDirection === 'asc' ? (
            <ChevronUp className="w-4 h-4 text-blue-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-blue-400" />
          )
        ) : (
          <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-50 transition-opacity" />
        )}
      </div>
    </th>
  )

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-600 border-t-blue-500 mb-3"></div>
            <p className="text-slate-400 text-sm">Searching traces...</p>
          </div>
        </div>
      </div>
    )
  }

  if (traces.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center text-slate-400">
            <Layers className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No traces found</p>
            <p className="text-sm mt-1 text-slate-500">Try adjusting your search filters</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header with stats */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Traces</h2>
          <span className="text-sm text-slate-400">{traces.length} results</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>&lt; P50</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
            <span>P50-P95</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-orange-500"></span>
            <span>P95-P99</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            <span>&gt; P99</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
        <table className="w-full">
          <thead className="bg-slate-900/50 border-b border-slate-700 sticky top-0 z-10">
            <tr>
              <SortHeader field="root_service">Service</SortHeader>
              <SortHeader field="root_operation">Operation</SortHeader>
              <SortHeader field="duration">Duration</SortHeader>
              <SortHeader field="span_count">Spans</SortHeader>
              <SortHeader field="status">Status</SortHeader>
              <SortHeader field="start_time">Time</SortHeader>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {sortedTraces.map((trace) => {
              const isSelected = selectedTrace?.trace_id === trace.trace_id
              const hasError = trace.status === 'error'

              return (
                <tr
                  key={trace.trace_id}
                  onClick={() => onTraceSelect(trace)}
                  className={`
                    cursor-pointer transition-colors
                    ${isSelected
                      ? 'bg-blue-900/30 border-l-4 border-l-blue-500'
                      : 'hover:bg-slate-700/30 border-l-4 border-l-transparent'
                    }
                  `}
                >
                  {/* Service */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white text-sm">{trace.root_service}</span>
                      {trace.services.length > 1 && (
                        <span className="text-xs text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                          +{trace.services.length - 1}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Operation */}
                  <td className="px-4 py-3">
                    <span className="text-sm text-slate-300 font-mono truncate block max-w-xs">
                      {trace.root_operation}
                    </span>
                  </td>

                  {/* Duration with color coding */}
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-mono ${getDurationColor(trace.duration)}`}>
                      <Clock className="w-3 h-3" />
                      {formatDuration(trace.duration)}
                    </span>
                  </td>

                  {/* Spans */}
                  <td className="px-4 py-3">
                    <span className="text-sm text-slate-400 flex items-center gap-1">
                      <Layers className="w-3 h-3" />
                      {trace.span_count}
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    {hasError ? (
                      <span className="inline-flex items-center gap-1 text-red-400 text-sm">
                        <AlertCircle className="w-4 h-4" />
                        <span>Error</span>
                        {trace.error_count > 1 && (
                          <span className="text-xs bg-red-500/20 px-1.5 py-0.5 rounded">
                            {trace.error_count}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-emerald-400 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        <span>OK</span>
                      </span>
                    )}
                  </td>

                  {/* Time */}
                  <td className="px-4 py-3">
                    <span className="text-sm text-slate-500">{formatTime(trace.start_time)}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
