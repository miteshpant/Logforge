/**
 * Logforge API Client
 *
 * Centralized API client for all Logforge backend services
 * Provides type-safe HTTP methods with automatic error handling
 */

// API Configuration
const API_CONFIG = {
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080',
  timeout: 30000, // 30 seconds default timeout
  headers: {
    'Content-Type': 'application/json',
  },
}

// Response types
export interface ApiResponse<T = any> {
  data?: T
  error?: string
  message?: string
  success?: boolean
  [key: string]: any
}

/**
 * Human-readable message from an API error body.
 *
 * FastAPI's HTTPException responds with `{"detail": "..."}` and validation
 * errors with `{"detail": [{"msg": ...}, ...]}`; some handlers use `error` or
 * `message`. Reading only error/message turned every server explanation into
 * a bare "HTTP 4xx" (and the login form into a generic "Login failed").
 */
export function describeApiError(data: any): string | undefined {
  if (!data || typeof data !== 'object') return typeof data === 'string' && data ? data : undefined
  if (typeof data.detail === 'string' && data.detail) return data.detail
  if (Array.isArray(data.detail) && data.detail.length) {
    return data.detail
      .map((d: any) => (d?.loc ? `${d.loc.filter((x: any) => x !== 'body').join('.')}: ` : '') + (d?.msg ?? ''))
      .join('; ')
  }
  if (typeof data.message === 'string' && data.message) return data.message
  if (typeof data.error === 'string' && data.error) return data.error
  return undefined
}

/**
 * Main API Client Class
 */
class ApiClient {
  private baseURL: string
  private defaultHeaders: Record<string, string>
  private timeout: number
  // LF-015: single in-flight refresh shared by concurrent 401s so a burst of
  // expired requests performs exactly one token rotation.
  private refreshPromise: Promise<boolean> | null = null

  constructor() {
    this.baseURL = API_CONFIG.baseURL
    this.defaultHeaders = API_CONFIG.headers
    this.timeout = API_CONFIG.timeout
  }

  /**
   * Restore auth headers from localStorage if they are not set yet.
   *
   * On a full page load React runs child effects before parent effects, so a
   * page's data-fetching effect fires before AuthContext has restored the
   * session. Those first requests went out with no Authorization or
   * X-Customer-ID header, got 401s, and triggered a token refresh: a burst of
   * avoidable failures on every reload or deep link. Hydrating here makes the
   * client usable as soon as it is called. It never overrides headers that
   * were set explicitly (e.g. by setAuth after login or a tenant switch).
   */
  private hydrateAuthFromStorage() {
    if (typeof window === 'undefined') return
    try {
      if (!this.defaultHeaders['Authorization']) {
        const token = localStorage.getItem('auth_token')
        if (token) this.setAuthToken(token)
      }
      if (!this.defaultHeaders['X-Customer-ID']) {
        const tenantId = localStorage.getItem('tenant_id')
        if (tenantId) this.setCustomerId(tenantId)
      }
      if (!this.defaultHeaders['X-User-Role']) {
        const userRole = localStorage.getItem('user_role')
        if (userRole) this.setHeader('X-User-Role', userRole)
      }
    } catch {
      // Storage can be unavailable (privacy mode); requests proceed unauthenticated.
    }
  }

