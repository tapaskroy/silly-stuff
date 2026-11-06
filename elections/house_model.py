#!/usr/bin/env python3
"""Probabilistic 2026 House model: same structure as senate_model.py, adapted to districts.

Inputs:
  house_data.json          all 435 districts: candidates, 2024 presidential margin on 2026 lines, ratings, context
  house_polls.json         audited records for the ~170 contested-or-polled districts: individual polls, ballot,
                           verified baseline, 2024 House result, corrections
  model_params_house.json  weights and error parameters with sources
Output:
  house_model.json         per-district forecast + seat distribution, control probability, scenarios

Margins are D minus R in points. No district-specific judgment adjustments are applied.
"""
import json
import math
import re
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np

import forecast_lib as lib

HERE = Path(__file__).parent
data = json.loads((HERE / "house_data.json").read_text())
audit = json.loads((HERE / "house_polls.json").read_text())
P = json.loads((HERE / "model_params_house.json").read_text())
OVR = json.loads((HERE / "house_overrides.json").read_text())
W, E = P["weights"], P["error"]
AS_OF = date.fromisoformat(P["as_of"])
MAJORITY = 218

REGION = {
    "Northeast": "CT DE MA MD ME NH NJ NY PA RI VT",
    "Midwest": "IA IL IN KS MI MN MO ND NE OH SD WI",
    "South": "AL AR FL GA KY LA MS NC OK SC TN TX VA WV",
    "West": "AK AZ CA CO HI ID MT NM NV OR UT WA WY",
}
REGION_OF = {s: g for g, ss in REGION.items() for s in ss.split()}


def parse_margin(s):
    """'R+4.2' / 'D+12' / 'Trump +3.1' -> D-minus-R float, or None."""
    m = re.search(r"\b(R|D|Trump|Harris)\s*\+\s*(\d+(?:\.\d+)?)", str(s or ""))
    if not m:
        return None
    v = float(m.group(2))
    return -v if m.group(1) in ("R", "Trump") else v


def party_of(inc):
    m = re.search(r"\((D|R|DFL|I)\b", inc or "")
    return {"DFL": "D"}.get(m.group(1), m.group(1)) if m else None


def surname(name):
    name = re.sub(r"\s*\((inc\.|D|R|DFL|I|[^)]*)\)", "", name or "").strip()
    parts = [p for p in name.replace(",", "").split() if p not in ("Jr.", "Jr", "Sr.", "II", "III", "IV")]
    if not parts:
        return ""
    i = len(parts) - 1
    while i > 0 and parts[i - 1] in ("von", "van", "de", "der", "del", "da", "di", "la", "le"):  # e.g. "von Wilpert"
        i -= 1
    return " ".join(parts[i:])


def clean_name(name):
    return re.sub(r"\s*\([^)]*\)", "", name or "").strip()


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", t.replace("-", " ")).strip()


def none_like(v):
    return not v or str(v).lower().startswith(("none", "no "))


