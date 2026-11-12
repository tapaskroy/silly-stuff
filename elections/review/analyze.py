#!/usr/bin/env python3
"""Gather everything the upset review (review.html) needs into review/analysis.json.

Inputs:
  frozen/                      the Nov 3 forecast (models, polls, the mid-October ratings stored with them)
  results.json                 AP calls (the scorecard's file)
  review/ap_count.json         AP's current count for every race (results.json keeps a margin only once 95% is in)
  review/national_vote.json    AP's national House vote
  review/national_polls.json   the final national generic-ballot polls
  review/research/             final_ratings.json (Cook, Sabato, Inside Elections, last update before Nov 3),
                               quant_senate_gov.json and quant_house.json (other models and prediction markets),
                               upsets_*.json (reporting on each upset, with sources)
Usage: python3 review/analyze.py
"""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

RV = Path(__file__).parent
HERE = RV.parent
F = HERE / "frozen"
load = lambda p: json.loads(Path(p).read_text())
opt = lambda p: load(p) if Path(p).exists() else {}

sen, hou, gov = load(F / "senate_model.json"), load(F / "house_model.json"), load(F / "gov_model.json")
sp, gp, hp = load(F / "senate_polls.json"), load(F / "gov_polls.json"), load(F / "house_polls.json")
hdata = {d["district"]: d for d in load(F / "house_data.json")}
RES = load(HERE / "results.json")
COUNT = load(RV / "ap_count.json")
NAT = load(RV / "national_vote.json")
NPOLLS = load(RV / "national_polls.json")
FINAL = load(RV / "research" / "final_ratings.json")
QSG = opt(RV / "research" / "quant_senate_gov.json")
QH = opt(RV / "research" / "quant_house.json")
UPS = {}
for f in sorted((RV / "research").glob("upsets_*.json")):
    UPS.update(load(f))
CHS = ("senate", "house", "governors")
WINDOW = "2026-08-01"
RATERS = {"cook": "Cook Political Report", "sabato": "Sabato's Crystal Ball", "inside": "Inside Elections"}
MARKETS = {"polymarket": "Polymarket", "kalshi": "Kalshi"}


def races():
    out = []
    for r in sen["races"]:
        out.append(dict(ch="senate", key=r["state"], a=r["challenger"], ap=r["challenger_party"], b=r["rep"], bp="R", p=r["p_challenger"],
                        mean=r["mean"], poll=r.get("poll_avg"), prior=r.get("prior"), prior_weight=r.get("prior_weight"), tier=r["tier"],
                        mid=sp[r["state"]].get("ratings") or {}, polls=sp[r["state"]].get("polls") or [],
                        pres=sp[r["state"]].get("fundamentals", {}).get("pres_2024_margin_D")))
    for r in hou["races"]:
        if r.get("fixed"):
            continue
        out.append(dict(ch="house", key=r["district"], a=r["dn"], ap=r["ch_party"], b=r["rn"], bp="R", p=r["p_dem"], mean=r["mean"],
                        poll=r.get("poll_avg"), prior=r.get("prior"), prior_weight=r.get("prior_weight"), tier=r["tier"],
                        mid=hdata[r["district"]].get("ratings") or {}, polls=(hp.get(r["district"]) or {}).get("polls") or [], pres=r.get("pres"),
                        names=(re.sub(r"\s*\(.*?\)", "", r.get("dem") or ""), re.sub(r"\s*\(.*?\)", "", r.get("rep") or "")),
                        inc=r.get("inc_party") if r.get("inc_running") else "open"))
    for r in gov["races"]:
        out.append(dict(ch="governors", key=r["state"], a=r["challenger"], ap=r["challenger_party"], b=r["rep"], bp=r["opponent_party"],
                        p=r["p_challenger"], mean=r["mean"], poll=r.get("poll_avg"), prior=r.get("prior"), prior_weight=r.get("prior_weight"),
                        tier=r["tier"], mid=gp[r["state"]].get("ratings") or {}, polls=gp[r["state"]].get("polls") or [],
                        pres=gp[r["state"]].get("fundamentals", {}).get("pres_2024_margin_D")))
    for r in out:
        x = RES[r["ch"]].get(r["key"]) or {}
        r["winner"] = x.get("winner") if x.get("status") == "called" else None
        r["winner_name"] = x.get("winner_name") or r["winner"]
        # +1 when the first-listed candidate is the Democratic side (or the non-Republican one in an independent-vs-R race)
        r["sign"] = 1 if r["ap"] == "D" or r["bp"] == "R" else -1
        r["p_d"] = r["p"] if r["sign"] == 1 else 1 - r["p"]  # our chance for the Democratic (or non-Republican) side
        r["d_won"] = None if not r["winner"] else (r["winner"] == r["a"]) == (r["sign"] == 1)
        r["upset"] = r["d_won"] is not None and (r["p_d"] >= .5) != r["d_won"]
        r["p_winner"] = None if r["d_won"] is None else (r["p_d"] if r["d_won"] else 1 - r["p_d"])
        c = COUNT[r["ch"]].get(r["key"]) or {}
        r["count_margin"] = c.get("margin")                    # first-listed minus second-listed, AP's current count
        r["counted"] = int(float(c["note"])) if str(c.get("note") or "").replace(".", "", 1).isdigit() else None  # % of expected vote in
        r["d_margin"] = None if r["count_margin"] is None else r["count_margin"] * r["sign"]
        r["d_mean"] = r["mean"] * r["sign"]
        r["err"] = None if r["d_margin"] is None else r["d_margin"] - r["d_mean"]
        r["final"] = (FINAL.get(r["ch"]) or {}).get(r["key"]) or {}
    return out


