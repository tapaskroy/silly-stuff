#!/usr/bin/env python3
"""Title-odds model for the tournament "big" picks (winner / runner-up / third).

Reads eloRatings from config.json and turns them into champion probabilities via a
softmax over scaled Elo (deeper runs reward strength superlinearly). Prints the
strength-ranked winner / runner-up / third. Stdlib only.

    python3 big_model.py
"""
import json
import math
import os

CONFIG = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG) as fh:
    cfg = json.load(fh)

ELO = cfg["eloRatings"]
SCALE = 90.0   # smaller = more top-heavy

z = {t: math.exp((r - 2000) / SCALE) for t, r in ELO.items()}
Z = sum(z.values())
title = {t: z[t] / Z for t in ELO}
ranked = sorted(title.items(), key=lambda kv: -kv[1])

print("TITLE ODDS (model):")
for t, p in ranked[:10]:
    print(f"  {t:12} {p*100:5.1f}%   (Elo {ELO[t]})")

print("\nPicks (strength-ranked):")
print("  Winner   :", ranked[0][0])
print("  Runner-up:", ranked[1][0])
print("  Third    :", ranked[2][0])
