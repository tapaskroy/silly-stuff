// Full-page screenshot of the standings/leaderboard page.
// Usage: node stats_shot.mjs [out.png] [routeKey-or-fullURL]
//   default route = config.routes.leaderboard
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE, url } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const OUT = process.argv[2] || 'stats.png';
const arg = process.argv[3];
const TARGET = arg ? (arg.startsWith('http') ? arg : url(arg)) : `${POOL_BASE}${ROUTES.leaderboard}`;
const b = await chromium.launch({headless:true});
const c = await b.newContext({storageState:AUTH, timezoneId:TIMEZONE, viewport:{width:760,height:2600}, deviceScaleFactor:2});
const p = await c.newPage();
await p.goto(TARGET,{waitUntil:'networkidle'});
await p.waitForTimeout(2000);
const full = await p.evaluate(()=>document.body.scrollHeight);
console.log('pageH:', full);
await p.screenshot({path:OUT, fullPage:true});
console.log('shot:', OUT);
await b.close();