def rating_side(s):
    m = re.match(r"\s*(Safe|Solid|Likely|Lean|Leans|Tilt|Tilts)\s+([DRI])\b", s or "")
    return None if not m else ("R" if m.group(2) == "R" else "D")


def rating_strength(s):
    m = re.match(r"\s*(Safe|Solid|Likely|Lean|Leans|Tilt|Tilts)", s or "")
    return None if not m else {"Safe": 3, "Solid": 3, "Likely": 2, "Lean": 1, "Leans": 1, "Tilt": 0, "Tilts": 0}[m.group(1)]


def final_rating(r, rater):
    """The rater's last pre-election rating; seats left off the research list (safe for everyone) keep the stored rating."""
    return r["final"].get(rater) or r["mid"].get(rater)


def quant(ch):
    if ch == "house":
        return QH.get("house") or {}, QH.get("forecasters") or {}
    return QSG.get(ch) or {}, QSG.get("forecasters") or {}


def model_p(entry):
    """(chance for the Democratic side or None, favored side 'D'/'R' or None) from one forecaster's entry."""
    if not isinstance(entry, dict):
        return None, None
    p = entry.get("p_dem")
    if p is not None:
        return p, ("D" if p > .5 else "R" if p < .5 else None)
    side = entry.get("favored")
    return None, ("D" if side in ("D", "I") else "R" if side == "R" else None)


R = races()
BY = {ch: [r for r in R if r["ch"] == ch] for ch in CHS}
CALLED = {ch: [r for r in BY[ch] if r["d_won"] is not None] for ch in CHS}


def ours_entry(rs):
    right = sum(not r["upset"] for r in rs)
    return dict(right=right, wrong=len(rs) - right, nocall=0, n=len(rs), brier=round(st.mean((r["p_d"] - r["d_won"]) ** 2 for r in rs), 4))


