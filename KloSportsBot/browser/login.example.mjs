// Pool login -> writes a (gitignored) auth.json session for the other scripts to reuse.
// Copy to login.mjs (gitignored) if you need local tweaks. Credentials come from the
// environment, NEVER hardcode them here:
//   POOL_EMAIL=you@example.com POOL_PASSWORD=... node login.example.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';

const EMAIL = process.env.POOL_EMAIL;
const PASSWORD = process.env.POOL_PASSWORD;
if (!EMAIL || !PASSWORD) {
  console.error('Set POOL_EMAIL and POOL_PASSWORD in your environment (see templates/env.example).');
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1600 }, timezoneId: TIMEZONE });
const page = await ctx.newPage();

await page.goto(`${POOL_BASE}${ROUTES.login}`, { waitUntil: 'networkidle' });

// Fill email + password (match by type / placeholder — adjust selectors for your pool).
const email = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();
const pass  = page.locator('input[type="password"], input[name="password"]').first();
await email.fill(EMAIL);
await pass.fill(PASSWORD);

await Promise.all([
  page.waitForLoadState('networkidle'),
  page.locator('button[type="submit"], button:has-text("Log"), button:has-text("Sign")').first().click(),
]);

await page.waitForTimeout(2500);
console.log('POST-LOGIN URL:', page.url());
console.log('--- visible text (first 600) ---');
console.log((await page.locator('body').innerText()).slice(0, 600));

// Save the logged-in session next to this script (auth.json is gitignored).
await ctx.storageState({ path: new URL('./auth.json', import.meta.url).pathname });
console.log('--- saved storageState to auth.json ---');
await browser.close();
