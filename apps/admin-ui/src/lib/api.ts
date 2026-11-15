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

/**
 * Rate card -- the single source of truth for pricing (LF-257).
 *
 * Pricing is base fee + metered usage (per GB ingested, per GB/month stored,
 * per 1000 queries and API calls). The console previously carried four hardcoded
 * price tables that disagreed with each other and with the server, and rendered
 * a flat per-tier figure as "Monthly Cost" -- which misstates the model as well
 * as the number.
 */
export interface RateCardTier {
  base_fee: number
  description?: string
  discount_percent?: number
}

export interface RateCard {
  pricing_version: string
  currency: string
  last_updated?: string
  tiers: Record<string, RateCardTier>
  feature_pricing?: Record<string, { unit: string; base_price: number; description?: string }>
  minimum_charge?: number
}

export async function fetchRateCard(): Promise<RateCard> {
  return apiRequest('/v1/billing/rate-card')
}

/**
 * Format a tier's base fee for display.
 *
 * Returns null when the rate card is unavailable or the tier is unknown, so
 * callers render an explicit "Unavailable" rather than inventing a number.
 * Never fall back to a literal price: a wrong price reaches a customer.
 */
export function formatBaseFee(rateCard: RateCard | null, tier: string | undefined): string | null {
  if (!rateCard || !tier) return null
  const entry = rateCard.tiers?.[tier.toLowerCase()]
  if (!entry || typeof entry.base_fee !== 'number') return null
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: rateCard.currency || 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(entry.base_fee)
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


export async function generateInvoice(tenantId: string, month?: string) {
  const queryParam = month ? `?month=${month}` : ''
  return apiRequest(`/v1/billing/generate/${tenantId}${queryParam}`, {
    method: 'POST',
  })
}

/**
 * Billing runs (LF-258).
 *
 * "Generate All Bills" used to be a `Promise.all` in the browser over whatever
 * tenants were on the page -- 50 of them, because `fetchTenants()` passed no
 * pagination argument and the API defaults to `page_size=50`. The month-end run
 * billed the first 50 and reported "Generated 50/50 bills successfully!".
 *
 * The browser now STARTS a run and watches it. Enumeration, concurrency and the
 * per-tenant record all live server-side, so closing the tab no longer aborts
 * month-end close.
 */

export interface BillingRun {
  run_id: string
  billing_period: string
  status: 'running' | 'completed' | 'completed_with_failures' | 'failed'
  total_tenants: number
  succeeded: number
  already_existed: number
  failed: number
  actor_email?: string
  reason?: string
  started_at: string
  finished_at: string | null
  error_message?: string
  /** True when a run with this idempotency key already existed. */
  reused?: boolean
}

export interface BillingRunItem {
  tenant_id: string
  tenant_name: string
  outcome: 'succeeded' | 'already_existed' | 'failed'
  bill_id: string
  total_amount: number
  currency: string
  error_message: string
}

export interface BillingRunDetail {
  run: BillingRun
  items?: BillingRunItem[]
  /** Stated by the server so under-coverage is arithmetic, not observation. */
  coverage: {
    total_tenants: number
    accounted_for: number
    unaccounted: number
    complete: boolean
  }
}

export async function startBillingRun(params: {
  billing_period: string
  reason: string
  idempotency_key?: string
}): Promise<BillingRun> {
  return apiRequest('/v1/admin/billing/runs', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function fetchBillingRun(
  runId: string,
  outcome?: 'succeeded' | 'already_existed' | 'failed'
): Promise<BillingRunDetail> {
  const query = outcome ? `?outcome=${encodeURIComponent(outcome)}` : ''
  return apiRequest(`/v1/admin/billing/runs/${runId}${query}`)
}

export async function fetchBillingRuns(limit = 20): Promise<{ runs: BillingRun[] }> {
  return apiRequest(`/v1/admin/billing/runs?limit=${limit}`)
}

export async function getBillingEstimate(tenantId: string) {
  return apiRequest(`/v1/billing/estimate/${tenantId}`)
}

export async function exportUsageData(tenantId: string, format: string = 'csv') {
  return apiRequest(`/v1/usage/export/${tenantId}?format=${format}`)
}



export async function downloadBillPDF(billId: string) {
  // This returns a blob, handled differently in the component
  return fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'}/v1/billing/bills/${billId}/pdf`)
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