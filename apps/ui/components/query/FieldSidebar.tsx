'use client'

/**
 * Field explorer (Phase 5): the tenant's fields from the catalogue, the
 * common-schema (ocsf.*) fields that resolve, and for any field its top
 * values with their share, each addable to (or excludable from) the query.
 */
import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Loader2, Minus, Plus, Search, X } from 'lucide-react'
import { fetchFieldValues, fetchFields } from '@/lib/api/fields'
import { CatalogueField, groupFields } from '@/lib/fieldFormat'

interface Props {
  window: string
  onClose: () => void
  onFilter: (field: string, value: unknown, exclude: boolean, type: string) => void
  onFields?: (names: string[]) => void
}

const TYPE_STYLE: Record<string, string> = {
  number: 'text-amber-300', ip: 'text-cyan-300', boolean: 'text-purple-300', string: 'text-slate-400',
}

export default function FieldSidebar({ window, onClose, onFilter, onFields }: Props) {
  const [fields, setFields] = useState<CatalogueField[]>([])
  const [sampled, setSampled] = useState(0)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [values, setValues] = useState<{ total: number; distinct: number; values: Array<{ value: string; count: number }> } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchFields(window)
      .then(r => { setFields(r.fields); setSampled(r.sampled_events); onFields?.(r.fields.map(f => f.name)) })
      .catch(e => setError(e?.message || 'Failed to load fields'))
      .finally(() => setLoading(false))
  }, [window])  // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (name: string) => {
    if (open === name) { setOpen(null); return }
    setOpen(name)
    setValues(null)
    try {
      setValues(await fetchFieldValues(name, window))
    } catch (e: any) {
      setError(e?.message || 'Failed to load values')
    }
  }

  const grouped = useMemo(() => groupFields(fields, search), [fields, search])

  const row = (f: CatalogueField) => (
    <li key={f.name} data-testid="field-row" data-field={f.name}>
      <button onClick={() => toggle(f.name)} className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 text-left">
        {open === f.name ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
        <span className="flex-1 truncate font-mono text-xs text-slate-200" title={f.name}>{f.name}</span>
        <span className={`text-[10px] ${TYPE_STYLE[f.type] || 'text-slate-400'}`}>{f.type}</span>
        <span className="text-[10px] text-slate-500 w-10 text-right">{f.presence_pct}%</span>
      </button>
      {open === f.name && (
        <div data-testid="field-values" className="ml-5 mr-1 mb-2 space-y-1">
          {!values && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
          {values && (
            <>
              <div className="text-[10px] text-slate-500">
                {values.distinct.toLocaleString()} distinct in {values.total.toLocaleString()} events · {f.services.slice(0, 3).join(', ')}
              </div>
              {values.values.map(v => {
                const share = values.total ? (100 * v.count) / values.total : 0
                return (
                  <div key={v.value} data-testid="field-value" className="group">
                    <div className="flex items-center gap-1 text-xs">
                      <span className="flex-1 truncate font-mono text-slate-300" title={v.value}>{v.value}</span>
                      <span className="text-slate-500">{v.count.toLocaleString()}</span>
                      <button aria-label={`Filter ${f.name} = ${v.value}`} data-testid="field-value-add"
                        onClick={() => onFilter(f.name, v.value, false, f.type)}
                        className="p-0.5 text-slate-500 hover:text-green-300"><Plus className="w-3 h-3" /></button>
                      <button aria-label={`Exclude ${f.name} = ${v.value}`}
                        onClick={() => onFilter(f.name, v.value, true, f.type)}
                        className="p-0.5 text-slate-500 hover:text-red-300"><Minus className="w-3 h-3" /></button>
                    </div>
                    <div className="h-1 bg-slate-800 rounded"><div className="h-1 bg-blue-500/70 rounded" style={{ width: `${Math.max(2, share)}%` }} /></div>
                  </div>
                )
              })}
              {values.values.length === 0 && <div className="text-xs text-slate-500">No values in this window.</div>}
            </>
          )}
        </div>
      )}
    </li>
  )

  return (
    <aside data-testid="field-sidebar" className="fixed right-0 top-0 h-full w-full sm:w-96 z-40 bg-slate-900/98 border-l border-white/10 shadow-2xl flex flex-col">
      <div className="flex items-center gap-2 p-4 border-b border-white/10">
        <h2 className="text-white font-semibold flex-1">Fields</h2>
        <button aria-label="Close fields" onClick={onClose} className="text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
      </div>
      <div className="p-3 border-b border-white/5">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input data-testid="field-search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Find a field"
            className="w-full pl-8 pr-2 py-1.5 bg-slate-950 border border-white/10 rounded text-sm text-white" />
        </div>
        <p className="text-[10px] text-slate-500 mt-2">From the latest {sampled.toLocaleString()} events in the window. Values are exact.</p>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {loading && <Loader2 className="w-4 h-4 animate-spin text-slate-400 m-2" />}
        {error && <div role="alert" className="text-xs text-red-400 p-2">{error}</div>}
        {!loading && (
          <>
            <ul>{grouped.fields.map(row)}</ul>
            {grouped.schema.length > 0 && (
              <>
                <h3 className="mt-3 mb-1 px-2 text-[11px] uppercase tracking-wide text-slate-500">Common schema (OCSF)</h3>
                <ul>{grouped.schema.map(row)}</ul>
              </>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
