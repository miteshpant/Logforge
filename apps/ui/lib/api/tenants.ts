/**
 * Tenants API Module
 *
 * APIs for tenant/customer management and multi-tenancy
 */

import { apiClient, ApiResponse } from '../api'

// ========== TYPE DEFINITIONS ==========

export interface Tenant {
  id: string
  name: string
  subdomain?: string
  status: 'active' | 'inactive' | 'suspended'
  created_at: string
  updated_at: string
  settings?: {
    retention_days?: number
    data_limit_gb?: number
    user_limit?: number
    features?: string[]
  }
  plan?: string
  billing_email?: string
}

export interface TenantUsage {
  tenant_id: string
  data_ingested_gb: number
  data_stored_gb: number
  active_users: number
  api_requests: number
  period_start: string
  period_end: string
}

export interface TenantMember {
  user_id: string
  email: string
  name: string
  role: string
  joined_at: string
  last_active?: string
  status: 'active' | 'inactive'
}

// ========== API FUNCTIONS ==========

/**
 * Get tenant by ID
 */
export async function getTenant(tenantId: string): Promise<ApiResponse<Tenant>> {
  return apiClient.get<Tenant>(`/v1/tenants/${tenantId}`)
}

/**
 * List all tenants (admin only)
 */
export async function listTenants(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<{ tenants: Tenant[]; total: number }>> {
  return apiClient.get('/v1/tenants', params)
}

/**
 * Create new tenant
 */
export async function createTenant(
  tenant: Omit<Tenant, 'id' | 'created_at' | 'updated_at'>
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
 * Delete tenant
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

/**
 * List tenant members
 */
export async function listTenantMembers(
  tenantId: string
): Promise<ApiResponse<{ members: TenantMember[] }>> {
  return apiClient.get(`/v1/tenants/${tenantId}/members`)
}

/**
 * Add member to tenant
 */
export async function addTenantMember(
  tenantId: string,
  member: {
    email: string
    role: string
  }
): Promise<ApiResponse<TenantMember>> {
  return apiClient.post<TenantMember>(`/v1/tenants/${tenantId}/members`, member)
}

/**
 * Update tenant member role
 */
export async function updateTenantMember(
  tenantId: string,
  userId: string,
  updates: {
    role?: string
    status?: string
  }
): Promise<ApiResponse<TenantMember>> {
  return apiClient.put<TenantMember>(
    `/v1/tenants/${tenantId}/members/${userId}`,
    updates
  )
}

/**
 * Remove member from tenant
 */
export async function removeTenantMember(
  tenantId: string,
  userId: string
): Promise<ApiResponse<void>> {
  return apiClient.delete(`/v1/tenants/${tenantId}/members/${userId}`)
}

// Export all functions as a namespace
export const TenantsApi = {
  getTenant,
  listTenants,
  createTenant,
  updateTenant,
  deleteTenant,
  getTenantUsage,
  listTenantMembers,
  addTenantMember,
  updateTenantMember,
  removeTenantMember,
}

export default TenantsApi
