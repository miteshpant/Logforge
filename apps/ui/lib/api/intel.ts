/**
 * Threat intelligence API (Phase 3): /v1/security/intel. Thin wrappers;
 * errors propagate to the caller.
 */
import { apiClient } from '../api'

export interface Feed {
  id: string | null
  name: string
  kind: string
  url: string
  enabled: boolean
  interval_minutes: number
  confidence: number
  ttl_days: number
  secret_env: string
  secret_configured: boolean
  last_status: string
  last_run_at: string | null
  last_count: number
  last_error: string
}

export interface IntelIndicator {
  indicator_type: string
  value: string
  threat_type: string
  confidence: number
  source: string
  tags: string[]
  expires_at: string | null
  seen_7d: number
}

const BASE = '/v1/security/intel'

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const listFeeds = () => read<{ feeds: Feed[]; templates: Feed[] }>(`${BASE}/feeds`)
export const searchIndicators = (params: { q?: string; type?: string; limit?: number }) =>
  read<{ indicators: IntelIndicator[]; total: number }>(`${BASE}/indicators`, params)

export async function addFeed(body: { template?: string } & Partial<Feed>) {
  return (await apiClient.post<Feed>(`${BASE}/feeds`, body)).data as Feed
}
export async function updateFeed(id: string, body: Partial<Feed>) {
  return (await apiClient.patch<Feed>(`${BASE}/feeds/${encodeURIComponent(id)}`, body)).data as Feed
}
export async function deleteFeed(id: string) {
  await apiClient.delete(`${BASE}/feeds/${encodeURIComponent(id)}`)
}
export async function runFeed(id: string) {
  return (await apiClient.post<{ status: string; count: number; new: unknown[]; error: string }>(
    `${BASE}/feeds/${encodeURIComponent(id)}/run`)).data
}
export async function addIndicator(body: { value: string; threat_type?: string; confidence?: number; tags?: string[] }) {
  return (await apiClient.post<IntelIndicator>(`${BASE}/indicators`, body)).data as IntelIndicator
}
export async function deleteIndicator(type: string, value: string) {
  await apiClient.delete(`${BASE}/indicators/${encodeURIComponent(type)}/${encodeURIComponent(value)}`)
}
