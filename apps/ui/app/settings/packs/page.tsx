'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { AlertTriangle, Loader2, Package } from 'lucide-react'
import { listPacks, PackSummary } from '@/lib/api/packs'
import { contentsSummary, packStatus, STATUS_CLASSES } from '@/lib/packFormat'

export default function PacksPage() {
  const [packs, setPacks] = useState<PackSummary[]>([])
  const [broken, setBroken] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const r = await listPacks()
        setPacks(r.packs)
        setBroken(r.errors)
      } catch (e: any) {
        setError(e?.message || 'Failed to load packs')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Package className="w-6 h-6 text-blue-400" /> Content Packs</h1>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Everything a log source needs in one install: pipelines that parse it into the common schema, detection rules
            with tests, saved searches and alert templates, and a dashboard. Upgrades keep the changes you made.
          </p>
        </div>

        {error && <div role="alert" className="p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-sm text-red-400">{error}</div>}
        {loading && <Loader2 className="w-5 h-5 animate-spin text-slate-400" />}

        {!loading && !error && packs.length === 0 && (
          <p className="text-sm text-slate-400">No packs found. The API reads them from packages/packs (or $SOURCE_PACKS_DIR).</p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {packs.map(p => {
            const status = packStatus(p)
            return (
              <Link key={p.id} href={`/settings/packs/${encodeURIComponent(p.id)}`} data-testid="pack-card"
                className="p-4 rounded-lg border border-white/10 bg-slate-800/40 hover:bg-slate-800/70 flex flex-col gap-2 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-white font-medium">{p.name}</div>
                    <div className="text-xs text-slate-500 font-mono">{p.id} · v{p.version}</div>
                  </div>
                  <span data-testid="pack-status" className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${STATUS_CLASSES[status.tone]}`}>{status.label}</span>
                </div>
                <p className="text-sm text-slate-400 line-clamp-3">{p.description}</p>
                <div className="text-xs text-slate-500 mt-auto">{contentsSummary(p.contents)}</div>
              </Link>
            )
          })}
        </div>

        {Object.keys(broken).length > 0 && (
          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-yellow-400" /> Packs that failed to load</h2>
            {Object.entries(broken).map(([id, reason]) => (
              <div key={id} className="text-xs text-slate-400"><span className="font-mono text-slate-300">{id}</span>: {reason}</div>
            ))}
          </section>
        )}
      </div>
    </DashboardLayout>
  )
}
