#!/usr/bin/env python3
"""Build governors.html from the model output (gov_model.json) and the audited research (gov_polls.json).
Run governor_model.py first."""
import html
import re
import json
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
CONFIDENT_MARGIN = 6.0  # a swing above this is called without a deep dive (was 10 in the original rule)
CM = f"{CONFIDENT_MARGIN:g}"
MAJORITY = 26  # a majority of the 50 governorships

model = json.loads((HERE / "gov_model.json").read_text())
audit = json.loads((HERE / "gov_polls.json").read_text())
comp = json.loads((HERE / "gov_composition.json").read_text())
P = model["params"]
HOLD = P["not_up"]
NOW_D = comp["current_governors"]["D"]


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def signed(m, ch, rep):
    if m is None:
        return "—"
    if abs(m) < 0.05:
        return "Even"
    return f"{ch} +{m:.1f}" if m > 0 else f"{rep} +{-m:.1f}"


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{p:.0%}"

def fav(r, sep=" ", p_key="p_challenger"):
    """'Name NN%' for whichever side the model favors: race chances are always quoted for the leader."""
    p = r[p_key]
    return f"{r['challenger']}{sep}{pct(p)}" if p >= 0.5 else f"{r['rep']}{sep}{pct(1 - p)}"



def name(full):
    """Candidate name without running-mate or party annotations, for the table."""
    full = re.split(r",\s*running mate|\(running mate|;", full or "—")[0]
    return re.sub(r"\s*\((D|R|I|DFL|incumbent|leading Republican|also [^)]*)\)?\s*$", "", full).strip()


def link(url, text):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>' if url else esc(text)


# ---- headline numbers and chart ---------------------------------------------------------------------
dist = {int(k): v for k, v in model["dist_d"].items()}
ks = [k for k in sorted(dist) if dist[k] >= 0.0005]
kmin, kmax = ks[0], ks[-1]
W_, H_, PL, PB, PT = 760, 230, 36, 34, 26
bw = (W_ - PL - 8) / (kmax - kmin + 1)
ymax = max(dist.values())
bars, ticks = [], []
for k in range(kmin, kmax + 1):
    v = dist.get(k, 0)
    h = (H_ - PB - PT) * v / ymax
    x = PL + (k - kmin) * bw
    side = "dem" if k >= MAJORITY else "rep"
    tip = f"{k} Democratic governors · {v:.1%} of simulations"
    bars.append(f'<rect class="bar {side}" x="{x + 1:.1f}" y="{H_ - PB - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" rx="2"></rect>'
                f'<rect class="hit" x="{x:.1f}" y="{PT}" width="{bw:.1f}" height="{H_ - PB - PT}" data-tip="{esc(tip)}"></rect>')
    ticks.append(f'<text x="{x + bw / 2:.1f}" y="{H_ - PB + 16}" text-anchor="middle">{k}</text>')
xm = PL + (MAJORITY - kmin) * bw
chart = f"""<svg viewBox="0 0 {W_} {H_}" role="img" aria-label="Distribution of Democratic governorships across {P['sims']:,} simulations">
  {''.join(ticks)}<line class="axis" x1="{PL}" x2="{W_ - 8}" y1="{H_ - PB}" y2="{H_ - PB}"></line>{''.join(bars)}
  <line class="majority" x1="{xm:.1f}" x2="{xm:.1f}" y1="{PT - 6}" y2="{H_ - PB}"></line>
  <text class="lbl" x="{xm + 4:.1f}" y="{PT - 12}">26 = majority of governors</text>
  <text x="{(W_ + PL) / 2:.0f}" y="{H_ - 2}" text-anchor="middle">Democratic governors after Nov 3 (of 50)</text></svg>"""
sc_rows = "".join(f"<tr><td>{esc(s['label'])}</td><td class='num'>{s['leaders_D']}</td><td class='num'>{s['median_D']:.0f}</td>"
                  f"<td class='num'>{pct(s['p_d_majority'])}</td></tr>" for s in model["scenarios"])

