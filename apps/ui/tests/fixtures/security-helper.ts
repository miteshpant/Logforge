import { Page, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

export class SecurityHelper {
  constructor(private page: Page, private apiClient: ApiClient) {}

  async navigateToSecurity() {
    await this.page.goto('/security')
    await expect(this.page.locator('[data-testid="security-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
  }

  async verifySecurityDashboard() {
    await this.navigateToSecurity()
    
    // Verify security widgets load with real data
    const widgets = this.page.locator('[data-testid^="security-widget-"]')
    const widgetCount = await widgets.count()
    expect(widgetCount).toBeGreaterThan(0)

    // Check threat intelligence
    const threatIntelResponse = await this.apiClient.getThreatIntel()
    expect(threatIntelResponse).toBeSuccessfulApiResponse()
  }

  async testThreatHunting() {
    const huntButton = this.page.locator('[data-testid="threat-hunt-button"]')
    if (await huntButton.isVisible()) {
      await huntButton.click()
      await expect(this.page.locator('[data-testid="threat-hunt-form"]')).toBeVisible()
    }
  }
}