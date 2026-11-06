#!/usr/bin/env python3
"""Build house.html from the model output (house_model.json), the audited district records (house_polls.json),
background research (house_data.json) and national context (house_meta.json). Run house_model.py first."""
import html
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
CONFIDENT_MARGIN = 6.0  # a swing above this is called without a deep dive (was 10 in the original rule)
CM = f"{CONFIDENT_MARGIN:g}"
MAJORITY = 218

model = json.loads((HERE / "house_model.json").read_text())
audit = json.loads((HERE / "house_polls.json").read_text())
research = {r["district"]: r for r in json.loads((HERE / "house_data.json").read_text())}
meta = json.loads((HERE / "house_meta.json").read_text())
v1 = json.loads((HERE / "house_calls_v1.json").read_text())
P = model["params"]

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def dist_sort(d):
    st, num = d.split("-")
    return (STATE_NAMES[st], int(num) if num.isdigit() else 0)


def signed(m):
    if m is None:
        return "—"
    if abs(m) < 0.05:
        return "Even"
    return f"D +{m:.1f}" if m > 0 else f"R +{-m:.1f}"


def pct(p):
    if p >= 0.995:
        return ">99%"
    if p <= 0.005:
        return "<1%"
    return f"{p:.0%}"

def fav(r):
    """Party and chance of whichever side the model favors: race chances are always quoted for the leader."""
    p = r["p_dem"]
    return (("D " if r["ch_party"] == "D" else "Ind. ") + pct(p)) if p >= 0.5 else "R " + pct(1 - p)



def link(url, text):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>' if url else esc(text)


def clean(name):
    return re.sub(r"\s*\(inc\.\)", "", str(name or "—"))


# ---- headline numbers and chart ---------------------------------------------------------------------
dist = {int(k): v for k, v in model["seat_dist_d"].items()}
pD = model["p_dem_control"]
pc = model["pct"]
lo, hi = pc["5"], pc["95"]
W_, H_, PL, PB, PT = 760, 220, 36, 34, 14
# Bin seats in 3s so bars stay readable; the bin containing 218 is split so control is never ambiguous.
bins = []
k = lo - (lo - MAJORITY) % 3
while k <= hi:
    bins.append((k, k + 2))
    k += 3
bw = (W_ - PL - 8) / len(bins)
vals = [sum(dist.get(s, 0) for s in range(a, b + 1)) for a, b in bins]
ymax = max(vals) or 1
bars, ticks = [], []
for i, ((a, b), v) in enumerate(zip(bins, vals)):
    h = (H_ - PB - PT) * v / ymax
    x = PL + i * bw
    side = "dem" if a >= MAJORITY else "rep"
    tip = f"{a}–{b} D seats · {v:.1%} of simulations · {'Democratic' if a >= MAJORITY else 'Republican'} majority"
    bars.append(f'<rect class="bar {side}" x="{x + 1:.1f}" y="{H_ - PB - h:.1f}" width="{bw - 2:.1f}" height="{max(h, 0):.1f}" rx="2"></rect>'
                f'<rect class="hit" x="{x:.1f}" y="{PT}" width="{bw:.1f}" height="{H_ - PB - PT}" data-tip="{esc(tip)}"></rect>')
    if i % 2 == 0:
        ticks.append(f'<text x="{x + bw / 2:.1f}" y="{H_ - PB + 16}" text-anchor="middle">{a}</text>')
xm = PL + next(i for i, (a, b) in enumerate(bins) if a >= MAJORITY) * bw
chart = f"""<svg viewBox="0 0 {W_} {H_}" role="img" aria-label="Distribution of Democratic House seats across {P['sims']:,} simulations">
  {''.join(ticks)}<line class="axis" x1="{PL}" x2="{W_ - 8}" y1="{H_ - PB}" y2="{H_ - PB}"></line>
  {''.join(bars)}<line class="majority" x1="{xm:.1f}" x2="{xm:.1f}" y1="{PT - 6}" y2="{H_ - PB}"></line>
  <text class="lbl" x="{xm + 4:.1f}" y="{PT + 4}">218 = majority</text>
  <text x="{(W_ + PL) / 2:.0f}" y="{H_ - 2}" text-anchor="middle">Democratic seats (bins of 3)</text></svg>"""
sc_rows = "".join(f"<tr><td>{esc(s['label'])}</td><td class='num'>{s['leaders_D']}–{435 - s['leaders_D']}</td>"
                  f"<td class='num'>{s['median_D']:.0f}</td><td class='num'>{pct(s['p_D'])}</td></tr>" for s in model["scenarios"])

# ---- per-district rows, grouped by state --------------------------------------------------------------
races = model["races"]
by_state = defaultdict(list)
for r in races:
    by_state[r["state"]].append(r)
