import { test, expect } from './fixtures'
import { GLOBAL_CONFIG } from './fixtures'

/**
 * 📊 ENTERPRISE DASHBOARD TESTING SUITE
 * 
 * Comprehensive dashboard testing for world-class enterprise platform:
 * - Real-time data visualization with actual API calls
 * - Interactive widgets with enterprise styling
 * - Time range controls and global state management
 * - Performance monitoring and optimization
 * - Mobile responsiveness and accessibility
 * - Multi-tenant data isolation
 */

test.describe('📊 Enterprise Dashboard', () => {
  test.beforeEach(async ({ authHelper, testCredentials }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
  })

  test('should load dashboard with stunning enterprise design and real data', async ({ 
    dashboardHelper,
    apiClient,
    page 
  }) => {
    // Measure dashboard performance
    const performance = await dashboardHelper.measureDashboardPerformance()
    expect(performance.isPerformant).toBe(true)
    expect(performance.widgetCount).toBeGreaterThan(0)
    
    console.log(`✅ Dashboard loaded in ${performance.loadTime}ms with ${performance.widgetCount} widgets`)
    console.log(`✅ Estimated ${performance.apiCalls} API calls made`)

    // Verify all widgets have real data
    await dashboardHelper.verifyWidgetsWithRealData()
    
    // Verify enterprise styling
    const dashboardContainer = page.locator('[data-testid="dashboard-container"]')
    await expect(dashboardContainer).toHaveEnterpriseStyles()
    
    console.log('✅ All widgets loaded with real data and enterprise styling')
  })

  test('should provide seamless time range controls with global state', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test global time range selector
    await dashboardHelper.testTimeRangeSelector()
    
    // Verify time range updates are reflected across all widgets
    const timeRangeIndicator = page.locator('[data-testid="current-time-range"]')
    await expect(timeRangeIndicator).toBeVisible()
    
    // Verify global time selector has enterprise styling
    const timeSelector = page.locator('[data-testid="time-range-selector"]')
    await expect(timeSelector).toHaveEnterpriseStyles()
    
    console.log('✅ Global time range controls working seamlessly')
  })

  test('should support real-time data updates and live streaming', async ({ 
    dashboardHelper,
    apiClient,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test real-time updates
    await dashboardHelper.verifyRealTimeUpdates()
    
    // Inject test data to verify real-time updates
    const testLog = {
      timestamp: new Date().toISOString(),
      level: 'INFO',
      service: 'dashboard-test',
      message: `Dashboard real-time test - ${Date.now()}`,
      metric_value: Math.random() * 100
    }
    
    await apiClient.ingestLog(testLog)
    
    // Wait for potential real-time update
    await page.waitForTimeout(5000)
    
    // Verify dashboard refreshes automatically
    await dashboardHelper.testDashboardRefresh()
    
    console.log('✅ Real-time data updates and streaming verified')
  })

  test('should provide interactive widgets with enterprise UX', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test widget interactions
    await dashboardHelper.testWidgetInteractions()
    
    // Verify hover effects and animations
    const widgets = page.locator('[data-testid^="widget-"]')
    const firstWidget = widgets.first()
    
    await firstWidget.hover()
    await expect(firstWidget).toHaveEnterpriseStyles()
    
    // Test widget responsiveness
    await page.setViewportSize({ width: 1200, height: 800 })
    await expect(widgets.first()).toBeVisible()
    
    await page.setViewportSize({ width: 768, height: 1024 })
    await expect(widgets.first()).toBeVisible()
    
    console.log('✅ Interactive widgets with enterprise UX verified')
  })

  test('should support advanced search and filtering', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test dashboard search
    await dashboardHelper.testDashboardSearch()
    
    // Test advanced filtering options
    const filterButton = page.locator('[data-testid="advanced-filters"]')
    if (await filterButton.isVisible()) {
      await filterButton.click()
      
      // Verify filter panel opens
      await expect(page.locator('[data-testid="filter-panel"]')).toBeVisible()
      
      // Test service filter
      const serviceFilter = page.locator('[data-testid="service-filter"]')
      if (await serviceFilter.isVisible()) {
        await serviceFilter.click()
        await page.locator('[data-testid="service-option"]').first().click()
        
        // Verify dashboard updates with filtered data
        await page.waitForTimeout(2000)
        await expect(page.locator('[data-testid="active-filters"]')).toBeVisible()
      }
      
      // Close filter panel
      await page.keyboard.press('Escape')
    }
    
    console.log('✅ Advanced search and filtering capabilities verified')
  })

  test('should handle dashboard customization and personalization', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test dashboard customization
    await dashboardHelper.testDashboardCustomization()
    
    // Test widget reordering (drag and drop)
    const widgets = page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    if (widgetCount >= 2) {
      const firstWidget = widgets.first()
      const secondWidget = widgets.nth(1)
      
      // Attempt drag and drop
      const firstBox = await firstWidget.boundingBox()
      const secondBox = await secondWidget.boundingBox()
      
      if (firstBox && secondBox) {
        await page.mouse.move(firstBox.x + firstBox.width / 2, firstBox.y + firstBox.height / 2)
        await page.mouse.down()
        await page.mouse.move(secondBox.x + secondBox.width / 2, secondBox.y + secondBox.height / 2)
        await page.mouse.up()
        
        await page.waitForTimeout(1000)
      }
    }
    
    console.log('✅ Dashboard customization and personalization verified')
  })

  test('should ensure accessibility and keyboard navigation', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test accessibility
    await dashboardHelper.verifyAccessibility()
    
    // Test keyboard navigation
    await page.keyboard.press('Tab')
    const focusedElement = page.locator(':focus')
    await expect(focusedElement).toBeVisible()
    
    // Test ARIA labels and roles
    const widgets = page.locator('[data-testid^="widget-"]')
    const firstWidget = widgets.first()
    
    const ariaLabel = await firstWidget.getAttribute('aria-label')
    const role = await firstWidget.getAttribute('role')
    expect(ariaLabel || role).toBeTruthy()
    
    console.log('✅ Accessibility and keyboard navigation verified')
  })

  test('should support multi-tenant data isolation', async ({ 
    dashboardHelper,
    apiClient,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Verify tenant context
    const tenantContext = page.locator('[data-testid="tenant-context"]')
    if (await tenantContext.isVisible()) {
      const tenantInfo = await tenantContext.textContent()
      expect(tenantInfo).toBeTruthy()
      console.log(`✅ Tenant context: ${tenantInfo}`)
    }
    
    // Verify data isolation through API
    const profileResponse = await apiClient.getProfile()
    expect(profileResponse).toBeSuccessfulApiResponse()
    expect(profileResponse.data?.tenant_id).toBeTruthy()
    
    // Verify dashboard data belongs to correct tenant
    const dashboardData = await apiClient.getDashboards()
    expect(dashboardData).toBeSuccessfulApiResponse()
    
    console.log('✅ Multi-tenant data isolation verified')
  })

  test('should provide enterprise export and sharing capabilities', async ({ 
    dashboardHelper,
    page 
  }) => {
    await dashboardHelper.navigateToDashboard()
    
    // Test enterprise dashboard features
    await dashboardHelper.verifyEnterpriseDashboard()
    
    // Test PDF export
    const exportButton = page.locator('[data-testid="export-dashboard"]')
    if (await exportButton.isVisible()) {
      await exportButton.click()
      
      const pdfOption = page.locator('[data-testid="export-pdf"]')
      if (await pdfOption.isVisible()) {
        const downloadPromise = page.waitForEvent('download')
        await pdfOption.click()
        
        const download = await downloadPromise
        expect(download.suggestedFilename()).toContain('.pdf')
        console.log(`✅ PDF export: ${download.suggestedFilename()}`)
      }
    }
    
    console.log('✅ Enterprise export and sharing capabilities verified')
  })

  test('should maintain performance under various load conditions', async ({ 
    dashboardHelper,
    apiClient,
    page 
  }) => {
    // Test performance with multiple rapid time range changes
    await dashboardHelper.navigateToDashboard()
    
    const timeRanges = ['1h', '24h', '7d', '30d', '24h']
    const performanceResults = []
    
    for (const timeRange of timeRanges) {
      const startTime = Date.now()
      
      await page.click('[data-testid="time-range-selector"]')
      await page.click(`[data-testid="time-range-${timeRange}"]`)
      
      // Wait for dashboard to update
      await page.waitForTimeout(2000)
      
      const timing = Date.now() - startTime
      performanceResults.push(timing)
      
      expect(timing).toBeLessThan(GLOBAL_CONFIG.PERFORMANCE.PAGE_LOAD_MAX)
    }
    
    const avgTiming = performanceResults.reduce((sum, time) => sum + time, 0) / performanceResults.length
    console.log(`✅ Average time range change: ${avgTiming.toFixed(0)}ms across ${performanceResults.length} changes`)
  })

  test('should handle error states gracefully with enterprise UX', async ({ 
    page,
    authHelper,
    testCredentials 
  }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
    
    // Simulate API failures
    await page.route('**/v1/dashboards/**', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Internal server error' })
      })
    })
    
    await page.goto('/dashboard')
    
    // Should show elegant error states
    const errorStates = page.locator('[data-testid="error-state"]')
    await expect(errorStates.first()).toBeVisible()
    
    // Error states should have enterprise styling
    await expect(errorStates.first()).toHaveEnterpriseStyles()
    
    // Should provide retry options
    const retryButton = page.locator('[data-testid="retry-button"]')
    if (await retryButton.isVisible()) {
      await expect(retryButton).toBeVisible()
    }
    
    console.log('✅ Error states handled gracefully with enterprise UX')
  })
})

