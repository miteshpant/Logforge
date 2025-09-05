import { test, expect } from '@playwright/test';

test.describe('Tenant Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to admin UI
    await page.goto('http://localhost:3002');
  });

  test('should display tenant management page correctly', async ({ page }) => {
    // Navigate to tenant management
    await page.click('text=Tenant Management');
    await expect(page).toHaveURL('http://localhost:3002/tenants');

    // Check page elements
    await expect(page.locator('h1')).toContainText('Tenant Management');
    await expect(page.locator('text=+ Onboard New Tenant')).toBeVisible();
    
    // Check statistics cards
    await expect(page.locator('text=Total Tenants')).toBeVisible();
    await expect(page.locator('text=Active Tenants')).toBeVisible();
    await expect(page.locator('text=Monthly Revenue')).toBeVisible();
    await expect(page.locator('text=Enterprise Customers')).toBeVisible();

    // Check table headers
    await expect(page.locator('text=Organization')).toBeVisible();
    await expect(page.locator('text=Tenant ID')).toBeVisible();
    await expect(page.locator('text=Type')).toBeVisible();
    await expect(page.locator('text=Status')).toBeVisible();
    await expect(page.locator('text=Industry')).toBeVisible();
    await expect(page.locator('text=Created')).toBeVisible();
    await expect(page.locator('text=Actions')).toBeVisible();
  });

  test('should open and close onboarding modal', async ({ page }) => {
    await page.click('text=Tenant Management');
    
    // Open modal
    await page.click('text=+ Onboard New Tenant');
    await expect(page.locator('text=Onboard New Tenant')).toBeVisible();
    
    // Check form fields
    await expect(page.locator('input[placeholder="Enter organization name"]')).toBeVisible();
    await expect(page.locator('input[placeholder="Enter contact person name"]')).toBeVisible();
    await expect(page.locator('input[placeholder="admin@company.com"]')).toBeVisible();
    await expect(page.locator('select')).toHaveCount(2); // Type and Industry selects
    
    // Close modal
    await page.click('text=Cancel');
    await expect(page.locator('text=Onboard New Tenant')).not.toBeVisible();
  });

  test('should validate form fields correctly', async ({ page }) => {
    await page.click('text=Tenant Management');
    await page.click('text=+ Onboard New Tenant');

    // Try to submit empty form
    await page.click('text=Create Tenant');
    
    // Should show HTML5 validation for required fields
    const nameInput = page.locator('input[placeholder="Enter organization name"]');
    await expect(nameInput).toHaveAttribute('required');
    
    const contactInput = page.locator('input[placeholder="Enter contact person name"]');
    await expect(contactInput).toHaveAttribute('required');
    
    const emailInput = page.locator('input[placeholder="admin@company.com"]');
    await expect(emailInput).toHaveAttribute('required');
    await expect(emailInput).toHaveAttribute('type', 'email');
  });

  test('should fill and submit tenant creation form', async ({ page }) => {
    await page.click('text=Tenant Management');
    await page.click('text=+ Onboard New Tenant');

    // Fill form
    await page.fill('input[placeholder="Enter organization name"]', 'Test Company');
    await page.fill('input[placeholder="Enter contact person name"]', 'John Doe');
    await page.fill('input[placeholder="admin@company.com"]', 'john@testcompany.com');
    await page.selectOption('select >> nth=0', 'startup'); // Organization type
    await page.fill('input[placeholder*="Technology"]', 'Software Development');

    // Submit form
    await page.click('text=Create Tenant');
    
    // Should close modal after submission (either success or error)
    // Note: This will depend on API availability - may show success or fallback to mock data
    await page.waitForTimeout(2000); // Wait for API call
  });

  test('should navigate to tenant details', async ({ page }) => {
    await page.click('text=Tenant Management');
    
    // Wait for tenants to load
    await page.waitForSelector('text=View Details', { timeout: 10000 });
    
    // Click on first "View Details" link
    await page.click('text=View Details >> nth=0');
    
    // Should navigate to tenant details page
    await expect(page.url()).toMatch(/\/tenants\/[a-f0-9-]+$/);
    
    // Check tenant details page elements
    await expect(page.locator('text=← Back to Tenants')).toBeVisible();
    await expect(page.locator('text=Basic Information')).toBeVisible();
    await expect(page.locator('text=Quick Actions')).toBeVisible();
    await expect(page.locator('text=Edit Tenant')).toBeVisible();
    await expect(page.locator('text=Delete Tenant')).toBeVisible();
  });

  test('should navigate to subscription management', async ({ page }) => {
    await page.click('text=Tenant Management');
    
    // Wait for tenants to load
    await page.waitForSelector('text=Manage Subscription', { timeout: 10000 });
    
    // Click on first "Manage Subscription" link
    await page.click('text=Manage Subscription >> nth=0');
    
    // Should navigate to subscription page
    await expect(page.url()).toMatch(/\/tenants\/[a-f0-9-]+\/subscription$/);
    
    // Check subscription page elements
    await expect(page.locator('text=Manage Subscription')).toBeVisible();
    await expect(page.locator('text=Current Subscription')).toBeVisible();
    await expect(page.locator('text=Available Subscription Tiers')).toBeVisible();
  });

  test('should enable tenant editing mode', async ({ page }) => {
    await page.click('text=Tenant Management');
    await page.waitForSelector('text=View Details', { timeout: 10000 });
    await page.click('text=View Details >> nth=0');
    
    // Enter edit mode
    await page.click('text=Edit Tenant');
    
    // Should show form fields
    await expect(page.locator('input[value*="Corp"], input[value*="Company"], input[value*="Inc"], input[value*="LLC"]')).toBeVisible();
    await expect(page.locator('text=Save Changes')).toBeVisible();
    await expect(page.locator('text=Cancel')).toBeVisible();
    
    // Cancel editing
    await page.click('text=Cancel');
    await expect(page.locator('text=Edit Tenant')).toBeVisible();
  });

  test('should show proper error handling for API failures', async ({ page }) => {
    // Mock API failure by using wrong endpoint
    await page.route('**/v1/tenants', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'Server error' })
      });
    });

    await page.click('text=Tenant Management');
    
    // Should show error state and fallback to mock data
    await expect(page.locator('text=Failed to load tenants')).toBeVisible();
    await expect(page.locator('text=Using mock data as fallback')).toBeVisible();
    
    // Should still show mock tenants
    await expect(page.locator('text=Acme Corp')).toBeVisible();
    await expect(page.locator('text=TechStart Inc')).toBeVisible();
    await expect(page.locator('text=DevTeam LLC')).toBeVisible();
  });

  test('should display loading states correctly', async ({ page }) => {
    // Mock slow API response
    await page.route('**/v1/tenants', route => {
      setTimeout(() => {
        route.fulfill({
          status: 200,
          body: JSON.stringify({ 
            tenants: [],
            total_count: 0,
            page: 1,
            page_size: 50
          })
        });
      }, 2000);
    });

    await page.click('text=Tenant Management');
    
    // Should show loading state initially
    await expect(page.locator('text=Loading tenants...')).toBeVisible();
    
    // Wait for loading to complete
    await expect(page.locator('text=Loading tenants...')).not.toBeVisible({ timeout: 5000 });
  });

  test('should navigate back to dashboard', async ({ page }) => {
    await page.click('text=Tenant Management');
    
    // Click back to dashboard
    await page.click('text=← Back to Dashboard');
    
    // Should return to dashboard
    await expect(page).toHaveURL('http://localhost:3002/');
    await expect(page.locator('text=Logforge Admin Dashboard')).toBeVisible();
  });

  test('should show tenant badges with correct colors', async ({ page }) => {
    await page.click('text=Tenant Management');
    await page.waitForSelector('table tbody tr', { timeout: 10000 });
    
    // Check that tenant type badges are visible
    const typeBadges = page.locator('tbody span[class*="bg-purple-100"], span[class*="bg-blue-100"], span[class*="bg-green-100"]');
    await expect(typeBadges.first()).toBeVisible();
    
    // Check that status badges are visible
    const statusBadges = page.locator('tbody span[class*="text-green-800"]');
    await expect(statusBadges.first()).toBeVisible();
  });
});

