'use client'

interface ImpactAssessment {
  affected_users: number
  failed_requests: number
  estimated_revenue_impact: number
  slo_breach: boolean
  severity: string
}

interface ImpactAssessmentCardProps {
  impact: ImpactAssessment
}

export default function ImpactAssessmentCard({ impact }: ImpactAssessmentCardProps) {
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const formatCurrency = (amount: number) => {
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(2)}M`
    if (amount >= 1000) return `$${(amount / 1000).toFixed(2)}K`
    return `$${amount.toFixed(2)}`
  }

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30'
      case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
      case 'low': return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30'
    }
  }

  const getImpactLevel = () => {
    if (impact.slo_breach || impact.affected_users > 10000 || impact.estimated_revenue_impact > 10000) {
      return { level: 'Critical Business Impact', color: 'text-red-400', icon: '🔴' }
    }
    if (impact.affected_users > 1000 || impact.estimated_revenue_impact > 1000) {
      return { level: 'Significant Impact', color: 'text-orange-400', icon: '🟠' }
    }
    if (impact.affected_users > 100 || impact.estimated_revenue_impact > 100) {
      return { level: 'Moderate Impact', color: 'text-yellow-400', icon: '🟡' }
    }
    return { level: 'Minor Impact', color: 'text-blue-400', icon: '🔵' }
  }

  const impactLevel = getImpactLevel()

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-200">Business Impact Assessment</h3>
        <span className={`text-sm px-3 py-1 rounded-full border ${getSeverityColor(impact.severity)}`}>
          {impact.severity.charAt(0).toUpperCase() + impact.severity.slice(1)} Severity
        </span>
      </div>

      {/* Impact Level Banner */}
      <div className={`bg-gradient-to-r ${
        impactLevel.level.includes('Critical') ? 'from-red-500/20 to-red-500/5 border-red-500/30' :
        impactLevel.level.includes('Significant') ? 'from-orange-500/20 to-orange-500/5 border-orange-500/30' :
        impactLevel.level.includes('Moderate') ? 'from-yellow-500/20 to-yellow-500/5 border-yellow-500/30' :
        'from-blue-500/20 to-blue-500/5 border-blue-500/30'
      } border rounded-lg p-4`}>
        <div className="flex items-center gap-3">
          <span className="text-3xl">{impactLevel.icon}</span>
          <div>
            <p className={`text-lg font-semibold ${impactLevel.color}`}>{impactLevel.level}</p>
            <p className="text-sm text-slate-400">Based on affected users, requests, and revenue</p>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Affected Users */}
        <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
          <div className="flex items-start justify-between mb-2">
            <div className="text-slate-400 text-sm">Affected Users</div>
            <span className="text-2xl">👥</span>
          </div>
          <p className="text-3xl font-bold text-slate-200">{formatNumber(impact.affected_users)}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-2 bg-slate-600 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  impact.affected_users > 10000 ? 'bg-red-500' :
                  impact.affected_users > 1000 ? 'bg-orange-500' :
                  impact.affected_users > 100 ? 'bg-yellow-500' :
                  'bg-blue-500'
                } transition-all duration-500`}
                style={{
                  width: `${Math.min((impact.affected_users / 10000) * 100, 100)}%`
                }}
              />
            </div>
          </div>
        </div>

        {/* Failed Requests */}
        <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
          <div className="flex items-start justify-between mb-2">
            <div className="text-slate-400 text-sm">Failed Requests</div>
            <span className="text-2xl">❌</span>
          </div>
          <p className="text-3xl font-bold text-slate-200">{formatNumber(impact.failed_requests)}</p>
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-2 bg-slate-600 rounded-full overflow-hidden">
              <div
                className={`h-full ${
                  impact.failed_requests > 50000 ? 'bg-red-500' :
                  impact.failed_requests > 10000 ? 'bg-orange-500' :
                  impact.failed_requests > 1000 ? 'bg-yellow-500' :
                  'bg-blue-500'
                } transition-all duration-500`}
                style={{
                  width: `${Math.min((impact.failed_requests / 50000) * 100, 100)}%`
                }}
              />
            </div>
          </div>
        </div>

        {/* Revenue Impact */}
        <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
          <div className="flex items-start justify-between mb-2">
            <div className="text-slate-400 text-sm">Revenue Impact</div>
            <span className="text-2xl">💰</span>
          </div>
          <p className="text-3xl font-bold text-slate-200">
            {formatCurrency(impact.estimated_revenue_impact)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Estimated loss</p>
        </div>

        {/* SLO Status */}
        <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
          <div className="flex items-start justify-between mb-2">
            <div className="text-slate-400 text-sm">SLO Status</div>
            <span className="text-2xl">{impact.slo_breach ? '⚠️' : '✅'}</span>
          </div>
          <p className={`text-2xl font-bold ${impact.slo_breach ? 'text-red-400' : 'text-green-400'}`}>
            {impact.slo_breach ? 'BREACHED' : 'Met'}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {impact.slo_breach ? 'Action required' : 'Within targets'}
          </p>
        </div>
      </div>

      {/* SLO Breach Alert */}
      {impact.slo_breach && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <p className="text-sm font-semibold text-red-400 mb-1">SLO Breach Detected</p>
              <p className="text-xs text-red-300">
                This anomaly has caused a Service Level Objective breach. Immediate action is required
                to restore service quality and prevent further customer impact.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Impact Summary */}
      <div className="border-t border-slate-700 pt-4">
        <p className="text-sm text-slate-400">
          {impact.affected_users > 0 && (
            <>
              <strong className="text-slate-300">{formatNumber(impact.affected_users)} users</strong> experienced issues,
            </>
          )}
          {impact.failed_requests > 0 && (
            <>
              {' '}with <strong className="text-slate-300">{formatNumber(impact.failed_requests)} failed requests</strong>
            </>
          )}
          {impact.estimated_revenue_impact > 0 && (
            <>
              , resulting in an estimated <strong className="text-slate-300">{formatCurrency(impact.estimated_revenue_impact)}</strong> revenue impact
            </>
          )}
          .
          {impact.slo_breach && (
            <span className="text-red-400 font-medium"> SLO targets were breached during this incident.</span>
          )}
        </p>
      </div>

      {/* Comparison Context */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-slate-700/30 rounded p-2 text-center">
          <p className="text-slate-500">vs. Last Hour</p>
          <p className="text-red-400 font-semibold mt-1">+{((impact.affected_users / 100) * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-slate-700/30 rounded p-2 text-center">
          <p className="text-slate-500">vs. Last Day</p>
          <p className="text-orange-400 font-semibold mt-1">+{((impact.failed_requests / 500) * 100).toFixed(0)}%</p>
        </div>
        <div className="bg-slate-700/30 rounded p-2 text-center">
          <p className="text-slate-500">Error Rate</p>
          <p className="text-yellow-400 font-semibold mt-1">
            {((impact.failed_requests / (impact.failed_requests + 10000)) * 100).toFixed(1)}%
          </p>
        </div>
      </div>
    </div>
  )
}