# ---- race rows ----------------------------------------------------------------------------------------
rows, flips = [], []
lead_tally = {"D": HOLD["D"], "R": HOLD["R"], "I": HOLD.get("I", 0)}
for r in sorted(model["races"], key=lambda r: r["state"]):
    st, a = r["state"], audit[r["state"]]
    ch, rep, p = r["challenger"], r["rep"], r["p_challenger"]
    opp = r["opponent_party"]
    lead_party = r["challenger_party"] if r["mean"] > 0 else opp
    lead_tally[lead_party] += 1
    leader = ch if r["mean"] > 0 else rep
    inc_p = (a.get("incumbent_party") or "")[:1]
    flip = inc_p and inc_p != lead_party
    if flip:
        flips.append((st, inc_p, lead_party))
    swing = abs(r["poll_avg"]) if r["poll_avg"] is not None else abs(r["mean"])
    rule = "confident" if swing > CONFIDENT_MARGIN else "deep"
    win_p = p if r["mean"] > 0 else 1 - p
    cls = {"D": "dem", "R": "rep", "I": "ind"}[lead_party]
    b = a["ballot"]
    open_txt = "" if a.get("incumbent_running") else f"Open: {a.get('open_reason') or 'not running'}"
    pbar = (f"<div class='pbar'><i class='dem' style='width:{p * 100:.1f}%'></i>"
            f"<i class='{'rep' if opp == 'R' else 'ind'}' style='width:{(1 - p) * 100:.1f}%'></i></div>")

    prow = []
    for q in sorted(r["polls"], key=lambda x: x["end"], reverse=True):
        tag = (f"<span class='tag {'dem' if q['partisan'] == 'D' else 'rep'}'>{q['partisan']}-sponsored</span>" if q.get("partisan")
               else f"<span class='tag soft'>{q['lean']}-leaning</span>" if q.get("lean") else "")
        resv = ", ".join(f"{k} {v:g}" for k, v in q["results"].items() if isinstance(v, (int, float)))
        prow.append(f"<tr><td>{esc(q['end'])}</td><td>{link(q.get('url'), q['pollster'])}{' · ' + esc(q['sponsor']) if q.get('sponsor') else ''} {tag}</td>"
                    f"<td>{esc(q.get('n') or '?')} {esc(q.get('pop') or '')}</td><td>{esc(resv)}</td><td class='num'>{q['raw_margin']:+.1f}</td>"
                    f"<td class='num'>{(q['adj'] or 0):+.1f}</td><td class='num'>{q['share']:.0%}</td><td>{'✓' if q.get('verified') else '<span class=muted>table</span>'}</td></tr>")
    polltable = (f"<table class='inner'><thead><tr><th>Ended</th><th>Pollster</th><th>Sample</th><th>Result</th><th>Margin</th><th>Adj.</th><th>Weight</th><th>Checked</th></tr></thead><tbody>{''.join(prow)}</tbody></table>"
                 if prow else "<p>No public polls with published numbers: the forecast is the fundamentals prior alone, with a wide error band.</p>")
    why = []
    if r["n_polls"]:
        why.append(f"{r['n_polls']} polls (effective {r['n_eff']:g}) average <b>{esc(signed(r['poll_avg'], ch, rep))}</b>"
                   + (f" after removing sponsor lean (unadjusted {esc(signed(r['poll_avg_raw'], ch, rep))})." if r["poll_avg"] != r["poll_avg_raw"] else "."))
    if r["prior"] is not None:
        f = a["fundamentals"]
        pp = r["prior_parts"]
        txt = (f"Fundamentals prior <b>{esc(signed(r['prior'], ch, rep))}</b>: {1 - P['last_gov_weight']:.0%} from the 2024 presidential margin "
               f"({f.get('pres_2024_margin_D'):+g}, shrunk to {P['pres_lean_coef']:g}× the state's lean, plus {P['national_shift_factor']:g}× the national swing"
               f"{', plus incumbency' if a.get('incumbent_running') and (a.get('incumbent_party') or '')[:1] in 'DR' else ''}: {pp.get('pres', 0):+.1f})")
        if "last" in pp:
            txt += f" and {P['last_gov_weight']:.0%} from the last governor result ({esc(f.get('last_gov'))}, adjusted for the national swing since: {pp['last']:+.1f})"
        why.append(txt + f"; it gets <b>{r['prior_weight']:.0%}</b> of the weight.")
    else:
        why.append("No fundamentals prior (an independent is one of the two leading candidates), so the forecast is polls only, with extra uncertainty.")
    why.append(f"Forecast <b>{esc(signed(r['mean'], ch, rep))}</b>, total error SD {r['sd']:g} → {esc(fav(r, ' wins '))} of simulations.")
    claims = "".join(f"<li><span class='st-{c['status'].lower()}'>{esc(c['status'])}</span> {esc(c['claim'])}<span class='sub'>{esc(str(c.get('source', ''))[:240])}</span></li>"
                     for c in a.get("claims", []))
    rt = a.get("ratings") or {}
    prim = a.get("primaries") or {}
    issues = "".join(f"<li>{esc(i)}</li>" for i in a.get("issues") or [])
    others = "; ".join(b.get("others") or [])
    rules = " ".join(x for x in ["Ranked-choice general election." if a.get("rcv") else "", f"Runoff: {a['runoff_rule']}" if a.get("runoff_rule") else ""] if x)
    rows.append(f"""
    <tr class="race {rule}{' tossup' if r['tier'] in ('Toss-up', 'Tilt', 'Lean') else ''}{' flipped' if flip else ''}">
      <td class="st">{esc(st)}<span class="sub">{esc(a.get('incumbent'))} ({esc(inc_p)})</span><span class="sub">{esc(open_txt)}</span></td>
      <td class="dem">{esc(name(b.get('D')))}</td>
      <td class="{'rep' if opp == 'R' else ''}">{esc(name(b.get('R')))}{'<span class="sub">Main opponent: independent ' + esc(rep) + '</span>' if opp != 'R' else ''}</td>
      <td class="num">{r['n_polls'] or '—'}</td>
      <td class="num">{esc(signed(r['poll_avg'], ch, rep))}</td>
      <td class="num">{esc(signed(r['mean'], ch, rep))}<span class="sub">± {r['sd']:g}</span></td>
      <td>{pbar}<span class="sub">{esc(fav(r))}</span></td>
      <td><span class="tag {rule}">{'Swing &gt; ' + CM if rule == 'confident' else 'Deep dive'}</span></td>
      <td class="win {cls}">{esc(r['tier'])} {esc(leader)}{' <span class="flip">FLIP</span>' if flip else ''}<span class="sub">{pct(win_p)}</span></td>
    </tr>
    <tr class="detail {rule}{' tossup' if r['tier'] in ('Toss-up', 'Tilt', 'Lean') else ''}{' flipped' if flip else ''}"><td colspan="9"><details><summary>Evidence: {esc(st)}</summary><div class="dd">
      <div class="wide"><h4>How the number is built</h4><p>{' '.join(why)}</p></div>
      <div class="wide"><h4>Polls (newest first)</h4>{polltable}
        <p class="note">Margin = {esc(ch)} minus {esc(rep)}. Adj. removes {P['weights']['partisan_shift']:g} pts from sponsored polls and {P['weights']['lean_shift']:g} from one-party pollsters.
        "table" = numbers seen only in a secondary polling table (weighted {P['weights']['unverified']:.0%}).</p></div>
      <div><h4>Ballot (audited)</h4><p><b>D:</b> {esc(b.get('D'))}<br><b>R:</b> {esc(b.get('R'))}{'<br><b>Also:</b> ' + esc(others) if others else ''}</p>
        {'<p><b>Withdrawn:</b> ' + esc('; '.join(b.get('withdrawals'))) + '</p>' if b.get('withdrawals') else ''}{'<p>' + esc(rules) + '</p>' if rules else ''}</div>
      <div><h4>Ratings</h4><p>Cook: {esc(rt.get('cook'))} · Sabato: {esc(rt.get('sabato'))} · Inside: {esc(rt.get('inside'))}</p><p class="sub">{esc(rt.get('as_of'))}</p>
        <h4>History</h4><p>Last governor race: {esc(a['fundamentals'].get('last_gov'))}<br>2024 president: {a['fundamentals'].get('pres_2024_margin_D'):+g}</p></div>
      {'<div class="wide"><h4>Fact audit</h4><ul class="claims">' + claims + '</ul></div>' if claims else ''}
      <div class="wide ctx"><h4>Context — not used in the forecast</h4>
        <p><b>D primary:</b> {esc(prim.get('dem'))}</p><p><b>R primary:</b> {esc(prim.get('rep'))}</p>{'<ul>' + issues + '</ul>' if issues else ''}
        {'<p class="note">' + esc(a.get('notes')) + '</p>' if a.get('notes') else ''}</div>
    </div></details></td></tr>""")

