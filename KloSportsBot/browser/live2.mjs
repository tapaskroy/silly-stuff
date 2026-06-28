// Live score + scorers from ESPN gamecast (public, no auth). Brittle to ESPN redesigns.
// Usage: node live2.mjs <gameId> <slug>    e.g. node live2.mjs 760437 croatia-england
import { chromium } from 'playwright';
const GID = process.argv[2];
const SLUG = process.argv[3];
if (!GID || !SLUG) { console.error('Usage: node live2.mjs <gameId> <slug>'); process.exit(1); }
const URL = `https://www.espn.com/soccer/match/_/gameId/${GID}/${SLUG}`;
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36' });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3500);
const lines = (await page.evaluate(()=>document.body.innerText)).split('\n').map(s=>s.trim()).filter(Boolean);
// Anchor on the live-match header label (handles both "2026 FIFA World Cup, Group Stage"
// and "FIFA World Cup, Group A"); take the FIRST, which is the scoreboard (a later identical
// string can appear in a "recent form" section).
let a = lines.findIndex(l=>/^(2026 )?FIFA World Cup, Group (Stage|[A-L])$/.test(l));
if (a < 0) a = lines.findIndex(l=>/Group Stage/i.test(l));
console.log('HEADER:', lines.slice(a+1, a+13).join(' | '));
const goals = lines.filter(l=>/ - \d{1,2}'(\+\d')?( Pen| OG)?$/i.test(l));
console.log('GOALS:', JSON.stringify([...new Set(goals)]));
await browser.close();
