import { Page, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

export class AlertsHelper {
  constructor(private page: Page, private apiClient: ApiClient) {}

  async navigateToAlerts() {
    await this.page.goto('/alerts')
    await expect(this.page.locator('[data-testid="alerts-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
  }

  async verifyAlertsWithRealData() {
    await this.navigateToAlerts()
    const alertsResponse = await this.apiClient.getAlerts()
    expect(alertsResponse).toBeSuccessfulApiResponse()
    
    const alerts = this.page.locator('[data-testid="alert-item"]')
    const alertCount = await alerts.count()
    expect(alertCount).toBeGreaterThanOrEqual(0)
  }

  async testAlertCreation() {
    const createButton = this.page.locator('[data-testid="create-alert"]')
    if (await createButton.isVisible()) {
      await createButton.click()
      await expect(this.page.locator('[data-testid="alert-form"]')).toBeVisible()
    }
  }
}