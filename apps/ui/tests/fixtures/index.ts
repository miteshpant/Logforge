import { test as base, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { AuthenticationHelper } from './auth-helper'
import { DashboardHelper } from './dashboard-helper'
import { SecurityHelper } from './security-helper'
import { LogsHelper } from './logs-helper'
import { AlertsHelper } from './alerts-helper'
import { ObservabilityHelper } from './observability-helper'

/**
 * Enterprise Testing Fixtures for Logforge UI
 * 
 * Provides comprehensive testing utilities for:
 * - Authentication and session management
 * - API testing and validation
 * - Page object models for all UI components
 * - Real-time data validation
 * - Enterprise features testing
 */

export interface TestFixtures {
  // Core API client for backend communication
  apiClient: ApiClient
  
  // Authentication and user management
  authHelper: AuthenticationHelper
  
  // Page-specific helpers
  dashboardHelper: DashboardHelper
  securityHelper: SecurityHelper
  logsHelper: LogsHelper
  alertsHelper: AlertsHelper
  observabilityHelper: ObservabilityHelper
  
  // Test data and utilities
  testCredentials: {
    email: string
    password: string
  }
  
  // Enterprise features
  tenantContext: {
    tenantId: string
    orgName: string
  }
}

// Test credentials for consistent testing
const TEST_CREDENTIALS = {
  email: 'testuser@testorg.com',
  password: 'TestUser123!'
}

// Extend base test with our fixtures
export const test = base.extend<TestFixtures>({
  // API client fixture
  apiClient: async ({ page }, use) => {
    const apiClient = new ApiClient(page)
    await use(apiClient)
  },

  // Authentication helper
  authHelper: async ({ page, apiClient }, use) => {
    const authHelper = new AuthenticationHelper(page, apiClient)
    await use(authHelper)
  },

  // Dashboard helper
  dashboardHelper: async ({ page, apiClient }, use) => {
    const dashboardHelper = new DashboardHelper(page, apiClient)
    await use(dashboardHelper)
  },

  // Security helper
  securityHelper: async ({ page, apiClient }, use) => {
    const securityHelper = new SecurityHelper(page, apiClient)
    await use(securityHelper)
  },

  // Logs helper
  logsHelper: async ({ page, apiClient }, use) => {
    const logsHelper = new LogsHelper(page, apiClient)
    await use(logsHelper)
  },

  // Alerts helper
  alertsHelper: async ({ page, apiClient }, use) => {
    const alertsHelper = new AlertsHelper(page, apiClient)
    await use(alertsHelper)
  },

  // Observability helper
  observabilityHelper: async ({ page, apiClient }, use) => {
    const observabilityHelper = new ObservabilityHelper(page, apiClient)
    await use(observabilityHelper)
  },

  // Test credentials
  testCredentials: async ({}, use) => {
    await use(TEST_CREDENTIALS)
  },

  // Tenant context (will be populated after login)
  tenantContext: async ({ authHelper, testCredentials }, use) => {
    // Login and get tenant context
    const context = await authHelper.loginAndGetContext(testCredentials)
    await use(context)
  }
})

// Export expect for consistency
export { expect }

// Custom expect matchers for Logforge-specific assertions
expect.extend({
  // Check if API response is successful
  toBeSuccessfulApiResponse(received: any) {
    const pass = received && received.success === true && received.data
    return {
      message: () => 
        pass 
          ? `Expected API response to not be successful`
          : `Expected API response to be successful, but received: ${JSON.stringify(received)}`,
      pass
    }
  },

  // Check if element has enterprise styling
  async toHaveEnterpriseStyles(locator: any) {
    const element = await locator.first()
    const classList = await element.getAttribute('class') || ''
    
    // Check for enterprise design patterns
    const hasGradient = classList.includes('gradient')
    const hasBackdrop = classList.includes('backdrop-blur')
    const hasShadow = classList.includes('shadow')
    const hasHover = classList.includes('hover:')
    
    const pass = hasGradient || hasBackdrop || hasShadow || hasHover
    
    return {
      message: () => 
        pass 
          ? `Expected element to not have enterprise styles`
          : `Expected element to have enterprise styles (gradient, backdrop-blur, shadow, hover effects), but found classes: ${classList}`,
      pass
    }
  },

  // Check if data is real (not mock)
  toBeRealData(received: any) {
    // Check for common mock data patterns
    const isMock = 
      (typeof received === 'string' && received.includes('mock')) ||
      (typeof received === 'string' && received.includes('test')) ||
      (typeof received === 'string' && received.includes('sample')) ||
      (Array.isArray(received) && received.length === 0) ||
      (typeof received === 'object' && received.placeholder)

    const pass = !isMock && received !== null && received !== undefined
    
    return {
      message: () => 
        pass 
          ? `Expected data to be mock data`
          : `Expected real data, but received what appears to be mock/test data: ${JSON.stringify(received)}`,
      pass
    }
  }
})

// Global test configuration
export const GLOBAL_CONFIG = {
  // API endpoints
  API_BASE_URL: 'http://localhost:7080',
  
  // Timeouts
  TIMEOUT: {
    SHORT: 5000,
    MEDIUM: 15000,
    LONG: 30000,
    EXTRA_LONG: 60000
  },
  
  // Retry configuration
  RETRY: {
    COUNT: 3,
    DELAY: 1000
  },
  
  // Performance thresholds
  PERFORMANCE: {
    PAGE_LOAD_MAX: 3000,
    API_RESPONSE_MAX: 2000,
    SEARCH_RESPONSE_MAX: 5000
  }
} as const