TOO_CLOSE = (0.20, 0.80)  # races in this band are listed as "where it's decided" and get an outcome switch
close = sorted((r for r in model["races"] if TOO_CLOSE[0] <= r["p_challenger"] <= TOO_CLOSE[1]), key=lambda r: abs(r["p_challenger"] - 0.5))
flip_txt = ", ".join(f"{s} ({a}→{b})" for s, a, b in flips) or "none"
n_polls = sum(r["n_polls"] for r in model["races"])
css = (HERE / "page.css").read_text()

# ---- scenario simulator (levers) ---------------------------------------------------------------------
E = P["error"]
assert E["t_df"] % 2 == 0, "gov_sim.js draws chi-square for even df only"
sim_regions = sorted({r["sim"]["region"] for r in model["races"]})
sim_data = {"n": 20000, "t_df": E["t_df"], "national_sd": E["national_sd"], "regional_sd": E["regional_sd"],
            "hold": HOLD, "majority": 26, "regions": sim_regions,
            "races": [{"st": r["state"], "ch": r["challenger"], "rp": r["rep"], "chp": r["challenger_party"], "opp": r["opponent_party"],
                       "mean": r["sim"]["mean"], "sd": r["sim"]["sd"], "reg": sim_regions.index(r["sim"]["region"])}
                      for r in model["races"]]}
