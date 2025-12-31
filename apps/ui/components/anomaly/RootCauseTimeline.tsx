'use client'

interface TimelineEvent {
  time: string
  event: string
  impact_score: number
  source: string
}

interface RootCauseTimelineProps {
  timeline: TimelineEvent[]
  rootCauseType?: string
}

export default function RootCauseTimeline({ timeline, rootCauseType }: RootCauseTimelineProps) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 text-center text-gray-500">
        No timeline data available
      </div>
    )
  }

  const getImpactColor = (score: number) => {
    if (score >= 0.8) return 'bg-red-500'
    if (score >= 0.6) return 'bg-orange-500'
    if (score >= 0.4) return 'bg-yellow-500'
    return 'bg-blue-500'
  }

  const getImpactBorderColor = (score: number) => {
    if (score >= 0.8) return 'border-red-500'
    if (score >= 0.6) return 'border-orange-500'
    if (score >= 0.4) return 'border-yellow-500'
    return 'border-blue-500'
  }

  const getSourceIcon = (source: string) => {
    const lowerSource = source.toLowerCase()
    if (lowerSource.includes('log')) return '📝'
    if (lowerSource.includes('metric')) return '📊'
    if (lowerSource.includes('trace')) return '🔍'
    if (lowerSource.includes('deployment')) return '🚀'
    if (lowerSource.includes('config')) return '⚙️'
    if (lowerSource.includes('alert')) return '🔔'
    return '•'
  }

  const formatTime = (timeStr: string) => {
    try {
      const date = new Date(timeStr)
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    } catch {
      return timeStr
    }
  }

  // Sort timeline chronologically
  const sortedTimeline = [...timeline].sort((a, b) =>
    new Date(a.time).getTime() - new Date(b.time).getTime()
  )

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-200">Root Cause Timeline</h3>
        {rootCauseType && (
          <span className="text-sm bg-purple-500/20 text-purple-400 px-3 py-1 rounded-full border border-purple-500/30">
            {rootCauseType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </span>
        )}
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-6 top-4 bottom-4 w-0.5 bg-gradient-to-b from-gray-600 via-gray-500 to-gray-600" />

        <div className="space-y-6">
          {sortedTimeline.map((event, index) => {
            const isHighImpact = event.impact_score >= 0.7
            const isCriticalEvent = event.impact_score >= 0.8

            return (
              <div key={index} className="relative pl-16">
                {/* Timeline dot */}
                <div className={`absolute left-4 top-2 w-5 h-5 rounded-full border-2 ${getImpactBorderColor(event.impact_score)} ${getImpactColor(event.impact_score)} flex items-center justify-center shadow-lg`}>
                  {isCriticalEvent && (
                    <div className="absolute inset-0 rounded-full animate-ping bg-red-500 opacity-75" />
                  )}
                </div>

                {/* Event card */}
                <div className={`bg-gray-700/50 rounded-lg p-4 border ${
                  isCriticalEvent ? 'border-red-500/50 shadow-lg shadow-red-500/10' :
                  isHighImpact ? 'border-orange-500/50' :
                  'border-gray-600'
                }`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      {/* Event description */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg">{getSourceIcon(event.source)}</span>
                        <p className={`text-sm font-medium ${
                          isCriticalEvent ? 'text-red-300' :
                          isHighImpact ? 'text-orange-300' :
                          'text-gray-200'
                        }`}>
                          {event.event}
                        </p>
                      </div>

                      {/* Source and time */}
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <span className="text-gray-400">Source:</span>
                          <span className="text-gray-300 font-mono">{event.source}</span>
                        </span>
                        <span className="text-gray-600">•</span>
                        <span className="flex items-center gap-1">
                          <span className="text-gray-400">Time:</span>
                          <span className="text-gray-300 font-mono">{formatTime(event.time)}</span>
                        </span>
                      </div>
                    </div>

                    {/* Impact score badge */}
                    <div className="flex flex-col items-end gap-1">
                      <span className={`text-xs font-medium px-2 py-1 rounded ${
                        event.impact_score >= 0.8 ? 'bg-red-500/20 text-red-400' :
                        event.impact_score >= 0.6 ? 'bg-orange-500/20 text-orange-400' :
                        event.impact_score >= 0.4 ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        Impact: {(event.impact_score * 100).toFixed(0)}%
                      </span>

                      {/* Impact indicator */}
                      <div className="w-16 h-1.5 bg-gray-600 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${getImpactColor(event.impact_score)} transition-all duration-500`}
                          style={{ width: `${event.impact_score * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Connection line to next event */}
                {index < sortedTimeline.length - 1 && (
                  <div className="absolute left-6 -bottom-3 w-0.5 h-6 bg-gradient-to-b from-gray-500 to-transparent" />
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Summary */}
      <div className="border-t border-gray-700 pt-4">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-gray-700/30 rounded-lg p-3">
            <p className="text-2xl font-bold text-gray-200">{timeline.length}</p>
            <p className="text-xs text-gray-500 mt-1">Events Detected</p>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-3">
            <p className="text-2xl font-bold text-orange-400">
              {timeline.filter(e => e.impact_score >= 0.7).length}
            </p>
            <p className="text-xs text-gray-500 mt-1">High Impact Events</p>
          </div>
          <div className="bg-gray-700/30 rounded-lg p-3">
            <p className="text-2xl font-bold text-red-400">
              {timeline.filter(e => e.impact_score >= 0.8).length}
            </p>
            <p className="text-xs text-gray-500 mt-1">Critical Events</p>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
        <p className="text-xs text-blue-400">
          This timeline shows events that led to the anomaly, ordered chronologically.
          Higher impact scores indicate events that contributed more significantly to the issue.
        </p>
      </div>
    </div>
  )
}