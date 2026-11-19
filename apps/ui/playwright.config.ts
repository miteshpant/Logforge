import { defineConfig, devices } from '@playwright/test'

/**
 * Logforge UI - Enterprise E2E Testing Configuration
 * 
 * This configuration tests the complete Logforge UI ecosystem:
 * - All 9 main pages (login, dashboard, logs, security, alerts, observability, etc.)
 * - 15+ API integrations with real backend calls
 * - Enterprise features: authentication, multi-tenancy, real-time updates
 * - Mobile responsiveness and accessibility
 * - Performance and reliability testing
 */

export default defineConfig({
  // Test directory
  testDir: './tests',
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['junit', { outputFile: 'test-results/results.xml' }],
    ['line']
  ],
  
  // Shared settings for all the projects below
  use: {
    // Base URL for all tests
    // The compose stack serves the UI on :3001; `npm run dev` uses :3000.
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Record video on failure
    video: 'retain-on-failure',
    
    // Take screenshot on failure
    screenshot: 'only-on-failure',
    
    // Global timeout for each action (e.g., click, fill, etc.)
    actionTimeout: 30000,
    
    // Global timeout for navigation (e.g., page.goto)
    navigationTimeout: 30000,
    
    // Ignore HTTPS errors
    ignoreHTTPSErrors: true,
    
    // Extra HTTP headers
    extraHTTPHeaders: {
      'Accept': 'application/json',
      'Accept-Language': 'en-US,en;q=0.9'
    }
  },

  // Global setup and teardown
  globalSetup: './tests/global-setup.ts',

  // Configure projects for major browsers
  projects: [
    // Setup project for authentication
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
      teardown: 'cleanup'
    },
    
    // Cleanup project
    {
      name: 'cleanup',
      testMatch: /.*\.teardown\.ts/
    },

    // Desktop Chrome - Primary testing environment
    {
      name: 'chromium',
      use: { 
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 }
      },
      dependencies: ['setup']
    },

    // Desktop Firefox - Cross-browser compatibility
    {
      name: 'firefox',
      use: { 
        ...devices['Desktop Firefox'],
        viewport: { width: 1920, height: 1080 }
      },
      dependencies: ['setup']
    },

    // Desktop Safari - WebKit engine testing
    {
      name: 'webkit',
      use: { 
        ...devices['Desktop Safari'],
        viewport: { width: 1920, height: 1080 }
      },
      dependencies: ['setup']
    },

    // Mobile testing - Enterprise mobile experience
    {
      name: 'Mobile Chrome',
      use: { 
        ...devices['Pixel 5']
      },
      dependencies: ['setup']
    },
    
    {
      name: 'Mobile Safari',
      use: { 
        ...devices['iPhone 12']
      },
      dependencies: ['setup']
    },

    // Tablet testing - Dashboard optimization
    {
      name: 'Tablet',
      use: { 
        ...devices['iPad Pro']
      },
      dependencies: ['setup']
    }
  ],

  // Run your local dev server before starting the tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
    env: {
      NODE_ENV: 'test'
    }
  },

  // Global test timeout
  timeout: 60000,

  // Expect timeout for assertions
  expect: {
    timeout: 15000
  },

  // Test output directory
  outputDir: 'test-results/',

  // Preserve output between runs
  preserveOutput: 'failures-only'
})