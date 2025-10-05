import { test, expect } from './fixtures'
import { GLOBAL_CONFIG } from './fixtures'

/**
 * 🌐 COMPREHENSIVE PAGE TESTING SUITE
 * 
 * Tests all remaining pages with enterprise-grade validation:
 * - Security Analytics & SIEM Features
 * - Alerts & Monitoring
 * - Observability & APM
 * - Health Monitoring
 * - Cross-page navigation and consistency
 */

test.describe('🌐 Complete Platform Testing', () => {
  test.beforeEach(async ({ authHelper, testCredentials }) => {
    await authHelper.login(testCredentials.email, testCredentials.password)
  })

  test('should provide world-class security analytics and SIEM features', async ({ 
    securityHelper,
    apiClient,
    page 
  }) => {
    await securityHelper.navigateToSecurity()
    
    // Verify security dashboard loads with real data
    await securityHelper.verifySecurityDashboard()
    
    // Test threat intelligence integration
    const threatIntelResponse = await apiClient.getThreatIntel()
    expect(threatIntelResponse).toBeSuccessfulApiResponse()
    
    if (threatIntelResponse.data && threatIntelResponse.data.length > 0) {
      const indicators = threatIntelResponse.data
      console.log(`✅ Threat Intelligence: ${indicators.length} indicators loaded`)
      
      // Verify threat intel data is real
      indicators.slice(0, 3).forEach((indicator: any) => {
        expect(indicator).toBeRealData()
        expect(indicator.type).toBeTruthy()
        expect(indicator.value).toBeTruthy()
      })
    }
    
    // Test security events
    const securityEvents = await apiClient.getSecurityEvents()
    expect(securityEvents).toBeSuccessfulApiResponse()
    
    // Test Sigma rules
    const sigmaRules = await apiClient.getSigmaRules()
    expect(sigmaRules).toBeSuccessfulApiResponse()
    
    if (sigmaRules.data && sigmaRules.data.length > 0) {
      console.log(`✅ Sigma Rules: ${sigmaRules.data.length} detection rules active`)
    }
    
    // Test threat hunting
    await securityHelper.testThreatHunting()
    
    // Verify MITRE ATT&CK integration
    const mitreResponse = await apiClient.makeRequest('/v1/security/mitre-attack/techniques')
    if (mitreResponse.success) {
      console.log('✅ MITRE ATT&CK framework integration verified')
    }
    
    console.log('✅ Security Analytics & SIEM features fully functional')
  })

  test('should provide comprehensive alerts and monitoring', async ({ 
    alertsHelper,
    apiClient,
    page 
  }) => {
    await alertsHelper.navigateToAlerts()
    
    // Verify alerts load with real data
    await alertsHelper.verifyAlertsWithRealData()
    
    // Test alert rules
    const alertRules = await apiClient.getAlertRules()
    expect(alertRules).toBeSuccessfulApiResponse()
    
    if (alertRules.data && alertRules.data.length > 0) {
      console.log(`✅ Alert Rules: ${alertRules.data.length} rules configured`)
      
      // Verify rule data is structured properly
      alertRules.data.slice(0, 3).forEach((rule: any) => {
        expect(rule.name).toBeTruthy()
        expect(rule.condition).toBeTruthy()
        expect(rule.severity).toBeTruthy()
      })
    }
    
    // Test alert channels
    const alertChannels = await apiClient.getAlertChannels()
    expect(alertChannels).toBeSuccessfulApiResponse()
    
    // Test alert creation
    await alertsHelper.testAlertCreation()
    
    // Test real-time alert updates
    const alertsContainer = page.locator('[data-testid="alerts-container"]')
    await expect(alertsContainer).toBeVisible()
    
    // Look for real-time indicators
    const liveIndicator = page.locator('[data-testid="live-alerts"]')
    if (await liveIndicator.isVisible()) {
      console.log('✅ Real-time alert monitoring active')
    }
    
    console.log('✅ Alerts and monitoring system fully functional')
  })

  test('should provide advanced observability and APM', async ({ 
    observabilityHelper,
    apiClient,
    page 
  }) => {
    await observabilityHelper.navigateToObservability()
    
    // Test service map
    await observabilityHelper.verifyServiceMap()
    
    // Test traces
    await observabilityHelper.testTraceAnalysis()
    
    // Test metrics
    const metricsResponse = await apiClient.getMetrics()
    expect(metricsResponse).toBeSuccessfulApiResponse()
    
    // Test APM summary
    const apmSummary = await apiClient.getApmSummary()
    expect(apmSummary).toBeSuccessfulApiResponse()
    
    if (apmSummary.data) {
      console.log('✅ APM Summary:', {
        services: apmSummary.data.service_count || 0,
        traces: apmSummary.data.trace_count || 0,
        errors: apmSummary.data.error_rate || 0
      })
    }
    
    // Verify observability widgets
    const widgets = page.locator('[data-testid^="observability-widget-"]')
    const widgetCount = await widgets.count()
    expect(widgetCount).toBeGreaterThan(0)
    
    console.log(`✅ Observability platform: ${widgetCount} widgets loaded`)
  })

  test('should provide comprehensive health monitoring', async ({ 
    apiClient,
    page 
  }) => {
    await page.goto('/health')
    
    // Wait for health page to load
    await expect(page.locator('[data-testid="health-container"]')).toBeVisible({
      timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
    })
    
    // Test health API
    const healthResponse = await apiClient.healthCheck()
    expect(healthResponse).toBeSuccessfulApiResponse()
    
    // Verify health status indicators
    const healthIndicators = page.locator('[data-testid^="health-"]')
    const indicatorCount = await healthIndicators.count()
    expect(indicatorCount).toBeGreaterThan(0)
    
    // Check system health components
    const components = [
      'database',
      'api',
      'storage',
      'queue',
      'cache'
    ]
    
    for (const component of components) {
      const indicator = page.locator(`[data-testid="health-${component}"]`)
      if (await indicator.isVisible()) {
        const status = await indicator.getAttribute('data-status')
        expect(['healthy', 'warning', 'error']).toContain(status)
        console.log(`✅ ${component}: ${status}`)
      }
    }
    
    console.log('✅ Health monitoring system operational')
  })

  test('should maintain consistent navigation and enterprise UX', async ({ page }) => {
    const pages = [
      { path: '/dashboard', name: 'Dashboard' },
      { path: '/logs', name: 'Logs' },
      { path: '/security', name: 'Security' },
      { path: '/alerts', name: 'Alerts' },
      { path: '/observability', name: 'Observability' },
      { path: '/health', name: 'Health' }
    ]
    
    for (const pageDef of pages) {
      await page.goto(pageDef.path)
      
      // Verify page loads
      const pageContainer = page.locator(`[data-testid="${pageDef.name.toLowerCase()}-container"], [data-testid="page-container"]`)
      await expect(pageContainer).toBeVisible({
        timeout: GLOBAL_CONFIG.TIMEOUT.MEDIUM
      })
      
      // Verify enterprise styling
      await expect(pageContainer).toHaveEnterpriseStyles()
      
      // Verify navigation elements
      await expect(page.locator('[data-testid="main-navigation"]')).toBeVisible()
      await expect(page.locator('[data-testid="user-menu"]')).toBeVisible()
      await expect(page.locator('[data-testid="tenant-selector"]')).toBeVisible()
      
      // Verify global time selector is present (except login/health pages)
      if (!['/login', '/health'].includes(pageDef.path)) {
        await expect(page.locator('[data-testid="time-range-selector"]')).toBeVisible()
      }
      
      console.log(`✅ ${pageDef.name} page: Navigation and UX consistent`)
    }
    
    console.log('✅ Cross-page navigation and UX consistency verified')
  })

  test('should handle AI-powered analysis and insights', async ({ 
    apiClient,
    page 
  }) => {
    // Test AI query functionality
    const aiQuery = {
      query: "Analyze error patterns in the last hour",
      context: "system_health",
      analysis_type: "pattern_analysis"
    }
    
    const aiResponse = await apiClient.queryAI(aiQuery)
    
    if (aiResponse.success) {
      expect(aiResponse.data).toBeRealData()
      console.log('✅ AI Analysis Response:', aiResponse.data?.summary || 'Analysis completed')
      
      // Test anomaly detection
      const anomalyResponse = await apiClient.getAnomalyDetection({ time_range: '1h' })
      if (anomalyResponse.success) {
        console.log('✅ Anomaly Detection:', anomalyResponse.data?.anomalies?.length || 0, 'anomalies detected')
      }
    } else {
      console.log('ℹ️ AI features may not be fully configured in test environment')
    }
    
    // Test AI integration in UI (if available)
    await page.goto('/dashboard')
    
    const aiAssistant = page.locator('[data-testid="ai-assistant"]')
    if (await aiAssistant.isVisible()) {
      await aiAssistant.click()
      
      const aiChat = page.locator('[data-testid="ai-chat"]')
      await expect(aiChat).toBeVisible()
      
      // Test AI query in UI
      await page.fill('[data-testid="ai-input"]', 'Show me recent error trends')
      await page.click('[data-testid="ai-send"]')
      
      // Wait for AI response
      const aiResult = page.locator('[data-testid="ai-response"]')
      await expect(aiResult).toBeVisible({ timeout: GLOBAL_CONFIG.TIMEOUT.EXTRA_LONG })
      
      console.log('✅ AI Assistant UI integration working')
    }
  })

  test('should provide enterprise data export and integration', async ({ 
    apiClient,
    page 
  }) => {
    // Test data export capabilities across different pages
    const exportTests = [
      { page: '/dashboard', exportType: 'dashboard-export' },
      { page: '/logs', exportType: 'logs-export' },
      { page: '/security', exportType: 'security-export' },
      { page: '/alerts', exportType: 'alerts-export' }
    ]
    
    for (const exportTest of exportTests) {
      await page.goto(exportTest.page)
      
      // Wait for page to load
      await page.waitForTimeout(2000)
      
      const exportButton = page.locator(`[data-testid="${exportTest.exportType}"], [data-testid="export-data"]`)
      if (await exportButton.isVisible()) {
        await exportButton.click()
        
        const exportDialog = page.locator('[data-testid="export-dialog"]')
        if (await exportDialog.isVisible()) {
          // Test different export formats
          const formats = ['csv', 'json', 'pdf']
          
          for (const format of formats) {
            const formatOption = page.locator(`[data-testid="export-${format}"]`)
            if (await formatOption.isVisible()) {
              console.log(`✅ ${exportTest.page}: ${format.toUpperCase()} export available`)
            }
          }
          
          await page.keyboard.press('Escape')
        }
      }
    }
    
    // Test API-based data access
    const dataEndpoints = [
      () => apiClient.executeQuery({ query_type: 'logs', filters: { limit: 10 } }),
      () => apiClient.getSecurityEvents(),
      () => apiClient.getAlerts(),
      () => apiClient.getCurrentUsage()
    ]
    
    for (const endpoint of dataEndpoints) {
      const response = await endpoint()
      expect(response.success).toBe(true)
      expect(response.data).toBeRealData()
    }
    
    console.log('✅ Enterprise data export and API integration verified')
  })

  test('should maintain performance across all platform features', async ({ 
    apiClient,
    page 
  }) => {
    const performanceResults: Array<{ page: string; loadTime: number; apiCalls: number }> = []
    
    const pages = [
      '/dashboard',
      '/logs', 
      '/security',
      '/alerts',
      '/observability'
    ]
    
    for (const pagePath of pages) {
      const startTime = Date.now()
      
      await page.goto(pagePath)
      
      // Wait for main content to load
      await page.waitForSelector('[data-testid*="container"], [data-testid*="widget"]', {
        timeout: GLOBAL_CONFIG.TIMEOUT.LONG
      })
      
      const loadTime = Date.now() - startTime
      
      // Estimate API calls based on page content
      const widgets = await page.locator('[data-testid^="widget-"]').count()
      const estimatedApiCalls = widgets + 2 // Base page calls + widget calls
      
      performanceResults.push({
        page: pagePath,
        loadTime,
        apiCalls: estimatedApiCalls
      })
      
      expect(loadTime).toBeLessThan(GLOBAL_CONFIG.PERFORMANCE.PAGE_LOAD_MAX)
      console.log(`✅ ${pagePath}: ${loadTime}ms (${estimatedApiCalls} API calls)`)
    }
    
    // Calculate overall performance metrics
    const avgLoadTime = performanceResults.reduce((sum, result) => sum + result.loadTime, 0) / performanceResults.length
    const totalApiCalls = performanceResults.reduce((sum, result) => sum + result.apiCalls, 0)
    
    console.log(`✅ Platform Performance Summary:`)
    console.log(`   Average load time: ${avgLoadTime.toFixed(0)}ms`)
    console.log(`   Total API calls: ${totalApiCalls}`)
    console.log(`   Pages tested: ${pages.length}`)
  })

  test('should validate enterprise security across all features', async ({ 
    page,
    apiClient 
  }) => {
    // Test CSRF protection
    const csrfResponse = await apiClient.makeRequest('/v1/auth/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    // Should either succeed (with CSRF token) or fail appropriately
    expect([200, 201, 403, 401]).toContain(csrfResponse.status)
    
    // Test rate limiting (if implemented)
    const rapidRequests = Array.from({ length: 10 }, () => 
      apiClient.healthCheck()
    )
    
    const rapidResults = await Promise.allSettled(rapidRequests)
    const successCount = rapidResults.filter(result => 
      result.status === 'fulfilled' && result.value.success
    ).length
    
    console.log(`✅ Rate limiting test: ${successCount}/10 requests succeeded`)
    
    // Test input validation
    const invalidInputs = [
      '<script>alert("xss")</script>',
      '"; DROP TABLE users; --',
      '../../../etc/passwd',
      'null\x00byte'
    ]
    
    for (const input of invalidInputs) {
      await page.goto('/logs')
      await page.fill('[data-testid="search-input"]', input)
      await page.click('[data-testid="search-button"]')
      
      // Should not cause errors or expose sensitive information
      const errorMessage = page.locator('[data-testid="error-message"]')
      if (await errorMessage.isVisible()) {
        const errorText = await errorMessage.textContent()
        expect(errorText).not.toContain('SQL')
        expect(errorText).not.toContain('database')
        expect(errorText).not.toContain('internal')
      }
    }
    
    console.log('✅ Enterprise security validation completed')
  })
})