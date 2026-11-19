/**
 * Formatting helpers for the case pages (Phase 2). Mirrors the status flow
 * in apps/api/cases.py.
 */

export type CaseStatus = 'new' | 'investigating' | 'contained' | 'resolved' | 'false_positive'

export interface CaseEvent {
  id: string
  case_id: string
  ts: string
  actor: string
  kind: string
  data: Record<string, any>
}

const STATUSES: CaseStatus[] = ['new', 'investigating', 'contained', 'resolved', 'false_positive']
const CLOSED: CaseStatus[] = ['resolved', 'false_positive']

export const statusLabel = (status: string) => status.replace(/_/g, ' ')

/** Statuses a case can move to from `status` (closed cases can only reopen). */
export function nextStatuses(status: CaseStatus): CaseStatus[] {
  if (CLOSED.includes(status)) return ['investigating']
  return STATUSES.filter(s => s !== status && s !== 'new')
}

export const needsReason = (status: string) => CLOSED.includes(status as CaseStatus)

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** One line describing a timeline event. */
export function describeEvent(event: CaseEvent): string {
  const { actor, data } = event
  switch (event.kind) {
    case 'created':
      return `${actor} opened the case`
    case 'alert_attached':
      return `Alert added: ${data.title || data.alert_id}${data.severity ? ` (${data.severity})` : ''}`
    case 'assigned':
      return data.to ? `${actor} assigned the case to ${data.to}` : `${actor} unassigned the case`
    case 'status_changed':
      return `${actor} changed status from ${statusLabel(data.from)} to ${statusLabel(data.to)}${data.reason ? `: ${data.reason}` : ''}`
    case 'comment':
      return `${actor} commented`
    case 'evidence_pinned':
      return `${actor} pinned ${data.kind}: ${data.title || data.ref}`
    case 'tags_changed':
      return `${actor} set tags: ${(data.to || []).join(', ') || 'none'}`
    case 'merged':
      return `${actor} merged ${plural((data.sources || []).length, 'case')} into this one`
    case 'merged_into':
      return `${actor} merged this case into ${data.target}`
    case 'split':
      return `${actor} moved ${plural((data.alert_ids || []).length, 'alert')} to ${data.new_case}`
    case 'split_from':
      return `${actor} split this case from ${data.case_id}`
    case 'updated':
      return `${actor} updated ${Object.keys(data).join(', ')}`
    default:
      return `${actor}: ${event.kind.replace(/_/g, ' ')}`
  }
}

/** "42m", "2h 15m", "2d 1h"; "—" when unknown. */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—'
  if (minutes < 1) return '<1m'
  if (minutes < 60) return `${Math.round(minutes)}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h ${Math.round(minutes % 60)}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

/** Where pinned evidence opens, or null if it has no page. Only http(s) links
 *  are followed, so a pinned `javascript:` URL can't run. */
export function evidenceHref(evidence: { kind: string; ref: string }): string | null {
  switch (evidence.kind) {
    case 'search':
      return `/observability/logs?q=${encodeURIComponent(evidence.ref)}`
    case 'trace':
      return `/observability/traces?trace_id=${encodeURIComponent(evidence.ref)}`
    case 'link':
    case 'file':
      return /^https?:\/\//i.test(evidence.ref) ? evidence.ref : null
    default:
      return null
  }
}
