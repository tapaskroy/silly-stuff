#!/usr/bin/env python3
"""Build review.html: the post-election review of the frozen Nov 3 forecast, with every upset in detail.

Reads review/analysis.json (written by review/analyze.py) and review/counterfactuals.json (review/counterfactuals.py).
Sections: 1. how we did, overall and against other forecasters; 2. where we went wrong, by chamber; 3. post-mortem;
4. who called the close races; 5. summary and changes for 2028; appendices with each upset, the pollsters, and sources.
Usage: python3 review/analyze.py && python3 build_review.py
"""
import html
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
RV = HERE / "review"
A = json.loads((RV / "analysis.json").read_text())
CF = json.loads((RV / "counterfactuals.json").read_text())
css = (HERE / "page.css").read_text()
esc = html.escape
CHS = ("senate", "house", "governors")
TITLE = {"senate": "Senate", "house": "House", "governors": "Governors"}
SHORT = {"This forecast": "This forecast", "Cook Political Report": "Cook", "Sabato's Crystal Ball": "Sabato's Crystal Ball",
         "Inside Elections": "Inside Elections"}


def short(name):
    """Forecaster names as the tables show them: drop the parenthetical credits."""
    return SHORT.get(name) or name.split(" (")[0].split(", now")[0]


def pct(p):
    return "–" if p is None else ">99%" if p >= .995 else "<1%" if p <= .005 else f"{p:.0%}"


def frac(a, b):
    return f"{a} of {b}" if b else "–"


def num(x, fmt="+.1f"):
    return "–" if x is None else format(x, fmt)


def pt(iso):
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=8)
    return f"{t:%b %-d}, {t:%-I:%M} {'a.m.' if t.hour < 12 else 'p.m.'} PT"


S = {ch: A[ch]["summary"] for ch in CHS}
B = {ch: A[ch]["board"] for ch in CHS}
NATL = A["national"]
ERR = A["errors"]
CFV = {ch: {v["key"]: v for v in CF[ch]} for ch in CHS}
ALL_UPSETS = [u for ch in CHS for u in A[ch]["upsets"]]


def find(ch, ident):
    return next((b for b in B[ch] if b["id"] == ident), None)


def party_cls(p):
    return {"D": "D", "R": "R"}.get(p, "I")


# ---------- 1. scoreboards ----------

def scoreboard(ch):
    """Every source on the called races it covered. Toss-ups count as no call; Brier only where a source gave odds,
    shown beside ours on exactly the same races."""
    rows = [b for b in B[ch] if b["kind"] != "national_poll"]
    nat = sorted((b for b in B[ch] if b["kind"] == "national_poll"), key=lambda b: -b["right"])
    ours = find(ch, "ours")
    if nat:
        rows.append(dict(nat[0], name=nat[0]["name"].replace(", uniform swing", "") + " · best national poll, applied evenly", kind="national_poll"))
    def key(b):
        return -(b["right"] + .5 * b["nocall"]) / b["n"], b["kind"] != "model"
    body = []
    full_rows = sorted((b for b in rows if b["covered"] == "all"), key=key)
    part_rows = sorted((b for b in rows if b["covered"] != "all"),
                       key=lambda b: -((b["right"] + .5 * b["nocall"] - b["right_ours_same"]) / b["n"] if b.get("right_ours_same") is not None else -1))
    ordered = full_rows + ([{"sub": "Scored only on the races they covered: compare with ours on the same races, in brackets"}] if part_rows else []) + part_rows
    for b in ordered:
        if "sub" in b:
            body.append(f"<tr class='sub'><td colspan='9'>{esc(b['sub'])}</td></tr>")
            continue
        full = b["covered"] == "all"
        share = (b["right"] + .5 * b["nocall"]) / b["n"]
        mine = b["id"] == "ours"
        brier = ("–" if b.get("brier") is None else
                 f"{b['brier']:.3f}" + (f" <span class='dim'>(ours {b['brier_ours_same']:.3f})</span>" if b.get("brier_ours_same") is not None and not mine else ""))
        cover = f"{b['n']}" if full else f"{b['n']} <span class='dim'>of {ours['n']}</span>"
        same = f" <span class='dim'>(ours {b['right_ours_same']})</span>" if b.get("right_ours_same") is not None and not full else ""
        kind = {"model": "Model", "rater": "Expert rating", "market": "Betting market", "national_poll": "National poll", "polls": "Polls"}[b["kind"]]
        flag = "" if b.get("verified", True) is not False else " <span class='dim' title='numbers from news reports, not the forecaster's own files'>†</span>"
        body.append(f"<tr class='{'mine' if mine else ''}'><td>{esc(short(b['name']))}{flag}</td><td class='dim'>{kind}</td><td class='num'>{cover}</td>"
                    f"<td class='num'><b>{b['right']}</b>{same}</td><td class='num'>{b['wrong']}</td><td class='num'>{b['nocall'] or '–'}</td>"
                    f"<td><span class='meter'><i style='width:{share * 100:.1f}%'></i></span> <span class='num'>{share:.1%}</span></td>"
                    f"<td class='num'>{len(b['upsets_caught']) if not mine else '–'}</td><td class='num'>{brier}</td></tr>")
    return (f"<div class='scroll'><table class='small board'><thead><tr><th>Source</th><th>Kind</th><th class='num'>Races scored</th><th class='num'>Right</th>"
            f"<th class='num'>Wrong</th><th class='num'>Toss-up</th><th>Score (toss-up = half)</th><th class='num'>Our upsets it caught</th>"
            f"<th class='num'>Brier</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>")


def control_table():
    c = A.get("control") or {}
    names = A.get("quant_forecasters") or {}
    rows = []
    for k, v in sorted(c.items(), key=lambda kv: -(kv[1].get("house_p_dem") or 0)):
        if not isinstance(v, dict) or (v.get("senate_p_dem") is None and v.get("house_p_dem") is None):
            continue
        nm = short((names.get(k) or {}).get("name") or k)
        rows.append(f"<tr><td>{esc(nm)}{'' if v.get('verified', True) else ' <span class=dim>†</span>'}</td>"
                    f"<td class='num'>{pct(v.get('senate_p_dem'))}</td><td class='num'>{v.get('senate_median_dem') or '–'}</td>"
                    f"<td class='num'>{pct(v.get('house_p_dem'))}</td><td class='num'>{v.get('house_median_dem') or '–'}</td></tr>")
    o, st_ = A["seats"]["ours"], A["seats"]
    rows.insert(0, f"<tr class='mine'><td>This forecast</td><td class='num'>{pct(o['senate_p_dem'])}</td><td class='num'>{o['senate_median_dem']}</td>"
                   f"<td class='num'>{pct(o['house_p_dem'])}</td><td class='num'>{o['house_median_dem']}</td></tr>")
    so = f" + {st_['senate_open']} uncalled" if st_["senate_open"] else ""
    ho = f" + {st_['house_open']} uncalled" if st_["house_open"] else ""
    rows.append(f"<tr class='result'><td><b>Result so far</b></td><td class='num'>Democrats won</td><td class='num'><b>{st_['senate_d']}</b>{so}</td>"
                f"<td class='num'>Democrats won</td><td class='num'><b>{st_['house_d']}</b>{ho}</td></tr>")
    return "".join(rows)


