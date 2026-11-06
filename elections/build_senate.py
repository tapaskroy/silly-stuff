#!/usr/bin/env python3
"""Build senate.html from the model output (senate_model.json), the audited poll file (senate_polls.json)
and the background research (senate_data.json). Run senate_model.py first."""
import html
import json
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
CONFIDENT_MARGIN = 6.0  # a swing above this is called without a deep dive (was 10 in the original rule)
CM = f"{CONFIDENT_MARGIN:g}"

model = json.loads((HERE / "senate_model.json").read_text())
audit = json.loads((HERE / "senate_polls.json").read_text())
research = {r["state"]: r for r in json.loads((HERE / "senate_data.json").read_text())}
v1 = json.loads((HERE / "senate_calls_v1.json").read_text())
P = model["params"]
HOLD = P["holdover"]


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def signed(m, ch, rep):
    if m is None:
        return "—"
    if abs(m) < 0.05:
        return "Even"
    return f"{ch} +{m:.1f}" if m > 0 else f"{rep} +{-m:.1f}"


def pct(p):
    if p >= 0.995:
        return ">99%"
    if p <= 0.005:
        return "<1%"
    return f"{p:.0%}"

def fav(r, sep=" ", p_key="p_challenger"):
    """'Name NN%' for whichever side the model favors: race chances are always quoted for the leader."""
    p = r[p_key]
    return f"{r['challenger']}{sep}{pct(p)}" if p >= 0.5 else f"{r['rep']}{sep}{pct(1 - p)}"



def link(url, text):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>' if url else esc(text)


# ---- seat distribution and headline numbers -------------------------------------------------------
dist = {int(k): v for k, v in model["seat_dist_d_plus_i"].items()}
exp_seats = sum(k * v for k, v in dist.items())
cum, lo80, hi80, median = 0.0, None, None, None
for k in sorted(dist):
    cum += dist[k]
    if lo80 is None and cum >= 0.10:
        lo80 = k
    if median is None and cum >= 0.50:
        median = k
    if hi80 is None and cum >= 0.90:
        hi80 = k
ctrl = model["control"]
sep = ctrl["separate"]
races = model["races"]
any_ind = [r for r in races if r["challenger_party"] == "I"]

W, H, PAD_L, PAD_B, PAD_T = 760, 220, 36, 34, 14
ks = [k for k in range(min(dist), max(dist) + 1)]
ks = [k for k in ks if dist.get(k, 0) >= 0.0005] or ks
kmin, kmax = ks[0], ks[-1]
bw = (W - PAD_L - 8) / (kmax - kmin + 1)
ymax = max(dist.values())
bars, ticks = [], []
for k in range(kmin, kmax + 1):
    v = dist.get(k, 0)
    h = (H - PAD_B - PAD_T) * v / ymax
    x = PAD_L + (k - kmin) * bw
    side = "dem" if k >= 51 else "rep"
    who = "Democrats + independents hold 51+" if k >= 51 else ("50-50: VP Vance gives Republicans control" if k == 50 else "Republicans hold a majority")
    bars.append(f'<rect class="bar {side}" x="{x + 1:.1f}" y="{H - PAD_B - h:.1f}" width="{bw - 2:.1f}" height="{max(h, 0):.1f}" rx="2" '
                f'data-tip="{k} D+I seats · {v:.1%} of simulations · {who}"></rect>'
                f'<rect class="hit" x="{x:.1f}" y="{PAD_T}" width="{bw:.1f}" height="{H - PAD_B - PAD_T}" '
                f'data-tip="{k} D+I seats · {v:.1%} of simulations · {who}"></rect>')
    if k % 2 == 0:
        ticks.append(f'<text x="{x + bw / 2:.1f}" y="{H - PAD_B + 16}" text-anchor="middle">{k}</text>')
x50 = PAD_L + (50.5 - kmin) * bw
for frac in (0.05, 0.10):
    if frac <= ymax:
        y = H - PAD_B - (H - PAD_B - PAD_T) * frac / ymax
        ticks.append(f'<line class="grid" x1="{PAD_L}" x2="{W - 8}" y1="{y:.1f}" y2="{y:.1f}"></line>'
                     f'<text x="{PAD_L - 4}" y="{y + 4:.1f}" text-anchor="end">{frac:.0%}</text>')
chart = f"""<svg viewBox="0 0 {W} {H}" role="img" aria-label="Distribution of Democratic plus independent Senate seats across {P['sims']:,} simulations">
  {''.join(ticks)}
  <line class="axis" x1="{PAD_L}" x2="{W - 8}" y1="{H - PAD_B}" y2="{H - PAD_B}"></line>
  {''.join(bars)}
  <line class="majority" x1="{x50:.1f}" x2="{x50:.1f}" y1="{PAD_T - 6}" y2="{H - PAD_B}"></line>
  <text class="lbl" x="{x50 + 4:.1f}" y="{PAD_T + 4}">51 = Democratic control</text>
  <text x="{(W + PAD_L) / 2:.0f}" y="{H - 2}" text-anchor="middle">Democratic + independent seats</text>
</svg>"""

