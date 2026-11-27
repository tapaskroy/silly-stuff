# Setup

End-to-end instructions for standing up a group-chat companion from nothing. Allow about
an hour, most of it waiting for a history sync.

Everything in angle brackets is a placeholder. Nothing in this repository should ever
contain a real phone number, chat id or account id.

---

## 0. What you are building

```
WhatsApp ──► wacli sync --follow ──webhook POST──► listener.mjs
                                                        │
                                            writes triggers.ndjson
                                                        │
                                              wait_dm.mjs blocks on it
                                                        │
                                           exits ──► your agent CLI wakes
                                                        │
                                         decides, maybe calls post.sh
                                                        │
                                            wacli send text ──► WhatsApp
```

Four long-running pieces: **sync** (transport), **listener** (webhook receiver),
**watchdog** (keeps the first two alive), **waiter** (wakes the agent). Only the waiter
dies with your agent session.

---

## 1. Get a separate phone number

Run the agent on its **own** WhatsApp account, not your personal one.

A data-only eSIM, a cheap prepaid SIM, or any number that can receive one SMS during
registration will do. It needs a phone to register WhatsApp once; after that the number
lives on the linked device.

Two reasons this matters, and the second is the real one:

- Direct messages to the agent are a legitimate inbound channel. On a shared account they
  would arrive mixed with your private correspondence, which the agent must not read.
- With a separate account, "who is allowed to give instructions" has exactly one answer:
  one account id. On a shared account that boundary does not exist.

Install WhatsApp on a phone, register the new number, and keep that phone reachable. It
is the primary device and the agent is a linked device.

---

## 2. Install wacli

`wacli` is a WhatsApp CLI built on whatsmeow. MIT licensed.

- Source: <https://github.com/openclaw/wacli>
- Docs: <https://wacli.sh>

macOS or Linux with Homebrew:

```sh
brew install openclaw/tap/wacli
wacli version
```

Pick a store directory and use it on **every** command. The store holds the session keys,
the message database and downloaded media.

```sh
export WACLI_STORE=~/.wacli-agent
mkdir -p "$WACLI_STORE"
```

---

## 3. Authenticate

```sh
wacli --store "$WACLI_STORE" auth
```

This prints a QR code. On the agent's phone: WhatsApp → Settings → Linked Devices → Link a
Device → scan. **A human has to do this.** The agent cannot, and it is worth writing that
into your skill so the agent asks instead of flailing when the session expires.

Confirm, and ask the phone for some history while you are here:

```sh
wacli --store "$WACLI_STORE" auth status
wacli --store "$WACLI_STORE" auth --history-days 30 --download-media
```

The history sync can take a while on a busy account. Let it finish.

---

## 4. Find the chats to watch

```sh
wacli --store "$WACLI_STORE" groups list
wacli --store "$WACLI_STORE" chats list --json | head
```

Group ids look like `<digits>@g.us`; one-to-one chats are `<digits>@s.whatsapp.net`.
Copy the ones you want into your config. Keep that config untracked.

You also need the agent's **own** account id, because mentions of the agent arrive in
message text as bare digits rather than as a name:

```sh
wacli --store "$WACLI_STORE" auth status --json
```

---

## 5. Install an agent CLI

