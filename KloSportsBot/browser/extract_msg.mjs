// Decode the pool's "Share to WhatsApp" result card for a given match.
// Relies on the DOM contract: results page has <a aria-label="Share to WhatsApp" href="...wa.me/?text=...">.
// Usage: node extract_msg.mjs "<team-substring>"
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const matchNeedle = process.argv[2];
if (!matchNeedle) { console.error('Usage: node extract_msg.mjs "<team-substring>"'); process.exit(1); }
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.predictPast}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
const hrefs = await page.evaluate(() =>
  Array.from(document.querySelectorAll('a[aria-label="Share to WhatsApp"]')).map(a => a.href)
);
const match = hrefs.find(h => decodeURIComponent(h).includes(matchNeedle));
if (!match) { console.log('NO MATCH for', matchNeedle); process.exit(1); }
const text = decodeURIComponent(new URL(match).searchParams.get('text'));
console.log('=====MSG_START=====');
console.log(text);
console.log('=====MSG_END=====');
await browser.close();