  /**
   * Core request method with error handling
   */
  async request<T = any>(
    endpoint: string,
    options: RequestInit = {},
    isRetryAfterRefresh: boolean = false
  ): Promise<ApiResponse<T>> {
    this.hydrateAuthFromStorage()
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`

    const config: RequestInit = {
      ...options,
      headers: {
        ...this.defaultHeaders,
        ...options.headers,
      },
    }

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), this.timeout)

      const response = await fetch(url, {
        ...config,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      // Handle non-JSON responses
      const contentType = response.headers.get('content-type')
      let data: any

      if (contentType?.includes('application/json')) {
        data = await response.json()
      } else {
        data = await response.text()
      }

      // Handle error responses
      if (!response.ok) {
        // LF-015: on 401, attempt one transparent token refresh and retry.
        if (
          response.status === 401 &&
          !isRetryAfterRefresh &&
          !this.isAuthEndpoint(endpoint)
        ) {
          const refreshed = await this.tryRefreshAccessToken()
          if (refreshed) {
            return this.request<T>(endpoint, options, true)
          }
        }

        return {
          success: false,
          error: describeApiError(data) || `HTTP ${response.status}: ${response.statusText}`,
          data: undefined,
        }
      }

      // Normalize response format
      // Some endpoints return { data: {...} }, others return data directly
      if (data && typeof data === 'object' && 'data' in data) {
        return {
          success: true,
          ...data,
        }
      }

      return {
        success: true,
        data,
      }
    } catch (error: any) {
      console.error('API Request Error:', error)

      if (error.name === 'AbortError') {
        return {
          success: false,
          error: 'Request timeout',
        }
      }

      return {
        success: false,
        error: error.message || 'Network error',
      }
    }
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string, params?: Record<string, any>): Promise<ApiResponse<T>> {
    let url = endpoint

    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value))
        }
      })

      const queryString = searchParams.toString()
      if (queryString) {
        url = `${endpoint}${endpoint.includes('?') ? '&' : '?'}${queryString}`
      }
    }

    return this.request<T>(url, { method: 'GET' })
  }

  /**
   * POST request
   */
  async post<T = any>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * PUT request
   */
  async put<T = any>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  /**
   * PATCH request
   */
  async patch<T = any>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  /**
   * Set custom header (e.g., for authentication)
   */
  setHeader(key: string, value: string) {
    this.defaultHeaders[key] = value
  }

  /**
   * Remove custom header
   */
  removeHeader(key: string) {
    delete this.defaultHeaders[key]
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string) {
    this.setHeader('Authorization', `Bearer ${token}`)
  }

  /**
   * Clear authentication token
   */
  clearAuthToken() {
    this.removeHeader('Authorization')
  }

  /**
   * Get SSE stream connection
   * Returns a cleanup function to close the connection
   */
  async getStream(
    endpoint: string,
    onData: (data: any) => void,
    onError?: (error: Error) => void
  ): Promise<() => void> {
    this.hydrateAuthFromStorage()
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`

    // Build URL with auth params for SSE (EventSource can't send headers)
    const urlWithAuth = new URL(url)

    // Add customer_id
    const customerId = this.defaultHeaders['X-Customer-ID']
    if (customerId) {
      urlWithAuth.searchParams.set('customer_id', customerId)
    }

    // Add auth token for SSE authentication
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token')
      if (token) {
        urlWithAuth.searchParams.set('token', token)
      }
    }

    const eventSource = new EventSource(urlWithAuth.toString())

