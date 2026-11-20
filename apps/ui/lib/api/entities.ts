/**
 * Entity analytics API (Phase 11): /v1/entities. Reads throw on failure.
 */
import { apiClient } from '../api'

export interface EntitySummary { entity_type: string; value: string; first_seen: string; last_seen: string; events: number }
export interface RiskFactor { kind: 'alert' | 'progression' | 'intel' | 'anomaly'; label: string; points: number; at?: string | null; ref?: string | null }
export interface EntityRisk {
  entity_type: string; value: string; score: number; raw: number; factors: RiskFactor[]; alerts: number
  tactics: string[]; last_alert: string | null
}
export interface EntityAnomaly { kind: string; label: string; severity: string; ts: string; value?: unknown; baseline?: unknown }
export interface EntityDetail {
  entity: EntitySummary
  risk: EntityRisk | null
  rank: number | null
  anomalies: EntityAnomaly[]
  alerts: { id: string; title: string; severity: string; ts: string; mitre_techniques?: string[] }[]
  cases: { id: string; title: string; status: string; severity: string }[]
  related: EntitySummary[]
  query: string
  flags: string[]
}

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const listEntities = (params: { type?: string; q?: string; limit?: number } = {}) =>
  read<{ entities: EntitySummary[] }>('/v1/entities', params)
export const entityRisk = (params: { type?: string; limit?: number } = {}) =>
  read<{ entities: EntityRisk[]; window_days: number; flags: string[] }>('/v1/entities/risk', params)
export const getEntity = (type: string, value: string) =>
  read<EntityDetail>(`/v1/entities/${encodeURIComponent(type)}/${encodeURIComponent(value)}`)
