'use client'

import { Clock, AlertCircle, CheckCircle, Layers } from 'lucide-react'
import type { Trace } from '@/app/observability/traces/page'

interface TraceListProps {
  traces: Trace[]
  selectedTrace: Trace | null
  onTraceSelect: (trace: Trace) => void
  isLoading: boolean
}

export default function TraceList({
  traces,
  selectedTrace,
  onTraceSelect,
  isLoading
}: TraceListProps) {
  const formatDuration = (microseconds: number) => {
    const ms = microseconds / 1000
    if (ms < 1) return `${microseconds}μs`
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  const formatTime = (microseconds: number) => {
    const date = new Date(microseconds / 1000)
    return date.toLocaleTimeString()
  }

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[700px]">
        <h2 className="text-lg font-semibold text-white mb-4">Traces</h2>
        <div className="flex items-center justify-center h-full">
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
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[700px]">
        <h2 className="text-lg font-semibold text-white mb-4">Traces</h2>
        <div className="flex items-center justify-center h-full">
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
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Traces</h2>
        <p className="text-sm text-slate-400 mt-1">{traces.length} results</p>
      </div>

      {/* Trace List */}
      <div className="overflow-y-auto max-h-[650px]">
        {traces.map((trace) => {
          const isSelected = selectedTrace?.trace_id === trace.trace_id
          const hasError = trace.status === 'error'

          return (
            <button
              key={trace.trace_id}
              onClick={() => onTraceSelect(trace)}
              className={`w-full p-4 border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors text-left ${
                isSelected ? 'bg-blue-900/20 border-l-4 border-l-blue-500' : ''
              }`}
            >
              {/* Service and Operation */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white truncate">
                      {trace.root_service}
                    </span>
                    {hasError ? (
                      <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-slate-400 truncate mt-1">
                    {trace.root_operation}
                  </p>
                </div>
              </div>

              {/* Metrics */}
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1 text-slate-400">
                  <Clock className="w-3 h-3" />
                  <span>{formatDuration(trace.duration)}</span>
                </div>
                <div className="flex items-center gap-1 text-slate-400">
                  <Layers className="w-3 h-3" />
                  <span>{trace.span_count} spans</span>
                </div>
                {hasError && (
                  <div className="text-red-400">
                    {trace.error_count} errors
                  </div>
                )}
              </div>

              {/* Services */}
              <div className="mt-2 flex flex-wrap gap-1">
                {trace.services.slice(0, 3).map((service) => (
                  <span
                    key={service}
                    className="px-2 py-0.5 bg-slate-700/50 text-slate-300 rounded text-xs"
                  >
                    {service}
                  </span>
                ))}
                {trace.services.length > 3 && (
                  <span className="px-2 py-0.5 bg-slate-700/50 text-slate-400 rounded text-xs">
                    +{trace.services.length - 3}
                  </span>
                )}
              </div>

              {/* Timestamp */}
              <div className="mt-2 text-xs text-slate-500">
                {formatTime(trace.start_time)}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
