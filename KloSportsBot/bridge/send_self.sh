#!/bin/sh
# Reply on the self-DM (note-to-self) thread. Atomic lock-dance (pause watchdog, free the
# lock, send, clear pause -> watchdog revives sync ~20s) + record the sent msg id to the
# skiplist so the bridge won't re-trigger the waiter on the agent's own reply.
# Usage: send_self.sh "message text"
#
# SELF_DM_TARGET (your note-to-self JID) is sourced from bridge.config.sh — see
# bridge.config.example.sh. Nothing is hardcoded here.
cd "$(dirname "$0")" || exit 1
[ -f bridge.config.sh ] && . ./bridge.config.sh
: "${SELF_DM_TARGET:?set SELF_DM_TARGET in bridge.config.sh}"
MSG="$1"
touch BRIDGE_PAUSE
ps ax -o pid,command | grep "[w]acli sync --follow" | awk '{print $1}' | xargs -r kill -INT 2>/dev/null
for i in $(seq 1 12); do ps ax | grep -q "[w]acli sync --follow" || break; sleep 1; done
OUT=$(wacli --json send text --to "$SELF_DM_TARGET" --message "$MSG" 2>&1)
echo "$OUT"
ID=$(echo "$OUT" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)
[ -n "$ID" ] && echo "$ID" >> agent_sent_ids.txt
rm -f BRIDGE_PAUSE
