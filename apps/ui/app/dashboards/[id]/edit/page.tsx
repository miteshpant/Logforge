'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Save,
  ArrowLeft,
  Plus,
  Trash2,
  Settings,
  Move,
  GripVertical,
  LineChart as LineChartIcon,
  BarChart3,
  PieChart as PieChartIcon,
  Activity,
  Gauge,
  Table,
  X,
  Check,
  Eye,
  Undo,
  Redo,
  Copy
} from 'lucide-react'

interface Widget {
  id: string
  name: string
  type: 'line_chart' | 'bar_chart' | 'area_chart' | 'pie_chart' | 'stat' | 'gauge' | 'table'
  query_definition: {
    metric?: string
    metrics?: string[]
    aggregation?: string
    group_by?: string
    query?: string
  }
  visualization_config: {
    colors?: string[]
    show_legend?: boolean
  }
  position: { x: number; y: number }
  size: { w: number; h: number }
}

interface Dashboard {
  id: string
  name: string
  description: string
  widgets: Widget[]
}

const WIDGET_TYPES = [
  { type: 'stat', name: 'Stat Card', icon: Activity, description: 'Single metric with trend' },
  { type: 'gauge', name: 'Gauge', icon: Gauge, description: 'Percentage or progress' },
  { type: 'line_chart', name: 'Line Chart', icon: LineChartIcon, description: 'Time series trend' },
  { type: 'area_chart', name: 'Area Chart', icon: Activity, description: 'Filled time series' },
  { type: 'bar_chart', name: 'Bar Chart', icon: BarChart3, description: 'Comparisons' },
  { type: 'pie_chart', name: 'Pie Chart', icon: PieChartIcon, description: 'Distribution' },
  { type: 'table', name: 'Table', icon: Table, description: 'Detailed data' }
]

const METRICS = [
  { value: 'latency', label: 'Latency (ms)' },
  { value: 'throughput', label: 'Throughput (req/s)' },
  { value: 'error_rate', label: 'Error Rate (%)' },
  { value: 'cpu_usage', label: 'CPU Usage (%)' },
  { value: 'memory_usage', label: 'Memory Usage (%)' },
  { value: 'request_count', label: 'Request Count' },
  { value: 'response_time', label: 'Response Time' },
  { value: 'connection_count', label: 'Connections' }
]

const AGGREGATIONS = [
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
  { value: 'sum', label: 'Sum' },
  { value: 'p50', label: 'P50' },
  { value: 'p95', label: 'P95' },
  { value: 'p99', label: 'P99' }
]

// Editor preview: a schematic of what the widget will show. Real values come
// from GET /v1/dashboards/{id}/data and are rendered on the dashboard page
// (the Preview button), so nothing here is invented.
function WidgetPreview({ widget }: { widget: Widget }) {
  const typeInfo = WIDGET_TYPES.find(t => t.type === widget.type)
  const Icon = typeInfo?.icon ?? Activity
  const q = widget.query_definition || {}
  const metric = METRICS.find(m => m.value === q.metric)?.label || q.metric || q.metrics?.join(', ') || q.query
  const aggregation = AGGREGATIONS.find(a => a.value === q.aggregation)?.label

  return (
    <div
      className="h-full flex flex-col items-center justify-center gap-1 text-center rounded border border-dashed border-slate-600/50 px-2"
      data-testid="widget-preview"
    >
      <Icon className="w-6 h-6 text-slate-500" />
      <div className="text-xs font-medium text-slate-300">{typeInfo?.name ?? widget.type}</div>
      <div className="text-[11px] text-slate-500 truncate max-w-full">
        {metric ? `${aggregation ? `${aggregation} of ` : ''}${metric}` : 'No metric selected'}
        {q.group_by ? ` by ${q.group_by}` : ''}
      </div>
    </div>
  )
}

