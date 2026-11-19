'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { ArrowLeft, CheckCircle2, Loader2, Package, Trash2 } from 'lucide-react'
import { getPack, installPack, PackDetail, PackPlan, planPack, removePack } from '@/lib/api/packs'
import { ACTION_LABELS, ACTION_ORDER, contentsSummary, packStatus, planSummary, STATUS_CLASSES, techniques } from '@/lib/packFormat'

const LEVEL_CLASSES: Record<string, string> = {
  critical: 'text-red-300', high: 'text-orange-300', medium: 'text-yellow-300', low: 'text-slate-300',
}

function message(e: any, fallback: string) {
  return e?.message || e?.detail || fallback
}

export default function PackPage() {
  const { id } = useParams<{ id: string }>()
  const [pack, setPack] = useState<PackDetail | null>(null)
  const [plan, setPlan] = useState<PackPlan | null>(null)
  const [force, setForce] = useState(false)
  const [busy, setBusy] = useState<'plan' | 'install' | 'remove' | null>('plan')
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async (withForce: boolean) => {
    setBusy('plan')
    try {
      const [detail, p] = await Promise.all([getPack(id), planPack(id, withForce)])
      setPack(detail)
      setPlan(p)
    } catch (e: any) {
      setError(message(e, 'Failed to load the pack'))
    } finally {
      setBusy(null)
    }
  }, [id])

  useEffect(() => { load(false) }, [load])

  async function onForce(value: boolean) {
    setForce(value)
    setError(null)
    await load(value)
  }

  async function onInstall() {
    setBusy('install')
    setError(null)
    setNotice(null)
    try {
      const r = await installPack(id, force)
      setNotice(`Installed ${r.installed.version}: ${planSummary(r.plan.counts)}.`)
      setForce(false)
      await load(false)
    } catch (e: any) {
      setError(message(e, 'Install failed'))
      setBusy(null)
    }
  }

  async function onRemove() {
    setBusy('remove')
    setError(null)
    setNotice(null)
    try {
      const r = await removePack(id)
      setConfirmRemove(false)
      setNotice(`Removed ${r.removed.length} objects.` + (r.kept.length ? ` Kept ${r.kept.length} you changed: ${r.kept.join(', ')}.` : ''))
      await load(false)
    } catch (e: any) {
      setError(message(e, 'Remove failed'))
      setBusy(null)
    }
  }

  const installedVersion = pack?.installed?.version ?? null
  const status = pack ? packStatus({ version: pack.version, installed_version: installedVersion,
                                     update_available: pack.update_available }) : null
  const changes = plan ? plan.counts.create + plan.counts.update + plan.counts.remove : 0

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6 max-w-6xl">
        <Link href="/settings/packs" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white">
          <ArrowLeft className="w-4 h-4" /> Content packs
        </Link>

        {!pack && busy && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}
        {error && <div role="alert" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {notice && (
          <div data-testid="pack-notice" className="p-3 rounded-lg border border-green-500/30 bg-green-500/10 text-sm text-green-300 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" /> <span>{notice}</span>
          </div>
        )}

        {pack && status && (
          <>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Package className="w-6 h-6 text-blue-400" /> {pack.name}
                </h1>
                <div className="text-xs text-slate-500 font-mono mt-1">{pack.id} · v{pack.version} · {contentsSummary(pack.contents)}</div>
                <p className="text-sm text-slate-400 mt-2 max-w-3xl">{pack.description}</p>
              </div>
              <span data-testid="pack-status" className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_CLASSES[status.tone]}`}>{status.label}</span>
            </div>

            <section className="rounded-lg border border-white/10 bg-slate-800/40 p-4 space-y-3" data-testid="pack-plan">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-white">
                    {installedVersion ? `What ${status.action.toLowerCase()} would change` : 'What installing adds'}
                    {installedVersion && plan && <span className="text-slate-500 font-normal"> ({installedVersion} → {plan.to_version})</span>}
                  </h2>
                  <p className="text-xs text-slate-400" data-testid="plan-summary">{plan ? planSummary(plan.counts) : 'Working out the changes…'}</p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {installedVersion && (
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input type="checkbox" data-testid="plan-force" checked={force} disabled={!!busy}
                        onChange={e => onForce(e.target.checked)} />
                      Overwrite my local changes
                    </label>
                  )}
                  <button data-testid="pack-install" onClick={onInstall} disabled={!!busy || !plan || (!!installedVersion && changes === 0)}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm">
                    {busy === 'install' && <Loader2 className="w-4 h-4 animate-spin" />} {status.action}
                  </button>
                  {installedVersion && !confirmRemove && (
                    <button data-testid="pack-remove" onClick={() => setConfirmRemove(true)} disabled={!!busy}
                      className="flex items-center gap-2 px-3 py-2 border border-white/10 hover:bg-white/5 text-slate-200 rounded-lg text-sm">
                      <Trash2 className="w-4 h-4" /> Remove
                    </button>
                  )}
                </div>
              </div>
              {confirmRemove && (
                <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-200">
                  <span className="flex-1 min-w-[200px]">Remove what this pack installed? Objects you have changed since are kept.</span>
                  <button data-testid="pack-remove-confirm" onClick={onRemove} disabled={!!busy}
                    className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg">
                    {busy === 'remove' && <Loader2 className="w-4 h-4 animate-spin" />} Remove pack
                  </button>
                  <button onClick={() => setConfirmRemove(false)} className="px-3 py-1.5 border border-white/10 rounded-lg text-slate-200">Cancel</button>
                </div>
              )}
              {plan && (
                <div className="space-y-3">
                  {ACTION_ORDER.filter(a => plan.actions[a]?.length).map(a => (
                    <div key={a} data-testid={`plan-group-${a}`}>
                      <div className="text-xs uppercase text-slate-500 mb-1">{ACTION_LABELS[a]} · {plan.actions[a].length}</div>
                      <ul className="divide-y divide-white/5 rounded border border-white/5">
                        {plan.actions[a].map(item => (
                          <li key={item.key} className="px-3 py-1.5 text-sm flex flex-wrap gap-x-3 gap-y-0.5">
                            <span className="text-xs text-slate-500 w-20 shrink-0">{item.kind}</span>
                            <span className="text-slate-200 break-all flex-1 min-w-[160px]">{item.name}</span>
                            <span className="text-xs text-slate-500">{item.reason}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white">Sources</h2>
              <ul className="space-y-1 text-sm">
                {pack.sources.map(s => (
                  <li key={s.name} className="text-slate-300">
                    {s.name}
                    {s.service && <span className="text-xs text-slate-500"> · send with service <code className="text-slate-300">{s.service}</code></span>}
                    {s.paths?.length ? <span className="text-xs text-slate-500"> · {s.paths.join(', ')}</span> : null}
                  </li>
                ))}
              </ul>
            </section>

            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-white">Detection rules</h2>
              <div className="rounded-lg border border-white/10 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/80 text-slate-400 text-xs uppercase">
                    <tr><th className="p-3 text-left">Rule</th><th className="p-3 text-left">Level</th><th className="p-3 text-left">ATT&amp;CK</th></tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {pack.rules.map(r => (
                      <tr key={r.id} data-testid="pack-rule">
                        <td className="p-3"><div className="text-slate-200">{r.title}</div><div className="text-xs text-slate-500">{r.description}</div></td>
                        <td className={`p-3 ${LEVEL_CLASSES[r.level] || 'text-slate-300'}`}>{r.level}</td>
                        <td className="p-3 text-xs font-mono text-slate-300">{techniques(r.tags).join(' ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-white">Pipelines</h2>
                <ul className="space-y-1 text-sm">
                  {pack.pipelines.map(p => (
                    <li key={p.id}>
                      <span className="font-mono text-slate-200">{p.id}</span>
                      <span className="text-xs text-slate-500"> · {p.description}{p.routing?.services?.length ? ` · services ${p.routing.services.join(', ')}` : ''}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="space-y-2">
                <h2 className="text-sm font-semibold text-white">Searches and dashboards</h2>
                <ul className="space-y-1 text-sm">
                  {pack.searches.map(s => (
                    <li key={s.id} className="text-slate-200">
                      {s.name}
                      <span className="text-xs text-slate-500">
                        {s.alert ? ` · alert template${s.enabled ? '' : ', disabled until you enable it'}` : ' · saved search'}
                        {s.every ? ` · every ${s.every}` : ''}
                      </span>
                    </li>
                  ))}
                  {pack.dashboards.map(d => (
                    <li key={d.name} className="text-slate-200">{d.name}<span className="text-xs text-slate-500"> · dashboard, {d.panels} panels</span></li>
                  ))}
                  {pack.lookups.map(l => (
                    <li key={l.name} className="text-slate-200">{l.name}<span className="text-xs text-slate-500"> · lookup table, {l.rows} rows</span></li>
                  ))}
                </ul>
              </section>
            </div>

            {pack.installed && (
              <p className="text-xs text-slate-500" data-testid="pack-installed">
                Installed {pack.installed.version}
                {pack.installed.installed_at ? ` on ${new Date(pack.installed.installed_at).toLocaleString()}` : ''}
                {pack.installed.installed_by ? ` by ${pack.installed.installed_by}` : ''}; {pack.installed.objects.length} objects.
                {' '}<Link href="/dashboards" className="text-blue-300 hover:underline">Dashboards</Link>
                {' · '}<Link href="/security/rules" className="text-blue-300 hover:underline">Detection rules</Link>
                {' · '}<Link href="/settings/pipelines" className="text-blue-300 hover:underline">Pipelines</Link>
              </p>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
