'use client'

interface ObservabilityStats {
  traces: {
    total_count: number
    error_count: number
  }
  performance: {
    avg_response_time_ms: number
    p95_latency_ms: number
    p99_latency_ms: number
  }
  reliability: {
    error_rate_percent: number
    total_errors: number
    total_success: number
  }
  services: {
    active_count: number
  }
  spans: {
    total_count: number
    spans_per_second: number
  }
}

interface ObservabilityStatsWidgetsProps {
  data: ObservabilityStats | null
  isLoading: boolean
}

export default function ObservabilityStatsWidgets({ data, isLoading }: ObservabilityStatsWidgetsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 animate-pulse">
            <div className="h-16"></div>
          </div>
        ))}
      </div>
    )
  }

  if (!data) {
    return null
  }

  // Format large numbers to K/M/G
  const formatNumber = (num: number): string => {
    if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}G`
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  // Calculate values
  const totalTraces = data.traces?.total_count || 0
  const avgResponseTime = Math.round(data.performance?.avg_response_time_ms || 0)
  const errorRate = data.reliability?.error_rate_percent || 0
  const activeServices = data.services?.active_count || 0
  const p95Latency = Math.round(data.performance?.p95_latency_ms || 0)
  const totalSpans = data.spans?.total_count || 0

  // Determine color for error rate
  const getErrorRateColor = (rate: number) => {
    if (rate < 1) return { text: 'text-green-500', gradient: 'from-green-500 to-green-700', glow: 'bg-green-500/10' }
    if (rate < 5) return { text: 'text-yellow-500', gradient: 'from-yellow-500 to-yellow-700', glow: 'bg-yellow-500/10' }
    return { text: 'text-red-500', gradient: 'from-red-500 to-red-700', glow: 'bg-red-500/10' }
  }

  const errorRateColor = getErrorRateColor(errorRate)

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* Total Traces */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-purple-500/20 transition-all duration-200">
        <div className="absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 bg-purple-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Traces</span>
          </div>
          <div className="text-2xl font-extrabold text-white leading-none">
            {formatNumber(totalTraces)}
          </div>
        </div>
      </div>

      {/* Avg Response Time */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-cyan-500/20 transition-all duration-200">
        <div className="absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Avg Time</span>
          </div>
          <div className="text-2xl font-extrabold text-white leading-none">
            {formatNumber(avgResponseTime)}<span className="text-sm font-medium text-slate-400 ml-1">ms</span>
          </div>
        </div>
      </div>

      {/* Error Rate */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-white/10 transition-all duration-200">
        <div className={`absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 ${errorRateColor.glow} rounded-full blur-2xl pointer-events-none`} />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${errorRateColor.gradient} flex items-center justify-center`}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Error Rate</span>
          </div>
          <div className={`text-2xl font-extrabold ${errorRateColor.text} leading-none`}>
            {errorRate.toFixed(1)}<span className={`text-sm font-medium ${errorRateColor.text} opacity-80 ml-0.5`}>%</span>
          </div>
        </div>
      </div>

      {/* Active Services */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-blue-500/20 transition-all duration-200">
        <div className="absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Services</span>
          </div>
          <div className="text-2xl font-extrabold text-white leading-none">
            {activeServices}
          </div>
        </div>
      </div>

      {/* P95 Latency */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-orange-500/20 transition-all duration-200">
        <div className="absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 bg-orange-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-700 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">P95</span>
          </div>
          <div className="text-2xl font-extrabold text-white leading-none">
            {formatNumber(p95Latency)}<span className="text-sm font-medium text-slate-400 ml-1">ms</span>
          </div>
        </div>
      </div>

      {/* Total Spans */}
      <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 border border-white/5 hover:border-indigo-500/20 transition-all duration-200">
        <div className="absolute top-0 right-0 w-20 h-20 -translate-y-8 translate-x-8 bg-indigo-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white">
                <line x1="8" y1="6" x2="21" y2="6" />
                <line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" />
                <line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
            </div>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Spans</span>
          </div>
          <div className="text-2xl font-extrabold text-white leading-none">
            {formatNumber(totalSpans)}
          </div>
        </div>
      </div>
    </div>
  )
}