# KloSportsBot

> **Status: experimental / personal project.** A hobby framework, not a product. Scrapers are best-effort and version-dated; sites change and things break.

A persona-neutral framework for a **personal AI WhatsApp sports-companion bot** that runs a prediction pool: live score commentary, kickoff and full-time result cards, automated picks, and leaderboard math — all delivered to a WhatsApp group, with a private self-DM "command channel" back to you.

## The worked example

The reference instance was built for the **KGP97 (IIT Kharagpur class of '97) "Sports Fans" WhatsApp group**, which runs a FIFA World Cup 2026 prediction pool on a Vercel app ([kgp97-wc2026.vercel.app](https://kgp97-wc2026.vercel.app)). The pool admin set a per-game mandate: a kickoff screenshot, and a full-time result card with a one-line comment. The bot automates exactly that, and adds short witty updates on confirmed major plays while games are live.

> The pool is named here with the pool admin's blessing — swap to a generic name if you prefer.

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

- Node ≥ 22, Python ≥ 3.11 (model uses stdlib `math` only — no pip deps)
- [Playwright](https://playwright.dev/) + Chromium
- [`wacli`](docs/SETUP.md#wacli) — the external WhatsApp CLI (hard dependency; not redistributed here)

## License

[MIT](LICENSE) © 2026 Tapas Roy.

## Roadmap (direction only)

Built so these slot in without restructuring: cloud hosting (keep all I/O behind config/env); a dedicated WhatsApp number for the bot (removes the shared-account disambiguation hack; `bridge.config` already abstracts identities); multi-user with admin approval (the self-DM command channel + skiplist + supervision are the seed of an approval queue).
