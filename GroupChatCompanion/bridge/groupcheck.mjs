// Read new GROUP messages since the marker, EXCLUDING the agent's own bot posts.
// Why id-based, not FromMe: the bot shares the owner's WhatsApp account, so BOTH the
// bot's posts and the owner's manual group posts are FromMe=true. We distinguish them by
// message id: post.sh logs every send to agent_group_sent.txt, so anything NOT in that
// list (members' posts AND the owner's manual posts) gets surfaced.
//
// Group JID comes from the BRIDGE_GROUP_JID env var (source bridge.config.sh). Paths are
// relative to this file.
import fs from 'fs';
const DIR = new URL('.', import.meta.url).pathname;
const GROUP = process.env.BRIDGE_GROUP_JID;
if (!GROUP) { console.error('Set BRIDGE_GROUP_JID (source bridge.config.sh).'); process.exit(1); }
const mark = fs.readFileSync(`${DIR}group_last_check.txt`, 'utf8').trim();
let botSent = new Set();
try { botSent = new Set(fs.readFileSync(`${DIR}agent_group_sent.txt`, 'utf8').split('\n').map(s=>s.trim()).filter(Boolean)); } catch {}
const lines = fs.readFileSync(`${DIR}events.ndjson`, 'utf8').trim().split('\n');
let any = false, latest = mark;
for (const line of lines) {
  if (!line.includes(GROUP)) continue;
  let e, b;
  try { e = JSON.parse(line); b = JSON.parse(e.body); } catch { continue; }
  if (b.Chat !== GROUP) continue;
  if (e.stamp <= mark) continue;
  if (e.stamp > latest) latest = e.stamp;
  if (!b.Text || !b.Text.trim()) continue;
  if (botSent.has(b.ID)) continue;           // skip the agent's own posts
  const who = b.FromMe ? `${b.PushName} (owner)` : b.PushName;
  console.log(`[${who}] ${b.Text.slice(0,200)}`);
  any = true;
}
if (!any) console.log('(no new group messages)');
console.log(`__LATEST__ ${latest}`);   // newest stamp seen, for advancing the marker