# ---- scenario table ---------------------------------------------------------------------------------
sc_rows = "".join(
    f"<tr><td>{esc(s['label'])}</td><td class='num'>{s['leaders']['D']}–{s['leaders']['R']}{' +' + str(s['leaders']['I']) + ' I' if s['leaders']['I'] else ''}</td>"
    f"<td class='num'>{pct(s['control']['separate']['D'])}</td><td class='num'>{pct(s['control']['separate']['R'])}</td></tr>"
    for s in model["scenarios"])
caucus_rows = "".join(
    f"<tr><td>{esc(c['label'])}</td><td class='num'>{pct(c['D'])}</td><td class='num'>{pct(c['R'])}</td><td class='num'>{pct(c['unclear'])}</td></tr>"
    for c in ctrl.values())

# ---- race rows --------------------------------------------------------------------------------------
rows, changes = [], []
tally = {"D": 0, "R": 0, "I": 0}
for r in sorted(races, key=lambda r: r["state"]):
    st = r["state"]
    a, res = audit[st], research.get(st, {})
    ch, rep = r["challenger"], r["rep"]
    chp = r["challenger_party"]
    p = r["p_challenger"]
    lead_party = chp if r["mean"] > 0 else "R"
    tally[lead_party] += 1
    leader = ch if r["mean"] > 0 else rep
    old = v1.get(st, {})
    old_txt = f"{old.get('winner', '')} ({old.get('party', '')}, {old.get('confidence', '')})" if old else ""
    if old and old.get("party") != lead_party:
        changes.append((st, old_txt, leader, lead_party, p if lead_party != "R" else 1 - p))
    swing = abs(r["poll_avg"]) if r["poll_avg"] is not None else abs(r["mean"])
    rule = "confident" if swing > CONFIDENT_MARGIN else "deep"
    b = a["ballot"]
    dname = b.get("D") or "None on ballot"
    others = [o for o in b.get("others", [])]
    ind_note = f"<span class='sub'>Challenger: {esc(ch)} (I)</span>" if chp == "I" else ""
    win_p = p if r["mean"] > 0 else 1 - p
    tierlbl = r["tier"]
    cls = {"D": "dem", "R": "rep", "I": "ind"}[lead_party]
    seat = f"<span class='sub'>{esc(a.get('seat') or '')} special</span>" if a.get("seat") else ""
    pbar = (f"<div class='pbar' title='{esc(ch)} {pct(p)} / {esc(rep)} {pct(1 - p)}'>"
            f"<i class='{'dem' if chp == 'D' else 'ind'}' style='width:{p * 100:.1f}%'></i><i class='rep' style='width:{(1 - p) * 100:.1f}%'></i></div>")

    # detail row: polls, prior, uncertainty, audit, context
    polls = sorted(r["polls"], key=lambda x: x["end"], reverse=True)
    prow = []
    for q in polls:
        tag = ""
        if q.get("partisan"):
            tag = f"<span class='tag {'dem' if q['partisan'] == 'D' else 'rep'}'>{q['partisan']}-sponsored</span>"
        elif q.get("lean"):
            tag = f"<span class='tag soft'>{q['lean']}-leaning</span>"
        resv = ", ".join(f"{k} {v:g}" for k, v in q["results"].items() if isinstance(v, (int, float)))
        prow.append(
            f"<tr><td>{esc(q['end'])}</td><td>{link(q.get('url'), q['pollster'])}{' · ' + esc(q['sponsor']) if q.get('sponsor') else ''} {tag}</td>"
            f"<td>{esc(q.get('n') or '?')} {esc(q.get('pop') or '')}</td><td>{esc(resv)}</td>"
            f"<td class='num'>{q['raw_margin']:+.1f}</td><td class='num'>{(q['adj'] or 0):+.1f}</td>"
            f"<td class='num'>{q['share']:.0%}</td><td>{'✓' if q.get('verified') else '<span class=muted>table</span>'}</td></tr>")
    polltable = (f"<table class='inner'><thead><tr><th>Ended</th><th>Pollster</th><th>Sample</th><th>Result</th>"
                 f"<th>Margin</th><th>Adj.</th><th>Weight</th><th>Checked</th></tr></thead><tbody>{''.join(prow)}</tbody></table>"
                 if prow else "<p>No public polls. The forecast is the fundamentals prior alone, with a wide error band.</p>")
    why = []
    if r["n_polls"]:
        why.append(f"{r['n_polls']} polls (effective sample of {r['n_eff']:g} independent polls after weighting) average "
                   f"<b>{esc(signed(r['poll_avg'], ch, rep))}</b>"
                   + (f" after removing the lean of sponsored and one-party pollsters (unadjusted {esc(signed(r['poll_avg_raw'], ch, rep))})."
                      if r["poll_avg"] != r["poll_avg_raw"] else "."))
    if r["prior"] is not None:
        inc = r["prior"] - a["fundamentals"]["pres_2024_margin_D"] - P["national_shift"]
        why.append(f"Fundamentals prior: 2024 presidential margin {a['fundamentals'].get('pres_2024_margin_D'):+g} + national shift {P['national_shift']:+g}"
                   f"{f' + incumbency {inc:+.0f}' if abs(inc) > 0.05 else ''} = {esc(signed(r['prior'], ch, rep))}, "
                   f"given <b>{r['prior_weight']:.0%}</b> of the weight.")
    elif chp == "I":
        why.append("No fundamentals prior: an independent challenger has no comparable past result, so the forecast is polls only, with extra uncertainty.")
    why.append(f"Forecast <b>{esc(signed(r['mean'], ch, rep))}</b> with a total error SD of {r['sd']:g} points "
               f"(national, regional and state error combined) → {esc(fav(r, ' wins '))} of simulations.")
    if r["undecided"] is not None:
        why.append(f"Average undecided/other: {r['undecided']:g}%.")
    claims = "".join(
        f"<li><span class='st-{c['status'].lower()}'>{esc(c['status'])}</span> {esc(c['claim'])}"
        f"<span class='sub'>{esc(c.get('source', ''))[:240]}</span></li>" for c in a.get("claims", []))
    caucus = "".join(f"<li><b>{esc(c['candidate'])}</b>: {esc(c['stance'])}</li>" for c in a.get("independent_caucus", []) or [])
    rt = a.get("ratings", {})
    ctx_prim = res.get("primaries", {})
    issues = "".join(f"<li>{esc(i)}</li>" for i in res.get("issues", []))
    rules = []
    if a.get("rcv"):
        rules.append("Ranked-choice general election.")
    if a.get("runoff_rule"):
        rules.append(f"Runoff: {a['runoff_rule']}")
    detail = f"""
    <tr class="detail"><td colspan="9"><details><summary>Evidence: {esc(st)}</summary><div class="dd">
      <div class="wide"><h4>How the number is built</h4><p>{' '.join(why)}</p></div>
      <div class="wide"><h4>Polls since Aug 1 (newest first)</h4>{polltable}
        <p class="note">Margin = {esc(ch)} minus {esc(rep)}. Adj. removes {P['weights']['partisan_shift']:g} pts from campaign/party-sponsored polls and
        {P['weights']['lean_shift']:g} pts from one-party pollsters, toward the other side. "Checked" = numbers confirmed at the original release;
        "table" = taken from a secondary polling table only (weighted at {P['weights']['unverified']:.0%}).</p></div>
      <div><h4>Ballot (audited)</h4><p><b>D:</b> {esc(dname)}<br><b>R:</b> {esc(b.get('R'))}{'<br><b>Also:</b> ' + esc('; '.join(others)) if others else ''}</p>
        {'<p><b>Withdrawn:</b> ' + esc('; '.join(b.get('withdrawals', []))) + '</p>' if b.get('withdrawals') else ''}
        {'<p>' + esc(' '.join(rules)) + '</p>' if rules else ''}</div>
      <div><h4>Ratings</h4><p>Cook: {esc(rt.get('cook'))} · Sabato: {esc(rt.get('sabato'))} · Inside: {esc(rt.get('inside'))}</p>
        <p class="sub">{esc(rt.get('as_of'))}</p><h4>Last result</h4><p>{esc(a['fundamentals'].get('last_senate'))}</p></div>
      {'<div class="wide"><h4>Caucus stance</h4><ul>' + caucus + '</ul></div>' if caucus else ''}
      {'<div class="wide"><h4>Fact audit</h4><ul class="claims">' + claims + '</ul></div>' if claims else ''}
      <div class="wide ctx"><h4>Context — not used in the forecast</h4>
        <p><b>D primary:</b> {esc(ctx_prim.get('dem'))}</p><p><b>R primary:</b> {esc(ctx_prim.get('rep'))}</p>
        {'<ul>' + issues + '</ul>' if issues else ''}
        <p class="note">Primary margins and local issues are shown for background only. They are not inputs: primary
        electorates differ from general electorates, and a lopsided primary often just reflects a weak challenger.</p></div>
      {'<div class="wide"><h4>Earlier call (v1, judgment-based)</h4><p>' + esc(old_txt) + ' — ' + esc(old.get('rationale', '')) + '</p></div>' if old else ''}
    </div></details></td></tr>"""
    rows.append(f"""
    <tr class="race {rule} {'tossup' if tierlbl in ('Toss-up', 'Tilt') else ''}">
      <td class="st">{esc(st)}{seat}<span class="sub">{esc(res.get('incumbent') or a.get('incumbent'))}</span></td>
      <td class="dem">{esc(dname)}{ind_note}</td>
      <td class="rep">{esc(b.get('R'))}</td>
      <td class="num">{r['n_polls'] or '—'}</td>
      <td class="num">{esc(signed(r['poll_avg'], ch, rep))}</td>
      <td class="num">{esc(signed(r['mean'], ch, rep))}<span class="sub">± {r['sd']:g}</span></td>
      <td>{pbar}<span class="sub">{esc(fav(r))}</span></td>
      <td><span class="tag {rule}">{'Swing &gt; ' + CM if rule == 'confident' else 'Deep dive'}</span></td>
      <td class="win {cls}">{esc(tierlbl)}{' ' + esc(leader) if tierlbl != 'Toss-up' else ''}<span class="sub">{'leader: ' + esc(leader) + ' · ' if tierlbl == 'Toss-up' else ''}{pct(win_p)}</span></td>
    </tr>{detail}""")

