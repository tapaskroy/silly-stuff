# Bridge configuration — copy to bridge.config.sh (gitignored) and fill in your values.
#
#   cp bridge.config.example.sh bridge.config.sh
#   # then edit bridge.config.sh with your real WhatsApp identifiers
#
# These are YOUR WhatsApp identifiers. Treat them as semi-sensitive: do NOT commit the
# filled-in bridge.config.sh (it is already gitignored). The shell scripts source this
# file; the Node scripts read the same values from the matching env vars, so export them
# in the shell you launch those from.
#
# How to find these: `wacli groups list` and `wacli chats list --json` give you the JIDs
# directly — see steps 3 and 4 of docs/SETUP.md. Failing that, watch events.ndjson while
# you send yourself a note-to-self; the Chat field on each inbound event is the value.

# Your note-to-self thread target (where send_self.sh delivers replies).
# Modern WhatsApp usually wants the phone JID here.
export SELF_DM_TARGET="<YOUR_PHONE>@s.whatsapp.net"

# All identifiers the listener should treat as "self" (note-to-self) — comma-separated.
# Note-to-self often arrives addressed by a LID, so list both the LID and the phone JID.
export BRIDGE_SELF_IDS="<YOUR_LID>@lid,<YOUR_PHONE>@s.whatsapp.net"

# The group you post coverage to. Get its JID from the webhook log (a *@g.us value).
export BRIDGE_GROUP_JID="<YOUR_GROUP_ID>@g.us"

# Local webhook the watchdog points follow-sync at (rarely needs changing).
export BRIDGE_WEBHOOK="http://127.0.0.1:8787/"
export BRIDGE_PORT="8787"