def board(ch):
    """Every source scored on the called races it covered: right, wrong, no call (toss-up or 50%), Brier where it gave odds,
    and our own score on exactly the same races for a fair comparison."""
    rs = CALLED[ch]
    rows = [dict(id="ours", name="This forecast", kind="model", covered="all", upsets_caught=[], **ours_entry(rs))]
    for k, name in RATERS.items():
        right = wrong = nocall = 0
        caught, missed = [], []
        for r in rs:
            s = rating_side(final_rating(r, k))
            if s is None:
                nocall += 1
            elif (s == "D") == r["d_won"]:
                right += 1
                if r["upset"]:
                    caught.append(r["key"])
            else:
                wrong += 1
                missed.append(r["key"])
        rows.append(dict(id=k, name=RATERS[k], kind="rater", covered="all", right=right, wrong=wrong, nocall=nocall, n=len(rs),
                         brier=None, upsets_caught=caught, wrong_races=missed,
                         date=(FINAL.get("sources", {}).get(k) or {}).get("date")))
    data, names = quant(ch)
    ids = sorted({f for v in data.values() if isinstance(v, dict) for f in v if not f.startswith("_")})
    for f in ids:
        right = wrong = nocall = 0
        caught, missed, sq, sq_ours = [], [], [], []
        for r in rs:
            p, side = model_p((data.get(r["key"]) or {}).get(f))
            if p is None and side is None:
                continue
            if side is None:
                nocall += 1
            elif (side == "D") == r["d_won"]:
                right += 1
                if r["upset"]:
                    caught.append(r["key"])
            else:
                wrong += 1
                missed.append(r["key"])
            if p is not None:
                sq.append((p - r["d_won"]) ** 2)
                sq_ours.append((r["p_d"] - r["d_won"]) ** 2)
        n = right + wrong + nocall
        if not n:
            continue
        covered = [r for r in rs if model_p((data.get(r["key"]) or {}).get(f)) != (None, None)]
        ours_same = sum(not r["upset"] for r in covered)
        meta = names.get(f) or {}
        rows.append(dict(id=f, name=meta.get("name") or f, kind="market" if f in MARKETS else "model", covered=n, right=right, wrong=wrong,
                         nocall=nocall, n=n, brier=round(st.mean(sq), 4) if sq else None, brier_ours_same=round(st.mean(sq_ours), 4) if sq_ours else None,
                         n_brier=len(sq), right_ours_same=ours_same, upsets_caught=caught, wrong_races=missed, date=meta.get("final_date"), verified=meta.get("verified")))
    # national generic-ballot polls applied as a uniform swing from each seat's 2024 presidential margin
    for p in NPOLLS["polls"]:
        swing = p["d_margin"] - NPOLLS["nat_pres_2024"]
        right, caught = 0, []
        for r in rs:
            d = (r["pres"] + swing > 0) if r["pres"] is not None else r["p_d"] >= .5
            right += d == r["d_won"]
            if r["upset"] and d == r["d_won"]:
                caught.append(r["key"])
        rows.append(dict(id="nat:" + p["pollster"], name=f"{p['pollster']} national poll (D+{p['d_margin']:g}), uniform swing", kind="national_poll",
                         covered="all", right=right, wrong=len(rs) - right, nocall=0, n=len(rs), brier=None, upsets_caught=caught))
    # the plain polling average in each polled race
    polled = [r for r in rs if r["poll"]]
    right = sum((r["poll"] * r["sign"] > 0) == r["d_won"] for r in polled)
    rows.append(dict(id="pollavg", name="Polling-average leader (polled races only)", kind="polls", covered=len(polled), right=right,
                     wrong=len(polled) - right, nocall=0, n=len(polled), brier=None,
                     upsets_caught=[r["key"] for r in polled if r["upset"] and (r["poll"] * r["sign"] > 0) == r["d_won"]]))
    return rows


