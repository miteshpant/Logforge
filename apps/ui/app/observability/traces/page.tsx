'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import TraceSearch from '@/components/observability/TraceSearch'
import TraceList from '@/components/observability/TraceList'
import TraceWaterfall from '@/components/observability/TraceWaterfall'
import { apiClient } from '@/lib/api'
import { useTimeRange } from '@/contexts/TimeRangeContext'

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

export default function TracesPage() {
  const { getApiTimeRange } = useTimeRange()
  const [traces, setTraces] = useState<Trace[]>([])
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null)
  const [isLoadingTraces, setIsLoadingTraces] = useState(false)
  const [isLoadingDetails, setIsLoadingDetails] = useState(false)
  const [filters, setFilters] = useState<TraceSearchFilters>({ status: 'all' })

  const searchTraces = async (searchFilters: TraceSearchFilters) => {
    try {
      setIsLoadingTraces(true)
      setFilters(searchFilters)

      const { start_time, end_time } = getApiTimeRange()

      const response = await apiClient.post<{ traces: Trace[] }>('/v1/observability/traces/search', {
        start_time,
        end_time,
        ...searchFilters,
        limit: 100
      })

      const data = response?.data || response

      if (data && 'traces' in data) {
        setTraces(data.traces)
      } else {
        // Mock data for development
        setTraces(generateMockTraces())
      }
    } catch (error) {
      console.error('Failed to search traces:', error)
      // Set mock data on error
      setTraces(generateMockTraces())
    } finally {
      setIsLoadingTraces(false)
    }
  }

  const loadTraceDetails = async (trace: Trace) => {
    try {
      setIsLoadingDetails(true)
      setSelectedTrace(trace)

      // If spans already loaded, skip API call
      if (trace.spans) {
        return
      }

      const response = await apiClient.get<{ spans: Span[] }>(
        `/v1/observability/traces/${trace.trace_id}/spans`
      )

      const data = response?.data || response

      if (data && 'spans' in data) {
        setSelectedTrace({
          ...trace,
          spans: data.spans
        })
      } else {
        // Mock spans data
        setSelectedTrace({
          ...trace,
          spans: generateMockSpans(trace.trace_id)
        })
      }
    } catch (error) {
      console.error('Failed to load trace details:', error)
      // Set mock spans on error
      setSelectedTrace({
        ...trace,
        spans: generateMockSpans(trace.trace_id)
      })
    } finally {
      setIsLoadingDetails(false)
    }
  }

  // Initial search
  useEffect(() => {
    searchTraces({ status: 'all' })
  }, [])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white">Distributed Tracing</h1>
          <p className="text-slate-400 mt-1">
            Explore distributed traces across your microservices
          </p>
        </div>

        {/* Search Filters */}
        <TraceSearch onSearch={searchTraces} isLoading={isLoadingTraces} />

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Trace List */}
          <div className="lg:col-span-1">
            <TraceList
              traces={traces}
              selectedTrace={selectedTrace}
              onTraceSelect={loadTraceDetails}
              isLoading={isLoadingTraces}
            />
          </div>

          {/* Waterfall Visualization */}
          <div className="lg:col-span-2">
            <TraceWaterfall
              trace={selectedTrace}
              isLoading={isLoadingDetails}
            />
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}

// Mock data generators
function generateMockTraces(): Trace[] {
  const services = ['frontend', 'api-gateway', 'auth-service', 'user-service', 'order-service', 'payment-service']
  const operations = ['GET /', 'POST /api/users', 'GET /api/orders', 'POST /api/payments', 'GET /health']

  return Array.from({ length: 20 }, (_, i) => {
    const hasError = Math.random() < 0.15
    const spanCount = Math.floor(Math.random() * 15) + 3
    const duration = hasError
      ? Math.floor(Math.random() * 5000000) + 1000000 // 1-6 seconds for errors
      : Math.floor(Math.random() * 500000) + 50000 // 50-550ms for success

    return {
      trace_id: `trace-${Date.now()}-${i}`,
      root_service: services[Math.floor(Math.random() * services.length)],
      root_operation: operations[Math.floor(Math.random() * operations.length)],
      start_time: Date.now() * 1000 - Math.floor(Math.random() * 3600000000), // within last hour
      duration,
      span_count: spanCount,
      error_count: hasError ? Math.floor(Math.random() * 3) + 1 : 0,
      status: hasError ? 'error' : 'ok',
      services: services.slice(0, Math.floor(Math.random() * 4) + 2)
    }
  }).sort((a, b) => b.start_time - a.start_time)
}

function generateMockSpans(traceId: string): Span[] {
  const services = ['frontend', 'api-gateway', 'auth-service', 'user-service', 'order-service', 'payment-service', 'postgres', 'redis']
  const operations = [
    'HTTP GET /',
    'HTTP POST /api/users',
    'authenticate',
    'query.users.findById',
    'cache.get',
    'db.query',
    'payment.process',
    'external.call'
  ]

  const rootSpan: Span = {
    span_id: `span-0`,
    trace_id: traceId,
    parent_span_id: null,
    service_name: 'api-gateway',
    operation_name: 'HTTP GET /api/orders',
    start_time: Date.now() * 1000,
    duration: 450000, // 450ms
    status: 'ok',
    tags: {
      'http.method': 'GET',
      'http.url': '/api/orders',
      'http.status_code': 200
    }
  }

  const childSpans: Span[] = Array.from({ length: 8 }, (_, i) => {
    const parentIdx = Math.floor(Math.random() * (i + 1))
    const startOffset = Math.floor(Math.random() * 100000)
    const duration = Math.floor(Math.random() * 150000) + 10000
    const hasError = Math.random() < 0.1

    return {
      span_id: `span-${i + 1}`,
      trace_id: traceId,
      parent_span_id: parentIdx === 0 ? rootSpan.span_id : `span-${parentIdx}`,
      service_name: services[Math.floor(Math.random() * services.length)],
      operation_name: operations[Math.floor(Math.random() * operations.length)],
      start_time: rootSpan.start_time + startOffset,
      duration,
      status: hasError ? 'error' : 'ok',
      tags: {
        'component': 'http',
        'span.kind': 'client',
        ...(hasError && { 'error': true, 'error.message': 'Connection timeout' })
      }
    }
  })

  return [rootSpan, ...childSpans].sort((a, b) => a.start_time - b.start_time)
}
