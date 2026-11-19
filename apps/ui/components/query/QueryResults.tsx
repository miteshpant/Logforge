'use client'

// Phase 6: results of stats / top / timechart queries as a table (and a
// chart for timecharts) instead of a list of log lines.

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { timechartSeries } from '@/lib/dashboardPanels'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

const cell = (value: any) => {
  if (value === null || value === undefined) return ''
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 })
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function QueryResults({ resultType, columns, rows, truncated }: {
  resultType: 'table' | 'timechart'
  columns: string[]
  rows: Record<string, any>[]
  truncated: boolean
}) {
  const chart = resultType === 'timechart' && rows.length > 0 ? timechartSeries(columns, rows) : null
  return (
    <div data-testid="query-results" className="mb-4 bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl rounded-2xl border border-white/5 shadow-xl p-4 space-y-4">
      {chart && (
        <div className="h-64" data-testid="query-results-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart.rows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="label" stroke="#64748b" fontSize={10}
                tickFormatter={(v: string) => (v.length > 16 ? new Date(v).toLocaleTimeString() : v)} />
              <YAxis stroke="#64748b" fontSize={10} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
              {chart.names.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {chart.names.map((name, i) => (
                <Line key={name} type="monotone" dataKey={name} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="overflow-auto max-h-[28rem]">
        <table className="w-full text-sm" data-testid="query-results-table">
          <thead className="sticky top-0 bg-slate-900">
            <tr className="border-b border-slate-700">
              {columns.map(c => <th key={c} className="text-left py-2 px-3 text-xs font-semibold text-slate-400 uppercase">{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-slate-700/40 hover:bg-white/5">
                {columns.map(c => <td key={c} className="py-1.5 px-3 text-slate-200 font-mono text-xs">{cell(row[c])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="text-sm text-slate-400 py-6 text-center">No rows</p>}
      </div>
      <p className="text-xs text-slate-500">
        {rows.length.toLocaleString()} row{rows.length === 1 ? '' : 's'}{truncated ? ' (more rows exist; add a head or narrow the query)' : ''}
      </p>
    </div>
  )
}
