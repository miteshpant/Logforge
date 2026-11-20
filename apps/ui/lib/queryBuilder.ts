// Query builder (Phase 6): a form that writes LogforgeQL. The query it builds
// goes into the query bar, where it can be edited, so nothing here is hidden.

export interface FilterRow { field: string; op: string; value: string }
export interface AggregationRow { fn: string; field: string; as: string }

export interface QuerySpec {
  search: string
  filters: FilterRow[]
  aggregations: AggregationRow[]
  groupBy: string[]
  /** a timechart span such as 1h; empty means stats */
  span: string
  /** e.g. "-errors" */
  sort: string
  limit: number | null
}

export const BUILDER_OPERATORS = ['=', '!=', '>', '>=', '<', '<=', 'contains', 'startswith', 'endswith', 'in',
  'not in', '=~'] as const
export const BUILDER_AGGREGATIONS = ['count', 'dc', 'sum', 'avg', 'min', 'max', 'median', 'p90', 'p95', 'p99',
  'values', 'earliest', 'latest'] as const

const quote = (text: string) => `"${text.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
const isNumber = (text: string) => /^-?(0|[1-9]\d*)(\.\d+)?$/.test(text.trim())
const literal = (text: string) => (isNumber(text) ? text.trim() : quote(text.trim()))

function condition(row: FilterRow): string | null {
  if (!row.field.trim() || !row.op) return null
  if (row.op === 'in' || row.op === 'not in') {
    const items = row.value.split(',').map(v => v.trim()).filter(Boolean)
    if (items.length === 0) return null
    return `${row.field} ${row.op} [${items.map(literal).join(', ')}]`
  }
  if (row.value.trim() === '') return null
  const value = row.op === '=~' || ['contains', 'startswith', 'endswith'].includes(row.op)
    ? quote(row.value.trim())
    : literal(row.value)
  return `${row.field} ${row.op} ${value}`
}

function aggregation(row: AggregationRow): string | null {
  if (!row.fn) return null
  if (row.fn !== 'count' && !row.field.trim()) return null
  const call = `${row.fn}(${row.fn === 'count' ? row.field.trim() : row.field.trim()})`
  return row.as.trim() ? `${call} as ${row.as.trim()}` : call
}

export function buildQuery(spec: QuerySpec): string {
  const parts: string[] = []
  const search = spec.search.trim()
  const head = search ? (search.includes(' ') ? quote(search) : search) : ''
  const conditions = spec.filters.map(condition).filter((c): c is string => !!c)
  if (conditions.length) parts.push(`where ${conditions.join(' and ')}`)
  const aggs = spec.aggregations.map(aggregation).filter((a): a is string => !!a)
  const by = spec.groupBy.map(f => f.trim()).filter(Boolean)
  if (aggs.length) {
    const byText = by.length ? ` by ${spec.span ? by[0] : by.join(', ')}` : ''
    parts.push(spec.span ? `timechart span=${spec.span} ${aggs.join(', ')}${byText}` : `stats ${aggs.join(', ')}${byText}`)
  }
  if (spec.sort.trim()) parts.push(`sort ${spec.sort.trim()}`)
  if (spec.limit && spec.limit > 0) parts.push(`head ${Math.floor(spec.limit)}`)
  if (!head && parts.length === 0) return ''
  return [head, ...parts.map(p => `| ${p}`)].filter(Boolean).join(' ')
}