lead_d = HOLD["D"] + tally["D"]
chg_rows = "".join(
    f"<li><b>{esc(s)}</b>: v1 {esc(o)} → now {esc(l)} ({esc(pp)}) leads, wins {pct(w)} of simulations</li>" for s, o, l, pp, w in changes)
TOO_CLOSE = (0.20, 0.80)  # races in this band are listed as "where it's decided" and get an outcome switch
tossups = sorted((r for r in races if TOO_CLOSE[0] <= r["p_challenger"] <= TOO_CLOSE[1]), key=lambda r: abs(r["p_challenger"] - 0.5))

# ---- scenario simulator (levers) ---------------------------------------------------------------------
E = P["error"]
assert E["t_df"] % 2 == 0, "senate_sim.js draws chi-square for even df only"
sim_regions = sorted({r["sim"]["region"] for r in races})
sim_data = {"n": 20000, "t_df": E["t_df"], "national_sd": E["national_sd"], "regional_sd": E["regional_sd"],
            "hold": HOLD, "regions": sim_regions,
            "races": [{"st": r["state"], "ch": r["challenger"], "rp": r["rep"], "chp": r["challenger_party"], "mean": r["sim"]["mean"],
                       "sd": r["sim"]["sd"], "reg": sim_regions.index(r["sim"]["region"])} for r in races]}