    // Handler for parsing and forwarding events
    const handleEvent = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        onData(data)
      } catch (e) {
        // If not JSON, pass raw data
        onData(event.data)
      }
    }

    // Listen for generic messages (event: message or no event type)
    eventSource.onmessage = handleEvent

    // Listen for specific named event types used by the streaming API
    // The server sends events like "event: alert_event", "event: security_event", etc.
    const namedEventTypes = [
      'alert_event',
      'security_event',
      'traces_event',    // Note: backend sends 'traces_event' (plural)
      'metrics_event',   // Note: backend sends 'metrics_event' (plural)
      'anomaly_event',
      'usage',
      'ai_insights',
      'connected',
      'heartbeat',
      'error',
      'shutdown',
      'keepalive'
    ]

    namedEventTypes.forEach(eventType => {
      eventSource.addEventListener(eventType, handleEvent as EventListener)
    })

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
      if (onError) {
        onError(new Error('Stream connection error'))
      }
    }

    // Return cleanup function
    return () => {
      // Remove all event listeners before closing
      namedEventTypes.forEach(eventType => {
        eventSource.removeEventListener(eventType, handleEvent as EventListener)
      })
      eventSource.close()
    }
  }

  /**
   * True for auth endpoints that must never trigger a refresh-retry loop.
   */
  private isAuthEndpoint(endpoint: string): boolean {
    return (
      endpoint.includes('/v1/auth/login') ||
      endpoint.includes('/v1/auth/refresh') ||
      endpoint.includes('/v1/auth/logout')
    )
  }

  /**
   * LF-015: exchange the stored refresh token for a new access token.
   * Returns true when the session was renewed. Rotation: the server
   * revokes the presented refresh token and issues a replacement.
   */
  private async tryRefreshAccessToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken()
    if (!refreshToken) {
      return false
    }

    if (!this.refreshPromise) {
      this.refreshPromise = (async () => {
        try {
          const response = await fetch(`${this.baseURL}/v1/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          })

          if (!response.ok) {
            // Refresh token expired/revoked: clear it so we stop retrying.
            this.clearRefreshToken()
            return false
          }

          const data = await response.json()
          if (!data?.access_token) {
            return false
          }

          // Persist the renewed access token under the same keys the rest
          // of the app reads, and update live headers.
          if (typeof window !== 'undefined') {
            localStorage.setItem('auth_token', data.access_token)
          }
          this.setAuthToken(data.access_token)

          if (data.refresh_token) {
            this.setRefreshToken(data.refresh_token)
          }

          return true
        } catch (error) {
          console.error('Token refresh failed:', error)
          return false
        } finally {
          this.refreshPromise = null
        }
      })()
    }

    return this.refreshPromise
  }

  /**
   * Store the rotating refresh token (LF-015).
   */
  setRefreshToken(refreshToken: string) {
    if (typeof window !== 'undefined') {
      localStorage.setItem('refresh_token', refreshToken)
    }
  }

  /**
   * Read the stored refresh token, if any.
   */
  getRefreshToken(): string | null {
    if (typeof window === 'undefined') {
      return null
    }
    return localStorage.getItem('refresh_token')
  }

  /**
   * Remove the stored refresh token.
   */
  clearRefreshToken() {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('refresh_token')
    }
  }

  /**
   * Set customer/tenant ID header
   */
  setCustomerId(customerId: string) {
    this.setHeader('X-Customer-ID', customerId)
  }

  /**
   * Set authentication context (token + tenant + role)
   */
  setAuth(token: string, tenantId: string, userRole?: string) {
    // Store in localStorage for persistence
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token)
      localStorage.setItem('tenant_id', tenantId)
      if (userRole) {
        localStorage.setItem('user_role', userRole)
      }
    }

    // Set headers
    this.setAuthToken(token)
    this.setCustomerId(tenantId)
    if (userRole) {
      this.setHeader('X-User-Role', userRole)
    }
  }

  /**
   * Get current authentication context
   */
  getAuthContext(): {
    isAuthenticated: boolean
    token: string | null
    tenantId: string | null
    userRole: string | null
  } {
    if (typeof window === 'undefined') {
      return {
        isAuthenticated: false,
        token: null,
        tenantId: null,
        userRole: null,
      }
    }

    const token = localStorage.getItem('auth_token')
    const tenantId = localStorage.getItem('tenant_id')
    const userRole = localStorage.getItem('user_role')

    return {
      isAuthenticated: !!token,
      token,
      tenantId,
      userRole,
    }
  }

  /**
   * Logout - clear all authentication state
   */
  logout() {
    // Clear localStorage
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('tenant_id')
      localStorage.removeItem('user_role')
      localStorage.removeItem('refresh_token')
    }

    // Clear headers
    this.clearAuthToken()
    this.removeHeader('X-Customer-ID')
    this.removeHeader('X-User-Role')
  }
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export class for testing/advanced usage
export { ApiClient }

// Default export
export default apiClient
