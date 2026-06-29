# Self-DM Channel Robustness — Spec

Status: **DRAFT — design only.**
Scope: the self-DM path owner → WhatsApp → bridge → wake the agent. Out of scope: group posting, the browser/analytics scripts, the pool model.

This is shipped as a worked design note: a real two-layer failure analysis of the bridge's notification path, kept because the failure model generalizes to any "wake an agent on an inbound message" pipeline. Incident specifics (dates, message text, names) are abstracted.

---

## 0. Why this exists

The self-DM channel went dark twice. Both times the owner noticed before the agent did. They were **two different failures at two different layers** — fixing one would not have caught the other. This spec leads with the root cause of each, proven from on-disk artifacts, and only then proposes a design.

The path has two independent layers, and each failure lives in exactly one:

```
owner's phone
   │  (WhatsApp servers)
   ▼
wacli sync --follow --webhook   ──①── INGESTION layer  (message enters the bridge)
   │  POST :8787
   ▼
listener.mjs ─► triggers.ndjson
   │
   ▼
wait_dm.mjs (waiter) exits ──────②── NOTIFICATION layer (a captured message wakes the agent)
   │  process-exit
   ▼
harness re-invokes the agent
```

- **Failure A = ingestion layer (①).** The message never reached `triggers.ndjson`. It was lost before the bridge ever saw it.
- **Failure B = notification layer (②).** The message *did* reach `triggers.ndjson`, but no wake fired, so the agent was never re-invoked.
- **Failure C = the wake-while-busy gap (②, deeper).** The wake only works if it arrives while the agent is **idle**. If the agent is mid-turn (actively scraping, posting, writing), the waiter fires, exits, and — because it is one-shot — leaves the channel **unguarded** while the collided wake produces no fresh action. This is the real root cause underneath A and B: **there is no end-of-work reconciliation; notification depends entirely on a wake landing during idle.**

---

## 1. Root cause — Failure A (ingestion gap)

**Incident.** An inbound self-DM never arrived. Its contents were only learned when the owner re-typed it hours later.

**Evidence (on disk, verified):**
- Grep of the **raw webhook log** `events.ndjson` for the message text returns only a later *quote* of the lost message, not the original.
- Raw events were flowing immediately before, so the listener and webhook were alive. The original is simply **absent from the raw log** — it was lost upstream of `listener.mjs`, i.e. inside or before `wacli sync --follow`.
- The connection was visibly unstable that day: dozens of websocket/EOF errors in `sync.log`, and the watchdog logged well over a hundred `RECOVERED: sync` events — sync dropping and being respawned repeatedly.

**Mechanism.** `wacli sync --follow` is a **push/stream** consumer of a websocket. When that socket drops (EOF) there is a **reconnect gap** — a window where no process is subscribed to the WhatsApp stream. Follow mode is **not a reconciling fetch**: on reconnect it resumes the live stream, it does **not** re-pull messages delivered during the gap. Anything that arrives in the gap is gone from the pipeline. With sync cycling many times a day, the probability that a given DM lands inside a gap is small per-message but non-trivial over a day.

**Aggravators (our own behavior widened the gaps):**
- The **lock-dance** on every send (`post.sh` / `send_self.sh`) deliberately **kills follow-sync**, sends, and waits ~20s for the watchdog to revive it. Every outbound message therefore opens a ~20s ingestion blackout. On a busy day these self-inflicted gaps stack up.
- **Rapid sends** can trigger a WhatsApp rate-limit warning, which can further disrupt the connection.

**Root cause, stated plainly:** ingestion is **push-only and lossy across reconnects**, and our send mechanism repeatedly tears the connection down. There is no mechanism that ever asks "what did I miss while disconnected?"

---

## 2. Root cause — Failure B (notification gap)

**Incident.** A group member's question came in. The agent didn't respond; the owner had to nudge.

**Evidence (on disk, verified):**
- The message reached `triggers.ndjson` **twice** (original + a resend), several minutes apart. So ingestion (layer ①) worked fine this time.
- Despite two queued triggers spanning several minutes, **zero wakes fired**. The only possible explanation: the **waiter (`wait_dm.mjs`) was not running** during that window.

**Mechanism — three compounding defects in the waiter:**

1. **It is unsupervised by design.** `watchdog.mjs` explicitly manages only `listener.mjs` and follow-sync; its own comments state the waiter is intentionally not managed there — it must stay harness-tracked. So if the waiter dies, **nothing restarts it**. The whole notification layer hinges on a single unsupervised one-shot process.

