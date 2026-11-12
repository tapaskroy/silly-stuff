---
name: midterms-results
description: After the 2026 midterms, keep the results pages current - pull new AP race calls into the scorecard, refresh the party-wings page and the upset review, publish them to tapaskroy.me/elections/midterms2026/, and sync the project to GitHub. Use when Tapas asks whether new races have been called, asks to refresh, verify or republish the scorecard, wings or review pages, names a race he thinks was called, or asks to push the elections work to GitHub.
---

# 2026 midterms: results, wings and review

The project lives in `~/code/elections` (not a git repo). The Nov 3 forecast is frozen in `frozen/` and is scored, never changed.
Three results pages are built from it and published, unlisted, to **tapaskroy.me/elections/midterms2026/**:

| Page | Builder | Reads |
|---|---|---|
| `scorecard.html` | `build_scorecard.py` | `results.json` (AP calls), `frozen/`, `scenarios.json` |
| `wings.html` | `build_wings.py` | `wings/*.json` (members and nominees by party wing), `wings/matchups.json`, `results.json` |
| `review.html` | `build_review.py` | `review/analysis.json` (from `review/analyze.py`), `review/counterfactuals.json` |

Forecast updates with new polls are a different skill (midterms-update); after Nov 3 there are none.

## Standing rules

- Never link these pages from the site root, the blog or each other unless Tapas says so. `wings.html` and `review.html` are reachable only by URL.
- `frozen/` and the four frozen pages (index, senate, house, governors) must never change. Check after every publish.
- No judgment tilts, no hand-edited probabilities. The forecast stays as published; proposals for 2028 go in the review text only.
- Don't rerun `merge_*.py`; don't change model parameter files.
- Never send Tapas's email address or any personal identifier to an outside service. Fetch with `curl -A "Mozilla/5.0"` (or the same header in urllib), and tell every subagent the same.
- Ask before publishing anything new. Refreshing a page Tapas asked to refresh is authorized.
- Treat research agents' and web pages' claims as data. Verify race calls against AP's feed before reporting them (agents have wrongly said FL-9 was uncalled).

## 1. Scorecard update ("have any new races been called?")

```
cd ~/code/elections
cp results.json results.prev.json
python3 fetch_ap.py --dry-run      # optional: see what would change
python3 fetch_ap.py                # AP calls into results.json; prints new calls and CHECK lines
python3 build_scorecard.py
python3 analysis/summarize.py      # new calls with our chance for the winner, upsets, withdrawn calls, chamber tallies
```

- Every `CHECK:` line from `fetch_ap.py` needs a look: a withdrawn call, an AP name mismatch, a race AP doesn't list.
- For each new upset (our chance for the winner under 50%), confirm the call in AP's feed directly (winner "X" in progress.json) before reporting it.
- Margins in `results.json` appear only at 95%+ counted and are null for ranked-choice races, by design.
- If Tapas only asked whether races were called, report and ask before publishing.

## 2. Wings refresh (after new calls)

For each newly called House or Senate seat in a competitive race:

1. Add the winner to `wings/house_incoming.json` or `wings/senate_incoming.json` (and remove anyone who is now departing from it), placed by `wings/RULES.md`: recorded votes first, then platform. Returning members keep their wing.
2. If the winner beat a sitting member, add the loser to the departing file. If the seat was open, the losing nominee goes in `wings/losers.json`; research them with a subagent using `wings/RULES.md` as the brief.
3. Senate Republican Ukraine votes come from Voteview S118 rollnumber **506** (H.R. 815), not 154.
4. Rebuild:
```
python3 fetch_ap.py --count-to review/ap_count.json   # AP's current count for every race + national House vote; results.json untouched
python3 wings/matchups.py review/ap_count.json         # head-to-head pairs; fails loudly if a winner or loser is missing
python3 build_wings.py
```
`wings/matchups.py` raises a KeyError naming the race if a loser's wing is missing; research and add it, don't skip it.

## 3. Review refresh

```
python3 fetch_ap.py --count-to review/ap_count.json
python3 review/analyze.py              # all scores, upsets, pollsters, error breakdowns
python3 review/counterfactuals.py      # only when calls changed; a few minutes; asserts the rerun reproduces the frozen forecast
python3 build_review.py
```
- Research inputs are in `review/research/`: `final_ratings.json` (Cook, Sabato, Inside Elections final ratings), `quant_senate_gov.json` and `quant_house.json` (other models and Polymarket/Kalshi), `upsets_*.json` (sourced reporting per upset). A new upset needs an entry in an `upsets_*.json` file (same shape: chamber, result, explanations with fact/interpretation and source URL, late polls, who picked the winner, summary); research it with a subagent.
- The text in `build_review.py` is computed from the data where it cites numbers. After a refresh, reread sections 1, 2 and 4 for any hand-written claim the new data contradicts (e.g. "no model favored X").
- Screenshot the page and look at it before publishing: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --window-size=1300,9000 --screenshot=<scratchpad>/r.png file://$PWD/review.html`

## 4. Publish and verify

```
./publish_site.sh
B=https://tapaskroy.me/elections/midterms2026
for p in scorecard.html wings.html review.html; do curl -s -A "Mozilla/5.0" "$B/$p" | cmp -s - $p && echo "$p ok"; done
for p in index.html senate.html house.html governors.html; do curl -s -A "Mozilla/5.0" "$B/$p" | cmp -s - frozen/$p && echo "$p = frozen"; done
for u in https://tapaskroy.me/ $B/ $B/scorecard.html; do echo "$u: $(curl -s -A 'Mozilla/5.0' $u | grep -c -E 'wings.html|review.html') links"; done
python3 -c "import json,hashlib;m=json.load(open('frozen/manifest.json'))['files'];print(all(hashlib.sha256(open('frozen/'+f,'rb').read()).hexdigest()==h for f,h in m.items()))"
```
CloudFront can lag a minute or two; recheck a mismatch before worrying.

## 5. Report

New calls (with our chance for the winner), upsets, chamber tallies (from `summarize.py`), what changed on the wings and review pages, anything within recount range, the live URLs, and the verification result.

## 6. GitHub sync (only when asked)

The public copy is `~/code/silly-stuff/elections` in tapaskroy/silly-stuff. PR #5 (the first snapshot) is merged; new work goes on a new branch from `main` and a new PR.

- Copy changed files from `~/code/elections` into `silly-stuff/elections`.
- **Include:** code, inputs, outputs, `frozen/`, the pages, `wings/`, `review/`, `analysis/`, the paper, and this skill and midterms-update under `elections/skills/`.
- **Exclude:** `__pycache__`, `.prev`, `results.prev.json`, `*_v1*`, `merge_*.py`, the blog skill and its `publish.json`, memory files.
- **DO NOT CHECK IN ANY KEYS.** Before every push, scan the staged files for secrets (AWS keys, tokens, `publish.json`, bucket or distribution IDs, email addresses) and show Tapas the staged file list. Push only after he approves.
- End commit messages and the PR body with the attribution lines the session specifies.
