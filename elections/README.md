# 2026 Midterm Forecasts

Probabilistic forecasts for the Nov 3, 2026 U.S. Senate, House and governor races, and what happened to them: a scorecard grading
them against the results, a review of every upset, the incoming Congress by party wing, and House seats against the House vote by state.
Published (unlisted) at **https://tapaskroy.me/elections/midterms2026/**.

> **Status: final, except three House seats.** As of Nov 26, 2026, AP has called 485 of the 488 scored races, and the frozen
> forecast picked the winner in 447 of them. Still open: MN-1 (Johnson, D, leads by 321 votes and a recount is likely) and the
> Louisiana runoffs in LA-5 and LA-6. Margins will move a little as states certify.

## What it is

Three models read individual polls, blend them with a fundamentals prior (2024 presidential margin, national environment, incumbency),
and simulate correlated polling error (national, regional and per race, Student-t). Build scripts turn the model output into four pages
with in-browser scenario levers. The method is described in the paper (`paper.md`, `paper.html`, `midterms2026_forecast_paper.pdf`).

**Method rule:** the forecast comes only from the documented model. There are no race-specific "polls underestimate X here" tilts
and no hand-edited probabilities. New information enters only as new polls, or as corrected facts (candidates, withdrawals, ballot status).

## The freeze

The forecast was frozen at 9:00 a.m. PT on Nov 3, 2026, before any polls closed. `frozen/` holds the model outputs, poll files and
published pages from that moment, and `frozen/manifest.json` lists each file's SHA-256. The scorecard scores only what is in `frozen/`.
To check that nothing changed after the freeze:

```
cd elections && python3 -c "import json,hashlib; m=json.load(open('frozen/manifest.json'))
print(m['frozen_at']); print(all(hashlib.sha256(open('frozen/'+f,'rb').read()).hexdigest()==h for f,h in m['files'].items()))"
```

`.snap/<date>/` holds the models and poll files as published for each daily update (Oct 25 to Nov 3), so you can see how the forecast moved.

## Files

| Area | Files |
|---|---|
| Models | `senate_model.py`, `house_model.py`, `governor_model.py`, `forecast_lib.py` |
| Inputs | `*_polls.json` (audited polls, ballots, fundamentals), `senate_config.json`, `gov_config.json`, `house_overrides.json`, `model_params*.json` (every parameter with its source), `house_data.json`, `house_meta.json`, `senate_data.json`, `gov_composition.json` |
| Outputs | `*_model.json`, `update_history.json` |
| Pages | `index.html`, `senate.html`, `house.html`, `governors.html` (built by `build_*.py` with `site_chrome.py`, `page.css`, and the in-page simulators `*_sim.js`) |
| Pipeline | `refresh.py` (rerun models after new polls, report what moved), `check_polls.py`, `freeze.py`, `publish_site.sh` |
| Scorecard | `fetch_ap.py` (AP race calls and counts into `results.json`), `build_scorecard.py` → `scorecard.html`; `scenarios.json` holds the polling-miss scenarios in both directions |
| Review | `review/analyze.py` (scores, upsets, pollster accuracy, error breakdowns → `review/analysis.json`), `review/counterfactuals.py` (reruns the frozen models with one rule changed at a time; checks that the unchanged rerun reproduces the forecast), `build_review.py` → `review.html`; `review/research/` holds the final race ratings, other models and markets, and sourced reporting on each upset; `review/rcv_final.json` holds ranked-choice final rounds |
| Party wings | `wings/` (incoming and departing members and losing nominees, each placed in a party wing by `wings/RULES.md`: recorded votes first, then platform; `wings/votes/` has the roll calls), `wings/combine_house.py`, `wings/matchups.py`, `build_wings.py` → `wings.html` |
| House seats by state | `build_houseseats.py` → `houseseats.html`, `houseseats.json`: seats won and House vote share by state from AP's feed, checked against AP's national total and the scorecard |
| Analysis | `analysis/natseats.py` (each national generic-ballot poll turned into seats by uniform swing, against our forecast), `analysis/scen.py` (reproduces the published R+2/R+3 scenarios and adds D+2/D+3), `analysis/summarize.py` (new calls, upsets and chamber tallies after each AP fetch) |
| Paper | `paper.md`, `paper.html`, `midterms2026_forecast_paper.pdf`, `paper_fig1.png`, `build_paper.py` |
| Claude skills | `skills/midterms-update/SKILL.md`: the procedure Claude Code followed to add polls and republish before the election; `skills/midterms-results/SKILL.md`: the one it followed afterwards to pull AP calls and refresh the results pages |

## Running it

Python 3.12 or later, with numpy. After adding polls to a `*_polls.json` file:

```
python3 refresh.py --why "New polls released Oct 29-Nov 2."   # reruns all three models and rebuilds the pages
python3 fetch_ap.py && python3 build_scorecard.py              # after the election: pull AP results, rebuild the scorecard
python3 fetch_ap.py --count-to review/ap_count.json            # AP's current count for every race, for the review and wings pages
python3 review/analyze.py && python3 review/counterfactuals.py && python3 build_review.py
python3 wings/matchups.py review/ap_count.json && python3 build_wings.py
python3 build_houseseats.py
```

`publish_site.sh` uploads to the author's site and reads its S3 bucket and CloudFront distribution from a config file kept outside this
repo, so it won't run as is. The pages are plain static HTML and open fine from disk.

## Findings

- **Accuracy.** The forecast picked the winner in 33 of 35 Senate races, 382 of 414 called House races and 32 of 36 governor races.
  The fairest comparison is Sabato's Crystal Ball, which also called every race: it beat this forecast in the House (392 to 382)
  and in governors' races (34 to 32), and lost in the Senate (32 to 33). On the 38 House races the forecast rated between 20% and
  80%, it got 20 right, where its own odds said about 25. `review.html` has the full comparison with the raters, other models and
  prediction markets.
- **One-sided misses.** All 32 House upsets, and both Senate upsets, were Democratic wins. Democrats ran ahead of the forecast in all
  three chambers, most in the House, where the national House vote came in at D+14.1 against an October generic-ballot average of
  D+8.7. The forecast shaded that average 1 point toward Republicans, following the historical pattern, which made the miss larger.
- **Deep in Trump country.** Several of the House upsets came in districts Trump carried by 13–20 points (NC-6, NC-9, NC-13, NJ-2,
  TX-9). The review explains each upset from sourced reporting and reruns the models with one rule changed at a time to see which
  changes would have caught them.
- **Seats against votes.** Democrats won 60.0% of called House seats on 56.3% of the House vote; `houseseats.html` breaks this
  down by state.