def close_board(ch):
    """The races we called too close (20-80%): who made a call in them, how often it was right, and how bold it was."""
    rs = [r for r in CALLED[ch] if .2 <= r["p_d"] <= .8]
    out = {"n": len(rs), "races": [r["key"] for r in rs], "sources": []}
    def add(name, kind, picks):
        """picks: list of (race, side or None, confident bool)"""
        if not picks:
            return
        calls = [(r, s, c) for r, s, c in picks if s]
        out["sources"].append(dict(name=name, kind=kind, covered=len(picks), calls=len(calls),
                                   right=sum((s == "D") == r["d_won"] for r, s, c in calls),
                                   confident=sum(c for r, s, c in calls),
                                   confident_right=sum(c and (s == "D") == r["d_won"] for r, s, c in calls),
                                   nocall=len(picks) - len(calls)))
    add("This forecast", "model", [(r, "D" if r["p_d"] >= .5 else "R", abs(r["p_d"] - .5) >= .2) for r in rs])
    for k, name in RATERS.items():
        add(name, "rater", [(r, rating_side(final_rating(r, k)), (rating_strength(final_rating(r, k)) or 0) >= 2) for r in rs])
    data, names = quant(ch)
    ids = sorted({f for v in data.values() if isinstance(v, dict) for f in v if not f.startswith("_")})
    for f in ids:
        picks = []
        for r in rs:
            p, side = model_p((data.get(r["key"]) or {}).get(f))
            if p is None and side is None:
                continue
            picks.append((r, side, p is not None and abs(p - .5) >= .2))
        add((names.get(f) or {}).get("name") or f, "market" if f in MARKETS else "model", picks)
    return out


def poll_margin(r, p):
    res = p.get("results") or {}
    return res[r["a"]] - res[r["b"]] if r["a"] in res and r["b"] in res else None


def describe(p):
    t = p["pollster"]
    if p.get("partisan"):
        t += f" ({p['partisan']} internal" + (f", for {p['sponsor']}" if p.get("sponsor") else "") + ")"
    elif p.get("lean"):
        t += f" ({p['lean']}-leaning firm)"
    elif p.get("sponsor"):
        t += f" for {p['sponsor']}"
    return t


def upset_detail(r):
    """Everything the appendix says about one upset."""
    win_d = r["d_won"]
    polls = []
    for p in r["polls"]:
        if (p.get("end") or "") < WINDOW:
            continue
        m = poll_margin(r, p)
        if m is None:
            continue
        w = m * r["sign"] * (1 if win_d else -1)  # the winner's lead in this poll
        polls.append(dict(pollster=describe(p), end=p["end"], winner_lead=round(w, 1), partisan=p.get("partisan"), lean=p.get("lean"),
                          url=p.get("source_url"), verified=p.get("verified")))
    polls.sort(key=lambda x: x["end"], reverse=True)
    wsign = 1 if win_d else -1
    data, names = quant(r["ch"])
    models = []
    for f, e in (data.get(r["key"]) or {}).items():
        if f.startswith("_"):
            continue
        p, side = model_p(e)
        if p is None and side is None:
            continue
        models.append(dict(id=f, name=(names.get(f) or {}).get("name") or f, market=f in MARKETS,
                           p_winner=None if p is None else round(p if win_d else 1 - p, 3), right=side is not None and (side == "D") == win_d,
                           band=e.get("p_dem_band_from_chart") if isinstance(e, dict) else None))
    research = UPS.get(r["key"]) or {}
    return dict(ch=r["ch"], key=r["key"], winner=r["winner_name"], winner_party=r["ap"] if r["winner"] == r["a"] else r["bp"],
                loser=r["b"] if r["winner"] == r["a"] else r["a"], names=r.get("names"),
                p_winner=round(r["p_winner"], 3), tier=r["tier"], forecast_margin_winner=round(r["d_mean"] * wsign, 1),
                actual_margin_winner=None if r["d_margin"] is None else round(r["d_margin"] * wsign, 1), counted=r["counted"],
                poll_avg_winner=None if not r["poll"] else round(r["poll"] * r["sign"] * wsign, 1),
                prior_winner=None if r["prior"] is None else round(r["prior"] * r["sign"] * wsign, 1),
                prior_weight=None if r["prior_weight"] is None else round(r["prior_weight"], 2),
                pres_2024_winner=None if r["pres"] is None else round(r["pres"] * wsign, 1),
                ratings={k: final_rating(r, k) for k in RATERS}, ratings_mid_oct={k: r["mid"].get(k) for k in RATERS},
                models=sorted(models, key=lambda m: (not m["right"], m["market"], m["name"])), polls=polls,
                research=research)


