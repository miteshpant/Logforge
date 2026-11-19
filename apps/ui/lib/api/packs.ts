/**
 * Content packs API (Phase 7): /v1/packs. Thin wrappers; reads throw on
 * failure, mutations reject (apiClient contract).
 */
import { apiClient } from '../api'
import type { PlanAction } from '../packFormat'

export interface PackSource { name: string; service?: string; paths?: string[] }
export interface PackSummary {
  id: string
  name: string
  version: string
  description: string
  sources: PackSource[]
  contents: Record<string, number>
  installed_version: string | null
  update_available: boolean
}
export interface InstalledPack { pack: string; version: string; objects: string[]; installed_at: string | null; installed_by: string }
export interface PackDetail extends Omit<PackSummary, 'installed_version'> {
  pipelines: { id: string; name: string; description: string; routing: any }[]
  rules: { id: string; title: string; level: string; description: string; tags: string[] }[]
  searches: { id: string; name: string; every: string | null; alert: boolean; enabled: boolean }[]
  dashboards: { name: string; panels: number }[]
  lookups: { name: string; rows: number }[]
  samples: { file: string; service: string; lines: number }[]
  installed: InstalledPack | null
}
export interface PlanItem { key: string; kind: string; name: string; reason: string }
export interface PackPlan {
  pack: string
  from_version: string | null
  to_version: string
  counts: Record<PlanAction, number>
  actions: Record<PlanAction, PlanItem[]>
}

const BASE = '/v1/packs'
const path = (id: string) => `${BASE}/${encodeURIComponent(id)}`

async function read<T>(endpoint: string): Promise<T> {
  const response = await apiClient.get<T>(endpoint)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const listPacks = () => read<{ packs: PackSummary[]; errors: Record<string, string> }>(BASE)
export const getPack = (id: string) => read<PackDetail>(path(id))

export async function planPack(id: string, force = false): Promise<PackPlan> {
  return (await apiClient.post<PackPlan>(`${path(id)}/plan${force ? '?force=true' : ''}`, {})).data as PackPlan
}

export async function installPack(id: string, force = false): Promise<{ plan: PackPlan; installed: InstalledPack }> {
  return (await apiClient.post<{ plan: PackPlan; installed: InstalledPack }>(
    `${path(id)}/install${force ? '?force=true' : ''}`, {})).data!
}

export async function removePack(id: string): Promise<{ pack: string; removed: string[]; kept: string[] }> {
  return (await apiClient.delete<{ pack: string; removed: string[]; kept: string[] }>(path(id))).data!
}
