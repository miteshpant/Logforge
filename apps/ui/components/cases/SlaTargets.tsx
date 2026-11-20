'use client'

import { useEffect, useState } from 'react'
import { saveSlaTargets, Severity, SlaMinutes, slaTargets } from '@/lib/api/cases'

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']
const KINDS = ['acknowledge', 'resolve'] as const

/** Per-tenant SLA targets: minutes to acknowledge and resolve, per severity. */
export default function SlaTargets({ onSaved }: { onSaved: () => void }) {
  const [targets, setTargets] = useState<SlaMinutes | null>(null)
  const [defaults, setDefaults] = useState<SlaMinutes | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    try {
      const data = await slaTargets()
      setTargets(data.targets_minutes); setDefaults(data.defaults_minutes)
    } catch (e: any) { setError(e?.message || 'Failed to load SLA targets') }
  }
  useEffect(() => { load() }, [])

  const save = async (reset = false) => {
    if (!targets || !defaults) return
    setError(null); setMessage(null)
    const overrides: Record<string, Record<string, number>> = {}
    if (!reset) for (const kind of KINDS) for (const s of SEVERITIES) {
      if (targets[kind][s] !== defaults[kind][s]) (overrides[kind] ||= {})[s] = targets[kind][s]
    }
    try {
      const data = await saveSlaTargets(overrides)
      setTargets(data.targets_minutes)
      setMessage(reset ? 'Back to the defaults.' : 'Saved.')
      onSaved()
    } catch (e: any) { setError(e?.message || 'Failed to save') }
  }

  if (!targets) return error ? <p className="text-sm text-red-400">{error}</p> : null
  return (
    <div data-testid="sla-targets" className="rounded-lg border border-white/10 bg-slate-800/50 p-4 space-y-3">
      <p className="text-sm text-slate-300">SLA targets, in minutes. Breaches in the overview count against these.</p>
      <table className="text-sm">
        <thead><tr className="text-slate-400"><th className="text-left pr-4">Severity</th><th className="pr-4">Acknowledge</th><th>Resolve</th></tr></thead>
        <tbody>
          {SEVERITIES.map(s => (
            <tr key={s}>
              <td className="pr-4 text-slate-200 capitalize">{s}</td>
              {KINDS.map(kind => (
                <td key={kind} className="pr-4 py-1">
                  <input type="number" min={1} data-testid={`sla-${kind}-${s}`} value={targets[kind][s]}
                    onChange={e => setTargets({ ...targets, [kind]: { ...targets[kind], [s]: Number(e.target.value) } })}
                    className="w-28 bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p role="alert" className="text-sm text-red-400" data-testid="sla-error">{error}</p>}
      {message && <p className="text-sm text-emerald-300" data-testid="sla-message">{message}</p>}
      <div className="flex gap-2">
        <button data-testid="sla-save" onClick={() => save()} className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-sm">Save</button>
        <button onClick={() => save(true)} className="px-3 py-1.5 rounded bg-slate-700 text-white text-sm">Reset to defaults</button>
      </div>
    </div>
  )
}
