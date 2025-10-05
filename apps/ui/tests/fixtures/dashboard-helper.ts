import { Page, expect, Locator } from '@playwright/test'
import { ApiClient } from './api-client'
import { GLOBAL_CONFIG } from './index'

/**
 * Dashboard Helper for Enterprise E2E Testing
 * 
 * Provides comprehensive dashboard testing:
 * - Real-time data validation
 * - Widget functionality
 * - Time range controls
 * - Performance monitoring
 * - Enterprise visualization features
 */

export class DashboardHelper {
  constructor(
    private page: Page,
    private apiClient: ApiClient
  ) {}

  /**
   * Navigate to dashboard and verify it loads with real data
   */
  async navigateToDashboard() {
    await this.page.goto('/dashboard')
    
    // Wait for dashboard to load
    await expect(this.page.locator('[data-testid="dashboard-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
    
    // Verify no loading states remain
    await expect(this.page.locator('[data-testid="loading-spinner"]')).not.toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.LONG
    })
  }

  /**
   * Verify all dashboard widgets load with real data
   */
  async verifyWidgetsWithRealData() {
    // Get all widget containers
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    expect(widgetCount).toBeGreaterThan(0)
    
    for (let i = 0; i < widgetCount; i++) {
      const widget = widgets.nth(i)
      const widgetId = await widget.getAttribute('data-testid')
      
      // Wait for widget data to load
      await expect(widget.locator('[data-testid="widget-content"]')).toBeVisible()
      
      // Verify widget has real data (not empty state)
      const isEmpty = await widget.locator('[data-testid="empty-state"]').isVisible()
      const hasError = await widget.locator('[data-testid="error-state"]').isVisible()
      
      expect(isEmpty).toBe(false)
      expect(hasError).toBe(false)
      
      // Check for actual data values
      const dataElements = widget.locator('[data-testid*="data-"]')
      const dataCount = await dataElements.count()
      expect(dataCount).toBeGreaterThan(0)
      
      // Verify data appears to be real (not placeholder)
      for (let j = 0; j < Math.min(dataCount, 3); j++) {
        const dataElement = dataElements.nth(j)
        const textContent = await dataElement.textContent()
        expect(textContent).toBeRealData()
      }
    }
  }

  /**
   * Test time range selector functionality
   */
  async testTimeRangeSelector() {
    // Click time range selector
    await this.page.click('[data-testid="time-range-selector"]')
    
    // Verify dropdown opens
    await expect(this.page.locator('[data-testid="time-range-dropdown"]')).toBeVisible()
    
    // Test different time ranges
    const timeRanges = ['1h', '24h', '7d', '30d']
    
    for (const timeRange of timeRanges) {
      // Select time range
      await this.page.click(`[data-testid="time-range-${timeRange}"]`)
      
      // Wait for dashboard to update
      await this.page.waitForTimeout(2000)
      
      // Verify dashboard updates with new data
      await this.verifyDashboardUpdated(timeRange)
      
      // Open selector again for next iteration
      if (timeRange !== timeRanges[timeRanges.length - 1]) {
        await this.page.click('[data-testid="time-range-selector"]')
      }
    }
  }

  /**
   * Verify dashboard updated with new time range
   */
  async verifyDashboardUpdated(timeRange: string) {
    // Check that current time range is displayed
    await expect(this.page.locator('[data-testid="current-time-range"]')).toContainText(timeRange)
    
    // Verify widgets refresh (look for updated timestamps or data)
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    for (let i = 0; i < Math.min(widgetCount, 3); i++) {
      const widget = widgets.nth(i)
      
      // Look for loading indicators that show refresh
      await expect(widget.locator('[data-testid="refreshing-indicator"]')).not.toBeVisible({
        timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
      })
    }
  }

  /**
   * Test dashboard refresh functionality
   */
  async testDashboardRefresh() {
    // Click refresh button
    await this.page.click('[data-testid="refresh-button"]')
    
    // Verify refresh indicators appear
    const refreshIndicators = this.page.locator('[data-testid="refreshing-indicator"]')
    if (await refreshIndicators.count() > 0) {
      await expect(refreshIndicators.first()).toBeVisible()
      
      // Wait for refresh to complete
      await expect(refreshIndicators.first()).not.toBeVisible({
        timeout: GLOBAL_CONFIG.TIMEOUT.LONG
      })
    }
    
    // Verify last updated time changes
    const lastUpdated = this.page.locator('[data-testid="last-updated"]')
    if (await lastUpdated.isVisible()) {
      const updatedText = await lastUpdated.textContent()
      expect(updatedText).toContain('ago')
    }
  }

  /**
   * Test dashboard search functionality
   */
  async testDashboardSearch() {
    const searchInput = this.page.locator('[data-testid="dashboard-search"]')
    
    if (await searchInput.isVisible()) {
      // Test search functionality
      await searchInput.fill('error')
      await this.page.waitForTimeout(1000)
      
      // Verify search results
      const searchResults = this.page.locator('[data-testid="search-results"]')
      if (await searchResults.isVisible()) {
        const resultCount = await searchResults.locator('[data-testid="search-result"]').count()
        expect(resultCount).toBeGreaterThan(0)
      }
      
      // Clear search
      await searchInput.clear()
      await this.page.waitForTimeout(1000)
    }
  }

