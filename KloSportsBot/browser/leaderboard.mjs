// Parse per-player pick results from the pool's "Group" result cards and compute a
// points leaderboard (5 pts exact score, 3 pts correct result, 0 otherwise).
// Relies on the DOM contract: result cards under a "Group" tab, each with a
// "<home> vs <away>" header, a "N-N FT" final, and an "All picks:" block.
// Usage: node leaderboard.mjs
import { chromium } from 'playwright';
import { POOL_BASE, ROUTES, TIMEZONE } from './config.mjs';
const AUTH = new URL('./auth.json', import.meta.url).pathname;
// Optional marker emoji the agent uses on its own leaderboard row; stripped during parse.
const AGENT_MARKER = process.env.AGENT_EMOJI || '';
const b = await chromium.launch({headless:true});
const c = await b.newContext({storageState:AUTH, timezoneId:TIMEZONE});
const p = await c.newPage();
await p.goto(`${POOL_BASE}${ROUTES.predict}`,{waitUntil:'networkidle'});
await p.waitForTimeout(2500);
// group-stage result cards live under the "Group" tab (board may have rolled to a later round)
try{ const gt=p.getByText(/^Group$/); if(await gt.count()){ await gt.first().click({timeout:2000}); await p.waitForTimeout(2500); } }catch{}
for(const t of await p.$$('button, summary, [role="button"]')){ const tx=(await t.textContent()||'').toLowerCase(); if(/all picks|show|picks/.test(tx)){ try{await t.click({timeout:400});}catch{} } }
await p.waitForTimeout(1000);
const cards = await p.evaluate((marker)=>{
  const stripMarker = s => marker ? s.split(marker).join('') : s;
  const flagOf = s => { const m=s.match(/^[^A-Za-z0-9]+/); return m?m[0].trim():''; };
  const lines = document.body.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
  const out=[]; let i=0;
  while(i<lines.length){
    const h=lines[i]; const hv=h.match(/^(.*\S)\s+vs\s+(\S.*)$/);
    if(hv && !/predicted/.test(h)){
      let res=null;
      for(let k=i+1;k<i+4&&k<lines.length;k++){const r=lines[k].match(/(\d+)\s*[–-]\s*(\d+)\s*FT/);if(r){res=[+r[1],+r[2]];break;}}
      const homeFlag=flagOf(hv[1]), awayFlag=flagOf(hv[2]);
      let j=i+1; while(j<lines.length && !/^All picks:/.test(lines[j]) && !/ vs /.test(lines[j])) j++;
      const picks=[];
      if(res && j<lines.length && /^All picks:/.test(lines[j])){
        let k=j+1, name=null;
        while(k<lines.length && !/ vs /.test(lines[k]) && !/^All picks:/.test(lines[k])){
          const sc=lines[k].match(/(\d+)\s*[–-]\s*(\d+)/);
          if(sc){ picks.push({name:name||'?', flag:flagOf(lines[k]), a:+sc[1], b:+sc[2], isDraw:/Draw/i.test(lines[k])}); name=null; }
          else name=stripMarker(lines[k]).trim();
          k++;
        }
        out.push({homeFlag,awayFlag,rs1:res[0],rs2:res[1],picks}); i=k; continue;
      }
    } i++;
  }
  return out;
}, AGENT_MARKER);
const S={}, norm=n=>n.replace(/\s+/g,' ').trim();
for(const c of cards){ const resW=c.rs1>c.rs2?'H':c.rs1<c.rs2?'A':'D';
  for(const pk of c.picks){ let hg,ag;
    if(pk.isDraw){hg=pk.a;ag=pk.b;} else if(pk.flag===c.homeFlag){hg=pk.a;ag=pk.b;} else if(pk.flag===c.awayFlag){hg=pk.b;ag=pk.a;} else {hg=pk.a;ag=pk.b;}
    const pkW=hg>ag?'H':hg<ag?'A':'D'; const nm=norm(pk.name); if(!nm||nm==='?')continue;
    const s=S[nm]||(S[nm]={pred:0,exact:0,winner:0,wrong:0,pts:0});
    s.pred++;
    if(hg===c.rs1&&ag===c.rs2){s.exact++;s.pts+=5;}
    else if(pkW===resW){s.winner++;s.pts+=3;}
    else s.wrong++;
  }
}
const rows=Object.entries(S).map(([n,s])=>({n,...s}));
rows.sort((x,y)=> y.pts-x.pts || y.exact-x.exact || (y.exact+y.winner)-(x.exact+x.winner));
console.log('cards parsed:',cards.length);
let r=0;
for(const x of rows){ r++; console.log(`${r}. ${x.n} — ${x.pts} pts  (${x.pred}p: ${x.exact}exact/${x.winner}win/${x.wrong}wrong)`); }
await b.close();
