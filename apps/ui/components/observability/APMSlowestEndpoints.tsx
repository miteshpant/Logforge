'use client'

import { Clock, AlertCircle } from 'lucide-react'
import type { EndpointPerformance } from '@/app/observability/apm/page'

// Format latency values for display
const formatLatency = (ms: number): string => {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

interface APMSlowestEndpointsProps {
  endpoints: EndpointPerformance[]
  isLoading: boolean
}

export default function APMSlowestEndpoints({ endpoints, isLoading }: APMSlowestEndpointsProps) {
  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Slowest Endpoints</h2>
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="h-16 bg-slate-700/50 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (endpoints.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[400px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No endpoint data available</p>
        </div>
      </div>
    )
  }

  const getLatencyColor = (latency: number) => {
    if (latency > 5000) return 'text-red-400'    // > 5s
    if (latency > 1000) return 'text-orange-400' // > 1s
    if (latency > 200) return 'text-yellow-400'  // > 200ms
    return 'text-emerald-400'
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Slowest Endpoints</h2>
        <p className="text-sm text-slate-400 mt-1">Top 10 endpoints by P99 latency</p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase">Endpoint</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase">Requests</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase">P50</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase">P95</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase">P99</th>
              <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase">Error %</th>
            </tr>
          </thead>
          <tbody>
            {endpoints.slice(0, 10).map((endpoint, idx) => (
              <tr
                key={`${endpoint.service}-${endpoint.endpoint}`}
                className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors"
              >
                {/* Endpoint */}
                <td className="px-6 py-4">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-white">{endpoint.endpoint}</span>
                    <span className="text-xs text-slate-400">{endpoint.service}</span>
                  </div>
                </td>

                {/* Request Count */}
                <td className="px-6 py-4 text-right text-sm text-slate-300">
                  {endpoint.request_count.toLocaleString()}
                </td>

                {/* P50 */}
                <td className={`px-6 py-4 text-right text-sm font-mono ${getLatencyColor(endpoint.p50_latency_ms)}`}>
                  {formatLatency(endpoint.p50_latency_ms)}
                </td>

                {/* P95 */}
                <td className={`px-6 py-4 text-right text-sm font-mono ${getLatencyColor(endpoint.p95_latency_ms)}`}>
                  {formatLatency(endpoint.p95_latency_ms)}
                </td>

                {/* P99 */}
                <td className={`px-6 py-4 text-right text-sm font-mono font-semibold ${getLatencyColor(endpoint.p99_latency_ms)}`}>
                  {formatLatency(endpoint.p99_latency_ms)}
                </td>

                {/* Error Rate */}
                <td className="px-6 py-4 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {endpoint.error_rate > 2 && (
                      <AlertCircle className="w-4 h-4 text-red-400" />
                    )}
                    <span className={`text-sm font-mono ${endpoint.error_rate > 2 ? 'text-red-400' : 'text-slate-300'}`}>
                      {endpoint.error_rate.toFixed(2)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
