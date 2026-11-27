#!/usr/bin/env python3
"""Scan a draft for AI writing tics before it is sent.

Usage:  python3 voice_check.py draft.txt
        cat draft.txt | python3 voice_check.py

Exit 0 = clean enough to send. Exit 1 = rewrite something first.

WHY THIS IS MECHANICAL AND NOT ADVISORY
---------------------------------------
An agent asked to "watch its tone" will agree, and will then produce the same
construction in the next message. A promise is not a mechanism. This is a gate
with an exit code, run against the draft file before the send call.

WHY YOU SHOULD DERIVE YOUR OWN RULES
------------------------------------
The HARD list below is a starting point, not a verdict. Build your real list by
counting constructions in your own agent's sent output, because the tic that
irritates readers enough to complain is rarely the most frequent one. Readers
report what grates; a counter finds what repeats. Those are different sets, and
the second is usually larger by orders of magnitude.

Promote a pattern to HARD when it is either (a) something a reader actually
objected to, or (b) something you ban in your own writing tooling. Keep the
reason inline so the rule can be argued with later.

TUNING WITHOUT DEGRADING THE PROSE
----------------------------------
A false positive is a real cost. When the gate fires on a sentence that is
correct, fix the regex rather than rewording the sentence. A checker that
quietly launders good prose into worse prose is worse than no checker, and the
failure is invisible because the output still passes.
"""
import re, sys

# (label, regex, limit, note). limit=0 means "must not appear at all".
HARD = [
    ("em-dash in prose", r"—", 0,
     "The single strongest tell in machine-written prose. Use a comma pair, a colon, "
     "or two sentences. Exempt a signature line if your agent signs its posts."),
    ("en-dash as punctuation", r"(?<=[a-z]) – (?=[a-z])", 0,
     "Same problem. An en-dash is correct ONLY for numeric ranges (1989-1991)."),
    ("importance signposting", r"\b(now|here'?s|and here'?s) the (part|thing|real|crux|whole|point)\b", 0,
     "Announcing that the next sentence matters. If a point is the important one, "
     "make it; the announcement is filler that also flattens everything around it."),
    ("'and it's/that's the whole'", r"\band (it'?s|that'?s) the (whole|entire|real|actual)\b", 0,
     "The second half of the same tic."),
    ("'not just X but Y'", r"\bnot (just|merely|simply|only)\b[^.?!]{0,70}\b(but|it'?s|they'?re)\b", 0,
     "Stock cadence. State the claim once."),
    ("'isn't X. It's Y.'", r"\b(isn'?t|wasn'?t) [^.?!,;:]{0,40}\.\s*(It'?s|That'?s)\b", 0,
     "Substitution across a period. The comma exclusion matters: without it this "
     "also matches an ordinary negation followed by an unrelated clause, which is "
     "a false positive that will tempt you to reword a correct sentence."),
]

SOFT = [
    ("throat-clearing", r"\b(It'?s worth noting|It is important to note|That said,|In conclusion|Ultimately,|Moreover,|Furthermore,|Conversely,)", 0,
     "Cut it, or start the sentence with its actual content."),
    ("buzzword", r"\b(delve|tapestry|testament|realm|landscape|underscore|boast|foster|leverage|navigate|nuanced)\b", 0,
     "Replace with the plain word you meant."),
    ("italic emphasis", r"(?<!\*)\*[^*\n]{2,40}\*(?!\*)", 4,
     "Emphasis stops working when everything has it."),
    ("bold emphasis", r"\*\*[^*\n]{2,60}\*\*", 6,
     "Bold a number or a claim, not a mood."),
    ("colon then claim", r":\s+[a-z]", 3,
     "Colon-introducing a verdict. Fine once, a tic by the fourth."),
    ("'the real X'", r"\bthe real (story|point|question|constraint|issue|answer|problem)\b", 1,
     "Implies everyone else found the fake one."),
    ("'which is exactly/precisely'", r"\bwhich is (exactly|precisely)\b", 1,
     "Self-congratulating connective."),
    ("'genuinely/actually' filler", r"\b(genuinely|actually)\b", 2,
     "Usually deletable without loss of meaning."),
    ("rule-of-three list", r"\b\w+, \w+,? and \w+\b", 3,
     "Tidy triples read as generated."),
]


def scan(text):
    problems, warnings = [], []
    for label, pat, limit, note in HARD:
        hits = list(re.finditer(pat, text, re.I))
        if len(hits) > limit:
            problems.append((label, hits, limit, note))
    for label, pat, limit, note in SOFT:
        hits = list(re.finditer(pat, text, re.I))
        if len(hits) > limit:
            warnings.append((label, hits, limit, note))
    return problems, warnings


def show(kind, items, text):
    for label, hits, limit, note in items:
        cap = "must not appear" if limit == 0 else f"limit {limit}"
        print(f"\n  [{kind}] {label}: {len(hits)} ({cap})")
        print(f"        {note}")
        for m in hits[:4]:
            a, b = max(0, m.start() - 38), min(len(text), m.end() + 38)
            print(f"        ...{text[a:b]!s}...".replace("\n", " "))
        if len(hits) > 4:
            print(f"        (+{len(hits) - 4} more)")


def main():
    text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else sys.stdin.read()
    problems, warnings = scan(text)
    print(f"voice_check: {len(text.split())} words")
    if problems:
        show("FIX", problems, text)
    if warnings:
        show("look", warnings, text)
    if not problems and not warnings:
        print("  clean")
    print()
    if problems:
        print(f"VERDICT: rewrite before sending ({len(problems)} hard tic(s)).")
        return 1
    if warnings:
        print(f"VERDICT: sendable, but {len(warnings)} soft tic(s) worth a second look.")
        return 0
    print("VERDICT: send it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
