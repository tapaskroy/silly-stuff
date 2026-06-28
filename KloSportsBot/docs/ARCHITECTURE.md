# Architecture

KloSportsBot is three cooperating layers running on one host. This doc explains how they
hand off, the two non-obvious mechanisms that make the bridge reliable (the **single-writer
lock model** and the **supervision model**), the self-DM failure analysis, and the **DOM
contract** the scrapers assume so you can adapt them to a non-KGP97 pool.

## The three layers

```
ESPN gamecast ──▶ browser/live2.mjs ──▶ state_<gameId>.txt (diff) ──▶ confirmed-major post
pool site     ──▶ browser/*.mjs (screenshots / cards / leaderboard / submit)
                                   │
                                   ▼
                            bridge/post.sh ──▶ wacli ──▶ WhatsApp group
owner's phone ──▶ WhatsApp ──▶ wacli sync --follow ──▶ listener.mjs ──▶ triggers.ndjson
                                                                         │
                                                          wait_dm.mjs exits ──▶ wakes the agent
                                   │
                                   ▼
                            skill/SKILL.md orchestrates the whole loop as the agent persona
```

1. **`browser/` (Playwright)** — the data + action layer. Scrapes the pool's `/tournament`
   for fixtures, ESPN for live scores, the `/predict` board for cards/screenshots, and the
   leaderboard. Submits the agent's own picks via a Poisson/EP model. Reads everything
   pool-specific from `config.json`.
2. **`bridge/` (Node + shell + `wacli`)** — the WhatsApp I/O layer. Inbound: `wacli sync
   --follow` streams messages to a webhook `listener` that filters self-DMs into
   `triggers.ndjson`. Outbound: `post.sh` / `send_self.sh` send through `wacli`.
3. **`skill/`** — the operating prompt (`SKILL.md`) that drives the loop, plus persona
   templates the agent loads at startup.

## The single-writer lock model

**`wacli` is single-writer.** A running `wacli sync --follow` holds the local message-store
lock. While it's held, **any `wacli send` blocks** — you cannot post while you're following.
This is a property of `wacli`, not a quirk of this project.

So every send does a **lock dance** (`bridge/post.sh`, `bridge/send_self.sh`):

1. `touch BRIDGE_PAUSE` — tells the watchdog to stop reviving sync.
2. Kill the running `wacli sync --follow` (`kill -INT`), wait for it to exit (≤12s).
3. `wacli send ...` — now the lock is free, the send succeeds.
4. `rm -f BRIDGE_PAUSE` — clears the pause; the **watchdog** (next 20s tick) revives sync.

Note the script does **not** restart sync itself. A sync spawned by the script is part of the
shell's process group and gets torn down when the Bash invocation ends; the **persistent
watchdog** is the reliable owner of follow-sync. Cost: each send opens a ~20s window where no
process is subscribed to the WhatsApp stream — see the ingestion-gap analysis in
[`../bridge/SELF_DM_ROBUSTNESS_SPEC.md`](../bridge/SELF_DM_ROBUSTNESS_SPEC.md).

## The supervision model

Two long-lived processes, supervised differently **on purpose**:

- **`watchdog.mjs`** — a 20s loop that restarts `listener.mjs` and `wacli sync --follow` if
  either is missing, and respects `BRIDGE_PAUSE`. The watchdog itself is launched as a
  *harness-tracked background command*, so if it dies, the agent harness is notified and
  relaunches it.
- **`wait_dm.mjs` (the waiter)** — a **one-shot** process. It baselines on `triggers.ndjson`
  and **exits** when a new self-DM lands. That process-exit is the wake signal: it
  re-invokes the agent with the new message. The waiter is **deliberately NOT
  watchdog-managed** — if the watchdog respawned it, the respawn wouldn't carry the
  harness-tracking that makes its exit a wake. So the agent relaunches the waiter after every
  exit (DM handled, or crash).

## Bot-shares-owner-account caveat

The bot posts from the **owner's** WhatsApp account. So both the bot's posts *and* the
owner's own manual group posts are `FromMe=true` — you can't tell them apart by `FromMe`
alone. The fix: `post.sh` logs every bot send's message id to `agent_group_sent.txt`, and
`groupcheck.mjs` surfaces any group message whose id is **not** in that list (members' posts
*and* the owner's manual posts), so the agent never echoes its own posts back to itself.

## Data flow: live commentary

1. `tournament.mjs` scrapes fixtures → kickoff epochs → the agent sets per-game timers.
2. On a poll wake, `live2.mjs <gameId> <slug>` scrapes ESPN's gamecast (public, no auth).
3. The agent diffs the score + goal list against `state_<gameId>.txt`.
4. A change is posted **only when the header score number confirms it** (post-VAR). If the
   summary lists a goal but the header hasn't moved, it's mid-VAR — re-poll, don't post.
5. After posting, `state_<gameId>.txt` is updated so the event isn't reposted.

## The DOM contract (porting to another pool)

The scrapers assume a pool site that exposes this contract. KGP97's Vercel app is the
reference implementation; any pool exposing the same shapes can be driven by editing
`browser/config.json` (and selectors if needed):

- **Routes** (configurable in `config.json.routes`): a login page; `/tournament` listing
  fixtures with dates, teams, scores, kickoff times; a `/predict` board; a past-results view
  (`/predict?tab=past`); a leaderboard/standings page.
- **Predict cards**: each open game is a card with **two `<input type="number">`** fields
  (home/away score) and a **"Save" button**. Frozen (post-kickoff) cards lack editable
  inputs. The submitters and `predict_open.mjs` rely on this.
- **Result cards**: a past/result card has a `<home> vs <away>` header, an `N-N FT` final,
  and an "All picks:" block per game (for the leaderboard parser).
- **Share links**: result/cup cards expose a "Share to WhatsApp" link
  (`<a aria-label="Share to WhatsApp" href="...wa.me/?text=...">`); the extractors decode the
  `text` query param.
- **LIVE / FT markers**: fixture/score text carries `LIVE` and `FT` markers used to classify
  state.

If your pool differs, change the routes in `config.json` and adjust the selectors in the
relevant `browser/*.mjs` script — the parsing logic generalizes.

## External live-score source

`live2.mjs` scrapes **ESPN gamecast** — public, no auth, but it's **scraping**, so it's
brittle to ESPN redesigns and is not an official API. Pin Playwright; expect occasional
breakage when ESPN ships UI changes.