Any agent runtime works if it can run shell commands, keep background processes alive
between turns, and be re-invoked when a background process exits. These instructions
assume [Claude Code](https://claude.com/claude-code):

```sh
npm install -g @anthropic-ai/claude-code
claude
```

Other CLIs with the same three properties will work; the skill files are plain Markdown
and carry no vendor-specific syntax.

Put `skill/SKILL.md` where your runtime looks for skills. For Claude Code that is
`~/.claude/skills/<name>/SKILL.md`. Do the same for `skill/dm-triage/SKILL.md`.

---

## 6. Configure and start the bridge

```sh
cp bridge/bridge.config.example.sh bridge/bridge.config.sh
$EDITOR bridge/bridge.config.sh      # store path, webhook port, chat ids
```

Add `bridge/bridge.config.sh` to `.gitignore` before you put anything real in it.

**Start the webhook receiver** (writes the triggers file):

```sh
node bridge/listener.mjs
```

**Start sync pointed at it.** The flags matter:

```sh
wacli --store "$WACLI_STORE" sync --follow \
  --webhook http://127.0.0.1:<PORT>/hook \
  --webhook-allow-private \
  --webhook-secret "$(openssl rand -hex 32)" \
  --download-media \
  --max-db-size 2GB
```

- `--webhook-allow-private` is required for a localhost URL; without it the URL is refused.
- `--webhook-secret` signs each POST with `X-Wacli-Signature` (HMAC-SHA256). Verify it in
  the listener and drop anything that fails. Put the same secret in your config.
- `--download-media` fetches images in the background so the agent can read them later.
- `--max-db-size` is a guard worth setting from day one. A busy account's media cache grows
  without bound, and a full disk takes down everything on the machine, not just this.
  `--max-messages` caps by count instead.

**Then the watchdog**, which restarts whichever of those dies:

```sh
node bridge/watchdog.mjs
```

---

## 7. The single-writer problem

The store allows one writer at a time. A running `sync --follow` holds that lock, so a
naive `wacli send` while sync is running simply fails.

Two ways out:

1. **`--lock-wait`**, which has the send wait for the lock instead of failing:
   ```sh
   wacli --store "$WACLI_STORE" --lock-wait 30s send text --to <CHAT> --message "..."
   ```
   Simplest, and the right default.
2. **Stop, send, restart**, the older "lock dance". Signal sync to stop, send, let the
   watchdog revive it within its poll interval. `bridge/post.sh` implements this. It costs
   a short transport gap on every send, which the watchdog closes.

Either way, **space outbound sends 10-15 seconds apart**. Back-to-back sends trip
WhatsApp's rate limiter, and `--send-spacing` on sync can pace delegated sends for you.

Replying inside a thread needs **both** the quoted message id and its sender:

```sh
wacli --store "$WACLI_STORE" --lock-wait 30s send text \
  --to <CHAT_ID> \
  --reply-to <MESSAGE_ID> \
  --reply-to-sender <SENDER_JID> \
  --message "..."
```

Omit `--reply-to-sender` in a group and the quote silently drops; the reply lands as a
loose message beside the thread instead of inside it.

---

## 8. Start the loop

Set the marker to the current line count first, so a backlog does not replay as fresh
traffic:

```sh
wc -l < triggers.ndjson > trig_marker.txt
node bridge/wait_dm.mjs          # run in the background
```

Then start your agent with the skill loaded and let it take over. Its first tick should
verify all four processes:

```sh
for p in "wacli.*sync" "listener.mjs" "watchdog.mjs" "wait_dm.mjs"; do
  pgrep -f "$p" >/dev/null && echo "UP   $p" || echo "DOWN $p"
done
```

Use exactly this `pgrep … && echo UP || echo DOWN` form. A pipeline that ends in a filter
exits 0 whether or not it matched, so a down process shows up only as a missing line and
never as the word DOWN.

---

## 9. When it goes quiet

Symptoms look identical from the outside, so check in this order.

1. **Is the waiter running?** It is the only piece that dies with the agent session, and
   the watchdog will keep the bridge green for days without it. A green transport is not
   evidence the agent is alive.
2. **Is the session authenticated?**
   ```sh
   wacli --store "$WACLI_STORE" auth status
   wacli --store "$WACLI_STORE" doctor
   ```
   A logged-out session shows up as an endless restart loop in the watchdog log. Only a
   human rescanning the QR fixes it.
3. **Is the room actually quiet?** An empty query is not evidence of silence. Any outage
   leaves an unmarked hole in the local store. Compare the store against the triggers file:
   ```sh
   wacli --store "$WACLI_STORE" messages list --chat <CHAT_ID> --limit 3
   ```
   If the store has recent traffic the triggers file lacks, ingestion is the problem. If
   both are empty, so was the room. Note that reactions land in the store but should not
   fire triggers, so "store is newer than my last trigger" is normal, not a fault.

---

## 10. Decide the privacy posture before you start

These are policy, not configuration, and they are much easier to decide now than when
someone asks:

- **What the agent retains.** Operational notes about its own conduct are easy to defend.
  Notes about individual participants are a different category.
- **Who can read them.** If notes about people exist and only the operator can read them,
  that asymmetry is real. Name it yourself rather than discovering it under questioning.
- **What leaves the machine.** Message content, participant identifiers and anything
  derived from them should stay local. That includes evaluation corpora: a set of captured
  messages is other people's conversation however useful it is for testing.
- **Link handling.** Shared URLs routinely carry per-sender tracking parameters, so
  fetching one registers a click against the person who shared it. Default to not fetching.
- **Media.** Downloaded images from a private group are private images. They live in the
  store; keep them there.
