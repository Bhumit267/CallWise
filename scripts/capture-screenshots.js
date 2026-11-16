/**
 * scripts/capture-screenshots.js
 *
 * Automated Playwright script to capture clean, high-resolution (deviceScaleFactor: 2)
 * product screenshots for the Callwise documentation and README.
 *
 * Rules & Safety:
 * - Uses only fake demo accounts (aarav.owner@test.com and salon.owner@test.com).
 * - Suppresses Next.js development overlays and badge portals.
 * - Does not touch database or alter application code.
 * - Saves screenshots in docs/screenshots/.
 *
 * Usage:
 *   node scripts/capture-screenshots.js
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../web/node_modules/playwright'));

const SCREENSHOT_DIR = path.resolve(__dirname, '../docs/screenshots');
const BASE_WEB_URL = 'http://localhost:3000';
const BASE_API_URL = 'http://localhost:8000';

const AARAV_CREDENTIALS = {
  email: 'aarav.owner@test.com',
  password: 'Password123!',
};

const LUXE_CREDENTIALS = {
  email: 'salon.owner@test.com',
  password: 'Password123!',
};

// CSS injected to ensure clean, publication-ready shots without dev banners
const CLEAN_STYLE = `
  #__next-build-watcher,
  nextjs-portal,
  [data-nextjs-toast],
  [data-next-badge],
  [id^="__next-dev"] {
    display: none !important;
    visibility: hidden !important;
  }
`;

async function getAuthToken(email, password) {
  const res = await fetch(`${BASE_API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error(`Failed to log in as ${email}: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return data.session_token;
}

async function preparePage(context, token, viewport = { width: 1920, height: 1080 }) {
  const page = await context.newPage();
  await page.setViewportSize(viewport);

  if (token) {
    await page.addInitScript((jwt) => {
      window.localStorage.setItem('callwise_token', jwt);
    }, token);
  }

  // Inject style after navigation to strip any dev banners
  page.on('domcontentloaded', async () => {
    try {
      await page.addStyleTag({ content: CLEAN_STYLE });
    } catch (e) {
      // ignore
    }
  });

  return page;
}

async function captureShot(page, route, filename, waitSelector = null, actionFn = null) {
  const url = `${BASE_WEB_URL}${route}`;
  console.log(`[Capture] Navigating to ${url} -> ${filename}...`);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });

  if (waitSelector) {
    try {
      await page.waitForSelector(waitSelector, { timeout: 10000 });
    } catch (e) {
      console.warn(`[Warning] Wait selector "${waitSelector}" timed out on ${route}`);
    }
  }

  if (actionFn) {
    await actionFn(page);
    await page.waitForTimeout(1000);
  }

  // Ensure dev overlays are gone
  await page.addStyleTag({ content: CLEAN_STYLE });
  await page.waitForTimeout(800);

  const outPath = path.join(SCREENSHOT_DIR, filename);
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`[Success] Saved ${filename}`);
}

async function main() {
  if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }

  console.log('Authenticating demo accounts against backend API...');
  const aaravToken = await getAuthToken(AARAV_CREDENTIALS.email, AARAV_CREDENTIALS.password);
  const luxeToken = await getAuthToken(LUXE_CREDENTIALS.email, LUXE_CREDENTIALS.password);
  console.log('Auth tokens retrieved successfully.');

  const browser = await chromium.launch({
    headless: true,
  });

  try {
    // ----------------------------------------------------
    // 1. Unauthenticated Login Page
    // ----------------------------------------------------
    {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 2,
        colorScheme: 'light',
      });
      const page = await preparePage(context, null);
      await page.goto(`${BASE_WEB_URL}/login`, { waitUntil: 'networkidle' });
      // Pre-fill email nicely for the screenshot
      await page.fill('input[type="email"]', 'aarav.owner@test.com');
      await page.waitForTimeout(500);
      await captureShot(page, '/login', '01-login.png');
      await context.close();
    }

    // ----------------------------------------------------
    // 2. Aarav Clinic Views (Desktop 1920x1080)
    // ----------------------------------------------------
    {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 2,
        colorScheme: 'light',
      });

      // 02: Inbox / Dashboard
      const inboxPage = await preparePage(context, aaravToken);
      await captureShot(inboxPage, '/inbox', '02-dashboard-inbox-aarav.png', 'table, [data-inbox-item], .space-y-4');

      // 03: Call Detail Drawer (click on Vikram Patel's cancellation call)
      await captureShot(inboxPage, '/inbox', '03-call-detail-drawer.png', null, async (p) => {
        // Look for the call card that contains "scheduling conflict" or "cancelled the appointment"
        const callRow = p.locator('div.cursor-pointer, div[role="button"]').filter({
          hasText: 'scheduling conflict'
        }).or(p.locator('div.cursor-pointer, div[role="button"]').filter({
          hasText: 'cancelled the appointment'
        })).first();

        if (await callRow.count() > 0) {
          console.log('[Action] Clicking Vikram Patel cancellation call row to open detail drawer...');
          await callRow.click();
          await p.waitForSelector('text=AI EXECUTIVE BRIEF', { timeout: 8000 }).catch(() => {});
          await p.waitForTimeout(1500);
        }
      });
      await inboxPage.close();

      // 04: Appointments
      const apptPage = await preparePage(context, aaravToken);
      await captureShot(apptPage, '/appointments', '04-appointments-aarav.png', 'text=Appointments & Bookings');
      await apptPage.close();

      // 05: Contacts
      const contactsPage = await preparePage(context, aaravToken);
      await captureShot(contactsPage, '/contacts', '05-contacts-aarav.png', 'text=Contacts Directory');
      await contactsPage.close();

      // 06: Follow-ups
      const followUpPage = await preparePage(context, aaravToken);
      await captureShot(followUpPage, '/follow-ups', '06-follow-ups-aarav.png', 'text=Follow-up Pipeline');
      await followUpPage.close();

      // 07: Knowledge Base
      const kbPage = await preparePage(context, aaravToken);
      await captureShot(kbPage, '/knowledge', '07-knowledge-base-aarav.png', 'text=Knowledge Base');
      await kbPage.close();

      // 08: Missed Questions
      const missPage = await preparePage(context, aaravToken);
      await captureShot(missPage, '/missed-questions', '08-missed-questions-aarav.png', 'text=Missed Questions');
      await missPage.close();

      // 09: Test Agent with grounded conversation answering rupee price
      const agentPage = await preparePage(context, aaravToken);
      // Route test-agent to return the grounded root canal price response
      await agentPage.route('**/api/onboarding/test-agent', async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            call_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            reply: 'At Aarav Health & Dental Clinic, our single-sitting Root Canal Treatment is ₹4,500, performed by MDS Endodontic specialists with rotary instrumentation and digital apex locators.',
            latency_ms: 1240.5,
          }),
        });
      });

      await captureShot(agentPage, '/test-agent', '09-test-agent-aarav.png', 'text=INTERACTIVE TEST AGENT', async (p) => {
        const textTab = p.locator('button, div[role="tab"]').filter({ hasText: 'TEXT CHAT SIMULATOR' }).first();
        if (await textTab.count() > 0) {
          console.log('[Action] Clicking Text Chat Simulator tab...');
          await textTab.click();
          await p.waitForTimeout(800);
        }

        const input = p.locator('input[placeholder*="Type caller inquiry"]');
        if (await input.count() > 0) {
          console.log('[Action] Typing price inquiry into Test Agent...');
          await input.fill('What is the price of a single sitting Root Canal Treatment?');
          await p.waitForTimeout(400);
          const sendBtn = p.locator('button').filter({ hasText: 'SEND' });
          if (await sendBtn.count() > 0) {
            await sendBtn.click();
          } else {
            await input.press('Enter');
          }
          await p.waitForSelector('text=₹4,500', { timeout: 6000 }).catch(() => {});
          await p.waitForTimeout(1000);
        }
      });
      await agentPage.close();

      // 10: Usage & Limits
      const usagePage = await preparePage(context, aaravToken);
      await captureShot(usagePage, '/usage', '10-usage-limits-aarav.png', 'text=Usage & Quotas');
      await usagePage.close();

      // 11: Settings
      const settingsPage = await preparePage(context, aaravToken);
      await captureShot(settingsPage, '/settings', '11-settings-aarav.png', 'text=Practice Settings');
      await settingsPage.close();

      // 12: Team & Access
      const teamPage = await preparePage(context, aaravToken);
      await captureShot(teamPage, '/team', '12-team-access-aarav.png', 'text=Team & Permissions');
      await teamPage.close();

      await context.close();
    }

    // ----------------------------------------------------
    // 3. Luxe Glow Salon Views (Desktop 1920x1080)
    // ----------------------------------------------------
    {
      const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 2,
        colorScheme: 'light',
      });

      // 13: Luxe Glow Inbox
      const luxeInboxPage = await preparePage(context, luxeToken);
      await captureShot(luxeInboxPage, '/inbox', '13-inbox-luxe.png', 'table, [data-inbox-item], .space-y-4');
      await luxeInboxPage.close();

      // 14: Luxe Glow Analytics
      const luxeAnalyticsPage = await preparePage(context, luxeToken);
      await captureShot(luxeAnalyticsPage, '/analytics', '14-analytics-luxe.png', 'text=Analytics & Insights');
      await luxeAnalyticsPage.close();

      await context.close();
    }

    // ----------------------------------------------------
    // 4. Mobile View (390x844 - iPhone 14 / modern smartphone)
    // ----------------------------------------------------
    {
      const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 2,
        colorScheme: 'light',
        isMobile: true,
        hasTouch: true,
      });

      // 15: Mobile Inbox
      const mobilePage = await preparePage(context, aaravToken, { width: 390, height: 844 });
      await captureShot(mobilePage, '/inbox', '15-inbox-mobile.png', 'text=Aarav');
      await mobilePage.close();

      await context.close();
    }

    console.log('\nAll 15 screenshots successfully captured and saved in docs/screenshots/!');
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('Fatal error during screenshot capture:', err);
  process.exit(1);
});