tot = {"D": 0, "R": 0, "I": 0}
flips = {"D": [], "R": [], "I": []}
changes, tiers = [], defaultdict(lambda: {"D": 0, "R": 0, "I": 0})
sections, nav = [], []
for st in sorted(by_state, key=lambda s: STATE_NAMES[s]):
    rows, st_tot, st_exp = [], {"D": 0, "R": 0, "I": 0}, 0.0
    for r in sorted(by_state[st], key=lambda r: dist_sort(r["district"])):
        d = r["district"]
        a, res = audit.get(d, {}), research[d]
        p = r["p_dem"]
        st_exp += p if r["ch_party"] == "D" else 0
        lead = r["fixed"] or (r["ch_party"] if r["mean"] > 0 else "R")
        tot[lead] += 1
        st_tot[lead] += 1
        tiers[r["tier"]][lead] += 1
        inc_p = r["inc_party"] if r["incumbent"] and "vacant" not in str(r["incumbent"]).lower() else None
        flip = inc_p in ("D", "R", "I") and inc_p != lead
        if flip:
            flips[lead].append(d)
        old = v1.get(d, {})
        if old.get("party") and old["party"] != lead:
            changes.append((d, old, lead, p if lead == "D" else 1 - p))
        swing = abs(r["poll_avg"]) if r["poll_avg"] is not None else (abs(r["pres"]) if r["pres"] is not None else 99)
        rule = "confident" if swing > CONFIDENT_MARGIN else "deep"
        close = r["tier"] in ("Toss-up", "Tilt", "Lean")
        win_p = p if lead != "R" else 1 - p
        leader = clean(r["dem"] if lead != "R" else r["rep"])
        cls = {"D": "dem", "R": "rep", "I": "ind"}[lead]
        redrawn = ' <span class="pill">new lines</span>' if res["baseline"].get("redistricted") else ""
        basis = f"2024 pres {signed(r['pres'])}" + (f" · {r['n_polls']} poll{'s' if r['n_polls'] > 1 else ''}" if r["n_polls"] else "")
        if r["fixed"]:
            basis = "Decided by the ballot (one party absent or same-party race)"
        pbar = ("" if r["fixed"] else
                f"<div class='pbar'><i class='dem' style='width:{p * 100:.1f}%'></i><i class='rep' style='width:{(1 - p) * 100:.1f}%'></i></div>")
        flip_tag = ' <span class="flip">FLIP</span>' if flip else ""
        rowcls = f"race {rule}{' flipped' if flip else ''}{' close' if close else ''}{' changed' if old.get('party') and old['party'] != lead else ''}"
        rows.append(f"""
      <tr class="{rowcls}">
        <td class="st">{esc(d)}{redrawn}</td>
        <td>{esc(r['incumbent'])}<span class="sub">{'' if r['inc_running'] else 'Open seat'}</span></td>
        <td class="dem">{esc(clean(r['dem']))}</td>
        <td class="rep">{esc(clean(r['rep']))}</td>
        <td class="poll">{esc(basis)}</td>
        <td class="num">{esc(signed(r['poll_avg']))}</td>
        <td class="num">{'' if r['fixed'] else esc(signed(r['mean']))}<span class="sub">{'' if r['fixed'] else '± ' + format(r['sd'], 'g')}</span></td>
        <td>{pbar}<span class="sub">{'' if r['fixed'] else fav(r)}</span></td>
        <td><span class="tag {rule}">{'Swing &gt; ' + CM if rule == 'confident' else 'Deep dive'}</span></td>
        <td class="win {cls}">{esc(r['tier'])} {esc(lead)}{flip_tag}<span class="sub">{esc(leader)}{'' if r['fixed'] else ' · ' + pct(win_p)}</span></td>
      </tr>""")
        if r["fixed"] or (swing > 10 and not close and not r["n_polls"] and not a.get("corrections")):
            continue
        # Evidence row
        why = []
        if r["prior"] is not None:
            parts = [f"2024 presidential margin {signed(r['pres'])}",
                     f"national shift {(P['national_shift'] + P['generic_ballot_bias_adj']) * (r['elastic'] or 1):+.1f}"]
            if r["inc_term"]:
                if r["overperf"] is not None:
                    parts.append(f"incumbency {r['inc_term']:+.1f} (generic {P['incumbency_bonus']:g} plus {P['overperformance_shrink']:.0%} of the member's "
                                 f"{r['overperf']:+.1f} 2024 over/under-performance vs. the presidential margin, net of incumbency)")
                else:
                    parts.append(f"incumbency {r['inc_term']:+.1f}" + (" (halved: mostly new territory)" if r["new_territory"] else ""))
            why.append("Fundamentals: " + " + ".join(parts) + f" = <b>{esc(signed(r['prior']))}</b>.")
        if r["n_polls"]:
            why.append(f"{r['n_polls']} district poll{'s' if r['n_polls'] > 1 else ''} average <b>{esc(signed(r['poll_avg']))}</b>"
                       + (f" after removing sponsor lean (unadjusted {esc(signed(r['poll_avg_raw']))})" if r["poll_avg"] != r["poll_avg_raw"] else "")
                       + f"; the polls get {1 - r['prior_weight']:.0%} of the weight.")
        if r["override"]:
            why.append(esc(r["override"]))
        why.append(f"Forecast <b>{esc(signed(r['mean']))}</b>, total error SD {r['sd']:g} → {('Democrat' if r['ch_party'] == 'D' else 'Challenger') if p >= 0.5 else 'Republican'} wins {pct(max(p, 1 - p))} of simulations.")
        prow = []
        for q in sorted(r["polls"], key=lambda x: x["end"], reverse=True):
            tag = (f"<span class='tag {'dem' if q['partisan'] == 'D' else 'rep'}'>{q['partisan']}-sponsored</span>" if q.get("partisan")
                   else f"<span class='tag soft'>{q['lean']}-leaning</span>" if q.get("lean") else "")
            resv = ", ".join(f"{k_} {v:g}" for k_, v in q["results"].items() if isinstance(v, (int, float)))
            prow.append(f"<tr><td>{esc(q['end'])}</td><td>{link(q.get('url'), q['pollster'])}{' · ' + esc(q['sponsor']) if q.get('sponsor') else ''} {tag}</td>"
                        f"<td>{esc(q.get('n') or '?')} {esc(q.get('pop') or '')}</td><td>{esc(resv)}</td><td class='num'>{q['raw_margin']:+.1f}</td>"
                        f"<td class='num'>{(q['adj'] or 0):+.1f}</td><td class='num'>{q['share']:.0%}</td><td>{'✓' if q.get('verified') else '<span class=muted>table</span>'}</td></tr>")
        polltable = (f"<table class='inner'><thead><tr><th>Ended</th><th>Pollster</th><th>Sample</th><th>Result</th><th>Margin (D−R)</th><th>Adj.</th><th>Weight</th><th>Checked</th></tr></thead><tbody>{''.join(prow)}</tbody></table>"
                     if prow else "<p>No public district polls: the forecast is the fundamentals alone.</p>")
        corr = "".join(f"<li><b>{esc(c.get('field'))}</b>: was {esc(c.get('was'))} → {esc(c.get('now'))} <span class='sub'>{esc(c.get('source'))}</span></li>"
                       for c in a.get("corrections") or [])
        rt = a.get("ratings") or res.get("ratings") or {}
        h24 = a.get("house_2024") or {}
        prim = res.get("primaries") or {}
        issues = "".join(f"<li>{esc(i)}</li>" for i in res.get("issues") or [])
        rows.append(f"""
      <tr class="detail {rowcls}"><td colspan="10"><details><summary>Evidence: {esc(d)}</summary><div class="dd">
        <div class="wide"><h4>How the number is built</h4><p>{' '.join(why)}</p></div>
        <div class="wide"><h4>District polls</h4>{polltable}</div>
        <div><h4>Baseline</h4><p>2024 president on 2026 lines: {esc(signed(r['pres']))}<span class="sub">{esc(r['pres_src'])}</span></p>
          <p>2024 House (predecessor): {esc(h24.get('winner') or res['baseline'].get('house_2024'))}{' ' + signed(h24.get('margin_D')) if h24.get('margin_D') is not None else ''}
          {'' if not h24 else ('· comparable lines' if h24.get('comparable') else '· not comparable')}</p></div>
        <div><h4>Ratings</h4><p>Cook: {esc(rt.get('cook'))} · Sabato: {esc(rt.get('sabato'))} · Inside: {esc(rt.get('inside'))}</p><p class="sub">{esc(rt.get('as_of'))}</p>
          <p>{esc(res.get('status_note') or '')}</p></div>
        {'<div class="wide"><h4>Corrections from the audit</h4><ul>' + corr + '</ul></div>' if corr else ''}
        {('<div class="wide ctx"><h4>Context — not used in the forecast</h4><p><b>D primary:</b> ' + esc(prim.get('dem')) + '</p><p><b>R primary:</b> ' + esc(prim.get('rep')) + '</p>' + ('<ul>' + issues + '</ul>' if issues else '') + '</div>') if prim or issues else ''}
        {'<div class="wide"><h4>Earlier call (v1, judgment-based)</h4><p>' + esc(old.get('winner')) + ' (' + esc(old.get('party')) + ', ' + esc(old.get('confidence')) + ') — ' + esc(old.get('rationale')) + '</p></div>' if old else ''}
      </div></details></td></tr>""")
    name = STATE_NAMES[st]
    note = meta.get("state_notes", {}).get(st, "")
    n = len(by_state[st])
    nav.append(f'<option value="st-{st}">{esc(name)} ({n})</option>')
    sections.append(f"""
  <section id="st-{st}">
    <h2>{esc(name)} <span class="cnt">{n} seat{'s' if n > 1 else ''} · leaders <b class="d">D {st_tot['D']}</b> – <b class="r">R {st_tot['R']}</b> · expected D seats {math.floor(st_exp)}</span></h2>
    {f'<p class="snote">{esc(note)}</p>' if note else ''}
    <div class="wrap"><table class="main">
      <thead><tr><th>District</th><th>Incumbent</th><th>Democrat</th><th>Republican</th><th>Basis</th><th>Poll avg</th><th>Forecast</th><th>Win prob.</th><th>{CM}-pt rule</th><th>Rating</th></tr></thead>
      <tbody>{''.join(rows)}</tbody></table></div>
  </section>""")

