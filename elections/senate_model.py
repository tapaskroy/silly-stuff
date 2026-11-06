#!/usr/bin/env python3
"""Probabilistic 2026 Senate model.

Inputs (all in this folder):
  senate_polls.json   individual polls + audited ballot facts per race (one record per poll)
  senate_config.json  per-race candidate mapping, region, RCV transfers, caucus assumptions
  model_params.json   weights and error parameters, each with a documented source
Output:
  senate_model.json   polling average, forecast mean/SD, win probability per race;
                      seat distribution, control probabilities, scenario table

Every number in the output is reproducible from those three files: no per-race judgment
adjustments are applied. Margins are always challenger (D or anti-R independent) minus R.
"""
import json
import math
import random
from datetime import date
from pathlib import Path

import forecast_lib as lib

HERE = Path(__file__).parent
polls_db = json.loads((HERE / "senate_polls.json").read_text())
config = json.loads((HERE / "senate_config.json").read_text())
P = json.loads((HERE / "model_params.json").read_text())
W, E = P["weights"], P["error"]
AS_OF = date.fromisoformat(P["as_of"])
ELECTION = date.fromisoformat(P["election"])
HOLDOVER = P["holdover"]


def poll_margin(poll, cfg):
    """Challenger minus R margin for one poll, after RCV transfers if the state uses them."""
    # A pollster's own final-round RCV numbers beat our transfer assumptions.
    final = poll.get("rcv_final") if cfg.get("rcv") else None
    res = {k.lower(): v for k, v in (final or poll["results"]).items() if isinstance(v, (int, float))}
    if final:
        ch, rep = res.get(cfg["challenger"].lower()), res.get(cfg["rep"].lower())
        return None if ch is None or rep is None else ch - rep
    ch, rep = res.get(cfg["challenger"].lower()), res.get(cfg["rep"].lower())
    if ch is None or rep is None:
        return None
    if cfg.get("rcv"):
        # Ranked choice: minor candidates' first choices are redistributed (share to R given per candidate).
        for name, to_r in cfg.get("rcv_to_r", {}).items():
            v = res.get(name.lower())
            if v:
                rep += v * to_r
                ch += v * (1 - to_r)
    return ch - rep


def average(state, cfg):
    return lib.average(polls_db[state].get("polls", []), lambda p: poll_margin(p, cfg), W, AS_OF, P["poll_window_start"])


def fundamentals(state, cfg):
    """Prior from 2024 presidential margin + national shift since 2024 (+ incumbency)."""
    f = polls_db[state]["fundamentals"]
    pres = f.get("pres_2024_margin_D")
    if pres is None or cfg["challenger_party"] != "D":
        return None
    prior = pres + P["national_shift"] + cfg.get("incumbency", 0) * P["incumbency_bonus"]
    return prior


def race(state):
    cfg = config[state]
    avg = average(state, cfg)
    prior = fundamentals(state, cfg)
    days_out = (ELECTION - AS_OF).days
    if avg:
        # Error of a polling average: base state error (scaled for time to election), sampling noise
        # when there are few polls, and extra uncertainty from undecided voters.
        poll_sd = math.sqrt(E["state_sd"] ** 2 * (1 + E["per_day"] * days_out)
                            + E["single_poll_sd"] ** 2 / avg["n_eff"]
                            + (E["per_undecided"] * avg["undecided"]) ** 2)
        if cfg["challenger_party"] != "D":
            poll_sd = math.sqrt(poll_sd ** 2 + E["independent_extra_sd"] ** 2)
        if prior is not None:
            pw, fw = 1 / poll_sd ** 2, 1 / E["fundamentals_sd"] ** 2
            mean = (avg["mean"] * pw + prior * fw) / (pw + fw)
            sd = math.sqrt(1 / (pw + fw))
            prior_w = fw / (pw + fw)
        else:
            mean, sd, prior_w = avg["mean"], poll_sd, 0.0
        basis = "polls"
    else:
        mean, sd, basis, prior_w = prior, E["fundamentals_sd"], "fundamentals", 1.0
    # The national and regional components are simulated separately, so the race SD here is state-specific.
    return {"state": state, "cfg": cfg, "avg": avg, "prior": prior, "prior_w": prior_w,
            "mean": mean, "sd": sd, "basis": basis}


def t_draw(rng, df):
    """Student-t with unit variance (fat tails: big misses happen more often than a normal implies)."""
    z = rng.gauss(0, 1)
    chi = rng.gammavariate(df / 2, 2)
    return z / math.sqrt(chi / df) * math.sqrt((df - 2) / df)


