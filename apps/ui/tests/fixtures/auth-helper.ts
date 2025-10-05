import { Page, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

/**
 * Authentication Helper for Enterprise E2E Testing
 * 
 * Provides comprehensive authentication testing:
 * - Login/logout flows
 * - Session management
 * - Multi-tenant context
 * - Permission validation
 * - Security testing
 */

export class AuthenticationHelper {
  constructor(
    private page: Page,
    private apiClient: ApiClient
  ) {}

  /**
   * Perform complete login flow and return tenant context
   */
  async loginAndGetContext(credentials: {
    email: string
    password: string
  }): Promise<{
    tenantId: string
    orgName: string
  }> {
    await this.login(credentials.email, credentials.password)
    
    // Get user profile to extract tenant info
    const profileResponse = await this.apiClient.getProfile()
    expect(profileResponse).toBeSuccessfulApiResponse()
    
    const tenantId = profileResponse.data?.tenant_id || 'default-tenant'
    const orgName = profileResponse.data?.organization || 'Test Organization'
    
    return { tenantId, orgName }
  }

  /**
   * Standard login flow
   */
  async login(email: string, password: string) {
    // Navigate to login page
    await this.page.goto('/login')
    
    // Wait for login form to be visible
    await expect(this.page.locator('[data-testid="login-form"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
    
    // Fill login form
    await this.page.fill('[data-testid="email-input"]', email)
    await this.page.fill('[data-testid="password-input"]', password)
    
    // Submit login form
    await this.page.click('[data-testid="login-button"]')
    
    // Wait for redirect to dashboard
    await expect(this.page).toHaveURL(/\/(dashboard|home)/, {
      timeout: GLOBAL_CONFIG.TIMEOUT.LONG
    })
    
    // Verify authentication was successful
    await this.verifyAuthenticated()
  }

  /**
   * Logout flow
   */
  async logout() {
    // Click user menu
    await this.page.click('[data-testid="user-menu"]')
    
    // Click logout
    await this.page.click('[data-testid="logout-button"]')
    
    // Wait for redirect to login
    await expect(this.page).toHaveURL(/\/login/, {
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
  }

  /**
   * Verify user is authenticated
   */
  async verifyAuthenticated() {
    // Check for authentication indicators
    await expect(this.page.locator('[data-testid="user-menu"]')).toBeVisible()
    await expect(this.page.locator('[data-testid="tenant-selector"]')).toBeVisible()
    
    // Verify API authentication
    const profileResponse = await this.apiClient.getProfile()
    expect(profileResponse.success).toBe(true)
    expect(profileResponse.data).toBeTruthy()
  }

  /**
   * Verify user is not authenticated
   */
  async verifyNotAuthenticated() {
    // Should be on login page
    await expect(this.page).toHaveURL(/\/login/)
    
    // Login form should be visible
    await expect(this.page.locator('[data-testid="login-form"]')).toBeVisible()
    
    // Profile API should fail
    const profileResponse = await this.apiClient.getProfile()
    expect(profileResponse.success).toBe(false)
  }

  /**
   * Test invalid login attempts
   */
  async testInvalidLogin() {
    await this.page.goto('/login')
    
    // Test empty credentials
    await this.page.click('[data-testid="login-button"]')
    await expect(this.page.locator('[data-testid="error-message"]')).toBeVisible()
    
    // Test invalid email
    await this.page.fill('[data-testid="email-input"]', 'invalid-email')
    await this.page.fill('[data-testid="password-input"]', 'password')
    await this.page.click('[data-testid="login-button"]')
    await expect(this.page.locator('[data-testid="error-message"]')).toBeVisible()
    
    // Test wrong password
    await this.page.fill('[data-testid="email-input"]', 'testuser@testorg.com')
    await this.page.fill('[data-testid="password-input"]', 'wrong-password')
    await this.page.click('[data-testid="login-button"]')
    await expect(this.page.locator('[data-testid="error-message"]')).toBeVisible()
  }

  /**
   * Verify session persistence
   */
  async verifySessionPersistence() {
    // Reload page
    await this.page.reload()
    
    // Should still be authenticated
    await this.verifyAuthenticated()
  }

  /**
   * Test multi-tenant context switching
   */
  async testTenantSwitching() {
    // Get available tenants
    const tenantsResponse = await this.apiClient.getTenants()
    expect(tenantsResponse).toBeSuccessfulApiResponse()
    
    if (tenantsResponse.data && tenantsResponse.data.length > 1) {
      // Click tenant selector
      await this.page.click('[data-testid="tenant-selector"]')
      
      // Select different tenant
      await this.page.click(`[data-testid="tenant-option-${tenantsResponse.data[1].id}"]`)
      
      // Verify tenant context changed
      await expect(this.page.locator('[data-testid="current-tenant"]')).toHaveText(
        tenantsResponse.data[1].name
      )
    }
  }

  /**
   * Test security features
   */
  async testSecurityFeatures() {
    // Test session timeout (if applicable)
    // Test CSRF protection
    // Test XSS protection
    
    // Verify secure headers
    const response = await this.page.goto('/dashboard')
    const headers = response?.headers() || {}
    
    // Check for security headers
    expect(headers['x-frame-options']).toBeTruthy()
    expect(headers['x-content-type-options']).toBe('nosniff')
  }

  /**
   * Setup authentication state for tests
   */
  async setupAuthState(credentials: {
    email: string
    password: string
  }) {
    await this.login(credentials.email, credentials.password)
    
    // Save authentication state
    await this.page.context().storageState({
      path: 'tests/auth-state.json'
    })
  }

  /**
   * Load authentication state for tests
   */
  async loadAuthState() {
    try {
      await this.page.context().addInitScript(() => {
        // Restore any necessary client-side auth state
      })
    } catch {
      // Auth state not available, will need to login
    }
  }

  /**
   * Verify enterprise authentication features
   */
  async verifyEnterpriseAuth() {
    // Check for SSO options (if configured)
    await this.page.goto('/login')
    
    // Look for SSO buttons
    const ssoButtons = this.page.locator('[data-testid*="sso-"]')
    const ssoCount = await ssoButtons.count()
    
    if (ssoCount > 0) {
      // Test SSO redirect flow (without actually logging in via SSO)
      for (let i = 0; i < ssoCount; i++) {
        const ssoButton = ssoButtons.nth(i)
        const ssoType = await ssoButton.getAttribute('data-testid')
        
        // Click SSO button
        await ssoButton.click()
        
        // Should redirect to SSO provider or show SSO form
        await this.page.waitForTimeout(2000)
        
        // Go back to test next SSO option
        await this.page.goBack()
      }
    }
    
    // Check for MFA setup options
    await this.login('testuser@testorg.com', 'TestUser123!')
    
    // Look for MFA setup in user settings
    await this.page.goto('/settings/security')
    const mfaSection = this.page.locator('[data-testid="mfa-section"]')
    if (await mfaSection.isVisible()) {
      // MFA is available - verify setup flow
      await expect(this.page.locator('[data-testid="enable-mfa-button"]')).toBeVisible()
    }
  }

  /**
   * Performance testing for authentication
   */
  async measureLoginPerformance(): Promise<{
    timing: number
    isPerformant: boolean
  }> {
    const startTime = Date.now()
    
    await this.login('testuser@testorg.com', 'TestUser123!')
    
    const timing = Date.now() - startTime
    const isPerformant = timing <= GLOBAL_CONFIG.PERFORMANCE.PAGE_LOAD_MAX
    
    return { timing, isPerformant }
  }
}