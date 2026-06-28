// Scrape the pool's /tournament page -> structured fixtures. Prints JSON.
// Output: { now, live:[...], next, upcoming:[...] }; kickoff times use config.timezone.
// Pool base URL + routes + timezone come from config.json.
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';

const AUTH = new URL('./auth.json', import.meta.url).pathname;
const MONTHS = {JAN:0,FEB:1,MAR:2,APR:3,MAY:4,JUN:5,JUL:6,AUG:7,SEP:8,OCT:9,NOV:10,DEC:11};
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, timezoneId: TIMEZONE });
const page = await ctx.newPage();
await page.goto(`${POOL_BASE}${ROUTES.tournament}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const lines = (await page.locator('body').innerText()).split('\n').map(s=>s.trim()).filter(Boolean);

const isDate = l => /^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),\s+([A-Z]{3})\s+(\d{1,2})$/.exec(l);
const isGroup = l => /^[A-L]$/.test(l) || /^(R32|R16|QF|SF|F|3rd)$/i.test(l);
const isScore = l => /^\d+$/.test(l);
const isTime = l => /^\d{1,2}:\d{2}\s+(AM|PM)$/.test(l);
const isTeam = l => /[A-Za-z]{2,}/.test(l) && !isScore(l) && !isTime(l) && !isGroup(l)
  && !/^(FT|LIVE|● LIVE|Score as of)/.test(l) && !isDate(l);

const live = [], upcoming = [];
let curDate = null; // {month, day}
for (let i = 0; i < lines.length; i++) {
  const dm = isDate(lines[i]);
  if (dm) { curDate = { mon: MONTHS[dm[2]], day: +dm[3] }; continue; }
  if (isGroup(lines[i]) && isTeam(lines[i+1]||'') && isTeam(lines[i+2]||'')) {
    const group = lines[i], t1 = lines[i+1], t2 = lines[i+2];
    let j = i + 3;
    if (isScore(lines[j]) && isScore(lines[j+1])) {
      const s1 = +lines[j], s2 = +lines[j+1], st = lines[j+2] || '';
      if (/LIVE/i.test(st)) live.push({ group, t1, t2, s1, s2 });
      i = j + 1;
    } else if (isTime(lines[j])) {
      const tstr = lines[j], venue = lines[j+1] || '';
      const m = /^(\d{1,2}):(\d{2})\s+(AM|PM)$/.exec(tstr);
      let h = +m[1] % 12; if (m[3] === 'PM') h += 12;
      let ko = null;
      if (curDate) ko = new Date(2026, curDate.mon, curDate.day, h, +m[2], 0).getTime();
      upcoming.push({ group, t1, t2, time: tstr, venue, kickoffEpoch: ko ? Math.floor(ko/1000) : null,
                      kickoffLocal: ko ? new Date(ko).toLocaleString('en-US',{timeZone:TIMEZONE}) : null });
      i = j + 1;
    }
  }
}
upcoming.sort((a,b)=>(a.kickoffEpoch||0)-(b.kickoffEpoch||0));
const now = Math.floor(Date.now()/1000);
console.log(JSON.stringify({ now, nowLocal: new Date().toLocaleString('en-US',{timeZone:TIMEZONE}), live, next: upcoming[0]||null, upcoming: upcoming.slice(0,6) }, null, 2));
await browser.close();
