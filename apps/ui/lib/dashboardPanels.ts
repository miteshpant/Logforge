// Dashboards from queries (Phase 6): helpers for query panels and variables.

/** A dashboard variable set to All (the API's "*"). */
export const ALL = '*'

export interface DashboardVariable {
  name: string
  label: string
  type: 'custom' | 'query' | 'text'
  values?: string[]
  query?: string
  default: string
  include_all: boolean
}

/** Query parameters for GET /v1/dashboards/{id}/data. */
export function dataParams(
  range: { start_time: string; end_time: string },
  values: Record<string, string>
): Record<string, string> {
  const params: Record<string, string> = { start_time: range.start_time, end_time: range.end_time }
  for (const [name, value] of Object.entries(values)) params[`var-${name}`] = value
  return params
}

export interface PanelSeries {
  names: string[]
  rows: Record<string, string | number>[]
}

/** A query panel's {labels, series: [{name, data}]} as chart rows, one key per series. */
export function seriesFromPanel(d: any): PanelSeries | null {
  if (!d || !Array.isArray(d.labels) || !Array.isArray(d.series)) return null
  if (!d.series.every((s: any) => s && typeof s.name === 'string' && Array.isArray(s.data))) return null
  // `label` is the axis key; a series that happens to be called "label" is renamed.
  const names: string[] = d.series.map((s: any) => (s.name === 'label' ? 'label ' : s.name || '(empty)'))
  const rows = d.labels.map((label: any, i: number) => {
    const row: Record<string, string | number> = { label: String(label) }
    d.series.forEach((s: any, j: number) => {
      const v = s.data[i]
      row[names[j]] = typeof v === 'number' ? v : 0
    })
    return row
  })
  return { names, rows }
}

export interface QueryResultShape {
  resultType: string
  columns: string[]
  rows: Record<string, any>[]
}

/** The widget type a query result fits best. */
export function panelTypeFor(result: QueryResultShape): string {
  if (result.resultType === 'timechart') return 'line_chart'
  if (result.resultType === 'events') return 'table'
  const first = result.rows[0] || {}
  const numeric = result.columns.filter(c => typeof first[c] === 'number')
  if (result.rows.length === 1 && numeric.length === result.columns.length && numeric.length > 0) return 'metric'
  if (numeric.length > 0 && numeric.length < result.columns.length) return 'bar_chart'
  return 'table'
}

/** Timechart rows (_time, [split], values...) as chart rows, one key per series. */
export function timechartSeries(columns: string[], rows: Record<string, any>[]): PanelSeries {
  const valueCols = columns.filter(c => c !== '_time' && rows.some(r => typeof r[c] === 'number'))
  const split = columns.find(c => c !== '_time' && !valueCols.includes(c))
  const labels: string[] = []
  for (const r of rows) if (!labels.includes(String(r._time))) labels.push(String(r._time))
  if (split && valueCols.length === 1) {
    const names: string[] = []
    const points = new Map<string, number>()
    for (const r of rows) {
      const name = String(r[split] ?? '')
      if (!names.includes(name)) names.push(name)
      points.set(`${name}\u0000${r._time}`, typeof r[valueCols[0]] === 'number' ? r[valueCols[0]] : 0)
    }
    return seriesFromPanel({ labels, series: names.map(n => ({ name: n, data: labels.map(l => points.get(`${n}\u0000${l}`) ?? 0) })) })!
  }
  const byLabel = new Map(rows.map(r => [String(r._time), r]))
  return seriesFromPanel({ labels, series: valueCols.map(c => ({ name: c, data: labels.map(l => byLabel.get(l)?.[c] ?? 0) })) })!
}