2. **Relaunch is cwd-fragile.** Earlier, the waiter was relaunched from the wrong directory, failed with "no such file" / exit 1, and the relaunch **silently did not take**. A failed relaunch is indistinguishable from success unless you re-check `pgrep`. (This framework version makes the scripts cwd-independent via `$(dirname "$0")` / `import.meta.url`, which removes this specific defect.)

3. **It is forgetful on restart.** On startup the waiter **baselines on the current contents of `triggers.ndjson`** — it treats everything already in the file as "seen" and only fires on lines appended *after* it starts. So even a *successful* late restart would **skip** already-queued messages. There is no durable "last message I actually processed" marker; the baseline is implicit and resets every launch.

**Root cause, stated plainly:** the notification layer is **a single unsupervised, cwd-fragile, amnesiac process**.

---

## 2.5. Root cause — Failure C (wake-while-busy), the deepest one

**Incident.** While the agent was actively writing this very spec, a self-DM arrived and was not acted on. On checking, the waiter was **down** (`pgrep wait_dm.mjs` = none) and the new line sat unprocessed in `triggers.ndjson`.

**Framing:** "you miss stuff when you are actively working on something." This is not a fourth coincidence — it is the **mechanism that underlies A and B**:

- The waiter is **one-shot**: it fires on the first new DM and **exits**. The agent then handles the DM and relaunches the waiter — only **at the end of a handling cycle.**
- The wake is delivered by **process-exit re-invoking the agent**. That only produces a fresh action if the agent is **idle** when it lands. If the agent is **mid-turn**, the re-invocation collides with the active turn and yields no new action.
- Worst part: because the waiter already **exited** to fire that (swallowed) wake, **no waiter is now running.** So during the entire active-work window the channel is **unguarded** — any further DMs queue in `triggers.ndjson` with nothing watching, until the agent happens to relaunch the waiter at the end of its current work.

So "the waiter was down" (Failure B) and "the message arrived while I was busy" (Failure C) are the **same hole** seen from two angles: **notification relies on a wake arriving during idle, and there is no sweep of `triggers.ndjson` when work finishes.** A busy agent is a deaf agent.

**Root cause, stated plainly:** the design has **no end-of-work reconciliation**. The waiter is a latency optimization that only works when the agent is idle; nothing guarantees that a DM which arrived (or fired a wake) during active work is ever picked up. This is the primary thing to fix.

---

## 3. Summary of root causes

| | Failure A | Failure B |
|---|---|---|
| Layer | Ingestion (①) | Notification (②) |
| Reached `triggers.ndjson`? | **No** | **Yes** |
| Reached `events.ndjson` (raw)? | **No** | Yes |
| Proximate cause | message arrived during a sync reconnect gap; follow-mode doesn't backfill | waiter was down; even a restart would have skipped already-queued lines |
| Underlying cause | push-only lossy ingestion, widened by per-send lock-dance | unsupervised + cwd-fragile + forgetful waiter |

The two are **orthogonal**. A robust channel needs a fix at **each** layer, plus reduced self-inflicted gaps.

---

## 4. Design (proposed — for review before any code)

Principles: prefer **event-driven over polling**; make every restart **self-healing and memoryful**; never let a captured message fail to wake; **assume the agent is sometimes busy and sweep on the way to idle.**

### Fix D (PRIMARY) — end-of-work reconciliation against a durable marker
Targets Failure C, the deepest cause. The single highest-value fix.

- **D1. Persist a `last_processed_id` marker** (or byte offset) for `triggers.ndjson`, advanced only after the agent has actually handled a line.
- **D2. Sweep before going idle.** At the **end of every turn / unit of work**, before relaunching the waiter and going idle, compare `triggers.ndjson` against the marker and **handle anything unprocessed right then** — regardless of whether a wake fired. This makes "arrived while I was busy" *recoverable by construction*.
- **D3. Demote the waiter to a latency optimization.** With D2 in place, the waiter's only job is to *shorten* time-to-respond when the agent is idle. If it's down or its wake is swallowed, the end-of-work sweep is the backstop — no DM is lost, only briefly delayed.
- This also subsumes B3 (reconcile-on-startup) — same marker, same sweep, run on waiter startup too.

### Fix B (supporting) — supervise + bulletproof the waiter
Targets Failure B directly; cheap, event-driven, no polling.

