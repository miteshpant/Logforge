'use client'

// Phase 6: build a LogforgeQL query from a form. The result goes into the
// query bar, so the query stays visible and editable.

import { useMemo, useState } from 'react'
import { Plus, Trash2, X } from 'lucide-react'
import {
  BUILDER_AGGREGATIONS, BUILDER_OPERATORS, buildQuery, type AggregationRow, type FilterRow,
} from '@/lib/queryBuilder'

const SPANS = ['', '1m', '5m', '15m', '1h', '6h', '1d']
const input = 'px-2 py-1.5 bg-slate-800 border border-white/10 rounded-md text-sm text-white'

export default function QueryBuilder({ fields, onUse, onClose }: {
  fields: string[]
  onUse: (query: string) => void
  onClose: () => void
}) {
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState<FilterRow[]>([{ field: '', op: '=', value: '' }])
  const [aggregations, setAggregations] = useState<AggregationRow[]>([{ fn: 'count', field: '', as: '' }])
  const [groupBy, setGroupBy] = useState('')
  const [span, setSpan] = useState('')
  const [sort, setSort] = useState('')
  const [limit, setLimit] = useState('')

  const query = useMemo(() => buildQuery({
    search, filters, aggregations, groupBy: groupBy.split(',').map(s => s.trim()).filter(Boolean), span, sort,
    limit: limit ? Number(limit) : null,
  }), [search, filters, aggregations, groupBy, span, sort, limit])

  const update = <T,>(list: T[], set: (v: T[]) => void, i: number, patch: Partial<T>) =>
    set(list.map((row, j) => (j === i ? { ...row, ...patch } : row)))

  return (
    <div data-testid="query-builder" className="mb-4 bg-slate-900 border border-white/10 rounded-2xl p-4 space-y-3">
      <datalist id="builder-fields">{fields.map(f => <option key={f} value={f} />)}</datalist>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Query builder</h3>
        <button onClick={onClose} aria-label="Close builder" className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
      </div>
      <input data-testid="builder-search" placeholder="Text in the message (optional)" value={search}
        onChange={e => setSearch(e.target.value)} className={`${input} w-full`} />

      <div className="space-y-2">
        <p className="text-xs text-slate-400">Where</p>
        {filters.map((row, i) => (
          <div key={i} className="flex gap-2">
            <input data-testid="builder-filter-field" list="builder-fields" placeholder="field" value={row.field}
              onChange={e => update(filters, setFilters, i, { field: e.target.value })} className={`${input} w-48`} />
            <select data-testid="builder-filter-op" value={row.op} onChange={e => update(filters, setFilters, i, { op: e.target.value })} className={input}>
              {BUILDER_OPERATORS.map(op => <option key={op} value={op}>{op}</option>)}
            </select>
            <input data-testid="builder-filter-value" placeholder={row.op.includes('in') ? 'a, b, c' : 'value'} value={row.value}
              onChange={e => update(filters, setFilters, i, { value: e.target.value })} className={`${input} flex-1`} />
            <button aria-label="Remove condition" onClick={() => setFilters(filters.filter((_, j) => j !== i))}
              className="text-slate-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        <button onClick={() => setFilters([...filters, { field: '', op: '=', value: '' }])}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"><Plus className="w-3 h-3" /> condition</button>
      </div>

      <div className="space-y-2">
        <p className="text-xs text-slate-400">Calculate</p>
        {aggregations.map((row, i) => (
          <div key={i} className="flex gap-2">
            <select data-testid="builder-agg-fn" value={row.fn} onChange={e => update(aggregations, setAggregations, i, { fn: e.target.value })} className={input}>
              {BUILDER_AGGREGATIONS.map(fn => <option key={fn} value={fn}>{fn}</option>)}
            </select>
            <input data-testid="builder-agg-field" list="builder-fields" placeholder={row.fn === 'count' ? '(all events)' : 'field'}
              value={row.field} onChange={e => update(aggregations, setAggregations, i, { field: e.target.value })} className={`${input} w-56`} />
            <input data-testid="builder-agg-as" placeholder="name (optional)" value={row.as}
              onChange={e => update(aggregations, setAggregations, i, { as: e.target.value })} className={`${input} w-40`} />
            <button aria-label="Remove calculation" onClick={() => setAggregations(aggregations.filter((_, j) => j !== i))}
              className="text-slate-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></button>
          </div>
        ))}
        <button onClick={() => setAggregations([...aggregations, { fn: 'avg', field: '', as: '' }])}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"><Plus className="w-3 h-3" /> calculation</button>
      </div>

      <div className="flex flex-wrap gap-3 items-end">
        <label className="text-xs text-slate-400 flex flex-col gap-1">Group by
          <input data-testid="builder-group-by" list="builder-fields" placeholder="service, host" value={groupBy}
            onChange={e => setGroupBy(e.target.value)} className={`${input} w-56`} />
        </label>
        <label className="text-xs text-slate-400 flex flex-col gap-1">Over time
          <select data-testid="builder-span" value={span} onChange={e => setSpan(e.target.value)} className={input}>
            {SPANS.map(s => <option key={s} value={s}>{s ? `every ${s}` : 'no'}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-400 flex flex-col gap-1">Sort
          <input data-testid="builder-sort" placeholder="-count" value={sort} onChange={e => setSort(e.target.value)} className={`${input} w-32`} />
        </label>
        <label className="text-xs text-slate-400 flex flex-col gap-1">Rows
          <input data-testid="builder-limit" type="number" min={1} max={10000} placeholder="all" value={limit}
            onChange={e => setLimit(e.target.value)} className={`${input} w-24`} />
        </label>
      </div>

      <pre data-testid="builder-query" className="text-xs text-emerald-300 bg-slate-800/60 rounded-lg p-2 whitespace-pre-wrap break-all min-h-[2rem]">{query || ' '}</pre>
      <div className="flex justify-end">
        <button data-testid="builder-use" disabled={!query} onClick={() => onUse(query)}
          className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50">Use query</button>
      </div>
    </div>
  )
}