net = tot["D"] - meta["pre"]["D"]
_sc = sorted(model["scenarios"], key=lambda s: s["shift"])
breakeven = next((abs(a["shift"] + (0.5 - a["p_D"]) * (b["shift"] - a["shift"]) / (b["p_D"] - a["p_D"]))
                  for a, b in zip(_sc, _sc[1:]) if a["p_D"] < 0.5 <= b["p_D"]), 6.0)
tier_rows = "".join(f"<tr><td>{t}</td><td class='num'>{tiers[t]['D']}</td><td class='num'>{tiers[t]['R']}</td></tr>"
                    for t in ("Certain", "Safe", "Likely", "Lean", "Tilt", "Toss-up") if tiers[t]["D"] + tiers[t]["R"])
d_solid = sum(tiers[t]["D"] for t in ("Certain", "Safe", "Likely", "Lean"))
chg = "".join(f"<li><b>{esc(d)}</b>: v1 {esc(o.get('winner'))} ({esc(o.get('party'))}, {esc(o.get('confidence'))}) → now {esc(l)} leads, {pct(w)}</li>"
              for d, o, l, w in sorted(changes, key=lambda c: dist_sort(c[0])))
audited = sum(1 for r in races if r["audited"])
n_polls = sum(r["n_polls"] for r in races)

