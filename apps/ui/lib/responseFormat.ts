/** Formatting for integrations, playbooks and reports (Phase 13). */

export interface KindInfo {
  kind: string; label: string; config: string[]; secrets: string[]; inputs: string[]; containment: boolean; ticket: boolean
}
export interface Field { name: string; label: string; secret: boolean; required: boolean; help?: string }

const WORDS: Record<string, string> = { url: 'URL', api: 'API', id: 'ID', smtp: 'SMTP' }

export function fieldLabel(name: string): string {
  const words = name.split('_').map(w => WORDS[w] ?? w)
  const first = words[0] === words[0].toUpperCase() ? words[0] : words[0][0].toUpperCase() + words[0].slice(1)
  return [first, ...words.slice(1)].join(' ')
}

/** Required config and secrets, then the optional secrets a kind can use. */
export function kindFields(kind: KindInfo): Field[] {
  const fields: Field[] = [
    ...kind.config.map(name => ({ name, label: fieldLabel(name), secret: false, required: true })),
    ...kind.secrets.map(name => ({ name, label: fieldLabel(name), secret: true, required: true })),
  ]
  if (kind.ticket) {
    fields.push({ name: 'webhook_secret', label: 'Webhook secret', secret: true, required: false,
      help: 'Lets the ticket system call back when a ticket changes, so the case follows it.' })
  }
  if (kind.kind === 'webhook' || kind.kind === 'containment_webhook') {
    fields.push({ name: 'signing_secret', label: 'Signing secret', secret: true, required: false,
      help: 'Requests carry an X-Logforge-Signature HMAC of the body.' })
  }
  return fields
}

export interface RunLike { status: string; steps: { id: string; type: string; status: string; prompt?: string; deadline?: string; approvers?: string[] }[] }

// step statuses (engine.py): pending, waiting, done, skipped, failed, rejected, expired
const DONE = new Set(['done', 'skipped', 'failed', 'rejected', 'expired'])

export function runProgress(run: RunLike): string {
  const done = run.steps.filter(s => DONE.has(s.status)).length
  return `${done} of ${run.steps.length} step${run.steps.length === 1 ? '' : 's'} done`
}

export function waitingApproval(run: RunLike) {
  return run.steps.find(s => s.status === 'waiting') ?? null
}

export type Tone = 'good' | 'bad' | 'waiting' | 'neutral'

export function runTone(status: string): Tone {
  if (status === 'succeeded') return 'good'
  if (status === 'waiting_approval' || status === 'running') return 'waiting'
  if (['failed', 'rejected', 'expired'].includes(status)) return 'bad'
  return 'neutral'
}

export const TONE_CLASS: Record<Tone, string> = {
  good: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  bad: 'bg-red-500/15 text-red-300 border-red-500/30',
  waiting: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  neutral: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
}

export function triggerSummary(p: { trigger?: string | null; when?: string | null; error?: string | null }): string {
  if (!p.trigger) return `Invalid: ${p.error || 'unreadable definition'}`
  const on = `On ${p.trigger.replace('_', ' ')}`
  return p.when ? `${on} when ${p.when}` : on
}

const EVERY: Record<string, string> = { daily: 'Daily', weekly: 'Weekly (Mondays)', monthly: 'Monthly (the 1st)' }

export function scheduleSummary(s: { every: string; hour: number; format: string; recipients: string[] }): string {
  const n = s.recipients.length
  return `${EVERY[s.every] || s.every} at ${String(s.hour).padStart(2, '0')}:00 UTC, ${s.format.toUpperCase()} to ` +
    `${n} recipient${n === 1 ? '' : 's'}`
}