# ---------- 2. upsets by chamber ----------

def who_right(u):
    """Short list of who favored the eventual winner."""
    raters = [short(n) for k, n in (("cook", "Cook Political Report"), ("sabato", "Sabato's Crystal Ball"), ("inside", "Inside Elections"))
              if (u["ratings"].get(k) or "").split(" ")[0] in ("Lean", "Leans", "Likely", "Tilt", "Tilts", "Safe", "Solid")
              and _side(u["ratings"][k]) == ("D" if u["winner_party"] != "R" else "R")]
    models = [m["name"] for m in u["models"] if m["right"]]
    polls = [p for p in u["polls"] if p["winner_lead"] > 0]
    return raters, models, polls


def _side(s):
    import re
    m = re.match(r"\s*(Safe|Solid|Likely|Lean|Leans|Tilt|Tilts)\s+([DRI])\b", s or "")
    return None if not m else ("R" if m.group(2) == "R" else "D")


def upset_table(ch):
    rows = []
    for u in A[ch]["upsets"]:
        raters, models, polls = who_right(u)
        indep = [p for p in polls if not p["partisan"]]
        n_models = len([m for m in u["models"]])
        rows.append(
            f"<tr><td class='key'><a href='#u-{esc(u['key'])}'>{esc(u['key'])}</a></td>"
            f"<td><span class='pt {party_cls(u['winner_party'])}'>{esc(u['winner'])}</span></td>"
            f"<td class='num'>{pct(u['p_winner'])}</td><td class='num'>{num(u['forecast_margin_winner'])}</td><td class='num'>{num(u['actual_margin_winner'])}</td>"
            f"<td>{esc(', '.join(raters)) or '<span class=dim>none</span>'}</td>"
            f"<td class='num'>{frac(len(models), n_models) if n_models else '<span class=dim>–</span>'}</td>"
            f"<td class='num'>{len(polls)} of {len(u['polls'])}" + (f" <span class='dim'>({len(indep)} independent)</span>" if polls else "") + "</td></tr>")
    return (f"<div class='scroll'><table class='small'><thead><tr><th>Race</th><th>Winner</th><th class='num'>Our chance</th>"
            f"<th class='num'>Forecast margin</th><th class='num'>Actual margin</th><th>Raters who had the winner</th><th class='num'>Models and markets with the winner</th>"
            f"<th class='num'>Polls with the winner ahead</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
            "<p class='note'>Margins are the winner's lead in points (forecast: our mean; actual: AP's current count). Polls: our audited polls ending Aug 1 or later.</p>")


# ---------- charts ----------

def national_strip():
    """National generic-ballot polls on one axis, with the average, our input and the result."""
    lo, hi = 2, 16
    x = lambda v: (v - lo) / (hi - lo) * 100
    dots = []
    stack = {}
    for p in sorted(NATL["polls"], key=lambda p: p["d_margin"]):
        k = round(p["d_margin"] * 2) / 2
        stack[k] = stack.get(k, 0) + 1
        dots.append(f"<span class='dot' style='left:{x(p['d_margin']):.2f}%;bottom:{(stack[k] - 1) * 11 + 4}px' "
                    f"data-t='{esc(p['pollster'])}: D+{p['d_margin']:g} (off by {abs(p['error']):.1f})'></span>")
    h = max(stack.values()) * 11 + 12
    marks = [(NATL["model_input"], "Our input D+" + f"{NATL['model_input']:g}", "inp"), (NATL["average"], f"Average D+{NATL['average']:g}", "avg"),
             (NATL["actual"], f"Result D+{NATL['actual']:g}", "act")]
    lines = "".join(f"<span class='vline {c}' style='left:{x(v):.2f}%'><em>{esc(t)}</em></span>" for v, t, c in marks)
    ticks = "".join(f"<span class='tk' style='left:{x(v):.2f}%'>D+{v}</span>" for v in range(lo, hi + 1, 2))
    return (f"<div class='nstrip' role='img' aria-label='Final national House polls from D+3 to D+14; the result was D+{NATL['actual']:g}'>"
            f"<div class='plot' style='height:{h}px'>{''.join(dots)}{lines}</div><div class='ticks'>{ticks}</div></div>")


def bars(groups, order, label_fmt="+.1f"):
    """Horizontal bars for mean signed error by group (+ = Democrats did better than forecast)."""
    mx = max(abs(groups[k]["mean"]) for k in order if k in groups) or 1
    out = []
    for k in order:
        if k not in groups:
            continue
        g = groups[k]
        out.append(f"<div class='brow'><span class='bl'>{esc(k)} <span class='dim'>({g['n']})</span></span>"
                   f"<span class='btrack'><i class='{'D' if g['mean'] > 0 else 'R'}' style='width:{abs(g['mean']) / mx * 100:.1f}%'></i></span>"
                   f"<span class='bv num'>{format(g['mean'], label_fmt)}</span></div>")
    return "<div class='bars'>" + "".join(out) + "</div>"


# ---------- 4. close races ----------

def close_table(ch):
    c = A[ch]["close"]
    rows = []
    for s in sorted(c["sources"], key=lambda s: (-(s["right"] + .5 * s["nocall"]) / s["covered"], -s["covered"])):
        mine = s["name"] == "This forecast"
        rows.append(f"<tr class='{'mine' if mine else ''}'><td>{esc(short(s['name']))}</td><td class='num'>{s['covered']}</td>"
                    f"<td class='num'>{s['calls']}</td><td class='num'><b>{s['right']}</b></td><td class='num'>{s['calls'] - s['right']}</td>"
                    f"<td class='num'>{s['nocall'] or '–'}</td><td class='num'>{frac(s['confident_right'], s['confident']) if s['confident'] else '–'}</td></tr>")
    return (f"<div class='scroll'><table class='small'><thead><tr><th>Source</th><th class='num'>Covered</th><th class='num'>Made a call</th>"
            f"<th class='num'>Right</th><th class='num'>Wrong</th><th class='num'>Toss-up</th><th class='num'>Confident calls right</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>")


# ---------- appendix: each upset ----------

