#!/usr/bin/env python3
"""Rerun the frozen Nov 3 models with one rule changed at a time, and score each version on the races AP has called.

Each run copies the model code and the frozen inputs into a temporary folder (the parameters come from the frozen model
output), so nothing in the project changes. The unchanged copy reproduces the frozen forecast exactly; the script checks that.
The last House/Senate/governor variant uses the actual national House vote (national_vote.json): hindsight, a diagnostic only.
Usage: python3 review/counterfactuals.py   (writes review/counterfactuals.json; takes a few minutes)
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RV = Path(__file__).parent
HERE = RV.parent
FROZEN = HERE / "frozen"
RES = json.loads((HERE / "results.json").read_text())
COUNT = json.loads((RV / "ap_count.json").read_text())  # AP's current count for every race, called or not
NAT = json.loads((RV / "national_vote.json").read_text())
ACTUAL = round(NAT["dem_pct"] - NAT["rep_pct"], 1)
MODELS = {"house": ("house_model.py", "model_params_house.json", "house_model.json", "district", "p_dem"),
          "senate": ("senate_model.py", "model_params.json", "senate_model.json", "state", "p_challenger"),
          "governors": ("governor_model.py", "model_params_gov.json", "gov_model.json", "state", "p_challenger")}


def parties(c):
    return {s.rsplit(" (", 1)[0]: s.rsplit("(", 1)[1].rstrip(")") for s in c.split(" vs ")}


def setp(*path, v):
    def f(P):
        o = P
        for p in path[:-1]:
            o = o[p]
        o[path[-1]] = v
    return f


def both(*fs):
    def f(P):
        for g in fs:
            g(P)
    return f


VARIANTS = {
    "house": [("frozen", "The forecast as published", lambda P: None),
              ("no_shade", "Generic ballot at face value (no 1-point shading toward Republicans)", setp("generic_ballot_bias_adj", v=0.0)),
              ("no_partisan_shift", "Partisan polls not shifted against their sponsor (still half weight)", setp("weights", "partisan_shift", v=0.0)),
              ("both", "Both of the above", both(setp("generic_ballot_bias_adj", v=0.0), setp("weights", "partisan_shift", v=0.0))),
              ("no_elasticity", "No damping of the national swing in lopsided seats", setp("elasticity_k", v=0.0)),
              ("light_prior", "Lighter fundamentals prior (its error x1.5)", both(setp("error", "fundamentals_sd", v=8.25), setp("error", "fundamentals_sd_open", v=9.0),
                                                                                  setp("error", "fundamentals_sd_new", v=9.75))),
              ("wide_national", "Wider national polling error (SD 3 to 4.5)", setp("error", "national_sd", v=4.5)),
              ("hindsight", f"Hindsight: national environment set to the actual House vote, D+{ACTUAL}",
               both(setp("national_shift", v=ACTUAL + 1.5), setp("generic_ballot_bias_adj", v=0.0)))],
    "senate": [("frozen", "The forecast as published", lambda P: None),
               ("no_partisan_shift", "Partisan polls not shifted against their sponsor", setp("weights", "partisan_shift", v=0.0)),
               ("light_prior", "Lighter fundamentals prior (its error 12 to 18)", setp("error", "fundamentals_sd", v=18.0)),
               ("wide_national", "Wider national polling error (SD 3 to 4.5)", setp("error", "national_sd", v=4.5)),
               ("hindsight", f"Hindsight: national environment set to the actual House vote, D+{ACTUAL}", setp("national_shift", v=ACTUAL + 1.5))],
    "governors": [("frozen", "The forecast as published", lambda P: None),
                  ("no_partisan_shift", "Partisan polls not shifted against their sponsor", setp("weights", "partisan_shift", v=0.0)),
                  ("light_prior", "Lighter fundamentals prior (its error x1.5)", both(setp("error", "fundamentals_sd", v=16.5), setp("error", "fundamentals_sd_nopoll", v=21.0))),
                  ("wide_national", "Wider national polling error (SD 3 to 4.5)", setp("error", "national_sd", v=4.5)),
                  ("hindsight", f"Hindsight: national environment set to the actual House vote, D+{ACTUAL}",
                   both(setp("national_shift", v=ACTUAL + 1.5), setp("generic_ballot", v=ACTUAL)))],
}


def score(ch, races, frozen):
    _, _, _, k, pk = MODELS[ch]
    right = n = close_r = close_n = 0
    brier = ll = 0.0
    fixed, broke, errs = [], [], []
    for r in races:
        if r.get("fixed"):
            continue
        x = RES[ch].get(r[k]) or {}
        if x.get("status") != "called":
            continue
        par = parties(x["candidates"])
        a = next(iter(par))
        p, win_a, pf = r[pk], x["winner"] == a, frozen[r[k]][pk]
        n += 1
        right += (p >= .5) == win_a
        brier += (p - win_a) ** 2
        ll -= math.log(max(1e-4, p if win_a else 1 - p))
        if 0.2 <= pf <= 0.8:
            close_n += 1
            close_r += (p >= .5) == win_a
        if (pf >= .5) != win_a and (p >= .5) == win_a:
            fixed.append(r[k])
        if (pf >= .5) == win_a and (p >= .5) != win_a:
            broke.append(r[k])
        m = (COUNT[ch].get(r[k]) or {}).get("margin")
        if m is not None:
            errs.append((m - r["mean"]) * (1 if par[a] != "R" else -1))
    return {"right": right, "n": n, "brier": round(brier / n, 4), "logloss": round(ll / n, 3), "close_right": close_r, "close_n": close_n,
            "upsets_fixed": fixed, "new_misses": broke, "bias": round(sum(errs) / len(errs), 1), "mae": round(sum(map(abs, errs)) / len(errs), 1)}


def main():
    out = {"actual_national": ACTUAL}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        base.mkdir()
        for f in ("house_model.py", "senate_model.py", "governor_model.py", "forecast_lib.py", "senate_config.json", "gov_config.json", "house_overrides.json"):
            shutil.copy(HERE / f, base)
        for f in ("house_data.json", "house_polls.json", "senate_polls.json", "gov_polls.json"):
            shutil.copy(FROZEN / f, base)
        for ch, (py, pf, mf, k, pk) in MODELS.items():
            (base / pf).write_text(json.dumps(json.loads((FROZEN / mf).read_text())["params"], indent=1))
        for ch, (py, pf, mf, k, pk) in MODELS.items():
            frozen = {r[k]: r for r in json.loads((FROZEN / mf).read_text())["races"]}
            out[ch] = []
            for key, label, edit in VARIANTS[ch]:
                d = Path(tmp) / f"{ch}_{key}"
                shutil.copytree(base, d)
                P = json.loads((d / pf).read_text())
                edit(P)
                (d / pf).write_text(json.dumps(P, indent=1))
                subprocess.run([sys.executable, py], cwd=d, check=True, capture_output=True)
                races = json.loads((d / mf).read_text())["races"]
                if key == "frozen":
                    assert all(abs(r[pk] - frozen[r[k]][pk]) < 1e-9 for r in races), f"{ch}: the rerun doesn't reproduce the frozen forecast"
                s = score(ch, races, frozen)
                s.update(key=key, label=label)
                out[ch].append(s)
                print(ch, key, {x: s[x] for x in ("right", "n", "brier", "close_right", "close_n", "upsets_fixed")}, flush=True)
    (RV / "counterfactuals.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
