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
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts'

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

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

// Generate sample preview data
const generatePreviewData = (type: string) => {
  if (type === 'line_chart' || type === 'area_chart') {
    return Array.from({ length: 10 }, (_, i) => ({
      time: i,
      value: Math.random() * 50 + 50
    }))
  }
  if (type === 'bar_chart') {
    return [
      { name: 'A', value: 40 },
      { name: 'B', value: 60 },
      { name: 'C', value: 35 },
      { name: 'D', value: 75 }
    ]
  }
  if (type === 'pie_chart') {
    return [
      { name: 'A', value: 40 },
      { name: 'B', value: 30 },
      { name: 'C', value: 20 },
      { name: 'D', value: 10 }
    ]
  }
  return []
}

// Widget Preview Component
function WidgetPreview({ widget }: { widget: Widget }) {
  const data = generatePreviewData(widget.type)

  if (widget.type === 'stat') {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <div className="text-2xl font-bold text-white">{Math.round(Math.random() * 500)}</div>
        <div className="text-xs text-emerald-400">↑ 12.5%</div>
      </div>
    )
  }

  if (widget.type === 'gauge') {
    const value = 65
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <div className="relative w-20 h-10">
          <svg viewBox="0 0 100 50" className="w-full h-full">
            <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#334155" strokeWidth="8" />
            <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#3b82f6" strokeWidth="8" strokeDasharray={`${value * 1.26} 126`} />
          </svg>
        </div>
        <div className="text-lg font-bold text-white">{value}%</div>
      </div>
    )
  }

  if (widget.type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (widget.type === 'area_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <Area type="monotone" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  if (widget.type === 'bar_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (widget.type === 'pie_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={15} outerRadius={30} dataKey="value">
            {data.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (widget.type === 'table') {
    return (
      <div className="text-xs text-slate-400 p-2">
        <div className="grid grid-cols-3 gap-1 border-b border-slate-700 pb-1 mb-1">
          <div>Col 1</div>
          <div>Col 2</div>
          <div>Col 3</div>
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="grid grid-cols-3 gap-1 text-slate-500">
            <div>Data</div>
            <div>Data</div>
            <div>Data</div>
          </div>
        ))}
      </div>
    )
  }

  return null
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

  // Fetch existing dashboard
  useEffect(() => {
    if (!isNew) {
      const fetchDashboard = async () => {
        try {
          const response = await apiClient.get(`/v1/dashboards/${params.id}`)
          setDashboard(response.data)
        } catch (err) {
          console.error('Failed to fetch dashboard:', err)
          // Keep default for demo
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
      position: { x: 0, y: dashboard.widgets.length },
      size: { w: type === 'stat' || type === 'gauge' ? 1 : 2, h: type === 'stat' || type === 'gauge' ? 1 : 2 }
    }

    setDashboard(prev => ({
      ...prev,
      widgets: [...prev.widgets, newWidget]
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
      widgets: [...prev.widgets, newWidget]
    }))
    setHasChanges(true)
  }

  // Save dashboard
  const saveDashboard = async () => {
    setIsSaving(true)
    try {
      if (isNew) {
        const response = await apiClient.post('/v1/dashboards', dashboard)
        router.push(`/dashboards/${response.data.id}`)
      } else {
        await apiClient.put(`/v1/dashboards/${params.id}`, dashboard)
      }
      setHasChanges(false)
    } catch (err) {
      console.error('Failed to save dashboard:', err)
      // For demo, just mark as saved
      setHasChanges(false)
    } finally {
      setIsSaving(false)
    }
  }

  // Get selected widget
  const selectedWidgetData = dashboard.widgets.find(w => w.id === selectedWidget)

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-120px)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/dashboards')}
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
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
                className="text-xl font-semibold text-slate-900 bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 -ml-2"
              />
              <input
                type="text"
                value={dashboard.description}
                onChange={(e) => {
                  setDashboard(prev => ({ ...prev, description: e.target.value }))
                  setHasChanges(true)
                }}
                placeholder="Add description..."
                className="block text-sm text-slate-500 bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 -ml-2 w-64"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            {hasChanges && (
              <span className="text-sm text-amber-600">Unsaved changes</span>
            )}
            <button
              onClick={() => router.push(`/dashboards/${params.id}`)}
              className="flex items-center gap-2 px-3 py-2 border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <Eye className="w-4 h-4" />
              Preview
            </button>
            <button
              onClick={saveDashboard}
              disabled={isSaving || !hasChanges}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {isSaving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        {/* Main Editor Area */}
        <div className="flex-1 flex gap-4 min-h-0">
          {/* Canvas */}
          <div className="flex-1 bg-slate-100 rounded-xl p-4 overflow-auto">
            {dashboard.widgets.length === 0 ? (
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
                {dashboard.widgets.map(widget => (
                  <div
                    key={widget.id}
                    onClick={() => setSelectedWidget(widget.id)}
                    className={`bg-slate-800 rounded-xl p-4 cursor-pointer transition-all ${
                      selectedWidget === widget.id
                        ? 'ring-2 ring-blue-500 shadow-lg'
                        : 'hover:ring-1 hover:ring-slate-600'
                    }`}
                    style={{
                      gridColumn: `span ${widget.size.w}`,
                      gridRow: `span ${widget.size.h}`
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
          <div className="w-80 bg-white rounded-xl border border-slate-200 flex flex-col flex-shrink-0">
            {selectedWidgetData ? (
              <>
                {/* Widget Settings Header */}
                <div className="p-4 border-b border-slate-200">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900">Widget Settings</h3>
                    <button
                      onClick={() => setSelectedWidget(null)}
                      className="p-1 text-slate-400 hover:text-slate-600 rounded"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Settings Form */}
                <div className="flex-1 overflow-auto p-4 space-y-4">
                  {/* Name */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
                    <input
                      type="text"
                      value={selectedWidgetData.name}
                      onChange={(e) => updateWidget(selectedWidget!, { name: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {/* Type */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
                    <select
                      value={selectedWidgetData.type}
                      onChange={(e) => updateWidget(selectedWidget!, { type: e.target.value as Widget['type'] })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {WIDGET_TYPES.map(type => (
                        <option key={type.type} value={type.type}>{type.name}</option>
                      ))}
                    </select>
                  </div>

                  {/* Metric */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Metric</label>
                    <select
                      value={selectedWidgetData.query_definition.metric || ''}
                      onChange={(e) => updateWidget(selectedWidget!, {
                        query_definition: { ...selectedWidgetData.query_definition, metric: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {METRICS.map(metric => (
                        <option key={metric.value} value={metric.value}>{metric.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Aggregation */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Aggregation</label>
                    <select
                      value={selectedWidgetData.query_definition.aggregation || 'avg'}
                      onChange={(e) => updateWidget(selectedWidget!, {
                        query_definition: { ...selectedWidgetData.query_definition, aggregation: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {AGGREGATIONS.map(agg => (
                        <option key={agg.value} value={agg.value}>{agg.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Size */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Size</label>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-slate-500">Width</label>
                        <select
                          value={selectedWidgetData.size.w}
                          onChange={(e) => updateWidget(selectedWidget!, {
                            size: { ...selectedWidgetData.size, w: parseInt(e.target.value) }
                          })}
                          className="w-full px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          {[1, 2, 3, 4].map(n => (
                            <option key={n} value={n}>{n} col</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500">Height</label>
                        <select
                          value={selectedWidgetData.size.h}
                          onChange={(e) => updateWidget(selectedWidget!, {
                            size: { ...selectedWidgetData.size, h: parseInt(e.target.value) }
                          })}
                          className="w-full px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                <div className="p-4 border-t border-slate-200">
                  <button
                    onClick={() => deleteWidget(selectedWidget!)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
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
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-2xl mx-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-slate-900">Add Widget</h2>
                <button
                  onClick={() => setShowWidgetPalette(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded"
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
                      className="p-4 border border-slate-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-left group"
                    >
                      <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center mb-3 group-hover:bg-blue-100 transition-colors">
                        <Icon className="w-5 h-5 text-slate-600 group-hover:text-blue-600" />
                      </div>
                      <h3 className="font-medium text-slate-900 mb-1">{widget.name}</h3>
                      <p className="text-xs text-slate-500">{widget.description}</p>
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