def appendix_card(u):
    raters, models, polls = who_right(u)
    r = u.get("research") or {}
    rt = "".join(f"<tr><td>{esc(n)}</td><td>{esc(u['ratings'].get(k) or '–')}</td><td class='dim'>{esc(u['ratings_mid_oct'].get(k) or '–')}</td></tr>"
                 for k, n in (("cook", "Cook"), ("sabato", "Sabato"), ("inside", "Inside Elections")))
    md = "".join(f"<li class='{'ok' if m['right'] else 'no'}'>{esc(short(m['name']))}: "
                 + (pct(m["p_winner"]) if m["p_winner"] is not None else esc(f"favored the {'winner' if m['right'] else 'loser'}" + (f" ({m['band']} band)" if m.get('band') else "")))
                 + "</li>" for m in u["models"]) or "<li class='dim'>No other model or market data found for this race.</li>"
    pl = "".join(f"<li class='{'ok' if p['winner_lead'] > 0 else 'tie' if p['winner_lead'] == 0 else 'no'}'>"
                 f"{esc(p['pollster'])}, ended {esc(p['end'])}: winner {p['winner_lead']:+.1f}"
                 + (f" · <a href='{esc(p['url'])}' rel='noopener'>source</a>" if p.get("url") else "") + "</li>" for p in u["polls"]) or "<li class='dim'>No polls in the window.</li>"
    ex = "".join(f"<li><span class='tag {'fact' if e.get('kind') == 'fact' else 'interp'}'>{'Reported' if e.get('kind') == 'fact' else 'Analysis'}</span> "
                 f"{esc(e.get('claim', ''))}" + (f" <a href='{esc(e['source'])}' rel='noopener'>source</a>" if e.get("source", "").startswith("http") else "") + "</li>"
                 for e in r.get("explanations", []))
    late = "".join(f"<li>{esc(p.get('pollster', ''))}, {esc(p.get('dates', ''))}: {esc(p.get('result', ''))}"
                   + (f" <a href='{esc(p['url'])}' rel='noopener'>source</a>" if str(p.get("url", "")).startswith("http") else "") + "</li>"
                   for p in r.get("late_polls_winner_ahead", []))
    picked = "".join(f"<li>{esc(p.get('who', ''))}: {esc(p.get('what', ''))}"
                     + (f" <a href='{esc(p['url'])}' rel='noopener'>source</a>" if str(p.get("url", "")).startswith("http") else "") + "</li>"
                     for p in r.get("picked_winner", []))
    facts = [f"We gave {esc(u['winner'])} {pct(u['p_winner'])} ({esc(u['tier'])})",
             f"forecast margin {num(u['forecast_margin_winner'])}, actual {num(u['actual_margin_winner'])}" + (f" with {esc(str(u['counted']))}% counted" if u.get("counted") else ""),
             f"poll average {num(u['poll_avg_winner'])}" if u.get("poll_avg_winner") is not None else "no usable polling average",
             f"fundamentals prior {num(u['prior_winner'])} (weight {u['prior_weight']:.0%})" if u.get("prior_winner") is not None and u.get("prior_weight") is not None else None,
             f"2024 presidential margin {num(u['pres_2024_winner'])} for the winner's party" if u.get("pres_2024_winner") is not None else None]
    names = f" · {esc(u['names'][0])} (D) vs {esc(u['names'][1])} (R)" if u.get("names") else ""
    return f"""<details class="up" id="u-{esc(u['key'])}"><summary><b>{esc(TITLE[u['ch']])} · {esc(u['key'])}</b>{names}
 <span class="chip {party_cls(u['winner_party'])}">{esc(u['winner'])} won</span> <span class="dim">we gave {pct(u['p_winner'])}</span></summary>
<p>{esc('; '.join(f for f in facts if f))}.</p>
{f"<p class='sum'>{esc(r['summary'])}</p>" if r.get('summary') else ""}
{f"<p class='dim'>Result: {esc(r['result'])}</p>" if r.get('result') else ""}
<div class="grid3">
 <div><h4>Final expert ratings</h4><table class="small"><thead><tr><th>Rater</th><th>Final</th><th>Mid-Oct</th></tr></thead><tbody>{rt}</tbody></table></div>
 <div><h4>Other models and markets (chance for the winner)</h4><ul class="lst">{md}</ul></div>
 <div><h4>Polls in our file (winner's lead)</h4><ul class="lst">{pl}</ul></div>
</div>
{f"<h4>Why it happened: what the reporting says</h4><ul class='lst ex'>{ex}</ul>" if ex else "<p class='dim'>Reporting on this race is still being gathered.</p>"}
{f"<h4>Late polls with the winner ahead (from reporting)</h4><ul class='lst'>{late}</ul>" if late else ""}
{f"<h4>Who picked the winner beforehand</h4><ul class='lst'>{picked}</ul>" if picked else ""}
</details>"""


# ---------- assemble ----------

h, s_, g = S["house"], S["senate"], S["governors"]
sab = {ch: find(ch, "sabato") for ch in CHS}
cook = {ch: find(ch, "cook") for ch in CHS}
nat_best = sorted((b for b in B["house"] if b["kind"] == "national_poll"), key=lambda b: -b["right"])
nat_beat = sum(b["right"] > find("house", "ours")["right"] for b in nat_best)
close_fav_r = sum(x["n"] for x in h["close_fav"] if x["fav"] == "R")
close_fav_r_lost = sum(x["n"] for x in h["close_fav"] if x["fav"] == "R" and x["won"] == "D")
tot_called = sum(S[c]["called"] for c in CHS)
tot_right = sum(S[c]["right"] for c in CHS)
tot_up = sum(len(S[c]["upsets"]) for c in CHS)
tot_exp = sum(S[c]["expected_upsets"] for c in CHS)
cfh = CFV["house"]
house_models = [b for b in B["house"] if b["kind"] in ("model", "market") and b["id"] != "ours"]
nat_input_err = round(NATL["actual"] - NATL["model_input"], 1)
pollsters = A["pollsters"]
indep = [p for p in pollsters if p["mostly"] == "none" and p["races"] >= 8]
indep.sort(key=lambda p: (p["mae"] if p["mae"] is not None else 99))
dint = [p for p in pollsters if p["mostly"] == "D" and p["upsets_polled"] >= 3]


def close_line():
    c = A["house"]["close"]
    src = {x["name"]: x for x in c["sources"]}
    full = sorted((x for x in c["sources"] if x["covered"] == c["n"]), key=lambda x: -x["right"])
    conf = sorted((x for x in c["sources"] if x["confident"] >= 5), key=lambda x: -x["confident_right"] / x["confident"])
    k = next((x for x in c["sources"] if x["name"] == "Kalshi"), None)
    return (f"Of the {c['n']} House races we rated 20–80%, right: " + "; ".join(f"{esc(short(x['name']))} {x['right']}" for x in full) + "."
            + (f" Kalshi listed only {k['covered']} of them and got {k['right']}." if k else "")
            + " Confident calls (70% or more) right: " + "; ".join(f"{esc(short(x['name']))} {x['confident_right']} of {x['confident']}" for x in conf) + ".")


RACES_OF = {"senate": "Senate races", "house": "House races", "governors": "governors' races"}


def lead(u, x):
    """A margin for the winner as 'Name +x' for whoever led."""
    return f"{u['winner']} +{x:.1f}" if x > 0 else f"{u['loser']} +{-x:.1f}" if x < 0 else "a tie"


