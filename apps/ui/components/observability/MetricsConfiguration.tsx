'use client'

import { Settings } from 'lucide-react'
import type { StreamConfig } from '@/app/observability/metrics/live/page'

interface MetricsConfigurationProps {
  config: StreamConfig
  onConfigChange: (config: StreamConfig) => void
  alertThresholds: Record<string, number>
  onThresholdsChange: (thresholds: Record<string, number>) => void
  disabled: boolean
}

const AVAILABLE_SERVICES = [
  'api-gateway',
  'auth-service',
  'user-service',
  'order-service',
  'payment-service'
]

const AVAILABLE_METRICS = [
  { name: 'latency', label: 'Latency (ms)', hasThreshold: true },
  { name: 'throughput', label: 'Throughput (req/s)', hasThreshold: false },
  { name: 'error_rate', label: 'Error Rate (%)', hasThreshold: true },
  { name: 'cpu', label: 'CPU Usage (%)', hasThreshold: true },
  { name: 'memory', label: 'Memory Usage (%)', hasThreshold: true }
]

export default function MetricsConfiguration({
  config,
  onConfigChange,
  alertThresholds,
  onThresholdsChange,
  disabled
}: MetricsConfigurationProps) {
  const toggleService = (service: string) => {
    const services = config.services.includes(service)
      ? config.services.filter(s => s !== service)
      : [...config.services, service]

    onConfigChange({ ...config, services })
  }

  const toggleMetric = (metric: string) => {
    const metrics = config.metrics.includes(metric)
      ? config.metrics.filter(m => m !== metric)
      : [...config.metrics, metric]

    onConfigChange({ ...config, metrics })
  }

  const updateInterval = (interval: number) => {
    onConfigChange({ ...config, interval })
  }

  const updateThreshold = (metric: string, value: number) => {
    onThresholdsChange({ ...alertThresholds, [metric]: value })
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
      <div className="flex items-center gap-2 mb-6">
        <Settings className="w-5 h-5 text-blue-400" />
        <h2 className="text-lg font-semibold text-white">Stream Configuration</h2>
        {disabled && (
          <span className="ml-auto text-xs text-slate-500">
            Stop streaming to modify configuration
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Services Selection */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Select Services</h3>
          <div className="space-y-2">
            {AVAILABLE_SERVICES.map(service => (
              <label
                key={service}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                  config.services.includes(service)
                    ? 'bg-blue-500/10 border-blue-500/50'
                    : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <input
                  type="checkbox"
                  checked={config.services.includes(service)}
                  onChange={() => toggleService(service)}
                  disabled={disabled}
                  className="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-blue-500 focus:ring-2 disabled:cursor-not-allowed"
                />
                <span className="text-sm text-slate-200">{service}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Metrics Selection */}
        <div>
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Select Metrics</h3>
          <div className="space-y-2">
            {AVAILABLE_METRICS.map(({ name, label }) => (
              <label
                key={name}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                  config.metrics.includes(name)
                    ? 'bg-blue-500/10 border-blue-500/50'
                    : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
                } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <input
                  type="checkbox"
                  checked={config.metrics.includes(name)}
                  onChange={() => toggleMetric(name)}
                  disabled={disabled}
                  className="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-blue-500 focus:ring-2 disabled:cursor-not-allowed"
                />
                <span className="text-sm text-slate-200">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Settings */}
        <div className="space-y-4">
          {/* Update Interval */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Update Interval</h3>
            <select
              value={config.interval}
              onChange={(e) => updateInterval(Number(e.target.value))}
              disabled={disabled}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="1000">1 second (real-time)</option>
              <option value="2000">2 seconds</option>
              <option value="5000">5 seconds</option>
              <option value="10000">10 seconds</option>
            </select>
          </div>

          {/* Alert Thresholds */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Alert Thresholds</h3>
            <div className="space-y-3">
              {AVAILABLE_METRICS.filter(m => m.hasThreshold).map(({ name, label }) => (
                <div key={name}>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {label}
                  </label>
                  <input
                    type="number"
                    value={alertThresholds[name] || 0}
                    onChange={(e) => updateThreshold(name, Number(e.target.value))}
                    disabled={disabled}
                    className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    placeholder="Enter threshold"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="mt-6 pt-4 border-t border-slate-700 flex items-center justify-between text-sm">
        <div className="text-slate-400">
          {config.services.length} services • {config.metrics.length} metrics • {config.interval}ms interval
        </div>
        {!disabled && config.services.length === 0 && (
          <div className="text-yellow-400 text-xs">
            ⚠️ Select at least one service to start streaming
          </div>
        )}
      </div>
    </div>
  )
}
