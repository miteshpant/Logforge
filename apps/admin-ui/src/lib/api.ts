import { authService } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'

export async function apiRequest(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE_URL}${endpoint}`
  const token = authService.getToken();
  
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'X-Customer-ID': 'platform', // Admin UI operates in platform context
    ...(token && { Authorization: `Bearer ${token}` }),
  }

  const defaultOptions: RequestInit = {
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
    ...options,
  }

  try {
    console.log(`🔧 DEBUG: Making API request to: ${url}`)
    console.log(`🔧 DEBUG: Request method: ${options.method || 'GET'}`)
    console.log(`🔧 DEBUG: Token present: ${token ? 'YES' : 'NO'}`)
    console.log(`🔧 DEBUG: Token preview: ${token ? token.substring(0, 50) + '...' : 'N/A'}`)
    console.log(`🔧 DEBUG: Default headers:`, defaultHeaders)
    console.log(`🔧 DEBUG: Options headers:`, options.headers)
    console.log(`🔧 DEBUG: Final merged headers:`, defaultOptions.headers)
    console.log(`🔧 DEBUG: Request body:`, options.body)
    
    const response = await fetch(url, defaultOptions)
    
    console.log(`🔧 DEBUG: Response status: ${response.status}`)
    console.log(`🔧 DEBUG: Response headers:`, Object.fromEntries(response.headers.entries()))
    
    if (!response.ok) {
      const errorData = await response.text()
      console.error(`🔧 DEBUG: API Error (${response.status}):`, errorData)
      throw new Error(`HTTP ${response.status}: ${errorData}`)
    }

    const data = await response.json()
    console.log(`🔧 DEBUG: API Response from ${endpoint}:`, data)
    return data
  } catch (error: any) {
    console.error(`🔧 DEBUG: API request failed for ${url}:`, error)
    
    // Check if it's a CORS error
    if (error.message && error.message.includes('CORS')) {
      console.error(`🔧 DEBUG: CORS Error detected - this might be a preflight request failure`)
      console.error(`🔧 DEBUG: Try refreshing the page or check if the backend is running`)
    }
    
    // Check if it's a network error
    if (error.message && error.message.includes('Failed to fetch')) {
      console.error(`🔧 DEBUG: Network error - could be CORS, network issues, or server down`)
    }
    
    throw error
  }
}

export async function fetchTenants() {
  return apiRequest('/v1/tenants')
}

export async function fetchTenant(tenantId: string) {
  return apiRequest(`/v1/tenants/${tenantId}`)
}

export async function fetchTenantUsage(tenantId: string) {
  return apiRequest(`/v1/tenants/${tenantId}/usage`)
}

export async function createTenant(tenantData: any) {
  return apiRequest('/v1/tenants', {
    method: 'POST',
    body: JSON.stringify(tenantData),
  })
}

export async function updateTenant(tenantId: string, updateData: any) {
  return apiRequest(`/v1/tenants/${tenantId}`, {
    method: 'PUT',
    body: JSON.stringify(updateData),
  })
}

export async function fetchTenantStats() {
  return apiRequest('/v1/tenants/stats')
}

// Usage Analytics API Functions
export async function fetchPlatformUsageStats() {
  return apiRequest('/v1/analytics/usage-trends')
}


export async function fetchCurrentUsage(tenantId: string) {
  return apiRequest(`/v1/usage/current/${tenantId}`)
}


/** Bill one tenant for a month (YYYY-MM, default the current one); idempotent. */
export async function generateInvoice(tenantId: string, month?: string) {
  return apiRequest(`/v1/tenants/${tenantId}/billing/generate`, {
    method: 'POST',
    body: JSON.stringify({ billing_period: month || 'current', include_usage_details: false }),
  })
}

/** Bills across tenants (newest first) and their totals per currency. */
export interface AdminBill {
  id: string
  tenant_id: string
  tenant_name: string
  billing_period: string
  subscription_tier: string
  total_amount: number
  currency: string
  status: string
  generated_at: string
  due_date: string | null
  paid_at: string | null
}

export async function fetchBills(period?: string): Promise<{ bills: AdminBill[]; totals: Record<string, number> }> {
  return apiRequest(`/v1/admin/billing/bills?limit=2000${period ? `&period=${period}` : ''}`)
}

/** Bill every active tenant for a month, server-side; tenants already billed keep their bill. */
export interface BillingRunResult {
  billing_period: string
  tenants: number
  generated: number
  already_billed: number
  failed: { tenant_id: string; tenant_name: string; error: string }[]
}

export async function runBilling(billingPeriod: string): Promise<BillingRunResult> {
  return apiRequest('/v1/admin/billing/generate', { method: 'POST', body: JSON.stringify({ billing_period: billingPeriod }) })
}

export interface FeatureRate {
  feature_name: string
  pricing_model: string
  base_rate: number
  tier_rates: Record<string, number>
  currency: string
  effective_date: string
  description: string
}

export async function fetchRates(): Promise<{ rates: FeatureRate[] }> {
  return apiRequest('/v1/admin/rates')
}

export async function updateRate(featureName: string, baseRate: number) {
  return apiRequest(`/v1/admin/rates/${encodeURIComponent(featureName)}`, {
    method: 'PUT', body: JSON.stringify({ base_rate: baseRate }),
  })
}

export interface FeatureMatrix {
  tiers: string[]
  bundles: Record<string, string[]>
  categories: { name: string; features: { name: string; tiers: Record<string, boolean> }[] }[]
}

export async function fetchFeatureMatrix(): Promise<FeatureMatrix> {
  return apiRequest('/v1/admin/features/matrix')
}

export interface SupportTicket {
  id: string
  tenant_id: string
  tenant_name?: string
  subject: string
  status: 'open' | 'answered' | 'closed'
  priority: 'low' | 'normal' | 'high' | 'urgent'
  created_by: string
  created_at: string
  updated_at: string
  messages: { author: string; from: 'customer' | 'support'; text: string; at: string }[]
}

export async function fetchTickets(status?: string): Promise<{ tickets: SupportTicket[]; counts: Record<string, number> }> {
  return apiRequest(`/v1/admin/support/tickets${status ? `?status=${status}` : ''}`)
}

export async function replyTicket(id: string, text: string): Promise<SupportTicket> {
  return apiRequest(`/v1/admin/support/tickets/${id}/messages`, { method: 'POST', body: JSON.stringify({ text }) })
}

export async function updateTicket(id: string, change: { status?: string; priority?: string }): Promise<SupportTicket> {
  return apiRequest(`/v1/admin/support/tickets/${id}`, { method: 'PUT', body: JSON.stringify(change) })
}

export async function exportUsageData(tenantId: string, format: string = 'csv') {
  return apiRequest(`/v1/usage/export/${tenantId}?format=${format}`)
}



/** Save a bill as PDF (GET /v1/admin/billing/bills/{id}/pdf). */
export async function downloadBill(billId: string, filename?: string): Promise<void> {
  const token = authService.getToken()
  const response = await fetch(`${API_BASE_URL}/v1/admin/billing/bills/${encodeURIComponent(billId)}/pdf`, {
    headers: { 'X-Customer-ID': 'platform', ...(token && { Authorization: `Bearer ${token}` }) },
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`)
  const url = window.URL.createObjectURL(await response.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `bill-${billId}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

// Admin Activity Log API Functions
// LF-263: the audit action vocabulary, served by the API.
//
// The console used to carry its own copy of the ClickHouse `Enum8` ordinal
// mapping, so inserting a value -- the ordinary way an enum grows -- silently
// relabelled every historical event here with nothing failing anywhere.
export interface AuditActionType {
  name: string
  ordinal: number
  label: string
  risk: string
}

export async function fetchAuditActionTypes(): Promise<{
  action_types: AuditActionType[]
  risk_levels: string[]
}> {
  return apiRequest('/v1/enterprise/audit-logs/action-types')
}

export async function fetchAdminAuditLogs(params: {
  start_time?: string
  end_time?: string
  user_id?: string
  action_types?: string
  risk_level?: string
  page?: number
  page_size?: number
} = {}) {
  const queryParams = new URLSearchParams()
  
  // Add parameters if provided
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value))
    }
  })

  const url = `/v1/enterprise/audit-logs${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return apiRequest(url)
}

// Control-plane audit (LF-262)
//
// Distinct from `fetchAdminAuditLogs`, which reads the HTTP-REQUEST stream:
// method, path, status, IP, byte count. These are SEMANTIC events -- a verb, a
// target, the state before and after, and the reason the operator gave.
export interface ControlPlaneEvent {
  event_id: string
  occurred_at: string
  action: string
  actor: { user_id: string; email: string; roles: string[]; ip: string }
  target_type: string
  target_id: string
  customer_id: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  changed_fields: string[]
  reason: string
  outcome: string
  error_message: string
}

export async function fetchControlPlaneEvents(params: {
  action_prefix?: string
  target_id?: string
  start_date?: string
  end_date?: string
  limit?: number
} = {}) {
  const queryParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value))
    }
  })
  const query = queryParams.toString()
  return apiRequest(`/v1/admin/audit/control-plane${query ? '?' + query : ''}`)
}

