# Setup

Step-by-step to stand up your own instance. Everything pool-specific and every secret lives
in a gitignored `*.example` → real-file copy; you never edit a committed file with real data.

## 0. Prerequisites

- **An AI coding-agent runtime + subscription.** This loop is *driven by an agent*, not a standalone daemon. The reference instance runs on **[Claude Code](https://www.anthropic.com/claude-code)** (Anthropic's agentic CLI — a subscription is required); an equivalent agent CLI such as **OpenAI Codex** that can read a skill/prompt file and run shell + Node works too. The agent executes `skill/SKILL.md` and orchestrates everything (step 6).
- **Node ≥ 22** and **Python ≥ 3.11** (the model uses only the Python stdlib — no pip deps).
- **Playwright + Chromium**.
- **`wacli`** — the external WhatsApp CLI (see step 2).

```sh
cd browser && npm install && npx playwright install chromium && cd ..
cd bridge  && npm install && cd ..
```

## 1. Copy the templates

```sh
cp templates/env.example .env
cp browser/config.example.json browser/config.json
cp bridge/bridge.config.example.sh bridge/bridge.config.sh
cp skill/persona/IDENTITY.template.md skill/persona/IDENTITY.md
cp skill/persona/USER.template.md     skill/persona/USER.md
cp skill/persona/MEMORY.template.md   skill/persona/MEMORY.md
```

All of the copied (real) files are gitignored. Fill them in:

- **`.env`** — pool login (`POOL_EMAIL` / `POOL_PASSWORD`) and your WhatsApp identifiers.
- **`browser/config.json`** — `poolBase`, route paths, timezone, and the team-ratings tables
  for the model. The shipped values are generic football priors — edit for your competition.
- **`bridge/bridge.config.sh`** — `SELF_DM_TARGET`, `BRIDGE_SELF_IDS`, `BRIDGE_GROUP_JID`
  (you'll get these in step 4).
- **`skill/persona/IDENTITY.md`** — your agent's name + emoji.

Load the env before running scripts:

```sh
set -a; . ./.env; set +a
```

## 2. <a name="wacli"></a>Install and authenticate `wacli`

`wacli` is the hard external dependency for WhatsApp I/O — it is **not** redistributed here.
Install it from its upstream source / your package manager, then authenticate:

```sh
wacli auth          # shows a QR — scan it from your phone's WhatsApp (a human must do this;
                    # the agent cannot scan a QR)
wacli auth status   # confirm you're authenticated
```

The single-writer lock behavior described in [`ARCHITECTURE.md`](ARCHITECTURE.md) is a
property of `wacli` — keep that in mind when scripting sends.

## 3. Generate your pool session

```sh
node browser/login.example.mjs   # reads POOL_EMAIL / POOL_PASSWORD from the env,
                                 # writes a gitignored browser/auth.json
```

Adjust the login selectors in `login.example.mjs` if your pool's form differs. If `auth.json`
ever expires (the scrapers start landing on the login page), re-run this.

## 4. Find your WhatsApp identifiers

Start follow-sync pointed at the local webhook and watch the raw log:

```sh
node bridge/listener.mjs &                                   # webhook receiver on :8787
wacli sync --follow --webhook http://127.0.0.1:8787/ --webhook-allow-private &
```

Now, from your phone:

- Send yourself a **note-to-self** message. The matching event's `Chat` field gives you your
  self identifier(s) — often a `*@lid` and/or your `*@s.whatsapp.net` phone JID. Put both in
  `BRIDGE_SELF_IDS`, and your phone JID in `SELF_DM_TARGET`.
- Send a message in the **pool group**. Its `Chat` is a `*@g.us` value → `BRIDGE_GROUP_JID`.

You can read these from `bridge/events.ndjson` (the raw webhook log). Fill them into
`bridge/bridge.config.sh` (and mirror into `.env`). Stop these processes once you have the
values; the watchdog will own them from here.

## 5. Run the bridge

```sh
cd bridge && . ./bridge.config.sh
node watchdog.mjs &     # brings up listener + follow-sync within one 20s tick
node wait_dm.mjs &      # self-DM waiter (its exit wakes the agent)
cd ..
```

Verify everything is up:

```sh
pgrep -f 'node.*watchdog.mjs'
pgrep -f 'wacli sync --follow'
pgrep -f 'node.*listener.mjs'
pgrep -f 'node.*wait_dm.mjs'
tail -n 20 bridge/watchdog.log
```

Smoke-test a post (use your real group JID from the config):

```sh
bridge/post.sh text "$BRIDGE_GROUP_JID" "hello from the bridge"
```

## 6. Wire up the skill / agent loop

**This loop is run by an AI coding agent** (see [Prerequisites](#0-prerequisites)) — the
reference instance runs on **[Claude Code](https://www.anthropic.com/claude-code)**. Install
`skill/SKILL.md` as a skill your agent can invoke — in Claude Code, place it under your skills
directory (e.g. `~/.claude/skills/<your-bot>/SKILL.md`) — and fill in its placeholders
(`<AGENT_NAME>`, `<AGENT_EMOJI>`, `<GROUP_JID>`, `<SELF_DM_TARGET>`, `<POOL_BASE>`,
`<REPO_DIR>`, `<POOL_ADMIN>`). Invoking the skill is what kicks off the loop.

The agent loads the persona files (`skill/persona/*.md`), stands up the bridge, schedules
per-game timers, and runs the live loop. The prediction model is driven from the command
line, e.g.:

```sh
node browser/predict_open.mjs
python3 browser/predict_model.py "Portugal,DR Congo" "England,Croatia"
node browser/submit_picks.mjs '[["Portugal",2,0],["England",1,0]]'
node browser/verify_picks.mjs
```

### Steering it live — the self-DM command channel

Once the loop is running, you control the bot **privately** by sending yourself a
**note-to-self** on WhatsApp (the same "Message yourself" thread from step 4). The bot posts
to the group, but you talk to it here:

1. You send yourself a note — e.g. *"post the leaderboard now,"* *"slow the live updates,"*
   *"skip the late game,"* or just a question.
2. The `wait_dm.mjs` **waiter** is watching that thread. Your message makes it exit, and its
   exit **wakes the agent** (it's a one-shot — the agent relaunches it after each wake).
3. The agent reads your note from `bridge/triggers.ndjson`, acts on it, and **replies on the
   same self-DM thread** — never in the group.

This is your remote control: retune cadence, request an off-schedule post, change what's
covered, or ask a question, all invisible to the group. Because the bot shares your WhatsApp
account, the self-DM channel is how you command it without a second phone number. (The bot's
own replies are id-skiplisted via `bridge/post.sh` / `send_self.sh` so they don't
re-trigger the waiter.)

## 7. Genericizing for a non-FIFA / non-KGP97 pool

- Set `poolBase` and `routes` in `browser/config.json` to your pool's URL + paths.
- Replace the `teamRatings` / `eloRatings` tables with your competition's teams.
- If your pool's DOM differs from the contract in
  [`ARCHITECTURE.md`](ARCHITECTURE.md#the-dom-contract-porting-to-another-pool), adjust the
  selectors in the relevant `browser/*.mjs` script — the parsing logic is generic.
- Swap the live-score source if you're not covering soccer (the ESPN scrapers in
  `live2.mjs` / `scorers.mjs` are soccer-gamecast-specific).

## Before you commit anything

Run the sanitization checklist in [`../SECURITY.md`](../SECURITY.md). Confirm
`git status --ignored` shows your real `auth.json`, `.env`, `bridge.config.sh`, `config.json`,
and persona files as **ignored**, never staged.
