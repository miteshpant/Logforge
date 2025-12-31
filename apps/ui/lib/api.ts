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
 * Main API Client Class
 */
class ApiClient {
  private baseURL: string
  private defaultHeaders: Record<string, string>
  private timeout: number

  constructor() {
    this.baseURL = API_CONFIG.baseURL
    this.defaultHeaders = API_CONFIG.headers
    this.timeout = API_CONFIG.timeout
  }

  /**
   * Core request method with error handling
   */
  async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
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
        return {
          success: false,
          error: data?.error || data?.message || `HTTP ${response.status}: ${response.statusText}`,
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
   * Set customer/tenant ID header
   */
  setCustomerId(customerId: string) {
    this.setHeader('X-Customer-ID', customerId)
  }
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export class for testing/advanced usage
export { ApiClient }

// Default export
export default apiClient
