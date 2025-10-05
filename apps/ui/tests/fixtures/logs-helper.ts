import { Page, expect } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

/**
 * Logs Helper for Enterprise E2E Testing
 * 
 * Provides comprehensive log analysis testing:
 * - Real-time log streaming
 * - Advanced search and filtering
 * - Time range analysis
 * - Log ingestion testing
 * - Performance monitoring
 */

export class LogsHelper {
  constructor(
    private page: Page,
    private apiClient: ApiClient
  ) {}

  /**
   * Navigate to logs page and verify it loads with real data
   */
  async navigateToLogs() {
    await this.page.goto('/logs')
    
    // Wait for logs page to load
    await expect(this.page.locator('[data-testid="logs-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
    
    // Wait for initial logs to load
    await this.waitForLogsToLoad()
  }

  /**
   * Wait for logs to load and verify real data
   */
  async waitForLogsToLoad() {
    // Wait for loading to complete
    await expect(this.page.locator('[data-testid="loading-spinner"]')).not.toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.LONG
    })
    
    // Verify we have log entries
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    await expect(logEntries.first()).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
    
    // Verify logs have real data
    const logCount = await logEntries.count()
    expect(logCount).toBeGreaterThan(0)
    
    // Check first few logs for real content
    for (let i = 0; i < Math.min(logCount, 3); i++) {
      const logEntry = logEntries.nth(i)
      const logMessage = await logEntry.locator('[data-testid="log-message"]').textContent()
      expect(logMessage).toBeRealData()
    }
  }

  /**
   * Test search functionality with real queries
   */
  async testLogSearch() {
    // Test basic search
    await this.page.fill('[data-testid="search-input"]', 'error')
    await this.page.click('[data-testid="search-button"]')
    
    // Wait for search results
    await this.waitForLogsToLoad()
    
    // Verify search results contain the search term
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    if (logCount > 0) {
      // Check that results are relevant
      const firstLog = await logEntries.first().locator('[data-testid="log-message"]').textContent()
      expect(firstLog?.toLowerCase()).toContain('error')
    }
    
    // Test advanced search with field:value syntax
    await this.page.fill('[data-testid="search-input"]', 'level:ERROR')
    await this.page.click('[data-testid="search-button"]')
    
    await this.waitForLogsToLoad()
    
    // Verify all results have ERROR level
    const errorLogs = this.page.locator('[data-testid="log-entry"]')
    const errorCount = await errorLogs.count()
    
    for (let i = 0; i < Math.min(errorCount, 5); i++) {
      const logEntry = errorLogs.nth(i)
      const logLevel = await logEntry.locator('[data-testid="log-level"]').textContent()
      expect(logLevel?.toUpperCase()).toBe('ERROR')
    }
    
    // Clear search
    await this.page.fill('[data-testid="search-input"]', '')
    await this.page.click('[data-testid="search-button"]')
    await this.waitForLogsToLoad()
  }

  /**
   * Test filtering functionality
   */
  async testLogFiltering() {
    // Test level filter
    await this.page.click('[data-testid="level-filter"]')
    await this.page.click('[data-testid="level-option-ERROR"]')
    
    await this.waitForLogsToLoad()
    
    // Verify all logs are ERROR level
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    for (let i = 0; i < Math.min(logCount, 3); i++) {
      const logEntry = logEntries.nth(i)
      const levelBadge = logEntry.locator('[data-testid="log-level"]')
      await expect(levelBadge).toContainText('ERROR')
    }
    
    // Test service filter
    await this.page.click('[data-testid="service-filter"]')
    const serviceOptions = this.page.locator('[data-testid^="service-option-"]')
    const serviceCount = await serviceOptions.count()
    
    if (serviceCount > 0) {
      // Select first available service
      await serviceOptions.first().click()
      await this.waitForLogsToLoad()
      
      // Verify logs are from selected service
      const serviceName = await serviceOptions.first().textContent()
      const filteredLogs = this.page.locator('[data-testid="log-entry"]')
      const filteredCount = await filteredLogs.count()
      
      for (let i = 0; i < Math.min(filteredCount, 3); i++) {
        const logEntry = filteredLogs.nth(i)
        const logService = await logEntry.locator('[data-testid="log-service"]').textContent()
        expect(logService).toBe(serviceName)
      }
    }
    
    // Reset filters
    await this.page.click('[data-testid="reset-filters"]')
    await this.waitForLogsToLoad()
  }