def versus(ch):
    """Which models and markets beat us, tied or trailed on the races they covered, by races right and by Brier score."""
    rows = [b for b in B[ch] if b["kind"] in ("model", "market") and b.get("right_ours_same") is not None]
    if not rows:
        return ""
    more = [short(b["name"]) for b in rows if b["right"] > b["right_ours_same"]]
    fewer = [short(b["name"]) for b in rows if b["right"] < b["right_ours_same"]]
    brier = [short(b["name"]) for b in rows if b.get("brier") is not None and b["brier"] < b["brier_ours_same"]]
    return (f"in the {RACES_OF[ch]}, {len(more)} of {len(rows)} got more right than we did on the same races"
            + (f" ({esc(', '.join(more))})" if more else "") + f", {len(fewer)} fewer"
            + (f", and {len(brier)} had a better Brier score ({esc(', '.join(brier))})." if brier else ", and none had a better Brier score."))


def close_versus(ch):
    c = A[ch]["close"]
    ours = next(x for x in c["sources"] if x["name"] == "This forecast")
    better = sorted((x for x in c["sources"] if x["right"] > ours["right"] and x["name"] != "This forecast"), key=lambda x: -x["right"])
    return (f"In the {c['n']} close {RACES_OF[ch].replace('the ', '')} we got {ours['right']} right"
            + (f"; {len(better)} sources did better: " + "; ".join(f"{esc(short(x['name']))} {x['right']}" for x in better) + "." if better else ", as well as anyone."))


def sc_sentence():
    sc = next((u for u in A["senate"]["upsets"] if u["key"] == "South Carolina"), None)
    if not sc or sc.get("prior_winner") is None or sc.get("poll_avg_winner") is None:
        return ""
    return (f" South Carolina is the one we should have come closer on: {len(sc['polls'])} polls averaged {lead(sc, sc['poll_avg_winner'])}, but"
            f" our fundamentals prior ({lead(sc, sc['prior_winner'])}) pulled the forecast to {lead(sc, sc['forecast_margin_winner'])}.")


def caught_line(ids):
    parts = [f"{esc(short(b['name']))} {len(b['upsets_caught'])}" for b in (find("house", i) for i in ids) if b]
    return ("Of the models and markets: " + ", ".join(parts) + ".") if parts else ""


def house_models_line():
    full = [b for b in house_models if b["n"] >= 100]
    if not full:
        return ""
    best = sorted(full, key=lambda b: -b["right"])
    better = [b for b in best if b["right"] > b["right_ours_same"]]
    lead = ("Every model and market with district odds did better." if len(better) == len(best)
            else f"{len(better)} of the {len(best)} models and markets with district odds did better.")
    return (f"{lead} On the same {best[0]['n']} competitive districts, where we got "
            f"{best[0]['right_ours_same']} right: " + "; ".join(f"{esc(short(b['name']))} {b['right']}" for b in best) + ".")


# ---------- hand-written claims, checked against the data ----------
# The prose below states these facts in words. If a recount, a withdrawn call or new research makes one false, the build stops
# here instead of publishing a stale sentence; update the text, then the check.

def _u(ch, key):
    return next((u for u in A[ch]["upsets"] if u["key"] == key), None)


def _models_right(u):
    return [m for m in u["models"] if m["right"]]


def _raters_right(u):
    return [k for k, v in u["ratings"].items() if _side(v) == ("R" if u["winner_party"] == "R" else "D")]


CLAIMS = {
    "Mississippi and South Carolina are the Senate upsets, both Democratic": sorted(s["key"] for s in A["senate"]["upsets"]) == ["Mississippi", "South Carolina"]
        and all(u["winner_party"] == "D" for u in A["senate"]["upsets"]),
    "no source favored Colom (Mississippi)": _u("senate", "Mississippi") is not None and not _models_right(_u("senate", "Mississippi"))
        and not _raters_right(_u("senate", "Mississippi")),
    "only one model (On Point) favored Andrews (South Carolina)": _u("senate", "South Carolina") is not None
        and [m["id"] for m in _models_right(_u("senate", "South Carolina"))] == ["onpoint"] and not _raters_right(_u("senate", "South Carolina")),
    "every House upset went to the Democrat": all(u["winner_party"] == "D" for u in A["house"]["upsets"]),
    "Vermont is the only Republican upset, and every rater, model and market favored Scott": [u["key"] for u in ALL_UPSETS if u["winner_party"] == "R"] == ["Vermont"]
        and all(m["right"] for m in _u("governors", "Vermont")["models"]) and len(_raters_right(_u("governors", "Vermont"))) == 3,
    "most models and both markets called Nevada right": _u("governors", "Nevada") is not None
        and 2 * len(_models_right(_u("governors", "Nevada"))) > len(_u("governors", "Nevada")["models"])
        and {"polymarket", "kalshi"} <= {m["id"] for m in _models_right(_u("governors", "Nevada"))},
    "Texas governor was missed by everyone": _u("governors", "Texas") is not None and not _models_right(_u("governors", "Texas"))
        and not _raters_right(_u("governors", "Texas")),
    "TX-9, 15, 23, 35 and NC-6, 9, 13, 14 are all upsets": all(_u("house", k) for k in ("TX-9", "TX-15", "TX-23", "TX-35", "NC-6", "NC-9", "NC-13", "NC-14")),
    "the NC upsets were 4-11% and won by 2-3 points": all(.035 <= _u("house", k)["p_winner"] <= .115 and 1.5 <= (_u("house", k)["actual_margin_winner"] or 0) <= 3.5
                                                       for k in ("NC-6", "NC-9", "NC-13", "NC-14")),
    "no rule change rescues Mississippi, South Carolina, TX-9, NJ-2 or the NC seats": not any(
        k in v["upsets_fixed"] for ch in CHS for v in CF[ch] for k in ("Mississippi", "South Carolina", "TX-9", "NJ-2", "NC-6", "NC-9", "NC-13", "NC-14")),
    "Democratic internals were among the most accurate (Impact, GBAO: below-median miss, right on most upsets they polled)": all(
        any(p["pollster"] == n and p["mae"] is not None and p["mae"] < statistics.median(q["mae"] for q in pollsters if q["races"] >= 8 and q["mae"] is not None)
            and p["upsets_polled"] and p["upsets_right"] / p["upsets_polled"] >= .75 for p in pollsters) for n in ("Impact Research", "GBAO")),
    "the House result ran past every forecaster's median": all((v.get("house_median_dem") or 0) < A["seats"]["house_d"]
                                                               for v in list((A.get("control") or {}).values()) + [A["seats"]["ours"]] if isinstance(v, dict)),
}
bad = [k for k, ok in CLAIMS.items() if not ok]
if bad:
    raise SystemExit("review.html not written; these sentences no longer match the data:\n  " + "\n  ".join(bad))