def simulate(races, shift=0.0, n=P["sims"], seed=2026):
    rng = random.Random(seed)
    df = E["t_df"]
    regions = sorted({r["cfg"]["region"] for r in races})
    wins = {r["state"]: 0 for r in races}
    seat_hist = {}
    control = {"D": 0, "R": 0}
    for _ in range(n):
        nat = t_draw(rng, df) * E["national_sd"] + shift
        reg = {g: t_draw(rng, df) * E["regional_sd"] for g in regions}
        seats = {"D": HOLDOVER["D"], "R": HOLDOVER["R"], "I": 0}
        for r in races:
            m = r["mean"] + nat + reg[r["cfg"]["region"]] + t_draw(rng, df) * r["sd"]
            if m > 0:
                wins[r["state"]] += 1
                seats["D" if r["cfg"]["challenger_party"] == "D" else "I"] += 1
            else:
                seats["R"] += 1
        key = (seats["D"], seats["I"])
        seat_hist[key] = seat_hist.get(key, 0) + 1
    return {s: w / n for s, w in wins.items()}, {f"{d},{i}": c / n for (d, i), c in sorted(seat_hist.items())}


def control_probs(hist):
    """Control under the caucus assumptions for anti-R independents.

    Senate control needs 51 seats, or 50 plus the VP (Vance, so Republicans win a 50-50 tie).
    """
    out = {}
    for mode in P["caucus_modes"]:
        d_ctrl = r_ctrl = unclear = 0.0
        for key, pr in hist.items():
            d, i = map(int, key.split(","))
            r = 100 - d - i
            if mode["independents"] == "D":
                d += i
            elif mode["independents"] == "R":
                r += i
            if d >= 51:
                d_ctrl += pr
            elif r >= 50:
                r_ctrl += pr
            else:
                unclear += pr  # neither side has a majority: independents decide
        out[mode["key"]] = {"label": mode["label"], "D": d_ctrl, "R": r_ctrl, "unclear": unclear}
    return out


def main():
    races = [race(s) for s in sorted(config)]
    probs, hist = simulate(races)
    scenarios = []
    for sc in P["scenarios"]:
        sp, sh = simulate(races, shift=sc["shift"], n=P["scenario_sims"])
        # Seats if every race went to whoever leads after the shift (no further noise).
        lead_d = sum(1 for r in races if r["mean"] + sc["shift"] > 0 and r["cfg"]["challenger_party"] == "D")
        lead_i = sum(1 for r in races if r["mean"] + sc["shift"] > 0 and r["cfg"]["challenger_party"] != "D")
        scenarios.append({"label": sc["label"], "shift": sc["shift"],
                          "leaders": {"D": HOLDOVER["D"] + lead_d, "I": lead_i,
                                      "R": 100 - HOLDOVER["D"] - lead_d - lead_i},
                          "control": control_probs(sh)})
    d_totals = {}
    for key, pr in hist.items():
        d, i = map(int, key.split(","))
        d_totals[d + i] = d_totals.get(d + i, 0) + pr
    out = {"as_of": P["as_of"], "params": P, "races": [], "seat_dist_d_plus_i": d_totals,
           "control": control_probs(hist), "scenarios": scenarios}
    for r in races:
        p = probs[r["state"]]
        a = r["avg"]
        out["races"].append({
            "state": r["state"], "challenger": r["cfg"]["challenger"], "challenger_party": r["cfg"]["challenger_party"],
            "rep": r["cfg"]["rep"], "basis": r["basis"],
            "poll_avg": round(a["mean"], 1) if a else None, "poll_avg_raw": round(a["raw_mean"], 1) if a else None,
            "n_polls": a["n_polls"] if a else 0, "n_eff": round(a["n_eff"], 1) if a else 0,
            "undecided": round(a["undecided"], 1) if a else None,
            "prior": round(r["prior"], 1) if r["prior"] is not None else None, "prior_weight": round(r["prior_w"], 3),
            "mean": round(r["mean"], 1), "sd": round(math.sqrt(r["sd"] ** 2 + E["national_sd"] ** 2 + E["regional_sd"] ** 2), 1),
            "p_challenger": p, "tier": lib.tier(p, P["tiers"]),
            # Inputs for the in-page scenario simulator (senate_sim.js): unrounded mean, state-only SD, region.
            "sim": {"mean": round(r["mean"], 3), "sd": round(r["sd"], 3), "region": r["cfg"]["region"]},
            "polls": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()} for row in (a["polls"] if a else [])],
        })
    (HERE / "senate_model.json").write_text(json.dumps(out, indent=1))
    exp = sum(k * v for k, v in d_totals.items())
    c = out["control"]
    print(f"expected D+I seats {exp:.1f}; control: " + "; ".join(
        f"{v['label']}: D {v['D']:.0%} R {v['R']:.0%} unclear {v['unclear']:.0%}" for v in c.values()))
    for r in out["races"]:
        if 0.03 < r["p_challenger"] < 0.97:
            print(f"  {r['state']:15} avg {r['poll_avg']!s:>6} mean {r['mean']:>5} sd {r['sd']:>4}  P(chal) {r['p_challenger']:.0%}  {r['tier']}")


if __name__ == "__main__":
    main()
