# KloSportsBot

> **Status: experimental / personal project.** A hobby framework, not a product. Scrapers are best-effort and version-dated; sites change and things break.

A persona-neutral framework for a **personal AI WhatsApp sports-companion bot** that runs a prediction pool: live score commentary, kickoff and full-time result cards, automated picks, and leaderboard math — all delivered to a WhatsApp group, with a private self-DM "command channel" back to you.

## The worked example

The reference instance was built for the **KGP97 (IIT Kharagpur class of '97) "Sports Fans" WhatsApp group**, which runs a FIFA World Cup 2026 prediction pool. The pool admin set a per-game mandate: a kickoff screenshot, and a full-time result card with a one-line comment. The bot automates exactly that, and adds short witty updates on confirmed major plays while games are live.

## Persona / lineage

This framework is **persona-neutral**: it runs as whatever agent identity you configure (`<AGENT_NAME>` / `<AGENT_EMOJI>` in `skill/persona/IDENTITY.template.md`). For the record, the original reference instance was **Klo** — an AI assistant with night-owl energy, emoji 🦉. That's the heritage; it isn't hardcoded. Make it your own.

## Architecture (three layers)

```
  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
  │  browser/   │     │   bridge/   │     │    skill/    │
  │ Playwright  │     │  WhatsApp   │     │   operating  │
  │  scrapers,  │────▶│  I/O via    │◀───▶│   prompt +   │
  │  model,     │     │  wacli      │     │   persona    │
  │  submitters │     │ (watchdog,  │     │  templates   │
  │             │     │  listener,  │     │              │
  │ ESPN live ──┘     │  waiter)    │     │              │
  └─────────────┘     └─────────────┘     └──────────────┘
```

1. **`browser/`** (Node + Playwright) — logs into the pool site, scrapes fixtures/scores, screenshots prediction cards, runs a Poisson/Dixon-Coles model to submit picks, and parses the leaderboard. ESPN gamecast is scraped for live scores.
2. **`bridge/`** (Node + shell + the external `wacli` CLI) — the WhatsApp I/O. A **watchdog** keeps `wacli sync --follow` + a webhook `listener` alive; a one-shot **waiter** wakes the agent on an incoming self-DM; posting goes through a **single-writer lock dance** (because a running follow-sync holds the store lock and blocks sends).
3. **`skill/`** — the operating prompt that orchestrates the loop, plus persona templates.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the lock model, supervision model, and the self-DM failure analysis.

## What executes the skill (agent runtime)

The `skill/` layer is a **prompt, not a program** — something has to read it and act on it. That "something" is an **AI coding agent** capable of reading a skill/prompt file and running shell + Node on your machine. The reference instance is operated from **[Claude Code](https://www.anthropic.com/claude-code)** (Anthropic's agentic CLI); an equivalent agent CLI such as **OpenAI Codex** can drive it too.

> **Prerequisite:** a subscription to such an agent (Claude Code, Codex, or similar) is required — it is the runtime that orchestrates the entire loop. This repo ships the scrapers, the WhatsApp bridge, and the operating prompt; **the agent is what runs them.** The reference instance runs from Claude Code, with `skill/SKILL.md` installed as a Claude Code skill.

## The self-DM command channel

The bot posts to your **group**, but you steer it privately through a **note-to-self** — a WhatsApp message to your own number (the "Message yourself" thread):

1. You send yourself a note — e.g. *"post the leaderboard now,"* *"slow the live updates,"* *"don't cover the late game,"* or just a question.
2. The `wait_dm.mjs` **waiter** is watching that thread. The moment your self-DM lands, the waiter exits — and its exit **wakes the agent**.
3. The agent reads your instruction from the trigger log, acts on it, and **replies on the same self-DM thread** — so the exchange stays private and never reaches the group.

It's your private remote control: retune cadence, request an off-schedule post, change what gets covered, or just ask a question — all invisible to the group. (The bot's own replies are id-skiplisted so they don't re-trigger the waiter.) Because the bot shares your account, this channel is also how you talk to it without a second phone number.

## Quickstart

Full step-by-step in [`docs/SETUP.md`](docs/SETUP.md). In short:

```sh
cd browser && npm install && npx playwright install chromium && cd ..
cd bridge  && npm install && cd ..
cp templates/env.example .env                       # fill in creds + JIDs
cp browser/config.example.json browser/config.json  # set your pool URL + ratings
cp bridge/bridge.config.example.sh bridge/bridge.config.sh   # set your WhatsApp JIDs
# install + authenticate wacli (see SETUP.md), then:
node browser/login.example.mjs                      # mints browser/auth.json
node bridge/watchdog.mjs &                           # bring up the bridge
node bridge/wait_dm.mjs &                            # self-DM waiter
```

## ⚠️ Secrets warning

This bot uses **your** WhatsApp account and a **live pool session**. Treat every secret as radioactive:

- **Never commit** `auth.json`, `.env`, `bridge.config.sh`, real `USER.md`/`MEMORY.md`, `events.ndjson`/`triggers.ndjson`, logs, or screenshots with member data.
- All of these are gitignored by default. Read [`SECURITY.md`](SECURITY.md) before your first commit and run the sanitization checklist.

## Responsible use

The bot **shares the owner's WhatsApp account** — treat it like sending from your own phone. Don't auto-post to groups you don't administer. This is a self-limiting design (you can only spam yourself and your own groups), and that's on purpose.

## Requirements

- An **AI coding-agent runtime + subscription** — [Claude Code](https://www.anthropic.com/claude-code) (what the reference instance runs on) or an equivalent agent CLI such as OpenAI Codex. This is what executes the `skill/` prompt and drives the loop; see [What executes the skill](#what-executes-the-skill-agent-runtime).
- Node ≥ 22, Python ≥ 3.11 (model uses stdlib `math` only — no pip deps)
- [Playwright](https://playwright.dev/) + Chromium
- [`wacli`](docs/SETUP.md#wacli) — the external WhatsApp CLI (hard dependency; not redistributed here)

## License

[MIT](LICENSE) © 2026 Tapas Roy.

## Roadmap (direction only)

Built so these slot in without restructuring: cloud hosting (keep all I/O behind config/env); a dedicated WhatsApp number for the bot (removes the shared-account disambiguation hack; `bridge.config` already abstracts identities); multi-user with admin approval (the self-DM command channel + skiplist + supervision are the seed of an approval queue).
