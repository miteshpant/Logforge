/**
 * Cases API (Phase 2): /v1/security/cases.
 *
 * Thin wrappers: errors propagate to the caller (mutations reject with
 * ApiError; failed reads throw too, so pages handle both the same way).
 */
import { apiClient } from '../api'
import type { CaseEvent, CaseStatus } from '../caseFormat'

export type Severity = 'low' | 'medium' | 'high' | 'critical'

export interface Case {
  id: string
  tenant_id: string
  title: string
  severity: Severity
  status: CaseStatus
  assignee: string | null
  description: string
  tags: string[]
  alert_ids: string[]
  entities: Record<string, string[]>
  group_key: string
  created_by: string
  created_at: string
  updated_at: string
  acknowledged_at: string | null
  contained_at: string | null
  resolved_at: string | null
  last_alert_at: string | null
  close_reason: string
  merged_into: string
}

export interface CaseAlert {
  id: string
  rule_id?: string
  title?: string
  severity?: Severity
  status?: string
  ts?: string
  mitre_techniques?: string[]
  entities?: Record<string, string[]>
  threat?: { max_confidence?: number | null; threat_types?: string[]; sources?: string[] }
  geo?: Record<string, { country?: string; city?: string; asn?: number | string; as_org?: string }>
  missing?: boolean
}

export interface CaseDetail {
  case: Case
  alerts: CaseAlert[]
  timeline: CaseEvent[]
  /** Pins not taken back (Phase 10). */
  evidence?: CaseEvent[]
}

export interface Evidence {
  kind: 'search' | 'event' | 'trace' | 'log' | 'link' | 'file'
  ref: string
  title?: string
  data?: Record<string, unknown>
}

interface TimeStat { mean: number | null; median: number | null; count: number }

export interface CaseMetrics {
  cases: number
  open_total: number
  open_by_status: Record<string, number>
  ageing: Record<string, number>
  analyst_load: Record<string, number>
  alerts_per_case: number
  by_severity: Record<Severity, { cases: number; open: number; mtta_minutes: TimeStat; mttr_minutes: TimeStat }>
  sla_breaches: { acknowledge: Record<Severity, number>; resolve: Record<Severity, number> }
}

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const BASE = '/v1/security/cases'

export const listCases = (params: { status?: string[]; q?: string; assignee?: string; severity?: string;
  limit?: number; offset?: number } = {}) =>
  read<{ cases: Case[]; total: number }>(BASE, params)

export const getCase = (id: string) => read<CaseDetail>(`${BASE}/${encodeURIComponent(id)}`)

export const caseMetrics = (days = 30) => read<CaseMetrics>(`${BASE}/metrics`, { days })

export type SlaMinutes = Record<'acknowledge' | 'resolve', Record<Severity, number>>
export interface SlaTargets { targets_minutes: SlaMinutes; defaults_minutes: SlaMinutes; overrides: Partial<SlaMinutes> }
export const slaTargets = () => read<SlaTargets>(`${BASE}/sla`)
export async function saveSlaTargets(overrides: Partial<Record<'acknowledge' | 'resolve', Partial<Record<Severity, number>>>>): Promise<SlaTargets> {
  return (await apiClient.put<SlaTargets>(`${BASE}/sla`, overrides)).data as SlaTargets
}

export async function createCase(body: { title: string; severity?: Severity; description?: string;
  alert_ids?: string[]; evidence?: Evidence[]; tags?: string[] }): Promise<Case> {
  return (await apiClient.post<Case>(BASE, body)).data as Case
}

type Action = 'assign' | 'comments' | 'status' | 'tags' | 'evidence' | 'alerts' | 'merge'

export async function caseAction(id: string, action: Action, body: Record<string, unknown>): Promise<Case> {
  return (await apiClient.post<Case>(`${BASE}/${encodeURIComponent(id)}/${action}`, body)).data as Case
}

export async function updateCase(id: string, body: { title?: string; description?: string; severity?: Severity }) {
  return (await apiClient.patch<Case>(`${BASE}/${encodeURIComponent(id)}`, body)).data as Case
}

export async function bulkCases(body: { case_ids: string[]; action: 'assign' | 'set_status' | 'tags';
  assignee?: string | null; status?: string; reason?: string; add?: string[]; remove?: string[] }) {
  return (await apiClient.post<{ updated: string[]; errors: Record<string, string> }>(`${BASE}/bulk`, body)).data
}

/** Move some alerts out of a case into a new one; returns both. */
export async function splitCase(id: string, alertIds: string[], title?: string): Promise<{ case: Case; new_case: Case }> {
  return (await apiClient.post<{ case: Case; new_case: Case }>(`${BASE}/${encodeURIComponent(id)}/split`,
    { alert_ids: alertIds, title: title || undefined })).data as { case: Case; new_case: Case }
}

/** Take back a pin (Phase 10): it stays in the timeline, marked as taken back. */
export async function unpinEvidence(id: string, evidenceId: string): Promise<Case> {
  return (await apiClient.delete<Case>(`${BASE}/${encodeURIComponent(id)}/evidence/${encodeURIComponent(evidenceId)}`)).data as Case
}
