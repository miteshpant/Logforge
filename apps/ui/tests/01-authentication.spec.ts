import { test, expect } from './fixtures'
import { GLOBAL_CONFIG } from './fixtures'

/**
 * 🔐 ENTERPRISE AUTHENTICATION TESTING SUITE
 * 
 * Comprehensive authentication testing for Logforge enterprise platform:
 * - Login/logout flows with real API calls
 * - Session management and persistence
 * - Multi-tenant context switching
 * - Security feature validation
 * - Performance monitoring
 * - Enterprise SSO testing
 */

test.describe('🔐 Enterprise Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure clean state
    await page.context().clearCookies()
    await page.context().clearPermissions()
  })

  test('should perform complete login flow with real authentication', async ({ 
    authHelper, 
    testCredentials,
    apiClient 
  }) => {
    // Verify API is ready
    const isApiReady = await apiClient.waitForApiReady()
    expect(isApiReady).toBe(true)

    // Test login performance
    const { timing, isPerformant } = await authHelper.measureLoginPerformance()
    expect(isPerformant).toBe(true)
    console.log(`✅ Login completed in ${timing}ms (target: <${GLOBAL_CONFIG.PERFORMANCE.PAGE_LOAD_MAX}ms)`)

    // Verify authentication state
    await authHelper.verifyAuthenticated()
    
    // Verify real user data (not mocked)
    const profileResponse = await apiClient.getProfile()
    expect(profileResponse).toBeSuccessfulApiResponse()
    expect(profileResponse.data).toBeRealData()
    
    console.log(`✅ Authenticated user: ${profileResponse.data?.email}`)
    console.log(`✅ Tenant: ${profileResponse.data?.organization}`)
  })

  test('should handle invalid login attempts securely', async ({ authHelper, page }) => {
    await authHelper.testInvalidLogin()
    
    // Verify no sensitive information leaked
    const pageContent = await page.content()
    expect(pageContent).not.toContain('password')
    expect(pageContent).not.toContain('token')
    expect(pageContent).not.toContain('secret')
  })

  test('should maintain session persistence across page reloads', async ({ 
    authHelper, 
    testCredentials 
  }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
    await authHelper.verifySessionPersistence()
    
    console.log('✅ Session persistence verified')
  })

  test('should handle logout flow completely', async ({ 
    authHelper, 
    testCredentials,
    apiClient 
  }) => {
    // Login first
    await authHelper.login(testCredentials.email, testCredentials.password)
    await authHelper.verifyAuthenticated()
    
    // Perform logout
    await authHelper.logout()
    await authHelper.verifyNotAuthenticated()
    
    // Verify API session is cleared
    const profileResponse = await apiClient.getProfile()
    expect(profileResponse.success).toBe(false)
    
    console.log('✅ Complete logout flow verified')
  })

  test('should support multi-tenant context switching', async ({ 
    authHelper, 
    testCredentials,
    apiClient 
  }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
    
    // Test tenant switching if multiple tenants available
    const tenantsResponse = await apiClient.getTenants()
    if (tenantsResponse.success && tenantsResponse.data?.length > 1) {
      await authHelper.testTenantSwitching()
      console.log(`✅ Multi-tenant switching tested with ${tenantsResponse.data.length} tenants`)
    } else {
      console.log('ℹ️ Single tenant environment - skipping tenant switching test')
    }
  })

  test('should validate enterprise security features', async ({ 
    authHelper, 
    page 
  }) => {
    await authHelper.testSecurityFeatures()
    
    // Additional security checks
    const responseHeaders = await page.goto('/dashboard').then(response => response?.headers())
    
    // Verify security headers
    expect(responseHeaders?.['x-frame-options']).toBeTruthy()
    expect(responseHeaders?.['x-content-type-options']).toBe('nosniff')
    
    console.log('✅ Enterprise security features validated')
  })

  test('should support enterprise SSO and MFA features', async ({ authHelper }) => {
    await authHelper.verifyEnterpriseAuth()
    console.log('✅ Enterprise authentication features verified')
  })

  test('should handle concurrent session management', async ({ 
    browser, 
    testCredentials,
    authHelper 
  }) => {
    // Create multiple contexts to simulate concurrent sessions
    const context1 = await browser.newContext()
    const context2 = await browser.newContext()
    
    const page1 = await context1.newPage()
    const page2 = await context2.newPage()
    
    // Login from both contexts
    const authHelper1 = new (await import('./fixtures/auth-helper')).AuthenticationHelper(
      page1, 
      new (await import('./fixtures/api-client')).ApiClient(page1)
    )
    
    const authHelper2 = new (await import('./fixtures/auth-helper')).AuthenticationHelper(
      page2, 
      new (await import('./fixtures/api-client')).ApiClient(page2)
    )
    
    await authHelper1.login(testCredentials.email, testCredentials.password)
    await authHelper2.login(testCredentials.email, testCredentials.password)
    
    // Verify both sessions are active
    await authHelper1.verifyAuthenticated()
    await authHelper2.verifyAuthenticated()
    
    // Cleanup
    await context1.close()
    await context2.close()
    
    console.log('✅ Concurrent session management verified')
  })

  test('should maintain authentication performance under load', async ({ 
    authHelper, 
    testCredentials 
  }) => {
    const performanceResults = []
    
    // Perform multiple login attempts to test performance consistency
    for (let i = 0; i < 3; i++) {
      await authHelper.logout()
      const { timing, isPerformant } = await authHelper.measureLoginPerformance()
      performanceResults.push({ timing, isPerformant })
      
      expect(isPerformant).toBe(true)
    }
    
    const avgTiming = performanceResults.reduce((sum, result) => sum + result.timing, 0) / performanceResults.length
    console.log(`✅ Average login performance: ${avgTiming.toFixed(0)}ms across ${performanceResults.length} attempts`)
  })

  test('should validate API authentication integration', async ({ 
    apiClient, 
    authHelper, 
    testCredentials 
  }) => {
    // Test unauthenticated API calls
    const unauthResponse = await apiClient.getProfile()
    expect(unauthResponse.success).toBe(false)
    
    // Login and test authenticated API calls
    await authHelper.login(testCredentials.email, testCredentials.password)
    
    // Test multiple API endpoints for authentication
    const endpoints = [
      () => apiClient.getProfile(),
      () => apiClient.getDashboards(),
      () => apiClient.getCurrentUsage(),
      () => apiClient.getTenants()
    ]
    
    for (const endpoint of endpoints) {
      const response = await endpoint()
      expect(response.success).toBe(true)
      expect(response.data).toBeRealData()
    }
    
    console.log(`✅ API authentication verified across ${endpoints.length} endpoints`)
  })
})

