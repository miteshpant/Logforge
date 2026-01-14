'use client'

import { useMemo } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { ErrorRateMetric } from '@/app/observability/apm/page'

interface APMErrorRatesProps {
  metrics: ErrorRateMetric[]
  isLoading: boolean
}

export default function APMErrorRates({ metrics, isLoading }: APMErrorRatesProps) {
  // Ensure metrics is always an array
  const safeMetrics = Array.isArray(metrics) ? metrics : []

  // Group by service and calculate average error rate
  const serviceErrorRates = useMemo(() => {
    const grouped = new Map<string, { total: number; count: number; max: number }>()

    safeMetrics.forEach(metric => {
      if (!grouped.has(metric.service)) {
        grouped.set(metric.service, { total: 0, count: 0, max: 0 })
      }

      const current = grouped.get(metric.service)!
      current.total += metric.error_rate
      current.count += 1
      current.max = Math.max(current.max, metric.error_rate)
    })

    return Array.from(grouped.entries())
      .map(([service, data]) => ({
        service,
        avgErrorRate: data.total / data.count,
        maxErrorRate: data.max
      }))
      .sort((a, b) => b.avgErrorRate - a.avgErrorRate)
  }, [safeMetrics])

  // Get recent trend (last 6 hours)
  const recentMetrics = useMemo(() => {
    const now = Date.now()
    const sixHoursAgo = now - (6 * 3600000)

    return safeMetrics
      .filter(m => m.timestamp >= sixHoursAgo)
      .sort((a, b) => a.timestamp - b.timestamp)
  }, [safeMetrics])

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Error Rates</h2>
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-12 bg-slate-700/50 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (serviceErrorRates.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[400px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No error data available</p>
        </div>
      </div>
    )
  }

  const getErrorColor = (rate: number) => {
    if (rate > 5) return 'bg-red-500'
    if (rate > 2) return 'bg-yellow-500'
    return 'bg-emerald-500'
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Error Rates by Service</h2>
        <p className="text-sm text-slate-400 mt-1">Average error rate over selected time range</p>
      </div>

      {/* Service Error Rates */}
      <div className="p-6 space-y-4">
        {serviceErrorRates.map(({ service, avgErrorRate, maxErrorRate }) => (
          <div key={service} className="space-y-2">
            {/* Service Name and Rate */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">{service}</span>
                {avgErrorRate > 2 && (
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                )}
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-sm font-mono text-white">
                    {avgErrorRate.toFixed(2)}%
                  </div>
                  <div className="text-xs text-slate-500">
                    peak: {maxErrorRate.toFixed(2)}%
                  </div>
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-slate-700/30 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full ${getErrorColor(avgErrorRate)} transition-all duration-500`}
                style={{ width: `${Math.min(avgErrorRate * 10, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Mini Sparkline Chart (simplified) */}
      <div className="p-6 border-t border-slate-700">
        <h3 className="text-sm font-semibold text-white mb-3">Error Rate Trend (Last 6h)</h3>
        <div className="h-24 flex items-end gap-1">
          {recentMetrics.slice(-24).reduce((acc, metric) => {
            const existing = acc.find(m => Math.floor(metric.timestamp / 900000) === Math.floor(m.timestamp / 900000))
            if (existing) {
              existing.error_rate = Math.max(existing.error_rate, metric.error_rate)
            } else {
              acc.push({ ...metric })
            }
            return acc
          }, [] as ErrorRateMetric[]).map((metric, idx) => {
            const height = Math.min((metric.error_rate / 10) * 100, 100)
            return (
              <div
                key={idx}
                className={`flex-1 rounded-t ${getErrorColor(metric.error_rate)} opacity-80 hover:opacity-100 transition-opacity`}
                style={{ height: `${height}%` }}
                title={`${metric.error_rate.toFixed(2)}% at ${new Date(metric.timestamp).toLocaleTimeString()}`}
              />
            )
          })}
        </div>
        <div className="flex justify-between text-xs text-slate-500 mt-2">
          <span>6h ago</span>
          <span>now</span>
        </div>
      </div>
    </div>
  )
}
