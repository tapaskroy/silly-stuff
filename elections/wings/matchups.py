#!/usr/bin/env python3
"""Pair up the two nominees in every competitive House and Senate race by wing, for the head-to-head section of wings.html.

Competitive: the frozen forecast didn't rate the race Safe (or Certain): Likely, Lean, Tilt or Toss-up. Only races AP has called.
Winners' wings come from house_incoming.json / senate_incoming.json. Losing incumbents' wings come from the departing files;
every other losing nominee was researched the same way and is in losers.json (research/losers_*.json).
Margins are AP's current count (D or independent minus R), passed in as a results.json-shaped file because the scorecard's
results.json only stores a margin once 95% of the expected vote is in.
Usage: python3 fetch_ap.py --count-to review/ap_count.json && python3 wings/matchups.py review/ap_count.json   (writes wings/matchups.json)
"""
import json
import re
import sys
from pathlib import Path

W = Path(__file__).parent
HERE = W.parent
load = lambda p: json.loads(Path(p).read_text())
side = lambda p: "D" if p in ("D", "I") else "R"
sur = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\s*\(.*?\)|,? (Jr|Sr|II|III)\.?$", "", n).split()[-1].lower())

now = load(sys.argv[1])
called = load(HERE / "results.json")
losers = {(x["chamber"], x["district"]): x for x in load(W / "losers.json")}
rows = []


def add(chamber, key, tier, mean, p_d, pres, x, d_name, r_name, d_inc, r_inc, winner, loser, now_x):
    margin = now_x["margin"]
    if margin is None:
        sys.exit(f"{chamber} {key}: no current margin in {sys.argv[1]}; refresh it with fetch_ap.py --count-to after the latest calls")
    rows.append({"chamber": chamber, "district": key, "tier": tier, "forecast_margin": round(mean, 1), "p_d": round(p_d, 3),
                 "pres_2024": pres, "margin": margin, "counted": int(float(now_x["note"])),  # percent of expected vote in (fetch_ap.py --count-to)
                 "d": d_name, "d_wing": (winner if side(winner["party"]) == "D" else loser)["wing"], "d_inc": d_inc,
                 "r": r_name, "r_wing": (winner if side(winner["party"]) == "R" else loser)["wing"], "r_inc": r_inc,
                 "winner": side(winner["party"]), "upset": side(winner["party"]) != ("D" if p_d >= 0.5 else "R"),  # same favorite rule as the scorecard and review
                 "vs_forecast": round(margin - mean, 1), "vs_pres": None if pres is None else round(margin - pres, 1)})


# House
inc = {x["district"]: x for x in load(W / "house_incoming.json")}
dep = {x["district"]: x for x in load(W / "house_departing.json")}
for r in load(HERE / "frozen" / "house_model.json")["races"]:
    k = r["district"]
    if r["tier"] in ("Safe", "Certain") or called["house"].get(k, {}).get("status") != "called":
        continue
    w = inc[k]
    lp = "R" if side(w["party"]) == "D" else "D"
    nominee = r["rep"] if lp == "R" else r["dem"]
    gone = dep.get(k)
    loser = gone if gone and side(gone["party"]) == lp and sur(gone["name"]) in re.sub(r"[^a-z]", "", nominee.lower()) else losers[("house", k)]
    add("House", k, r["tier"], r["mean"], r["p_dem"], r["pres"], r, re.sub(r"\s*\(.*?\)", "", r["dem"]), re.sub(r"\s*\(.*?\)", "", r["rep"]),
        r["inc_running"] and r["inc_party"] == "D", r["inc_running"] and r["inc_party"] == "R", w, loser, now["house"][k])

# Senate
POSTAL = {"Arkansas": "AR", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Idaho": "ID", "Illinois": "IL", "Iowa": "IA",
          "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Michigan": "MI", "Minnesota": "MN", "Montana": "MT",
          "Nebraska": "NE", "New Hampshire": "NH", "New Jersey": "NJ", "North Carolina": "NC", "Ohio": "OH", "Oregon": "OR",
          "South Carolina": "SC", "South Dakota": "SD", "Texas": "TX", "Alaska": "AK", "Mississippi": "MS"}
sinc = load(W / "senate_incoming.json")
sdep = {}
for x in load(W / "senate_departing.json"):
    sdep.setdefault(x["state"], []).append(x)
polls = load(HERE / "frozen" / "senate_polls.json")
cfg = load(HERE / "senate_config.json")
for r in load(HERE / "frozen" / "senate_model.json")["races"]:
    st, x = r["state"], called["senate"][r["state"]]
    if r["tier"] == "Safe" or x.get("status") != "called":
        continue
    c, pc = cfg[st], polls[st]
    win_name = x["winner"]
    w = next(m for m in sinc if m["state"] == POSTAL[st] and sur(m["name"]) == sur(win_name))
    lname = c["rep"] if sur(win_name) == sur(c["challenger"]) else c["challenger"]
    gone = next((g for g in sdep.get(POSTAL[st], []) if sur(g["name"]) == sur(lname)), None)
    loser = gone or losers[("senate", st)]
    # the incumbent is the Republican in every competitive race except the Democratic-held seats (DE, GA, IL, MI, MN, NH, NJ, OR)
    inc_party = re.search(r"\((\w)\)", pc["incumbent"] or "")
    running = not pc.get("open_seat") and "lost renomination" not in (pc["incumbent"] or "")
    d_inc = bool(running and inc_party and inc_party.group(1) == "D")
    r_inc = bool(running and inc_party and inc_party.group(1) == "R")
    pres = pc["fundamentals"].get("pres_2024_margin_D")
    add("Senate", st, r["tier"], r["mean"], r["p_challenger"], pres, r,
        c["challenger"], c["rep"], d_inc, r_inc, w, loser, now["senate"][st])

(W / "matchups.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
print(len(rows), "races;", sum(r["upset"] for r in rows), "upsets")
