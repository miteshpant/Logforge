'use client'

import { useState, useEffect } from 'react'

interface LogLevel {
  level: string
  total_logs: number
  affected_services: number
  affected_hosts: number
}

interface LogsOverviewData {
  logs: LogLevel[]
  total_count: number
  execution_time_ms: number
}

interface LogsOverviewWidgetProps {
  data: LogsOverviewData | null
  isLoading: boolean
  timeRange?: string
}

export default function LogsOverviewWidget({ data, isLoading, timeRange }: LogsOverviewWidgetProps) {
  const [isLoaded, setIsLoaded] = useState(false)
  const [hoveredSegment, setHoveredSegment] = useState<number | null>(null)

  useEffect(() => {
    if (!isLoading && data) {
      setTimeout(() => setIsLoaded(true), 100)
    }
  }, [isLoading, data])

  // Calculate totals
  const totalLogs = data?.logs?.reduce((sum, level) => sum + level.total_logs, 0) || 0
  const errorLogs = data?.logs?.find(l => l.level === 'error')?.total_logs || 0
  const warnLogs = data?.logs?.find(l => l.level === 'warn' || l.level === 'warning')?.total_logs || 0
  const infoLogs = data?.logs?.find(l => l.level === 'info')?.total_logs || 0
  const debugLogs = data?.logs?.find(l => l.level === 'debug')?.total_logs || 0

  const errorPercentage = totalLogs > 0 ? (errorLogs / totalLogs) * 100 : 0
  const warnPercentage = totalLogs > 0 ? (warnLogs / totalLogs) * 100 : 0
  const infoPercentage = totalLogs > 0 ? (infoLogs / totalLogs) * 100 : 0
  const debugPercentage = totalLogs > 0 ? (debugLogs / totalLogs) * 100 : 0

  // Get unique services and hosts
  const servicesArray = data?.logs?.map(l => l.affected_services) || []
  const hostsArray = data?.logs?.map(l => l.affected_hosts) || []
  const totalServices = servicesArray.length > 0 ? Math.max(...servicesArray) : 0
  const totalHosts = hostsArray.length > 0 ? Math.max(...hostsArray) : 0

  // Chart segments data
  const chartData = [
    { label: 'Error', value: errorPercentage, color: '#EF4444' },
    { label: 'Warning', value: warnPercentage, color: '#F59E0B' },
    { label: 'Info', value: infoPercentage, color: '#3B82F6' },
    { label: 'Debug', value: debugPercentage, color: '#8B5CF6' },
  ]

  // Donut chart calculations
  const size = 160
  const strokeWidth = 20
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  let cumulativePercent = 0
  const segments = chartData.map((item) => {
    const percent = item.value / 100
    const strokeDasharray = `${circumference * percent} ${circumference * (1 - percent)}`
    const strokeDashoffset = -circumference * cumulativePercent
    cumulativePercent += percent
    return { ...item, strokeDasharray, strokeDashoffset }
  })

  const formatNumber = (num: number) => num >= 1000 ? (num / 1000).toFixed(1) + 'K' : num.toString()

  // Health status
  const isCritical = errorPercentage > 5
  const isWarning = errorPercentage > 1 || warnPercentage > 10

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl">
        <div className="flex items-center justify-center h-40">
          <div className="text-slate-400 text-sm animate-pulse">Loading...</div>
        </div>
      </div>
    )
  }

  return (
    <>
      <style jsx>{`
        @keyframes pulse-glow {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .pulse-dot {
          animation: pulse-glow 2s ease-in-out infinite;
        }
      `}</style>

      <div className="relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 w-full">
        {/* Background glow effects */}
        <div className="absolute top-0 right-0 w-48 h-48 -translate-y-16 translate-x-8 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-40 h-40 translate-y-12 -translate-x-6 bg-purple-500/8 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="relative z-10 flex items-start justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-md shadow-blue-500/30">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 10h16M4 14h10M4 18h6" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">Logs Overview</h2>
              <p className="text-xs text-slate-400 font-medium flex items-center gap-1 mt-0.5">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
                  <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                {timeRange || 'Last 24 hours'}
              </p>
            </div>
          </div>

          {/* Status Badge */}
          {isCritical ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-gradient-to-br from-red-500/15 to-red-500/5 border border-red-500/25">
              <span className="pulse-dot w-1 h-1 rounded-full bg-red-500 shadow-md shadow-red-500/50" />
              <span className="text-[10px] font-bold text-red-500 uppercase tracking-wide">Critical</span>
            </div>
          ) : isWarning ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-gradient-to-br from-orange-500/15 to-orange-500/5 border border-orange-500/25">
              <span className="pulse-dot w-1 h-1 rounded-full bg-orange-500 shadow-md shadow-orange-500/50" />
              <span className="text-[10px] font-bold text-orange-500 uppercase tracking-wide">Warning</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-gradient-to-br from-green-500/15 to-green-500/5 border border-green-500/25">
              <span className="pulse-dot w-1 h-1 rounded-full bg-green-500 shadow-md shadow-green-500/50" />
              <span className="text-[10px] font-bold text-green-500 uppercase tracking-wide">Healthy</span>
            </div>
          )}
        </div>

        {/* Main Content - Chart LEFT, Legend RIGHT */}
        <div className="relative z-10 flex gap-3 items-center">
          {/* Donut Chart - LEFT SIDE */}
          <div className="relative flex-shrink-0">
            <svg width={size} height={size} className="-rotate-90 drop-shadow-lg">
              <circle
                cx={size/2}
                cy={size/2}
                r={radius}
                fill="none"
                stroke="rgba(255,255,255,0.04)"
                strokeWidth={strokeWidth + 2}
              />
              {segments.map((seg, i) => (
                <circle
                  key={seg.label}
                  cx={size/2}
                  cy={size/2}
                  r={radius}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={hoveredSegment === i ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={seg.strokeDasharray}
                  strokeDashoffset={seg.strokeDashoffset}
                  strokeLinecap="round"
                  className="transition-all duration-300 cursor-pointer"
                  style={{
                    opacity: isLoaded ? 1 : 0,
                    filter: hoveredSegment === i ? `drop-shadow(0 0 8px ${seg.color})` : 'none',
                  }}
                  onMouseEnter={() => setHoveredSegment(i)}
                  onMouseLeave={() => setHoveredSegment(null)}
                />
              ))}
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-3xl font-extrabold text-white tracking-tight leading-none">
                  {formatNumber(totalLogs)}
                </div>
                <div className="text-[10px] text-slate-400 font-semibold mt-0.5 uppercase tracking-wider">
                  Total Logs
                </div>
              </div>
            </div>
          </div>

          {/* Legend & Stats - RIGHT SIDE */}
          <div className="flex-1 space-y-2.5">
            {/* Legend - Big Cards */}
            <div className="space-y-1">
              {chartData.map((item, i) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg transition-all duration-200 cursor-pointer"
                  style={{
                    background: hoveredSegment === i
                      ? `linear-gradient(135deg, ${item.color}18 0%, ${item.color}08 100%)`
                      : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${hoveredSegment === i ? `${item.color}35` : 'rgba(255,255,255,0.04)'}`,
                    transform: hoveredSegment === i ? 'translateX(2px)' : 'translateX(0)',
                  }}
                  onMouseEnter={() => setHoveredSegment(i)}
                  onMouseLeave={() => setHoveredSegment(null)}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-sm transition-shadow duration-200"
                      style={{
                        background: item.color,
                        boxShadow: hoveredSegment === i ? `0 0 8px ${item.color}` : 'none',
                      }}
                    />
                    <span
                      className="text-xs font-medium transition-colors duration-200"
                      style={{ color: hoveredSegment === i ? '#F1F5F9' : '#94A3B8' }}
                    >
                      {item.label}
                    </span>
                  </div>
                  <span
                    className="text-base font-bold font-mono transition-colors duration-200 ml-auto"
                    style={{ color: hoveredSegment === i ? item.color : '#E2E8F0' }}
                  >
                    {item.value.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>

            {/* Coverage Stats - Below Legend */}
            <div className="flex gap-2">
              <div className="flex-1 px-2.5 py-2 rounded-lg bg-gradient-to-br from-blue-500/10 to-blue-500/5 border border-blue-500/15 text-center">
                <div className="text-xl font-extrabold text-blue-400 leading-none">{totalServices}</div>
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide mt-1">Services</div>
              </div>
              <div className="flex-1 px-2.5 py-2 rounded-lg bg-gradient-to-br from-purple-500/10 to-purple-500/5 border border-purple-500/15 text-center">
                <div className="text-xl font-extrabold text-purple-400 leading-none">{totalHosts}</div>
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide mt-1">Hosts</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/3">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" className="text-slate-400">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
              <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <span className="text-[10px] text-slate-400 font-mono font-medium">
              {new Date().toISOString().replace('T', ' • ').slice(0, -5)} UTC
            </span>
          </div>
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-green-500/8 border border-green-500/15">
            <span className="pulse-dot w-1 h-1 rounded-full bg-green-500 shadow-sm shadow-green-500/40" />
            <span className="text-[10px] font-semibold text-green-500">Live</span>
          </div>
        </div>
      </div>
    </>
  )
}