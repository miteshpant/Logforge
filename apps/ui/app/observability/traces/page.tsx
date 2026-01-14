'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import TraceSearch from '@/components/observability/TraceSearch'
import TraceTable from '@/components/observability/TraceTable'
import TraceWaterfall from '@/components/observability/TraceWaterfall'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { useSearchParams } from 'next/navigation'
import { Filter } from 'lucide-react'

export interface Span {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  service_name: string
  operation_name: string
  start_time: number // microseconds
  duration: number // microseconds
  status: 'ok' | 'error'
  tags: Record<string, any>
  logs?: Array<{
    timestamp: number
    fields: Record<string, any>
  }>
}

export interface Trace {
  trace_id: string
  root_service: string
  root_operation: string
  start_time: number
  duration: number // microseconds
  span_count: number
  error_count: number
  status: 'ok' | 'error'
  services: string[]
  spans?: Span[]
}

export interface TraceSearchFilters {
  service?: string
  operation?: string
  min_duration?: number // microseconds
  max_duration?: number
  status?: 'ok' | 'error' | 'all'
  tags?: Record<string, string>
}

// Raw span data from API (uses duration_ms, different field names)
interface ApiSpan {
  id?: string
  span_id: string
  trace_id: string
  parent_span_id: string | null
  service_name: string
  operation_name: string
  start_time: string | number
  end_time?: string | number
  duration_ms: number
  kind?: string
  status: string
  attributes?: Record<string, any>
  events?: Array<any>
  links?: Array<any>
  resource?: Record<string, any>
}

// Transform API span to UI Span format
function transformSpan(apiSpan: ApiSpan): Span {
  // Convert start_time to microseconds if it's a string (ISO format)
  let startTimeMicros: number
  if (typeof apiSpan.start_time === 'string') {
    startTimeMicros = new Date(apiSpan.start_time).getTime() * 1000
  } else {
    // Assume it's already in microseconds or milliseconds
    startTimeMicros = apiSpan.start_time > 1e15 ? apiSpan.start_time : apiSpan.start_time * 1000
  }

  return {
    span_id: apiSpan.span_id,
    trace_id: apiSpan.trace_id,
    parent_span_id: apiSpan.parent_span_id,
    service_name: apiSpan.service_name,
    operation_name: apiSpan.operation_name,
    start_time: startTimeMicros,
    duration: apiSpan.duration_ms * 1000, // Convert ms to microseconds
    status: apiSpan.status === 'error' ? 'error' : 'ok',
    tags: apiSpan.attributes || {}
  }
}


