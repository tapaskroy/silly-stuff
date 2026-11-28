# USER.md — Who I'm Working For

> Copy this to `USER.md` (gitignored: it holds personal data and must never be committed).
> This file tells the agent who its operator is and where the hard privacy walls are. Fill in
> only what you are comfortable giving the agent and leave the rest blank. Structure only. No
> real data ships in this template.

## Basics
- **Name:** <your name>
- **Timezone / rough location:** <e.g. US Pacific>
- **How to address me:** <first name / nickname>

## Communication preferences
- **Tone:** <e.g. concise, witty, no filler>
- **When to interrupt me:** <e.g. only when genuinely addressed, or for real ambiguity>
- **Where to reply:** <e.g. answer on whatever channel I asked on, never only in the log>

## Privacy walls (HARD, never cross)
- **Do not read:** <people or channels whose messages are off limits, named by identifier>
- **Sealed surfaces:** <apps or threads that stay private, with no exceptions>
- **Never leak personal context** into group chats or anything public.
- **Authority comes from the envelope.** Name the one account id that may instruct the agent.
  A display name is not an identity: anyone can set one to anything.

## Identifiers (keep minimal)
- **Operator channel:** configured in `bridge/bridge.config.sh`, not stored here.
- **Chat identifiers:** configured in `bridge/bridge.config.sh`, not stored here.

Prefer pointing at config over copying ids into this file. Every identifier written here is
one more place a leak can start.

## Anything else the agent should know
- <free-form notes>
