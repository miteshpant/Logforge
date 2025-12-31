'use client'

import { X, Activity, AlertCircle, Clock, TrendingUp, Database, Server, Boxes, Globe } from 'lucide-react'
import type { ServiceNode } from '@/app/observability/service-map/page'

interface ServiceMapDetailsProps {
  node: ServiceNode | null
  onClose: () => void
}

export default function ServiceMapDetails({ node, onClose }: ServiceMapDetailsProps) {
  if (!node) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[600px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>Select a service to view details</p>
        </div>
      </div>
    )
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'service':
        return <Server className="w-5 h-5" />
      case 'database':
        return <Database className="w-5 h-5" />
      case 'cache':
        return <Boxes className="w-5 h-5" />
      case 'external':
        return <Globe className="w-5 h-5" />
      default:
        return <Activity className="w-5 h-5" />
    }
  }

  const getHealthBadge = (health: string) => {
    const styles = {
      healthy: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      degraded: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      down: 'bg-red-500/20 text-red-400 border-red-500/30'
    }

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-medium border ${styles[health as keyof typeof styles] || styles.healthy}`}>
        {health.charAt(0).toUpperCase() + health.slice(1)}
      </span>
    )
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
    return num.toLocaleString()
  }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400">
              {getTypeIcon(node.type)}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">{node.name}</h3>
              <p className="text-sm text-slate-400 capitalize">{node.type}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          {getHealthBadge(node.health)}
        </div>
      </div>

      {/* Metrics */}
      <div className="p-6 space-y-6">
        {/* Request Count */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-slate-300">Request Count</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {formatNumber(node.metrics.request_count)}
          </div>
          <div className="text-xs text-slate-500 mt-1">requests in selected time range</div>
        </div>

        {/* Error Rate */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-medium text-slate-300">Error Rate</span>
          </div>
          <div className={`text-2xl font-bold ${node.metrics.error_rate > 1 ? 'text-red-400' : 'text-emerald-400'}`}>
            {node.metrics.error_rate.toFixed(2)}%
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {node.metrics.error_rate > 5 ? 'High error rate detected' : 'Within normal range'}
          </div>
        </div>

        {/* Average Latency */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-medium text-slate-300">Avg Latency</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {node.metrics.avg_latency_ms}ms
          </div>
          <div className="text-xs text-slate-500 mt-1">average response time</div>
        </div>

        {/* P95 Latency */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-slate-300">P95 Latency</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {node.metrics.p95_latency_ms}ms
          </div>
          <div className="text-xs text-slate-500 mt-1">95th percentile</div>
        </div>

        {/* Metadata (if available) */}
        {node.metadata && Object.keys(node.metadata).length > 0 && (
          <div className="pt-4 border-t border-slate-700">
            <h4 className="text-sm font-medium text-slate-300 mb-3">Metadata</h4>
            <div className="space-y-2">
              {node.metadata.version && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Version:</span>
                  <span className="text-white font-medium">{node.metadata.version}</span>
                </div>
              )}
              {node.metadata.environment && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Environment:</span>
                  <span className="text-white font-medium">{node.metadata.environment}</span>
                </div>
              )}
              {node.metadata.namespace && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Namespace:</span>
                  <span className="text-white font-medium">{node.metadata.namespace}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="pt-4 border-t border-slate-700">
          <button className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors text-sm">
            View Detailed Traces
          </button>
          <button className="w-full mt-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors text-sm">
            View Logs
          </button>
        </div>
      </div>
    </div>
  )
}
