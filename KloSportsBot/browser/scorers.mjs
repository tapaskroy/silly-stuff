// Detailed goal-scorer lines from ESPN gamecast (public, no auth).
// Usage: node scorers.mjs <gameId> <slug>
import { chromium } from 'playwright';
const GID = process.argv[2];
const SLUG = process.argv[3];
if (!GID || !SLUG) { console.error('Usage: node scorers.mjs <gameId> <slug>'); process.exit(1); }
const URL = `https://www.espn.com/soccer/match/_/gameId/${GID}/${SLUG}`;
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36' });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3500);
const t = await page.evaluate(()=>document.body.innerText);
const lines = t.split('\n').map(s=>s.trim()).filter(Boolean);
// lines like "Name - 45'+2'" or "Name - 6'"
const goals = lines.filter(l=>/\s-\s\d{1,2}'(\+\d')?$/.test(l));
console.log('GOAL LINES:', JSON.stringify([...new Set(goals)]));
const i = lines.findIndex(l=>/Group Stage/i.test(l));
console.log('HEADER:', lines.slice(i, i+12).join(' | '));
await browser.close();
