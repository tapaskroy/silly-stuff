#!/usr/bin/env python3
"""Self-DM ingestion backstop (snapshot edition).

The webhook -> listener -> triggers.ndjson -> waiter path can silently miss a
self-DM (observed in practice: a note-to-self absent from the store while group
messages flowed normally, because the linked device's follow-sync was briefly
down during a burst of posts). This script is the safety net.

It reads a SNAPSHOT COPY of wacli's store DB (zero lock contention, and crucially
ZERO follow-sync interruption — so it never adds the offline windows that cause
the very gap it guards against), finds recent self-chat messages, and appends any
that aren't already queued to triggers.ndjson so the waiter delivers them through
the normal path.

Run it on a short recurring timer (e.g. every ~180s) alongside the webhook waiter:
the webhook is the instant primary path; this is the belt-and-suspenders backstop.

Limitation: it can only recover messages that REACHED the store. A message
WhatsApp never delivered to this linked device (dropped while sync was down) is
not in the store and cannot be recovered here — the fix for that is keeping
follow-sync maximally alive (don't kill it more than necessary).

Config (env, source bridge.config.sh first):
  SELF_DM_TARGET   your note-to-self JID, e.g. <your-number>@s.whatsapp.net (required)
  WACLI_STORE_DIR  wacli store dir (default: ~/.wacli)
"""
import json, os, sqlite3, shutil, sys, datetime

DIR  = os.path.dirname(os.path.abspath(__file__))
TRIG = os.path.join(DIR, 'triggers.ndjson')
SENT = os.path.join(DIR, 'agent_sent_ids.txt')   # the agent's own sends, to skip

SELF = os.environ.get('SELF_DM_TARGET')
if not SELF:
    print('selfdm_backstop: set SELF_DM_TARGET (source bridge.config.sh first)', file=sys.stderr)
    sys.exit(1)

STORE_DIR = os.path.expanduser(os.environ.get('WACLI_STORE_DIR', '~/.wacli'))
STORE = os.path.join(STORE_DIR, 'wacli.db')
SNAP  = os.path.join('/tmp', 'wacli_snap')

# 1) snapshot the store (db + wal + shm together so WAL writes are visible)
os.makedirs(SNAP, exist_ok=True)
for ext in ('', '-wal', '-shm'):
    try:
        shutil.copy2(STORE + ext, os.path.join(SNAP, 'wacli.db' + ext))
    except FileNotFoundError:
        pass

# 2) read recent from-me self-chat messages from the snapshot (read-only)
try:
    con = sqlite3.connect(f"file:{os.path.join(SNAP, 'wacli.db')}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT msg_id, ts, coalesce(text,''), coalesce(media_type,'') "
        "FROM messages WHERE chat_jid=? AND from_me=1 ORDER BY ts DESC LIMIT 25",
        (SELF,)).fetchall()
    con.close()
except Exception as e:
    print('selfdm_backstop: db read error:', e, file=sys.stderr)
    sys.exit(0)

# 3) dedup against what's already queued and the agent's own sends
def load_ids(path, from_json):
    out = set()
    try:
        for line in open(path):
            if from_json:
                try: out.add(json.loads(line).get('id'))
                except Exception: pass
            else:
                s = line.strip()
                if s: out.add(s)
    except FileNotFoundError:
        pass
    return out

known = load_ids(TRIG, True) | load_ids(SENT, False)

new = []
for msg_id, ts, text, mtype in reversed(rows):     # oldest-first
    if not msg_id or msg_id in known:
        continue
    text = (text or '').strip()
    if not text:
        if not mtype:
            continue
        text = f'[media: {mtype} — recover via its msg_id {msg_id}]'
    stamp = (datetime.datetime.utcfromtimestamp(int(ts)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
             if ts else '')
    new.append((msg_id, text, stamp))

# 4) feed missed messages into the trigger stream; the waiter picks them up
if new:
    with open(TRIG, 'a') as f:
        for mid, txt, stamp in new:
            f.write(json.dumps({'stamp': stamp, 'id': mid, 'fromMe': True,
                                'text': txt, 'skipped': False, 'via': 'backstop'}) + '\n')

print(f'selfdm_backstop: {len(new)} recovered self-DM(s) appended')
for mid, txt, stamp in new:
    print('  +', stamp, '|', txt[:60])