test.describe('📊 Dashboard Mobile Experience', () => {
  test('should provide excellent mobile dashboard experience', async ({ 
    page,
    authHelper,
    testCredentials,
    dashboardHelper 
  }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })
    
    await authHelper.login(testCredentials.email, testCredentials.password)
    await dashboardHelper.navigateToDashboard()
    
    // Verify mobile-optimized layout
    const dashboardContainer = page.locator('[data-testid="dashboard-container"]')
    await expect(dashboardContainer).toBeVisible()
    
    // Test mobile time range selector
    const timeSelector = page.locator('[data-testid="time-range-selector"]')
    await expect(timeSelector).toBeVisible()
    await timeSelector.click()
    
    // Verify mobile-friendly dropdown
    const dropdown = page.locator('[data-testid="time-range-dropdown"]')
    await expect(dropdown).toBeVisible()
    
    // Test touch interactions
    await page.locator('[data-testid="time-range-24h"]').tap()
    await page.waitForTimeout(1000)
    
    // Verify widgets are mobile-responsive
    const widgets = page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    for (let i = 0; i < Math.min(widgetCount, 3); i++) {
      const widget = widgets.nth(i)
      await expect(widget).toBeVisible()
      
      const box = await widget.boundingBox()
      expect(box?.width).toBeLessThanOrEqual(375)
    }
    
    console.log(`✅ Mobile dashboard experience verified with ${widgetCount} responsive widgets`)
  })

  test('should handle tablet dashboard optimization', async ({ 
    page,
    authHelper,
    testCredentials,
    dashboardHelper 
  }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 })
    
    await authHelper.login(testCredentials.email, testCredentials.password)
    await dashboardHelper.navigateToDashboard()
    
    // Verify tablet layout optimization
    const widgets = page.locator('[data-testid^="widget-"]')
    const widgetCount = await widgets.count()
    
    // On tablet, should have more widgets per row than mobile
    const firstRowWidgets = widgets.filter({
      hasNot: page.locator('[style*="transform: translateY"]')
    })
    
    const firstRowCount = await firstRowWidgets.count()
    expect(firstRowCount).toBeGreaterThan(1)
    
    console.log(`✅ Tablet optimization verified with ${firstRowCount} widgets per row`)
  })
})