# ---- scenario simulator (levers) ---------------------------------------------------------------------
E = P["error"]
assert E["t_df"] % 2 == 0, "house_sim.js draws chi-square for even df only"
TOO_CLOSE = (0.20, 0.80)  # districts whose model Democratic chance falls in this band get an outcome switch
live = [r for r in races if r["sim"]]
sim_regions = sorted({r["sim"]["region"] for r in live})
sim_data = {"n": 10000, "t_df": E["t_df"], "national_sd": E["national_sd"], "regional_sd": E["regional_sd"],
            "majority": MAJORITY, "regions": sim_regions, "fixed_d": sum(1 for r in races if r["fixed"] == "D"),
            "fixed_by_state": {st: sum(1 for r in rs if r["fixed"] == "D") for st, rs in by_state.items()},
            "seats_by_state": {st: len(rs) for st, rs in by_state.items()},
            "races": [{"d": r["district"], "st": r["state"], "chp": r["ch_party"], "mean": r["sim"]["mean"], "sd": r["sim"]["sd"],
                       "reg": sim_regions.index(r["sim"]["region"])} for r in live]}
sim_json = json.dumps(sim_data).replace("</", "<\\/")
sim_js = (HERE / "house_sim.js").read_text()


def short(name):
    return re.sub(r"\s*\([^)]*\)", "", str(name or "—")).strip()


too_close = [r for r in live if TOO_CLOSE[0] <= r["p_dem"] <= TOO_CLOSE[1]]
close_by_state = defaultdict(list)
for r in too_close:
    close_by_state[r["state"]].append(r)
state_blocks = []
for st in sorted(close_by_state, key=lambda s: STATE_NAMES[s]):
    rows_ = []
    for r in sorted(close_by_state[st], key=lambda r: dist_sort(r["district"])):
        dn, rn = short(r["dem"]), short(r["rep"])
        rows_.append(
            f"<div class='lrow' data-d='{esc(r['district'])}'>"
            f"<span class='lst'>{esc(r['district'])}<span class='sub'>{esc(r['tier'])} · model {fav(r)} · {esc(r['incumbent'] if r['inc_running'] else 'open seat')}</span></span>"
            f"<span class='lbar'><span class='pbar'><i class='ch dem'></i><i class='rp rep'></i></span><span class='sub lp'></span></span>"
            f"<span class='seg' role='group' aria-label='Outcome in {esc(r['district'])}'>"
            f"<button data-v='D' class='dem'>{esc(dn)} (D)</button><button data-v=''>Model</button>"
            f"<button data-v='R' class='rep'>{esc(rn)} (R)</button></span></div>")
    n = len(close_by_state[st])
    state_blocks.append(
        f"<details class='sblock' data-st='{st}'><summary><span class='sname'>{esc(STATE_NAMES[st])}</span>"
        f"<span class='sinfo'>{n} too close · <span class='sexp'></span> <span class='scalled'></span></span>"
        f"<span class='seg sseg' role='group' aria-label='All too-close districts in {esc(STATE_NAMES[st])}'>"
        f"<button data-v='D' class='dem'>All D</button><button data-v=''>Model</button><button data-v='R' class='rep'>All R</button></span>"
        f"</summary>{''.join(rows_)}</details>")
reg_levers = "".join(
    f"<label class='rlev'><span>{esc(g)}</span><input class='sim-reg' data-g='{i}' type='range' min='-6' max='6' step='0.5' value='0' "
    f"aria-label='{esc(g)} extra swing'><output>None</output></label>" for i, g in enumerate(sim_regions))

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 House Forecast</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1d1f; --muted:#6b6b70; --line:#e3e1db; --card:#fff;
  --dem:#1f5fbf; --dem-bg:#e8f0fc; --rep:#c0392b; --rep-bg:#fcebe9; --dem-mark:#1f5fbf; --rep-mark:#c0392b;
  --conf:#2e7d4f; --conf-bg:#e6f4ec; --deep:#a35a00; --deep-bg:#fdf1e1; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#141416; --fg:#ececef; --muted:#9a9aa2; --line:#2c2c31; --card:#1c1c20;
  --dem:#7fb0ff; --dem-bg:#1a2740; --rep:#ff8a7d; --rep-bg:#3a1c1a; --dem-mark:#4f8be8; --rep-mark:#e0604f;
  --conf:#6fd39a; --conf-bg:#173024; --deep:#f0b366; --deep-bg:#3a2a14; }} }}