// Admin User Management API Functions
export async function fetchAdminUsers(page: number = 1, pageSize: number = 50) {
  return apiRequest(`/v1/admin/users?page=${page}&page_size=${pageSize}`)
}

export async function createAdminUser(userData: any) {
  return apiRequest('/v1/admin/users', {
    method: 'POST',
    body: JSON.stringify(userData),
  })
}

export async function getAdminUser(userId: string) {
  return apiRequest(`/v1/admin/users/${userId}`)
}

export async function updateAdminUser(userId: string, updateData: any) {
  return apiRequest(`/v1/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(updateData),
  })
}

/**
 * Incident-response actions (LF-265).
 *
 * The console's "Security Actions" buttons had no handler at all, so an operator
 * responding to a suspected compromise clicked "Revoke Sessions", saw no error,
 * and believed the attacker was locked out.
 */
export interface RevokeSessionsResult {
  user_id: string
  revoked_count: number
  message: string
}

export async function revokeUserSessions(userId: string): Promise<RevokeSessionsResult> {
  return apiRequest(`/v1/admin/users/${userId}/sessions/revoke`, { method: 'POST' })
}

export interface PasswordResetResult {
  user_id: string
  email: string
  reset_token: string
  expires_at: string
  delivery: string
  message: string
}

export async function issuePasswordReset(userId: string): Promise<PasswordResetResult> {
  return apiRequest(`/v1/admin/users/${userId}/password-reset`, { method: 'POST' })
}

export async function deleteAdminUser(userId: string) {
  return apiRequest(`/v1/admin/users/${userId}`, {
    method: 'DELETE',
  })
}

// Regular User Management API Functions (for tenant users)
export async function createUser(userData: any) {
  return apiRequest('/v1/users', {
    method: 'POST',
    body: JSON.stringify(userData),
  })
}

// Role Management API Functions
export async function assignUserRole(userId: string, roleData: any) {
  return apiRequest(`/v1/users/${userId}/roles`, {
    method: 'POST',
    body: JSON.stringify(roleData),
  })
}

export async function getUserRoles(userId: string, tenantId?: string) {
  const queryParam = tenantId ? `?tenant_id=${tenantId}` : ''
  return apiRequest(`/v1/users/${userId}/roles${queryParam}`)
}

// Enhanced tenant creation with admin user setup
export async function createTenantWithAdmin(tenantData: any) {
  console.log('🏢 Creating tenant with admin user workflow...')
  
  try {
    // Step 1: Create the tenant
    console.log('📝 Step 1: Creating tenant...', tenantData)
    const tenant = await createTenant(tenantData)
    console.log('✅ Tenant created:', tenant)
    
    // Step 2: Create the admin user using the tenant's admin contact info
    const adminUserData = {
      email: tenantData.primary_contact_email,
      name: tenantData.primary_contact_name,
      password: generateSecurePassword(), // Generate a secure temporary password
      status: 'active'
    }
    
    console.log('👤 Step 2: Creating admin user...', { ...adminUserData, password: '[REDACTED]' })
    const user = await createUser(adminUserData)
    console.log('✅ Admin user created:', user)
    
    // Step 3: Assign tenant admin role to the user
    const roleAssignment = {
      tenant_id: tenant.tenant_id || tenant.id,
      role: 'tenant_admin'
    }
    console.log('🔐 Step 3: Assigning tenant admin role...', roleAssignment)
    const role = await assignUserRole(user.id, roleAssignment)
    console.log('✅ Role assigned:', role)
    
    return {
      tenant,
      user,
      role,
      tempPassword: adminUserData.password // Return temp password for notification
    }
  } catch (error) {
    console.error('❌ Failed in tenant creation workflow:', error)
    throw error
  }
}

// Helper function to generate secure temporary password
function generateSecurePassword(): string {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
  let password = ''
  
  // Ensure at least one of each required character type
  password += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[Math.floor(Math.random() * 26)] // Uppercase
  password += 'abcdefghijklmnopqrstuvwxyz'[Math.floor(Math.random() * 26)] // Lowercase  
  password += '0123456789'[Math.floor(Math.random() * 10)] // Number
  password += '!@#$%^&*'[Math.floor(Math.random() * 8)] // Special char
  
  // Fill remaining length (minimum 12 chars total)
  for (let i = 4; i < 16; i++) {
    password += charset[Math.floor(Math.random() * charset.length)]
  }
  
  // Shuffle the password
  return password.split('').sort(() => Math.random() - 0.5).join('')
}