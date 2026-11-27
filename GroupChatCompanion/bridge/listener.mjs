// Self-DM bridge: receives wacli webhook POSTs, extracts self-DM (note-to-self) messages,
// writes user-incoming ones to triggers.ndjson (skipping the agent's own sends).
//
// Configure your own self-DM identifiers via the BRIDGE_SELF_IDS env var (comma-separated).
// Modern WhatsApp addresses note-to-self by a LID and/or the phone JID, so usually you
// list both, e.g.  BRIDGE_SELF_IDS="<your-lid>@lid,<your-number>@s.whatsapp.net"
// (source these from bridge.config.sh — see bridge.config.example.sh). No identifiers are
// hardcoded here.
import http from 'node:http';
import fs from 'node:fs';

const PORT = Number(process.env.BRIDGE_PORT || 8787);
const SELF_IDS = (process.env.BRIDGE_SELF_IDS || '')
  .split(',').map(s => s.trim()).filter(Boolean);
if (SELF_IDS.length === 0) {
  console.error('No BRIDGE_SELF_IDS set — source bridge.config.sh first (see bridge.config.example.sh).');
}
const DIR = new URL('.', import.meta.url).pathname;
const RAW = DIR + 'events.ndjson';
const TRIG = DIR + 'triggers.ndjson';
const SKIP = DIR + 'agent_sent_ids.txt';

function skiplist() {
  try { return new Set(fs.readFileSync(SKIP, 'utf8').split('\n').map(s=>s.trim()).filter(Boolean)); }
  catch { return new Set(); }
}
// recursively pull first matching value for any of the candidate keys
function dig(obj, keys) {
  if (obj == null || typeof obj !== 'object') return undefined;
  for (const k of Object.keys(obj)) {
    if (keys.includes(k) && obj[k] != null && typeof obj[k] !== 'object') return obj[k];
  }
  for (const k of Object.keys(obj)) {
    const v = dig(obj[k], keys);
    if (v !== undefined) return v;
  }
  return undefined;
}

http.createServer((req, res) => {
  let body = '';
  req.on('data', c => body += c);
  req.on('end', () => {
    const stamp = new Date().toISOString();
    fs.appendFileSync(RAW, JSON.stringify({stamp, body}) + '\n');
    try {
      const j = JSON.parse(body);
      const chat = dig(j, ['Chat','chat','chat_jid','chatJID','ChatJID','jid','remoteJid']);
      const text = dig(j, ['Text','text','body','message','caption','conversation','Body','DisplayText']);
      const id   = dig(j, ['ID','id','msg_id','MsgID','message_id','stanzaId']);
      const fromMe = dig(j, ['FromMe','from_me','fromMe']);
      const isSelf = SELF_IDS.includes(String(chat||''));
      if (isSelf) {
        const skipped = id && skiplist().has(String(id));
        const rec = {stamp, id: id??null, fromMe: fromMe??null, text: text??null, skipped: !!skipped};
        if (!skipped && text) fs.appendFileSync(TRIG, JSON.stringify(rec) + '\n');
        console.log(`[self-dm] id=${id} skipped=${!!skipped} text=${JSON.stringify(text)}`);
      }
    } catch (e) {
      console.log('parse-skip:', e.message);
    }
    res.writeHead(200); res.end('ok');
  });
}).listen(PORT, '127.0.0.1', () => console.log(`bridge listener on http://127.0.0.1:${PORT}`));
