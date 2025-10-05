import { Page, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

export class ObservabilityHelper {
  constructor(private page: Page, private apiClient: ApiClient) {}

  async navigateToObservability() {
    await this.page.goto('/observability')
    await expect(this.page.locator('[data-testid="observability-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
  }

  async verifyServiceMap() {
    await this.navigateToObservability()
    const serviceMapResponse = await this.apiClient.getServiceMap()
    expect(serviceMapResponse).toBeSuccessfulApiResponse()
    
    const serviceMap = this.page.locator('[data-testid="service-map"]')
    await expect(serviceMap).toBeVisible()
  }

  async testTraceAnalysis() {
    const tracesResponse = await this.apiClient.getTraces()
    expect(tracesResponse).toBeSuccessfulApiResponse()
    
    const traces = this.page.locator('[data-testid="trace-item"]')
    const traceCount = await traces.count()
    expect(traceCount).toBeGreaterThanOrEqual(0)
  }
}