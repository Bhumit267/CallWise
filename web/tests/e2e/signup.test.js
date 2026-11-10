/**
 * End-to-end browser regression test for /signup flow with self-cleaning teardown.
 */
const { chromium } = require('playwright');
const assert = require('assert');
const { execSync } = require('child_process');
const path = require('path');

(async () => {
  console.log('--- Starting Playwright End-to-End Signup Test (Self-Cleaning) ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const timestamp = Date.now();
  const testEmail = `playwright_owner_${timestamp}@example.com`;
  const testName = 'Dr. Playwright Tester';
  const testBiz = `Playwright Dental ${timestamp}`;
  const testBizType = 'Dental Clinic';
  const testPassword = 'SecurePassword123!';

  try {
    console.log(`1. Navigating to http://localhost:3000/signup ...`);
    await page.goto('http://localhost:3000/signup', { waitUntil: 'networkidle' });

    // Verify form elements exist
    console.log('2. Inspecting signup form inputs...');
    await page.waitForSelector('input[placeholder="Jane Doe"]');
    await page.waitForSelector('input[placeholder="Apex Dental Clinic"]');
    await page.waitForSelector('select');
    await page.waitForSelector('input[placeholder="you@company.com"]');
    await page.waitForSelector('input[placeholder="At least 8 characters"]');

    console.log(`3. Filling form with valid credentials (${testEmail})...`);
    await page.fill('input[placeholder="Jane Doe"]', testName);
    await page.fill('input[placeholder="Apex Dental Clinic"]', testBiz);
    await page.selectOption('select', testBizType);
    await page.fill('input[placeholder="you@company.com"]', testEmail);
    await page.fill('input[placeholder="At least 8 characters"]', testPassword);

    console.log('4. Clicking "Create Account"...');
    await page.click('button[type="submit"]');

    console.log('5. Waiting for navigation redirect...');
    await page.waitForURL('**/onboarding', { timeout: 15000 });

    const currentUrl = page.url();
    console.log(`Current URL after signup: ${currentUrl}`);
    assert.ok(currentUrl.includes('/onboarding'), `Expected URL to include '/onboarding', got: ${currentUrl}`);

    console.log('6. User successfully landed on /onboarding page!');
  } finally {
    await browser.close();

    // Self-cleaning teardown: remove test business and user created during test
    console.log('7. Running self-cleaning teardown...');
    try {
      const rootDir = path.resolve(__dirname, '../../..');
      execSync('uv run python scripts/testing/clean_test_biz.py', {
        cwd: rootDir,
        stdio: 'inherit'
      });
      console.log('8. Test database cleaned: only original seed businesses remain.');
    } catch (cleanupErr) {
      console.warn('Cleanup warning:', cleanupErr.message);
    }
  }

  console.log('--- Playwright Signup E2E Test PASSED! ---');
})().catch((err) => {
  console.error('Playwright Test Failed:', err);
  process.exit(1);
});

