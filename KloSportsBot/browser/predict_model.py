#!/usr/bin/env python3
"""Poisson / Dixon-Coles-style score model -> pool-optimal picks.

Team (attack, defense) multipliers and the goals baseline come from config.json
(teamRatings + baseGoals). Pass fixtures as "Home,Away" pairs on the command line:

    python3 predict_model.py "Portugal,DR Congo" "England,Croatia"

For each fixture it prints the most-likely scoreline plus the pick that maximizes
expected pool points (EP = 3*P(correct result) + 2*P(exact score)).
Uses only the Python stdlib (math) — no pip dependencies.
"""
import json
import math
import os
import sys

CONFIG = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG) as fh:
    cfg = json.load(fh)

BASE = cfg.get("baseGoals", 1.35)
T = {name: tuple(v) for name, v in cfg["teamRatings"].items()}

fixtures = [arg.split(",", 1) for arg in sys.argv[1:]]
if not fixtures:
    print('Usage: python3 predict_model.py "Home,Away" ["Home2,Away2" ...]', file=sys.stderr)
    sys.exit(1)


def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def rating(team):
    if team not in T:
        print(f"!! no rating for {team!r} in config.json teamRatings", file=sys.stderr)
        sys.exit(1)
    return T[team]


print("=== most-likely scorelines ===")
for a, b in fixtures:
    a, b = a.strip(), b.strip()
    asA, dsA = rating(a)
    asB, dsB = rating(b)
    lamA = BASE * asA * dsB
    lamB = BASE * asB * dsA
    N = 9
    pa = [pois(i, lamA) for i in range(N)]
    pb = [pois(j, lamB) for j in range(N)]
    best = (0, 0)
    bestp = 0
    pW = pD = pL = 0
    for i in range(N):
        for j in range(N):
            p = pa[i] * pb[j]
            if p > bestp:
                bestp = p
                best = (i, j)
            if i > j:
                pW += p
            elif i == j:
                pD += p
            else:
                pL += p
    print(f"{a} vs {b:14}| xG {lamA:.2f}-{lamB:.2f} | "
          f"pred {best[0]}-{best[1]} ({bestp*100:.0f}%) | "
          f"W/D/L {pW*100:.0f}/{pD*100:.0f}/{pL*100:.0f}")

print("\n=== POOL-OPTIMAL picks (maximize EP = 3*P(result) + 2*P(exact)) ===")
for a, b in fixtures:
    a, b = a.strip(), b.strip()
    asA, dsA = rating(a)
    asB, dsB = rating(b)
    lamA = BASE * asA * dsB
    lamB = BASE * asB * dsA
    N = 9
    pa = [pois(i, lamA) for i in range(N)]
    pb = [pois(j, lamB) for j in range(N)]
    P = {}
    pW = pD = pL = 0
    for i in range(N):
        for j in range(N):
            p = pa[i] * pb[j]
            P[(i, j)] = p
            if i > j:
                pW += p
            elif i == j:
                pD += p
            else:
                pL += p
    cls = {"W": pW, "D": pD, "L": pL}

    def cl(i, j):
        return "W" if i > j else ("D" if i == j else "L")

    bestEP = -1
    bestS = None
    for (i, j), p in P.items():
        if i + j > 6:
            continue
        ep = 3 * cls[cl(i, j)] + 2 * p
        if ep > bestEP:
            bestEP = ep
            bestS = (i, j)
    print(f"{a:12} vs {b:14} -> {bestS[0]}-{bestS[1]}   (EP {bestEP:.2f} pts)")