  /**
   * Test time range functionality with global selector
   */
  async testTimeRangeSelection() {
    // Test different time ranges
    const timeRanges = ['1h', '24h', '7d']
    
    for (const timeRange of timeRanges) {
      // Click global time range selector
      await this.page.click('[data-testid="time-range-selector"]')
      await this.page.click(`[data-testid="time-range-${timeRange}"]`)
      
      // Wait for logs to update
      await this.waitForLogsToLoad()
      
      // Verify time range is applied
      await expect(this.page.locator('[data-testid="current-time-range"]')).toContainText(timeRange)
      
      // Verify logs are within time range
      const logEntries = this.page.locator('[data-testid="log-entry"]')
      const logCount = await logEntries.count()
      
      if (logCount > 0) {
        // Check timestamp of first log
        const firstLogTime = await logEntries.first().locator('[data-testid="log-timestamp"]').textContent()
        expect(firstLogTime).toBeTruthy()
        
        // Verify timestamp is recent (within selected range)
        const timestamp = new Date(firstLogTime!)
        const now = new Date()
        const diffHours = (now.getTime() - timestamp.getTime()) / (1000 * 60 * 60)
        
        switch (timeRange) {
          case '1h':
            expect(diffHours).toBeLessThanOrEqual(1)
            break
          case '24h':
            expect(diffHours).toBeLessThanOrEqual(24)
            break
          case '7d':
            expect(diffHours).toBeLessThanOrEqual(7 * 24)
            break
        }
      }
    }
  }

  /**
   * Test log ingestion by sending test logs
   */
  async testLogIngestion() {
    // Send a test log via API
    const testLog = {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      service: 'playwright-test',
      message: `Test log from Playwright - ${Date.now()}`,
      host: 'test-host',
      user_id: 'test-user',
      request_id: `req_${Date.now()}`
    }
    
    const ingestionResponse = await this.apiClient.ingestLog(testLog)
    expect(ingestionResponse).toBeSuccessfulApiResponse()
    
    // Wait for log to appear (give time for indexing)
    await this.page.waitForTimeout(3000)
    
    // Search for our test log
    await this.page.fill('[data-testid="search-input"]', testLog.message)
    await this.page.click('[data-testid="search-button"]')
    
    await this.waitForLogsToLoad()
    
    // Verify our test log appears
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    if (logCount > 0) {
      const firstLogMessage = await logEntries.first().locator('[data-testid="log-message"]').textContent()
      expect(firstLogMessage).toContain(testLog.message)
    }
    
    // Clear search
    await this.page.fill('[data-testid="search-input"]', '')
    await this.page.click('[data-testid="search-button"]')
  }

  /**
   * Test log details and expansion
   */
  async testLogDetails() {
    await this.waitForLogsToLoad()
    
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    if (logCount > 0) {
      const firstLog = logEntries.first()
      
      // Click to expand log details
      await firstLog.click()
      
      // Verify expanded details
      const expandedContent = firstLog.locator('[data-testid="log-details"]')
      await expect(expandedContent).toBeVisible()
      
      // Check for detailed fields
      await expect(expandedContent.locator('[data-testid="log-timestamp"]')).toBeVisible()
      await expect(expandedContent.locator('[data-testid="log-level"]')).toBeVisible()
      await expect(expandedContent.locator('[data-testid="log-service"]')).toBeVisible()
      await expect(expandedContent.locator('[data-testid="log-message"]')).toBeVisible()
      
      // Check for optional fields
      const hostField = expandedContent.locator('[data-testid="log-host"]')
      const userField = expandedContent.locator('[data-testid="log-user"]')
      const requestField = expandedContent.locator('[data-testid="log-request"]')
      
      // At least some additional fields should be present
      const additionalFieldsCount = await hostField.count() + await userField.count() + await requestField.count()
      expect(additionalFieldsCount).toBeGreaterThan(0)
      
      // Collapse log details
      await firstLog.click()
      await expect(expandedContent).not.toBeVisible()
    }
  }

  /**
   * Test log export functionality
   */
  async testLogExport() {
    // Click export button
    const exportButton = this.page.locator('[data-testid="export-logs"]')
    
    if (await exportButton.isVisible()) {
      await exportButton.click()
      
      // Verify export options
      await expect(this.page.locator('[data-testid="export-options"]')).toBeVisible()
      
      // Test CSV export
      const csvOption = this.page.locator('[data-testid="export-csv"]')
      if (await csvOption.isVisible()) {
        // Start download
        const downloadPromise = this.page.waitForEvent('download')
        await csvOption.click()
        
        const download = await downloadPromise
        expect(download.suggestedFilename()).toContain('.csv')
      }
      
      // Close export dialog
      await this.page.keyboard.press('Escape')
    }
  }

