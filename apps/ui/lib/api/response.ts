/**
 * Response automation API (Phase 13): integrations, playbooks and their runs,
 * case tickets, and reports. Calls throw on failure.
 */
import { apiClient } from '../api'
import type { KindInfo } from '../responseFormat'

export interface Integration {
  id: string; name: string; kind: string; config: Record<string, any>; enabled: boolean
  secrets_set: string[]; updated_by?: string; updated_at?: string
}
export interface ActionResult { ok: boolean; status: number | null; output: Record<string, any>; error: string }
export interface Playbook {
  id: string; name: string; definition: string; enabled: boolean; updated_by?: string; updated_at?: string
  trigger: string | null; when: string | null; steps: { id: string; type: string }[]; error: string | null
}
export interface RunStep {
  id: string; type: string; status: string; output: Record<string, any>; error: string
  prompt?: string; approvers?: string[]; deadline?: string; started_at?: string; finished_at?: string
  decision?: { by: string; approved: boolean; note: string; at: string }
}
export interface Run {
  id: string; playbook_id: string; playbook_name: string; trigger: string; trigger_ref: string; status: string
  steps: RunStep[]; context: Record<string, any>; created_at: string; updated_at: string
}
export interface CaseTicket {
  ticket: string; url: string; system: string; integration: string; ticket_status: string; case_status: string; synced_at: string
}
export interface ReportSchedule {
  id: string; name: string; every: 'daily' | 'weekly' | 'monthly'; hour: number; format: 'pdf' | 'csv'
  integration_id: string; recipients: string[]; enabled: boolean; last_sent: string | null; last_error: string
}
export interface SocReport {
  title: string; tenant: string; period: { start: string; end: string; days: number }
  sections: { title: string; columns?: string[]; rows: any[][]; note?: string }[]
}

async function call<T>(promise: Promise<{ success?: boolean; data?: T; error?: string }>, what: string): Promise<T> {
  const response = await promise
  if (!response.success) throw new Error(response.error || what)
  return response.data as T
}

// integrations
export const listKinds = () => call<{ kinds: KindInfo[] }>(apiClient.get('/v1/integrations/kinds'), 'Failed to load integration kinds')
export const listIntegrations = () => call<{ integrations: Integration[] }>(apiClient.get('/v1/integrations'), 'Failed to load integrations')
export const saveIntegration = (body: { name: string; kind: string; config: Record<string, any>; secrets?: Record<string, string>; enabled?: boolean }, id?: string) =>
  call<{ integration: Integration }>(id ? apiClient.put(`/v1/integrations/${id}`, body) : apiClient.post('/v1/integrations', body),
    'Failed to save the integration')
export const deleteIntegration = (id: string) => call(apiClient.delete(`/v1/integrations/${id}`), 'Failed to delete the integration')
export const testIntegration = (id: string) =>
  call<{ result: ActionResult }>(apiClient.post(`/v1/integrations/${id}/test`, {}), 'The test failed to run')
export const caseTickets = (caseId: string) =>
  call<{ tickets: CaseTicket[] }>(apiClient.get('/v1/integrations/tickets', { case_id: caseId }), 'Failed to load tickets')
export const syncTickets = () => call<Record<string, any>>(apiClient.post('/v1/integrations/tickets/sync', {}), 'Ticket sync failed')

// playbooks
export const listPlaybooks = () => call<{ playbooks: Playbook[] }>(apiClient.get('/v1/playbooks'), 'Failed to load playbooks')
export const validatePlaybook = (definition: string) =>
  call<{ valid: boolean; error?: string; name?: string; trigger?: string; when?: string; steps?: { id: string; type: string; containment: boolean }[] }>(
    apiClient.post('/v1/playbooks/validate', { definition }), 'Validation failed')
export const savePlaybook = (definition: string, enabled: boolean, id?: string) =>
  call<{ playbook: Playbook }>(id ? apiClient.put(`/v1/playbooks/${id}`, { definition, enabled })
    : apiClient.post('/v1/playbooks', { definition, enabled }), 'Failed to save the playbook')
export const deletePlaybook = (id: string) => call(apiClient.delete(`/v1/playbooks/${id}`), 'Failed to delete the playbook')
export const runPlaybook = (id: string, target: { alert_id?: string; case_id?: string }) =>
  call<{ run: Run }>(apiClient.post(`/v1/playbooks/${id}/run`, target), 'Failed to start the run')
export const listRuns = (status?: string) =>
  call<{ runs: Run[] }>(apiClient.get('/v1/playbooks/runs', status ? { status } : undefined), 'Failed to load runs')
export const decide = (runId: string, step: string, decision: 'approve' | 'reject', note = '') =>
  call<{ run: Run }>(apiClient.post(`/v1/playbooks/runs/${runId}/decision`, { step, decision, note }), 'The decision was not recorded')

// reports
export const socReport = (days: number) => call<SocReport>(apiClient.get('/v1/reports/soc', { days }), 'Failed to build the report')
export const listSchedules = () => call<{ schedules: ReportSchedule[] }>(apiClient.get('/v1/reports/schedules'), 'Failed to load schedules')
export const saveSchedule = (body: Omit<ReportSchedule, 'id' | 'last_sent' | 'last_error'>, id?: string) =>
  call<{ schedule: ReportSchedule }>(id ? apiClient.put(`/v1/reports/schedules/${id}`, body)
    : apiClient.post('/v1/reports/schedules', body), 'Failed to save the schedule')
export const deleteSchedule = (id: string) => call(apiClient.delete(`/v1/reports/schedules/${id}`), 'Failed to delete the schedule')
export const sendSchedule = (id: string) =>
  call<{ result: ActionResult }>(apiClient.post(`/v1/reports/schedules/${id}/send`, {}), 'Failed to send the report')

/** Save an export (SOC report as PDF or CSV, or the ATT&CK Navigator layer) to the user's computer. */
export async function download(endpoint: string, fallbackName: string): Promise<string> {
  const { blob, filename } = await apiClient.getBlob(endpoint)
  const name = filename || fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return name
}