sim_json = json.dumps(sim_data).replace("</", "<\\/")
sim_js = (HERE / "gov_sim.js").read_text()
PCLS = {"D": "dem", "R": "rep", "I": "ind"}
lever_rows = []
for r in close:
    chp, op = r["challenger_party"], r["opponent_party"]
    lever_rows.append(
        f"<div class='lrow' data-st='{esc(r['state'])}'>"
        f"<span class='lst'>{esc(r['state'])}<span class='sub'>{esc(r['tier'])} · model {esc(fav(r))}</span></span>"
        f"<span class='lbar'><span class='pbar'><i class='ch {PCLS[chp]}'></i><i class='rp {PCLS[op]}'></i></span><span class='sub lp'></span></span>"
        f"<span class='seg' role='group' aria-label='Outcome in {esc(r['state'])}'>"
        f"<button data-v='C' class='{PCLS[chp]}'>{esc(r['challenger'])} ({chp})</button><button data-v=''>Model</button>"
        f"<button data-v='O' class='{PCLS[op]}'>{esc(r['rep'])} ({op})</button></span></div>")

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 Governor Forecast</title>
<style>{css}</style></head><body><main>
{site.nav('governors.html')}
<h1>2026 Governor Forecast</h1>
<p class="lede">36 governorships on the ballot Nov 3, 2026. A probabilistic model built from {n_polls} individual polls, with no race-by-race judgment
adjustments. Today: {NOW_D} D, {50 - NOW_D} R. Not up this year: D {HOLD['D']}, R {HOLD['R']}. Polls through {esc(model['as_of'])}.</p>
<div class="summary">
  <div class="card"><b>{model['pct']['50']}</b><span>Median Democratic governors (today {NOW_D})</span></div>
  <div class="card"><b>{model['pct']['10']}–{model['pct']['90']}</b><span>80% range of Democratic governors</span></div>
  <div class="card"><b style="color:var(--dem)">{pct(model['p_d_majority'])}</b><span>Democrats hold a majority (26+) of governorships</span></div>
  <div class="card"><b>{lead_tally['D']}–{lead_tally['R']}{' –' + str(lead_tally['I']) + ' I' if lead_tally['I'] else ''}</b><span>If every leader wins (D {'+' if lead_tally['D'] >= NOW_D else ''}{lead_tally['D'] - NOW_D})</span></div>
