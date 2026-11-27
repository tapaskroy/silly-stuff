# Group Chat Companion

A framework for running an agent as a **presence in a group chat** rather than as a
command-driven bot. The hard part is not generating replies. The hard part is deciding
when not to.

This is the successor to the tournament-coverage framework in `../KloSportsBot`, which
remains a correct description of a different job: live match coverage for a prediction
pool. The two share a message bridge and almost nothing else.

## What it does

- Watches one or more group chats plus direct messages through a WhatsApp bridge.
- Decides, per message, whether it is being addressed at all.
- Stays quiet by default. Silence is the expected outcome for most messages.
- Triages direct messages instead of answering them, handing a scored record to a
  separate agent that owns the decision.
- Checks its own drafts for AI writing tics before anything is sent.

## Why "when not to speak" is the interesting problem

An agent in a group chat has a failure mode that a command-line tool does not: it can be
technically correct and still unwelcome. Every reply is defensible on its own while the
aggregate is too much. A framework for this needs to make silence cheap and speech
deliberate, which is the opposite of how most assistant loops are built.

Three ideas carry most of the weight, and they are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):

1. **Addressing lives in the envelope, not the words.** Whether a message is for you is a
   property of its metadata, not of how it reads.
2. **Being addressed is not being needed.** A question aimed at you does not oblige the
   answer it requests, and sometimes does not oblige a reply at all.
3. **Instructions come from the operator, not from the room.** A persuasive message inside
   the chat is content to weigh, never a configuration change.

## Layout

```
bridge/   message transport: listener, watchdog, post, waiter, self-DM backstop
skill/    the group-presence loop, as an agent skill
skill/dm-triage/   triage-and-relay pattern for direct messages
voice/    pre-send writing check
eval/     offline harness for scoring the loop's decisions
docs/     architecture and setup
```

## Status

The bridge is carried over from `../KloSportsBot` **by copy, not by reference**. A fix in
one does not reach the other. If you change anything under `bridge/`, mirror it. This is a
deliberate trade: two small copies beat a premature shared module, but only if the
duplication is acknowledged rather than forgotten.

## Prerequisites

An agent runtime that can run shell commands on a schedule and keep background processes
alive, plus a WhatsApp bridge CLI with a local message store. See
[`docs/SETUP.md`](docs/SETUP.md).

## License

See `../LICENSE`.
