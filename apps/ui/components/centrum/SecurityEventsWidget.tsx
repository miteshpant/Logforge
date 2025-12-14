'use client'

import { useState, useEffect } from 'react'

interface SecurityDashboardData {
  total_events: number
  events_by_severity: {
    critical?: number
    high?: number
    medium?: number
    low?: number
    informational?: number
  }
  events_by_technique?: Record<string, number>
  top_rules?: Array<any>
  recent_events?: Array<any>
  threat_intel_stats?: Record<string, any>
}

interface SecurityEventsWidgetProps {
  data: SecurityDashboardData | null
  isLoading: boolean
  timeRange?: string
}

export default function SecurityEventsWidget({ data, isLoading, timeRange }: SecurityEventsWidgetProps) {
  const [isLoaded, setIsLoaded] = useState(false)
  const [hoveredSegment, setHoveredSegment] = useState<number | null>(null)

  useEffect(() => {
    if (!isLoading && data) {
      setTimeout(() => setIsLoaded(true), 100)
    }
  }, [isLoading, data])

  if (isLoading) {
    return (
      <div className="relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 w-full max-w-[420px]">
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-400 text-sm animate-pulse">Loading security data...</div>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="relative overflow-hidden rounded-2xl p-5 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 w-full max-w-[420px]">
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-400 text-sm">No security data available</div>
        </div>
      </div>
    )
  }

  // Calculate percentages for each severity
  const total = data.total_events || 0
  const criticalCount = data.events_by_severity?.critical || 0
  const highCount = data.events_by_severity?.high || 0
  const mediumCount = data.events_by_severity?.medium || 0
  const lowCount = data.events_by_severity?.low || 0

  const criticalPct = total > 0 ? (criticalCount / total) * 100 : 0
  const highPct = total > 0 ? (highCount / total) * 100 : 0
  const mediumPct = total > 0 ? (mediumCount / total) * 100 : 0
  const lowPct = total > 0 ? (lowCount / total) * 100 : 0

  // Chart segments data
  const chartData = [
    { label: 'Critical', value: criticalPct, count: criticalCount, color: '#EF4444' },  // Red
    { label: 'High', value: highPct, count: highCount, color: '#F59E0B' },              // Orange
    { label: 'Medium', value: mediumPct, count: mediumCount, color: '#FBBF24' },        // Yellow
    { label: 'Low', value: lowPct, count: lowCount, color: '#3B82F6' },                 // Blue
  ]

  // SVG donut chart parameters
  const size = 160
  const strokeWidth = 20
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  // Create segments with cumulative offsets
  let cumulativePercent = 0
  const segments = chartData.map((item) => {
    const percent = item.value / 100
    const strokeDasharray = `${circumference * percent} ${circumference * (1 - percent)}`
    const strokeDashoffset = -circumference * cumulativePercent
    cumulativePercent += percent
    return { ...item, strokeDasharray, strokeDashoffset }
  })

  // Determine overall status badge
  const statusColor = criticalCount > 0 ? 'red' : highCount > 0 ? 'orange' : mediumCount > 0 ? 'yellow' : 'green'
  const statusLabel = criticalCount > 0 ? 'Critical' : highCount > 0 ? 'High' : mediumCount > 0 ? 'Medium' : 'Secure'

  const statusColors = {
    red: {
      bg: 'from-red-500/15 to-red-500/5',
      border: 'border-red-500/25',
      dot: 'bg-red-500 shadow-red-500/50',
      text: 'text-red-500'
    },
    orange: {
      bg: 'from-orange-500/15 to-orange-500/5',
      border: 'border-orange-500/25',
      dot: 'bg-orange-500 shadow-orange-500/50',
      text: 'text-orange-500'
    },
    yellow: {
      bg: 'from-yellow-500/15 to-yellow-500/5',
      border: 'border-yellow-500/25',
      dot: 'bg-yellow-500 shadow-yellow-500/50',
      text: 'text-yellow-500'
    },
    green: {
      bg: 'from-green-500/15 to-green-500/5',
      border: 'border-green-500/25',
      dot: 'bg-green-500 shadow-green-500/50',
      text: 'text-green-500'
    }
  }

  const currentStatus = statusColors[statusColor]

  // Count threat detections and mitigated
  const totalDetections = criticalCount + highCount + mediumCount + lowCount
  const mitigated = 0 // This would come from resolved/acknowledged events

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
        <div className="absolute top-0 right-0 w-48 h-48 -translate-y-16 translate-x-8 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-40 h-40 translate-y-12 -translate-x-6 bg-pink-500/8 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="relative z-10 flex items-start justify-between mb-4">
          {/* Icon & Title */}
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center shadow-md shadow-purple-500/30">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">Security Events</h2>
              <p className="text-xs text-slate-400 font-medium flex items-center gap-1 mt-0.5">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-400">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                {timeRange || 'Last 24 hours'}
              </p>
            </div>
          </div>

          {/* Status Badge */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-gradient-to-br ${currentStatus.bg} border ${currentStatus.border}`}>
            <span className={`pulse-dot w-1 h-1 rounded-full ${currentStatus.dot} shadow-md`} />
            <span className={`text-[10px] font-bold ${currentStatus.text} uppercase tracking-wide`}>{statusLabel}</span>
          </div>
        </div>

        {/* Main Content - Chart + Stats */}
        <div className="relative z-10 flex gap-3 items-center">
          {/* Donut Chart - LEFT SIDE */}
          <div className="relative flex-shrink-0">
            <svg width={size} height={size} className="-rotate-90 drop-shadow-lg">
              {/* Background circle */}
              <circle
                cx={size/2}
                cy={size/2}
                r={radius}
                fill="none"
                stroke="rgba(255,255,255,0.04)"
                strokeWidth={strokeWidth + 2}
              />
              {/* Chart segments with hover effects */}
              {segments.map((seg, i) => (
                seg.count > 0 && (
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
                )
              ))}
            </svg>

            {/* Center text - Total events */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="text-3xl font-extrabold text-white tracking-tight leading-none">
                  {total.toLocaleString()}
                </div>
                <div className="text-[10px] text-slate-400 font-semibold mt-0.5 uppercase tracking-wider">
                  Total Events
                </div>
              </div>
            </div>
          </div>

          {/* Legend & Stats - RIGHT SIDE */}
          <div className="flex-1 space-y-2.5">
            {/* Legend with hover effects - Show all severity levels */}
            <div className="space-y-1">
              {segments.map((item, i) => (
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

            {/* Status Summary - Below Legend */}
            <div className="flex gap-2">
              <div className="flex-1 px-2.5 py-2 rounded-lg bg-gradient-to-br from-purple-500/10 to-purple-500/5 border border-purple-500/15 text-center">
                <div className="text-xl font-extrabold text-purple-400 leading-none">{totalDetections.toLocaleString()}</div>
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide mt-1">Detected</div>
              </div>
              <div className="flex-1 px-2.5 py-2 rounded-lg bg-gradient-to-br from-green-500/10 to-green-500/5 border border-green-500/15 text-center">
                <div className="text-xl font-extrabold text-green-400 leading-none">{mitigated.toLocaleString()}</div>
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide mt-1">Mitigated</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
          {/* Timestamp */}
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/3">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-400">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span className="text-[10px] text-slate-400 font-mono font-medium">
              {new Date().toISOString().replace('T', ' • ').slice(0, -5)} UTC
            </span>
          </div>

          {/* Live indicator */}
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-green-500/8 border border-green-500/15">
            <span className="pulse-dot w-1 h-1 rounded-full bg-green-500 shadow-sm shadow-green-500/40" />
            <span className="text-[10px] font-semibold text-green-500">Live</span>
          </div>
        </div>
      </div>
    </>
  )
}