/**
 * Tenants API Module
 *
 * APIs for tenant/customer management and multi-tenancy.
 * All paths verified against the live OpenAPI spec (LF-027):
 *   GET/POST   /v1/tenants
 *   GET/PUT/DELETE /v1/tenants/{tenant_id}
 *   GET        /v1/tenants/{tenant_id}/usage
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

/**
 * Shape of the backend's TenantResponse model (apps/api/models.py).
 */
export interface Tenant {
  tenant_id: string
  name: string
  type: string
  status: 'active' | 'inactive' | 'suspended' | string
  primary_contact_name?: string
  primary_contact_email?: string
  industry?: string
  created_at: string
  updated_at: string
}

export interface TenantListResponse {
  tenants: Tenant[]
  total_count: number
  page: number
  page_size: number
  total_pages: number
}

export interface TenantUsage {
  tenant_id: string
  [key: string]: any
}

// ========== API FUNCTIONS ==========

/**
 * Get tenant by ID
 */
export async function getTenant(tenantId: string): Promise<ApiResponse<Tenant>> {
  return apiClient.get<Tenant>(`/v1/tenants/${tenantId}`)
}

/**
 * List all tenants (platform admin only)
 */
export async function listTenants(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<TenantListResponse>> {
  return apiClient.get('/v1/tenants', params)
}

/**
 * Create new tenant (platform admin only)
 */
export async function createTenant(
  tenant: Omit<Tenant, 'tenant_id' | 'created_at' | 'updated_at'>
): Promise<ApiResponse<Tenant>> {
  return apiClient.post<Tenant>('/v1/tenants', tenant)
}

/**
 * Update tenant
 */
export async function updateTenant(
  tenantId: string,
  updates: Partial<Tenant>
): Promise<ApiResponse<Tenant>> {
  return apiClient.put<Tenant>(`/v1/tenants/${tenantId}`, updates)
}

/**
 * Delete (decommission) tenant
 */
export async function deleteTenant(
  tenantId: string
): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/tenants/${tenantId}`)
}

/**
 * Get tenant usage statistics
 */
export async function getTenantUsage(
  tenantId: string,
  params?: {
    start_time?: string
    end_time?: string
  }
): Promise<ApiResponse<TenantUsage>> {
  return apiClient.get<TenantUsage>(`/v1/tenants/${tenantId}/usage`, params)
}

// Export all functions as a namespace
export const TenantsApi = {
  getTenant,
  listTenants,
  createTenant,
  updateTenant,
  deleteTenant,
  getTenantUsage,
}

export default TenantsApi
