'use client'

import { useState, useEffect, useRef } from 'react'
import { apiClient } from '@/lib/api'

type StreamType = 'alerts' | 'security' | 'traces' | 'metrics'

interface StreamEvent {
  id: string
  timestamp: string
  type: string
  data: any
}

export default function LiveStreamingPanel() {
  const [activeStream, setActiveStream] = useState<StreamType>('alerts')
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isExpanded, setIsExpanded] = useState(true) // Default to expanded
  const cleanupRef = useRef<(() => void) | null>(null)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (isExpanded && eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, isExpanded])

  // Connect to SSE stream
  useEffect(() => {
    if (!isExpanded) {
      // Disconnect when panel is collapsed
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
        setIsConnected(false)
      }
      return
    }

    // Clear events when switching streams
    setEvents([])
    setIsConnected(false)

    // Connect to stream
    connectToStream()

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
        setIsConnected(false)
      }
    }
  }, [activeStream, isExpanded])

  const connectToStream = async () => {
    try {
      const url = `/v1/stream/${activeStream}`

      console.log('Connecting to stream:', url)

      console.log('Stream connected successfully')
      setIsConnected(true)

      // Use apiClient.getStream for proper auth handling
      const cleanup = await apiClient.getStream(
        url,
        (data) => {
          // Handle incoming stream data
          console.log('📥 SSE event received:', {
            event_type: data.event_type,
            alert_id: data.alert_id,
            status: data.status,
            fullData: data
          })

          // Filter out background status checks
          if (data.status === 'listening' || data.status === 'streaming_started') {
            console.log('⏸️  Background status check, skipping UI update')
            return
          }

          const newEvent: StreamEvent = {
            id: data.id || data.alert_id || Date.now().toString(),
            timestamp: data.timestamp || data.triggered_at || new Date().toISOString(),
            type: data.event_type || data.type || 'message',
            data: data
          }

          console.log('✅ Adding event to UI:', newEvent)

          setEvents(prev => {
            const updated = [newEvent, ...prev]
            console.log(`📊 Total events in UI: ${updated.length}`)
            return updated.slice(0, 50) // Keep last 50 events
          })
        },
        (error) => {
          // Handle errors
          console.error('❌ Stream error:', error)
          setIsConnected(false)
        }
      )

      // Store cleanup function for later use
      if (cleanupRef.current) {
        // If there's already a cleanup function, call it
        cleanupRef.current()
      }
      cleanupRef.current = cleanup
    } catch (error) {
      console.error('Stream connection error:', error)
      setIsConnected(false)
    }
  }

  const getEventIcon = (type: string) => {
    if (type.includes('alert')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
          <line x1="12" y1="9" x2="12" y2="13"></line>
          <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
      )
    } else if (type.includes('security')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      )
    } else if (type.includes('trace')) {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      )
    } else {
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="12" y1="1" x2="12" y2="23"></line>
          <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
        </svg>
      )
    }
  }

  const getEventColor = (type: string) => {
    if (type.includes('triggered') || type.includes('critical')) return 'text-red-400'
    if (type.includes('security') || type.includes('threat')) return 'text-purple-400'
    if (type.includes('resolved') || type.includes('acknowledged')) return 'text-green-400'
    if (type.includes('trace')) return 'text-blue-400'
    return 'text-cyan-400'
  }

  const getSeverityBadge = (severity: string) => {
    const severityColors: Record<string, string> = {
      critical: 'bg-red-500/20 text-red-400 border-red-500/30',
      high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      info: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30'
    }
    return severityColors[severity] || severityColors.info
  }

  const renderAlertCard = (event: StreamEvent) => {
    const data = event.data
    const severity = data.severity || 'info'
    const ruleName = data.rule_name || 'Unknown Alert'
    const message = data.message || 'No message available'
    const status = data.status || 'unknown'

    return (
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase border ${getSeverityBadge(severity)}`}>
              {severity}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
              status === 'triggered' ? 'bg-red-500/20 text-red-400' :
              status === 'resolved' ? 'bg-green-500/20 text-green-400' :
              'bg-slate-500/20 text-slate-400'
            }`}>
              {status.toUpperCase()}
            </span>
          </div>
          <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <h4 className="text-white font-bold text-base mb-1">{ruleName}</h4>
        <p className="text-slate-300 text-sm leading-relaxed">{message}</p>
      </div>
    )
  }

  const renderSecurityCard = (event: StreamEvent) => {
    const data = event.data
    const severity = data.severity || data.level || 'info'
    const title = data.title || data.detection_name || 'Security Event'
    const description = data.description || data.message || 'Security event detected'

    return (
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase border ${getSeverityBadge(severity)}`}>
            {severity}
          </span>
          <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <h4 className="text-white font-bold text-base mb-1">{title}</h4>
        <p className="text-slate-300 text-sm leading-relaxed">{description}</p>
        {data.src_ip && (
          <div className="mt-2 flex items-center gap-4 text-xs text-slate-400">
            <span>Source IP: <span className="text-purple-400 font-mono">{data.src_ip}</span></span>
            {data.target_user && <span>User: <span className="text-purple-400 font-mono">{data.target_user}</span></span>}
          </div>
        )}
      </div>
    )
  }

  const renderTraceCard = (event: StreamEvent) => {
    const data = event.data

    // Extract trace data from OpenTelemetry structure
    // traces[] contains trace objects with nested spans
    const traces = data.traces || []
    const firstTrace = traces[0] || {}

    // Use OpenTelemetry field names: root_service, root_operation
    const serviceName = firstTrace.root_service ||
                       firstTrace.service_name ||
                       data.service_name ||
                       'Unknown Service'
    const operation = firstTrace.root_operation ||
                     firstTrace.operation_name ||
                     data.operation_name ||
                     'Unknown Operation'
    const duration = firstTrace.duration_ms ? `${firstTrace.duration_ms}ms` :
                    data.duration_ms ? `${data.duration_ms}ms` : 'N/A'
    const status = firstTrace.status || data.status || 'ok'
    const traceId = firstTrace.trace_id || data.trace_id
    const spanCount = firstTrace.span_count || traces.reduce((acc: number, t: any) => acc + (t.span_count || 0), 0)
    const serviceCount = firstTrace.service_count || firstTrace.services?.length || 0

    return (
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-400">
              {serviceName}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
              status === 'error' ? 'bg-red-500/20 text-red-400' :
              'bg-green-500/20 text-green-400'
            }`}>
              {status.toUpperCase()}
            </span>
            {spanCount > 0 && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-600/50 text-slate-300">
                {spanCount} spans
              </span>
            )}
            {serviceCount > 1 && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-500/20 text-purple-400">
                {serviceCount} services
              </span>
            )}
          </div>
          <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <h4 className="text-white font-bold text-base mb-1">{operation}</h4>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span>Duration: <span className="text-blue-400 font-mono">{duration}</span></span>
          {traceId && <span>Trace: <span className="text-blue-400 font-mono">{traceId.substring(0, 8)}...</span></span>}
        </div>
      </div>
    )
  }

  const renderMetricCard = (event: StreamEvent) => {
    const data = event.data

    // Extract metrics from OpenTelemetry structure
    // metrics[] contains individual metric objects
    const metrics = data.metrics || []
    const metricsCount = data.metrics_count || metrics.length
    const firstMetric = metrics[0] || {}

    // Extract metric data - check both metric object and top-level data
    const metricName = firstMetric.metric_name ||
                      firstMetric.name ||
                      data.metric_name ||
                      data.name ||
                      'Unknown Metric'
    const value = firstMetric.value !== undefined ? firstMetric.value :
                 data.value !== undefined ? data.value : 'N/A'
    const unit = firstMetric.labels?.unit ||
                firstMetric.unit ||
                data.unit || ''
    const serviceName = firstMetric.service_name ||
                       firstMetric.resource?.['service.name'] ||
                       data.service_name

    // Format value for display
    const displayValue = typeof value === 'number' ? value.toFixed(2) : value

    return (
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-xs font-semibold bg-cyan-500/20 text-cyan-400">
              METRIC
            </span>
            {serviceName && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400">
                {serviceName}
              </span>
            )}
            {metricsCount > 1 && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-600/50 text-slate-300">
                +{metricsCount - 1} more
              </span>
            )}
          </div>
          <span className="text-xs text-slate-500 font-mono whitespace-nowrap">
            {new Date(event.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <h4 className="text-white font-bold text-base mb-1">{metricName}</h4>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-cyan-400">{displayValue}</span>
          {unit && <span className="text-sm text-slate-400">{unit}</span>}
        </div>
      </div>
    )
  }

  const renderEventCard = (event: StreamEvent) => {
    if (event.type.includes('alert')) {
      return renderAlertCard(event)
    } else if (event.type.includes('security')) {
      return renderSecurityCard(event)
    } else if (event.type.includes('trace')) {
      return renderTraceCard(event)
    } else if (event.type.includes('metric')) {
      return renderMetricCard(event)
    } else {
      // Fallback for unknown event types
      return renderAlertCard(event)
    }
  }

  const tabs = [
    { id: 'alerts' as StreamType, label: 'Alerts', icon: '🚨' },
    { id: 'security' as StreamType, label: 'Security', icon: '🛡️' },
    { id: 'traces' as StreamType, label: 'Traces', icon: '📊' },
    { id: 'metrics' as StreamType, label: 'Metrics', icon: '📈' }
  ]

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
            <span className="text-white font-bold text-lg">Live Streaming</span>
          </div>
          <span className="text-xs text-slate-400">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveStream(tab.id)}
              className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all duration-200 ${
                activeStream === tab.id
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                  : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-white'
              }`}
            >
              <span className="mr-1">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Collapse/Expand Button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          title={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="18 15 12 9 6 15"></polyline>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          )}
        </button>
      </div>

      {/* Events Stream - Collapsible */}
      {isExpanded && (
        <div className="overflow-y-auto px-6 py-4 max-h-96" style={{ height: '400px' }}>
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mb-4 opacity-50">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
              <p className="text-sm">
                {isConnected ? 'Waiting for events...' : 'Connecting to stream...'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {events.map((event, index) => (
                <div
                  key={event.id}
                  className="p-3 rounded-lg bg-slate-800/50 border border-white/5 hover:border-white/10 transition-all duration-200"
                  style={{
                    opacity: 1 - (index * 0.02),
                    animation: index === 0 ? 'slideIn 0.3s ease-out' : 'none'
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className={`mt-1 flex-shrink-0 ${getEventColor(event.type)}`}>
                      {getEventIcon(event.type)}
                    </div>
                    {renderEventCard(event)}
                  </div>
                </div>
              ))}
              <div ref={eventsEndRef} />
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  )
}