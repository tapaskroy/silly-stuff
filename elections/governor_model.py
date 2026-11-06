#!/usr/bin/env python3
"""Probabilistic 2026 governor model: same structure as senate_model.py and house_model.py.

Inputs:
  gov_polls.json           audited per-state research: individual polls, ballot, fundamentals, ratings, context
  gov_config.json          per-race candidate mapping, region, RCV transfers, incumbency (built by merge_gov.py)
  model_params_gov.json    weights and error parameters with sources
Output:
  gov_model.json           per-race forecast + distribution of governorships, scenarios

Margins are challenger (D, or the main anti-R independent) minus R. No race-specific judgment adjustments.
"""
import json
import math
from datetime import date
from pathlib import Path

import numpy as np

import forecast_lib as lib

HERE = Path(__file__).parent
db = json.loads((HERE / "gov_polls.json").read_text())
config = json.loads((HERE / "gov_config.json").read_text())
P = json.loads((HERE / "model_params_gov.json").read_text())
W, E = P["weights"], P["error"]
AS_OF = date.fromisoformat(P["as_of"])
ELECTION = date.fromisoformat(P["election"])
HOLD = P["not_up"]


def poll_margin(poll, cfg):
    final = poll.get("rcv_final") if cfg.get("rcv") else None
    res = {k.lower(): v for k, v in (final or poll["results"]).items() if isinstance(v, (int, float))}
    ch, rep = res.get(cfg["challenger"].lower()), res.get(cfg["rep"].lower())
    if ch is None or rep is None:
        return None
    if cfg.get("rcv") and not final:
        for name, to_r in cfg.get("rcv_to_r", {}).items():
            v = res.get(name.lower())
            if v:
                rep += v * to_r
                ch += v * (1 - to_r)
    return ch - rep


def fundamentals(state, cfg):
    """Prior: a blend of (2024 presidential margin + national swing) and (last governor margin + swing since then),
    plus incumbency. Governors run far ahead of or behind the top of the ticket, so the prior is weak."""
    if cfg["challenger_party"] != "D" or cfg["opponent_party"] != "R":
        return None, {}  # D-vs-R fundamentals don't describe a race against an independent
    f = db[state]["fundamentals"]
    pres, last = f.get("pres_2024_margin_D"), f.get("last_gov_margin_D")
    shift = P["national_shift"] * P["national_shift_factor"]
    parts = {}
    if pres is not None:
        # State lean = presidential margin relative to the nation (R+1.5 in 2024), shrunk for governors.
        nat = P["national_pres_2024"]
        parts["pres"] = nat + P["pres_lean_coef"] * (pres - nat) + shift + cfg["incumbency"] * P["incumbency_bonus"]
    if last is not None and cfg.get("last_year") in P["house_vote_by_year"]:
        since = (P["generic_ballot"] - P["house_vote_by_year"][cfg["last_year"]]) * P["national_shift_factor"]
        # The last result already contains the then-candidates' strength; only add incumbency if the
        # winner's party now runs an incumbent who wasn't on that ballot (rare) — so none is added here.
        parts["last"] = last + since
    if not parts:
        return None, {}
    if "pres" in parts and "last" in parts:
        w = P["last_gov_weight"]
        return (1 - w) * parts["pres"] + w * parts["last"], parts
    return next(iter(parts.values())), parts


def race(state):
    cfg = config[state]
    avg = lib.average(db[state].get("polls", []), lambda p: poll_margin(p, cfg), W, AS_OF, P["poll_window_start"])
    prior, parts = fundamentals(state, cfg)
    days_out = (ELECTION - AS_OF).days
    prior_w = None
    if avg:
        poll_sd = math.sqrt(E["state_sd"] ** 2 * (1 + E["per_day"] * days_out)
                            + E["single_poll_sd"] ** 2 / avg["n_eff"]
                            + (E["per_undecided"] * avg["undecided"]) ** 2)
        if "I" in (cfg["challenger_party"], cfg["opponent_party"]):
            poll_sd = math.sqrt(poll_sd ** 2 + E["independent_extra_sd"] ** 2)
        if prior is not None:
            pw, fw = 1 / poll_sd ** 2, 1 / E["fundamentals_sd"] ** 2
            mean, sd, prior_w = (avg["mean"] * pw + prior * fw) / (pw + fw), math.sqrt(1 / (pw + fw)), fw / (pw + fw)
        else:
            mean, sd, prior_w = avg["mean"], poll_sd, 0.0
        basis = "polls"
    else:
        mean, sd, basis, prior_w = prior, E["fundamentals_sd_nopoll"], "fundamentals", 1.0
    return {"state": state, "cfg": cfg, "avg": avg, "prior": prior, "parts": parts, "prior_w": prior_w,
            "mean": mean, "sd": sd, "basis": basis}


