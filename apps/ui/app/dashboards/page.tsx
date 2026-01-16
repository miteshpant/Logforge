'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Plus,
  LayoutDashboard,
  Search,
  MoreVertical,
  Edit,
  Trash2,
  Share2,
  Copy,
  Star,
  StarOff,
  Clock,
  Globe,
  Lock,
  ChevronRight,
  FolderOpen,
  Sparkles,
  RefreshCw
} from 'lucide-react'

interface Dashboard {
  id: string
  name: string
  description: string
  widgets: any[]
  created_by: string
  created_at: string
  updated_at: string
  is_public: boolean
  is_favorite?: boolean
  tags: string[]
  thumbnail?: string
}

interface DashboardTemplate {
  id: string
  name: string
  description: string
  category: string
  widgets: any[]
  preview_image?: string
}

const DASHBOARD_TEMPLATES: DashboardTemplate[] = [
  {
    id: 'template-apm',
    name: 'APM Overview',
    description: 'Application performance monitoring with latency, throughput, and error metrics',
    category: 'observability',
    widgets: [
      { type: 'stat', metric: 'latency_p95', title: 'P95 Latency' },
      { type: 'stat', metric: 'throughput', title: 'Throughput' },
      { type: 'stat', metric: 'error_rate', title: 'Error Rate' },
      { type: 'line_chart', metrics: ['latency'], title: 'Latency Trend' },
      { type: 'bar_chart', metric: 'throughput', group_by: 'service', title: 'Throughput by Service' }
    ]
  },
  {
    id: 'template-infrastructure',
    name: 'Infrastructure Health',
    description: 'CPU, memory, disk, and network utilization across your infrastructure',
    category: 'infrastructure',
    widgets: [
      { type: 'gauge', metric: 'cpu_usage', title: 'CPU Usage' },
      { type: 'gauge', metric: 'memory_usage', title: 'Memory Usage' },
      { type: 'line_chart', metrics: ['cpu_usage', 'memory_usage'], title: 'Resource Trend' },
      { type: 'table', query: 'top_hosts', title: 'Top Hosts by CPU' }
    ]
  },
  {
    id: 'template-errors',
    name: 'Error Analysis',
    description: 'Track and analyze errors across services and endpoints',
    category: 'observability',
    widgets: [
      { type: 'stat', metric: 'total_errors', title: 'Total Errors' },
      { type: 'line_chart', metric: 'error_rate', title: 'Error Rate Timeline' },
      { type: 'pie_chart', metric: 'errors_by_type', title: 'Errors by Type' },
      { type: 'table', query: 'top_errors', title: 'Top Error Messages' }
    ]
  },
  {
    id: 'template-logs',
    name: 'Log Analytics',
    description: 'Log volume, patterns, and anomalies visualization',
    category: 'logs',
    widgets: [
      { type: 'stat', metric: 'log_volume', title: 'Log Volume' },
      { type: 'bar_chart', metric: 'logs_by_level', title: 'Logs by Level' },
      { type: 'line_chart', metric: 'log_rate', title: 'Log Rate' },
      { type: 'table', query: 'recent_errors', title: 'Recent Errors' }
    ]
  },
  {
    id: 'template-security',
    name: 'Security Overview',
    description: 'Security events, alerts, and threat indicators',
    category: 'security',
    widgets: [
      { type: 'stat', metric: 'security_events', title: 'Security Events' },
      { type: 'stat', metric: 'critical_alerts', title: 'Critical Alerts' },
      { type: 'line_chart', metric: 'events_timeline', title: 'Events Timeline' },
      { type: 'table', query: 'top_threats', title: 'Top Threats' }
    ]
  }
]

