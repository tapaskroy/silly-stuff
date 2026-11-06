---
name: midterms-update
description: Update the 2026 midterm forecasts (Senate, House, Governors) with new polls and republish them to tapaskroy.me/elections/midterms2026/. Use when Tapas says new polls are out, asks to refresh, update or rerun the midterm/election forecasts or sheets, or names a new poll to add.
---

# Update the 2026 midterm forecasts

The project lives in `~/code/elections`. Three probabilistic models (Senate, House, Governors) read individual polls,
blend them with a fundamentals prior, and simulate correlated polling error. Build scripts turn the model output into
four pages, which `publish_site.sh` uploads to **tapaskroy.me/elections/midterms2026/**. That URL is unlisted on purpose:
never link it from the site's root page or the blog.

**Method rule:** the forecast comes only from the documented model. Never add race-specific "polls underestimate X here"
tilts or other judgment adjustments, and never hand-edit a race's probability. New information enters only as new
polls, or as corrected facts such as candidates, withdrawals or ballot status.

## 1. Find what's new

Each poll file records the latest fieldwork end date it holds:

```
cd ~/code/elections
python3 -c "import json
for f in ['senate_polls.json','house_polls.json','gov_polls.json']:
  d=json.load(open(f)); print(f, max((p.get('end') or '') for x in d.values() for p in (x.get('polls') or [])))"
```

Search for general-election polls that ended after that date. Search the competitive races first (`tier` not "Safe" in
the `*_model.json` files), then anything else. Good sources:
- Wikipedia race pages (`2026_<State>_Senate_election`, `..._gubernatorial_election`, `2026_United_States_House_of_Representatives_elections_in_<State>`; the `?action=raw` wikitext is easiest to parse)
- 270toWin
- pollster releases

If the user named specific polls, add those. For a broad sweep, run one subagent per chamber in parallel and give each
the rules below.

## 2. Add each poll

Append to the race's `polls` list in the right file:

| Chamber | File | Race key |
|---|---|---|
| Senate | `senate_polls.json` | state name, e.g. `"Maine"` |
| House | `house_polls.json` | district, e.g. `"PA-7"` |
| Governor | `gov_polls.json` | state name |

For a House district not yet in the file, add `{"PA-7": {"polls": [...]}}`; the model falls back to its baseline record for everything else.

One entry per poll:
```json
{"pollster": "Marist", "sponsor": null, "partisan": null, "lean": null,
 "start": "2026-10-24", "end": "2026-10-27", "n": 1100, "pop": "LV",
 "results": {"Jackson": 48, "Collins": 46}, "undecided": 6,
 "source_url": "https://...", "verified": true}
```

Rules (these are what the weighting assumes):
- Count each poll once. Never record an aggregator average (RCP, 538, Silver Bulletin, DDHQ averages). A poll is a duplicate if it has the same pollster and the same end date.
- If a pollster published both likely-voter and registered-voter numbers, use the LV version. Record the matchup that matches the actual ballot.
- **`partisan`:** "D" or "R" when a campaign, party or allied group paid for or commissioned the poll; otherwise null.
- **`lean`:** "D" or "R" for one-party pollsters released without a sponsor: Cygnal, Quantus, Trafalgar, co/efficient, InsiderAdvantage, Rasmussen, Data for Progress, PPP and similar. Nonpartisan shops like Emerson, Marist or Siena get null.
- **`verified`:** true only if you saw the numbers in the original release or in a reputable outlet's report of that poll. Numbers seen only in a Wikipedia or 270toWin table are false; they are weighted lower but still used.
- **Results keys must be surnames that match the model's candidate names.** Otherwise the poll is silently skipped.
  - Senate: `challenger` and `rep` in `senate_config.json`.
  - Governor: `challenger` and `rep` in `gov_config.json`.
  - House: the surnames of `dem` and `rep` in `house_model.json`. Compound surnames such as "De La Cruz" are fine.
  - Include minor candidates too; Alaska's ranked-choice transfers use them.
- A pollster's older releases are discounted automatically, so add the new release and keep the old one.

**Don't do these:**
- Don't rerun `merge_senate_polls.py`, `merge_house_polls.py`, `merge_house.py` or `merge_gov.py`. They rebuild the poll files from a past session's research folder, which no longer exists, and would wipe the polls.
- Don't change the model parameter files except `as_of`. The refresh script sets that.

**If a fact changed** (a withdrawal, a replacement nominee, a death, a candidate leaving or joining the ballot), tell the
user before changing anything. Then update the race's `ballot` in the poll file, and the config: `senate_config.json`
or `gov_config.json`, or `house_overrides.json` for the House.

## 3. Refresh and check

```
python3 refresh.py --why "New polls released Oct 28–30."    # as-of = today; or add --as-of YYYY-MM-DD
```

`--why` is required: it is the one-line reason shown in the update history on all four pages. Say why the update
happened (new polls and their date range; a fact change such as a withdrawal; a fix), not what moved.

The script:
- sets `as_of` in all three parameter files and reruns the three models;
- compares against the latest snapshot in `.snap/` dated before the as-of date, and prints the headline change for each
  chamber plus every race whose win chance moved 5+ points, that got new polls, or whose leader changed;
- writes that day's entry in `update_history.json` (the reason plus the generated list of changes per page; a same-day
  rerun replaces it);
- rebuilds the four pages, each with an "Update history" section above the footer;
- saves the models and poll files to `.snap/<as-of>/`;
- runs `check_polls.py`.

For a change that isn't a poll refresh (wording, layout), add or edit an entry in `update_history.json` by hand:
`{"date": "YYYY-MM-DD", "why": "...", "pages": {"index.html": [...], "senate.html": [...]}}`. A page shows only
entries that list it.

`check_polls.py` must report **0 in-window polls not used**. If it lists any, the poll's results keys don't match the
model's names: fix the keys and rerun.

Before publishing, sanity-check the report. A big jump in a race should trace back to the polls you just added.
The project isn't a git repo; each update's models and poll files are saved in `.snap/<as-of>/` for comparison.

## 4. Publish (ask first)

Show the user the change report and ask before publishing, because publishing puts it on the live site. Then:

```
./publish_site.sh
```

The script:
- copies the four pages into the site repo (`~/code/watchagent/terraform-simple/landing-page/elections/midterms2026/`), so the blog skill's full `aws s3 sync --delete` keeps them;
- syncs only that folder to S3;
- invalidates `/elections/midterms2026/*` on CloudFront.

It reads the bucket and distribution from `~/.claude/skills/blog-tapaskroy/publish.json`.

Verify the live pages:
```
for p in "" senate.html house.html governors.html; do curl -s -o /dev/null -w "%{http_code} $p\n" "https://tapaskroy.me/elections/midterms2026/$p"; done
```

The CloudFront refresh can take a minute or two. Pages are cached for 5 minutes.

## 5. Report back

Tell the user:
- how many polls were added, per chamber;
- the headline changes (Senate control, House control, Governors 26+), old → new;
- races whose leader changed or whose chance moved a lot, and which polls moved them;
- anything skipped or unverified, and any fact changes;
- the live URL.

## Files

| File | Role |
|---|---|
| `*_polls.json` | Audited polls plus ballot, fundamentals and fact-check claims per race. Edit these. |
| `senate_config.json`, `gov_config.json`, `house_overrides.json` | Candidate mapping, region, caucus/RCV settings. |
| `model_params*.json` | Weights and error parameters with sources. Only `as_of` changes on an update. |
| `senate_model.py`, `house_model.py`, `governor_model.py` | The models. They write `*_model.json`. |
| `build_*.py` | Page builders. |
| `senate_sim.js`, `house_sim.js`, `gov_sim.js` | The in-page scenario levers (inlined at build time). |
| `site_chrome.py` | Nav, the noindex tag, and the update-history section. |
| `update_history.json` | What changed on each update and why; shown on every page. |
| `refresh.py`, `check_polls.py`, `publish_site.sh` | The update pipeline. |