PSHIFT = json.loads((HERE / "frozen" / "house_model.json").read_text())["params"]["weights"]["partisan_shift"]
_biased = [p for p in pollsters if p["bias_d"] is not None and p["races"] >= 3]
under_d = f"{sum(p['bias_d'] > 0 for p in _biased)} of the {len(_biased)} pollsters with 3 or more called races underestimated Democrats on average"
upset_cards = "".join(appendix_card(u) for u in sorted(ALL_UPSETS, key=lambda u: (CHS.index(u["ch"]), u["p_winner"])))
pollster_rows = "".join(
    f"<tr><td>{esc(p['pollster'])}</td><td class='dim'>{ {'none': 'Independent', 'D': 'Democratic internal', 'R': 'Republican internal'}.get(p['mostly'], esc(p['mostly'])) }</td>"
    f"<td class='num'>{p['races']}</td><td class='num'>{p['right']}</td><td class='num'>{p['ties'] or '–'}</td><td class='num'>{num(p['bias_d'])}</td><td class='num'>{num(p['mae'], '.1f')}</td>"
    f"<td class='num'>{frac(p['upsets_right'], p['upsets_polled']) if p['upsets_polled'] else '–'}</td>"
    f"<td class='dim'>{esc(', '.join(x['race'] + (' ✓' if x['ok'] else ' =' if x['tie'] else ' ✗') for x in p['upsets']))}</td></tr>"
    for p in pollsters if p["races"] >= 3 or p["upsets_polled"])
nat_rows = "".join(
    f"<tr><td>{esc(p['pollster'])}</td><td class='num'>D+{p['d_margin']:g}</td><td class='num'>{p['error']:+.1f}</td><td class='num'>{p['house_right']}</td>"
    f"<td class='num'>{p['house_d']}</td><td class='num'>{len(p['upsets_caught'])}</td></tr>" for p in NATL["polls"])
cf_rows = "".join(
    f"<tr class='{'mine' if v['key'] == 'frozen' else 'hind' if v['key'] == 'hindsight' else ''}'><td>{esc(v['label'])}</td>"
    + "".join(f"<td class='num'>{CFV[ch][v['key']]['right'] if v['key'] in CFV[ch] else '–'}</td>" for ch in CHS)
    + f"<td class='num'>{v['close_right']} of {v['close_n']}</td><td class='num'>{v['brier']:.3f}</td><td class='num'>{v['bias']:+.1f}</td>"
    f"<td class='dim'>{esc(', '.join(v['upsets_fixed'])) or '–'}</td></tr>" for v in CF["house"])

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 Upsets and Misses</title>
<style>{css}
.dim {{ color:var(--muted) }} td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums }} .note {{ color:var(--muted); font-size:13px }}
.pt {{ font-weight:600 }} .pt.D {{ color:var(--dem) }} .pt.R {{ color:var(--rep) }} .pt.I {{ color:var(--ind) }}
.chip {{ display:inline-block; padding:1px 9px; border-radius:10px; font-weight:700; font-size:12px; white-space:nowrap }}
.chip.D {{ background:var(--dem-bg); color:var(--dem) }} .chip.R {{ background:var(--rep-bg); color:var(--rep) }} .chip.I {{ background:var(--ind-bg); color:var(--ind) }}
.banner {{ background:var(--deep-bg); color:var(--fg); border-radius:8px; padding:8px 12px; margin:0 0 16px; font-size:13px }}
.prose {{ max-width:860px }} .prose p, .prose li {{ font-size:14.5px }} .prose li {{ margin:0 0 6px }}
h2 {{ font-size:20px; margin:36px 0 8px; padding-top:8px; border-top:1px solid var(--line) }} h3 {{ font-size:15px; margin:22px 0 6px }}
h4 {{ font-size:13px; margin:12px 0 4px }}
nav.toc {{ font-size:13px; margin:0 0 18px }} nav.toc a {{ color:inherit; margin-right:12px }}
tr.sub td {{ font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase; padding-top:12px }} tr.result td {{ border-top:2px solid var(--line) }} tr.mine td {{ background:var(--conf-bg); font-weight:600 }} tr.hind td {{ color:var(--muted); font-style:italic }}
td.key {{ font-weight:600; white-space:nowrap }} td.key a {{ color:inherit }}
.meter {{ display:inline-block; width:70px; height:6px; border-radius:3px; background:var(--line); vertical-align:1px; overflow:hidden }}
.meter i {{ display:block; height:100%; background:var(--fg); opacity:.55 }}
table.board td {{ white-space:nowrap }}
.nstrip {{ margin:8px 0 2px; padding:0 8px }} .nstrip .plot {{ position:relative; border-bottom:1px solid var(--line); margin-top:34px }}
.nstrip .dot {{ position:absolute; width:9px; height:9px; margin-left:-4.5px; border-radius:50%; background:var(--dem-mark); box-shadow:0 0 0 2px var(--card) }}
.nstrip .vline {{ position:absolute; top:-30px; bottom:0; border-left:2px solid var(--fg) }}
.nstrip .vline em {{ position:absolute; top:-2px; left:4px; font-style:normal; font-size:11px; white-space:nowrap; color:var(--fg); font-weight:600 }}
.nstrip .vline.inp {{ border-left-style:dashed; border-color:var(--muted) }} .nstrip .vline.inp em {{ color:var(--muted); top:12px }}
.nstrip .vline.avg {{ border-left-style:dotted; border-color:var(--muted) }} .nstrip .vline.avg em {{ color:var(--muted); top:-16px }}
.nstrip .vline.act {{ border-color:var(--deep) }} .nstrip .vline.act em {{ color:var(--deep) }}
.nstrip .ticks {{ position:relative; height:16px }} .nstrip .tk {{ position:absolute; transform:translateX(-50%); font-size:11px; color:var(--muted) }}
.bars {{ display:grid; gap:6px; max-width:620px }} .brow {{ display:grid; grid-template-columns:170px 1fr 48px; gap:8px; align-items:center; font-size:13px }}
.btrack {{ height:12px; background:transparent; border-left:1px solid var(--line) }} .btrack i {{ display:block; height:100%; border-radius:0 4px 4px 0 }}
.btrack i.D {{ background:var(--dem-mark) }} .btrack i.R {{ background:var(--rep-mark) }}
details.up {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 14px; margin:0 0 8px }}
details.up summary {{ cursor:pointer; padding:4px 0 }} details.up[open] summary {{ margin-bottom:6px; border-bottom:1px solid var(--line); padding-bottom:8px }}
details.up p.sum {{ font-size:14px }}
.grid3 {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px }} @media (max-width:900px) {{ .grid3 {{ grid-template-columns:minmax(0,1fr) }} }}
ul.lst {{ margin:4px 0; padding-left:18px; font-size:13px }} ul.lst li {{ margin:0 0 3px }}
ul.lst li.ok::marker {{ content:"✓  "; color:var(--conf) }} ul.lst li.no::marker {{ content:"✗  "; color:var(--muted) }} ul.lst li.tie::marker {{ content:"=  "; color:var(--muted) }}
.tag {{ display:inline-block; font-size:10.5px; font-weight:700; text-transform:uppercase; padding:0 5px; border-radius:4px; margin-right:4px }}
.tag.fact {{ background:var(--conf-bg); color:var(--conf) }} .tag.interp {{ background:var(--deep-bg); color:var(--deep) }}
.lessons li {{ margin-bottom:10px }}
</style></head><body><main>
{site.nav("review.html")}
<h1>Upsets and misses: a review of the 2026 forecast</h1>
<p class="lede">How the frozen Nov 3 forecast did against the results and against other forecasters, where it went wrong, why, and what to change
for 2028. Draft as of {esc(pt(A['as_of']))}: {tot_called} of {sum(S[c]['n'] for c in CHS)} races called; counts are AP's and still moving.</p>
<p class="banner"><b>Draft.</b> Still uncalled: {esc('; '.join([f"{x} Senate" for x in S['senate']['uncalled']] + [f"{x} governor" for x in S['governors']['uncalled']])) or 'no statewide race'} and
{len(S['house']['uncalled'])} House seats. Numbers will change as counting, recounts and certification finish. Other forecasters' numbers marked † come from news reports rather than their own files.</p>
<nav class="toc"><a href="#s1">1. How we did</a><a href="#s2">2. Where we went wrong</a><a href="#s3">3. Post-mortem</a>
<a href="#s4">4. Who called the close ones</a><a href="#s5">5. Summary and 2028</a><a href="#appA">Appendix: every upset</a><a href="#appB">Pollsters</a><a href="#appC">Sources</a></nav>

