# Pre-send writing check

`voice_check.py` scans a drafted message for AI writing tics and exits non-zero if it
finds a hard one. Wire it into the loop between drafting and sending:

```sh
python3 voice/voice_check.py draft.txt || { echo "rewrite"; exit 1; }
./bridge/post.sh text "<CHANNEL>" "$(cat draft.txt)"
```

Skip it for one-line replies, where the tic surface is nil.

## Deriving your own rules

The shipped list is a starting point. Build the real one by counting constructions in your
agent's own sent output.

Expect the result to be lopsided. The construction a reader complains about is rarely the
one that repeats most; people report what grates, while a counter finds what recurs. A
first pass over a few dozen sent messages will typically surface one dominant pattern
appearing hundreds of times that nobody has ever mentioned, alongside the handful somebody
did. Both belong in the list, for different reasons.

## Hard versus soft

**Hard** rules fail the draft. Promote a pattern to hard when it is either something a
reader actually objected to, or something already banned in your own writing tooling.

**Soft** rules print a warning and pass. They exist for constructions that are fine once
and tiresome by the fourth, where a count is the right test and a ban is not.

## The failure mode to design against

A false positive costs more than it looks. When the gate fires on a sentence that is
correct, the tempting fix is to reword the sentence, because that is faster than editing a
regex. Do that a few times and the checker is quietly degrading the prose it was built to
protect, invisibly, because the output passes.

**Fix the rule, keep the sentence.** Then re-run against a known-positive example to
confirm the rule still catches the real pattern.
