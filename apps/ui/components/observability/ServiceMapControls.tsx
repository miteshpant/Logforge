'use client'

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
  environments = []
}: ServiceMapControlsProps) {
  return (
    <div className="bg-white rounded-lg p-4 border border-slate-200 shadow-sm">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Service Selector - Unique service names */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Service
          </label>
          <select
            value={selectedService}
            onChange={(e) => onSelectedServiceChange(e.target.value)}
            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
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
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Environment
          </label>
          <select
            value={filterEnvironment}
            onChange={(e) => onFilterEnvironmentChange(e.target.value)}
            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
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
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Type
          </label>
          <select
            value={filterType}
            onChange={(e) => onFilterTypeChange(e.target.value)}
            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
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
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Health
          </label>
          <select
            value={filterHealth}
            onChange={(e) => onFilterHealthChange(e.target.value)}
            className="w-full px-4 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          >
            <option value="all">All Status</option>
            <option value="healthy">Healthy</option>
            <option value="degraded">Degraded</option>
            <option value="unhealthy">Unhealthy</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {/* Auto Refresh */}
        <div className="col-span-2 md:col-span-1 lg:col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-2">
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
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            {autoRefresh && (
              <select
                value={refreshInterval}
                onChange={(e) => onRefreshIntervalChange(Number(e.target.value))}
                className="px-2 py-1 bg-white border border-slate-300 rounded text-sm text-slate-900 focus:outline-none focus:border-blue-500"
              >
                <option value="10000">10s</option>
                <option value="30000">30s</option>
                <option value="60000">1m</option>
                <option value="300000">5m</option>
              </select>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