<h2 id="s1">1. How we did, overall and against the professionals</h2>
<div class="summary">
 <div class="card"><b>{frac(tot_right, tot_called)}</b><span>called races where our favorite won</span></div>
 <div class="card"><b>{tot_up}</b><span>upsets; the forecast's own odds implied about {tot_exp:.0f}</span></div>
 <div class="card"><b>{frac(h['close_right'], h['close_n'])}</b><span>House races we rated 20–80% that we got right</span></div>
 <div class="card"><b>D+{NATL['actual']:g}</b><span>national House vote ({NATL['eevp']:.0f}% counted); we assumed D+{NATL['model_input']:g}</span></div>
</div>
<div class="prose">
<p>The scorecard shows this forecast with more races right than the expert raters in every chamber. That comparison flatters us. We never
say "toss-up": every race gets a favorite, so we get credit for every coin flip that lands our way, while Cook and Inside Elections leave their
hardest races uncalled. Scored only on the close races, the picture changes. We rated {h['close_n']} House races between 20% and 80% and got
{h['close_right']} right, a coin flip, where our own odds said we should get about {h['close_expected']:.0f}. In {close_fav_r} of those races we
made the Republican the favorite, and Democrats won {close_fav_r_lost} of them.</p>
<p>The fairest single comparison is with Sabato's Crystal Ball, which, like us, made a call in every race. It beat us in the House
({sab['house']['right']} to {h['right']} of {h['called']}) and in governors' races ({sab['governors']['right']} to {g['right']}); we beat it in the
Senate ({s_['right']} to {sab['senate']['right']}). Against the other models and the betting markets: {versus('senate')} {versus('governors')[0].upper() + versus('governors')[1:]}
The House was the clear loss. {house_models_line()} And {nat_beat} of the {len(nat_best)} final
national generic-ballot polls, applied evenly to every district, would have called more House races right than our district model did.</p>
</div>
"""
for ch in CHS:
    page += f"<h3>{TITLE[ch]}</h3>" + scoreboard(ch)
page += f"""<p class="note">Right and wrong are counted on races AP has called. A toss-up counts as half in the score. Models and markets are scored only on the races
they published odds for; the Brier column (0 is perfect, 0.25 is a coin flip) puts ours on exactly the same races in brackets. "Our upsets it
caught" counts races where our underdog won and this source had favored the winner. The national poll row applies that poll's national margin as an
even swing from each seat's 2024 presidential result.</p>
<h3>Chamber control: the final odds</h3>
<div class="scroll"><table class="small"><thead><tr><th>Forecaster</th><th class="num">Senate: Democratic control</th><th class="num">Median Democratic seats</th>
<th class="num">House: Democratic control</th><th class="num">Median Democratic seats</th></tr></thead><tbody>{control_table()}</tbody></table></div>
<p class="note">Seat medians count independents with Democrats. Every forecaster favored Democrats in both chambers; in the House the result
ran past every forecaster's median.</p>

<h2 id="s2">2. Where we went wrong</h2>
<div class="prose">
<p>{tot_up} favorites lost: {len(s_['upsets'])} in the Senate, {len(h['upsets'])} in the House, {len(g['upsets'])} for governor. Every House upset and both
Senate upsets went to the Democrat. Upsets were expected, about {tot_exp:.0f} of them from our own odds, but they should have broken both ways.
When {sum(S[c]['upsets_by_winner'].get('D', 0) for c in CHS)} of {tot_up} break the same way, the misses are one error, not {tot_up}: the whole forecast
sat too far to the right. Each upset is written up in <a href="#appA">the appendix</a>.</p>
</div>
<h3>Senate: {len(s_['upsets'])} upsets in {s_['called']} called races</h3>
<div class="prose"><p>Both misses were in the Deep South and both went to Democrats. No forecaster, rater or market we found favored Scott Colom in Mississippi,
and only one little-known model favored Annie Andrews in South Carolina, so these were shared misses.{sc_sentence()} Mississippi had only two polls, both showing Hyde-Smith ahead; reporting credits a surge in
Black turnout that no poll captured.</p></div>
{upset_table("senate")}
<h3>House: {len(h['upsets'])} upsets in {h['called']} called races</h3>
<div class="prose"><p>The House is where the forecast failed. The misses cluster in three places:</p><ul>
<li><b>Texas's new map:</b> TX-9, 15, 23 and 35, seats drawn to be Trump +10 to +20, all went Democratic. In competitive Texas seats Democrats ran
{ERR['house']['competitive_by_state'].get('TX', {}).get('mean', 0):+.1f} points better than we forecast on average.</li>
<li><b>North Carolina:</b> NC-6, 9, 13 and 14, which we gave 4–11%, each went Democratic by 2–3 points (competitive NC seats:
{ERR['house']['competitive_by_state'].get('NC', {}).get('mean', 0):+.1f}).</li>
<li><b>The Midwest and battleground suburbs:</b> Ohio (7, 9, 10, 15), Michigan (4, 10), Wisconsin's 1st, Indiana's 5th, Pennsylvania's 1st, where
the polls were close and we leaned Republican almost every time.</li></ul>
<p>Sabato's final ratings caught {len(sab['house']['upsets_caught'])} of our {len(h['upsets'])} House upsets, Cook {len(cook['house']['upsets_caught'])};
{caught_line(('polymarket', 'splitticket'))}
{house_models_line()}</p></div>
{upset_table("house")}
<h3>Governors: {len(g['upsets'])} upsets in {g['called']} called races</h3>
<div class="prose"><p>The one upset that went to a Republican was here: Phil Scott in Vermont, whom every rater, model and market favored. We gave
him 27% because the state's only frequent pollster, UNH's opt-in panel, had him well behind; it has now underestimated him three cycles running.
Nevada was a near coin flip that most models and both markets called right; Texas (Hinojosa) was missed by everyone.</p></div>
{upset_table("governors")}

