'use client'

import { useState } from 'react'
import { Clock, AlertTriangle, ChevronRight, ChevronDown, Info } from 'lucide-react'
import type { Trace, Span } from '@/app/observability/traces/page'

interface TraceWaterfallProps {
  trace: Trace | null
  isLoading: boolean
}

export default function TraceWaterfall({ trace, isLoading }: TraceWaterfallProps) {
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set())
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null)

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[700px] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-600 border-t-blue-500 mb-3"></div>
          <p className="text-slate-400 text-sm">Loading trace details...</p>
        </div>
      </div>
    )
  }

  if (!trace) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[700px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Select a trace to view details</p>
        </div>
      </div>
    )
  }

  if (!trace.spans || trace.spans.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[700px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <Info className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No span data available for this trace</p>
        </div>
      </div>
    )
  }

  // Build span hierarchy
  const spanMap = new Map<string, Span>()
  const rootSpans: Span[] = []
  const childrenMap = new Map<string, Span[]>()

  trace.spans.forEach(span => {
    spanMap.set(span.span_id, span)
    if (!span.parent_span_id) {
      rootSpans.push(span)
    } else {
      if (!childrenMap.has(span.parent_span_id)) {
        childrenMap.set(span.parent_span_id, [])
      }
      childrenMap.get(span.parent_span_id)!.push(span)
    }
  })

  // Calculate trace timeline
  const minStartTime = Math.min(...trace.spans.map(s => s.start_time))
  const maxEndTime = Math.max(...trace.spans.map(s => s.start_time + s.duration))
  const totalDuration = maxEndTime - minStartTime

  const toggleSpan = (spanId: string) => {
    const newExpanded = new Set(expandedSpans)
    if (newExpanded.has(spanId)) {
      newExpanded.delete(spanId)
    } else {
      newExpanded.add(spanId)
    }
    setExpandedSpans(newExpanded)
  }

  const formatDuration = (microseconds: number) => {
    const ms = microseconds / 1000
    if (ms < 1) return `${microseconds}μs`
    if (ms < 1000) return `${ms.toFixed(2)}ms`
    return `${(ms / 1000).toFixed(3)}s`
  }

  const getSpanColor = (span: Span) => {
    if (span.status === 'error') return 'bg-red-500'
    if (span.service_name.includes('database') || span.service_name.includes('postgres')) return 'bg-purple-500'
    if (span.service_name.includes('cache') || span.service_name.includes('redis')) return 'bg-orange-500'
    if (span.service_name.includes('external')) return 'bg-slate-500'
    return 'bg-blue-500'
  }

  const renderSpan = (span: Span, depth: number = 0) => {
    const children = childrenMap.get(span.span_id) || []
    const hasChildren = children.length > 0
    const isExpanded = expandedSpans.has(span.span_id)
    const isSelected = selectedSpan?.span_id === span.span_id

    // Calculate position and width for timeline bar
    const startOffset = ((span.start_time - minStartTime) / totalDuration) * 100
    const width = (span.duration / totalDuration) * 100

    return (
      <div key={span.span_id} className="mb-1">
        {/* Span Row */}
        <div
          className={`group hover:bg-slate-700/30 transition-colors ${
            isSelected ? 'bg-blue-900/20' : ''
          }`}
        >
          <div className="flex items-center py-2 px-4">
            {/* Left: Span Info */}
            <div
              className="flex items-center gap-2 flex-1 min-w-0"
              style={{ paddingLeft: `${depth * 24}px` }}
            >
              {/* Expand/Collapse */}
              {hasChildren ? (
                <button
                  onClick={() => toggleSpan(span.span_id)}
                  className="flex-shrink-0 p-0.5 hover:bg-slate-600 rounded transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  )}
                </button>
              ) : (
                <div className="w-5" />
              )}

              {/* Service Name */}
              <span className="text-xs font-medium text-slate-300 truncate flex-shrink-0" style={{ minWidth: '120px', maxWidth: '120px' }}>
                {span.service_name}
              </span>

              {/* Operation Name */}
              <span className="text-xs text-slate-400 truncate flex-1 min-w-0">
                {span.operation_name}
              </span>

              {/* Error Indicator */}
              {span.status === 'error' && (
                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
              )}
            </div>

            {/* Right: Timeline and Duration */}
            <div className="flex items-center gap-4 flex-shrink-0 ml-4" style={{ width: '500px' }}>
              {/* Timeline Bar */}
              <div className="relative flex-1 h-6 bg-slate-800/50 rounded overflow-hidden">
                <div
                  className={`absolute h-full ${getSpanColor(span)} opacity-80 hover:opacity-100 transition-opacity cursor-pointer`}
                  style={{
                    left: `${startOffset}%`,
                    width: `${Math.max(width, 0.5)}%`
                  }}
                  onClick={() => setSelectedSpan(span)}
                  title={`${span.operation_name} - ${formatDuration(span.duration)}`}
                />
              </div>

              {/* Duration */}
              <span className="text-xs font-mono text-slate-400 w-20 text-right">
                {formatDuration(span.duration)}
              </span>
            </div>
          </div>
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div>
            {children
              .sort((a, b) => a.start_time - b.start_time)
              .map(child => renderSpan(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-white">Trace Timeline</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">
              {trace.span_count} spans
            </span>
            <span className="text-xs text-slate-400">•</span>
            <span className="text-xs text-slate-400">
              {formatDuration(trace.duration)} total
            </span>
          </div>
        </div>

        {/* Trace ID */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Trace ID:</span>
          <code className="text-xs text-slate-300 bg-slate-900/50 px-2 py-1 rounded font-mono">
            {trace.trace_id}
          </code>
        </div>
      </div>

      {/* Waterfall */}
      <div className="overflow-y-auto" style={{ maxHeight: '600px' }}>
        {/* Header Row */}
        <div className="sticky top-0 z-10 bg-slate-800 border-b border-slate-700 py-2 px-4">
          <div className="flex items-center">
            <div className="flex-1">
              <span className="text-xs font-semibold text-slate-400">Service / Operation</span>
            </div>
            <div className="flex items-center gap-4 flex-shrink-0 ml-4" style={{ width: '500px' }}>
              <span className="text-xs font-semibold text-slate-400 flex-1">Timeline</span>
              <span className="text-xs font-semibold text-slate-400 w-20 text-right">Duration</span>
            </div>
          </div>
        </div>

        {/* Spans */}
        <div className="py-2">
          {rootSpans
            .sort((a, b) => a.start_time - b.start_time)
            .map(span => renderSpan(span, 0))}
        </div>
      </div>

      {/* Selected Span Details */}
      {selectedSpan && (
        <div className="border-t border-slate-700 p-4 bg-slate-900/50">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Span Details</h3>
            <button
              onClick={() => setSelectedSpan(null)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-slate-500">Span ID:</span>
              <div className="text-slate-300 font-mono mt-1">{selectedSpan.span_id}</div>
            </div>
            <div>
              <span className="text-slate-500">Service:</span>
              <div className="text-slate-300 mt-1">{selectedSpan.service_name}</div>
            </div>
            <div>
              <span className="text-slate-500">Operation:</span>
              <div className="text-slate-300 mt-1">{selectedSpan.operation_name}</div>
            </div>
            <div>
              <span className="text-slate-500">Duration:</span>
              <div className="text-slate-300 mt-1">{formatDuration(selectedSpan.duration)}</div>
            </div>
          </div>

          {/* Tags */}
          {Object.keys(selectedSpan.tags).length > 0 && (
            <div className="mt-4">
              <span className="text-slate-500 text-xs">Tags:</span>
              <div className="mt-2 space-y-1">
                {Object.entries(selectedSpan.tags).map(([key, value]) => (
                  <div key={key} className="flex items-start gap-2 text-xs">
                    <span className="text-slate-400 font-mono">{key}:</span>
                    <span className="text-slate-300 font-mono flex-1">{JSON.stringify(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