def district(r):
    d = r["district"]
    a = audit.get(d, {})
    b = a.get("ballot") or {}
    dem = b.get("D") if b else r["dem"]
    rep = b.get("R") if b else r["rep"]
    pres = a.get("pres_2024_margin_D")
    pres_src = a.get("pres_source") or r["baseline"].get("note")
    if pres is None:
        pres = parse_margin(r["baseline"].get("pres_2024"))
    inc_p = a.get("incumbent_party") or party_of(r["incumbent"])
    inc_p = inc_p[0] if inc_p and inc_p[0] in "DRI" else None  # e.g. "I (NPP; caucuses R)" -> "I"
    inc_running = a.get("incumbent_running")
    if inc_running is None:
        inc_running = not r["open_seat"] and "vacant" not in r["incumbent"].lower()
    new_terr = a.get("incumbent_new_territory")
    if new_terr is None:
        new_terr = bool(r["baseline"].get("redistricted"))
    ov = OVR.get(d, {})
    ch_party = ov.get("challenger_party", "D")
    if ov.get("challenger"):
        dem = ov["challenger"]
    out = {"district": d, "state": d.split("-")[0], "incumbent": a.get("incumbent") or r["incumbent"],
           "ch_party": ch_party, "override": ov.get("why"),
           "inc_party": inc_p, "inc_running": inc_running, "dem": dem, "rep": rep, "pres": pres,
           "pres_src": pres_src, "audited": bool(a), "fixed": None, "avg": None, "prior": None}

    # Races decided by the ballot itself: one major party absent, or a same-party (top-two) contest.
    same = (b.get("same_party") or "") if b else ""
    if b.get("uncontested") or none_like(dem) or none_like(rep) or same:
        if same:
            out["fixed"] = "D" if same.upper().startswith("D") else "R"
        else:
            out["fixed"] = "R" if none_like(dem) else "D"
        return out
    if " / " in str(dem) and none_like(rep):
        out["fixed"] = "D"
        return out

    # Fundamentals prior: presidential margin + national swing (scaled by elasticity) + incumbency.
    if pres is not None and ch_party == "D":
        elastic = 1 - P["elasticity_k"] * min(abs(pres), 40) / 40
        sign = {"D": 1, "R": -1}.get(inc_p, 0) if inc_running else 0
        inc_term = sign * P["incumbency_bonus"] * (P["new_territory_factor"] if new_terr else 1)
        h = a.get("house_2024") or {}
        overperf = None
        # A 2024 margin of 60+ usually means no real opponent; that says nothing about candidate strength.
        if sign and h.get("comparable") and h.get("margin_D") is not None and not new_terr and abs(h["margin_D"]) < P["overperf_max_margin"]:
            overperf = h["margin_D"] - pres  # incumbent's 2024 result relative to the top of the ticket
            overperf = max(-P["overperf_cap"], min(P["overperf_cap"], overperf))
            inc_term = sign * P["incumbency_bonus"] + P["overperformance_shrink"] * (overperf - sign * P["incumbency_bonus"])
        out["prior"] = pres + (P["national_shift"] + P["generic_ballot_bias_adj"]) * elastic + inc_term
        out["inc_term"], out["overperf"], out["elastic"] = inc_term, overperf, elastic
        out["new_territory"] = new_terr

    # District polls.
    dn, rn = surname(dem), surname(rep)
    out["dn"], out["rn"] = dn, rn

    full_d, full_r = (";".join(norm(x) for x in clean_name(n).split(";")) for n in (dem, rep))

    def pick(res, full, last):
        # Poll tables key candidates by surname, which may be compound ("Van Drew", "De La Cruz").
        # Several names separated by ";" (Louisiana's all-party primary) are summed as a party total.
        names = [n.strip() for n in full.split(";")] if ";" in full else [full]
        total, hit = 0.0, False
        for name in names:
            for k, v in res.items():
                nk = norm(k)
                if nk and (name.endswith(nk) or (len(names) == 1 and nk.split()[-1] == norm(last))):
                    total, hit = total + v, True
                    break
        return total if hit else None

    def margin_of(p):
        res = {k: v for k, v in p["results"].items() if isinstance(v, (int, float))}
        x, y = pick(res, full_d, dn), pick(res, full_r, rn)
        if x is None or y is None:
            return None
        for name, to_r in ov.get("rcv_to_r", {}).items():  # ranked-choice transfers of minor candidates
            v = res.get(name)
            if v:
                x, y = x + v * (1 - to_r), y + v * to_r
        return x - y

    out["avg"] = lib.average(a.get("polls") or [], margin_of, W, AS_OF, P["poll_window_start"])
    fsd = E["fundamentals_sd_open"] if not inc_running else (E["fundamentals_sd_new"] if new_terr else E["fundamentals_sd"])
    avg = out["avg"]
    if avg and out["prior"] is not None:
        poll_sd = math.sqrt(E["poll_state_sd"] ** 2 + E["single_poll_sd"] ** 2 / avg["n_eff"]
                            + (E["per_undecided"] * avg["undecided"]) ** 2)
        pw, fw = 1 / poll_sd ** 2, 1 / fsd ** 2
        out["mean"] = (avg["mean"] * pw + out["prior"] * fw) / (pw + fw)
        out["sd"] = math.sqrt(1 / (pw + fw))
        out["prior_weight"] = fw / (pw + fw)
        out["basis"] = "polls + fundamentals"
    elif avg:
        # Independent challenger: no comparable past result, so polls only, with extra uncertainty.
        out["mean"] = avg["mean"]
        out["sd"] = math.sqrt(E["poll_state_sd"] ** 2 + E["single_poll_sd"] ** 2 / avg["n_eff"]
                              + (E["per_undecided"] * avg["undecided"]) ** 2 + E["independent_extra_sd"] ** 2)
        out["prior_weight"], out["basis"] = 0.0, "polls"
    elif out["prior"] is not None:
        out["mean"], out["sd"], out["prior_weight"], out["basis"] = out["prior"], fsd, 1.0, "fundamentals"
    else:
        raise SystemExit(f"{d}: no baseline and no polls")
    return out


