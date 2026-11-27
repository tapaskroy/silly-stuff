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

## Known limits

The rules were derived by counting tics in a corpus of **chat messages**, and the
thresholds do not transfer cleanly to other registers. Two over-firings are known and
neither is worth rewriting good text to satisfy:

- **Markdown structure.** Em-dashes in a heading (`## Step 1 — identify the sender`), in a
  table cell, or as a bullet label are separators, not sentence-interruption punctuation.
  The checker counts them all the same.
- **Fenced code blocks.** An em-dash inside ``` is flagged exactly like one in prose, so a
  shell sample or a quoted template can fail a file that reads perfectly.

Both are false positives in a documentation repository, and the fix is a parser that strips
fences and structural markup before counting. Until then, read the `[FIX]` lines rather
than obeying the exit code: a checker that launders good prose into worse prose is worse
than no checker. The soft counts (bold, colons) are tuned for short posts and will fire on
any technical document; they are advisory by design.
