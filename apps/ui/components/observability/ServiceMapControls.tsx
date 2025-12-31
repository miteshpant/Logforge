'use client'

import { Search } from 'lucide-react'

interface ServiceMapControlsProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  filterType: string
  onFilterTypeChange: (type: string) => void
  filterHealth: string
  onFilterHealthChange: (health: string) => void
  autoRefresh: boolean
  onAutoRefreshChange: (enabled: boolean) => void
  refreshInterval: number
  onRefreshIntervalChange: (interval: number) => void
}

export default function ServiceMapControls({
  searchQuery,
  onSearchChange,
  filterType,
  onFilterTypeChange,
  filterHealth,
  onFilterHealthChange,
  autoRefresh,
  onAutoRefreshChange,
  refreshInterval,
  onRefreshIntervalChange
}: ServiceMapControlsProps) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Search */}
        <div className="lg:col-span-2">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Search Services
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search by service name..."
              className="w-full pl-10 pr-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        {/* Type Filter */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Type
          </label>
          <select
            value={filterType}
            onChange={(e) => onFilterTypeChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="all">All Types</option>
            <option value="service">Services</option>
            <option value="database">Databases</option>
            <option value="cache">Caches</option>
            <option value="external">External APIs</option>
          </select>
        </div>

        {/* Health Filter */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Health Status
          </label>
          <select
            value={filterHealth}
            onChange={(e) => onFilterHealthChange(e.target.value)}
            className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="all">All Status</option>
            <option value="healthy">Healthy</option>
            <option value="degraded">Degraded</option>
            <option value="down">Down</option>
          </select>
        </div>

        {/* Auto Refresh */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
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
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
            {autoRefresh && (
              <select
                value={refreshInterval}
                onChange={(e) => onRefreshIntervalChange(Number(e.target.value))}
                className="px-2 py-1 bg-slate-900/50 border border-slate-600 rounded text-sm text-white focus:outline-none focus:border-blue-500"
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
