/**
 * Ingest pipelines API (Phase 4): /v1/pipelines. Thin wrappers; reads throw on
 * failure, mutations reject (apiClient contract).
 */
import { apiClient } from '../api'
import type { Routing, Step } from '../pipelineFormat'

export interface PipelineDef {
  id: string
  name: string
  description: string
  enabled: boolean
  routing: Routing
  version: number
  builtin: boolean
  updated_at: string | null
  updated_by: string
  processors: Step[]
  on_failure: Step[]
}

export interface ProcessorStats {
  index: number; type: string; tag: string; count: number; skipped: number; failed: number; dropped: number
  time_us: number; avg_us: number
}
export interface VersionStats {
  version: number
  events: { in: number; ok: number; dropped: number; failed: number }
  events_per_second: number
  avg_us: number
  processors: ProcessorStats[]
}
export interface SimulationStep { index: number; processor: string; tag: string; status: string; doc: any; error?: string; on_failure?: boolean }
export interface SimulationResult { status: 'ok' | 'dropped' | 'failed'; doc: any; error: any; steps: SimulationStep[] }
export interface DeadLetter {
  id: string; pipeline_id: string; pipeline_version: number; processor: string; error: string; event: any
  failed_at: string; status: string
}

const BASE = '/v1/pipelines'

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const listPipelines = () => read<{ pipelines: PipelineDef[]; builtins: PipelineDef[] }>(BASE)
export const getPipeline = (id: string) => read<PipelineDef>(`${BASE}/${encodeURIComponent(id)}`)
export const tenantStats = () => read<{ pipelines: Record<string, { events: VersionStats['events']; events_per_second: number }> }>(`${BASE}/stats`)
export const pipelineStats = (id: string) => read<{ versions: VersionStats[] }>(`${BASE}/${encodeURIComponent(id)}/stats`)
export const deadLetters = (params: { pipeline_id?: string; status?: string; limit?: number }) =>
  read<{ entries: DeadLetter[]; total: number; counts: Record<string, Record<string, number>> }>(`${BASE}/dlq`, params)

export type PipelineBody = Omit<PipelineDef, 'version' | 'builtin' | 'updated_at' | 'updated_by'>

export async function createPipeline(body: PipelineBody) {
  return (await apiClient.post<PipelineDef>(BASE, body)).data as PipelineDef
}
export async function updatePipeline(id: string, body: PipelineBody) {
  return (await apiClient.put<PipelineDef>(`${BASE}/${encodeURIComponent(id)}`, body)).data as PipelineDef
}
export async function deletePipeline(id: string) {
  await apiClient.delete(`${BASE}/${encodeURIComponent(id)}`)
}
export async function simulatePipeline(pipeline: Partial<PipelineBody>, docs: Array<string | Record<string, unknown>>) {
  return (await apiClient.post<{ results: SimulationResult[] }>(`${BASE}/simulate`, { pipeline, docs })).data!.results
}
export async function replayDeadLetters(body: { ids?: string[]; pipeline_id?: string }) {
  return (await apiClient.post<{ replayed: number }>(`${BASE}/dlq/replay`, body)).data!
}
export async function discardDeadLetters(ids: string[]) {
  return (await apiClient.post<{ discarded: number }>(`${BASE}/dlq/discard`, { ids })).data!
}
