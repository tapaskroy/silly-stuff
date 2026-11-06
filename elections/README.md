# 2026 Midterm Forecasts

Probabilistic forecasts for the Nov 3, 2026 U.S. Senate, House and governor races, plus a scorecard grading them against the results.
Published (unlisted) at **https://tapaskroy.me/elections/midterms2026/**.

> **Status: results are still coming in.** This snapshot was checked in on Nov 5, 2026, with 459 of 488 scored races called by AP
> (Alaska's ranked-choice count, California and a few close House seats are still open). The scorecard, `results.json` and the
> analysis here will be updated as the remaining races are called, again when state election offices report final margins, and once
> more with a full retrospective.

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
| Analysis | `analysis/natseats.py` (each national generic-ballot poll turned into seats by uniform swing, against our forecast), `analysis/scen.py` (reproduces the published R+2/R+3 scenarios and adds D+2/D+3) |
| Paper | `paper.md`, `paper.html`, `midterms2026_forecast_paper.pdf`, `paper_fig1.png`, `build_paper.py` |
| Claude skill | `skills/midterms-update/SKILL.md`: the procedure Claude Code followed to add polls and republish |

## Running it

Python 3 with numpy. After adding polls to a `*_polls.json` file:

```
python3 refresh.py --why "New polls released Oct 29-Nov 2."   # reruns all three models and rebuilds the pages
python3 fetch_ap.py && python3 build_scorecard.py              # after the election: pull AP results, rebuild the scorecard
```

`publish_site.sh` uploads to the author's site and reads its S3 bucket and CloudFront distribution from a config file kept outside this
repo, so it won't run as is. The pages are plain static HTML and open fine from disk.

## Early findings (provisional)

- Democrats ran ahead of the forecast in all three chambers, most in the House, where the national House vote is about D+11 against an
  October generic-ballot average of D+8.7. The forecast shaded that average 1 point toward Republicans, following the historical
  pattern, which made the miss larger.
- The Senate forecast called 32 of 33 decided races right and the governor forecast 31 of 34; most of the misses are House seats where
  Democrats won districts the model had leaning Republican, including several Trump carried by 13–20 points (NC-6, NC-9, NC-13, NJ-2, TX-9).
- See `scorecard.html` for the current race-by-race grading. A full retrospective will follow once every race is final.