export default function DashboardsPage() {
  const router = useRouter()
  const [dashboards, setDashboards] = useState<Dashboard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<'all' | 'my' | 'shared' | 'public'>('all')
  const [showTemplates, setShowTemplates] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showMenuFor, setShowMenuFor] = useState<string | null>(null)

  // Fetch dashboards
  useEffect(() => {
    const fetchDashboards = async () => {
      setIsLoading(true)
      try {
        const response = await apiClient.get('/v1/dashboards')
        const data = response.data?.dashboards || response.data || []
        setDashboards(Array.isArray(data) ? data : [])
      } catch (err) {
        console.error('Failed to fetch dashboards:', err)
        setDashboards([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchDashboards()
  }, [])

  // Filter dashboards
  const filteredDashboards = dashboards.filter(dashboard => {
    const matchesSearch = dashboard.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      dashboard.description?.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesFilter = filterType === 'all' ||
      (filterType === 'public' && dashboard.is_public) ||
      (filterType === 'my' && dashboard.created_by === 'admin')

    return matchesSearch && matchesFilter
  })

  // Create new dashboard
  const createDashboard = async (name: string, description: string, template?: DashboardTemplate) => {
    try {
      const response = await apiClient.post('/v1/dashboards', {
        name,
        description,
        widgets: template?.widgets || [],
        tags: template ? [template.category] : [],
        is_public: false
      })

      const newDashboard = response.data
      router.push(`/dashboards/${newDashboard.id}/edit`)
    } catch (err) {
      console.error('Failed to create dashboard:', err)
    }
  }

  // Delete dashboard
  const deleteDashboard = async (id: string) => {
    if (!confirm('Are you sure you want to delete this dashboard?')) return

    try {
      await apiClient.delete(`/v1/dashboards/${id}`)
      setDashboards(prev => prev.filter(d => d.id !== id))
    } catch (err) {
      console.error('Failed to delete dashboard:', err)
    }
    setShowMenuFor(null)
  }

  // Duplicate dashboard
  const duplicateDashboard = async (dashboard: Dashboard) => {
    try {
      const response = await apiClient.post('/v1/dashboards', {
        name: `${dashboard.name} (Copy)`,
        description: dashboard.description,
        widgets: dashboard.widgets,
        tags: dashboard.tags,
        is_public: false
      })

      setDashboards(prev => [...prev, response.data])
    } catch (err) {
      console.error('Failed to duplicate dashboard:', err)
    }
    setShowMenuFor(null)
  }

  // Toggle favorite
  const toggleFavorite = (id: string) => {
    setDashboards(prev => prev.map(d =>
      d.id === id ? { ...d, is_favorite: !d.is_favorite } : d
    ))
  }

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search dashboards..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 w-64 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />
              </div>

              {/* Filter */}
              <div className="flex items-center gap-1 bg-slate-700/50 border border-white/10 rounded-lg p-1">
                {(['all', 'my', 'shared', 'public'] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => setFilterType(type)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      filterType === type
                        ? 'bg-blue-500/20 text-blue-400'
                        : 'text-slate-400 hover:bg-slate-600/50'
                    }`}
                  >
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 border border-purple-500/30 rounded-lg text-purple-400 hover:bg-purple-500/30 transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                Templates
              </button>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 border border-blue-500/30 rounded-lg text-blue-400 hover:bg-blue-500/30 font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                New Dashboard
              </button>
            </div>
          </div>
        </div>

        {/* Templates Panel */}
        {showTemplates && (
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-purple-900/30 to-slate-900/95 backdrop-blur-xl shadow-xl border border-purple-500/20 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">Dashboard Templates</h3>
                <p className="text-sm text-slate-400">Start with a pre-built template</p>
              </div>
              <button
                onClick={() => setShowTemplates(false)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ×
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
              {DASHBOARD_TEMPLATES.map(template => (
                <button
                  key={template.id}
                  onClick={() => createDashboard(template.name, template.description, template)}
                  className="text-left p-4 bg-slate-800/50 rounded-xl border border-white/5 hover:border-purple-500/30 hover:bg-slate-700/50 transition-all group"
                >
                  <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center mb-3 group-hover:bg-purple-500/30 transition-colors">
                    <LayoutDashboard className="w-5 h-5 text-purple-400" />
                  </div>
                  <h4 className="font-medium text-white mb-1">{template.name}</h4>
                  <p className="text-xs text-slate-400 line-clamp-2">{template.description}</p>
                  <div className="mt-2 text-xs text-purple-400 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    Use template <ChevronRight className="w-3 h-3" />
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Dashboards Grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="relative overflow-hidden rounded-xl p-6 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5">
                <div className="animate-pulse">
                  <div className="h-32 bg-slate-700 rounded-lg mb-4" />
                  <div className="h-4 bg-slate-700 rounded w-3/4 mb-2" />
                  <div className="h-3 bg-slate-700 rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredDashboards.length === 0 ? (
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 py-16">
            <div className="text-center">
              <FolderOpen className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-white mb-2">No dashboards found</h3>
              <p className="text-slate-400 mb-6">
                {searchQuery ? 'Try a different search term' : 'Create your first dashboard to get started'}
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg font-medium hover:bg-blue-500/30 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Create Dashboard
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredDashboards.map(dashboard => (
              <div
                key={dashboard.id}
                className="relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 hover:border-blue-500/30 transition-all group cursor-pointer"
                onClick={() => router.push(`/dashboards/${dashboard.id}`)}
              >
                {/* Thumbnail */}
                <div className="h-36 bg-gradient-to-br from-slate-700/50 to-slate-800/50 p-4 relative overflow-hidden">
                  {/* Mini widget preview */}
                  <div className="grid grid-cols-3 gap-2 h-full opacity-50">
                    {(dashboard.widgets || []).slice(0, 6).map((_, i) => (
                      <div
                        key={i}
                        className="bg-slate-600/50 rounded"
                      />
                    ))}
                  </div>
                  {/* Hover overlay */}
                  <div className="absolute inset-0 bg-blue-600/90 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="text-white font-medium flex items-center gap-2">
                      Open Dashboard <ChevronRight className="w-4 h-4" />
                    </span>
                  </div>
                </div>

                {/* Content */}
                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-white truncate">
                          {dashboard.name}
                        </h3>
                        {dashboard.is_public ? (
                          <Globe className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                        ) : (
                          <Lock className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-sm text-slate-400 truncate mt-0.5">
                        {dashboard.description || 'No description'}
                      </p>
                    </div>

                    {/* Actions Menu */}
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setShowMenuFor(showMenuFor === dashboard.id ? null : dashboard.id)
                        }}
                        className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>

                      {showMenuFor === dashboard.id && (
                        <div className="absolute right-0 top-8 w-48 bg-slate-800 rounded-lg shadow-lg border border-white/10 py-1 z-10">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/dashboards/${dashboard.id}/edit`)
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700"
                          >
                            <Edit className="w-4 h-4" />
                            Edit
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              duplicateDashboard(dashboard)
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700"
                          >
                            <Copy className="w-4 h-4" />
                            Duplicate
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700"
                          >
                            <Share2 className="w-4 h-4" />
                            Share
                          </button>
                          <hr className="my-1 border-slate-700" />
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              deleteDashboard(dashboard.id)
                            }}
                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Meta info */}
                  <div className="flex items-center justify-between text-xs text-slate-500 mt-3 pt-3 border-t border-white/5">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <LayoutDashboard className="w-3 h-3" />
                        {(dashboard.widgets || []).length} widgets
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(dashboard.updated_at)}
                      </span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleFavorite(dashboard.id)
                      }}
                      className={`p-1 rounded transition-colors ${
                        dashboard.is_favorite
                          ? 'text-yellow-500 hover:text-yellow-400'
                          : 'text-slate-500 hover:text-slate-400'
                      }`}
                    >
                      {dashboard.is_favorite ? (
                        <Star className="w-4 h-4 fill-current" />
                      ) : (
                        <StarOff className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 w-full max-w-md mx-4 border border-white/10 shadow-2xl">
              <h2 className="text-xl font-semibold text-white mb-4">Create New Dashboard</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  const formData = new FormData(e.currentTarget)
                  createDashboard(
                    formData.get('name') as string,
                    formData.get('description') as string
                  )
                  setShowCreateModal(false)
                }}
              >
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Dashboard Name
                    </label>
                    <input
                      type="text"
                      name="name"
                      required
                      placeholder="My Dashboard"
                      className="w-full px-4 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Description
                    </label>
                    <textarea
                      name="description"
                      rows={3}
                      placeholder="What does this dashboard track?"
                      className="w-full px-4 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg font-medium hover:bg-blue-500/30 transition-colors"
                  >
                    Create
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