test.describe('🔐 Authentication Error Handling', () => {
  test('should handle network failures gracefully', async ({ page, authHelper }) => {
    // Simulate network failure
    await page.route('**/v1/auth/login', route => route.abort())
    
    await page.goto('/login')
    await page.fill('[data-testid="email-input"]', 'test@example.com')
    await page.fill('[data-testid="password-input"]', 'password')
    await page.click('[data-testid="login-button"]')
    
    // Should show appropriate error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible()
    await expect(page.locator('[data-testid="error-message"]')).toContainText(/network|connection|failed/)
    
    console.log('✅ Network failure handling verified')
  })

  test('should handle API timeout gracefully', async ({ page }) => {
    // Simulate slow API response
    await page.route('**/v1/auth/login', route => {
      setTimeout(() => route.fulfill({
        status: 408,
        body: JSON.stringify({ error: 'Request timeout' })
      }), 100)
    })
    
    await page.goto('/login')
    await page.fill('[data-testid="email-input"]', 'test@example.com')
    await page.fill('[data-testid="password-input"]', 'password')
    await page.click('[data-testid="login-button"]')
    
    // Should show timeout error
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible()
    
    console.log('✅ API timeout handling verified')
  })

  test('should handle session expiration', async ({ 
    authHelper, 
    testCredentials, 
    apiClient,
    page 
  }) => {
    // Login normally
    await authHelper.login(testCredentials.email, testCredentials.password)
    
    // Simulate session expiration by intercepting API calls
    await page.route('**/v1/**', route => {
      route.fulfill({
        status: 401,
        body: JSON.stringify({ error: 'Session expired' })
      })
    })
    
    // Try to access protected resource
    await page.goto('/dashboard')
    
    // Should redirect to login or show session expired message
    await page.waitForTimeout(2000)
    const currentUrl = page.url()
    const hasLoginForm = await page.locator('[data-testid="login-form"]').isVisible()
    const hasSessionExpired = await page.locator('[data-testid="session-expired"]').isVisible()
    
    expect(currentUrl.includes('/login') || hasLoginForm || hasSessionExpired).toBe(true)
    
    console.log('✅ Session expiration handling verified')
  })
})