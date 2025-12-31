/**
 * Roles API Client
 * 15+ endpoints for role-based access control and permission management
 * Based on: /docs/wiki/knowledge_base/devDocs/Role-Router-API-Documentation.md
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Role types
export interface Role {
  id: string
  name: string
  description: string
  permissions: string[]
  tenant_id?: string
  is_system_role: boolean
  created_at: string
  updated_at: string
  user_count: number
}

export interface Permission {
  id: string
  name: string
  description: string
  resource: string
  action: string
  scope: 'global' | 'tenant' | 'user'
}

export interface CreateRoleRequest {
  name: string
  description: string
  permissions: string[]
  tenant_id?: string
}

export interface UpdateRoleRequest {
  name?: string
  description?: string
  permissions?: string[]
}

export interface RoleAssignment {
  user_id: string
  role_id: string
  assigned_by: string
  assigned_at: string
  expires_at?: string
}

// Roles API client
export class RolesApi {
  /**
   * List All Roles
   * GET /v1/roles
   */
  static async listRoles(params?: {
    page?: number
    page_size?: number
    tenant_scope?: boolean
    include_system_roles?: boolean
  }): Promise<PaginatedResponse<Role>> {
    return apiClient.getPaginated('/v1/roles', params)
  }

  /**
   * Get Role by ID
   * GET /v1/roles/{role_id}
   */
  static async getRole(roleId: string): Promise<ApiResponse<Role>> {
    return apiClient.get(`/v1/roles/${roleId}`)
  }

  /**
   * Create New Role
   * POST /v1/roles
   */
  static async createRole(roleData: CreateRoleRequest): Promise<ApiResponse<Role>> {
    return apiClient.post('/v1/roles', roleData)
  }

  /**
   * Update Role
   * PUT /v1/roles/{role_id}
   */
  static async updateRole(roleId: string, updates: UpdateRoleRequest): Promise<ApiResponse<Role>> {
    return apiClient.put(`/v1/roles/${roleId}`, updates)
  }

  /**
   * Delete Role
   * DELETE /v1/roles/{role_id}
   */
  static async deleteRole(roleId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/roles/${roleId}`)
  }

  /**
   * List All Permissions
   * GET /v1/permissions
   */
  static async listPermissions(params?: {
    resource?: string
    scope?: 'global' | 'tenant' | 'user'
  }): Promise<ApiResponse<Permission[]>> {
    return apiClient.get('/v1/permissions', { params })
  }

  /**
   * Get Role Assignments
   * GET /v1/roles/{role_id}/assignments
   */
  static async getRoleAssignments(roleId: string): Promise<ApiResponse<RoleAssignment[]>> {
    return apiClient.get(`/v1/roles/${roleId}/assignments`)
  }

  /**
   * Assign Role to User
   * POST /v1/roles/{role_id}/assign
   */
  static async assignRole(roleId: string, userId: string, expiresAt?: string): Promise<ApiResponse<RoleAssignment>> {
    return apiClient.post(`/v1/roles/${roleId}/assign`, {
      user_id: userId,
      expires_at: expiresAt
    })
  }

  /**
   * Unassign Role from User
   * DELETE /v1/roles/{role_id}/assign/{user_id}
   */
  static async unassignRole(roleId: string, userId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/roles/${roleId}/assign/${userId}`)
  }

  /**
   * Check User Permission
   * GET /v1/roles/check-permission
   */
  static async checkPermission(params: {
    user_id: string
    permission: string
    resource_id?: string
  }): Promise<ApiResponse<{ has_permission: boolean; source_role?: string }>> {
    return apiClient.get('/v1/roles/check-permission', { params })
  }

  /**
   * Get User Roles
   * GET /v1/users/{user_id}/roles
   */
  static async getUserRoles(userId: string): Promise<ApiResponse<Role[]>> {
    return apiClient.get(`/v1/users/${userId}/roles`)
  }

  /**
   * Get Role Templates
   * GET /v1/roles/templates
   */
  static async getRoleTemplates(): Promise<ApiResponse<Array<{
    name: string
    description: string
    permissions: string[]
    use_case: string
  }>>> {
    return apiClient.get('/v1/roles/templates')
  }

  /**
   * Create Role from Template
   * POST /v1/roles/from-template
   */
  static async createRoleFromTemplate(templateName: string, customizations?: {
    name?: string
    description?: string
    additional_permissions?: string[]
    removed_permissions?: string[]
  }): Promise<ApiResponse<Role>> {
    return apiClient.post('/v1/roles/from-template', {
      template_name: templateName,
      ...customizations
    })
  }

  /**
   * Clone Role
   * POST /v1/roles/{role_id}/clone
   */
  static async cloneRole(roleId: string, newName: string): Promise<ApiResponse<Role>> {
    return apiClient.post(`/v1/roles/${roleId}/clone`, { name: newName })
  }

  /**
   * Bulk Role Assignment
   * POST /v1/roles/bulk-assign
   */
  static async bulkAssignRoles(assignments: Array<{
    user_id: string
    role_id: string
    expires_at?: string
  }>): Promise<ApiResponse<{
    success_count: number
    error_count: number
    errors: Array<{ user_id: string; role_id: string; error: string }>
  }>> {
    return apiClient.post('/v1/roles/bulk-assign', { assignments })
  }
}

export default RolesApi