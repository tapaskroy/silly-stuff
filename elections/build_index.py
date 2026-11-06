#!/usr/bin/env python3
"""Build index.html, the overview page linking the three sheets. Run after the three models."""
import json
from pathlib import Path

import numpy as np

import governor_model
import house_model
import senate_model
import site_chrome as site

HERE = Path(__file__).parent
sen = json.loads((HERE / "senate_model.json").read_text())
hou = json.loads((HERE / "house_model.json").read_text())
gov = json.loads((HERE / "gov_model.json").read_text())
css = (HERE / "page.css").read_text()


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{p:.0%}"




def median(seats):
    """Median seat count of an array of simulated seat totals: the smallest count that half the simulations reach or fall below."""
    return int(np.percentile(seats, 50, method="inverted_cdf"))


def miss(shift):
    """Rerun each model's simulation with every race shifted toward Republicans. Per chamber:
    (P(Democrats control), P(Republicans control), median Democratic seats, median Republican seats). Senate Democratic
    seats include independents; the Senate's two chances can sum below 100% when unaligned independents decide. Same
    simulations and seed as the headline, so the only difference is the shift."""
    races = [senate_model.race(s) for s in sorted(senate_model.config)]
    _, hist = senate_model.simulate(races, shift=shift)
    s_ctl = senate_model.control_probs(hist)["separate"]
    s_di = np.repeat([int(d) + int(i) for k in hist for d, i in [k.split(",")]],
                     [round(v * senate_model.P["sims"]) for v in hist.values()])
    _, seats = house_model.simulate([house_model.district(r) for r in house_model.data], shift=shift)
    _, d_gov, i_gov = governor_model.simulate([governor_model.race(s) for s in sorted(governor_model.config)], shift=shift)
    return {"senate.html": (s_ctl["D"], s_ctl["R"], median(s_di), median(100 - s_di)),
            "house.html": ((seats >= house_model.MAJORITY).mean(), (seats < house_model.MAJORITY).mean(),
                           median(seats), median(435 - seats)),
            "governors.html": ((d_gov >= 26).mean(), (50 - d_gov - i_gov >= 26).mean(),
                               median(d_gov), median(50 - d_gov - i_gov))}


MISSES = {k: miss(-k) for k in (2, 3)}
BASE = miss(0)  # reproduces the published headline; used for each party's median seats
assert abs(BASE["house.html"][0] - hou["p_dem_control"]) < 1e-9 and abs(BASE["governors.html"][0] - gov["p_d_majority"]) < 1e-9
# Per chamber: total seats, what Democrats would win and Republicans keep (Republicans hold all three now), seat words.
CHAMBER = {"senate.html": (100, "winning control", "keeping control", "Democratic and independent seats", "Republican seats",
                           "unaligned independents decide control"),
           "house.html": (435, "winning control", "keeping control", "Democratic seats", "Republican seats", ""),
           "governors.html": (50, "winning a majority of governorships", "keeping a majority of governorships",
                              "Democratic governors", "Republican governors", "governorships split 25–25")}


def miss_line(k, href):
    """One sentence from the favored party's side, with each party's median seat count.
    When the favorite is under 50%, the other party's chance and what happens in the remaining simulations are added."""
    p_d, p_r, d, r = MISSES[k][href]
    total, d_goal, r_goal, d_seats, r_seats, rest = CHAMBER[href]
    who, p, goal, other, p_o = ("Democrats", p_d, d_goal, "Republicans", p_r) if p_d >= p_r else ("Republicans", p_r, r_goal, "Democrats", p_d)
    tail = f" {other} have <strong>{pct(p_o)}</strong>; in the rest, {rest}." if p < 0.5 and rest else ""
    if href == "senate.html" and d == r:
        tail += " A 50–50 Senate goes to the party of the Vice President, a Republican."
    return f"<br>R+{k}: {who} have a <strong>{pct(p)}</strong> chance of {goal}, with a median of <strong>{d}</strong> {d_seats} and <strong>{r}</strong> {r_seats}.{tail}"


def miss_block(href):
    return f'<p class="miss">If the polls overstate Democrats:{"".join(miss_line(k, href) for k in MISSES)}</p>'


def base_seats(href):
    """Each party's median seats with the polls taken as right, seat counts in bold."""
    _, _, d, r = BASE[href]
    _, _, _, d_seats, r_seats, _ = CHAMBER[href]
    return f"Median <strong>{d}</strong> {d_seats}, <strong>{r}</strong> {r_seats}."


sep = sen["control"]["separate"]
cards = [
    ("senate.html", "Senate", "35 seats", pct(sep["D"]), "Democrats win control (51+)",
     f"{base_seats('senate.html')} Republicans <strong>{pct(sep['R'])}</strong>; unaligned independents decide <strong>{pct(sep['unclear'])}</strong>."),
    ("house.html", "House", "435 seats, state by state", pct(hou["p_dem_control"]), "Democrats win the House (218+)",
     f"{base_seats('house.html')} Democratic seats 80% range <strong>{hou['pct']['10']}–{hou['pct']['90']}</strong>."),
    ("governors.html", "Governors", "36 races", pct(gov["p_d_majority"]), "Democrats hold 26+ governorships",
     f"{base_seats('governors.html')} Democratic governors 80% range <strong>{gov['pct']['10']}–{gov['pct']['90']}</strong>."),
]
tiles = "".join(
    f'<a class="card hub" href="{href}"><span class="k">{name} · {sub}</span><b style="color:var(--dem)">{big}</b>'
    f'<span>{lab}</span><p>{detail}</p>{miss_block(href)}<span class="go">Open the {name.lower()} sheet, with levers →</span></a>'
    for href, name, sub, big, lab, detail in cards)

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 Midterm Forecasts</title>
<style>{css}
.hubs {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr)); gap:16px; margin:16px 0 }}
a.hub {{ color:inherit; text-decoration:none; display:flex; flex-direction:column; gap:2px; padding:16px }}
a.hub:hover {{ border-color:var(--fg) }} a.hub .k {{ font-weight:600; color:var(--fg); font-size:13px }}
a.hub .miss {{ color:var(--fg); margin-top:0 }} a.hub strong {{ color:var(--fg) }}
a.hub b {{ font-size:36px }} a.hub p {{ color:var(--muted); font-size:13px; margin:8px 0 }} a.hub .go {{ color:var(--dem); font-weight:600; font-size:13px }}
</style></head><body><main>
{site.nav('index.html')}
<h1>2026 Midterm Forecasts</h1>
<p class="lede">Probabilistic forecasts for the Senate, House and governor races on Nov 3, 2026, built from individual polls and a
documented fundamentals model with correlated polling error, and no race-by-race judgment calls. Each sheet has levers to try your own scenario:
a polling miss, more or less uncertainty, and calling the too-close-to-call races yourself. Data as of {sen['as_of']}.</p>
<p class="lede">The headline numbers assume the polls are right on average. Each card also shows the same simulation with every race
shifted 2 or 3 points toward Republicans (R+2, R+3), the size of polling miss seen in several recent elections. For the House the
shift comes on top of the {-house_model.P['generic_ballot_bias_adj']:g}-point shading toward Republicans already in the forecast.</p>
<div class="hubs">{tiles}</div>
{site.history('index.html')}
<footer>Forecasts, not predictions of certainty: a 70% favorite loses 3 times in 10 in simulations.</footer>
</main></body></html>"""
(HERE / "index.html").write_text(page)
print("index.html written")
