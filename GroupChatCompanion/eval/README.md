# Offline decision harness

The loop's hardest output is the one it does not produce. A reply can be judged by reading
it; a silence can only be judged against what the message deserved. This harness makes
silences reviewable.

## Shape

Each case is one message envelope plus a labelled expectation:

```json
{
  "case_id": "env-001",
  "channel": "tag-only",
  "text": "@<AGENT_ID> what do you make of this?",
  "mentions_agent": true,
  "reply_to_agent": false,
  "has_media": false,
  "gold_addressed": true,
  "gold_should_speak": true,
  "note": "explicit mention carrying a question"
}
```

Run the loop's decision function over the cases and compare against `gold_*`. Two numbers
matter and they are not symmetric:

- **Missed address** — `gold_addressed` true, decided false. Someone asked and got
  nothing. Expensive and visible.
- **Unprompted speech** — `gold_should_speak` false, decided true. Cheap individually,
  corrosive in aggregate, and the thing participants actually complain about.

Track them separately. A single accuracy number hides the trade.

## Strata worth separating

- explicit mention
- quoted reply with no mention
- plain-text nickname or literal `@name`
- bare follow-up continuing an exchange the agent is in
- another participant's id in the text, not the agent's
- media with no caption
- a question aimed at the room rather than the agent
- a punchline aimed at the agent that needs no answer

The last two carry most of the interesting errors.

## Fixtures

`fixtures/envelopes.jsonl` holds synthetic cases covering each stratum. They are invented,
not captured. **Build your own set from your own traffic, and keep it out of the
repository** — a corpus of real messages is other people's conversation regardless of how
useful it is for testing.
