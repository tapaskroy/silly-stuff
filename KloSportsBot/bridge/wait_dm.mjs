// One-shot waiter: baselines on current triggers, exits cleanly when a NEW
// (non-skipped) self-DM lands — which re-invokes the agent with the message.
// Launch this as a harness-tracked background command so its exit wakes the agent.
import fs from 'node:fs';
const F = new URL('./triggers.ndjson', import.meta.url).pathname;
const read = () => { try { return fs.readFileSync(F,'utf8').split('\n').filter(Boolean); } catch { return []; } };
let base = read().length;
function check() {
  const ls = read();
  if (ls.length > base) {
    ls.slice(base).forEach(l => console.log(l));
    process.exit(0);
  }
}
fs.watchFile(F, { interval: 1000 }, check);
try { fs.watch(F, check); } catch {}
console.error(`armed: watching ${F}, baseline ${base} lines`);
