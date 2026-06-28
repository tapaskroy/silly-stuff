// Read back the currently-saved score predictions on the /predict board.
// Relies on the DOM contract: each card has a "Save" button + two number inputs.
// Usage: node verify_picks.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const b=await chromium.launch({headless:true});
const c=await b.newContext({storageState:AUTH,timezoneId:TIMEZONE});
const p=await c.newPage();
await p.goto(`${POOL_BASE}${ROUTES.predict}`,{waitUntil:'networkidle'});
await p.waitForTimeout(1800);
const v=await p.evaluate(()=>{
  const out=[]; const saves=[...document.querySelectorAll('button')].filter(b=>/^save/i.test(b.textContent.trim()));
  saves.forEach(btn=>{ let el=btn; for(let u=0;u<6&&el;u++){ const inp=el.querySelectorAll('input[type=number]');
    if(inp.length>=2){ const team=el.innerText.split('\n').filter(Boolean)[0]; out.push(`${team}: ${inp[0].value}-${inp[1].value} ${/saved/i.test(el.innerText)?'(saved)':''}`); break;} el=el.parentElement;}});
  return out;
});
v.forEach(x=>console.log(' ',x));
await b.close();
