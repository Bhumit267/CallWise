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

    // Self-cleaning teardown: remove ONLY the specific user and business created during this test run
    console.log(`7. Running self-cleaning teardown for ${testEmail}...`);
    try {
      const rootDir = path.resolve(__dirname, '../../..');
      const cleanupCmd = `uv run python -c "from callwise.db.session import SyncSessionLocal; from callwise.db.models import Business, User, Membership; from sqlalchemy import select, delete; s = SyncSessionLocal(); u = s.scalar(select(User).where(User.email == '${testEmail}')); mems = s.scalars(select(Membership).where(Membership.user_id == u.id)).all() if u else []; biz_ids = [m.business_id for m in mems]; s.execute(delete(User).where(User.id == u.id)) if u else None; [s.execute(delete(Business).where(Business.id == bid)) for bid in biz_ids]; s.commit(); s.close()"`;
      execSync(cleanupCmd, {
        cwd: rootDir,
        stdio: 'inherit'
      });
      console.log(`8. Test database cleaned: purged user ${testEmail} and associated test business.`);
    } catch (cleanupErr) {
      console.warn('Cleanup warning:', cleanupErr.message);
    }
  }

  console.log('--- Playwright Signup E2E Test PASSED! ---');
})().catch((err) => {
  console.error('Playwright Test Failed:', err);
  process.exit(1);
});

