# Security & Privacy

This bot uses **your** WhatsApp account and a **live, logged-in pool session**. A single
leaked secret can hand someone your session or your phone identifiers. Read this before your
first commit.

## NEVER COMMIT — the exclusion list

All of these are gitignored by default. If you ever see one show up in `git status` (not
ignored), stop and fix `.gitignore` before committing.

| What | Why it's dangerous |
|---|---|
| `browser/auth.json` (real) | Live pool session cookie — full account access. Ship only `auth.json.example` (`{"cookies":[],"origins":[]}`). |
| `.env` (real) | Pool email/password and your WhatsApp JIDs. |
| `bridge/bridge.config.sh` (real) | Your phone JID, LID, and group JID. Semi-secret identifiers. |
| `browser/config.json` (real) | Your pool URL (and ratings, if you treat them as private). |
| `skill/persona/USER.md`, `MEMORY.md`, `IDENTITY.md` (real) | Personal data about the owner / operational memory. Only the `*.template.md` scaffolds and `SOUL.md` ship. |
| `events.ndjson`, `triggers.ndjson` | Raw WhatsApp message bodies (group + self-DM). Real people's words. |
| `agent_sent_ids.txt`, `agent_group_sent.txt`, `group_last_check.txt`, `state_*.txt`, `BRIDGE_PAUSE` | Run-state; may embed ids/JIDs. |
| `*.log` (`watchdog.log`, `listener.log`, `sync.log`, `waiter.log`) | Logs can contain message text and JIDs. |
| `*.png` / screenshots with member names or picks | Other people's private predictions. Only redacted/synthetic images belong in `docs/images/`. |
| `*.csv` / `*.json` sim dumps, scratch scripts | Tournament-day throwaways; not part of the framework. |
| `node_modules/` | Rebuilt via `npm install`. |

Treat your **phone number, WhatsApp JID, LID, and group JID as semi-secret**. They're not
passwords, but they identify you and your group; keep them in the gitignored
`bridge.config.sh` / `.env`, never in committed code.

## Pre-commit sanitization checklist

Run this before **every** PR merge:

- [ ] No `auth.json` with real cookies — only the empty `.example`.
- [ ] No real credentials — grep for your pool password, login email, any password string.
- [ ] No phone numbers / JIDs — grep for `@s.whatsapp.net`, `@lid`, `@g.us`, and any numeric JID.
- [ ] No personal-data files — `events.ndjson`, `triggers.ndjson`, real `USER.md` / `MEMORY.md`.
- [ ] No absolute machine paths (`/Users/...`, `/home/...`) in shipped code — all dir-relative or config-driven.
- [ ] No screenshots showing real member names or picks.
- [ ] `.gitignore` covers every exclusion above; `git status --ignored` confirms it.

A combined grep (run from the repo root, excluding examples/templates and `node_modules`):

```sh
grep -rIn -E '@s\.whatsapp\.net|@lid|@g\.us|/Users/|/home/[a-z]|password|secret|BEGIN [A-Z ]*PRIVATE KEY' . \
  --exclude-dir=node_modules --exclude-dir=.git \
  --exclude='*.example*' --exclude='*.template*' --exclude='SECURITY.md' --exclude='CONTRIBUTING.md'
```

It should return nothing.

## Responsible use

- The bot **shares the owner's WhatsApp account** — every post is "from you." Don't auto-post
  to groups you don't administer. Don't impersonate.
- This is a self-limiting design by construction: you can only message yourself and your own
  groups. Keep it that way.

## Reporting a vulnerability or accidental leak

If you find a secret committed to this repo (or its history), or a vulnerability in the code,
**do not open a public issue containing the secret**. Contact the maintainer (Tapas Roy)
privately via the repository's contact channel so the session can be rotated and the history
scrubbed first. If a live `auth.json` is ever exposed, the fix is to **log out / rotate the
pool session immediately**, then purge it from history.
