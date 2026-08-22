/**
 * Comprehensive API Client for Logforge Customer UI
 * Integrates with 170+ backend endpoints with enterprise-grade features
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import Cookies from 'js-cookie'

// Base API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:7080'
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:7080'

// Authentication tokens
const AUTH_TOKEN_KEY = 'logforge_auth_token'
const TENANT_ID_KEY = 'logforge_tenant_id'
const REFRESH_TOKEN_KEY = 'logforge_refresh_token'

// API Response types
export interface ApiResponse<T = any> {
  data: T
  success: boolean
  message?: string
  error?: string
  timestamp?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  hasNext: boolean
  hasPrev: boolean
}

// Backend-specific paginated response (actual format from backend)
export interface BackendPaginatedResponse<T> {
  [key: string]: T[] | number | any // The first property is usually the data array (e.g., "alerts", "dashboards", etc.)
  total: number
  limit: number
  offset: number
}

// Authentication context
export interface AuthContext {
  token: string | null
  tenantId: string | null
  userId: string | null
  roles: string[]
  isAuthenticated: boolean
}

// Error type (LF-014): a real class, not an interface, so `throw new
// ApiError(...)` works at runtime and callers can use `instanceof ApiError`.
// The shape (message/code/status/details) is preserved for structural
// consumers that only read fields.
export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
    public details?: any
  ) {
    super(message)
    this.name = 'ApiError'
    // Maintain prototype chain when targeting ES5
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

class LogforgeApiClient {
  private client: AxiosInstance
  private tenantId: string | null = null
  private authToken: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
      paramsSerializer: {
        serialize: (params) => {
          // Custom serialization to handle arrays without [] brackets
          const searchParams = new URLSearchParams()
          Object.keys(params).forEach(key => {
            const value = params[key]
            if (Array.isArray(value)) {
              // For arrays, use the first value without brackets
              if (value.length > 0) {
                searchParams.append(key, value[0])
              }
            } else if (value !== undefined && value !== null) {
              searchParams.append(key, value.toString())
            }
          })
          return searchParams.toString()
        }
      }
    })

    // Initialize from stored credentials
    this.initializeAuth()

    // Request interceptor for authentication
    this.client.interceptors.request.use(
      (config) => {
        // Add authentication token
        if (this.authToken) {
          config.headers.Authorization = `Bearer ${this.authToken}`
        }

        // Add tenant context
        if (this.tenantId) {
          config.headers['X-Customer-ID'] = this.tenantId
        }

        // Add request ID for tracing
        config.headers['X-Request-ID'] = this.generateRequestId()

        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error) => {
        const originalRequest = error.config

        // Handle 401 Unauthorized - attempt token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true
          
          try {
            await this.refreshToken()
            return this.client(originalRequest)
          } catch (refreshError) {
            this.logout()
            throw new ApiError('Session expired. Please log in again.', 'AUTH_EXPIRED', 401)
          }
        }

        // Handle other errors: throw the same ApiError class so all
        // failures are instanceof-checkable (LF-014).
        throw new ApiError(
          error.response?.data?.message || error.message || 'An error occurred',
          error.response?.data?.code || 'UNKNOWN_ERROR',
          error.response?.status || 500,
          error.response?.data?.details
        )
      }
    )
  }

  private initializeAuth(): void {
    if (typeof window !== 'undefined') {
      this.authToken = Cookies.get(AUTH_TOKEN_KEY) || null
      this.tenantId = Cookies.get(TENANT_ID_KEY) || null
    }
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  private async refreshToken(): Promise<void> {
    const refreshToken = Cookies.get(REFRESH_TOKEN_KEY)
    if (!refreshToken) {
      throw new Error('No refresh token available')
    }

    const response = await axios.post(`${API_BASE_URL}/v1/auth/refresh`, {
      refresh_token: refreshToken,
    })

    const { access_token, refresh_token: newRefreshToken } = response.data
    
    this.setAuth(access_token, this.tenantId!, newRefreshToken)
  }

  // Authentication methods
  public setAuth(token: string, tenantId: string, refreshToken?: string): void {
    this.authToken = token
    this.tenantId = tenantId

    if (typeof window !== 'undefined') {
      // ENH-018 (partial hardening).
      //
      // `Secure` was previously conditional on the CURRENT page protocol, so a
      // deployment served over plain HTTP silently sent bearer tokens in the
      // clear. It is now off only on localhost, where HTTPS is impractical for
      // development; every other origin gets Secure unconditionally.
      const isLocalhost =
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        window.location.hostname === '[::1]'
      const secure = !isLocalhost

      // KNOWN LIMITATION: these cookies are readable by JavaScript, so any XSS
      // in this application yields full account takeover. The complete fix is
      // httpOnly cookies issued by the API plus a CSRF strategy -- that is an
      // auth-flow change spanning the API and both UIs, tracked as the
      // remaining work in ENH-018. Until then the refresh token's lifetime is
      // reduced from 30 days to 7 to bound the exposure window.
      Cookies.set(AUTH_TOKEN_KEY, token, { expires: 1, secure, sameSite: 'strict' })
      Cookies.set(TENANT_ID_KEY, tenantId, { expires: 30, secure, sameSite: 'strict' })

      if (refreshToken) {
        Cookies.set(REFRESH_TOKEN_KEY, refreshToken, { expires: 7, secure, sameSite: 'strict' })
      }
    }
  }

  public logout(): void {
    this.authToken = null
    this.tenantId = null

    if (typeof window !== 'undefined') {
      Cookies.remove(AUTH_TOKEN_KEY)
      Cookies.remove(TENANT_ID_KEY)
      Cookies.remove(REFRESH_TOKEN_KEY)
    }
  }

  public getAuthContext(): AuthContext {
    return {
      token: this.authToken,
      tenantId: this.tenantId,
      userId: null, // Will be populated from token decode
      roles: [], // Will be populated from token decode
      isAuthenticated: !!this.authToken,
    }
  }

  // Core HTTP methods
  public async get<T = any>(
    endpoint: string,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    const response = await this.client.get(endpoint, config)
    
    // Handle auth endpoints that return data directly without wrapper
    if (endpoint.includes('/auth/me') || endpoint.includes('/auth/refresh')) {
      return {
        data: response.data,
        success: true,
        message: 'Success'
      }
    }
    
    return response.data
  }

  public async post<T = any>(
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    const response = await this.client.post(endpoint, data, config)
    
    // Handle auth endpoints that return data directly without wrapper
    if (endpoint.includes('/auth/login') || endpoint.includes('/auth/refresh')) {
      return {
        data: response.data,
        success: true,
        message: 'Success'
      }
    }
    
    return response.data
  }

  public async put<T = any>(
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    const response = await this.client.put(endpoint, data, config)
    return response.data
  }

  public async patch<T = any>(
    endpoint: string,
    data?: any,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    const response = await this.client.patch(endpoint, data, config)
    return response.data
  }

  public async delete<T = any>(
    endpoint: string,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    const response = await this.client.delete(endpoint, config)
    return response.data
  }

  // Paginated requests
  public async getPaginated<T = any>(
    endpoint: string,
    params?: {
      page?: number
      limit?: number
      sort?: string
      filter?: Record<string, any>
    }
  ): Promise<PaginatedResponse<T>> {
    const response = await this.client.get(endpoint, { params })
    const rawData = response.data
    
    // Backend returns different formats, we need to extract the data array
    // Common formats: {alerts: [...], total, limit, offset} or {dashboards: [...], total, limit, offset}
    let dataArray: T[] = []
    let total = 0
    let limit = params?.limit || 50
    let offset = 0
    
    if (rawData) {
      // Find the data array (usually the first non-primitive property)
      const dataKey = Object.keys(rawData).find(key => 
        Array.isArray(rawData[key]) && key !== 'total' && key !== 'limit' && key !== 'offset'
      )
      
      if (dataKey) {
        dataArray = rawData[dataKey] || []
      }
      
      total = rawData.total || rawData.total_count || dataArray.length
      limit = rawData.limit || limit
      offset = rawData.offset || 0
    }
    
    const page = Math.floor(offset / limit) + 1
    
    return {
      data: dataArray,
      total,
      page,
      limit,
      hasNext: offset + limit < total,
      hasPrev: offset > 0
    }
  }

  // File upload with progress
  public async uploadFile(
    endpoint: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<ApiResponse> {
    const formData = new FormData()
    formData.append('file', file)

    return this.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = (progressEvent.loaded / progressEvent.total) * 100
          onProgress(Math.round(progress))
        }
      },
    })
  }

  // Streaming endpoints (for logs, metrics, etc.)
  public async getStream(
    endpoint: string,
    onData: (data: any) => void,
    onError?: (error: Error) => void
  ): Promise<() => void> {
    let abortController = new AbortController()
    let isActive = true

    const startStream = async () => {
      try {
        // Build headers with authentication (Fetch API supports custom headers unlike EventSource)
        const headers: Record<string, string> = {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
        }

        // Add authentication token
        if (this.authToken) {
          headers['Authorization'] = `Bearer ${this.authToken}`
        }

        // Add tenant context
        if (this.tenantId) {
          headers['X-Customer-ID'] = this.tenantId
        }

        // Add request ID for tracing
        headers['X-Request-ID'] = this.generateRequestId()

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
          method: 'GET',
          headers,
          signal: abortController.signal,
          credentials: 'include',
          mode: 'cors', // Explicitly set CORS mode
        })

        if (!response.ok) {
          throw new Error(`Stream request failed: ${response.status} ${response.statusText}`)
        }

        if (!response.body) {
          throw new Error('No response body for streaming')
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent: { id?: string; event?: string; data?: string } = {}

        // Read the stream
        while (isActive && !abortController.signal.aborted) {
          const { done, value } = await reader.read()

          if (done) {
            break
          }

          // Decode the chunk and add to buffer
          buffer += decoder.decode(value, { stream: true })

          // Process complete lines (Server-Sent Events format)
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer

          for (const line of lines) {
            // Empty line means end of event
            if (line.trim() === '') {
              if (currentEvent.data) {
                try {
                  const data = JSON.parse(currentEvent.data)
                  onData(data)
                } catch (error) {
                  console.error('Failed to parse SSE data:', error, 'Data:', currentEvent.data)
                }
              }
              currentEvent = {}
            }
            // Parse SSE fields
            else if (line.startsWith('id: ')) {
              currentEvent.id = line.slice(4)
            }
            else if (line.startsWith('event: ')) {
              currentEvent.event = line.slice(7)
            }
            else if (line.startsWith('data: ')) {
              currentEvent.data = line.slice(6)
            }
          }
        }

        reader.releaseLock()
      } catch (error) {
        if (!abortController.signal.aborted && isActive) {
          console.error('Streaming error:', error)
          onError?.(error as Error)
        }
      }
    }

    // Start the stream
    startStream()

    // Return cleanup function
    return () => {
      isActive = false
      abortController.abort()
    }
  }

  // Health check
  public async healthCheck(): Promise<boolean> {
    try {
      await this.get('/health')
      return true
    } catch {
      return false
    }
  }

  // Get WebSocket URL with authentication
  public getWebSocketUrl(path: string): string {
    const wsUrl = new URL(path, WS_BASE_URL.replace('http', 'ws'))
    
    if (this.authToken) {
      wsUrl.searchParams.set('token', this.authToken)
    }
    
    if (this.tenantId) {
      wsUrl.searchParams.set('tenant_id', this.tenantId)
    }

    return wsUrl.toString()
  }
}

// Export singleton instance
export const apiClient = new LogforgeApiClient()

// NOTE: ApiResponse, PaginatedResponse, AuthContext are exported inline at
// their declarations; ApiError is exported as a VALUE (class) above (LF-014).

// Export class for creating additional instances if needed
export { LogforgeApiClient }