# Silly Stuff

A junk drawer of personal experiments and hobby projects — small, self-contained, and mostly built for fun.

**Main project: [`KloSportsBot/`](KloSportsBot/)** — a persona-neutral framework for an AI WhatsApp sports-companion bot that runs a prediction pool (live commentary, kickoff/full-time cards, automated picks). Start there.

**[`GroupChatCompanion/`](GroupChatCompanion/)** — a framework for running an agent as a presence in a group chat rather than as a command-driven bot. The interesting problem there is deciding when *not* to speak: recognising when you are actually being addressed, triaging direct messages instead of answering them, and checking your own drafts before sending. Shares a message bridge with `KloSportsBot/` and little else.

**[`elections/`](elections/)** — probabilistic forecasts for the 2026 U.S. midterms (Senate, House and governors), and an accounting of how they did. Three models read individual polls, blend them with a fundamentals prior and simulate correlated polling error. The forecast was frozen before the polls closed on Nov 3, with SHA-256 hashes so anyone can check it wasn't changed afterwards. After the election, a scorecard grades it against AP's race calls, a review digs into each upset and reruns the models with one rule changed at a time, and two more pages sort the incoming Congress by party wing and compare House seats with the House vote, state by state. The method is written up in a paper in the same folder.
