// Accuracy breakdown: per-player exact% / winner% / wrong% across the pool.
// Sources: the "Group" result cards (Nailed the score / Just the winner lines) for
// exact & winner tallies, and the /stats leaderboard for each player's total picks made.
// Usage: node topu_calc.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
const AGENT_MARKER = process.env.AGENT_EMOJI || '';
const b=await chromium.launch({headless:true});
const c=await b.newContext({storageState:AUTH,timezoneId:TIMEZONE});
const p=await c.newPage();

// 1) Group tab summary cards -> per-player exact & winner tallies
await p.goto(`${POOL_BASE}${ROUTES.predict}`,{waitUntil:'networkidle'});
await p.waitForTimeout(2500);
try{ const gt=p.getByText(/^Group$/); if(await gt.count()){ await gt.first().click({timeout:2000}); await p.waitForTimeout(3000); } }catch{}
const body=await p.evaluate(()=>document.body.innerText);
const exact={}, winner={}; let cards=0;
const stripMarker = s => AGENT_MARKER ? s.split(AGENT_MARKER).join('') : s;
const splitNames=s=>s.split(',').map(x=>stripMarker(x).trim()).filter(Boolean);
const reEx=/Nailed the score\s*\((\d+)\)\s*:\s*([^\n]+)/g;
const reWin=/Just the winner\s*\((\d+)\)\s*:\s*([^\n]+)/g;
let m;
while((m=reEx.exec(body))){ cards++; for(const nm of splitNames(m[2])) exact[nm]=(exact[nm]||0)+1; }
while((m=reWin.exec(body))){ for(const nm of splitNames(m[2])) winner[nm]=(winner[nm]||0)+1; }

// 2) /stats leaderboard -> per-player "Picks made X/NN" total
await p.goto(`${POOL_BASE}${ROUTES.stats}`,{waitUntil:'networkidle'});
await p.waitForTimeout(2500);
const stext=await p.evaluate(()=>document.body.innerText);
// rows like: "Name 32/32 6/6 27"  -> name then picksMade/total
const made={};
for(const line of stext.split('\n')){
  const mm=line.match(/^(.+?)\s+(\d+)\/(\d+)\s+\d+\/\d+\s+\d+$/);
  if(mm){ made[stripMarker(mm[1]).trim()]=+mm[2]; }
}
await b.close();

// 3) compute accuracy table
const names=new Set([...Object.keys(exact),...Object.keys(winner),...Object.keys(made)]);
const rows=[];
for(const n of names){
  const e=exact[n]||0, w=winner[n]||0;
  let tot=made[n];
  if(tot===undefined) tot=e+w;            // fallback if not in /stats
  const wrong=Math.max(0,tot-e-w);
  if(tot===0) continue;
  rows.push({n,e,w,wrong,tot, ep:100*e/tot, wp:100*w/tot, xp:100*wrong/tot});
}
rows.sort((a,b)=>b.ep-a.ep || b.wp-a.wp);
console.log('exact-cards parsed:',cards,'| players:',rows.length);
console.log('#  Name                  exact%  win%  wrong%   (e/w/x, n)');
rows.forEach((r,i)=>console.log(
  `${String(i+1).padStart(2)} ${r.n.padEnd(22)} ${r.ep.toFixed(1).padStart(5)}% ${r.wp.toFixed(1).padStart(5)}% ${r.xp.toFixed(1).padStart(5)}%  (${r.e}/${r.w}/${r.wrong}, n=${r.tot})`));
