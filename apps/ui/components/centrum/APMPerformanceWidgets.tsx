'use client'

import { useState, useEffect } from 'react'

interface APMPerformanceData {
  avg_response_time: {
    value_ms: number
    p95_ms: number
    p99_ms: number
  }
  error_rate: {
    percentage: number
    total_errors: number
    total_requests: number
  }
  throughput: {
    requests_per_second: number
    requests_per_minute: number
    total_requests: number
  }
  slowest_services: Array<{
    service_name: string
    avg_response_time_ms: number
  }>
}

interface APMPerformanceWidgetsProps {
  data: APMPerformanceData | null
  isLoading: boolean
}

export default function APMPerformanceWidgets({ data, isLoading }: APMPerformanceWidgetsProps) {
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    if (!isLoading && data) {
      setTimeout(() => setIsLoaded(true), 100)
    }
  }, [isLoading, data])

  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toFixed(1)
  }

  const formatMs = (ms: number): string => {
    if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
    return `${ms.toFixed(0)}ms`
  }

  const getErrorRateColor = (percentage: number) => {
    if (percentage < 1) return { text: 'text-green-500', gradient: 'from-green-500 to-green-700', glow: 'bg-green-500/10' }
    if (percentage < 5) return { text: 'text-yellow-500', gradient: 'from-yellow-500 to-yellow-700', glow: 'bg-yellow-500/10' }
    return { text: 'text-red-500', gradient: 'from-red-500 to-red-700', glow: 'bg-red-500/10' }
  }

  const getLatencyColor = (ms: number) => {
    if (ms < 100) return { text: 'text-green-500', gradient: 'from-green-500 to-green-700', glow: 'bg-green-500/10' }
    if (ms < 500) return { text: 'text-yellow-500', gradient: 'from-yellow-500 to-yellow-700', glow: 'bg-yellow-500/10' }
    return { text: 'text-red-500', gradient: 'from-red-500 to-red-700', glow: 'bg-red-500/10' }
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-2"></div>
              <div className="h-8 bg-slate-700 rounded w-3/4"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="text-slate-400 text-sm col-span-full text-center py-4">No APM data available</div>
      </div>
    )
  }

  const avgResponseTime = data.avg_response_time?.value_ms || 0
  const p95Latency = data.avg_response_time?.p95_ms || 0
  const errorRate = data.error_rate?.percentage || 0
  const requestsPerSecond = data.throughput?.requests_per_second || 0
  const slowestServices = data.slowest_services || []

  const latencyColor = getLatencyColor(avgResponseTime)
  const errorRateColor = getErrorRateColor(errorRate)

  const widgets = [
    {
      title: 'Avg Response Time',
      value: formatMs(avgResponseTime),
      subtitle: `P95: ${formatMs(p95Latency)}`,
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      ),
      gradient: latencyColor.gradient,
      glow: latencyColor.glow,
      textColor: latencyColor.text
    },
    {
      title: 'Error Rate',
      value: `${errorRate.toFixed(2)}%`,
      subtitle: `${data.error_rate?.total_errors || 0} errors`,
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      ),
      gradient: errorRateColor.gradient,
      glow: errorRateColor.glow,
      textColor: errorRateColor.text
    },
    {
      title: 'Throughput',
      value: `${formatNumber(requestsPerSecond)}/s`,
      subtitle: `${formatNumber(data.throughput?.total_requests || 0)} total`,
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      ),
      gradient: 'from-blue-500 to-blue-700',
      glow: 'bg-blue-500/10',
      textColor: 'text-blue-400'
    },
    {
      title: 'Slowest Service',
      value: slowestServices[0]?.service_name || 'N/A',
      subtitle: slowestServices[0] ? `${formatMs(slowestServices[0].avg_response_time_ms)}` : 'No data',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="9" y1="9" x2="15" y2="15"></line>
          <line x1="15" y1="9" x2="9" y2="15"></line>
        </svg>
      ),
      gradient: 'from-orange-500 to-orange-700',
      glow: 'bg-orange-500/10',
      textColor: 'text-orange-400'
    }
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {widgets.map((widget, index) => (
        <div
          key={widget.title}
          className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 transition-all duration-300 hover:border-white/10 hover:shadow-2xl"
          style={{
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(10px)',
            transition: `all 0.3s ease-out ${index * 0.05}s`
          }}
        >
          {/* Background glow */}
          <div className={`absolute top-0 right-0 w-32 h-32 -translate-y-8 translate-x-8 ${widget.glow} rounded-full blur-3xl pointer-events-none`} />

          {/* Icon */}
          <div className={`relative z-10 w-10 h-10 rounded-lg bg-gradient-to-br ${widget.gradient} flex items-center justify-center shadow-md mb-3`}>
            <div className="text-white">
              {widget.icon}
            </div>
          </div>

          {/* Content */}
          <div className="relative z-10">
            <div className={`text-2xl font-extrabold ${widget.textColor} leading-none mb-1 ${widget.title === 'Slowest Service' ? 'text-base truncate' : ''}`}>
              {widget.value}
            </div>
            <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
              {widget.title}
            </div>
            <div className="text-[10px] text-slate-500 font-medium mt-0.5">
              {widget.subtitle}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}