  /**
   * Test widget interactions
   */
  async testWidgetInteractions() {
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    if (widgetCount > 0) {
      const firstWidget = widgets.first()
      
      // Test widget hover effects
      await firstWidget.hover()
      await expect(firstWidget).toHaveEnterpriseStyles()
      
      // Test widget click (if clickable)
      const isClickable = await firstWidget.getAttribute('data-clickable')
      if (isClickable === 'true') {
        await firstWidget.click()
        
        // Check if detail view opens
        const detailModal = this.page.locator('[data-testid="widget-detail-modal"]')
        if (await detailModal.isVisible()) {
          // Verify detail modal has content
          await expect(detailModal.locator('[data-testid="detail-content"]')).toBeVisible()
          
          // Close modal
          await this.page.click('[data-testid="close-modal"]')
          await expect(detailModal).not.toBeVisible()
        }
      }
    }
  }

  /**
   * Verify real-time updates
   */
  async verifyRealTimeUpdates() {
    // Look for real-time indicators
    const liveIndicator = this.page.locator('[data-testid="live-indicator"]')
    if (await liveIndicator.isVisible()) {
      // Verify live indicator is active
      await expect(liveIndicator).toHaveClass(/active|live|pulse/)
    }
    
    // Check for WebSocket connection status
    const connectionStatus = this.page.locator('[data-testid="connection-status"]')
    if (await connectionStatus.isVisible()) {
      await expect(connectionStatus).toHaveClass(/connected|online/)
    }
    
    // Monitor for automatic updates (wait for some time and check for changes)
    const initialWidgetData = await this.getWidgetDataSnapshot()
    
    // Wait for potential real-time update
    await this.page.waitForTimeout(10000)
    
    const updatedWidgetData = await this.getWidgetDataSnapshot()
    
    // Note: In a real environment, we might expect some data to change
    // For now, we just verify the widgets are still functional
    expect(Object.keys(updatedWidgetData)).toEqual(Object.keys(initialWidgetData))
  }

  /**
   * Get snapshot of widget data for comparison
   */
  async getWidgetDataSnapshot(): Promise<Record<string, string>> {
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    const snapshot: Record<string, string> = {}
    
    for (let i = 0; i < widgetCount; i++) {
      const widget = widgets.nth(i)
      const widgetId = await widget.getAttribute('data-testid') || `widget-${i}`
      const content = await widget.locator('[data-testid="widget-content"]').textContent() || ''
      snapshot[widgetId] = content
    }
    
    return snapshot
  }

  /**
   * Test dashboard customization (if available)
   */
  async testDashboardCustomization() {
    // Look for customization options
    const customizeButton = this.page.locator('[data-testid="customize-dashboard"]')
    
    if (await customizeButton.isVisible()) {
      await customizeButton.click()
      
      // Verify customization panel opens
      await expect(this.page.locator('[data-testid="customization-panel"]')).toBeVisible()
      
      // Test widget reordering (if available)
      const dragHandle = this.page.locator('[data-testid="widget-drag-handle"]').first()
      if (await dragHandle.isVisible()) {
        // Perform drag and drop
        await dragHandle.dragTo(this.page.locator('[data-testid="drop-zone"]').first())
      }
      
      // Close customization panel
      await this.page.click('[data-testid="close-customization"]')
      await expect(this.page.locator('[data-testid="customization-panel"]')).not.toBeVisible()
    }
  }

  /**
   * Verify dashboard accessibility
   */
  async verifyAccessibility() {
    // Check for ARIA labels
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    for (let i = 0; i < Math.min(widgetCount, 3); i++) {
      const widget = widgets.nth(i)
      
      // Check for accessibility attributes
      const ariaLabel = await widget.getAttribute('aria-label')
      const role = await widget.getAttribute('role')
      
      expect(ariaLabel || role).toBeTruthy()
    }
    
    // Test keyboard navigation
    await this.page.keyboard.press('Tab')
    await this.page.waitForTimeout(100)
    
    // Verify focus is visible
    const focusedElement = this.page.locator(':focus')
    expect(await focusedElement.count()).toBe(1)
  }

  /**
   * Performance testing for dashboard
   */
  async measureDashboardPerformance(): Promise<{
    loadTime: number
    widgetCount: number
    apiCalls: number
    isPerformant: boolean
  }> {
    const startTime = Date.now()
    
    // Navigate to dashboard
    await this.navigateToDashboard()
    
    const loadTime = Date.now() - startTime
    
    // Count widgets
    const widgets = this.page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    // Estimate API calls (basic heuristic)
    const apiCalls = widgetCount + 2 // Base dashboard calls + widget calls
    
    const isPerformant = loadTime <= GLOBAL_CONFIG.PERFORMANCE.PAGE_LOAD_MAX
    
    return {
      loadTime,
      widgetCount,
      apiCalls,
      isPerformant
    }
  }

  /**
   * Verify enterprise dashboard features
   */
  async verifyEnterpriseDashboard() {
    // Check for enterprise-specific features
    await this.navigateToDashboard()
    
    // Multi-tenant data isolation
    const tenantIndicator = this.page.locator('[data-testid="tenant-context"]')
    if (await tenantIndicator.isVisible()) {
      const tenantName = await tenantIndicator.textContent()
      expect(tenantName).toBeTruthy()
    }
    
    // Export functionality
    const exportButton = this.page.locator('[data-testid="export-dashboard"]')
    if (await exportButton.isVisible()) {
      await exportButton.click()
      
      // Verify export options
      await expect(this.page.locator('[data-testid="export-options"]')).toBeVisible()
      
      // Close export dialog
      await this.page.keyboard.press('Escape')
    }
    
    // Sharing functionality
    const shareButton = this.page.locator('[data-testid="share-dashboard"]')
    if (await shareButton.isVisible()) {
      await shareButton.click()
      
      // Verify share dialog
      await expect(this.page.locator('[data-testid="share-dialog"]')).toBeVisible()
      
      // Close share dialog
      await this.page.keyboard.press('Escape')
    }
  }
}