</div>
<div class="grid2">
  <div class="panel"><h3>Democratic governors across {P['sims']:,} simulated elections</h3>{chart}
    <div class="legend"><span><i style="background:var(--dem-mark)"></i>Democratic majority (26+)</span><span><i style="background:var(--rep-mark)"></i>Republican majority or 25-25</span></div></div>
  <div class="panel"><h3>If the polls are off</h3>
    <div class="scroll"><table class="small"><thead><tr><th>Scenario (same shift in every race)</th><th>D if leaders win</th><th>Median D</th><th>P(D 26+)</th></tr></thead><tbody>{sc_rows}</tbody></table></div>
    <p class="note">Governor polls missed by R+8 in 2020 and D-leaning misses of 3-4 happened in 2014 and 2016; the direction does not carry from one cycle to the next.</p>
    <h3 style="margin-top:12px">Seats changing party (if leaders win)</h3><p>{esc(flip_txt)}</p></div>
</div>
<div class="method callout"><b>Where it's decided.</b> {len(close)} races are too close to call (the model gives either side {TOO_CLOSE[0]:.0%} to {TOO_CLOSE[1]:.0%}), closest first:
{', '.join(esc(r['state']) + ' (' + esc(fav(r)) + ')' for r in close)}.</div>
<section class="sim" id="levers"><h2>Try your own scenario</h2>
<p class="note" style="margin:0">Move the levers to see how the balance of governorships changes. The page re-runs {sim_data['n']:,} simulations in your browser on every change,
using the same model and the same random draws each time, so any change you see comes from the lever.</p>
<div class="levers">
  <div class="lever"><label for="sim-swing">Polling miss in every race <output id="sim-swing-out">None</output></label>
    <input id="sim-swing" type="range" min="-10" max="10" step="0.5" value="0">
    <div class="ends"><span>Republicans beat polls by 10</span><span>Democrats by 10</span></div>
    <div class="presets"><button data-preset="-8">R+8 (2020)</button><button data-preset="-3">R+3 (2014/2016)</button><button data-preset="0">None</button><button data-preset="3">D+3</button></div>
    <p class="note" style="margin:6px 0 0">The shift applies to every race; only too-close races are listed below.</p></div>
  <div class="lever"><label for="sim-err">Uncertainty <output id="sim-err-out">×1</output></label>
    <input id="sim-err" type="range" min="0" max="2" step="0.25" value="1">
    <div class="ends"><span>0: every leader wins</span><span>×1 historical</span><span>×2</span></div></div>
</div>
<p id="sim-status-row"><span id="sim-status"></span> <button class="btn" id="sim-reset">Reset all levers</button></p>
<div class="summary">
  <div class="card"><b id="sim-pd" style="color:var(--dem)"></b><span>Democrats hold 26+ governorships</span></div>
  <div class="card"><b id="sim-exp"></b><span>Median Democratic governors (today {NOW_D})</span></div>
  <div class="card"><b id="sim-range"></b><span>80% range</span></div>
  <div class="card"><b id="sim-lead"></b><span>D–R if every leader wins</span></div>