def simulate(races, shift=0.0, n=None, seed=2026):
    n = n or P["sims"]
    rng = np.random.default_rng(seed)
    df = E["t_df"]
    scale = math.sqrt((df - 2) / df)
    regions = sorted({r["cfg"]["region"] for r in races})
    ridx = np.array([regions.index(r["cfg"]["region"]) for r in races])
    mean = np.array([r["mean"] for r in races])
    sd = np.array([r["sd"] for r in races])
    nat = rng.standard_t(df, n) * scale * E["national_sd"] + shift
    reg = rng.standard_t(df, (n, len(regions))) * scale * E["regional_sd"]
    loc = rng.standard_t(df, (n, len(races))) * scale * sd
    win = (mean + nat[:, None] + reg[:, ridx] + loc) > 0
    # A challenger win goes to the challenger's party; otherwise to the opponent's (R, or I in Rhode Island).
    party = lambda p: np.array([r["cfg"][p] for r in races])
    ch, op = party("challenger_party"), party("opponent_party")
    d_seats = (win & (ch == "D")).sum(axis=1) + (~win & (op == "D")).sum(axis=1) + HOLD["D"]
    i_seats = (win & (ch == "I")).sum(axis=1) + (~win & (op == "I")).sum(axis=1) + HOLD.get("I", 0)
    return win.mean(axis=0), d_seats, i_seats


def main():
    races = [race(s) for s in sorted(config)]
    probs, d_seats, i_seats = simulate(races)
    dist = {int(k): float(v) for k, v in enumerate(np.bincount(d_seats) / len(d_seats)) if v}
    scen = []
    for sc in P["scenarios"]:
        _, ds, _ = simulate(races, shift=sc["shift"], n=P["scenario_sims"])
        leaders = HOLD["D"] + sum(1 for r in races if r["cfg"]["challenger_party"] == "D" and r["mean"] + sc["shift"] > 0)
        scen.append({"label": sc["label"], "shift": sc["shift"], "leaders_D": leaders,
                     "median_D": float(np.median(ds)), "p_d_majority": float((ds >= 26).mean())})
    out = {"as_of": P["as_of"], "params": P, "dist_d": dist, "expected_d": float(d_seats.mean()),
           "expected_i": float(i_seats.mean()), "p_d_majority": float((d_seats >= 26).mean()),
           "pct": {q: int(np.percentile(d_seats, q)) for q in (10, 50, 90)}, "scenarios": scen, "races": []}
    for r, p in zip(races, probs):
        a = r["avg"]
        out["races"].append({
            "state": r["state"], "challenger": r["cfg"]["challenger"], "challenger_party": r["cfg"]["challenger_party"],
            "opponent_party": r["cfg"]["opponent_party"],
            "rep": r["cfg"]["rep"], "basis": r["basis"],
            "poll_avg": round(a["mean"], 1) if a else None, "poll_avg_raw": round(a["raw_mean"], 1) if a else None,
            "n_polls": a["n_polls"] if a else 0, "n_eff": round(a["n_eff"], 1) if a else 0,
            "undecided": round(a["undecided"], 1) if a else None,
            "prior": round(r["prior"], 1) if r["prior"] is not None else None,
            "prior_parts": {k: round(v, 1) for k, v in r["parts"].items()}, "prior_weight": round(r["prior_w"], 3),
            "mean": round(r["mean"], 1),
            "sd": round(math.sqrt(r["sd"] ** 2 + E["national_sd"] ** 2 + E["regional_sd"] ** 2), 1),
            "p_challenger": float(p), "tier": lib.tier(float(p), P["tiers"]),
            # Inputs for the in-page scenario simulator (gov_sim.js): unrounded mean, state-only SD, region.
            "sim": {"mean": round(r["mean"], 3), "sd": round(r["sd"], 3), "region": r["cfg"]["region"]},
            "polls": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()} for row in (a["polls"] if a else [])],
        })
    (HERE / "gov_model.json").write_text(json.dumps(out, indent=1))
    print(f"expected D governors {out['expected_d']:.1f} (+I {out['expected_i']:.1f}); P(D 26+) {out['p_d_majority']:.0%}")
    for r in out["races"]:
        if 0.03 < r["p_challenger"] < 0.97:
            print(f"  {r['state']:15} avg {r['poll_avg']!s:>6} prior {r['prior']!s:>6} mean {r['mean']:>6} sd {r['sd']:>4} "
                  f"P(chal) {r['p_challenger']:.0%} {r['tier']}")


if __name__ == "__main__":
    main()
