'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useTimeRange } from '@/contexts/TimeRangeContext'
import { apiClient } from '@/lib/api'
import {
  Edit,
  RefreshCw,
  Clock,
  ArrowLeft,
  Maximize2,
  AlertTriangle,
  Inbox
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
  type: 'line_chart' | 'bar_chart' | 'area_chart' | 'pie_chart' | 'stat' | 'gauge' | 'table' | 'metric'
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

// Per-widget entry from GET /v1/dashboards/{id}/data.
// Built-in dashboards return widgets as a dict keyed by widget id; custom
// dashboards return a list of {widget_id, name, type, data, ...}.
interface WidgetDataEntry {
  title?: string
  name?: string
  type?: string
  data?: any
  error?: string
  execution_time_ms?: number
  last_updated?: string
}

type NormalizedWidget =
  | { kind: 'error'; message: string }
  | { kind: 'unsupported'; message: string }
  | { kind: 'empty' }
  | { kind: 'stat'; value: number; formatted?: string; change?: number; label?: string }
  | { kind: 'series'; rows: { label: string; value: number }[] }
  | { kind: 'table'; columns: string[]; rows: any[] }

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

// Extract {label, value} rows from the various chart payload shapes the data
// API returns. Returns [] when the payload contains no plottable data — an
// empty chart is rendered honestly, values are never invented.
const extractSeriesRows = (d: any): { label: string; value: number }[] => {
  if (!d || typeof d !== 'object') return []

  if (Array.isArray(d.series) && d.series.length > 0) {
    const first = d.series[0]

    // Engine pie shape: series = [{label, value}, ...]
    if (first && typeof first === 'object' && 'value' in first && !('data' in first)) {
      return d.series
        .filter((s: any) => typeof s.value === 'number')
        .map((s: any) => ({ label: String(s.label ?? s.name ?? ''), value: s.value }))
    }

    if (first && Array.isArray(first.data)) {
      // Engine time-series shape: series = [{name, data: [{x, y}]}]
      if (first.data.length > 0 && typeof first.data[0] === 'object' && first.data[0] !== null && 'y' in first.data[0]) {
        return first.data
          .filter((p: any) => typeof p.y === 'number')
          .map((p: any) => ({ label: String(p.x ?? ''), value: p.y }))
      }
      // DAO shape: series = [{name, data: [numbers]}], labels = [...]
      if (first.data.length > 0 && typeof first.data[0] === 'number') {
        const labels: any[] = Array.isArray(d.labels) ? d.labels : (Array.isArray(d.categories) ? d.categories : [])
        return first.data.map((v: number, i: number) => ({
          label: String(labels[i] ?? i),
          value: v
        }))
      }
    }
  }

  // Query-engine default shape: {logs, aggregations, total_count}
  if (d.aggregations && typeof d.aggregations === 'object') {
    if (Array.isArray(d.aggregations.time_series)) {
      return d.aggregations.time_series
        .map((item: any) => {
          const values = Object.values(item).filter(v => typeof v === 'number')
          return {
            label: String(item.time ?? ''),
            value: (values.length > 0 ? values[values.length - 1] : NaN) as number
          }
        })
        .filter((r: any) => Number.isFinite(r.value))
    }
    const rows = Object.entries(d.aggregations)
      .filter(([, v]) => typeof v === 'number')
      .map(([k, v]) => ({ label: k, value: v as number }))
    if (rows.length > 0) return rows
  }

  return []
}

const normalizeWidgetData = (widgetType: string, entry: WidgetDataEntry): NormalizedWidget => {
  if (entry.error) {
    return { kind: 'error', message: entry.error }
  }
  const d = entry.data
  if (d === null || d === undefined) {
    return { kind: 'empty' }
  }
  if (typeof d === 'object' && typeof d.error === 'string' && d.error) {
    return { kind: 'error', message: d.error }
  }
  if (typeof d === 'object' && typeof d.message === 'string' && d.message.includes('not implemented')) {
    return { kind: 'unsupported', message: d.message }
  }

  if (widgetType === 'stat' || widgetType === 'gauge' || widgetType === 'metric') {
    if (typeof d.value === 'number') {
      let change: number | undefined
      if (typeof d.change === 'string') {
        const parsed = parseFloat(d.change)
        if (Number.isFinite(parsed)) change = parsed
      } else if (typeof d.change === 'number') {
        change = d.change
      }
      return {
        kind: 'stat',
        value: d.value,
        formatted: typeof d.formatted_value === 'string' ? d.formatted_value : undefined,
        change,
        label: typeof d.label === 'string' ? d.label : undefined
      }
    }
    return { kind: 'empty' }
  }

  if (widgetType === 'table') {
    const columns: string[] = Array.isArray(d.columns) ? d.columns : (Array.isArray(d.headers) ? d.headers : [])
    const rows: any[] = Array.isArray(d.rows) ? d.rows : []
    if (rows.length === 0) return { kind: 'empty' }
    return {
      kind: 'table',
      columns: columns.length > 0 ? columns : Object.keys(rows[0] ?? {}),
      rows
    }
  }

  // Chart types
  const rows = extractSeriesRows(d)
  if (rows.length === 0) return { kind: 'empty' }
  return { kind: 'series', rows }
}

// Widget Components
function StatWidget({ widget, data }: { widget: Widget; data: Extract<NormalizedWidget, { kind: 'stat' }> }) {
  return (
    <div className="h-full flex flex-col justify-center">
      <div className="text-3xl font-bold text-white">
        {data.formatted ?? (Number.isInteger(data.value) ? data.value : data.value.toFixed(2))}
        <span className="text-sm font-normal text-slate-400 ml-1">
          {widget.query_definition?.metric === 'latency' ? 'ms' : ''}
          {widget.query_definition?.metric === 'throughput' ? '/s' : ''}
          {widget.query_definition?.metric === 'error_rate' ? '%' : ''}
        </span>
      </div>
      {data.change !== undefined && (
        <div className={`text-sm mt-1 ${data.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {data.change >= 0 ? '↑' : '↓'} {Math.abs(data.change).toFixed(1)}%
        </div>
      )}
      {data.label && (
        <div className="text-xs text-slate-500 mt-1">{data.label}</div>
      )}
    </div>
  )
}

function GaugeWidget({ data }: { data: Extract<NormalizedWidget, { kind: 'stat' }> }) {
  const value = Math.max(0, Math.min(data.value, 100))
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
      <div className="text-2xl font-bold text-white mt-2">{data.value.toFixed(0)}%</div>
      {data.label && <div className="text-xs text-slate-500 mt-1">{data.label}</div>}
    </div>
  )
}

function TableWidget({ data }: { data: Extract<NormalizedWidget, { kind: 'table' }> }) {
  return (
    <div className="h-full overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            {data.columns.map(key => (
              <th key={key} className="text-left py-2 px-2 text-slate-400 font-medium">
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i} className="border-b border-slate-700/50">
              {data.columns.map((col, j) => (
                <td key={j} className="py-2 px-2 text-white">
                  {String((row && typeof row === 'object' ? row[col] : row) ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ChartWidget({ widget, rows }: { widget: Widget; rows: { label: string; value: number }[] }) {
  const type = widget.type

  if (type === 'line_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="label" stroke="#64748b" fontSize={10} />
          <YAxis stroke="#64748b" fontSize={10} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
          />
          <Line type="monotone" dataKey="value" stroke={CHART_COLORS[0]} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'area_chart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
              <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="label" stroke="#64748b" fontSize={10} />
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
        <BarChart data={rows} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
          <XAxis type="number" stroke="#64748b" fontSize={10} />
          <YAxis dataKey="label" type="category" stroke="#64748b" fontSize={10} width={80} />
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
            data={rows}
            cx="50%"
            cy="50%"
            innerRadius={40}
            outerRadius={60}
            paddingAngle={2}
            dataKey="value"
            nameKey="label"
          >
            {rows.map((_, index) => (
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

function WidgetMessage({ icon: Icon, title, detail, tone }: {
  icon: any
  title: string
  detail?: string
  tone: 'error' | 'muted'
}) {
  const color = tone === 'error' ? 'text-red-400' : 'text-slate-400'
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-2">
      <Icon className={`w-6 h-6 mb-2 ${tone === 'error' ? 'text-red-400' : 'text-slate-500'}`} />
      <p className={`text-xs font-medium ${color}`}>{title}</p>
      {detail && <p className="text-[10px] text-slate-500 mt-1 break-all">{detail}</p>}
    </div>
  )
}

// Widget Renderer — three explicit states: loading, error, empty.
// Data always comes from GET /v1/dashboards/{id}/data; nothing is generated
// client-side.
function WidgetRenderer({ widget, entry, isLoading, fetchError, dataEndpoint }: {
  widget: Widget
  entry: WidgetDataEntry | undefined
  isLoading: boolean
  fetchError: string | null
  dataEndpoint: string
}) {
  if (isLoading) {
    return <div className="h-full flex items-center justify-center text-slate-400 text-sm">Loading...</div>
  }

  if (fetchError) {
    return (
      <WidgetMessage
        icon={AlertTriangle}
        title="Failed to load widget data"
        detail={fetchError}
        tone="error"
      />
    )
  }

  if (!entry) {
    return (
      <WidgetMessage
        icon={AlertTriangle}
        title="No data returned for this widget"
        detail={`${dataEndpoint} did not include widget "${widget.id}"`}
        tone="error"
      />
    )
  }

  const normalized = normalizeWidgetData(widget.type, entry)

  switch (normalized.kind) {
    case 'error':
      return (
        <WidgetMessage
          icon={AlertTriangle}
          title="Widget query failed"
          detail={normalized.message}
          tone="error"
        />
      )
    case 'unsupported':
      return (
        <WidgetMessage
          icon={Inbox}
          title="Widget type not supported by the data API"
          detail={normalized.message}
          tone="muted"
        />
      )
    case 'empty':
      return (
        <WidgetMessage
          icon={Inbox}
          title="No data in selected range"
          tone="muted"
        />
      )
    case 'stat':
      return widget.type === 'gauge'
        ? <GaugeWidget data={normalized} />
        : <StatWidget widget={widget} data={normalized} />
    case 'table':
      return <TableWidget data={normalized} />
    case 'series':
      return <ChartWidget widget={widget} rows={normalized.rows} />
  }
}

export default function DashboardViewPage() {
  const params = useParams()
  const router = useRouter()
  const { getApiTimeRange, refreshTrigger } = useTimeRange()
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [widgetData, setWidgetData] = useState<Record<string, WidgetDataEntry>>({})
  const [isDataLoading, setIsDataLoading] = useState(true)
  const [dataError, setDataError] = useState<string | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null)

  const dataEndpoint = `GET /v1/dashboards/${params.id}/data`

  // Fetch dashboard definition
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

  // Fetch real widget data for the whole dashboard
  const fetchDashboardData = useCallback(async () => {
    try {
      const { start_time, end_time } = getApiTimeRange()
      const response = await apiClient.get(`/v1/dashboards/${params.id}/data`, {
        params: { start_time, end_time }
      })
      const data: any = response?.data ?? response

      // Normalize the two widget-collection shapes into a map keyed by widget id
      const map: Record<string, WidgetDataEntry> = {}
      if (Array.isArray(data?.widgets)) {
        data.widgets.forEach((w: any) => {
          if (w?.widget_id) map[w.widget_id] = w
        })
      } else if (data?.widgets && typeof data.widgets === 'object') {
        Object.entries(data.widgets).forEach(([id, w]) => {
          map[id] = w as WidgetDataEntry
        })
      }
      setWidgetData(map)
      setDataError(null)
      setLastFetchedAt(new Date())
    } catch (err: any) {
      console.error('Failed to fetch dashboard data:', err)
      setWidgetData({})
      setDataError(`${dataEndpoint} returned ${err?.status ?? 'a network error'}${err?.message ? ` — ${err.message}` : ''}`)
    } finally {
      setIsDataLoading(false)
    }
  }, [params.id, getApiTimeRange, dataEndpoint])

  // Initial fetch + refetch when the global time range changes
  useEffect(() => {
    setIsDataLoading(true)
    fetchDashboardData()
  }, [fetchDashboardData, refreshTrigger])

  // Refresh by re-calling the data endpoint — driven by the widgets'
  // refresh_interval (smallest wins) or the auto-refresh toggle. Values are
  // never regenerated locally.
  useEffect(() => {
    if (!dashboard) return
    const intervals = (dashboard.widgets || [])
      .map(w => w.refresh_interval)
      .filter((n): n is number => typeof n === 'number' && n > 0)
    const widgetIntervalMs = intervals.length > 0 ? Math.min(...intervals) * 1000 : null
    const periodMs = autoRefresh
      ? Math.min(widgetIntervalMs ?? 30000, 30000)
      : widgetIntervalMs

    if (!periodMs) return
    const timer = setInterval(() => {
      fetchDashboardData()
    }, Math.max(periodMs, 5000))
    return () => clearInterval(timer)
  }, [dashboard, autoRefresh, fetchDashboardData])

  // Manual refresh — refetches from the API
  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await fetchDashboardData()
    } finally {
      setIsRefreshing(false)
    }
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

        {/* Dashboard-level data error */}
        {dataError && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-400">
              Failed to load widget data: {dataError}
            </p>
          </div>
        )}

        {/* Widgets Grid */}
        <div className="grid grid-cols-4 gap-4">
          {(dashboard.widgets || []).map(widget => (
            <div
              key={widget.id}
              style={getWidgetStyle(widget)}
              className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-slate-300">
                  {widget.name || widgetData[widget.id]?.title || 'Widget'}
                </h3>
                <button className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors">
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="h-[calc(100%-2rem)]">
                <WidgetRenderer
                  widget={widget}
                  entry={widgetData[widget.id]}
                  isLoading={isDataLoading}
                  fetchError={dataError}
                  dataEndpoint={dataEndpoint}
                />
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
            {lastFetchedAt && (
              <span>Data fetched: {lastFetchedAt.toLocaleTimeString()}</span>
            )}
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
