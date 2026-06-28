// All scorer-pattern lines + header from ESPN gamecast (public, no auth).
// Usage: node goaldetail.mjs <gameId> <slug>
import { chromium } from 'playwright';
const GID = process.argv[2];
const SLUG = process.argv[3];
if (!GID || !SLUG) { console.error('Usage: node goaldetail.mjs <gameId> <slug>'); process.exit(1); }
const URL = `https://www.espn.com/soccer/match/_/gameId/${GID}/${SLUG}`;
const b = await chromium.launch({ headless: true });
const c = await b.newContext({ userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36' });
const p = await c.newPage();
await p.goto(URL, { waitUntil:'domcontentloaded' });
await p.waitForTimeout(4000);
const lines = (await p.evaluate(()=>document.body.innerText)).split('\n').map(s=>s.trim()).filter(Boolean);
const a = lines.findIndex(l=>/Group Stage/i.test(l));
console.log('HEADER:', lines.slice(a+1, a+14).join(' | '));
const goals = lines.filter(l=>/ - \d{1,2}'(\+\d')?( Pen| OG)?$/i.test(l));
console.log('ALL GOAL LINES:', JSON.stringify([...new Set(goals)]));
await b.close();
