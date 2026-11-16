import { test, expect } from '@playwright/test';

test.describe('User Story 1: Platform Health Monitoring', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses for testing
    await page.route('**/v1/auth/login', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-token-123',
          user: {
            id: 'admin-1',
            email: 'admin@example.com',
            full_name: 'Admin User',
            role: 'admin'
          }
        })
      });
    });

    await page.route('**/health', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          services: {
            api: 'healthy',
            database: 'healthy',
            clickhouse: 'healthy',
            storage: 'healthy'
          }
        })
      });
    });

    await page.route('**/v1/tenants', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tenants: [
            { id: 'tenant-1', status: 'active', type: 'enterprise' },
            { id: 'tenant-2', status: 'active', type: 'smb' },
            { id: 'tenant-3', status: 'inactive', type: 'startup' }
          ]
        })
      });
    });

    await page.route('**/v1/analytics/usage-trends', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_revenue: 127450,
          total_data: '15.2TB'
        })
      });
    });
  });

  test('Admin logs into Admin Interface', async ({ page }) => {
    // Navigate to admin UI
    await page.goto('http://localhost:3002');

    // Should redirect to login page
    await expect(page).toHaveURL('http://localhost:3002/login');
    
    // Verify login page elements
    await expect(page.locator('h1')).toContainText('Logforge Admin');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    
    // Fill in credentials
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    
    // Click login
    await page.click('button[type="submit"]');
    
    // Should redirect to dashboard
    await expect(page).toHaveURL('http://localhost:3002/');
  });

  test('Admin views Platform Dashboard with statistics', async ({ page }) => {
    // Login first
    await page.goto('http://localhost:3002/login');
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    await page.click('button[type="submit"]');
    
    // Wait for dashboard to load
    await page.waitForURL('http://localhost:3002/');
    
    // Verify dashboard title
    await expect(page.locator('h1')).toContainText('Platform Dashboard');
    
    // Verify platform statistics cards are present
    await expect(page.locator('text=Active Tenants')).toBeVisible();
    await expect(page.locator('text=Monthly Revenue')).toBeVisible();
    await expect(page.locator('text=Total Data Ingested')).toBeVisible();
    await expect(page.locator('text=System Uptime')).toBeVisible();
    
    // Wait for API calls to complete and verify data is loaded
    await page.waitForTimeout(2000);
    
    // Check that statistics show actual values (not loading state)
    // More specific locators to avoid conflicts
    await expect(page.locator('[data-testid="active-tenants-value"], span:has-text("2")').first()).toBeVisible(); // Active tenants count
    await expect(page.locator('span:has-text("$127,450")')).toBeVisible(); // Revenue
    await expect(page.locator('span:has-text("15.2TB")')).toBeVisible(); // Data volume
    await expect(page.locator('span:has-text("99.97%")')).toBeVisible(); // Uptime
  });

  test('Admin checks System Health', async ({ page }) => {
    // Login and navigate to dashboard
    await page.goto('http://localhost:3002/login');
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:3002/');
    
    // Wait for health data to load
    await page.waitForTimeout(2000);
    
    // Verify system uptime shows healthy status
    await expect(page.locator('text=99.97%')).toBeVisible();
    
    // Verify the health API was called
    // Note: In a real test, we could check network requests or server logs
  });

  test('Admin sees navigation cards for all functions', async ({ page }) => {
    // Login and navigate to dashboard
    await page.goto('http://localhost:3002/login');
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:3002/');
    
    // Verify all navigation cards from Admin UI specs are present
    await expect(page.locator('text=Tenant Management')).toBeVisible();
    await expect(page.locator('text=Usage Analytics')).toBeVisible();
    await expect(page.locator('text=Billing & Subscriptions')).toBeVisible();
    await expect(page.locator('text=Feature Management')).toBeVisible();
    await expect(page.locator('text=Support & Tickets')).toBeVisible();
    await expect(page.locator('text=Admin Users')).toBeVisible();
  });

  test('Admin can logout successfully', async ({ page }) => {
    // Login and navigate to dashboard
    await page.goto('http://localhost:3002/login');
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:3002/');
    
    // Verify welcome message with user name
    await expect(page.locator('text=Welcome, Admin User')).toBeVisible();
    
    // Click logout button
    await page.click('button:has-text("Logout")');
    
    // Should redirect back to login page
    await expect(page).toHaveURL('http://localhost:3002/login');
    
    // Verify login form is visible
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test('Platform statistics load correctly without horizontal scroll', async ({ page }) => {
    // Login and navigate to dashboard
    await page.goto('http://localhost:3002/login');
    await page.fill('input[type="email"]', 'admin@example.com');
    await page.fill('input[type="password"]', 'mock-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('http://localhost:3002/');
    
    // Check page doesn't have horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1); // Allow for small rounding differences
    
    // Check responsive design - statistics should be in grid
    const statsGrid = page.locator('div').filter({ hasText: 'Active Tenants' }).first().locator('..');
    await expect(statsGrid).toBeVisible();
    
    // Verify cards don't overflow on mobile
    await page.setViewportSize({ width: 375, height: 667 }); // Mobile size
    await page.waitForTimeout(500); // Allow layout to adjust
    
    const mobileScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const mobileClientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(mobileScrollWidth).toBeLessThanOrEqual(mobileClientWidth + 1);
  });
});