<h2 id="s3">3. Post-mortem</h2>
<h3>The national environment was the big miss</h3>
<div class="prose"><p>The House forecast starts from the national generic ballot. The October average was D+{NATL['average']:g}; we shaded it a point
toward Republicans, because generic-ballot polls have overstated Democrats in 7 of the last 10 cycles, and used D+{NATL['model_input']:g}. AP's
national House count is D+{NATL['actual']:g}. We were {nat_input_err:.1f} points short, and the shading made it worse: {NATL['closer_than_input']} of
{len(NATL['polls'])} final national polls were closer to the result than our input. The poll closest to the result was AtlasIntel, at D+14.1.</p></div>
<div class="panel">{national_strip()}<p class="note" style="margin:6px 0 0">Each dot is one final national House poll (hover for the pollster).
Seat-by-seat counts don't add up to the national vote exactly: uncontested seats inflate it.</p></div>

<h3>The errors ran one way, and further in safe Republican seats</h3>
<div class="prose"><p>In {ERR['house']['d_better']} of {ERR['house']['n']} called House races Democrats beat our forecast margin; the average error was
{ERR['house']['mean']:+.1f} points (Senate {ERR['senate']['mean']:+.1f}, governors {ERR['governors']['mean']:+.1f}). The model shrinks the national swing
in lopsided seats, on the theory that safe seats move less. This year the deepest red seats moved the most:</p></div>
<div class="panel"><h4 style="margin-top:0">House: average margin error by 2024 presidential margin (+ = Democrats did better than forecast)</h4>
{bars(ERR['house']['by_pres'], ['Harris +10 or more', 'Harris +0 to 10', 'Trump +0 to 10', 'Trump +10 to 20', 'Trump +20 or more'])}
<h4>Competitive House seats, states with 3 or more</h4>
{bars(ERR['house']['competitive_by_state'], list(ERR['house']['competitive_by_state']))}</div>

<h3>Which of our rules cost us</h3>
<div class="prose"><p>To separate bad luck from bad rules, the frozen model was rerun with one rule changed at a time, on the same polls and the same
random draws; the unchanged rerun reproduces the published forecast exactly. The last row uses the actual national vote: hindsight, shown only
to measure how much of the miss was the national number.</p></div>
<div class="scroll"><table class="small"><thead><tr><th>Rule changed</th><th class="num">Senate right</th><th class="num">House right</th><th class="num">Governors right</th>
<th class="num">House close races right</th><th class="num">House Brier</th><th class="num">House avg error</th><th>House upsets it would have caught</th></tr></thead>
<tbody>{cf_rows}</tbody></table></div>
<div class="prose">
<p>Three things stand out:</p><ul>
<li><b>We discounted the polls that were right.</b> Partisan polls are shifted {PSHIFT:g} points
against their sponsor and given half weight. This year Democratic internal polls (Impact Research, GBAO, PPP for House Majority PAC, Hart) were
among the most accurate in the field and were the polls most likely to show the upset winners ahead. Removing the shift alone fixes
{len(cfh['no_partisan_shift']['upsets_fixed'])} House upsets and Nevada governor and cuts the House Brier score from {cfh['frozen']['brier']:.3f} to
{cfh['no_partisan_shift']['brier']:.3f}. One cycle is not proof: the shift exists because internals usually do overstate their side.</li>
<li><b>The 1-point shading pointed the wrong way</b>, and on its own fixes only {len(cfh['no_shade']['upsets_fixed'])} races. With both changes the House
goes from {cfh['frozen']['right']} to {cfh['both']['right']} right and close races from {cfh['frozen']['close_right']} to {cfh['both']['close_right']} of {cfh['both']['close_n']}.</li>
<li><b>Even perfect knowledge of the national vote leaves an average error of {cfh['hindsight']['bias']:+.1f}</b> in the House, and no rule change
rescues Mississippi, South Carolina, TX-9, NJ-2 or the North Carolina seats. Those were not misreadings of the polls. The electorate itself was
different from the one the fundamentals assumed.</li></ul>
<h3>What no rule would have caught</h3>
<ul>
<li><b>Who turned out.</b> Reporting on the Deep South upsets (Mississippi, South Carolina, AL-2) and North Carolina credits a surge in Black turnout;
in Mississippi the Black share of the electorate rose from about 30% to 33%, and on the 2024 electorate Hyde-Smith would have won. Our House prior
is built from 2024 presidential margins, which bakes in the 2024 electorate.</li>
<li><b>Latino voters in South Texas swung back.</b> The 2025 Texas map assumed Trump's 2024 Latino gains would hold. Voter surveys put Latino voters
around 65–70% Democratic this year; all four border-area seats flipped and the Texas governor's race was, by some accounts, the largest statewide
polling miss in the state's history.</li>
<li><b>Candidates and campaigns.</b> Several Republican nominees were weak (Darline Graham, appointed after Lindsey Graham's death; Brandon Herrera
in TX-23), and some Democrats won while badly outspent (NC-14 on about $56,000). Our House model has no candidate-quality term.</li>
<li><b>The other direction.</b> Vermont's Phil Scott is a reminder that a single, systematically wrong pollster can sink a thinly polled race.</li></ul>
<h3>Lessons</h3>
<ol class="lessons">
<li><b>A model is only as good as its national number.</b> Most of the House miss traces to the generic ballot. Shading it by a historical
average added error this year; the honest version is to keep the uncertainty and drop the directional tilt.</li>
<li><b>Correlated error has to show up in the race odds, not just the seat totals.</b> The model simulates a national error, but it called
{close_fav_r} close races for Republicans and they broke {close_fav_r_lost}–{close_fav_r - close_fav_r_lost} the other way. When most close races lean
one way, a single national error flips them together, and the overview should say so.</li>
<li><b>Treat partisan polls by track record, not by rule.</b> A fixed {PSHIFT:g}-point penalty for every internal poll threw away the best signal in the
races that decided the House.</li>
<li><b>The prior should yield faster to polls.</b> South Carolina had 18 polls and the prior still moved the margin 0.6 points; with a lighter prior the
House would have caught MT-1 and the Senate odds would have been less confident.</li>
<li><b>New maps need wider error.</b> Redrawn seats are scored on 2024 margins from a different electorate. Texas and North Carolina, both on 2025 mid-decade maps, had
the largest misses among states with many competitive seats.</li>
<li><b>Calling every race is fine, but the scorecard must be honest about it.</b> "Most races right" mostly reflects not using a toss-up category.
Report the close-race record and the Brier score alongside it.</li></ol>
</div>

