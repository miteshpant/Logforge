'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { apiClient } from '@/lib/api'
import {
  Edit,
  RefreshCw,
  Share2,
  MoreVertical,
  Clock,
  ArrowLeft,
  Maximize2,
  Download,
  Settings
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
  Legend,
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
  refresh_interval?: number
}

interface Dashboard {
  id: string
  name: string
  description: string
  widgets: Widget[]
  layout: any
  created_by: string
  created_at: string
  updated_at: string
}

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

// Generate sample data for widgets
const generateWidgetData = (widget: Widget) => {
  const now = Date.now()
  const type = widget.type

  if (type === 'line_chart' || type === 'area_chart') {
    return Array.from({ length: 20 }, (_, i) => ({
      time: new Date(now - (19 - i) * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: Math.random() * 100 + 50,
      value2: Math.random() * 80 + 30
    }))
  }

  if (type === 'bar_chart') {
    return [
      { name: 'api-service', value: Math.random() * 100 + 50 },
      { name: 'web-service', value: Math.random() * 100 + 50 },
      { name: 'db-service', value: Math.random() * 100 + 50 },
      { name: 'cache-service', value: Math.random() * 100 + 50 },
      { name: 'auth-service', value: Math.random() * 100 + 50 }
    ]
  }

  if (type === 'pie_chart') {
    return [
      { name: 'Success', value: 85 + Math.random() * 10 },
      { name: 'Error', value: 5 + Math.random() * 5 },
      { name: 'Timeout', value: 3 + Math.random() * 3 },
      { name: 'Other', value: 2 + Math.random() * 2 }
    ]
  }

  if (type === 'stat') {
    return { value: Math.random() * 500 + 100, change: (Math.random() - 0.5) * 20 }
  }

  if (type === 'gauge') {
    return { value: Math.random() * 100 }
  }

  if (type === 'table') {
    return [
      { endpoint: '/api/users', latency: '45ms', calls: 1234, errors: 12 },
      { endpoint: '/api/orders', latency: '67ms', calls: 892, errors: 8 },
      { endpoint: '/api/products', latency: '32ms', calls: 2341, errors: 5 },
      { endpoint: '/api/auth', latency: '23ms', calls: 4521, errors: 23 },
      { endpoint: '/api/search', latency: '89ms', calls: 567, errors: 2 }
    ]
  }

  return []
}

// Widget Components
function StatWidget({ widget, data }: { widget: Widget; data: any }) {
  const change = data?.change || 0
  const value = data?.value || 0

  return (
    <div className="h-full flex flex-col justify-center">
      <div className="text-3xl font-bold text-white">
        {value.toFixed(0)}
        <span className="text-sm font-normal text-slate-400 ml-1">
          {widget.query_definition.metric === 'latency' ? 'ms' : ''}
          {widget.query_definition.metric === 'throughput' ? '/s' : ''}
          {widget.query_definition.metric === 'error_rate' ? '%' : ''}
        </span>
      </div>
      <div className={`text-sm mt-1 ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
        {change >= 0 ? '↑' : '↓'} {Math.abs(change).toFixed(1)}%
      </div>
    </div>
  )
}

function GaugeWidget({ widget, data }: { widget: Widget; data: any }) {
  const value = data?.value || 0
  const color = value > 80 ? '#ef4444' : value > 60 ? '#f59e0b' : '#10b981'

  return (
    <div className="h-full flex flex-col items-center justify-center">
      <div className="relative w-32 h-16">
        <svg viewBox="0 0 100 50" className="w-full h-full">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="#334155"
            strokeWidth="8"
          />
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeDasharray={`${value * 1.26} 126`}
          />
        </svg>
      </div>
      <div className="text-2xl font-bold text-white mt-2">{value.toFixed(0)}%</div>
    </div>
  )
}

function TableWidget({ widget, data }: { widget: Widget; data: any[] }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            {data[0] && Object.keys(data[0]).map(key => (
              <th key={key} className="text-left py-2 px-2 text-slate-400 font-medium">
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-slate-700/50">
              {Object.values(row).map((val, j) => (
                <td key={j} className="py-2 px-2 text-white">
                  {String(val)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChartWidget({ widget, data }: { widget: Widget; data: any[] }) {
  const type = widget.type

  if (type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
          <YAxis stroke="#64748b" fontSize={10} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          />
          <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="value2" stroke={CHART_COLORS[1]} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'area_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
              <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
          <YAxis stroke="#64748b" fontSize={10} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          />
          <Area type="monotone" dataKey="value" stroke={CHART_COLORS[0]} fill="url(#areaGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'bar_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
          <XAxis type="number" stroke="#64748b" fontSize={10} />
          <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={10} width={80} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          />
          <Bar dataKey="value" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'pie_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={40}
            outerRadius={60}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  return null
}

// Widget Renderer
function WidgetRenderer({ widget }: { widget: Widget }) {
  const [data, setData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Generate sample data
    setData(generateWidgetData(widget))
    setIsLoading(false)

    // Set up refresh interval if configured
    if (widget.refresh_interval) {
      const interval = setInterval(() => {
        setData(generateWidgetData(widget))
      }, widget.refresh_interval * 1000)
      return () => clearInterval(interval)
    }
  }, [widget])

  if (isLoading) {
    return <div className="h-full flex items-center justify-center text-slate-400">Loading...</div>
  }

  switch (widget.type) {
    case 'stat':
      return <StatWidget widget={widget} data={data} />
    case 'gauge':
      return <GaugeWidget widget={widget} data={data} />
    case 'table':
      return <TableWidget widget={widget} data={data || []} />
    default:
      return <ChartWidget widget={widget} data={data || []} />
  }
}

export default function DashboardViewPage() {
  const params = useParams()
  const router = useRouter()
  const { getApiTimeRange } = useTimeRange()
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)

  // Fetch dashboard
  useEffect(() => {
    const fetchDashboard = async () => {
      setIsLoading(true)
      try {
        const response = await apiClient.get(`/v1/dashboards/${params.id}`)
        const data = response.data
        // Ensure widgets is always an array
        setDashboard({
          ...data,
          widgets: data?.widgets || []
        })
      } catch (err) {
        console.error('Failed to fetch dashboard:', err)
        setDashboard(null)
      } finally {
        setIsLoading(false)
      }
    }
    fetchDashboard()
  }, [params.id])

  // Refresh dashboard
  const handleRefresh = async () => {
    setIsRefreshing(true)
    // Trigger re-render of widgets
    setDashboard(prev => prev ? { ...prev } : null)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <RefreshCw className="w-8 h-8 text-slate-400 animate-spin" />
        </div>
      </DashboardLayout>
    )
  }

  if (!dashboard) {
    return (
      <DashboardLayout>
        <div className="text-center py-16">
          <h2 className="text-xl font-semibold text-white">Dashboard not found</h2>
          <button
            onClick={() => router.push('/dashboards')}
            className="mt-4 text-blue-400 hover:text-blue-300"
          >
            Back to dashboards
          </button>
        </div>
      </DashboardLayout>
    )
  }

  // Calculate grid layout
  const getWidgetStyle = (widget: Widget) => {
    const rowHeight = 150 // pixels
    const size = widget.size || { w: 1, h: 1 }
    return {
      gridColumn: `span ${size.w}`,
      gridRow: `span ${size.h}`,
      minHeight: `${size.h * rowHeight}px`
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/dashboards')}
              className="p-2 text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-white">{dashboard.name}</h1>
              <p className="text-sm text-slate-400">{dashboard.description}</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Auto Refresh */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">Auto-refresh</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-slate-700 peer-focus:ring-2 peer-focus:ring-blue-500/50 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-300 after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
              </label>
            </div>

            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3 py-2 border border-white/10 rounded-lg text-slate-300 hover:bg-white/5 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>

            <button
              onClick={() => router.push(`/dashboards/${params.id}/edit`)}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              <Edit className="w-4 h-4" />
              Edit
            </button>
          </div>
        </div>

        {/* Widgets Grid */}
        <div className="grid grid-cols-4 gap-4">
          {(dashboard.widgets || []).map(widget => (
            <div
              key={widget.id}
              style={getWidgetStyle(widget)}
              className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-slate-300">{widget.name || 'Widget'}</h3>
                <button className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors">
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="h-[calc(100%-2rem)]">
                <WidgetRenderer widget={widget} />
              </div>
            </div>
          ))}
        </div>

        {/* Empty state when no widgets */}
        {(dashboard.widgets || []).length === 0 && (
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-12 text-center">
            <p className="text-slate-400 mb-4">This dashboard has no widgets yet.</p>
            <button
              onClick={() => router.push(`/dashboards/${params.id}/edit`)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
            >
              Add Widgets
            </button>
          </div>
        )}

        {/* Footer info */}
        <div className="flex items-center justify-between text-xs text-slate-500 pt-4 border-t border-white/5">
          <div className="flex items-center gap-4">
            <span>Last updated: {dashboard.updated_at ? new Date(dashboard.updated_at).toLocaleString() : 'Unknown'}</span>
            <span>Created by: {dashboard.created_by || 'Unknown'}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3 h-3" />
            <span>{(dashboard.widgets || []).length} widgets</span>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