export default function DashboardEditPage() {
  const params = useParams()
  const router = useRouter()
  const isNew = params.id?.toString().startsWith('new-')

  const [dashboard, setDashboard] = useState<Dashboard>({
    id: params.id as string,
    name: 'New Dashboard',
    description: '',
    widgets: []
  })

  const [selectedWidget, setSelectedWidget] = useState<string | null>(null)
  const [showWidgetPalette, setShowWidgetPalette] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [draggedWidget, setDraggedWidget] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Fetch existing dashboard
  useEffect(() => {
    if (!isNew) {
      const fetchDashboard = async () => {
        try {
          const response = await apiClient.get(`/v1/dashboards/${params.id}`)
          // apiClient reports HTTP errors as { success: false }, not by throwing.
          if (!response.success || !response.data) {
            throw new Error(response.error || 'Dashboard not found')
          }
          const data = response.data
          // Ensure widgets is always an array
          setDashboard({
            id: data?.id || params.id as string,
            name: data?.name || 'Dashboard',
            description: data?.description || '',
            widgets: data?.widgets || []
          })
        } catch (err) {
          console.error('Failed to fetch dashboard:', err)
          // Saving the empty default would overwrite the real dashboard, so
          // saving stays disabled until it loads.
          setLoadError('Could not load this dashboard. Saving is disabled so it is not overwritten.')
        }
      }
      fetchDashboard()
    }
  }, [params.id, isNew])

  // Add widget
  const addWidget = (type: string) => {
    const newWidget: Widget = {
      id: `widget-${Date.now()}`,
      name: WIDGET_TYPES.find(w => w.type === type)?.name || 'Widget',
      type: type as Widget['type'],
      query_definition: {
        metric: 'latency',
        aggregation: 'avg'
      },
      visualization_config: {},
      position: { x: 0, y: (dashboard.widgets || []).length },
      size: { w: type === 'stat' || type === 'gauge' ? 1 : 2, h: type === 'stat' || type === 'gauge' ? 1 : 2 }
    }

    setDashboard(prev => ({
      ...prev,
      widgets: [...(prev.widgets || []), newWidget]
    }))
    setSelectedWidget(newWidget.id)
    setShowWidgetPalette(false)
    setHasChanges(true)
  }

  // Update widget
  const updateWidget = (widgetId: string, updates: Partial<Widget>) => {
    setDashboard(prev => ({
      ...prev,
      widgets: prev.widgets.map(w =>
        w.id === widgetId ? { ...w, ...updates } : w
      )
    }))
    setHasChanges(true)
  }

  // Delete widget
  const deleteWidget = (widgetId: string) => {
    setDashboard(prev => ({
      ...prev,
      widgets: prev.widgets.filter(w => w.id !== widgetId)
    }))
    setSelectedWidget(null)
    setHasChanges(true)
  }

  // Duplicate widget
  const duplicateWidget = (widget: Widget) => {
    const newWidget: Widget = {
      ...widget,
      id: `widget-${Date.now()}`,
      name: `${widget.name} (Copy)`,
      position: { ...widget.position, y: widget.position.y + 1 }
    }
    setDashboard(prev => ({
      ...prev,
      widgets: [...(prev.widgets || []), newWidget]
    }))
    setHasChanges(true)
  }

  // Save dashboard
  const saveDashboard = async () => {
    if (loadError) return
    setIsSaving(true)
    setSaveError(null)
    try {
      if (isNew) {
        // post/put reject with ApiError on failure (handled below).
        const response = await apiClient.post('/v1/dashboards', dashboard)
        if (!response.data?.id) {
          throw new Error('Save returned no dashboard id')
        }
        router.push(`/dashboards/${response.data.id}`)
      } else {
        await apiClient.put(`/v1/dashboards/${params.id}`, dashboard)
      }
      setHasChanges(false)
    } catch (err) {
      console.error('Failed to save dashboard:', err)
      // Keep "Unsaved changes" so the user knows nothing was stored.
      setSaveError('Save failed. Your changes are not saved yet; try again.')
    } finally {
      setIsSaving(false)
    }
  }

  // Get selected widget
  const selectedWidgetData = (dashboard.widgets || []).find(w => w.id === selectedWidget)

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-120px)] flex flex-col max-w-7xl mx-auto">
        {/* Header */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 mb-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/dashboards')}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <input
                  type="text"
                  value={dashboard.name}
                  onChange={(e) => {
                    setDashboard(prev => ({ ...prev, name: e.target.value }))
                    setHasChanges(true)
                  }}
                  className="text-xl font-semibold text-white bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 -ml-2"
                />
                <input
                  type="text"
                  value={dashboard.description}
                  onChange={(e) => {
                    setDashboard(prev => ({ ...prev, description: e.target.value }))
                    setHasChanges(true)
                  }}
                  placeholder="Add description..."
                  className="block text-sm text-slate-400 bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 -ml-2 w-64 placeholder-slate-500"
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              {loadError && (
                <span className="text-sm text-red-400" role="alert">{loadError}</span>
              )}
              {saveError && (
                <span className="text-sm text-red-400" role="alert" data-testid="save-error">{saveError}</span>
              )}
              {hasChanges && !loadError && !saveError && (
                <span className="text-sm text-amber-400">Unsaved changes</span>
              )}
              <button
                onClick={() => router.push(`/dashboards/${params.id}`)}
                className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-slate-300 hover:bg-slate-600/50 transition-colors"
              >
                <Eye className="w-4 h-4" />
                Preview
              </button>
              <button
                onClick={saveDashboard}
                disabled={isSaving || !hasChanges || !!loadError}
                className="flex items-center gap-2 px-4 py-2 bg-blue-500/20 border border-blue-500/30 text-blue-400 rounded-lg font-medium hover:bg-blue-500/30 transition-colors disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>

        {/* Main Editor Area */}
        <div className="flex-1 flex gap-4 min-h-0">
          {/* Canvas */}
          <div className="flex-1 relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-xl border border-white/5 p-4 overflow-auto">
            {(dashboard.widgets || []).length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400">
                <BarChart3 className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">No widgets yet</p>
                <p className="text-sm mb-4">Add widgets from the palette to get started</p>
                <button
                  onClick={() => setShowWidgetPalette(true)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Widget
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-4 gap-4 auto-rows-[150px]">
                {(dashboard.widgets || []).map(widget => (
                  <div
                    key={widget.id}
                    onClick={() => setSelectedWidget(widget.id)}
                    className={`bg-slate-800 rounded-xl p-4 cursor-pointer transition-all ${
                      selectedWidget === widget.id
                        ? 'ring-2 ring-blue-500 shadow-lg'
                        : 'hover:ring-1 hover:ring-slate-600'
                    }`}
                    style={{
                      gridColumn: `span ${widget.size?.w || 1}`,
                      gridRow: `span ${widget.size?.h || 1}`
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-300 truncate">
                        {widget.name}
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            duplicateWidget(widget)
                          }}
                          className="p-1 text-slate-500 hover:text-slate-400 rounded"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteWidget(widget.id)
                          }}
                          className="p-1 text-slate-500 hover:text-red-400 rounded"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <div className="h-[calc(100%-2rem)]">
                      <WidgetPreview widget={widget} />
                    </div>
                  </div>
                ))}

                {/* Add Widget Button */}
                <button
                  onClick={() => setShowWidgetPalette(true)}
                  className="bg-slate-700/50 rounded-xl border-2 border-dashed border-slate-600 hover:border-blue-500 hover:bg-slate-700 transition-colors flex items-center justify-center"
                >
                  <div className="text-center text-slate-400">
                    <Plus className="w-8 h-8 mx-auto mb-2" />
                    <span className="text-sm">Add Widget</span>
                  </div>
                </button>
              </div>
            )}
          </div>

          {/* Right Panel - Widget Settings */}
          <div className="w-80 relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 flex flex-col flex-shrink-0">
            {selectedWidgetData ? (
              <>
                {/* Widget Settings Header */}
                <div className="p-4 border-b border-white/5">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-white">Widget Settings</h3>
                    <button
                      onClick={() => setSelectedWidget(null)}
                      className="p-1 text-slate-400 hover:text-white rounded"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Settings Form */}
                <div className="flex-1 overflow-auto p-4 space-y-4">
                  {/* Name */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Name</label>
                    <input
                      type="text"
                      value={selectedWidgetData.name}
                      onChange={(e) => updateWidget(selectedWidget!, { name: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>

                  {/* Type */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Type</label>
                    <select
                      value={selectedWidgetData.type}
                      onChange={(e) => updateWidget(selectedWidget!, { type: e.target.value as Widget['type'] })}
                      className="w-full px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    >
                      {WIDGET_TYPES.map(type => (
                        <option key={type.type} value={type.type}>{type.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Metric */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Metric</label>
                    <select
                      value={selectedWidgetData.query_definition?.metric || ''}
                      onChange={(e) => updateWidget(selectedWidget!, {
                        query_definition: { ...(selectedWidgetData.query_definition || {}), metric: e.target.value }
                      })}
                      className="w-full px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    >
                      {METRICS.map(metric => (
                        <option key={metric.value} value={metric.value}>{metric.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Aggregation */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Aggregation</label>
                    <select
                      value={selectedWidgetData.query_definition?.aggregation || 'avg'}
                      onChange={(e) => updateWidget(selectedWidget!, {
                        query_definition: { ...(selectedWidgetData.query_definition || {}), aggregation: e.target.value }
                      })}
                      className="w-full px-3 py-2 bg-slate-700/50 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    >
                      {AGGREGATIONS.map(agg => (
                        <option key={agg.value} value={agg.value}>{agg.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Size */}
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Size</label>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-slate-400">Width</label>
                        <select
                          value={selectedWidgetData.size?.w || 1}
                          onChange={(e) => updateWidget(selectedWidget!, {
                            size: { ...(selectedWidgetData.size || { w: 1, h: 1 }), w: parseInt(e.target.value) }
                          })}
                          className="w-full px-2 py-1 bg-slate-700/50 border border-white/10 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        >
                          {[1, 2, 3, 4].map(n => (
                            <option key={n} value={n}>{n} col</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-slate-400">Height</label>
                        <select
                          value={selectedWidgetData.size?.h || 1}
                          onChange={(e) => updateWidget(selectedWidget!, {
                            size: { ...(selectedWidgetData.size || { w: 1, h: 1 }), h: parseInt(e.target.value) }
                          })}
                          className="w-full px-2 py-1 bg-slate-700/50 border border-white/10 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        >
                          {[1, 2, 3, 4].map(n => (
                            <option key={n} value={n}>{n} row</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Delete Button */}
                <div className="p-4 border-t border-white/5">
                  <button
                    onClick={() => deleteWidget(selectedWidget!)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Widget
                  </button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-400 p-4">
                <Settings className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm text-center">Select a widget to edit its settings</p>
              </div>
            )}
          </div>
        </div>

        {/* Widget Palette Modal */}
        {showWidgetPalette && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 w-full max-w-2xl mx-4 border border-white/10 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-white">Add Widget</h2>
                <button
                  onClick={() => setShowWidgetPalette(false)}
                  className="p-1 text-slate-400 hover:text-white rounded"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {WIDGET_TYPES.map(widget => {
                  const Icon = widget.icon
                  return (
                    <button
                      key={widget.type}
                      onClick={() => addWidget(widget.type)}
                      className="p-4 bg-slate-800/50 border border-white/5 rounded-xl hover:border-blue-500/30 hover:bg-slate-700/50 transition-colors text-left group"
                    >
                      <div className="w-10 h-10 bg-slate-700/50 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-500/20 transition-colors">
                        <Icon className="w-5 h-5 text-slate-400 group-hover:text-blue-400" />
                      </div>
                      <h3 className="font-medium text-white mb-1">{widget.name}</h3>
                      <p className="text-xs text-slate-400">{widget.description}</p>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