- **B1. Supervise the waiter.** Extend `watchdog.mjs` (or a sibling) to keep `wait_dm.mjs` alive on the same ~20s tick, respecting `BRIDGE_PAUSE`. (Open question: the waiter must remain the thing whose **process-exit re-invokes the agent** — confirm a watchdog-spawned waiter still triggers the harness wake, or keep the harness-tracked waiter and have the watchdog only *detect+alert* if it's missing.)
- **B2. Cwd-independent launch.** Use `$(dirname "$0")` / `import.meta.url` throughout so the waiter and send scripts **cannot fail from the wrong cwd**. (Done in this framework version.)
- **B3. Reconcile-on-startup against a durable marker.** Replace the implicit "baseline = whole file" with a persisted `last_processed_id` (or byte offset). On startup, fire immediately on any unprocessed lines newer than the marker, then advance only after they're handled.
- **B4. PID lockfile.** Prevent two waiters racing after a supervised restart.

### Fix C-mit (SECONDARY) — shrink the self-inflicted ingestion gaps
Reduces the frequency/width of Failure-A windows.

- **C1. Send spacing / queue.** Serialize outbound sends with a minimum spacing (e.g. ≥10–15s) to avoid rate-limit warnings and back-to-back lock-dances. One queue, one drain.
- **C2. Coalesce sends** where possible so sync is torn down fewer times.

### Fix A-mitigation (the harder layer)
Ingestion loss is inherent to push-only follow mode; can't be fully eliminated without a reconciling pull. In reserve:

- **A-reserve.** A periodic *reconciling* fetch (a low-frequency `wacli` history pull, e.g. piggybacked on an existing poll wake) that asks "any self-DMs since marker X I don't have?" and feeds them into `triggers.ndjson`. The only thing that can recover a Failure-A message. Kept in reserve because it reintroduces some polling.

### Explicitly dropped
- **Standalone frequent triggers poll** — rejected as expensive.

---

## 5. Open questions (must resolve before implementing)
1. **B1 wake semantics:** can a watchdog-spawned waiter still re-invoke the agent via process-exit, or must the waiter stay harness-tracked and the watchdog only detect-and-alert?
2. **Marker granularity (B3):** message-id vs byte-offset in `triggers.ndjson`. Id is robust to file rotation; offset is simpler.
3. **A-reserve trigger:** is piggybacking on existing poll wakes enough coverage, or do we accept the residual Failure-A risk during quiet hours?

---

## 6. What this spec deliberately does NOT do
- No code changes to `watchdog.mjs`, `wait_dm.mjs`, `listener.mjs`, or the send scripts beyond what's already noted as done.
- No new daemons started.
- No change to a live loop, which keeps running on the current mechanism while this is reviewed.

---

## 7. Implemented: snapshot backstop (`selfdm_backstop.py`) — A-reserve, refined

**Status: shipped.** The A-reserve idea (§4) is implemented in `selfdm_backstop.py`, with one
refinement that removes its main drawback.

The original A-reserve worried about "reintroducing polling" — and a naive implementation
(pause follow-sync → `wacli sync` catch-up → read store → resume) is actively *harmful*: it
tears down follow-sync on every cycle, **adding exactly the offline windows** that cause
Failure-A in the first place (a self-note sent during that window may never be delivered to
the linked device, and is then unrecoverable).

The fix: **read a snapshot copy of the store instead of pulling.** Each cycle copies
`wacli.db` + `-wal` + `-shm` to a temp dir and opens it read-only via sqlite3. This:
- never touches `wacli sync --follow` (zero added offline windows — it can't worsen Failure-A),
- has zero lock contention (the live store keeps its single-writer lock),
- sees recent writes (the `-wal` is copied alongside the main db),
- appends any self-DM not already in `triggers.ndjson` / `agent_sent_ids.txt`, so the existing
  waiter delivers it through the normal path (no new wake mechanism).

Run it on a short recurring timer (~180s) next to the webhook waiter: webhook = instant primary
path, snapshot backstop = safety net that recovers anything the webhook silently dropped.

**Boundary (unchanged):** the snapshot only recovers messages that *reached the store*. A
message WhatsApp never delivered to this linked device is not in the store and is recovered by
neither path — the only mitigation there is keeping follow-sync alive (§ Fix C-mit), i.e. don't
kill it more than each post strictly requires.