def pollster_board():
    """Each pollster's latest in-window poll per called race: did it have the winner ahead, its average miss, and the upsets."""
    stat = defaultdict(lambda: dict(races=0, right=0, ties=0, errs=[], ups=[], partisan=Counter()))
    for r in R:
        if r["d_won"] is None:
            continue
        latest = {}
        for p in r["polls"]:
            if (p.get("end") or "") < WINDOW or poll_margin(r, p) is None:
                continue
            k = re.sub(r"^(New York Times/Siena|Siena College|Siena University|The New York Times/Siena College)$", "NYT/Siena", p["pollster"].strip())
            if k not in latest or p["end"] > latest[k]["end"]:
                latest[k] = p
        for k, p in latest.items():
            m = poll_margin(r, p) * r["sign"]  # D minus R
            s = stat[k]
            s["races"] += 1
            if m == 0:
                s["ties"] += 1
            elif (m > 0) == r["d_won"]:
                s["right"] += 1
            if r["d_margin"] is not None:
                s["errs"].append(r["d_margin"] - m)
            s["partisan"][p.get("partisan") or (p.get("lean") and p["lean"] + "-lean") or "none"] += 1
            if r["upset"]:
                s["ups"].append(dict(race=r["key"], ok=m != 0 and (m > 0) == r["d_won"], tie=m == 0))
    rows = []
    for k, s in stat.items():
        rows.append(dict(pollster=k, races=s["races"], right=s["right"], ties=s["ties"],
                         bias_d=round(st.mean(s["errs"]), 1) if s["errs"] else None, mae=round(st.mean(map(abs, s["errs"])), 1) if s["errs"] else None,
                         upsets_polled=len(s["ups"]), upsets_right=sum(u["ok"] for u in s["ups"]), upsets=s["ups"],
                         mostly=s["partisan"].most_common(1)[0][0]))
    rows.sort(key=lambda x: (-x["upsets_right"], -x["right"]))
    return rows


def national():
    actual = round(NAT["dem_pct"] - NAT["rep_pct"], 1)
    rows = []
    for p in NPOLLS["polls"]:
        swing = p["d_margin"] - NPOLLS["nat_pres_2024"]
        d_seats = sum((r["pres"] + swing > 0) if r["pres"] is not None else r["p_d"] >= .5 for r in CALLED["house"])
        right = sum(((r["pres"] + swing > 0) if r["pres"] is not None else r["p_d"] >= .5) == r["d_won"] for r in CALLED["house"])
        ups = [r["key"] for r in CALLED["house"] if r["upset"] and r["pres"] is not None and (r["pres"] + swing > 0) == r["d_won"]]
        rows.append(dict(pollster=p["pollster"], d_margin=p["d_margin"], error=round(actual - p["d_margin"], 1), house_right=right, upsets_caught=ups,
                         house_d=d_seats))
    rows.sort(key=lambda x: abs(x["error"]))  # closest to the result first
    return dict(actual=actual, eevp=NAT["eevp"], average=NPOLLS["average"], model_input=NPOLLS["model_input"], polls=rows,
                closer_than_input=sum(abs(x["error"]) < abs(actual - NPOLLS["model_input"]) for x in rows))


def errors():
    """Signed margin errors (+ = Democrats did better than forecast) on AP's current count, by group."""
    def grp(rs, key):
        d = defaultdict(list)
        for r in rs:
            if r["err"] is not None and key(r) is not None:
                d[key(r)].append(r["err"])
        return {k: dict(n=len(v), mean=round(st.mean(v), 1), sd=round(st.pstdev(v), 1)) for k, v in d.items()}
    bins = lambda r: None if r["pres"] is None else ("Trump +20 or more" if r["pres"] < -20 else "Trump +10 to 20" if r["pres"] < -10 else
                                                    "Trump +0 to 10" if r["pres"] < 0 else "Harris +0 to 10" if r["pres"] < 10 else "Harris +10 or more")
    out = {}
    for ch in CHS:
        rs = CALLED[ch]
        e = [r["err"] for r in rs if r["err"] is not None]
        out[ch] = dict(n=len(e), mean=round(st.mean(e), 1), mae=round(st.mean(map(abs, e)), 1), d_better=sum(x > 0 for x in e),
                       by_pres=grp(rs, bins), by_tier=grp(rs, lambda r: r["tier"]))
    comp = [r for r in CALLED["house"] if r["tier"] != "Safe"]
    states = grp(comp, lambda r: r["key"].split("-")[0])
    out["house"]["competitive_by_state"] = {k: v for k, v in sorted(states.items(), key=lambda kv: -kv[1]["mean"]) if v["n"] >= 3}
    out["house"]["competitive_by_inc"] = grp(comp, lambda r: r["inc"])
    out["house"]["competitive_polled"] = grp(comp, lambda r: "polled" if r["poll"] else "no polls")
    return out


