/**
 * Storage tiers API (Phase 12): /v1/storage/tiers. Reads throw on failure.
 */
import { apiClient } from '../api'
import type { SteadyState } from '../storageFormat'

export interface DataTypeTier {
  data_type: string; table: string; searchable_days: number; archive_days: number; custom: boolean
  default: { searchable_days: number; archive_days: number }
  archived_days: number; archived_rows: number; oldest_archive: string | null; newest_archive: string | null
  rehydrated_days: string[]
}
export interface TiersSummary {
  tiers: { hot: { days: number }; warm: { enabled: boolean | null }; cold: { bucket: string } }
  limits: { max_searchable_days: number; max_archive_days: number }
  data_types: DataTypeTier[]
  last_run: Record<string, any> | null
}
export interface SourceUsage { service: string; events: number; raw_bytes: number; share: number; levels: Record<string, number> }
export interface NoiseCandidate {
  service: string; level: string; events: number; raw_bytes: number; share: number; reason: string
  routing: { services: string[] }; drop_step: Record<string, any>
}
export interface TierUsage { rows: number; bytes: number; days?: number }
export interface CostReport {
  window_days: number
  ingest: { per_day: { day: string; events: number; raw_bytes: number }[]; events: number; raw_bytes: number; by_source: SourceUsage[] }
  storage: { data_type: string; bytes_per_row: number; hot: TierUsage; warm: TierUsage; cold: TierUsage }[]
  projection: {
    days_used: number; daily_events: number; daily_raw_bytes: number; monthly_events: number; monthly_raw_bytes: number
    steady_state: SteadyState; archive_ratio_assumed: boolean; logs_policy: { searchable_days: number; archive_days: number }
  }
  prices: Record<string, number>
  noise: NoiseCandidate[]
  notes: string[]
}
export interface RehydrateResult { rehydrated_days: number; rows: number; skipped: { day: string; reason: string }[]; errors: string[]; until: string }

async function call<T>(promise: Promise<{ success?: boolean; data?: T; error?: string }>, what: string): Promise<T> {
  const response = await promise
  if (!response.success) throw new Error(response.error || what)
  return response.data as T
}

export const getTiers = () => call<TiersSummary>(apiClient.get('/v1/storage/tiers'), 'Failed to load storage tiers')
export const getCosts = () => call<CostReport>(apiClient.get('/v1/storage/tiers/costs'), 'Failed to load storage costs')
export const setRetention = (dataType: string, body: { searchable_days: number; archive_days: number }) =>
  call(apiClient.put(`/v1/storage/tiers/policies/${encodeURIComponent(dataType)}`, body), 'Failed to save the retention')
export const runRetention = () => call<Record<string, any>>(apiClient.post('/v1/storage/tiers/run', {}), 'Retention run failed')
export const rehydrate = (body: { data_type: string; first_day: string; last_day: string; keep_days: number }) =>
  call<RehydrateResult>(apiClient.post('/v1/storage/tiers/rehydrate', body), 'Rehydration failed')
export const searchArchive = (query: string, start: string, end: string) =>
  call<{ logs: Record<string, any>[]; columns: string[]; total_count: number; query_info: Record<string, any> }>(
    apiClient.post('/v1/query/logql', { query, source: 'archive', start_time: start, end_time: end }), 'Archive search failed')
