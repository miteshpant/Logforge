import { chromium, FullConfig } from '@playwright/test'

/**
 * Global Setup for Logforge Enterprise Testing
 * 
 * Prepares the testing environment:
 * - Verifies API connectivity
 * - Sets up authentication state
 * - Validates test data
 * - Configures test environment
 */

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting Logforge Enterprise Testing Suite')
  console.log('=' .repeat(60))
  
  const browser = await chromium.launch()
  const page = await browser.newPage()
  
  try {
    // 1. Verify API is accessible
    console.log('🔍 Verifying API connectivity...')
    const healthResponse = await page.request.get('http://localhost:7080/v1/health')
    
    if (!healthResponse.ok()) {
      throw new Error(`API health check failed: ${healthResponse.status()}`)
    }
    
    console.log('✅ API connectivity verified')
    
    // 2. Set up authentication
    console.log('🔐 Setting up authentication...')
    const loginResponse = await page.request.post('http://localhost:7080/v1/auth/login', {
      data: {
        email: 'testuser@testorg.com',
        password: 'TestUser123!'
      }
    })
    
    if (!loginResponse.ok()) {
      console.log('⚠️ Authentication setup failed - tests will handle login individually')
    } else {
      console.log('✅ Authentication verified')
      
      // Save authentication state
      await page.context().storageState({ path: 'tests/auth-state.json' })
      console.log('✅ Authentication state saved')
    }
    
    // 3. Verify test data availability
    console.log('📊 Verifying test data availability...')
    
    const endpoints = [
      { path: '/v1/dashboards', name: 'Dashboards' },
      { path: '/v1/query/advanced', name: 'Query Engine', method: 'POST', body: { query_type: 'logs', filters: { limit: 1 } } },
      { path: '/v1/security/dashboard', name: 'Security Analytics' },
      { path: '/v1/alerts', name: 'Alerts' },
      { path: '/v1/observability/service-map', name: 'Observability' }
    ]
    
    let dataAvailability = 0
    
    for (const endpoint of endpoints) {
      try {
        const response = endpoint.method === 'POST' 
          ? await page.request.post(`http://localhost:7080${endpoint.path}`, { data: endpoint.body })
          : await page.request.get(`http://localhost:7080${endpoint.path}`)
        
        if (response.ok()) {
          dataAvailability++
          console.log(`✅ ${endpoint.name}: Available`)
        } else {
          console.log(`⚠️ ${endpoint.name}: Limited data (${response.status()})`)
        }
      } catch (error) {
        console.log(`❌ ${endpoint.name}: Error - ${error}`)
      }
    }
    
    console.log(`📈 Data availability: ${dataAvailability}/${endpoints.length} endpoints ready`)
    
    // 4. Environment validation
    console.log('🔧 Validating test environment...')
    
    const userAgent = await page.evaluate(() => navigator.userAgent)
    const viewport = page.viewportSize()
    
    console.log(`   Browser: ${userAgent.split(' ').pop()}`)
    console.log(`   Viewport: ${viewport?.width}x${viewport?.height}`)
    console.log(`   Base URL: ${config.projects[0]?.use?.baseURL || 'http://localhost:3000'}`)
    
    // 5. Performance baseline
    console.log('⚡ Establishing performance baseline...')
    
    const startTime = Date.now()
    await page.goto('http://localhost:3000/login')
    const pageLoadTime = Date.now() - startTime
    
    console.log(`   Page load time: ${pageLoadTime}ms`)
    
    if (pageLoadTime > 5000) {
      console.log('⚠️ Slow page load detected - performance tests may need adjustment')
    }
    
  } catch (error) {
    console.error('❌ Global setup failed:', error)
    throw error
  } finally {
    await browser.close()
  }
  
  console.log('=' .repeat(60))
  console.log('✅ Enterprise testing environment ready!')
  console.log('🎯 Testing Features:')
  console.log('   • Authentication & Session Management')
  console.log('   • Real-time Dashboard Analytics') 
  console.log('   • Advanced Log Search & Analysis')
  console.log('   • Security Analytics & SIEM')
  console.log('   • Alert Management & Monitoring')
  console.log('   • Observability & APM')
  console.log('   • Enterprise Performance & Security')
  console.log('=' .repeat(60))
}

export default globalSetup