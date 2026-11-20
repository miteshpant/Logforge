/**
 * AI assistant API (Phase 8): /v1/ai. Thin wrappers; reads throw on
 * failure, mutations reject (apiClient contract).
 */
import { apiClient } from '../api'
import type { AIProviderInfo } from '../aiFormat'

export interface AIStatus {
  global_enabled: boolean
  providers: AIProviderInfo[]
  tenant_enabled: boolean
  active: boolean
  provider: AIProviderInfo | null
  reason_code: string | null
  reason: string | null
}
export interface AISettings {
  enabled: boolean
  provider: string | null
  redact_fields: string[]
  monthly_token_budget: number | null
  requests_per_minute: number | null
}
export interface AISettingsResponse {
  settings: AISettings
  effective: { monthly_token_budget: number; requests_per_minute: number; max_tool_calls: number; redact_fields: string[] }
  status: AIStatus
}
export interface AICitation { id: string; kind: string; label: string; link: string }
export interface AIAnswer {
  mode: 'ai' | 'rule_based'
  text: string
  citations: AICitation[]
  grounded: boolean
  flags: string[]
  uncited?: string[]
  provider: AIProviderInfo | null
  usage?: { input_tokens: number; output_tokens: number }
  tool_calls?: { name: string; arguments: Record<string, string>; ok: boolean; error?: string }[]
  request_id?: string
  reason?: string
  reason_code?: string
  suggestions?: string[]
}
export interface AIUsage { tokens: number; requests: number; since: string; monthly_token_budget: number; requests_per_minute: number }
export interface AIAuditEntry {
  request_id: string; seq: number; ts: string; user_id: string; feature: string; kind: string
  provider: string; model: string; external: number; content: any; input_tokens: number; output_tokens: number
}

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const getAIStatus = () => read<AIStatus>('/v1/ai/status')
export const getAISettings = () => read<AISettingsResponse>('/v1/ai/settings')
export const getAIUsage = () => read<AIUsage>('/v1/ai/usage')
export const getAIAudit = (params: { request_id?: string; limit?: number } = {}) =>
  read<{ entries: AIAuditEntry[] }>('/v1/ai/audit', params)

export async function saveAISettings(settings: AISettings): Promise<AISettingsResponse> {
  return (await apiClient.put<AISettingsResponse>('/v1/ai/settings', settings)).data as AISettingsResponse
}

export async function askAI(question: string): Promise<AIAnswer> {
  return (await apiClient.post<AIAnswer>('/v1/ai/ask', { question })).data as AIAnswer
}

// -- Phase 9 -----------------------------------------------------------------------------
import type { DraftReport } from '../aiFormat'

interface Fallback { reason?: string; reason_code?: string; provider: AIProviderInfo | null; request_id?: string }

export interface QueryDraft extends Fallback {
  query: string | null; explanation: string; valid: boolean; mode: 'ai' | 'rule_based'; error: string | null
  fields_used: string[]; unknown_fields: string[]
}
export interface CitedSection { key: string; title: string; sentences: string[] }
export interface CitedSummary extends Fallback {
  subject: { kind: string; id: string; title?: string | null }
  mode: 'ai' | 'template'
  sections: CitedSection[]
  citations: AICitation[]
  dropped: string[]
  flags: string[]
}
export interface Explanation extends CitedSummary {
  fields: { field: string; value: unknown; meaning: string }[]
  queries: { label: string; query: string }[]
}
export interface PipelineDraft extends Fallback {
  pipeline: { name: string; description?: string; processors: Record<string, any>[]; on_failure?: Record<string, any>[] }
  explanation: string; report: DraftReport; mode: 'ai' | 'heuristic'; flags: string[]
}

async function post<T>(endpoint: string, body: unknown): Promise<T> {
  const response = await apiClient.post<T>(endpoint, body)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const draftQuery = (question: string) => post<QueryDraft>('/v1/ai/nl2query', { question })
export const triage = (kind: 'alert' | 'case', id: string) => post<CitedSummary>('/v1/ai/triage', { kind, id })
export const explainEvent = (event: Record<string, unknown>) => post<Explanation>('/v1/ai/explain', { event })
export const draftPipeline = (samples: string[], service: string) =>
  post<PipelineDraft>('/v1/ai/pipeline-draft', { samples, service })
