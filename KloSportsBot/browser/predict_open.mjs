// List the currently OPEN (editable) games on the /predict board — cards that still
// have editable number inputs + a Save button (not yet frozen at kickoff).
// Usage: node predict_open.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const b = await chromium.launch({headless:true});
const c = await b.newContext({storageState:AUTH, timezoneId:TIMEZONE});
const p = await c.newPage();
await p.goto(`${POOL_BASE}${ROUTES.predict}`,{waitUntil:'networkidle'});
await p.waitForTimeout(1500);
const data = await p.evaluate(()=>{
  const out=[];
  const saves=[...document.querySelectorAll('button')].filter(b=>/^save$/i.test(b.textContent.trim()));
  saves.forEach((btn,i)=>{
    let el=btn;
    for(let u=0;u<6&&el;u++){ if(el.querySelectorAll('input[type=number]').length>=2){
      const t=el.innerText.replace(/\n+/g,' | ').slice(0,80); out.push({idx:i,card:t}); break;} el=el.parentElement; }
  });
  return out;
});
console.log('OPEN (editable) games:', data.length);
data.forEach(d=>console.log(' ',d.idx, d.card));
await b.close();