export default function TracesPage() {
  const { getApiTimeRange } = useTimeRange()
  const searchParams = useSearchParams()
  const [traces, setTraces] = useState<Trace[]>([])
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null)
  const [isLoadingTraces, setIsLoadingTraces] = useState(false)
  const [isLoadingDetails, setIsLoadingDetails] = useState(false)
  const [filters, setFilters] = useState<TraceSearchFilters>({ status: 'all' })
  const [initialSearchDone, setInitialSearchDone] = useState(false)

  // Get filters from URL query params (for linking from service map, APM page, etc.)
  const serviceFromUrl = searchParams.get('service')
  const operationFromUrl = searchParams.get('operation')
  const minDurationFromUrl = searchParams.get('min_duration') // in milliseconds

  const searchTraces = async (searchFilters: TraceSearchFilters) => {
    try {
      setIsLoadingTraces(true)
      setFilters(searchFilters)

      const { start_time, end_time } = getApiTimeRange()

      // Map UI filter names to API field names
      const apiFilters: Record<string, any> = {
        start_time,
        end_time,
        limit: 100
      }

      // Map filter fields to API expected names
      if (searchFilters.service) {
        apiFilters.service_name = searchFilters.service
      }
      if (searchFilters.operation) {
        apiFilters.operation_name = searchFilters.operation
      }
      if (searchFilters.min_duration) {
        // UI sends microseconds, API expects milliseconds
        apiFilters.min_duration_ms = Math.floor(searchFilters.min_duration / 1000)
      }
      if (searchFilters.max_duration) {
        apiFilters.max_duration_ms = Math.floor(searchFilters.max_duration / 1000)
      }
      if (searchFilters.status && searchFilters.status !== 'all') {
        apiFilters.status = searchFilters.status
      }

      const response = await apiClient.post('/v1/observability/traces/search', apiFilters)

      // Handle nested response wrapper
      const data = response?.data?.data || response?.data || response

      if (data && 'traces' in data && Array.isArray(data.traces)) {
        // API returns pre-aggregated trace summaries, transform to UI format
        const uiTraces: Trace[] = data.traces.map((t: any) => {
          // Convert start_time to microseconds (field is trace_start_time from API)
          const startTimeValue = t.trace_start_time || t.start_time
          let startTimeMicros: number
          if (typeof startTimeValue === 'string') {
            startTimeMicros = new Date(startTimeValue).getTime() * 1000
          } else {
            startTimeMicros = startTimeValue > 1e15 ? startTimeValue : startTimeValue * 1000
          }

          // Status field is trace_status from API
          const statusValue = t.trace_status || t.status

          return {
            trace_id: t.trace_id,
            root_service: t.root_service || t.services?.[0] || 'unknown',
            root_operation: t.root_operation || 'unknown',
            start_time: startTimeMicros,
            duration: (t.duration_ms || 0) * 1000, // Convert ms to microseconds
            span_count: t.span_count || 1,
            error_count: t.error_count || 0,
            status: statusValue === 'error' ? 'error' : 'ok',
            services: Array.isArray(t.services) ? t.services : [t.root_service || 'unknown']
          }
        })
        setTraces(uiTraces)
      } else {
        // No data returned
        setTraces([])
      }
    } catch (error) {
      console.error('Failed to search traces:', error)
      setTraces([])
    } finally {
      setIsLoadingTraces(false)
    }
  }

  const loadTraceDetails = async (trace: Trace) => {
    try {
      setIsLoadingDetails(true)
      setSelectedTrace(trace)

      // If spans already loaded, skip API call
      if (trace.spans && trace.spans.length > 0) {
        setIsLoadingDetails(false)
        return
      }

      // Use GET /v1/observability/traces/{trace_id} endpoint
      const response = await apiClient.get(`/v1/observability/traces/${trace.trace_id}`)

      // Handle nested response wrapper
      const data = response?.data?.data || response?.data || response

      if (data && data.trace && data.trace.spans) {
        // Transform API spans to UI format
        const uiSpans = data.trace.spans.map(transformSpan)
        setSelectedTrace({
          ...trace,
          spans: uiSpans
        })
      } else {
        // No spans found
        setSelectedTrace({
          ...trace,
          spans: []
        })
      }
    } catch (error) {
      console.error('Failed to load trace details:', error)
      setSelectedTrace({
        ...trace,
        spans: []
      })
    } finally {
      setIsLoadingDetails(false)
    }
  }

  // Initial search - apply filters from URL params
  useEffect(() => {
    if (!initialSearchDone) {
      const initialFilters: TraceSearchFilters = { status: 'all' }
      if (serviceFromUrl) {
        initialFilters.service = serviceFromUrl
      }
      if (operationFromUrl) {
        initialFilters.operation = operationFromUrl
      }
      if (minDurationFromUrl) {
        // URL param is in milliseconds, convert to microseconds for filter
        initialFilters.min_duration = parseInt(minDurationFromUrl) * 1000
      }
      searchTraces(initialFilters)
      setInitialSearchDone(true)
    }
  }, [serviceFromUrl, operationFromUrl, minDurationFromUrl, initialSearchDone])

  const [showFilters, setShowFilters] = useState(true)

  return (
    <DashboardLayout>
      <div className="space-y-4">
        {/* Compact Header with Filter Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Distributed Tracing</h1>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors flex items-center gap-2"
          >
            <Filter className="w-4 h-4" />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </button>
        </div>

        {/* Collapsible Search Filters */}
        {showFilters && (
          <TraceSearch
            onSearch={searchTraces}
            isLoading={isLoadingTraces}
            initialService={serviceFromUrl || undefined}
            initialOperation={operationFromUrl || undefined}
            initialMinDuration={minDurationFromUrl ? parseInt(minDurationFromUrl) : undefined}
          />
        )}

        {/* Trace Table */}
        <TraceTable
          traces={traces}
          selectedTrace={selectedTrace}
          onTraceSelect={loadTraceDetails}
          isLoading={isLoadingTraces}
        />

        {/* Waterfall Visualization - shows when trace is selected */}
        {selectedTrace && (
          <TraceWaterfall
            trace={selectedTrace}
            isLoading={isLoadingDetails}
          />
        )}
      </div>
    </DashboardLayout>
  )
}
