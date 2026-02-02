'use client'

import { RefreshCw } from 'lucide-react'

interface ServiceOption {
  name: string
  instanceCount: number
}

interface ServiceMapControlsProps {
  filterType: string
  onFilterTypeChange: (type: string) => void
  filterHealth: string
  onFilterHealthChange: (health: string) => void
  filterEnvironment: string
  onFilterEnvironmentChange: (env: string) => void
  autoRefresh: boolean
  onAutoRefreshChange: (enabled: boolean) => void
  refreshInterval: number
  onRefreshIntervalChange: (interval: number) => void
  services?: ServiceOption[]
  selectedService: string
  onSelectedServiceChange: (serviceName: string) => void
  environments?: string[]
  onRefresh?: () => void
  isLoading?: boolean
}

export default function ServiceMapControls({
  filterType,
  onFilterTypeChange,
  filterHealth,
  onFilterHealthChange,
  filterEnvironment,
  onFilterEnvironmentChange,
  autoRefresh,
  onAutoRefreshChange,
  refreshInterval,
  onRefreshIntervalChange,
  services = [],
  selectedService,
  onSelectedServiceChange,
  environments = [],
  onRefresh,
  isLoading = false
}: ServiceMapControlsProps) {
  return (
    <div className="bg-slate-800/80 rounded-lg p-4 border border-white/10 shadow-sm">
      <div className="flex items-end gap-4 flex-wrap">
        {/* Service Selector - Unique service names */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">
            Service
          </label>
          <select
            value={selectedService}
            onChange={(e) => onSelectedServiceChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-700 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          >
            <option value="all">All Services ({services.length})</option>
            {services.map((service) => (
              <option key={service.name} value={service.name}>
                {service.name} {service.instanceCount > 1 ? `(${service.instanceCount})` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Environment Filter */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">
            Environment
          </label>
          <select
            value={filterEnvironment}
            onChange={(e) => onFilterEnvironmentChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-700 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          >
            <option value="all">All Environments</option>
            {environments.map((env) => (
              <option key={env} value={env}>
                {env.charAt(0).toUpperCase() + env.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Type Filter - Match DB enum */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">
            Type
          </label>
          <select
            value={filterType}
            onChange={(e) => onFilterTypeChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-700 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          >
            <option value="all">All Types</option>
            <option value="api">API</option>
            <option value="application">Application</option>
            <option value="database">Database</option>
            <option value="cache">Cache</option>
            <option value="queue">Queue</option>
            <option value="external">External</option>
          </select>
        </div>

        {/* Health Filter - Match DB enum */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">
            Health
          </label>
          <select
            value={filterHealth}
            onChange={(e) => onFilterHealthChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-700 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          >
            <option value="all">All Status</option>
            <option value="healthy">Healthy</option>
            <option value="degraded">Degraded</option>
            <option value="unhealthy">Unhealthy</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {/* Auto Refresh */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">
            Auto Refresh
          </label>
          <div className="flex items-center gap-3">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => onAutoRefreshChange(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-600 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-500 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            {autoRefresh && (
              <select
                value={refreshInterval}
                onChange={(e) => onRefreshIntervalChange(Number(e.target.value))}
                className="px-2 py-1 bg-slate-700 border border-white/10 rounded text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="10000">10s</option>
                <option value="30000">30s</option>
                <option value="60000">1m</option>
                <option value="300000">5m</option>
              </select>
            )}
          </div>
        </div>

        {/* Refresh Button */}
        {onRefresh && (
          <div className="ml-auto">
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