</div>
<div id="sim-chart"></div>
<h3 style="margin:14px 0 0;font-size:14px">Call too-close-to-call races yourself</h3>
<p class="note" style="margin:2px 0">Pick a winner to fix that race; the rest stay simulated, and still move with the national and regional error.
Listed: the {len(lever_rows)} races where the model gives either side between {TOO_CLOSE[0]:.0%} and {TOO_CLOSE[1]:.0%}, closest first.
Bars show each race's chance under your current levers.</p>
<div id="sim-races">{''.join(lever_rows)}</div>
</section>
<details class="method"><summary>Method, parameters and sources</summary><ul>
<li><b>Polling average.</b> Same procedure as the Senate and House sheets: every poll since Aug 1 counted once, weighted by recency (half-life {P['weights']['half_life_days']} days), √sample size,
LV/RV, ×{P['weights']['partisan_sponsor']} for sponsored polls, ×{P['weights']['unverified']} if seen only in a secondary table; sponsored polls shifted {P['weights']['partisan_shift']:g} pts against their sponsor.</li>
<li><b>Fundamentals prior.</b> Governors run far ahead of or behind their party, so this prior is deliberately weak (SD {P['error']['fundamentals_sd']:g}; {P['error']['fundamentals_sd_nopoll']:g} with no polls).
It blends the 2024 presidential margin (state lean × {P['pres_lean_coef']:g}, plus {P['national_shift_factor']:g} × the {P['national_shift']:+g} national swing, plus {P['incumbency_bonus']:g} pts for an incumbent)
with the last governor result adjusted for the swing since ({P['last_gov_weight']:.0%} weight).</li>
<li><b>Correlated error.</b> National SD {P['error']['national_sd']:g}, regional {P['error']['regional_sd']:g}, state {P['error']['state_sd']:g} + sampling; Student-t, {P['error']['t_df']} df. No partisan bias assumed in the baseline.</li>
<li><b>Ranked choice</b> applies only in Alaska; Maine uses plurality for governor. Pollsters' final-round numbers are used where published. Georgia requires a majority (Dec 1 runoff), not modeled since it is a two-candidate race.</li>
<li><b>Tiers</b>: Safe ≥ 99%, Likely ≥ 90%, Lean ≥ 75%, Tilt ≥ 60%, else Toss-up. The {CM}-point rule only flags deep dives (the original sheet used 10).</li>
{''.join(f'<li><b>{esc(k)}</b>: {esc(v)}</li>' for k, v in P.get('sources', {}).items())}
</ul></details>
<h2>Race by race</h2>
<div class="filters"><button class="on" data-f="all">All 36</button><button data-f="tossup">Lean, Tilt &amp; Toss-up</button><button data-f="deep">Deep dives (swing ≤ {CM})</button><button data-f="flipped">Flips</button></div>
<div class="wrap"><table class="main">
<thead><tr><th>State</th><th>Democrat</th><th>Republican</th><th>Polls</th><th>Poll average</th><th>Forecast</th><th>Win probability</th><th>{CM}-pt rule</th><th>Rating</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{site.history('governors.html')}
<footer>Model: governor_model.py + model_params_gov.json; polls, ballot audit and context in gov_polls.json (each poll with its source URL).
Ratings via Wikipedia's ratings table where the raters' sites were unreachable. Margins are the Democrat (or main challenger) minus the opponent, in points.</footer>
</main>
<div id="tip"></div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('table.main > tbody > tr').forEach(tr => {{
    tr.style.display = (f === 'all' || tr.classList.contains(f)) ? '' : 'none';
  }});
}});
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

(HERE / "governors.html").write_text(page)
print(f"governors.html: expected D {model['expected_d']:.1f}; leaders D {lead_tally['D']} R {lead_tally['R']}; flips {flip_txt}")
