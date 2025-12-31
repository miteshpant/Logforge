'use client'

import { useState } from 'react'
import { Search, Filter, X } from 'lucide-react'
import type { TraceSearchFilters } from '@/app/observability/traces/page'

interface TraceSearchProps {
  onSearch: (filters: TraceSearchFilters) => void
  isLoading: boolean
}

export default function TraceSearch({ onSearch, isLoading }: TraceSearchProps) {
  const [service, setService] = useState('')
  const [operation, setOperation] = useState('')
  const [minDuration, setMinDuration] = useState('')
  const [maxDuration, setMaxDuration] = useState('')
  const [status, setStatus] = useState<'ok' | 'error' | 'all'>('all')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSearch = () => {
    const filters: TraceSearchFilters = {
      status
    }

    if (service) filters.service = service
    if (operation) filters.operation = operation
    if (minDuration) filters.min_duration = parseFloat(minDuration) * 1000 // convert ms to microseconds
    if (maxDuration) filters.max_duration = parseFloat(maxDuration) * 1000

    onSearch(filters)
  }

  const handleClear = () => {
    setService('')
    setOperation('')
    setMinDuration('')
    setMaxDuration('')
    setStatus('all')
    onSearch({ status: 'all' })
  }

  const hasActiveFilters = service || operation || minDuration || maxDuration || status !== 'all'

  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700">
      {/* Main Search Bar */}
      <div className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {/* Service Filter */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Service
            </label>
            <input
              type="text"
              value={service}
              onChange={(e) => setService(e.target.value)}
              placeholder="e.g., api-gateway"
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
            />
          </div>

          {/* Operation Filter */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Operation
            </label>
            <input
              type="text"
              value={operation}
              onChange={(e) => setOperation(e.target.value)}
              placeholder="e.g., GET /api/users"
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
            />
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as 'ok' | 'error' | 'all')}
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500 transition-colors text-sm"
            >
              <option value="all">All</option>
              <option value="ok">Success</option>
              <option value="error">Errors</option>
            </select>
          </div>

          {/* Min Duration */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Min Duration (ms)
            </label>
            <input
              type="number"
              value={minDuration}
              onChange={(e) => setMinDuration(e.target.value)}
              placeholder="0"
              min="0"
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
            />
          </div>

          {/* Max Duration */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Max Duration (ms)
            </label>
            <input
              type="number"
              value={maxDuration}
              onChange={(e) => setMaxDuration(e.target.value)}
              placeholder="∞"
              min="0"
              className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 mt-4">
          <button
            onClick={handleSearch}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm"
          >
            <Search className="w-4 h-4" />
            {isLoading ? 'Searching...' : 'Search Traces'}
          </button>

          {hasActiveFilters && (
            <button
              onClick={handleClear}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2 text-sm"
            >
              <X className="w-4 h-4" />
              Clear Filters
            </button>
          )}

          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="ml-auto px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2 text-sm"
          >
            <Filter className="w-4 h-4" />
            {showAdvanced ? 'Hide' : 'Show'} Advanced
          </button>
        </div>
      </div>

      {/* Advanced Filters (collapsible) */}
      {showAdvanced && (
        <div className="p-4 border-t border-slate-700 bg-slate-900/30">
          <h3 className="text-sm font-semibold text-white mb-3">Advanced Filters</h3>
          <div className="text-sm text-slate-400">
            <p>Advanced tag-based filtering coming soon...</p>
            <p className="mt-2 text-xs">
              You'll be able to filter by custom tags like <code className="px-1 py-0.5 bg-slate-800 rounded">http.status_code=500</code> or <code className="px-1 py-0.5 bg-slate-800 rounded">user.id=12345</code>
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
