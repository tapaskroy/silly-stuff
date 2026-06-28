// Read back the persisted tournament "big" picks (winner/runner-up/third + player awards).
// Usage: node verify_big.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, timezoneId: TIMEZONE });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.bigOnes}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1800);
const v = await page.evaluate(()=>{
  const s=[...document.querySelectorAll('select')].map(x=>x.options[x.selectedIndex]?.textContent.trim());
  const t=[...document.querySelectorAll('input[type=text]')].map(x=>x.value);
  const n=[...document.querySelectorAll('input[type=number]')].map(x=>x.value);
  return {selects:s, texts:t, numbers:n};
});
console.log('BIG ONES (persisted):', JSON.stringify(v,null,2));
await browser.close();
