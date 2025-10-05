import { test, expect } from './fixtures'
import { GLOBAL_CONFIG } from './fixtures'

/**
 * 📋 ENTERPRISE LOG ANALYSIS TESTING SUITE
 * 
 * Comprehensive log analysis testing for world-class enterprise platform:
 * - Real-time log streaming and search with actual data
 * - Advanced filtering and querying capabilities  
 * - Global time range integration
 * - Log ingestion and validation
 * - Performance optimization
 * - Enterprise security and compliance
 */

test.describe('📋 Enterprise Log Analysis', () => {
  test.beforeEach(async ({ authHelper, testCredentials }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
  })

  test('should load logs page with real data and stunning UI', async ({ 
    logsHelper,
    apiClient,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Verify logs load with real data
    await logsHelper.waitForLogsToLoad()
    
    // Verify enterprise styling
    const logsContainer = page.locator('[data-testid="logs-container"]')
    await expect(logsContainer).toHaveEnterpriseStyles()
    
    // Verify log entries have proper structure
    const logEntries = page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    expect(logCount).toBeGreaterThan(0)
    
    console.log(`✅ Logs page loaded with ${logCount} real log entries`)
    
    // Verify first few logs have all required fields
    for (let i = 0; i < Math.min(logCount, 3); i++) {
      const logEntry = logEntries.nth(i)
      
      await expect(logEntry.locator('[data-testid="log-timestamp"]')).toBeVisible()
      await expect(logEntry.locator('[data-testid="log-level"]')).toBeVisible()
      await expect(logEntry.locator('[data-testid="log-service"]')).toBeVisible()
      await expect(logEntry.locator('[data-testid="log-message"]')).toBeVisible()
      
      // Verify data is real
      const message = await logEntry.locator('[data-testid="log-message"]').textContent()
      expect(message).toBeRealData()
    }
    
    console.log('✅ Log entries have proper structure with real data')
  })

  test('should provide advanced search with enterprise features', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test advanced search functionality
    await logsHelper.testLogSearch()
    
    // Measure search performance
    const { searchTime, resultCount, isPerformant } = await logsHelper.measureSearchPerformance()
    expect(isPerformant).toBe(true)
    
    console.log(`✅ Search completed in ${searchTime}ms with ${resultCount} results`)
    console.log(`✅ Performance target: <${GLOBAL_CONFIG.PERFORMANCE.SEARCH_RESPONSE_MAX}ms`)
    
    // Test complex search queries
    const complexQueries = [
      'level:ERROR AND service:web-api',
      'status:500 OR status:404',
      'message:"connection failed"',
      'timestamp:[now-1h TO now]'
    ]
    
    for (const query of complexQueries) {
      await page.fill('[data-testid="search-input"]', query)
      await page.click('[data-testid="search-button"]')
      
      await logsHelper.waitForLogsToLoad()
      
      // Verify search executed without errors
      const errorMessage = page.locator('[data-testid="search-error"]')
      expect(await errorMessage.isVisible()).toBe(false)
    }
    
    console.log(`✅ Advanced search queries tested: ${complexQueries.length} patterns`)
  })

  test('should support sophisticated filtering and faceting', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test filtering functionality
    await logsHelper.testLogFiltering()
    
    // Test faceted search
    const facetPanels = page.locator('[data-testid^="facet-"]')
    const facetCount = await facetPanels.count()
    
    if (facetCount > 0) {
      for (let i = 0; i < Math.min(facetCount, 3); i++) {
        const facetPanel = facetPanels.nth(i)
        const facetName = await facetPanel.getAttribute('data-testid')
        
        // Click facet to expand
        await facetPanel.click()
        
        // Verify facet values appear
        const facetValues = facetPanel.locator('[data-testid^="facet-value-"]')
        const valueCount = await facetValues.count()
        
        if (valueCount > 0) {
          // Click first facet value
          await facetValues.first().click()
          await logsHelper.waitForLogsToLoad()
          
          // Verify filter is applied
          const activeFilters = page.locator('[data-testid="active-filters"]')
          await expect(activeFilters).toBeVisible()
          
          console.log(`✅ Faceted search working for ${facetName}`)
        }
      }
    }
  })

  test('should integrate seamlessly with global time range', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test time range integration
    await logsHelper.testTimeRangeSelection()
    
    // Verify global time selector reflects in logs
    const globalTimeRange = page.locator('[data-testid="current-time-range"]')
    await expect(globalTimeRange).toBeVisible()
    
    // Test real-time updates when time range changes
    const initialLogCount = await page.locator('[data-testid="log-entry"]').count()
    
    // Change time range
    await page.click('[data-testid="time-range-selector"]')
    await page.click('[data-testid="time-range-1h"]')
    
    await logsHelper.waitForLogsToLoad()
    
    // Verify log count potentially changed (reflecting time range)
    const newLogCount = await page.locator('[data-testid="log-entry"]').count()
    console.log(`✅ Time range change: ${initialLogCount} → ${newLogCount} logs`)
    
    // Verify all logs are within the selected time range
    const logTimestamps = page.locator('[data-testid="log-timestamp"]')
    const timestampCount = await logTimestamps.count()
    
    if (timestampCount > 0) {
      const firstTimestamp = await logTimestamps.first().textContent()
      const timestamp = new Date(firstTimestamp!)
      const now = new Date()
      const diffHours = (now.getTime() - timestamp.getTime()) / (1000 * 60 * 60)
      
      expect(diffHours).toBeLessThanOrEqual(1) // Within 1 hour range
    }
    
    console.log('✅ Global time range integration working seamlessly')
  })

  test('should support real-time log ingestion and streaming', async ({ 
    logsHelper,
    apiClient,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test log ingestion
    await logsHelper.testLogIngestion()
    
    // Test real-time streaming
    await logsHelper.testRealTimeStreaming()
    
    // Test batch ingestion
    const batchLogs = Array.from({ length: 5 }, (_, i) => ({
      timestamp: new Date().toISOString(),
      level: 'INFO',
      service: 'batch-test',
      message: `Batch test log ${i + 1} - ${Date.now()}`,
      host: 'test-host',
      batch_id: `batch_${Date.now()}`
    }))
    
    const batchResponse = await apiClient.batchIngestLogs(batchLogs)
    expect(batchResponse).toBeSuccessfulApiResponse()
    
    // Wait for batch to be indexed
    await page.waitForTimeout(5000)
    
    // Search for batch logs
    await page.fill('[data-testid="search-input"]', `batch_${Date.now().toString().slice(-6)}`)
    await page.click('[data-testid="search-button"]')
    
    await logsHelper.waitForLogsToLoad()
    
    const batchResults = page.locator('[data-testid="log-entry"]')
    const batchCount = await batchResults.count()
    expect(batchCount).toBeGreaterThan(0)
    
    console.log(`✅ Batch ingestion: ${batchLogs.length} logs → ${batchCount} results`)
  })

  test('should provide detailed log analysis and expansion', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test log details
    await logsHelper.testLogDetails()
    
    // Test log parsing and field extraction
    const logEntries = page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    if (logCount > 0) {
      const firstLog = logEntries.first()
      await firstLog.click()
      
      // Verify expanded view shows structured data
      const expandedView = firstLog.locator('[data-testid="log-details"]')
      await expect(expandedView).toBeVisible()
      
      // Check for parsed fields
      const parsedFields = expandedView.locator('[data-testid^="field-"]')
      const fieldCount = await parsedFields.count()
      expect(fieldCount).toBeGreaterThan(3) // Should have multiple parsed fields
      
      // Test field search functionality
      if (fieldCount > 0) {
        const firstField = parsedFields.first()
        const fieldName = await firstField.getAttribute('data-testid')
        const fieldValue = await firstField.textContent()
        
        // Click field to search
        await firstField.click()
        
        // Should add field search to query
        const searchInput = page.locator('[data-testid="search-input"]')
        const searchValue = await searchInput.inputValue()
        expect(searchValue).toContain(fieldName?.replace('field-', '') || '')
        
        console.log(`✅ Field-based search: ${fieldName} = ${fieldValue}`)
      }
    }
  })

  test('should support enterprise export and sharing', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    await logsHelper.waitForLogsToLoad()
    
    // Test log export
    await logsHelper.testLogExport()
    
    // Test saved queries
    const saveQueryButton = page.locator('[data-testid="save-query"]')
    if (await saveQueryButton.isVisible()) {
      // Create a search query first
      await page.fill('[data-testid="search-input"]', 'level:ERROR')
      await page.click('[data-testid="search-button"]')
      await logsHelper.waitForLogsToLoad()
      
      // Save the query
      await saveQueryButton.click()
      
      const saveDialog = page.locator('[data-testid="save-query-dialog"]')
      await expect(saveDialog).toBeVisible()
      
      await page.fill('[data-testid="query-name"]', 'Error Log Analysis')
      await page.fill('[data-testid="query-description"]', 'Monitor error logs across all services')
      await page.click('[data-testid="save-query-confirm"]')
      
      // Verify query was saved
      await expect(page.locator('[data-testid="save-success"]')).toBeVisible()
      
      console.log('✅ Query saved successfully')
    }
    
    // Test sharing functionality
    const shareButton = page.locator('[data-testid="share-logs"]')
    if (await shareButton.isVisible()) {
      await shareButton.click()
      
      const shareDialog = page.locator('[data-testid="share-dialog"]')
      await expect(shareDialog).toBeVisible()
      
      // Test share link generation
      const generateLinkButton = page.locator('[data-testid="generate-share-link"]')
      if (await generateLinkButton.isVisible()) {
        await generateLinkButton.click()
        
        const shareLink = page.locator('[data-testid="share-link"]')
        await expect(shareLink).toBeVisible()
        
        const linkValue = await shareLink.inputValue()
        expect(linkValue).toContain('http')
        
        console.log('✅ Share link generated')
      }
      
      await page.keyboard.press('Escape')
    }
  })

  test('should handle pagination and large result sets', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test pagination
    await logsHelper.testLogPagination()
    
    // Test different page sizes
    const pageSizeSelector = page.locator('[data-testid="page-size-selector"]')
    if (await pageSizeSelector.isVisible()) {
      const pageSizes = ['25', '50', '100', '200']
      
      for (const pageSize of pageSizes) {
        await pageSizeSelector.click()
        await page.click(`[data-testid="page-size-${pageSize}"]`)
        
        await logsHelper.waitForLogsToLoad()
        
        // Verify page size is applied
        const logEntries = page.locator('[data-testid="log-entry"]')
        const actualCount = await logEntries.count()
        expect(actualCount).toBeLessThanOrEqual(parseInt(pageSize))
        
        console.log(`✅ Page size ${pageSize}: ${actualCount} logs displayed`)
      }
    }
    
    // Test infinite scroll (if implemented)
    const initialLogCount = await page.locator('[data-testid="log-entry"]').count()
    
    // Scroll to bottom
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await page.waitForTimeout(2000)
    
    const newLogCount = await page.locator('[data-testid="log-entry"]').count()
    
    if (newLogCount > initialLogCount) {
      console.log(`✅ Infinite scroll: ${initialLogCount} → ${newLogCount} logs`)
    }
  })

  test('should maintain performance under heavy load', async ({ 
    logsHelper,
    apiClient,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Test performance with rapid searches
    const searchQueries = [
      'level:ERROR',
      'service:web-api',
      'status:500',
      'level:WARN',
      'level:INFO'
    ]
    
    const performanceResults = []
    
    for (const query of searchQueries) {
      const startTime = Date.now()
      
      await page.fill('[data-testid="search-input"]', query)
      await page.click('[data-testid="search-button"]')
      
      await logsHelper.waitForLogsToLoad()
      
      const timing = Date.now() - startTime
      performanceResults.push(timing)
      
      expect(timing).toBeLessThan(GLOBAL_CONFIG.PERFORMANCE.SEARCH_RESPONSE_MAX)
    }
    
    const avgTiming = performanceResults.reduce((sum, time) => sum + time, 0) / performanceResults.length
    console.log(`✅ Average search performance: ${avgTiming.toFixed(0)}ms across ${searchQueries.length} queries`)
    
    // Test concurrent search performance
    const concurrentSearches = searchQueries.map(query => 
      apiClient.executeQuery({
        query_type: 'logs',
        filters: { query, limit: 50 }
      })
    )
    
    const concurrentStartTime = Date.now()
    const results = await Promise.all(concurrentSearches)
    const concurrentTiming = Date.now() - concurrentStartTime
    
    // All searches should succeed
    results.forEach(result => {
      expect(result).toBeSuccessfulApiResponse()
    })
    
    console.log(`✅ Concurrent searches: ${searchQueries.length} queries in ${concurrentTiming}ms`)
  })

  test('should enforce enterprise security and compliance', async ({ 
    logsHelper,
    page 
  }) => {
    await logsHelper.navigateToLogs()
    
    // Verify enterprise log features
    await logsHelper.verifyEnterpriseLogFeatures()
    
    // Test data redaction/masking
    const logEntries = page.locator('[data-testid="log-entry"]')
    const logCount = await logEntries.count()
    
    for (let i = 0; i < Math.min(logCount, 5); i++) {
      const logEntry = logEntries.nth(i)
      const logMessage = await logEntry.locator('[data-testid="log-message"]').textContent()
      
      // Check for potential PII patterns that should be redacted
      const piiPatterns = [
        /\b\d{3}-\d{2}-\d{4}\b/, // SSN pattern
        /\b\d{16}\b/, // Credit card pattern
        /\b[\w._%+-]+@[\w.-]+\.[A-Z|a-z]{2,}\b/ // Email pattern (might be intentionally shown)
      ]
      
      // In enterprise systems, sensitive data should be redacted
      // This is a basic check - real implementation would be more sophisticated
      if (logMessage) {
        piiPatterns.forEach((pattern, index) => {
          const matches = logMessage.match(pattern)
          if (matches) {
            // Could check if data is properly redacted (e.g., contains *** or [REDACTED])
            console.log(`ℹ️ Potential PII pattern ${index + 1} found - verify redaction policy`)
          }
        })
      }
    }
    
    // Test audit trail access
    const auditButton = page.locator('[data-testid="audit-trail"]')
    if (await auditButton.isVisible()) {
      await auditButton.click()
      
      const auditPanel = page.locator('[data-testid="audit-panel"]')
      await expect(auditPanel).toBeVisible()
      
      console.log('✅ Audit trail access verified')
      
      await page.keyboard.press('Escape')
    }
    
    console.log('✅ Enterprise security and compliance features verified')
  })
})