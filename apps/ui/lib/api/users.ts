/**
 * Users API Client
 * 15+ endpoints for comprehensive user management and administration
 * Based on: /docs/wiki/knowledge_base/devDocs/User-Router-API-Documentation.md
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// User types
export interface User {
  id: string
  email: string
  name: string
  status: 'active' | 'inactive' | 'pending' | 'suspended'
  created_at: string
  updated_at: string
  last_login_at?: string
  email_verified_at?: string
  roles?: UserRole[]
  tenant_id?: string
}

export interface UserRole {
  id: string
  name: string
  permissions: string[]
  tenant_id?: string
}

export interface CreateUserRequest {
  email: string
  name: string
  password: string
  status?: 'active' | 'inactive' | 'pending'
  roles?: string[]
}

export interface UpdateUserRequest {
  name?: string
  status?: 'active' | 'inactive' | 'pending' | 'suspended'
  email?: string
}

export interface UserSearchParams {
  q: string
  page?: number
  page_size?: number
  status?: string
  role?: string
}

export interface UserSearchResponse {
  users: User[]
  total_count: number
  page: number
  page_size: number
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ResetPasswordRequest {
  email: string
}

export interface AdminUser {
  id: string
  email: string
  name: string
  role: 'super_admin' | 'admin' | 'support_admin' | 'billing_admin'
  status: 'active' | 'inactive'
  created_at: string
  last_login_at?: string
  permissions: string[]
}

export interface CreateAdminUserRequest {
  email: string
  name: string
  password: string
  role: 'super_admin' | 'admin' | 'support_admin' | 'billing_admin'
}

export interface UserSession {
  id: string
  user_id: string
  created_at: string
  last_activity: string
  ip_address: string
  user_agent: string
  is_current: boolean
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system'
  timezone: string
  language: string
  notifications: {
    email: boolean
    push: boolean
    in_app: boolean
  }
  dashboard_settings: Record<string, any>
}

// Users API client
export class UsersApi {
  /**
   * Create New User
   * POST /v1/users
   */
  static async createUser(userData: CreateUserRequest): Promise<ApiResponse<User>> {
    return apiClient.post('/v1/users', userData)
  }

  /**
   * Search Users
   * GET /v1/users/search
   */
  static async searchUsers(params: UserSearchParams): Promise<ApiResponse<UserSearchResponse>> {
    return apiClient.get('/v1/users/search', { params })
  }

  /**
   * Get Current User Profile
   * GET /v1/users/me
   */
  static async getCurrentUser(): Promise<ApiResponse<User>> {
    return apiClient.get('/v1/users/me')
  }

  /**
   * Update Current User Profile
   * PUT /v1/users/me
   */
  static async updateCurrentUser(updates: UpdateUserRequest): Promise<ApiResponse<User>> {
    return apiClient.put('/v1/users/me', updates)
  }

  /**
   * Get User by ID
   * GET /v1/users/{user_id}
   */
  static async getUserById(userId: string): Promise<ApiResponse<User>> {
    return apiClient.get(`/v1/users/${userId}`)
  }

  /**
   * Update User by ID
   * PUT /v1/users/{user_id}
   */
  static async updateUser(userId: string, updates: UpdateUserRequest): Promise<ApiResponse<User>> {
    return apiClient.put(`/v1/users/${userId}`, updates)
  }

  /**
   * Delete User
   * DELETE /v1/users/{user_id}
   */
  static async deleteUser(userId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/users/${userId}`)
  }

  /**
   * Change Password
   * POST /v1/users/me/change-password
   */
  static async changePassword(passwordData: ChangePasswordRequest): Promise<ApiResponse<void>> {
    return apiClient.post('/v1/users/me/change-password', passwordData)
  }

  /**
   * Request Password Reset
   * POST /v1/users/reset-password
   */
  static async requestPasswordReset(resetData: ResetPasswordRequest): Promise<ApiResponse<void>> {
    return apiClient.post('/v1/users/reset-password', resetData)
  }

  /**
   * Verify Email
   * POST /v1/users/me/verify-email
   */
  static async verifyEmail(token: string): Promise<ApiResponse<void>> {
    return apiClient.post('/v1/users/me/verify-email', { token })
  }

  /**
   * Resend Email Verification
   * POST /v1/users/me/resend-verification
   */
  static async resendEmailVerification(): Promise<ApiResponse<void>> {
    return apiClient.post('/v1/users/me/resend-verification')
  }

  /**
   * Get User Sessions
   * GET /v1/users/me/sessions
   */
  static async getUserSessions(): Promise<ApiResponse<UserSession[]>> {
    return apiClient.get('/v1/users/me/sessions')
  }

  /**
   * Revoke User Session
   * DELETE /v1/users/me/sessions/{session_id}
   */
  static async revokeSession(sessionId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/users/me/sessions/${sessionId}`)
  }

  /**
   * Revoke All Sessions (except current)
   * DELETE /v1/users/me/sessions
   */
  static async revokeAllSessions(): Promise<ApiResponse<void>> {
    return apiClient.delete('/v1/users/me/sessions')
  }

  /**
   * Get User Preferences
   * GET /v1/users/me/preferences
   */
  static async getUserPreferences(): Promise<ApiResponse<UserPreferences>> {
    return apiClient.get('/v1/users/me/preferences')
  }

  /**
   * Update User Preferences
   * PUT /v1/users/me/preferences
   */
  static async updateUserPreferences(preferences: Partial<UserPreferences>): Promise<ApiResponse<UserPreferences>> {
    return apiClient.put('/v1/users/me/preferences', preferences)
  }

  /**
   * Get User Roles
   * GET /v1/users/{user_id}/roles
   */
  static async getUserRoles(userId: string): Promise<ApiResponse<UserRole[]>> {
    return apiClient.get(`/v1/users/${userId}/roles`)
  }

  /**
   * Assign Role to User
   * POST /v1/users/{user_id}/roles
   */
  static async assignRole(userId: string, roleId: string): Promise<ApiResponse<void>> {
    return apiClient.post(`/v1/users/${userId}/roles`, { role_id: roleId })
  }

  /**
   * Remove Role from User
   * DELETE /v1/users/{user_id}/roles/{role_id}
   */
  static async removeRole(userId: string, roleId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/users/${userId}/roles/${roleId}`)
  }

  /**
   * List All Users (Admin)
   * GET /v1/users
   */
  static async listUsers(params?: {
    page?: number
    page_size?: number
    status?: string
    tenant_id?: string
  }): Promise<PaginatedResponse<User>> {
    return apiClient.getPaginated('/v1/users', params)
  }

  /**
   * Bulk User Operations (Admin)
   * POST /v1/users/bulk
   */
  static async bulkUserOperation(operation: {
    action: 'activate' | 'deactivate' | 'delete' | 'update_role'
    user_ids: string[]
    data?: Record<string, any>
  }): Promise<ApiResponse<{
    success_count: number
    error_count: number
    errors: Array<{ user_id: string; error: string }>
  }>> {
    return apiClient.post('/v1/users/bulk', operation)
  }

  // Platform Admin User Management
  /**
   * List Platform Admin Users
   * GET /v1/admin/users
   */
  static async listAdminUsers(): Promise<ApiResponse<AdminUser[]>> {
    return apiClient.get('/v1/admin/users')
  }

  /**
   * Create Platform Admin User
   * POST /v1/admin/users
   */
  static async createAdminUser(adminData: CreateAdminUserRequest): Promise<ApiResponse<AdminUser>> {
    return apiClient.post('/v1/admin/users', adminData)
  }

  /**
   * Get Platform Admin User
   * GET /v1/admin/users/{user_id}
   */
  static async getAdminUser(userId: string): Promise<ApiResponse<AdminUser>> {
    return apiClient.get(`/v1/admin/users/${userId}`)
  }

  /**
   * Update Platform Admin User
   * PUT /v1/admin/users/{user_id}
   */
  static async updateAdminUser(userId: string, updates: Partial<AdminUser>): Promise<ApiResponse<AdminUser>> {
    return apiClient.put(`/v1/admin/users/${userId}`, updates)
  }

  /**
   * Delete Platform Admin User
   * DELETE /v1/admin/users/{user_id}
   */
  static async deleteAdminUser(userId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/admin/users/${userId}`)
  }

  // Utility methods
  /**
   * Check if User has Permission
   */
  static async checkUserPermission(userId: string, permission: string): Promise<ApiResponse<{ has_permission: boolean }>> {
    return apiClient.get(`/v1/users/${userId}/permissions/${permission}`)
  }

  /**
   * Get User Activity Log
   * GET /v1/users/{user_id}/activity
   */
  static async getUserActivity(userId: string, params?: {
    limit?: number
    offset?: number
    action_type?: string
  }): Promise<ApiResponse<Array<{
    id: string
    action: string
    timestamp: string
    ip_address: string
    user_agent: string
    metadata: Record<string, any>
  }>>> {
    return apiClient.get(`/v1/users/${userId}/activity`, { params })
  }

  /**
   * Export Users Data
   * GET /v1/users/export
   */
  static async exportUsers(params: {
    format: 'csv' | 'json'
    filters?: {
      status?: string
      tenant_id?: string
      created_after?: string
      created_before?: string
    }
  }): Promise<ApiResponse<{
    download_url: string
    expires_at: string
    record_count: number
  }>> {
    return apiClient.get('/v1/users/export', { params })
  }
}

export default UsersApi