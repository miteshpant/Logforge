/** Field catalogue API (Phase 5): /v1/fields. Reads throw on failure. */
import { apiClient } from '../api'
import type { CatalogueField } from '../fieldFormat'

async function read<T>(endpoint: string, params?: Record<string, any>): Promise<T> {
  const response = await apiClient.get<T>(endpoint, params)
  if (!response.success) throw new Error(response.error || `Request failed: ${endpoint}`)
  return response.data as T
}

export const fetchFields = (window = '24h', service?: string) =>
  read<{ sampled_events: number; fields: CatalogueField[] }>('/v1/fields', { window, service })

export const fetchFieldValues = (field: string, window = '24h', limit = 10) =>
  read<{ field: string; total: number; distinct: number; values: Array<{ value: string; count: number }> }>(
    '/v1/fields/values', { field, window, limit })