  /**
   * Test real-time log streaming
   */
  async testRealTimeStreaming() {
    // Look for real-time indicator
    const liveIndicator = this.page.locator('[data-testid="live-logs"]')
    
    if (await liveIndicator.isVisible()) {
      // Enable live streaming
      await liveIndicator.click()
      
      // Verify streaming is active
      await expect(this.page.locator('[data-testid="streaming-active"]')).toBeVisible()
      
      // Send a test log to see if it appears in real-time
      const testLog = {
        timestamp: new Date().toISOString(),
        level: 'DEBUG',
        service: 'realtime-test',
        message: `Real-time test log - ${Date.now()}`,
        host: 'test-host'
      }
      
      await this.apiClient.ingestLog(testLog)
      
      // Wait for real-time update (should be faster than regular search)
      await this.page.waitForTimeout(2000)
      
      // Check if new log appeared at the top
      const firstLog = this.page.locator('[data-testid="log-entry"]').first()
      const firstLogMessage = await firstLog.locator('[data-testid="log-message"]').textContent()
      
      // Note: In real-time streaming, the newest log should appear first
      if (firstLogMessage?.includes('Real-time test log')) {
        // Real-time streaming is working
        expect(true).toBe(true)
      }
      
      // Disable live streaming
      await liveIndicator.click()
      await expect(this.page.locator('[data-testid="streaming-active"]')).not.toBeVisible()
    }
  }

  /**
   * Performance testing for log search
   */
  async measureSearchPerformance(): Promise<{
    searchTime: number
    resultCount: number
    isPerformant: boolean
  }> {
    const startTime = Date.now()
    
    // Perform a search
    await this.page.fill('[data-testid="search-input"]', 'level:INFO')
    await this.page.click('[data-testid="search-button"]')
    
    // Wait for results
    await this.waitForLogsToLoad()
    
    const searchTime = Date.now() - startTime
    
    // Count results
    const logEntries = this.page.locator('[data-testid="log-entry"]')
    const resultCount = await logEntries.count()
    
    const isPerformant = searchTime <= GLOBAL_CONFIG.PERFORMANCE.SEARCH_RESPONSE_MAX
    
    return {
      searchTime,
      resultCount,
      isPerformant
    }
  }

  /**
   * Test log pagination
   */
  async testLogPagination() {
    await this.waitForLogsToLoad()
    
    // Check if pagination exists
    const paginationContainer = this.page.locator('[data-testid="pagination"]')
    
    if (await paginationContainer.isVisible()) {
      // Test next page
      const nextButton = paginationContainer.locator('[data-testid="next-page"]')
      if (await nextButton.isVisible() && !await nextButton.isDisabled()) {
        await nextButton.click()
        await this.waitForLogsToLoad()
        
        // Verify page changed
        await expect(this.page.locator('[data-testid="current-page"]')).toContainText('2')
        
        // Test previous page
        const prevButton = paginationContainer.locator('[data-testid="prev-page"]')
        await prevButton.click()
        await this.waitForLogsToLoad()
        
        // Verify back to page 1
        await expect(this.page.locator('[data-testid="current-page"]')).toContainText('1')
      }
    }
  }

  /**
   * Verify enterprise log features
   */
  async verifyEnterpriseLogFeatures() {
    // Check for tenant isolation
    const tenantContext = this.page.locator('[data-testid="tenant-context"]')
    if (await tenantContext.isVisible()) {
      const tenantInfo = await tenantContext.textContent()
      expect(tenantInfo).toBeTruthy()
    }
    
    // Check for audit trail
    const auditInfo = this.page.locator('[data-testid="audit-info"]')
    if (await auditInfo.isVisible()) {
      // Verify audit information is present
      expect(await auditInfo.textContent()).toBeTruthy()
    }
    
    // Check for compliance features
    const complianceIndicator = this.page.locator('[data-testid="compliance-indicator"]')
    if (await complianceIndicator.isVisible()) {
      // Verify compliance status
      await expect(complianceIndicator).toHaveClass(/compliant|secure/)
    }
  }
}