:root[data-theme="dark"] {{ --bg:#141416; --fg:#ececef; --muted:#9a9aa2; --line:#2c2c31; --card:#1c1c20;
  --dem:#7fb0ff; --dem-bg:#1a2740; --rep:#ff8a7d; --rep-bg:#3a1c1a; --dem-mark:#4f8be8; --rep-mark:#e0604f;
  --conf:#6fd39a; --conf-bg:#173024; --deep:#f0b366; --deep-bg:#3a2a14; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1400px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ margin:0 0 4px; font-size:26px }} .lede {{ color:var(--muted); margin:0 0 20px; max-width:900px }}
h2 {{ font-size:18px; margin:28px 0 8px; display:flex; flex-wrap:wrap; align-items:baseline; gap:10px }}
h2 .cnt {{ font-size:13px; font-weight:400; color:var(--muted) }} b.d {{ color:var(--dem) }} b.r {{ color:var(--rep) }}
.snote {{ color:var(--muted); font-size:12px; margin:0 0 8px }}
.summary {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; min-width:150px }}
.card b {{ display:block; font-size:24px; font-variant-numeric:tabular-nums }} .card span {{ color:var(--muted); font-size:12px }}
.grid2 {{ display:grid; grid-template-columns:minmax(0,1.4fr) minmax(0,1fr); gap:16px; margin-bottom:16px }}
@media (max-width:900px) {{ .grid2 {{ grid-template-columns:minmax(0,1fr) }} }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px }}
.panel h3 {{ margin:0 0 6px; font-size:14px }} .scroll {{ overflow-x:auto }}
svg {{ width:100%; height:auto; display:block }}
svg text {{ fill:var(--muted); font-size:11px }} svg text.lbl {{ fill:var(--fg); font-weight:600 }}
svg .axis {{ stroke:var(--line) }} svg .majority {{ stroke:var(--fg); stroke-dasharray:4 3 }}
svg .bar.dem {{ fill:var(--dem-mark) }} svg .bar.rep {{ fill:var(--rep-mark) }} svg .hit {{ fill:transparent }}
.legend {{ display:flex; gap:14px; font-size:12px; color:var(--muted); margin-top:4px }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px }}
#tip {{ position:fixed; pointer-events:none; background:var(--fg); color:var(--bg); font-size:12px; padding:4px 8px; border-radius:4px; display:none; z-index:10 }}
table.small {{ width:100%; border-collapse:collapse; font-size:13px }}
table.small td, table.small th {{ padding:4px 6px; border-bottom:1px solid var(--line); text-align:left }}
table.small th {{ color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase }}
.method {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin-bottom:12px; color:var(--muted) }}
.method b {{ color:var(--fg) }} .method ul {{ margin:4px 0; padding-left:18px }} .callout {{ border-left:4px solid var(--deep) }}
.wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--card) }}
table.main {{ border-collapse:collapse; width:100%; min-width:1200px }}
table.main > thead th, table.main > tbody > tr > td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top }}
table.main > thead th {{ background:var(--card); font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted) }}
td.dem {{ color:var(--dem) }} td.rep {{ color:var(--rep) }}
td.num, .num {{ font-variant-numeric:tabular-nums; white-space:nowrap }} table.main td.num {{ font-weight:600 }}
td.poll {{ font-size:12px; color:var(--muted); max-width:220px }}
td.st {{ font-weight:600; white-space:nowrap }}
.sub {{ display:block; font-size:11px; color:var(--muted); font-weight:400 }}
.pill {{ display:inline-block; font-size:10px; font-weight:500; color:var(--muted); border:1px solid var(--line); border-radius:8px; padding:0 5px; margin-left:4px }}
td.win {{ font-weight:700; white-space:nowrap }} td.win.dem {{ background:var(--dem-bg); color:var(--dem) }} td.win.rep {{ background:var(--rep-bg); color:var(--rep) }} td.win.ind {{ background:var(--card); color:var(--muted) }}
.pbar {{ display:flex; width:100px; height:10px; border-radius:5px; overflow:hidden; gap:2px }}
.pbar i {{ display:block; height:100% }} .pbar i.dem {{ background:var(--dem-mark) }} .pbar i.rep {{ background:var(--rep-mark) }}
.tag {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; white-space:nowrap }}
.tag.confident {{ background:var(--conf-bg); color:var(--conf) }} .tag.deep {{ background:var(--deep-bg); color:var(--deep) }}
.tag.dem {{ background:var(--dem-bg); color:var(--dem) }} .tag.rep {{ background:var(--rep-bg); color:var(--rep) }} .tag.soft {{ border:1px solid var(--line); color:var(--muted) }}
.flip {{ font-size:10px; background:var(--fg); color:var(--bg); padding:1px 5px; border-radius:4px; margin-left:4px }}
tr.detail td {{ padding:0 10px 8px; border-bottom:2px solid var(--line) }}
tr.race:has(+ tr.detail) td {{ border-bottom:none }}
summary {{ cursor:pointer; color:var(--deep); font-size:12px; font-weight:600; padding:4px 0 }}
.dd {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:8px 20px; padding:8px 0 }}
.dd .wide {{ grid-column:1/-1; overflow-x:auto }} .dd h4 {{ margin:6px 0 2px; font-size:12px; text-transform:uppercase; color:var(--muted) }}
.dd p, .dd ul {{ margin:2px 0 }} .dd a {{ color:var(--dem) }} .dd .ctx {{ border-top:1px dashed var(--line); padding-top:6px; color:var(--muted) }}
table.inner {{ border-collapse:collapse; width:100%; font-size:12px }}
table.inner td, table.inner th {{ padding:3px 6px; border-bottom:1px solid var(--line); text-align:left }} table.inner th {{ color:var(--muted); font-weight:600 }}
.note {{ font-size:11px; color:var(--muted) }} .muted {{ color:var(--muted) }}
.toolbar {{ position:sticky; top:0; z-index:5; background:var(--bg); padding:10px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; border-bottom:1px solid var(--line) }}
.toolbar button, .toolbar select {{ background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:14px; padding:4px 12px; cursor:pointer; font:inherit }}
.toolbar button.on {{ background:var(--fg); color:var(--bg) }}
.fliplist {{ font-size:13px; color:var(--muted) }} .fliplist b {{ color:var(--fg) }}
footer {{ color:var(--muted); font-size:12px; margin-top:24px }}
.sim {{ border:1px solid var(--line); border-radius:8px; background:var(--card); padding:14px 16px; margin-bottom:16px }}
.sim > h2 {{ margin:0 0 4px }}
.levers {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px 24px; margin:12px 0 }}
.lever > label {{ display:flex; justify-content:space-between; font-weight:600; font-size:13px }}
.lever output, .rlev output {{ font-variant-numeric:tabular-nums }}
.lever input[type=range], .rlev input {{ width:100%; accent-color:var(--fg) }}
.lever .ends {{ display:flex; justify-content:space-between; font-size:11px; color:var(--muted) }}
.lever > .rlev {{ display:grid; grid-template-columns:80px minmax(0,1fr) 48px; gap:8px; align-items:center; font-size:12px }}
.rlev output {{ text-align:right }}
.presets {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:4px }}
.presets button, .seg button, .sim .btn {{ background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:12px; padding:3px 10px; font-size:12px; cursor:pointer; font-family:inherit }}
.seg {{ display:inline-flex; flex-wrap:wrap; gap:4px }}
.seg button[aria-pressed="true"] {{ background:var(--fg); color:var(--bg); border-color:var(--fg) }}
.seg button.dem[aria-pressed="true"] {{ background:var(--dem-mark); border-color:var(--dem-mark); color:#fff }}
.seg button.rep[aria-pressed="true"] {{ background:var(--rep-mark); border-color:var(--rep-mark); color:#fff }}
.sim .summary .card b em {{ font-style:normal; font-size:12px; font-weight:600; margin-left:6px }}
em.up, em.dn {{ font-style:normal; margin-left:4px }} em.up {{ color:var(--conf) }} em.dn {{ color:var(--rep) }}
#sim-status-row {{ font-size:12px; color:var(--muted); margin:0 0 8px; display:flex; flex-wrap:wrap; gap:8px; align-items:center }}
#sim-chart {{ max-width:820px }}
#sim-states {{ max-width:900px; margin-top:8px }}
.sblock {{ border-bottom:1px solid var(--line) }}
.sblock > summary {{ display:grid; grid-template-columns:minmax(0,150px) minmax(0,1fr) auto; gap:8px; align-items:center; padding:8px 0; color:var(--fg); font-size:13px }}
.sname {{ font-weight:700 }} .sinfo {{ color:var(--muted); font-weight:400; font-size:12px }}
.sblock[open] > summary {{ border-bottom:1px dashed var(--line) }}
.lrow {{ display:grid; grid-template-columns:minmax(0,1fr) 110px auto; gap:8px; align-items:center; padding:6px 0 6px 16px; border-bottom:1px solid var(--line) }}
.lrow:last-child {{ border-bottom:none }}
.lrow.locked .lst {{ text-decoration:underline dotted }}
.lst {{ font-weight:600 }} .lbar .pbar {{ width:100px }}
.pbar i.ch, .pbar i.rp {{ transition:width .15s }}
@media (max-width:600px) {{ .sblock > summary {{ grid-template-columns:minmax(0,1fr) }} .lrow {{ grid-template-columns:minmax(0,1fr) auto; padding-left:8px }} .lrow .seg {{ grid-column:1/-1 }} }}
</style></head><body><main>
{site.nav('house.html')}
<h1>2026 House Forecast</h1>
<p class="lede">All 435 seats, state by state, seat by seat. A probabilistic model: every district starts from its 2024 presidential margin on the
2026 lines plus the national swing and incumbency, then blends in {n_polls} individual district polls where they exist. {audited} competitive or polled
districts were fact-checked. No district-specific judgment calls. Data as of {esc(model['as_of'])}.</p>
<div class="summary">
  <div class="card"><b style="color:var(--dem)">{pct(pD)}</b><span>Democrats win the House (218+)</span></div>
  <div class="card"><b style="color:var(--rep)">{pct(1 - pD)}</b><span>Republicans keep the House</span></div>
  <div class="card"><b>{pc['50']}</b><span>Median Democratic seats</span></div>
  <div class="card"><b>{pc['10']}–{pc['90']}</b><span>80% range of Democratic seats</span></div>
  <div class="card"><b>{tot['D']}–{tot['R']}</b><span>If every district leader wins ({'D' if net >= 0 else 'R'} +{abs(net)} vs. today)</span></div>
</div>
<div class="grid2">
  <div class="panel"><h3>Seat distribution across {P['sims']:,} simulated elections</h3>{chart}
    <div class="legend"><span><i style="background:var(--dem-mark)"></i>Democratic majority</span><span><i style="background:var(--rep-mark)"></i>Republican majority</span></div></div>
  <div class="panel"><h3>If the polls are off</h3>
    <div class="scroll"><table class="small"><thead><tr><th>Scenario (same shift in every district)</th><th>Leaders</th><th>Median D</th><th>P(D)</th></tr></thead><tbody>{sc_rows}</tbody></table></div>
    <p class="note">The national swing comes from the generic ballot, which is itself a poll. Each row moves every district by the same amount and re-runs the simulation.</p>
    <h3 style="margin-top:12px">Seats by rating</h3>
    <div class="scroll"><table class="small"><thead><tr><th>Tier</th><th>D</th><th>R</th></tr></thead><tbody>{tier_rows}</tbody></table></div>
    <p class="note">Certain = decided by the ballot. Democrats' Certain + Safe + Likely + Lean seats total {d_solid}.</p></div>
</div>
<div class="method callout"><b>Big picture.</b> The generic ballot is about D+8.7, against R+2.6 in the 2024 House vote. Mid-decade redistricting shifted
roughly 9 notional seats to Republicans, but a swing that size outweighs it. Republicans become favorites only if the polls and generic ballot miss by about {breakeven:.1f}+ points in their direction, beyond the
baseline shading. Polling misses of that size have happened (2014, 2020), which is why this is about {pct(pD)}, not a certainty.</div>
<section class="sim" id="levers"><h2>Try your own scenario</h2>
<p class="note" style="margin:0">Move the levers to see how control changes. The page re-runs {sim_data['n']:,} simulations in your browser on every change,
using the same model and the same random draws each time, so any change you see comes from the lever.</p>
<div class="levers">
  <div class="lever"><label for="sim-swing">Polling miss in every district <output id="sim-swing-out">None</output></label>
    <input id="sim-swing" type="range" min="-10" max="10" step="0.5" value="0">
    <div class="ends"><span>Republicans beat polls by 10</span><span>Democrats by 10</span></div>
    <div class="presets"><button data-preset="-6">R+6 (2020)</button><button data-preset="-3">R+3 (2016/2024)</button><button data-preset="0">None</button><button data-preset="3">D+3 (2012)</button></div>
    <p class="note" style="margin:6px 0 0">The shift applies to every district; only too-close districts are listed below.</p></div>
  <div class="lever"><label>Extra swing by region <span class="note" style="font-weight:400">on top of the national miss</span></label>{reg_levers}</div>
  <div class="lever"><label for="sim-err">Uncertainty <output id="sim-err-out">×1</output></label>
    <input id="sim-err" type="range" min="0" max="2" step="0.25" value="1">
    <div class="ends"><span>0: every leader wins</span><span>×1 historical</span><span>×2</span></div></div>
</div>
<p id="sim-status-row"><span id="sim-status"></span> <button class="btn" id="sim-reset">Reset all levers</button></p>
<div class="summary">
  <div class="card"><b id="sim-pd" style="color:var(--dem)"></b><span>Democrats win the House</span></div>
  <div class="card"><b id="sim-pr" style="color:var(--rep)"></b><span>Republicans keep the House</span></div>
  <div class="card"><b id="sim-exp"></b><span>Median Democratic seats</span></div>
  <div class="card"><b id="sim-range"></b><span>80% range</span></div>
  <div class="card"><b id="sim-lead"></b><span>Seats if every leader wins</span></div>
</div>
<div id="sim-chart"></div>
<h3 style="margin:14px 0 0;font-size:14px">Call too-close-to-call races yourself, state by state</h3>
<p class="note" style="margin:2px 0">{len(too_close)} districts in {len(close_by_state)} states are too close to call: the model gives either side between {TOO_CLOSE[0]:.0%} and {TOO_CLOSE[1]:.0%}.
Use All D / All R to call a state's close districts at once, or open a state to call them one by one. Everything you don't call stays simulated.
Each state line shows its expected Democratic seats across all its districts. <button class="btn" id="sim-expand">Expand / collapse all</button></p>
<div id="sim-states">{''.join(state_blocks)}</div>
</section>

{'<details class="method"><summary>What changed from v1 (' + str(len(changes)) + ' districts)</summary><p>v1 called each seat by judgment. The model now sets the leader from fundamentals and polls alone.</p><ul>' + chg + '</ul></details>' if changes else ''}
<details class="method"><summary>Method, parameters and sources</summary><ul>
<li><b>Fundamentals.</b> 2024 presidential margin on the 2026 lines + national shift {P['national_shift'] + P['generic_ballot_bias_adj']:+g} (generic ballot D+8.7 minus the 2024 national presidential margin R+1.5 = {P['national_shift']:+g}, shaded {P['generic_ballot_bias_adj']:+g} for the generic ballot's history of overstating Democrats)
× elasticity (1 − {P['elasticity_k']:g}×|margin|/40, capped at 40) + incumbency {P['incumbency_bonus']:g} pts for a member running (×{P['new_territory_factor']:g} on mostly new territory).
Where the member's 2024 race was on comparable lines, {P['overperformance_shrink']:.0%} of their over/under-performance vs. the presidential margin (net of generic incumbency) carries forward.
District error SD: {P['error']['fundamentals_sd']:g} (incumbent), {P['error']['fundamentals_sd_open']:g} (open), {P['error']['fundamentals_sd_new']:g} (incumbent on new lines).</li>
<li><b>District polls.</b> Same weighting as the Senate model (recency half-life {P['weights']['half_life_days']} days, sample size, LV/RV, ×{P['weights']['partisan_sponsor']} and a {P['weights']['partisan_shift']:g}-pt shift for campaign/party internals).
A district poll average carries residual error SD {P['error']['poll_state_sd']:g} plus sampling noise, and is blended with the fundamentals by precision.</li>
<li><b>Why the generic ballot is shaded when Senate and governor polls are not.</b> The two rest on different evidence. Senate and governor polls have missed in both directions, and one cycle's miss says almost nothing about the next (correlation 0.17 between cycles, 1998–2022), so those models assume no bias and test misses as scenarios. The generic ballot is a single national question asked the same way every cycle, and its final average overstated Democrats in 7 of 10 cycles from 2006 to 2024, by 1.85 points on average (standard error about 0.7). That is a measured property of the instrument, not a guess about this year, so half of it ({P['generic_ballot_bias_adj']:+g}) is applied to every district. The full and zero versions are in the scenario table.</li>
<li><b>Correlated error.</b> National SD {P['error']['national_sd']:g}, regional SD {P['error']['regional_sd']:g}, district SD as above; Student-t, {P['error']['t_df']} df.</li>
<li><b>Ballot-decided seats</b> (one major party absent, or a California top-two race within one party) are certain.</li>
<li><b>Tiers</b>: Safe ≥ 99%, Likely ≥ 90%, Lean ≥ 75%, Tilt ≥ 60%, else Toss-up. The {CM}-point rule only flags deep dives (the original sheet used 10).</li>
<li><b>Not modeled:</b> Louisiana's Dec 12 runoffs (the Nov 3 leader is shown); candidate scandals or money beyond what polls capture.</li>
{''.join(f'<li><b>{esc(k)}</b>: {esc(v)}</li>' for k, v in P.get('sources', {}).items())}
</ul></details>
<p class="fliplist">Seats changing hands, by the party of the sitting member (new seats with no incumbent are not tagged).<br>
<b>Flips to D ({len(flips['D'])}):</b> {esc(', '.join(sorted(flips['D'], key=dist_sort)) or 'none')}<br>
<b>Flips to R ({len(flips['R'])}):</b> {esc(', '.join(sorted(flips['R'], key=dist_sort)) or 'none')}</p>
<div class="toolbar">
  <button class="on" data-f="all">All seats</button><button data-f="close">Lean, Tilt &amp; Toss-up</button><button data-f="deep">Deep dives (swing ≤ {CM})</button>
  <button data-f="flipped">Flips</button><button data-f="changed">Changed from v1</button>
  <select id="jump"><option value="">Jump to state…</option>{''.join(nav)}</select>
</div>
{''.join(sections)}
{site.history('house.html')}
<footer>{esc(meta['footer'])} Model: house_model.py + model_params_house.json; polls and audit in house_polls.json.</footer>
</main>
<div id="tip"></div>
<script>
const btns = document.querySelectorAll('.toolbar button');
btns.forEach(b => b.onclick = () => {{
  btns.forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('section').forEach(sec => {{
    let any = false;
    sec.querySelectorAll('table.main > tbody > tr').forEach(tr => {{
      const show = f === 'all' || tr.classList.contains(f);
      tr.style.display = show ? '' : 'none';
      if (show) any = true;
    }});
    sec.style.display = any ? '' : 'none';
  }});
}});
document.getElementById('jump').onchange = e => {{
  if (e.target.value) document.getElementById(e.target.value).scrollIntoView({{behavior: 'smooth'}});
}};
const tip = document.getElementById('tip');
document.querySelectorAll('svg .hit').forEach(el => {{
  el.addEventListener('mousemove', e => {{ tip.textContent = el.dataset.tip; tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + 'px'; tip.style.top = (e.clientY - 30) + 'px'; }});
  el.addEventListener('mouseleave', () => tip.style.display = 'none');
}});
</script>
<script>
const SIM = {sim_json};
{sim_js}
</script>
</body></html>"""

(HERE / "house.html").write_text(page)
print(f"house.html: P(D) {pD:.0%}; expected D {model['expected_d']:.1f}; leaders D {tot['D']} / R {tot['R']}; "
      f"flips to D {len(flips['D'])}, to R {len(flips['R'])}; {len(changes)} changed vs v1")
