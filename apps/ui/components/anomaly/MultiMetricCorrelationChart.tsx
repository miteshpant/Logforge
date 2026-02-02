'use client'

interface AffectedMetric {
  metric: string
  baseline: number
  current: number
  deviation: number
  contribution_score: number
}

interface MultiMetricCorrelationChartProps {
  metrics: AffectedMetric[]
  correlationScore?: number
}

export default function MultiMetricCorrelationChart({
  metrics,
  correlationScore
}: MultiMetricCorrelationChartProps) {
  if (!metrics || metrics.length === 0) {
    return (
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 text-center text-slate-500">
        No metric correlation data available
      </div>
    )
  }

  const getDeviationColor = (deviation: number) => {
    const absDeviation = Math.abs(deviation)
    if (absDeviation >= 50) return 'bg-red-500'
    if (absDeviation >= 30) return 'bg-orange-500'
    if (absDeviation >= 15) return 'bg-yellow-500'
    return 'bg-blue-500'
  }

  const getContributionWidth = (score: number) => {
    return `${Math.min(score * 100, 100)}%`
  }

  const formatMetricName = (metric: string) => {
    return metric
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase())
  }

  const formatValue = (value: number, metric: string) => {
    if (metric.includes('rate') || metric.includes('percent')) {
      return `${value.toFixed(1)}%`
    }
    if (metric.includes('cpu')) {
      return `${value.toFixed(1)}%`
    }
    if (metric.includes('memory')) {
      return `${value.toFixed(0)}MB`
    }
    if (metric.includes('latency') || metric.includes('duration') || metric.includes('time')) {
      return `${value.toFixed(0)}ms`
    }
    return value.toFixed(2)
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-200">Multi-Metric Correlation Analysis</h3>
        {correlationScore !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Correlation Strength:</span>
            <span className={`font-mono text-sm px-2 py-1 rounded ${
              correlationScore >= 0.8 ? 'bg-red-500/20 text-red-400' :
              correlationScore >= 0.6 ? 'bg-orange-500/20 text-orange-400' :
              'bg-yellow-500/20 text-yellow-400'
            }`}>
              {(correlationScore * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="space-y-4">
        {metrics
          .sort((a, b) => b.contribution_score - a.contribution_score) // Sort by contribution
          .map((metric, index) => (
            <div key={index} className="space-y-2">
              {/* Metric Header */}
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-300">
                    {formatMetricName(metric.metric)}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    Math.abs(metric.deviation) >= 50 ? 'bg-red-500/20 text-red-400' :
                    Math.abs(metric.deviation) >= 30 ? 'bg-orange-500/20 text-orange-400' :
                    Math.abs(metric.deviation) >= 15 ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {metric.deviation >= 0 ? '+' : ''}{metric.deviation.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span>Baseline: <strong className="text-slate-300">{formatValue(metric.baseline, metric.metric)}</strong></span>
                  <span>Current: <strong className="text-slate-300">{formatValue(metric.current, metric.metric)}</strong></span>
                </div>
              </div>

              {/* Contribution Bar */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Contribution to anomaly</span>
                  <span className="font-mono">{(metric.contribution_score * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ${getDeviationColor(metric.deviation)}`}
                    style={{ width: getContributionWidth(metric.contribution_score) }}
                  />
                </div>
              </div>

              {/* Deviation Indicator */}
              <div className="relative h-8 bg-slate-700/50 rounded">
                {/* Center line */}
                <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-600" />

                {/* Baseline marker */}
                <div className="absolute left-1/2 top-1/2 -translate-y-1/2 -translate-x-1/2">
                  <div className="w-2 h-2 rounded-full bg-slate-400" />
                </div>

                {/* Current value marker */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 transition-all duration-500"
                  style={{
                    left: `calc(50% + ${Math.min(Math.max(metric.deviation / 2, -50), 50)}%)`
                  }}
                >
                  <div className={`w-3 h-3 rounded-full ${
                    Math.abs(metric.deviation) >= 50 ? 'bg-red-500' :
                    Math.abs(metric.deviation) >= 30 ? 'bg-orange-500' :
                    Math.abs(metric.deviation) >= 15 ? 'bg-yellow-500' :
                    'bg-blue-500'
                  }`} />
                </div>

                {/* Labels */}
                <div className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-slate-500">-100%</div>
                <div className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-500">+100%</div>
              </div>
            </div>
          ))}
      </div>

      {/* Legend */}
      <div className="border-t border-slate-700 pt-4">
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span>Critical (≥50%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-orange-500" />
            <span>High (30-50%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-yellow-500" />
            <span>Medium (15-30%)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-500" />
            <span>Low (&lt;15%)</span>
          </div>
        </div>
      </div>

      {/* Insights */}
      {metrics.length > 1 && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
          <p className="text-sm text-blue-400">
            <strong>{metrics.length} metrics</strong> are showing correlated anomalous behavior.
            The top contributor is <strong>{formatMetricName(metrics[0].metric)}</strong> with
            a {metrics[0].deviation >= 0 ? 'spike' : 'drop'} of <strong>{Math.abs(metrics[0].deviation).toFixed(1)}%</strong>.
          </p>
        </div>
      )}
    </div>
  )
}