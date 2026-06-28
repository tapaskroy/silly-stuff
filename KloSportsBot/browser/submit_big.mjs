// Submit the tournament "big" picks: winner / runner-up / third (dropdowns), plus
// top-scorer + best-player text fields and a goals number, then verify on reload.
// Relies on the DOM contract: the big-ones page has N <select> dropdowns in order,
// text inputs for the player awards, and a number input for the goal tally.
//
// Pass picks as JSON:
//   node submit_big.mjs '{"teams":["France","Argentina","Spain"],"players":["Player A","Player B"],"goals":8}'
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const raw = process.argv[2];
if (!raw) { console.error('Usage: node submit_big.mjs \'{"teams":[...3],"players":[...2],"goals":N}\''); process.exit(1); }
const { teams, players, goals } = JSON.parse(raw);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, timezoneId: TIMEZONE });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.bigOnes}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

const selects = page.locator('select');
for (let i=0;i<teams.length;i++){
  const sel = selects.nth(i);
  const val = await sel.locator('option', {hasText: teams[i]}).first().getAttribute('value');
  await sel.selectOption(val);
  const chosen = await sel.locator('option:checked').innerText();
  console.log(`select ${i} -> ${chosen.trim()}`);
}

const texts = page.locator('input[type="text"]');
for (let i=0;i<(players||[]).length;i++){ await texts.nth(i).fill(players[i]); }
if (goals != null) await page.locator('input[type="number"]').first().fill(String(goals));
console.log('filled players + goals');

await page.getByRole('button', { name: /save|continue/i }).first().click();
await page.waitForTimeout(2500);
console.log('clicked save, url:', page.url());

await page.reload({ waitUntil:'networkidle' });
await page.waitForTimeout(1500);
const v = await page.evaluate(()=>{
  const s=[...document.querySelectorAll('select')].map(x=>x.options[x.selectedIndex]?.textContent.trim());
  const t=[...document.querySelectorAll('input[type=text]')].map(x=>x.value);
  const n=[...document.querySelectorAll('input[type=number]')].map(x=>x.value);
  return {selects:s, texts:t, numbers:n};
});
console.log('VERIFY:', JSON.stringify(v,null,2));
await browser.close();