<h2 id="s4">4. Who called the close ones</h2>
<div class="prose"><p>These are the races we rated too close to call (20–80%). For each source: how many it made a call on, how many of those were
right, and how its confident calls did (Likely or stronger for raters; 70% or more for models and markets). Leaving a race as a toss-up is not
wrong, but it is not a call either.</p>
<p>In the House, the sources willing to commit did best. {close_line()} Sabato's Crystal Ball eliminated every toss-up on Nov 2 and
broke the last 17 House toss-ups 14–3 toward Democrats. {close_versus('senate')} {close_versus('governors')} Cook and Inside Elections left the most races
uncalled, so they were seldom wrong but seldom useful in exactly the races that mattered.</p></div>
"""
for ch in CHS:
    page += f"<h3>{TITLE[ch]}: {A[ch]['close']['n']} close races</h3>" + close_table(ch)
top_nat = sorted(NATL["polls"], key=lambda p: -p["d_margin"])[:3]
page += f"""
<h3>Pollsters who saw the upsets coming</h3>
<div class="prose"><p>Nationally, the polls that best anticipated the upsets were the ones with the biggest Democratic margins:
{esc(', '.join(f"{p['pollster']} (D+{p['d_margin']:g})" for p in top_nat))}. Applied evenly to every district, {esc(top_nat[0]['pollster'])}'s number alone catches
{len(top_nat[0]['upsets_caught'])} of the {len(h['upsets'])} House upsets. In the districts, the polls that had the upset winners
ahead were mostly Democratic internals:
{esc('; '.join(f"{p['pollster']} {p['upsets_right']} of {p['upsets_polled']}" for p in sorted(dint, key=lambda p: -p['upsets_right'] / p['upsets_polled'])))}.
Among independent pollsters with 8 or more races, the most accurate were
{esc('; '.join(f"{p['pollster']} ({p['right']} of {p['races']} right, average miss {p['mae']:.1f})" for p in indep[:4]))}.
{under_d}. The full table is in <a href="#appB">Appendix B</a>.</p></div>

<h2 id="s5">5. Summary, and what to change for 2028</h2>
<div class="prose">
<p><b>Summary.</b> The forecast called the Senate about as well as anyone and favored the right party for control of both chambers. It was
slightly behind the field on governors and clearly behind every other model and market in the House. It underestimated Democrats almost everywhere, by {ERR['house']['mean']:.1f} points in the average House race. Most of that was the national
environment: we started from a generic-ballot number that was already low and lowered it further. On top of that, the rules for partisan polls
threw away the information that pointed to the upsets, and a fundamentals prior built on 2024 margins could not see a changed electorate. Upsets
themselves were expected; {tot_up} of them, all but one in one direction, were not.</p>
<p><b>Changes for 2028</b> (rule-based, set before any 2028 polls, and tested on 2018–2026 before use):</p>
<ol class="lessons">
<li><b>National environment without a directional tilt.</b> Use the polling average at face value, and widen the national error instead of shading it.
For a presidential year, the national popular-vote polls and the state polls should be tied together explicitly, so a state that moves pulls its
neighbors.</li>
<li><b>Pollster-specific house effects.</b> Replace the flat partisan-sponsor penalty with each firm's measured bias from past cycles, shrunk toward
zero for firms with little history. Track internal polls by sponsor and firm; this year that would have counted Impact and GBAO at close to face value.</li>
<li><b>A lighter prior where polls are plentiful</b>, and an explicit turnout-composition term for the fundamentals (who voted in 2024 versus who is
registered and voting early), so a South Carolina or Mississippi can move before election night.</li>
<li><b>Extra error for redrawn districts and for groups that swung hard last time</b> (Latino voters in South Texas and Florida; rural Black turnout in
the Deep South), applied by rule, not by hand.</li>
<li><b>Publish both directions of polling miss</b> on the overview (D+2, D+3 as well as R+2, R+3), and show how many close races lean each way.</li>
<li><b>Score the forecast honestly</b>: alongside "races right," publish the close-race record, Brier score and calibration, and compare against
Sabato, the markets and the leading models on the same races.</li>
<li><b>For the presidency itself:</b> the Electoral College hinges on 7–8 states, so the state-to-state error correlation matters more than anything
here. Backtest it on 2016, 2020 and 2024, when polls underestimated Republicans, and on 2026, when they underestimated Democrats; a model that
handles both directions without a tilt is the target.</li></ol>
<p class="note">These are proposals for the 2028 model, not changes to the 2026 forecast, which stays frozen as published.</p>
</div>

<h2 id="appA">Appendix A: every upset, seat by seat</h2>
<p class="note">Ordered by how unlikely we said the result was. "Reported" items are facts as reported; "Analysis" items are commentators'
interpretations. Every claim links to its source.</p>
{upset_cards}

<h2 id="appB">Appendix B: pollsters</h2>
<h3>District and state pollsters</h3>
<div class="scroll"><table class="small"><thead><tr><th>Pollster</th><th>Mostly</th><th class="num">Called races polled</th><th class="num">Winner ahead</th><th class="num">Tied</th>
<th class="num">Avg error (+ = D better)</th><th class="num">Avg miss</th><th class="num">Upsets right</th><th>Upset races</th></tr></thead><tbody>{pollster_rows}</tbody></table></div>
<p class="note">Each pollster's latest poll (ending Aug 1 or later) in each called race. Error is AP's current count minus the poll's margin. Pollsters with at least 3 races or any upset race.</p>
<h3>National generic-ballot polls</h3>
<div class="scroll"><table class="small"><thead><tr><th>Pollster</th><th class="num">Final poll</th><th class="num">Result minus poll</th><th class="num">House races right (even swing)</th>
<th class="num">Democratic seats among called</th><th class="num">House upsets caught</th></tr></thead><tbody>{nat_rows}</tbody></table></div>

<h2 id="appC">Appendix C: sources and method</h2>
<div class="method"><ul>
<li><b>Results:</b> AP race calls and AP's current count, as on the scorecard; the national House vote is AP's national aggregate.</li>
<li><b>Expert ratings:</b> each rater's last update before Nov 3 ({esc('; '.join(f"{RATER}: {(A.get('rater_sources') or {}).get(k, {}).get('date', '?')}" for k, RATER in (('cook', 'Cook'), ('sabato', 'Sabato'), ('inside', 'Inside Elections'))))}),
from Wikipedia's prediction tables checked race by race against 270toWin's maps of each rater; the raters' own sites blocked automated reads.</li>
<li><b>Other models and markets:</b> final pre-election runs from each forecaster's published data files, checked against timestamps; Polymarket and
Kalshi prices from the morning of Nov 3. Silver Bulletin's race-level odds are paywalled; only the side it favored is used. 538 published no 2026 model.</li>
<li><b>Reporting on each upset:</b> gathered from news coverage and post-election analysis, with every claim linked.</li>
<li><b>Counterfactuals:</b> review/counterfactuals.py reruns the frozen models with one parameter changed; review/analyze.py builds every number on this page.</li>
</ul></div>
<div id="tip"></div>
<script>
const tip = document.getElementById('tip');
document.querySelectorAll('[data-t]').forEach(el => {{
  el.addEventListener('mouseenter', () => {{ tip.textContent = el.dataset.t; tip.style.display = 'block'; }});
  el.addEventListener('mousemove', e => {{ tip.style.left = (e.clientX + 12) + 'px'; tip.style.top = (e.clientY + 12) + 'px'; }});
  el.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});
}});
</script>
</main></body></html>"""
(HERE / "review.html").write_text(page)
print("review.html written:", len(ALL_UPSETS), "upsets")
