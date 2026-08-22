'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LiveMetricsChart from '@/components/observability/LiveMetricsChart'
import MetricsConfiguration from '@/components/observability/MetricsConfiguration'
import { apiClient } from '@/lib/api'
import { Play, Pause, Download, AlertCircle, RefreshCw, WifiOff } from 'lucide-react'

export interface MetricDataPoint {
  timestamp: number
  service: string
  metric_name: string
  value: number
  unit: string
}

export interface StreamConfig {
  services: string[]
  metrics: string[]
  interval: number // milliseconds
}

const STREAM_ENDPOINT = '/v1/stream/metrics'
const MAX_RECONNECT_DELAY_MS = 30000

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected'

export default function LiveMetricsPage() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('idle')
  const [streamError, setStreamError] = useState<string | null>(null)
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [dataPoints, setDataPoints] = useState<MetricDataPoint[]>([])
  const [config, setConfig] = useState<StreamConfig>({
    services: [],
    metrics: ['latency', 'throughput', 'error_rate'],
    interval: 1000 // 1 second
  })
  const [alertThresholds, setAlertThresholds] = useState<Record<string, number>>({
    latency: 500,
    error_rate: 5
  })
  const [alerts, setAlerts] = useState<string[]>([])

  const stopStreamRef = useRef<(() => void) | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const manualStopRef = useRef(false)
  const attemptRef = useRef(0)
  const configRef = useRef(config)
  const thresholdsRef = useRef(alertThresholds)

  useEffect(() => { configRef.current = config }, [config])
  useEffect(() => { thresholdsRef.current = alertThresholds }, [alertThresholds])

  const isStreaming = connectionState === 'connected' || connectionState === 'connecting'

  // Turn a raw metric record from the stream into a data point.
  // Only real, numeric values received from the server become points —
  // records without a usable value are dropped, never invented.
  const toDataPoint = (record: any, fallbackTimestamp: number): MetricDataPoint | null => {
    const metricName = record?.metric_name
    const value = record?.value
    if (typeof metricName !== 'string' || metricName === '') return null
    const numeric = typeof value === 'number' ? value : Number(value)
    if (!Number.isFinite(numeric)) return null

    const service = record?.service_name || record?.service || 'unknown'
    const ts = record?.timestamp ? Date.parse(record.timestamp) : NaN
    return {
      timestamp: Number.isFinite(ts) ? ts : fallbackTimestamp,
      service,
      metric_name: metricName,
      value: numeric,
      unit: typeof record?.unit === 'string' ? record.unit : ''
    }
  }

  const ingestPoints = (points: MetricDataPoint[]) => {
    const cfg = configRef.current
    const filtered = points.filter(p =>
      (cfg.services.length === 0 || cfg.services.includes(p.service)) &&
      (cfg.metrics.length === 0 || cfg.metrics.includes(p.metric_name))
    )
    if (filtered.length === 0) return

    setDataPoints(prev => [...prev, ...filtered].slice(-500))

    // Threshold alerts derive only from data points the server actually sent
    const thresholds = thresholdsRef.current
    const triggered: string[] = []
    filtered.forEach(p => {
      if (p.metric_name === 'latency' && thresholds.latency != null && p.value > thresholds.latency) {
        triggered.push(`High latency detected: ${p.service} - ${p.value}${p.unit || 'ms'}`)
      }
      if (p.metric_name === 'error_rate' && thresholds.error_rate != null && p.value > thresholds.error_rate) {
        triggered.push(`High error rate detected: ${p.service} - ${p.value}${p.unit || '%'}`)
      }
    })
    if (triggered.length > 0) {
      setAlerts(prev => [...prev, ...triggered].slice(-10))
    }
  }

  const handleStreamData = useCallback((data: any) => {
    // Server sends: connected {status: 'streaming_started'},
    // keepalive {status: 'listening'}, error {message},
    // metrics_event {event_type, metrics: [...] | metric_name/value}
    if (data?.status === 'streaming_started') {
      attemptRef.current = 0
      setReconnectAttempt(0)
      setStreamError(null)
      setConnectionState('connected')
      return
    }
    if (data?.status === 'listening') {
      return // keepalive
    }
    if (data?.message && !data?.event_type) {
      setStreamError(`Stream error from ${STREAM_ENDPOINT}: ${data.message}`)
      return
    }
    if (!data?.event_type) return

    const now = Date.now()
    const points: MetricDataPoint[] = []
    if (Array.isArray(data.metrics)) {
      data.metrics.forEach((m: any) => {
        const p = toDataPoint({ timestamp: data.timestamp, service_name: data.service_name, ...m }, now)
        if (p) points.push(p)
      })
    } else {
      const p = toDataPoint(data, now)
      if (p) points.push(p)
    }
    ingestPoints(points)
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (manualStopRef.current) return
    attemptRef.current += 1
    setReconnectAttempt(attemptRef.current)
    const delay = Math.min(1000 * 2 ** (attemptRef.current - 1), MAX_RECONNECT_DELAY_MS)
    reconnectTimerRef.current = setTimeout(() => {
      if (manualStopRef.current) return
      setConnectionState('connecting')
      // eslint-disable-next-line @typescript-eslint/no-use-before-define
      connect()
    }, delay)
  }, [])

  const handleStreamError = useCallback((error: Error) => {
    if (stopStreamRef.current) {
      stopStreamRef.current()
      stopStreamRef.current = null
    }
    if (manualStopRef.current) return
    setConnectionState('disconnected')
    setStreamError(`Connection to ${STREAM_ENDPOINT} lost: ${error?.message || 'network error'}`)
    scheduleReconnect()
  }, [scheduleReconnect])

  const connect = useCallback(async () => {
    try {
      const stop = await apiClient.getStream(STREAM_ENDPOINT, handleStreamData, handleStreamError)
      if (manualStopRef.current) {
        stop()
        return
      }
      stopStreamRef.current = stop
    } catch (error: any) {
      handleStreamError(error instanceof Error ? error : new Error(String(error)))
    }
  }, [handleStreamData, handleStreamError])

  const startStreaming = () => {
    manualStopRef.current = false
    attemptRef.current = 0
    setReconnectAttempt(0)
    setStreamError(null)
    setConnectionState('connecting')
    connect()
  }

  const stopStreaming = () => {
    manualStopRef.current = true
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (stopStreamRef.current) {
      stopStreamRef.current()
      stopStreamRef.current = null
    }
    attemptRef.current = 0
    setReconnectAttempt(0)
    setConnectionState('idle')
  }

  const reconnectNow = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    manualStopRef.current = false
    setStreamError(null)
    setConnectionState('connecting')
    connect()
  }

  const exportData = () => {
    const csv = [
      ['Timestamp', 'Service', 'Metric', 'Value', 'Unit'].join(','),
      ...dataPoints.map(d => [
        new Date(d.timestamp).toISOString(),
        d.service,
        d.metric_name,
        d.value,
        d.unit
      ].join(','))
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `metrics-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const clearAlerts = () => setAlerts([])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      manualStopRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (stopStreamRef.current) {
        stopStreamRef.current()
      }
    }
  }, [])

  const statusLabel =
    connectionState === 'connected' ? 'Streaming' :
    connectionState === 'connecting' ? (reconnectAttempt > 0 ? `Reconnecting (attempt ${reconnectAttempt})` : 'Connecting') :
    connectionState === 'disconnected' ? 'Disconnected' :
    'Stopped'

  const statusColor =
    connectionState === 'connected' ? 'text-emerald-400' :
    connectionState === 'connecting' ? 'text-yellow-400' :
    connectionState === 'disconnected' ? 'text-red-400' :
    'text-slate-400'

  return (
    <DashboardLayout>
      <div className="space-y-4">
        {/* Controls Bar */}
        <div className="flex items-center gap-3">
          {isStreaming || connectionState === 'disconnected' ? (
            <button
              onClick={stopStreaming}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <Pause className="w-4 h-4" />
              Stop Streaming
            </button>
          ) : (
            <button
              onClick={startStreaming}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Streaming
            </button>
          )}

          <button
            onClick={exportData}
            disabled={dataPoints.length === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 ml-auto"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>

        {/* Connection error / disconnected state — no data is ever synthesised */}
        {(connectionState === 'disconnected' || (streamError && connectionState !== 'connected')) && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2">
                <WifiOff className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
                <div>
                  <h3 className="text-sm font-semibold text-red-300">
                    Metrics stream disconnected
                  </h3>
                  <p className="text-xs text-red-200 mt-1">
                    {streamError || `Connection to ${STREAM_ENDPOINT} lost`}
                  </p>
                  {reconnectAttempt > 0 && !manualStopRef.current && (
                    <p className="text-xs text-red-300/70 mt-1">
                      Reconnecting automatically (attempt {reconnectAttempt}, backoff capped at {MAX_RECONNECT_DELAY_MS / 1000}s). No metrics are shown while disconnected.
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={reconnectNow}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-200 rounded-lg text-xs font-medium transition-colors shrink-0"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Reconnect now
              </button>
            </div>
          </div>
        )}

        {/* Configuration */}
        <MetricsConfiguration
          config={config}
          onConfigChange={setConfig}
          alertThresholds={alertThresholds}
          onThresholdsChange={setAlertThresholds}
          disabled={isStreaming}
        />

        {/* Alerts */}
        {alerts.length > 0 && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <h3 className="text-sm font-semibold text-red-300">
                  Threshold Alerts ({alerts.length})
                </h3>
              </div>
              <button
                onClick={clearAlerts}
                className="text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                Clear
              </button>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {alerts.slice().reverse().map((alert, idx) => (
                <div key={idx} className="text-xs text-red-200">
                  • {alert}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Live Charts */}
        <LiveMetricsChart
          dataPoints={dataPoints}
          config={config}
          isStreaming={connectionState === 'connected'}
        />

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl rounded-lg p-4 border border-white/5">
            <div className="text-sm text-slate-400 mb-1">Data Points</div>
            <div className="text-2xl font-bold text-white">{dataPoints.length}</div>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl rounded-lg p-4 border border-white/5">
            <div className="text-sm text-slate-400 mb-1">Stream Endpoint</div>
            <div className="text-sm font-mono text-white mt-2 truncate">{STREAM_ENDPOINT}</div>
          </div>
          <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl rounded-lg p-4 border border-white/5">
            <div className="text-sm text-slate-400 mb-1">Status</div>
            <div className={`text-2xl font-bold ${statusColor}`}>
              {statusLabel}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