def simulate(ds, shift=0.0, n=P["sims"], seed=2026):
    rng = np.random.default_rng(seed)
    df = E["t_df"]
    scale = math.sqrt((df - 2) / df)  # unit-variance t
    live = [x for x in ds if x["fixed"] is None]
    fixed_d = sum(1 for x in ds if x["fixed"] == "D")
    mean = np.array([x["mean"] for x in live])
    sd = np.array([x["sd"] for x in live])
    regions = sorted(REGION)
    ridx = np.array([regions.index(REGION_OF[x["state"]]) for x in live])
    nat = rng.standard_t(df, n) * scale * E["national_sd"] + shift
    reg = rng.standard_t(df, (n, len(regions))) * scale * E["regional_sd"]
    loc = rng.standard_t(df, (n, len(live))) * scale * sd
    margins = mean + nat[:, None] + reg[:, ridx] + loc
    dwin = margins > 0
    is_d = np.array([x["ch_party"] == "D" for x in live])
    seats = dwin[:, is_d].sum(axis=1) + fixed_d  # an independent challenger's win is not a Democratic seat
    probs = dict(zip([x["district"] for x in live], dwin.mean(axis=0)))
    for x in ds:
        if x["fixed"]:
            probs[x["district"]] = 1.0 if x["fixed"] == "D" else 0.0
    return probs, seats


def main():
    ds = [district(r) for r in data]
    probs, seats = simulate(ds)
    hist = np.bincount(seats, minlength=436)
    dist = {int(k): float(v / len(seats)) for k, v in enumerate(hist) if v}
    scen = []
    for sc in P["scenarios"]:
        _, s2 = simulate(ds, shift=sc["shift"], n=P["scenario_sims"])
        leaders = sum(1 for x in ds if (x["fixed"] == "D") or (x["fixed"] is None and x["ch_party"] == "D" and x["mean"] + sc["shift"] > 0))
        scen.append({"label": sc["label"], "shift": sc["shift"], "leaders_D": leaders,
                     "p_D": float((s2 >= MAJORITY).mean()), "median_D": float(np.median(s2))})
    races = []
    for x in ds:
        p = float(probs[x["district"]])
        a = x["avg"]
        races.append({
            "district": x["district"], "state": x["state"], "incumbent": x["incumbent"], "inc_party": x["inc_party"],
            "inc_running": x["inc_running"], "ch_party": x["ch_party"], "override": x["override"], "dem": x["dem"], "rep": x["rep"], "dn": x.get("dn"), "rn": x.get("rn"),
            "pres": x["pres"], "pres_src": x["pres_src"], "audited": x["audited"], "fixed": x["fixed"],
            "prior": None if x["prior"] is None else round(x["prior"], 1),
            "inc_term": round(x.get("inc_term") or 0, 1), "overperf": x.get("overperf"),
            "new_territory": x.get("new_territory"), "elastic": x.get("elastic"),
            "poll_avg": round(a["mean"], 1) if a else None, "poll_avg_raw": round(a["raw_mean"], 1) if a else None,
            "n_polls": a["n_polls"] if a else 0, "n_eff": round(a["n_eff"], 1) if a else 0,
            "undecided": round(a["undecided"], 1) if a else None,
            "mean": None if x["fixed"] else round(x["mean"], 1),
            "sd": None if x["fixed"] else round(math.sqrt(x["sd"] ** 2 + E["national_sd"] ** 2 + E["regional_sd"] ** 2), 1),
            "prior_weight": None if x["fixed"] else round(x["prior_weight"], 3), "basis": x.get("basis", "ballot"),
            "p_dem": p, "tier": "Certain" if x["fixed"] else lib.tier(p, P["tiers"]),
            # Inputs for the in-page scenario simulator (house_sim.js): unrounded mean, district-only SD, region.
            "sim": None if x["fixed"] else {"mean": round(x["mean"], 3), "sd": round(x["sd"], 3), "region": REGION_OF[x["state"]]},
            "polls": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()} for row in (a["polls"] if a else [])],
        })
    exp = float(seats.mean())
    out = {"as_of": P["as_of"], "params": P, "races": races, "seat_dist_d": dist,
           "p_dem_control": float((seats >= MAJORITY).mean()), "expected_d": exp,
           "pct": {q: int(np.percentile(seats, q)) for q in (5, 10, 50, 90, 95)}, "scenarios": scen}
    (HERE / "house_model.json").write_text(json.dumps(out, indent=1))
    print(f"P(D control) {out['p_dem_control']:.1%}; expected D {exp:.1f}; 80% {out['pct'][10]}-{out['pct'][90]}")
    for s in scen:
        print(f"  {s['label']}: leaders D {s['leaders_D']}, P(D) {s['p_D']:.0%}")


if __name__ == "__main__":
    main()