sim_json = json.dumps(sim_data).replace("</", "<\\/")
lever_rows = []
for r in tossups:
    chp = r["challenger_party"]
    chc = "dem" if chp == "D" else "ind"
    lever_rows.append(
        f"<div class='lrow' data-st='{esc(r['state'])}'>"
        f"<span class='lst'>{esc(r['state'])}<span class='sub'>{esc(r['tier'])} · model {esc(fav(r))}</span></span>"
        f"<span class='lbar'><span class='pbar'><i class='ch {chc}'></i><i class='rp rep'></i></span><span class='sub lp'></span></span>"
        f"<span class='seg' role='group' aria-label='Outcome in {esc(r['state'])}'>"
        f"<button data-v='C' class='{chc}'>{esc(r['challenger'])} ({chp})</button><button data-v=''>Model</button>"
        f"<button data-v='R' class='rep'>{esc(r['rep'])} (R)</button></span></div>")
sim_js = (HERE / "senate_sim.js").read_text()

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 Senate Forecast</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1d1f; --muted:#6b6b70; --line:#e3e1db; --card:#fff;
  --dem:#1f5fbf; --dem-bg:#e8f0fc; --rep:#c0392b; --rep-bg:#fcebe9; --ind:#7a5c00; --ind-bg:#f6efd9;
  --dem-mark:#1f5fbf; --rep-mark:#c0392b; --ind-mark:#a07800;
  --conf:#2e7d4f; --conf-bg:#e6f4ec; --deep:#a35a00; --deep-bg:#fdf1e1; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#141416; --fg:#ececef; --muted:#9a9aa2; --line:#2c2c31; --card:#1c1c20;
  --dem:#7fb0ff; --dem-bg:#1a2740; --rep:#ff8a7d; --rep-bg:#3a1c1a; --ind:#e3c15a; --ind-bg:#332a12;
  --dem-mark:#4f8be8; --rep-mark:#e0604f; --ind-mark:#c9a43a;
  --conf:#6fd39a; --conf-bg:#173024; --deep:#f0b366; --deep-bg:#3a2a14; }} }}
