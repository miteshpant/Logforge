'use client'

import { useState, useEffect } from 'react'

interface UsageStatsData {
  api_calls: {
    total_this_month: number
  }
  storage: {
    used_gb: number
    limit_gb: number
    usage_percentage: number
  }
  ingestion: {
    used_records: number
    limit_records: number
    usage_percentage: number
  }
  active_users: number
  api_rate: {
    requests_last_hour: number
    requests_per_minute: number
  }
}

interface UsageStatsWidgetsProps {
  data: UsageStatsData | null
  isLoading: boolean
}

export default function UsageStatsWidgets({ data, isLoading }: UsageStatsWidgetsProps) {
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    if (!isLoading && data) {
      setTimeout(() => setIsLoaded(true), 100)
    }
  }, [isLoading, data])

  const formatNumber = (num: number): string => {
    if (num >= 1000000000) return `${(num / 1000000000).toFixed(1)}G`
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const getStorageColor = (percentage: number) => {
    if (percentage < 70) return { text: 'text-green-500', gradient: 'from-green-500 to-green-700', glow: 'bg-green-500/10', border: 'border-green-500/20' }
    if (percentage < 85) return { text: 'text-yellow-500', gradient: 'from-yellow-500 to-yellow-700', glow: 'bg-yellow-500/10', border: 'border-yellow-500/20' }
    return { text: 'text-red-500', gradient: 'from-red-500 to-red-700', glow: 'bg-red-500/10', border: 'border-red-500/20' }
  }

  const getIngestionColor = (percentage: number) => {
    if (percentage < 70) return { text: 'text-blue-500', gradient: 'from-blue-500 to-blue-700', glow: 'bg-blue-500/10', border: 'border-blue-500/20' }
    if (percentage < 85) return { text: 'text-yellow-500', gradient: 'from-yellow-500 to-yellow-700', glow: 'bg-yellow-500/10', border: 'border-yellow-500/20' }
    return { text: 'text-red-500', gradient: 'from-red-500 to-red-700', glow: 'bg-red-500/10', border: 'border-red-500/20' }
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
            <div className="animate-pulse">
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-2"></div>
              <div className="h-8 bg-slate-700 rounded w-3/4"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <div className="text-slate-400 text-sm col-span-full text-center py-4">No usage data available</div>
      </div>
    )
  }

  const apiCalls = data.api_calls?.total_this_month || 0
  const storageUsed = data.storage?.used_gb || 0
  const storageLimit = data.storage?.limit_gb || 0
  const storagePercentage = data.storage?.usage_percentage || 0
  const ingestionUsed = data.ingestion?.used_records || 0
  const ingestionLimit = data.ingestion?.limit_records || 0
  const ingestionPercentage = data.ingestion?.usage_percentage || 0
  const activeUsers = data.active_users || 0
  const apiRate = data.api_rate?.requests_per_minute || 0

  const storageColor = getStorageColor(storagePercentage)
  const ingestionColor = getIngestionColor(ingestionPercentage)

  const widgets = [
    {
      title: 'API Calls',
      value: formatNumber(apiCalls),
      subtitle: 'This Month',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      ),
      gradient: 'from-blue-500 to-blue-700',
      glow: 'bg-blue-500/10',
      textColor: 'text-blue-400'
    },
    {
      title: 'Storage',
      value: `${storageUsed.toFixed(1)}/${storageLimit.toFixed(1)} GB`,
      subtitle: `${storagePercentage.toFixed(0)}% Used`,
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
        </svg>
      ),
      gradient: storageColor.gradient,
      glow: storageColor.glow,
      textColor: storageColor.text
    },
    {
      title: 'Ingestion',
      value: `${formatNumber(ingestionUsed)}/${formatNumber(ingestionLimit)}`,
      subtitle: `${ingestionPercentage.toFixed(0)}% Used`,
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
      ),
      gradient: ingestionColor.gradient,
      glow: ingestionColor.glow,
      textColor: ingestionColor.text
    },
    {
      title: 'Active Users',
      value: activeUsers.toString(),
      subtitle: 'This Month',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>
      ),
      gradient: 'from-purple-500 to-purple-700',
      glow: 'bg-purple-500/10',
      textColor: 'text-purple-400'
    },
    {
      title: 'API Rate',
      value: apiRate.toFixed(1),
      subtitle: 'Req/Min (1h)',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
      ),
      gradient: 'from-cyan-500 to-cyan-700',
      glow: 'bg-cyan-500/10',
      textColor: 'text-cyan-400'
    }
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
      {widgets.map((widget, index) => (
        <div
          key={widget.title}
          className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 transition-all duration-300 hover:border-white/10 hover:shadow-2xl"
          style={{
            opacity: isLoaded ? 1 : 0,
            transform: isLoaded ? 'translateY(0)' : 'translateY(10px)',
            transition: `all 0.3s ease-out ${index * 0.05}s`
          }}
        >
          {/* Background glow */}
          <div className={`absolute top-0 right-0 w-32 h-32 -translate-y-8 translate-x-8 ${widget.glow} rounded-full blur-3xl pointer-events-none`} />

          {/* Icon */}
          <div className={`relative z-10 w-10 h-10 rounded-lg bg-gradient-to-br ${widget.gradient} flex items-center justify-center shadow-md mb-3`}>
            <div className="text-white">
              {widget.icon}
            </div>
          </div>

          {/* Content */}
          <div className="relative z-10">
            <div className={`text-2xl font-extrabold ${widget.textColor} leading-none mb-1`}>
              {widget.value}
            </div>
            <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
              {widget.title}
            </div>
            <div className="text-[10px] text-slate-500 font-medium mt-0.5">
              {widget.subtitle}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}