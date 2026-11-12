#!/usr/bin/env python3
"""What changed in results.json since the last update: new AP calls with our chance for the winner, upsets, withdrawn calls,
and the scorecard's headline numbers. Back up results.json to results.prev.json before running fetch_ap.py.
Usage: python3 analysis/summarize.py   (from the project folder, after build_scorecard.py)
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent.parent
load = lambda f: json.loads((HERE / f).read_text())
r, prev = load("results.json"), load("results.prev.json")
mods = {"senate": {x["state"]: x for x in load("frozen/senate_model.json")["races"]},
        "governors": {x["state"]: x for x in load("frozen/gov_model.json")["races"]},
        "house": {x["district"]: x for x in load("frozen/house_model.json")["races"]}}
pk = {"senate": "p_challenger", "governors": "p_challenger", "house": "p_dem"}
safe = 0
for ch in mods:
    for k, x in r[ch].items():
        before = (prev[ch].get(k) or {}).get("winner")
        if x["winner"] and not before:
            p = mods[ch][k][pk[ch]]
            a = x["candidates"].split(" (")[0]
            pw = p if x["winner"] == a else 1 - p
            party = x["candidates"].split(" vs ")[0 if x["winner"] == a else 1].rsplit("(", 1)[1][0]
            if pw < 0.98 or ch != "house":
                print(ch, k, (x.get("winner_name") or x["winner"]) + f" ({party})", f"{pw:.0%}", "UPSET" if pw < 0.5 else "")
            else:
                safe += 1
        if before and x["winner"] != before:
            print("CHANGED", ch, k, before, "->", x["winner"])
print("safe House calls:", safe)
s = (HERE / "scorecard.html").read_text()
t = re.sub(r"<[^>]+>", "", s)
print(re.findall(r"D \d+ · \d+ not yet called · R \d+", t))
print(s.count("verdict miss"), "misses")
print(re.findall(r"(\d+) of \d+ races called", s))
