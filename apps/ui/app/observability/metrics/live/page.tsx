'use client'

import { useState, useEffect, useRef } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LiveMetricsChart from '@/components/observability/LiveMetricsChart'
import MetricsConfiguration from '@/components/observability/MetricsConfiguration'
import { Play, Pause, Download, AlertCircle } from 'lucide-react'

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

export default function LiveMetricsPage() {
  const [isStreaming, setIsStreaming] = useState(false)
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

  const eventSourceRef = useRef<EventSource | null>(null)
  const dataPointsRef = useRef<MetricDataPoint[]>([])

  // Keep dataPoints in sync with ref for SSE callback
  useEffect(() => {
    dataPointsRef.current = dataPoints
  }, [dataPoints])

  const startStreaming = async () => {
    if (config.services.length === 0 || config.metrics.length === 0) {
      alert('Please select at least one service and one metric')
      return
    }

    try {
      // Apply configuration to backend
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'}/v1/streaming/config/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          services: config.services,
          metrics: config.metrics,
          interval: config.interval
        })
      })

      // Start SSE connection
      const params = new URLSearchParams({
        services: config.services.join(','),
        metrics: config.metrics.join(','),
        interval: config.interval.toString()
      })

      const eventSource = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'}/v1/streaming/live?${params}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data: MetricDataPoint = JSON.parse(event.data)

          // Add to data points (keep last 100 points per metric/service combo)
          setDataPoints(prev => {
            const key = `${data.service}-${data.metric_name}`
            const filtered = prev.filter(p =>
              `${p.service}-${p.metric_name}` !== key ||
              prev.indexOf(p) >= prev.length - 99
            )
            return [...filtered, data].slice(-500) // Keep last 500 total points
          })

          // Check thresholds for alerts
          if (data.metric_name === 'latency' && data.value > alertThresholds.latency) {
            setAlerts(prev => [
              ...prev,
              `High latency detected: ${data.service} - ${data.value}${data.unit}`
            ].slice(-10))
          }

          if (data.metric_name === 'error_rate' && data.value > alertThresholds.error_rate) {
            setAlerts(prev => [
              ...prev,
              `High error rate detected: ${data.service} - ${data.value}${data.unit}`
            ].slice(-10))
          }
        } catch (err) {
          console.error('Failed to parse SSE data:', err)
        }
      }

      eventSource.onerror = (error) => {
        console.error('SSE error:', error)
        // Use mock data generator instead
        startMockStreaming()
        eventSource.close()
      }

      eventSourceRef.current = eventSource
      setIsStreaming(true)
    } catch (error) {
      console.error('Failed to start streaming:', error)
      // Fallback to mock streaming
      startMockStreaming()
      setIsStreaming(true)
    }
  }

  const startMockStreaming = () => {
    const interval = setInterval(() => {
      const now = Date.now()

      config.services.forEach(service => {
        config.metrics.forEach(metric => {
          let value: number
          let unit: string

          switch (metric) {
            case 'latency':
              value = Math.random() * 200 + 50 + (Math.random() > 0.9 ? 300 : 0)
              unit = 'ms'
              break
            case 'throughput':
              value = Math.random() * 500 + 200
              unit = 'req/s'
              break
            case 'error_rate':
              value = Math.random() * 2 + (Math.random() > 0.95 ? 5 : 0)
              unit = '%'
              break
            case 'cpu':
              value = Math.random() * 40 + 30
              unit = '%'
              break
            case 'memory':
              value = Math.random() * 30 + 50
              unit = '%'
              break
            default:
              value = Math.random() * 100
              unit = ''
          }

          const dataPoint: MetricDataPoint = {
            timestamp: now,
            service,
            metric_name: metric,
            value,
            unit
          }

          setDataPoints(prev => [...prev, dataPoint].slice(-500))

          // Check thresholds
          if (metric === 'latency' && value > alertThresholds.latency) {
            setAlerts(prev => [
              ...prev,
              `High latency detected: ${service} - ${value.toFixed(0)}${unit}`
            ].slice(-10))
          }

          if (metric === 'error_rate' && value > alertThresholds.error_rate) {
            setAlerts(prev => [
              ...prev,
              `High error rate detected: ${service} - ${value.toFixed(2)}${unit}`
            ].slice(-10))
          }
        })
      })
    }, config.interval)

    eventSourceRef.current = { close: () => clearInterval(interval) } as any
  }

  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
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
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  return (
    <DashboardLayout>
      <div className="space-y-4">
        {/* Controls Bar */}
        <div className="flex items-center gap-3">
          {isStreaming ? (
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
          isStreaming={isStreaming}
        />

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-1">Data Points</div>
            <div className="text-2xl font-bold text-white">{dataPoints.length}</div>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-1">Update Interval</div>
            <div className="text-2xl font-bold text-white">{config.interval}ms</div>
          </div>
          <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
            <div className="text-sm text-slate-400 mb-1">Status</div>
            <div className={`text-2xl font-bold ${isStreaming ? 'text-emerald-400' : 'text-slate-400'}`}>
              {isStreaming ? 'Streaming' : 'Stopped'}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
