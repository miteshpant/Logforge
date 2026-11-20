'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { Archive, Database, HardDrive, Loader2, Play, RotateCcw, Search, Snowflake, TrendingUp } from 'lucide-react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import {
  getCosts, getTiers, rehydrate, runRetention, searchArchive, setRetention,
  type CostReport, type RehydrateResult, type TiersSummary,
} from '@/lib/api/storage'
import { bytes, money, percent, retentionSummary, steadyRows } from '@/lib/storageFormat'

const LABEL: Record<string, string> = { logs: 'Logs', security: 'Security alerts', traces: 'Traces', metrics: 'Metrics' }
const isoDay = (d: Date) => d.toISOString().slice(0, 10)

/** Settings → Storage (Phase 12): tiers, retention per data type, costs, archives. */
export default function StoragePage() {
  const [tiers, setTiers] = useState<TiersSummary | null>(null)
  const [costs, setCosts] = useState<CostReport | null>(null)
  const [edits, setEdits] = useState<Record<string, { searchable_days: number; archive_days: number }>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [t, c] = await Promise.all([getTiers(), getCosts()])
      setTiers(t)
      setCosts(c)
      setEdits(Object.fromEntries(t.data_types.map(d => [d.data_type, { searchable_days: d.searchable_days, archive_days: d.archive_days }])))
    } catch (e: any) {
      setError(e?.message || 'Failed to load storage')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const save = async (dataType: string) => {
    setMessage(null); setError(null)
    try {
      await setRetention(dataType, edits[dataType])
      setMessage(`Saved: ${LABEL[dataType] || dataType} ${retentionSummary(edits[dataType])}.`)
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to save')
    }
  }

  const run = async () => {
    setBusy(true); setMessage(null); setError(null)
    try {
      const out = await runRetention()
      setMessage(`Retention ran: ${out.archived} day(s) archived, ${out.deleted_days} deleted, ${out.expired} archive(s) expired` +
        (out.errors?.length ? `; ${out.errors.length} error(s): ${out.errors[0]}` : '.'))
      await load()
    } catch (e: any) {
      setError(e?.message || 'Retention run failed')
    } finally {
      setBusy(false)
    }
  }

  const maxDay = Math.max(1, ...(costs?.ingest.per_day.map(d => d.events) || [1]))
  const chartDays = costs ? lastDays(costs.window_days, costs.ingest.per_day) : []

  return (
    <DashboardLayout>
      <div className="p-6 space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><HardDrive className="w-6 h-6" /> Storage & Retention</h1>
          <p className="text-slate-400 mt-1">Where your data lives, how long it stays, and what it costs.</p>
        </div>
        {message && <p className="text-sm text-emerald-300" data-testid="storage-message">{message}</p>}
        {error && <p className="text-sm text-red-400" data-testid="storage-error">{error}</p>}
        {!tiers && !error && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}

        {tiers && (
          <section className="grid gap-4 md:grid-cols-3" data-testid="storage-tiers">
            <Tier icon={<Database className="w-5 h-5" />} name="Hot" where="ClickHouse, local disk"
              detail={`The newest ${tiers.tiers.hot.days} days`} />
            <Tier icon={<HardDrive className="w-5 h-5" />} name="Warm" where="ClickHouse, object storage"
              detail={tiers.tiers.warm.enabled ? 'Searchable until each type’s searchable days' : 'Not configured: searchable data stays on local disk'} />
            <Tier icon={<Snowflake className="w-5 h-5" />} name="Cold" where={`Parquet archives (${tiers.tiers.cold.bucket})`}
              detail="One file per day, searchable in place or rehydrated" />
          </section>
        )}

        {tiers && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Retention</h2>
              <button onClick={run} disabled={busy} data-testid="retention-run"
                className="px-3 py-1.5 rounded-lg border border-white/10 text-sm text-slate-200 hover:bg-white/5 flex items-center gap-2">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Run now
              </button>
            </div>
            <div className="rounded-xl border border-white/10 overflow-x-auto">
              <table className="w-full text-sm" data-testid="retention-table">
                <thead className="bg-slate-900/60 text-slate-400 text-xs uppercase">
                  <tr><th className="text-left p-3">Data</th><th className="text-left p-3">Searchable days</th>
                    <th className="text-left p-3">Archive days (0: none)</th><th className="text-left p-3">Archives</th><th className="p-3" /></tr>
                </thead>
                <tbody>
                  {tiers.data_types.map(d => (
                    <tr key={d.data_type} className="border-t border-white/5" data-testid={`retention-${d.data_type}`}>
                      <td className="p-3 text-white">{LABEL[d.data_type] || d.data_type}
                        <span className="block text-xs text-slate-500">{d.custom ? 'your setting' : 'default'} · {retentionSummary(edits[d.data_type] || d)}</span></td>
                      <td className="p-3"><input type="number" min={1} max={tiers.limits.max_searchable_days}
                        value={edits[d.data_type]?.searchable_days ?? d.searchable_days} data-testid={`searchable-${d.data_type}`}
                        onChange={e => setEdits({ ...edits, [d.data_type]: { ...edits[d.data_type], searchable_days: Number(e.target.value) } })}
                        className="w-24 px-2 py-1 rounded bg-slate-900 border border-white/10 text-white" /></td>
                      <td className="p-3"><input type="number" min={0} max={tiers.limits.max_archive_days}
                        value={edits[d.data_type]?.archive_days ?? d.archive_days} data-testid={`archive-${d.data_type}`}
                        onChange={e => setEdits({ ...edits, [d.data_type]: { ...edits[d.data_type], archive_days: Number(e.target.value) } })}
                        className="w-24 px-2 py-1 rounded bg-slate-900 border border-white/10 text-white" /></td>
                      <td className="p-3 text-slate-300 text-xs">
                        {d.archived_days ? `${d.archived_days} day(s), ${d.archived_rows.toLocaleString()} rows, ${d.oldest_archive} to ${d.newest_archive}` : 'none yet'}
                        {d.rehydrated_days.length > 0 && <span className="block text-amber-300">rehydrated: {d.rehydrated_days.join(', ')}</span>}
                      </td>
                      <td className="p-3 text-right"><button onClick={() => save(d.data_type)} data-testid={`save-${d.data_type}`}
                        className="px-3 py-1 rounded bg-blue-600 text-white text-xs hover:bg-blue-500">Save</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500">A day past its searchable period is archived, the archive is read back and counted,
              and only then is the day deleted from ClickHouse. The job runs hourly.</p>
          </section>
        )}

        {costs && (
          <section className="space-y-4" data-testid="storage-costs">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2"><TrendingUp className="w-5 h-5" /> Ingest and cost</h2>
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-xl border border-white/10 p-4 lg:col-span-2">
                <p className="text-sm text-slate-300">Logs per day, last {costs.window_days} days: {costs.ingest.events.toLocaleString()} events,
                  {' '}{bytes(costs.ingest.raw_bytes)} received</p>
                <div className="mt-3 flex items-end gap-1 h-32" data-testid="ingest-chart">
                  {chartDays.map(d => (
                    <div key={d.day} className={`flex-1 rounded-t min-w-[4px] ${d.events ? 'bg-blue-500/60' : 'bg-white/5'}`}
                      style={{ height: `${d.events ? Math.max(2, (d.events / maxDay) * 100) : 2}%` }}
                      title={`${d.day}: ${d.events.toLocaleString()} events, ${bytes(d.raw_bytes)}`} />
                  ))}
                </div>
              </div>
              <div className="rounded-xl border border-white/10 p-4" data-testid="cost-projection">
                <p className="text-sm text-slate-300">At this rate ({costs.projection.daily_events.toLocaleString()} events a day,
                  {' '}{bytes(costs.projection.monthly_raw_bytes)} a month) and {retentionSummary(costs.projection.logs_policy)}:</p>
                <table className="w-full text-sm mt-2">
                  <tbody>
                    {steadyRows(costs.projection.steady_state).map(r => (
                      <tr key={r.tier}><td className="py-1 capitalize text-slate-400">{r.tier}</td><td className="text-slate-300">{r.days} d</td>
                        <td className="text-slate-300">{bytes(r.gb * 1024 ** 3)}</td><td className="text-right text-white">{money(r.cost)}</td></tr>
                    ))}
                    <tr className="border-t border-white/10"><td className="py-1 text-slate-300" colSpan={3}>Storage per month</td>
                      <td className="text-right font-semibold text-white">{money(costs.projection.steady_state.monthly_cost.total)}</td></tr>
                  </tbody>
                </table>
                <p className="text-xs text-slate-500 mt-2">Prices per GB-month: hot ${costs.prices.hot}, warm ${costs.prices.warm},
                  cold ${costs.prices.cold} (configuration).{costs.projection.archive_ratio_assumed ? ' Archive size assumed equal to ClickHouse’s until archives exist.' : ''}</p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-white/10 overflow-x-auto">
                <table className="w-full text-sm" data-testid="ingest-sources">
                  <thead className="bg-slate-900/60 text-slate-400 text-xs uppercase">
                    <tr><th className="text-left p-2">Source</th><th className="text-right p-2">Events</th><th className="text-right p-2">Share</th><th className="text-right p-2">Received</th></tr>
                  </thead>
                  <tbody>
                    {costs.ingest.by_source.slice(0, 10).map(s => (
                      <tr key={s.service} className="border-t border-white/5">
                        <td className="p-2 text-white">{s.service}<span className="block text-xs text-slate-500">
                          {Object.entries(s.levels).sort((a, b) => b[1] - a[1]).map(([l, n]) => `${l} ${n.toLocaleString()}`).join(' · ')}</span></td>
                        <td className="p-2 text-right text-slate-300">{s.events.toLocaleString()}</td>
                        <td className="p-2 text-right text-slate-300">{percent(s.share)}</td>
                        <td className="p-2 text-right text-slate-300">{bytes(s.raw_bytes)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="rounded-xl border border-white/10 overflow-x-auto">
                <table className="w-full text-sm" data-testid="storage-by-tier">
                  <thead className="bg-slate-900/60 text-slate-400 text-xs uppercase">
                    <tr><th className="text-left p-2">Stored now</th><th className="text-right p-2">Hot</th><th className="text-right p-2">Warm</th><th className="text-right p-2">Cold</th></tr>
                  </thead>
                  <tbody>
                    {costs.storage.map(s => (
                      <tr key={s.data_type} className="border-t border-white/5">
                        <td className="p-2 text-white">{LABEL[s.data_type] || s.data_type}</td>
                        {(['hot', 'warm', 'cold'] as const).map(t => (
                          <td key={t} className="p-2 text-right text-slate-300">{bytes(s[t].bytes)}<span className="block text-xs text-slate-500">{s[t].rows.toLocaleString()} rows</span></td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-slate-500 p-2">{costs.notes[0]}</p>
              </div>
            </div>

            {costs.noise.length > 0 && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-2" data-testid="noise">
                <p className="text-sm font-semibold text-amber-200">Noise you could drop before it is stored</p>
                {costs.noise.map(n => (
                  <div key={`${n.service}:${n.level}`} className="text-sm text-slate-200">
                    {n.reason}. A pipeline for <code className="text-amber-200">{n.service}</code> with the step{' '}
                    <code className="text-amber-200">{JSON.stringify(n.drop_step)}</code> drops them.
                  </div>
                ))}
                <Link href="/settings/pipelines" className="text-sm text-blue-300 hover:underline">Open Ingest Pipelines</Link>
              </div>
            )}
          </section>
        )}

        {tiers && <ArchivePanel />}
      </div>
    </DashboardLayout>
  )
}

/** The window's days, oldest first, with zeros for days without data. */
function lastDays(n: number, perDay: { day: string; events: number; raw_bytes: number }[]) {
  const byDay = new Map(perDay.map(d => [d.day, d]))
  const today = new Date()
  return Array.from({ length: n }, (_, i) => {
    const day = isoDay(new Date(today.getTime() - (n - 1 - i) * 86400_000))
    return byDay.get(day) || { day, events: 0, raw_bytes: 0 }
  })
}

function Tier({ icon, name, where, detail }: { icon: React.ReactNode; name: string; where: string; detail: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-800/40 p-4">
      <p className="text-white font-semibold flex items-center gap-2">{icon} {name}</p>
      <p className="text-sm text-slate-300 mt-1">{where}</p>
      <p className="text-xs text-slate-500 mt-1">{detail}</p>
    </div>
  )
}

function ArchivePanel() {
  const today = new Date()
  const [query, setQuery] = useState('* | stats count() by service')
  const [start, setStart] = useState(isoDay(new Date(today.getTime() - 90 * 86400_000)))
  const [end, setEnd] = useState(isoDay(today))
  const [result, setResult] = useState<{ logs: Record<string, any>[]; columns: string[]; query_info: Record<string, any> } | null>(null)
  const [first, setFirst] = useState(isoDay(new Date(today.getTime() - 60 * 86400_000)))
  const [last, setLast] = useState(isoDay(new Date(today.getTime() - 60 * 86400_000)))
  const [keep, setKeep] = useState(7)
  const [rehydrated, setRehydrated] = useState<RehydrateResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const search = async () => {
    setBusy(true); setError(null)
    try {
      setResult(await searchArchive(query, `${start}T00:00:00Z`, `${end}T23:59:59Z`))
    } catch (e: any) {
      setError(e?.message || 'Archive search failed')
    } finally {
      setBusy(false)
    }
  }

  const restore = async () => {
    setBusy(true); setError(null)
    try {
      setRehydrated(await rehydrate({ data_type: 'logs', first_day: first, last_day: last, keep_days: keep }))
    } catch (e: any) {
      setError(e?.message || 'Rehydration failed')
    } finally {
      setBusy(false)
    }
  }

  const columns = result ? (result.columns.length ? result.columns : Object.keys(result.logs[0] || {})) : []
  return (
    <section className="space-y-4" data-testid="archive-panel">
      <h2 className="text-lg font-semibold text-white flex items-center gap-2"><Archive className="w-5 h-5" /> Archives</h2>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="rounded-xl border border-white/10 p-4 space-y-3">
        <p className="text-sm text-slate-300">Search archived logs in place, with the same query language (up to a year at a time).</p>
        <div className="flex flex-wrap gap-2">
          <input value={query} onChange={e => setQuery(e.target.value)} data-testid="archive-query"
            className="flex-1 min-w-[16rem] px-3 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-sm text-white font-mono" />
          <input type="date" value={start} onChange={e => setStart(e.target.value)} className="px-2 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-sm text-white" />
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} className="px-2 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-sm text-white" />
          <button onClick={search} disabled={busy} data-testid="archive-search"
            className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm flex items-center gap-2"><Search className="w-4 h-4" /> Search archives</button>
        </div>
        {result && (
          <div data-testid="archive-results">
            <p className="text-xs text-slate-500">{result.query_info.archived_days} archived day(s) read
              {result.query_info.first_day ? `, ${result.query_info.first_day} to ${result.query_info.last_day}` : ''}; {result.logs.length} row(s).</p>
            {result.logs.length > 0 && (
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-xs">
                  <thead className="text-slate-400"><tr>{columns.map(c => <th key={c} className="text-left p-1">{c}</th>)}</tr></thead>
                  <tbody>{result.logs.slice(0, 50).map((row, i) => (
                    <tr key={i} className="border-t border-white/5">{columns.map(c => <td key={c} className="p-1 text-slate-300">{String(row[c] ?? '')}</td>)}</tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="rounded-xl border border-white/10 p-4 space-y-3">
        <p className="text-sm text-slate-300">Rehydrate: copy archived days back into ClickHouse, for full-speed search and dashboards, for a few days.</p>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-300">
          from <input type="date" value={first} onChange={e => setFirst(e.target.value)} data-testid="rehydrate-first" className="px-2 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-white" />
          to <input type="date" value={last} onChange={e => setLast(e.target.value)} data-testid="rehydrate-last" className="px-2 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-white" />
          keep for <input type="number" min={1} max={30} value={keep} onChange={e => setKeep(Number(e.target.value))} className="w-16 px-2 py-1.5 rounded-lg bg-slate-900 border border-white/10 text-white" /> days
          <button onClick={restore} disabled={busy} data-testid="rehydrate"
            className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-200 hover:bg-white/5 flex items-center gap-2"><RotateCcw className="w-4 h-4" /> Rehydrate</button>
        </div>
        {rehydrated && (
          <p className="text-sm text-slate-300" data-testid="rehydrate-result">
            {rehydrated.rehydrated_days} day(s), {rehydrated.rows.toLocaleString()} rows back until {rehydrated.until}.
            {rehydrated.skipped.length > 0 && ` Skipped ${rehydrated.skipped.length}: still in ClickHouse.`}
            {rehydrated.errors.length > 0 && ` Errors: ${rehydrated.errors.join('; ')}`}
          </p>
        )}
      </div>
    </section>
  )
}