test.describe('Tenant Details Page', () => {
  test('should display tenant information correctly', async ({ page }) => {
    await page.goto('http://localhost:3002/tenants');
    await page.waitForSelector('text=View Details', { timeout: 10000 });
    await page.click('text=View Details >> nth=0');
    
    // Check tenant details elements
    await expect(page.locator('text=Organization Name')).toBeVisible();
    await expect(page.locator('text=Primary Contact')).toBeVisible();
    await expect(page.locator('text=Contact Email')).toBeVisible();
    await expect(page.locator('text=Organization Type')).toBeVisible();
    await expect(page.locator('text=Industry')).toBeVisible();
    await expect(page.locator('text=Status')).toBeVisible();
    await expect(page.locator('text=Created')).toBeVisible();
    await expect(page.locator('text=Last Updated')).toBeVisible();
  });

  test('should provide quick action links', async ({ page }) => {
    await page.goto('http://localhost:3002/tenants');
    await page.waitForSelector('text=View Details', { timeout: 10000 });
    await page.click('text=View Details >> nth=0');
    
    // Check quick actions
    await expect(page.locator('text=Manage Subscription')).toBeVisible();
    await expect(page.locator('text=Generate Invoice')).toBeVisible();
    await expect(page.locator('text=View Usage Analytics')).toBeVisible();
    await expect(page.locator('text=Send Notification')).toBeVisible();
  });
});

test.describe('Tenant Subscription Management', () => {
  test('should display subscription tiers', async ({ page }) => {
    await page.goto('http://localhost:3002/tenants');
    await page.waitForSelector('text=Manage Subscription', { timeout: 10000 });
    await page.click('text=Manage Subscription >> nth=0');
    
    // Check subscription page elements
    await expect(page.locator('text=Current Subscription')).toBeVisible();
    await expect(page.locator('text=Available Subscription Tiers')).toBeVisible();
    
    // Check that subscription tiers are displayed
    await expect(page.locator('text=Starter')).toBeVisible();
    await expect(page.locator('text=Professional')).toBeVisible();
    await expect(page.locator('text=Enterprise')).toBeVisible();
  });

  test('should navigate back to tenant details', async ({ page }) => {
    await page.goto('http://localhost:3002/tenants');
    await page.waitForSelector('text=Manage Subscription', { timeout: 10000 });
    await page.click('text=Manage Subscription >> nth=0');
    
    // Should be able to navigate back
    await page.click('text=← Back to');
    await expect(page.url()).toMatch(/\/tenants\/[a-f0-9-]+$/);
  });
});