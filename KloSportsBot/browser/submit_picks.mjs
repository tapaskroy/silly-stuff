// Submit score predictions on the /predict board, matching each card by a home-team
// substring needle, then verify the persisted values on reload.
// Relies on the DOM contract: each open card has two number inputs + a "Save" button.
//
// Picks are passed as a JSON array of [homeNeedle, homeScore, awayScore]:
//   node submit_picks.mjs '[["Portugal",2,0],["England",1,0],["Mexico",2,1]]'
// or via a file:  node submit_picks.mjs --file picks.json
import fs from 'node:fs';
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;

let raw = process.argv[2];
if (raw === '--file') raw = fs.readFileSync(process.argv[3], 'utf8');
if (!raw) { console.error('Usage: node submit_picks.mjs \'[["Home",h,a],...]\'  |  --file picks.json'); process.exit(1); }
const PICKS = JSON.parse(raw);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, timezoneId: TIMEZONE });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.predict}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

const saveButtons = page.getByRole('button', { name: /save/i });
console.log('save buttons:', await saveButtons.count());

for (let i = 0; i < PICKS.length; i++) {
  const [home, hs, as] = PICKS[i];
  const btn = saveButtons.nth(i);
  // climb to the card container that holds 2 inputs
  const card = btn.locator('xpath=ancestor::*[.//input][1]');
  const cardText = (await card.innerText()).replace(/\n+/g, ' ');
  if (!cardText.includes(home)) {
    console.log(`!! MISMATCH at idx ${i}: expected "${home}", card="${cardText.slice(0,60)}" — SKIPPING`);
    continue;
  }
  const inputs = card.locator('input[type="number"]');
  await inputs.nth(0).fill(String(hs));
  await inputs.nth(1).fill(String(as));
  await btn.click();
  await page.waitForTimeout(900);
  console.log(`OK ${home}: ${hs}-${as}  [card: ${cardText.slice(0,40)}]`);
}

// reload and verify persisted values
await page.waitForTimeout(1500);
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
console.log('\n=== VERIFY (reloaded) ===');
const sb2 = page.getByRole('button', { name: /save/i });
const n2 = await sb2.count();
for (let i = 0; i < Math.min(n2, PICKS.length); i++) {
  const card = sb2.nth(i).locator('xpath=ancestor::*[.//input][1]');
  const inputs = card.locator('input[type="number"]');
  const v0 = await inputs.nth(0).inputValue().catch(()=> '?');
  const v1 = await inputs.nth(1).inputValue().catch(()=> '?');
  const ct = (await card.innerText()).replace(/\n+/g,' ').slice(0,38);
  console.log(`  ${ct}  -> ${v0}-${v1}`);
}
await browser.close();