:root[data-theme="dark"] {{ --bg:#141416; --fg:#ececef; --muted:#9a9aa2; --line:#2c2c31; --card:#1c1c20;
  --dem:#7fb0ff; --dem-bg:#1a2740; --rep:#ff8a7d; --rep-bg:#3a1c1a; --ind:#e3c15a; --ind-bg:#332a12;
  --dem-mark:#4f8be8; --rep-mark:#e0604f; --ind-mark:#c9a43a;
  --conf:#6fd39a; --conf-bg:#173024; --deep:#f0b366; --deep-bg:#3a2a14; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1400px; margin:0 auto; padding:24px 16px 64px; }}
h1 {{ margin:0 0 4px; font-size:26px }} h2 {{ font-size:17px; margin:28px 0 8px }} .lede {{ color:var(--muted); margin:0 0 20px; max-width:900px }}
.summary {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; min-width:150px }}
.card b {{ display:block; font-size:24px; font-variant-numeric:tabular-nums }} .card span {{ color:var(--muted); font-size:12px }}
.grid2 {{ display:grid; grid-template-columns:minmax(0,1.4fr) minmax(0,1fr); gap:16px }}
@media (max-width:900px) {{ .grid2 {{ grid-template-columns:minmax(0,1fr) }} }}
.scroll {{ overflow-x:auto }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px }}
.panel h3 {{ margin:0 0 6px; font-size:14px }}
svg {{ width:100%; height:auto; display:block }}
svg text {{ fill:var(--muted); font-size:11px }} svg text.lbl {{ fill:var(--fg); font-weight:600 }}
svg .axis {{ stroke:var(--line) }} svg .grid {{ stroke:var(--line); stroke-dasharray:2 3 }}
svg .majority {{ stroke:var(--fg); stroke-dasharray:4 3 }}
svg .bar.dem {{ fill:var(--dem-mark) }} svg .bar.rep {{ fill:var(--rep-mark) }} svg .hit {{ fill:transparent; cursor:default }}
.legend {{ display:flex; gap:14px; font-size:12px; color:var(--muted); margin-top:4px }}
.legend i {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px }}
#tip {{ position:fixed; pointer-events:none; background:var(--fg); color:var(--bg); font-size:12px; padding:4px 8px; border-radius:4px; display:none; z-index:10 }}
table.small {{ width:100%; border-collapse:collapse; font-size:13px }}
table.small td, table.small th {{ padding:4px 6px; border-bottom:1px solid var(--line); text-align:left }}
table.small th {{ color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase }}
.method {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin-bottom:16px; color:var(--muted) }}
.method b {{ color:var(--fg) }} .method ul {{ margin:4px 0; padding-left:18px }}
.callout {{ border-left:4px solid var(--deep) }}
.wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:8px; background:var(--card) }}
table.main {{ border-collapse:collapse; width:100%; min-width:1150px }}
table.main > thead th, table.main > tbody > tr > td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top }}
table.main > thead th {{ position:sticky; top:0; background:var(--card); font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted) }}
td.dem {{ color:var(--dem) }} td.rep {{ color:var(--rep) }}
td.num, .num {{ font-variant-numeric:tabular-nums; white-space:nowrap }} table.main td.num {{ font-weight:600 }}
td.st {{ font-weight:600; min-width:150px; max-width:220px }}
.sub {{ display:block; font-size:11px; color:var(--muted); font-weight:400 }}
td.win {{ font-weight:700; white-space:nowrap }} td.win.dem {{ background:var(--dem-bg); color:var(--dem) }} td.win.rep {{ background:var(--rep-bg); color:var(--rep) }} td.win.ind {{ background:var(--ind-bg); color:var(--ind) }}
.pbar {{ display:flex; width:120px; height:10px; border-radius:5px; overflow:hidden; gap:2px; background:var(--card) }}
.pbar i {{ display:block; height:100% }} .pbar i.dem {{ background:var(--dem-mark) }} .pbar i.rep {{ background:var(--rep-mark) }} .pbar i.ind {{ background:var(--ind-mark) }}
.tag {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; white-space:nowrap }}
.tag.confident {{ background:var(--conf-bg); color:var(--conf) }} .tag.deep {{ background:var(--deep-bg); color:var(--deep) }}
.tag.dem {{ background:var(--dem-bg); color:var(--dem) }} .tag.rep {{ background:var(--rep-bg); color:var(--rep) }} .tag.soft {{ border:1px solid var(--line); color:var(--muted) }}
tr.detail td {{ padding:0 10px 8px; border-bottom:2px solid var(--line) }}
tr.race td {{ border-bottom:none }}
summary {{ cursor:pointer; color:var(--deep); font-size:12px; font-weight:600; padding:4px 0 }}
.dd {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:8px 20px; padding:8px 0 }}
.dd .wide {{ grid-column:1/-1 }} .dd h4 {{ margin:6px 0 2px; font-size:12px; text-transform:uppercase; color:var(--muted) }}
.dd p, .dd ul {{ margin:2px 0 }} .dd a {{ color:var(--dem) }}
.dd .ctx {{ border-top:1px dashed var(--line); padding-top:6px; color:var(--muted) }}
table.inner {{ border-collapse:collapse; width:100%; font-size:12px }}
.dd .wide {{ overflow-x:auto }}
table.inner td, table.inner th {{ padding:3px 6px; border-bottom:1px solid var(--line); text-align:left }}
table.inner th {{ color:var(--muted); font-weight:600 }}
.note {{ font-size:11px; color:var(--muted) }} .muted {{ color:var(--muted) }}
ul.claims {{ padding-left:18px }} .st-confirmed {{ color:var(--conf); font-weight:600 }} .st-false {{ color:var(--rep); font-weight:700 }} .st-unconfirmed {{ color:var(--deep); font-weight:600 }}
.filters {{ margin:0 0 10px; display:flex; gap:8px; flex-wrap:wrap }}
.filters button {{ background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:14px; padding:4px 12px; cursor:pointer }}
.filters button.on {{ background:var(--fg); color:var(--bg) }}
footer {{ color:var(--muted); font-size:12px; margin-top:16px }}
.sim {{ border:1px solid var(--line); border-radius:8px; background:var(--card); padding:14px 16px; margin-bottom:16px }}
.sim h2 {{ margin:0 0 4px }}
.levers {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px 24px; margin:12px 0 }}
.lever label {{ display:flex; justify-content:space-between; font-weight:600; font-size:13px }}
.lever output {{ font-variant-numeric:tabular-nums }}
.lever input[type=range] {{ width:100%; accent-color:var(--fg) }}
.lever .ends {{ display:flex; justify-content:space-between; font-size:11px; color:var(--muted) }}
.presets {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:4px }}
.presets button, .seg button, .sim .btn {{ background:var(--card); color:var(--fg); border:1px solid var(--line); border-radius:12px; padding:3px 10px; font-size:12px; cursor:pointer }}
.seg {{ display:inline-flex; flex-wrap:wrap; gap:4px }}
.seg button[aria-pressed="true"] {{ background:var(--fg); color:var(--bg); border-color:var(--fg) }}
.seg button.dem[aria-pressed="true"] {{ background:var(--dem-mark); border-color:var(--dem-mark); color:#fff }}
.seg button.rep[aria-pressed="true"] {{ background:var(--rep-mark); border-color:var(--rep-mark); color:#fff }}
.seg button.ind[aria-pressed="true"] {{ background:var(--ind-mark); border-color:var(--ind-mark); color:#fff }}
.sim .summary .card b em {{ font-style:normal; font-size:12px; font-weight:600; margin-left:6px }}
em.up {{ color:var(--conf) }} em.dn {{ color:var(--rep) }}
#sim-status-row {{ font-size:12px; color:var(--muted); margin:0 0 8px; display:flex; flex-wrap:wrap; gap:8px; align-items:center }}
#sim-chart {{ max-width:820px }}
#sim-races {{ max-width:820px; margin-top:8px }}
.lrow {{ display:grid; grid-template-columns:minmax(0,1fr) 130px auto; gap:8px; align-items:center; padding:6px 0; border-bottom:1px solid var(--line) }}
.lrow.locked .lst {{ text-decoration:underline dotted }}
.lst {{ font-weight:600 }} .lbar .pbar {{ width:120px }}
.pbar i.ch, .pbar i.rp {{ transition:width .15s }}
@media (max-width:560px) {{ .lrow {{ grid-template-columns:minmax(0,1fr) auto }} .lrow .seg {{ grid-column:1/-1 }} }}
</style></head><body><main>
{site.nav('senate.html')}
<h1>2026 Senate Forecast</h1>
<p class="lede">35 seats on the ballot Nov 3, 2026 (33 regular seats plus the Ohio and Florida specials). A probabilistic model built from
{sum(r['n_polls'] for r in races)} individual polls, with no race-by-race judgment adjustments. Polls through {esc(model['as_of'])}.
Not up this year: D {HOLD['D']} (incl. 2 independents), R {HOLD['R']}.</p>

<div class="summary">
  <div class="card"><b style="color:var(--dem)">{pct(sep['D'])}</b><span>Democrats win control (51+ seats)</span></div>
  <div class="card"><b style="color:var(--rep)">{pct(sep['R'])}</b><span>Republicans keep control (50+ with VP Vance)</span></div>
  <div class="card"><b>{pct(sep['unclear'])}</b><span>Unaligned independents hold the balance</span></div>
  <div class="card"><b>{median}</b><span>Median D + independent seats</span></div>
  <div class="card"><b>{lo80}–{hi80}</b><span>80% range of D + independent seats</span></div>
</div>

<div class="grid2">
  <div class="panel"><h3>Seat distribution across {P['sims']:,} simulated elections</h3>
    {chart}
    <div class="legend"><span><i style="background:var(--dem-mark)"></i>Democratic control</span><span><i style="background:var(--rep-mark)"></i>Republican control (incl. 50-50)</span></div>
  </div>
  <div class="panel"><h3>If the polls are off</h3>
    <div class="scroll"><table class="small"><thead><tr><th>Scenario (shift applied to every race)</th><th>Seats if leaders win</th><th>P(D)</th><th>P(R)</th></tr></thead><tbody>{sc_rows}</tbody></table></div>
    <p class="note">Each row adds the same shift to every race, then re-runs the simulation. These are sensitivity tests, not alternative forecasts.
    "Seats if leaders win" counts Democrats + caucusing independents – Republicans, with no further noise.</p>
    <h3 style="margin-top:12px">Independents</h3>
    <div class="scroll"><table class="small"><thead><tr><th>Assumption</th><th>P(D)</th><th>P(R)</th><th>Unclear</th></tr></thead><tbody>{caucus_rows}</tbody></table></div>
    <p class="note">{', '.join(esc(r['challenger']) + ' (' + esc(r['state']) + ')' for r in any_ind)} have each said they would caucus with neither party.
    "Unclear" = simulations where neither side reaches a majority without them. King and Sanders (not up) are counted with Democrats.</p>
  </div>
</div>

<div class="method callout"><b>Where it's decided.</b> {len(tossups)} races are too close to call (the model gives either side {TOO_CLOSE[0]:.0%} to {TOO_CLOSE[1]:.0%}), closest first:
{', '.join(esc(r['state']) + ' (' + esc(fav(r)) + ')' for r in tossups)}.
Democrats lead in enough of them to reach {lead_d} seats if every leader wins, but they need 51, and because polling errors are correlated
these races tend to fall the same way. A uniform 3-point miss toward Republicans (the size seen in 2016 and 2024) is enough to flip control.</div>

<section class="sim" id="levers"><h2>Try your own scenario</h2>
<p class="note" style="margin:0">Move the levers to see how control changes. The page re-runs {sim_data['n']:,} simulations in your browser on every change, using the same
model and the same random draws each time, so any change you see comes from the lever.</p>
<div class="levers">
  <div class="lever"><label for="sim-swing">Polling miss in every race <output id="sim-swing-out">None</output></label>
    <input id="sim-swing" type="range" min="-10" max="10" step="0.5" value="0">
    <div class="ends"><span>Republicans beat polls by 10</span><span>Democrats by 10</span></div>
    <div class="presets"><button data-preset="-6">R+6 (2020)</button><button data-preset="-3">R+3 (2016/2024)</button><button data-preset="0">None</button><button data-preset="3">D+3 (2012)</button></div>
    <p class="note" style="margin:6px 0 0">The shift applies to every race; only too-close races are listed below.</p></div>
  <div class="lever"><label for="sim-err">Uncertainty <output id="sim-err-out">×1</output></label>
    <input id="sim-err" type="range" min="0" max="2" step="0.25" value="1">
    <div class="ends"><span>0: every leader wins</span><span>×1 historical</span><span>×2</span></div></div>
  <div class="lever"><label>Unaligned independents ({', '.join(esc(r['challenger']) for r in any_ind)})</label>
    <div class="seg" id="sim-caucus" role="group" aria-label="Independents"><button data-v="sep">Stay unaligned</button><button data-v="D" class="dem">Caucus with D</button><button data-v="R" class="rep">Caucus with R</button></div>
    <p class="note">Unaligned means a seat with neither party can leave control undecided.</p></div>
</div>
<p id="sim-status-row"><span id="sim-status"></span> <button class="btn" id="sim-reset">Reset all levers</button></p>
<div class="summary">
  <div class="card"><b id="sim-pd" style="color:var(--dem)"></b><span>Democrats win control</span></div>
  <div class="card"><b id="sim-pr" style="color:var(--rep)"></b><span>Republicans keep control</span></div>
  <div class="card" id="sim-pu-card"><b id="sim-pu"></b><span>Independents hold the balance</span></div>
  <div class="card"><b id="sim-exp"></b><span>Median Democratic-side seats</span></div>
  <div class="card"><b id="sim-range"></b><span>80% range</span></div>
  <div class="card"><b id="sim-lead"></b><span>Seats if every leader wins</span></div>
</div>
<div id="sim-chart"></div>
<h3 style="margin:14px 0 0;font-size:14px">Call too-close-to-call races yourself</h3>
<p class="note" style="margin:2px 0">Pick a winner to fix that race; the rest stay simulated, and still move with the national and regional error.
Listed: the {len(lever_rows)} races where the model gives either side between {TOO_CLOSE[0]:.0%} and {TOO_CLOSE[1]:.0%}, closest first.
Bars show each race's chance under your current levers.</p>
<div id="sim-races">{''.join(lever_rows)}</div>
</section>

{'<div class="method"><b>What changed from v1.</b> The first version applied state-specific "polls underestimate Republicans here" adjustments to close races, which moved every one of them toward Republicans. Those are removed. Changes in the projected leader:<ul>' + chg_rows + '</ul></div>' if changes else ''}

<details class="method"><summary>Method, parameters and sources</summary>
<ul>
<li><b>Polling average.</b> Every poll since Aug 1 is counted once (aggregator averages are never used as inputs). Weight = recency (half-life {P['weights']['half_life_days']} days)
× √(sample size, capped at {P['weights']['n_cap']}) × population (LV 1.0, RV {P['weights']['pop']['RV']}, adults {P['weights']['pop']['A']})
× {P['weights']['partisan_sponsor']} for campaign/party-sponsored polls × {P['weights']['unverified']} if the numbers were only seen in a secondary table.
A pollster's older releases count at {P['weights']['superseded']}× per newer release, so frequent pollsters don't dominate. Sponsored polls are shifted {P['weights']['partisan_shift']} points
against their sponsor and one-party pollsters {P['weights']['lean_shift']} points. {esc(P['sources']['partisan_shift'])}.</li>
<li><b>Fundamentals prior.</b> 2024 presidential margin + national shift of {P['national_shift']:+g} ({esc(P['sources']['national_shift'])}) + {P['incumbency_bonus']:g} points for an incumbent.
It is blended with the polls by precision, so it matters only where polling is thin. Prior SD {P['error']['fundamentals_sd']:g}. Not used for independent challengers.</li>
<li><b>No partisan bias assumed.</b> {esc(P['sources']['prior_bias'])} A state's past polling miss predicts its next one only weakly (correlation about 0.2), so no state-specific adjustments are applied.</li>
<li><b>Correlated error.</b> Each simulation draws one national error (SD {P['error']['national_sd']:g}; {esc(P['sources']['national_sd'])}), one per region (SD {P['error']['regional_sd']:g}),
and one per race (SD {P['error']['state_sd']:g} plus sampling noise of {P['error']['single_poll_sd']:g}/√(effective polls), plus {P['error']['per_undecided']:g} × undecided %, plus {P['error']['independent_extra_sd']:g} for independent challengers).
All errors are Student-t with {P['error']['t_df']} degrees of freedom, so big misses are more likely than under a normal curve.</li>
<li><b>Ranked choice.</b> Maine and Alaska use RCV. Where a pollster published final-round numbers they are used; otherwise minor candidates' first choices are transferred (Alaska: Heikes 80% to Sullivan, Sullivan Jr. split evenly).</li>
<li><b>Tiers</b> come from win probability: Safe ≥ 99%, Likely ≥ 90%, Lean ≥ 75%, Tilt ≥ 60%, else Toss-up. The <b>{CM}-point rule</b> (10 in the original sheet) is kept only to flag which races get a deep dive.</li>
<li><b>Not modeled:</b> turnout scenarios beyond what the polls capture; late candidate events; Louisiana and Georgia runoffs (both are two-candidate races, so they cannot trigger).</li>
</ul></details>

<h2>Race by race</h2>
<div class="filters"><button class="on" data-f="all">All 35</button><button data-f="tossup">Toss-up &amp; Tilt</button><button data-f="deep">Deep dives (swing ≤ {CM})</button><button data-f="confident">Swing &gt; {CM}</button></div>
<div class="wrap"><table class="main">
<thead><tr><th>State</th><th>Democrat</th><th>Republican</th><th>Polls</th><th>Poll average</th><th>Forecast</th><th>Win probability</th><th>{CM}-pt rule</th><th>Rating</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
{site.history('senate.html')}
<footer>Model: senate_model.py with model_params.json; polls in senate_polls.json (each with its source URL). Fact audit against Secretary of State filings, AP and major outlets, Oct 2026.
Ratings: Cook (Oct 20), Sabato (Oct 14), Inside Elections (Oct 15). The forecast margin is the challenger minus the Republican, in points.</footer>
</main>
<div id="tip"></div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('table.main > tbody > tr').forEach(tr => {{
    const kind = tr.classList.contains('detail') ? tr.previousElementSibling.className : tr.className;
    tr.style.display = (f === 'all' || kind.split(' ').includes(f)) ? '' : 'none';
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

(HERE / "senate.html").write_text(page)
print(f"senate.html written: P(D) {sep['D']:.0%}, P(R) {sep['R']:.0%}, expected D+I {exp_seats:.1f}, leaders D {lead_d}; {len(changes)} changed calls")
