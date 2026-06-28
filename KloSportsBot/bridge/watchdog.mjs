// Bridge watchdog: keeps listener + follow-sync alive. Runs forever; if IT dies, a
// process-supervisor / agent harness that launched it as a tracked background command
// is notified and relaunches it.
// Respects BRIDGE_PAUSE (set while posting, to avoid single-writer lock fights — see
// docs/ARCHITECTURE.md). All paths are relative to this file; no absolute paths.
import { execSync, spawn } from 'node:child_process';
import fs from 'node:fs';

const DIR = new URL('.', import.meta.url).pathname.replace(/\/$/, '');
const WEBHOOK = process.env.BRIDGE_WEBHOOK || 'http://127.0.0.1:8787/';
const PAUSE = DIR + '/BRIDGE_PAUSE';
const LOG = DIR + '/watchdog.log';
const log = m => { try { fs.appendFileSync(LOG, new Date().toISOString() + ' ' + m + '\n'); } catch {} };
const pids = pat => { try { return execSync(`ps ax -o pid,command | grep "${pat}" | grep -v grep | awk '{print $1}'`).toString().trim().split('\n').filter(Boolean); } catch { return []; } };
const spawnDetached = (cmd, args, logfile) => {
  const out = logfile ? fs.openSync(DIR + '/' + logfile, 'a') : 'ignore';
  spawn(cmd, args, { detached: true, stdio: logfile ? ['ignore', out, out] : 'ignore', cwd: DIR }).unref();
};
function tick() {
  try {
    if (fs.existsSync(PAUSE)) { log('paused — skip'); return; }
    let fixed = [];
    if (pids('listener\\.mjs').length === 0) { spawnDetached('node', [DIR+'/listener.mjs'], 'listener.log'); fixed.push('listener'); }
    if (pids('wacli sync --follow').length === 0) { spawnDetached('wacli', ['sync','--follow','--webhook',WEBHOOK,'--webhook-allow-private'], 'sync.log'); fixed.push('sync'); }
    // NOTE: the waiter (wait_dm.mjs) is intentionally NOT managed here — it must stay a
    // harness-tracked background command so its exit re-invokes the agent on a self-DM.
    if (fixed.length) log('RECOVERED: ' + fixed.join(','));
  } catch (e) { log('tick error: ' + e.message); }
}
setInterval(tick, 20000);
tick();
log('watchdog started (pid ' + process.pid + ')');