def summary(ch):
    rs = CALLED[ch]
    close = [r for r in rs if .2 <= r["p_d"] <= .8]
    fav = Counter(("D" if r["p_d"] >= .5 else "R", "D" if r["d_won"] else "R") for r in close)
    return dict(n=len(BY[ch]), called=len(rs), right=sum(not r["upset"] for r in rs), upsets=[r["key"] for r in rs if r["upset"]],
                expected_upsets=round(sum(min(r["p_d"], 1 - r["p_d"]) for r in rs), 1),
                upsets_by_winner=dict(Counter("D" if r["d_won"] else "R" for r in rs if r["upset"])),
                close_n=len(close), close_right=sum(not r["upset"] for r in close), close_expected=round(sum(max(r["p_d"], 1 - r["p_d"]) for r in close), 1),
                close_fav=[dict(fav=f, won=w, n=n) for (f, w), n in sorted(fav.items())],
                uncalled=[r["key"] for r in BY[ch] if r["d_won"] is None],
                calibration=[dict(lo=lo, hi=hi, n=len(b), expected=round(sum(max(r["p_d"], 1 - r["p_d"]) for r in b), 1), won=sum(not r["upset"] for r in b))
                             for lo, hi in ((.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, .99), (.99, 1.01))
                             for b in [[r for r in rs if lo <= max(r["p_d"], 1 - r["p_d"]) < hi]]])


def seats():
    """Democratic (and independent) seats won so far, holdovers and pre-decided seats included, and our frozen control odds."""
    hold = sen["params"]["holdover"]
    sd = hold["D"] + sum(1 for r in CALLED["senate"] if r["d_won"])
    hd = sum(1 for r in hou["races"] if r.get("fixed") == "D") + sum(1 for r in CALLED["house"] if r["d_won"])
    dist = {int(k): v for k, v in sen["seat_dist_d_plus_i"].items()}
    cum, med = 0, None
    for k in sorted(dist):
        cum += dist[k]
        if med is None and cum >= .5:
            med = k
    return dict(senate_d=sd, senate_open=len(BY["senate"]) - len(CALLED["senate"]), house_d=hd, house_open=len(BY["house"]) - len(CALLED["house"]),
                ours=dict(senate_p_dem=sen["control"]["separate"]["D"], senate_median_dem=med, house_p_dem=hou["p_dem_control"], house_median_dem=hou["pct"]["50"]))


out = dict(as_of=RES.get("_updated"), seats=seats(), national=national(), errors=errors(), pollsters=pollster_board(),
           control={k: v for k, v in (QSG.get("control") or {}).items()}, quant_forecasters={**(QSG.get("forecasters") or {}), **{f"house:{k}": v for k, v in (QH.get("forecasters") or {}).items()}},
           rater_sources=FINAL.get("sources"), rater_summary=FINAL.get("summary"), rater_chamber=FINAL.get("chamber_calls") or FINAL.get("chamber"))
for ch in CHS:
    out[ch] = dict(summary=summary(ch), board=board(ch), close=close_board(ch),
                   upsets=[upset_detail(r) for r in sorted(CALLED[ch], key=lambda r: r["p_winner"]) if r["upset"]])
(RV / "analysis.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
for ch in CHS:
    s = out[ch]["summary"]
    print(f"{ch}: {s['right']}/{s['called']} right, {len(s['upsets'])} upsets (expected {s['expected_upsets']}), close {s['close_right']}/{s['close_n']}")
