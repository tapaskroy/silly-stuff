#!/bin/sh
# Atomic group/self post: pause watchdog, free the single-writer lock, send, unpause.
# usage: post.sh text "<jid>" "<message>"  |  post.sh file "<jid>" "<path>" "<caption>"
#
# wacli is single-writer: a running `sync --follow` holds the store lock and blocks sends.
# So we pause the watchdog, kill follow-sync, send, then clear the pause — the watchdog
# (20s loop) revives sync. See docs/ARCHITECTURE.md for the full lock model.
cd "$(dirname "$0")" || exit 1
[ -f bridge.config.sh ] && . ./bridge.config.sh
MODE="$1"; JID="$2"
touch BRIDGE_PAUSE
ps ax -o pid,command | grep "[w]acli sync --follow" | awk '{print $1}' | xargs -r kill -INT 2>/dev/null
for i in $(seq 1 12); do ps ax | grep -q "[w]acli sync --follow" || break; sleep 1; done
if [ "$MODE" = "file" ]; then
  OUT=$(wacli --json send file --to "$JID" --file "$3" --caption "$4")
else
  OUT=$(wacli --json send text --to "$JID" --message "$3")
fi
RC=$?
printf '%s\n' "$OUT"
# Log this send's message id so the group sweep (groupcheck.mjs) can distinguish the
# agent's own posts from the owner's manual group posts — both are FromMe=true when the
# bot shares the owner's WhatsApp account.
printf '%s\n' "$OUT" | grep -oE '"id":"[^"]*"' | head -1 | sed 's/.*"id":"//; s/"$//' >> agent_group_sent.txt
# Clear pause; the watchdog reliably revives follow-sync within ~20s. (We don't restart
# sync here — a script-spawned detached sync doesn't survive shell process-group teardown;
# the persistent watchdog is the reliable owner.)
rm -f BRIDGE_PAUSE
exit $RC
