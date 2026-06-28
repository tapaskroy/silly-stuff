// Screenshot the live /predict card, clipped from the Home-team header to the next match.
// Usage: node shot_live_card.mjs "<HomeTeam>" "<NextMatchHomeTeam>" [out.png]
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const HOME = process.argv[2], NEXT = process.argv[3], OUT = process.argv[4] || 'live_card.png';
if (!HOME) { console.error('Usage: node shot_live_card.mjs "<HomeTeam>" "<NextMatchHomeTeam>" [out.png]'); process.exit(1); }
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, timezoneId: TIMEZONE, viewport:{width:760,height:1600}, deviceScaleFactor:2 });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.predict}`, { waitUntil:'networkidle' });
await page.waitForTimeout(1200);
try { await page.getByText(/^In play$/).first().click({timeout:2000}); await page.waitForTimeout(700);} catch {}
console.log('--- in-play text (first 500) ---');
console.log((await page.locator('body').innerText()).slice(0,500));
const hb = await page.locator(`text=${HOME}`).first().boundingBox();
let nb=null; try { nb = await page.locator(`text=${NEXT}`).first().boundingBox(); } catch {}
const top=Math.max(0,hb.y-44), height=(nb?nb.y:top+520)-top-18;
await page.screenshot({ path: OUT, clip:{x:8,y:top,width:744,height} });
console.log('captured', OUT, 'top',top.toFixed(0),'h',height.toFixed(0));
await browser.close();
