// Decode the cup/leaderboard "Share to WhatsApp" text from the stats/cup page.
// Relies on the DOM contract: an <a> whose href is a wa.me / ?text= share link.
// Usage: node cup_msg.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const b = await chromium.launch({headless:true});
const c = await b.newContext({storageState:AUTH, timezoneId:TIMEZONE});
const p = await c.newPage();
await p.goto(`${POOL_BASE}${ROUTES.statsCup}`,{waitUntil:'networkidle'});
await p.waitForTimeout(2000);
const href = await p.evaluate(()=>{const a=Array.from(document.querySelectorAll('a')).find(a=>/wa\.me|text=/.test(a.href)); return a?a.href:null;});
if(!href){ console.log('NO SHARE LINK'); } else { console.log(decodeURIComponent(new URL(href).searchParams.get('text')||'')); }
await b.close();
