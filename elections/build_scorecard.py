#!/usr/bin/env python3
"""Build scorecard.html: how the frozen Nov 3 forecast did against the results.

Reads the forecast from frozen/ (written by freeze.py); before the freeze it scores the current model files and says so.
Reads results from results.json, which is filled in by hand as races are called. The first run creates it with a
blank entry for every race that was on the ballot (House seats decided before November are left out).

results.json, per race:
  winner     surname of the winner, as listed in "candidates" (null until called)
  margin     first-listed candidate's share minus the second's, in points of the total vote (null until counted);
             for ranked-choice races the final round, for runoffs the Nov 3 round
  status     "pending", "called" (AP call, count still moving), "final" (count essentially complete) or "certified"
  winner_name  the winner's actual surname, when it differs from winner (Louisiana House races are scored by party)
  called_by, called_at, source, note: where the call and the numbers came from
Usage: python3 build_scorecard.py
"""
import html
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import governor_model
import senate_model
import site_chrome as site

HERE = Path(__file__).parent
FROZEN = HERE / "frozen"
SRC = FROZEN if (FROZEN / "manifest.json").exists() else HERE
RESULTS = HERE / "results.json"
css = (HERE / "page.css").read_text()
esc = html.escape


def load(name):
    return json.loads((SRC / name).read_text())


sen, hou, gov = load("senate_model.json"), load("house_model.json"), load("gov_model.json")
sen_polls, gov_polls = load("senate_polls.json"), load("gov_polls.json")
house_ratings = {d["district"]: d.get("ratings") or {} for d in load("house_data.json")}


def races():
    """Every scored race as a dict: chamber, key, a/b candidate surnames and parties, p = P(a wins), mean = a minus b."""
    out = []
    for r in sen["races"]:
        out.append({"ch": "senate", "key": r["state"], "a": r["challenger"], "ap": r["challenger_party"], "b": r["rep"],
                    "bp": "R", "p": r["p_challenger"], "mean": r["mean"], "poll": r.get("poll_avg"),
                    "ratings": sen_polls.get(r["state"], {}).get("ratings") or {}})
    for r in hou["races"]:
        if r.get("fixed"):
            continue
        # Louisiana's crowded fields: the model lists several names per side, so the page labels the sides by party
        by_party = ";" in (r.get("dem") or "") + (r.get("rep") or "")
        out.append({"ch": "house", "key": r["district"], "a": r["dn"], "ap": r["ch_party"], "b": r["rn"], "bp": "R",
                    "p": r["p_dem"], "mean": r["mean"], "poll": r.get("poll_avg"),
                    "ratings": house_ratings.get(r["district"], {}),
                    "labels": {r["dn"]: "Democrat", r["rn"]: "Republican"} if by_party else {},
                    "fields": (r.get("dem"), r.get("rep")) if by_party else None})
    for r in gov["races"]:
        out.append({"ch": "governors", "key": r["state"], "a": r["challenger"], "ap": r["challenger_party"],
                    "b": r["rep"], "bp": r["opponent_party"], "p": r["p_challenger"], "mean": r["mean"],
                    "poll": r.get("poll_avg"), "ratings": gov_polls.get(r["state"], {}).get("ratings") or {}})
    return out


RACES = races()
if not RESULTS.exists():
    blank = {"_updated": None, "_sources": "Winners: AP race calls. Margins: state election offices.",
             "senate": {}, "house": {}, "governors": {}}
    for r in RACES:
        blank[r["ch"]][r["key"]] = {"candidates": f"{r['a']} ({r['ap']}) vs {r['b']} ({r['bp']})", "winner": None,
                                    "margin": None, "status": "pending", "called_by": None, "called_at": None,
                                    "source": None, "note": ""}
    RESULTS.write_text(json.dumps(blank, indent=1, ensure_ascii=False))
    print(f"results.json created with {len(RACES)} blank races")
RES = json.loads(RESULTS.read_text())
for r in RACES:
    x = RES[r["ch"]].get(r["key"]) or {}
    assert x.get("winner") in (None, r["a"], r["b"]), f"{r['ch']} {r['key']}: winner {x.get('winner')!r} is not {r['a']} or {r['b']}"
    r["winner"], r["margin"], r["status"] = x.get("winner"), x.get("margin"), x.get("status") or "pending"
    r["winner_name"] = x.get("winner_name") or r["winner"]  # differs only where the model scored a side, not a person


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{p:.0%}"


def dsign(r):
    """+1 if the first-listed candidate is the Democratic (or non-Republican) side, -1 if the second is the Democrat."""
    return -1 if r["bp"] == "D" else 1


def rating_side(s):
    """'Lean D' -> 'D', 'Toss-up' -> None; trailing dates and notes are ignored."""
    m = re.match(r"\s*(Safe|Solid|Likely|Lean|Tilt)\s+([DRI])\b", s or "")
    return m.group(2) if m else None


def fav(r):
    return r["a"] if r["p"] >= 0.5 else r["b"]


def score(rs):
    """Scores for one set of races; only called races count, only counted races enter the margin error."""
    called = [r for r in rs if r["winner"]]
    s = {"n": len(rs), "called": len(called), "right": sum(fav(r) == r["winner"] for r in called)}
    s["brier"] = sum((r["p"] - (r["winner"] == r["a"])) ** 2 for r in called) / len(called) if called else None
    close = [r for r in called if 0.2 <= r["p"] <= 0.8]
    s["close"] = (sum(fav(r) == r["winner"] for r in close), len(close))
    clear = [r for r in called if not 0.2 <= r["p"] <= 0.8]
    s["clear"] = (sum(fav(r) == r["winner"] for r in clear), len(clear))
    s["close_n"] = sum(0.2 <= r["p"] <= 0.8 for r in rs)  # all too-close races, called or not
    counted = [r for r in rs if r["margin"] is not None]
    errs = [(r["margin"] - r["mean"]) * dsign(r) for r in counted]
    s["bias"] = sum(errs) / len(errs) if errs else None
    s["mae"] = sum(abs(e) for e in errs) / len(errs) if errs else None
    s["counted"] = len(counted)
    s["upsets"] = [r for r in called if fav(r) != r["winner"]]
    s["experts"] = {}
    for rater in ("cook", "sabato", "inside"):
        rated = [(r, rating_side(r["ratings"].get(rater))) for r in called]
        party = lambda r: r["ap"] if r["winner"] == r["a"] else r["bp"]
        leaned = [(r, side) for r, side in rated if side]
        s["experts"][rater] = (sum(side == party(r) for r, side in leaned), len(leaned), len(rated) - len(leaned))
    polled = [r for r in called if r["poll"] is not None and r["poll"] != 0]
    s["polls"] = (sum((r["a"] if r["poll"] > 0 else r["b"]) == r["winner"] for r in polled), len(polled))
    return s


def calibration(rs):
    called = [r for r in rs if r["winner"]]
    rows = []
    for lo, hi in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.99), (0.99, 1.01)]:
        b = [r for r in called if lo <= max(r["p"], 1 - r["p"]) < hi]
        rows.append((lo, hi, len(b), sum(max(r["p"], 1 - r["p"]) for r in b), sum(fav(r) == r["winner"] for r in b)))
    return rows


def seats():
    """Seats so far for each chamber (holdovers and pre-decided seats included) and the forecast median and 80% range."""
    def tally(ch, base):
        t = dict(base)
        for r in RACES:
            if r["ch"] == ch and r["winner"]:
                party = r["ap"] if r["winner"] == r["a"] else r["bp"]
                t[party] = t.get(party, 0) + 1
        return t
    fixed_d = sum(1 for r in hou["races"] if r.get("fixed") == "D")
    fixed_r = sum(1 for r in hou["races"] if r.get("fixed") == "R")
    dist = {int(k): v for k, v in sen["seat_dist_d_plus_i"].items()}
    cum, q = 0.0, {}
    for k in sorted(dist):
        cum += dist[k]
        for name, lvl in (("10", 0.1), ("50", 0.5), ("90", 0.9)):
            if name not in q and cum >= lvl:
                q[name] = k
    st = tally("senate", senate_model.HOLDOVER)
    return [("Senate", "Democratic and independent seats", st.get("D", 0) + st.get("I", 0), st.get("R", 0), 100, q),
            ("House", "Democratic seats", *(lambda t: (t.get("D", 0), t.get("R", 0)))(tally("house", {"D": fixed_d, "R": fixed_r})),
             435, hou["pct"]),
            ("Governors", "Democratic governors", *(lambda t: (t.get("D", 0), t.get("R", 0)))(tally("governors", governor_model.HOLD)),
             50, gov["pct"])]


def margin_txt(r, m):
    if m is None:
        return "–"
    lead = r["a"] if m >= 0 else r["b"]
    return f"{esc(lead)} +{abs(m):.1f}"


def side(r, name):
    """Party letter (D/R/I) of the candidate named, as the forecast listed them."""
    return r["ap"] if name == r["a"] else r["bp"]


def who(r, name, label=None):
    return f"<span class='pt {side(r, name)}'>{esc(label or r.get('labels', {}).get(name) or name)}</span>"


def odds_bar(r):
    """The forecast split as a two-tone bar, first-listed candidate on the left."""
    return (f"<span class='odds' aria-hidden='true'><i class='{r['ap']}' style='width:{r['p'] * 100:.0f}%'></i>"
            f"<i class='{r['bp']}' style='width:{(1 - r['p']) * 100:.0f}%'></i></span>")


def margin_html(r, m):
    if m is None:
        return "<span class='dim'>–</span>"
    lead = r["a"] if m >= 0 else r["b"]
    return f"{who(r, lead)} +{abs(m):.1f}"


def race_rows(rs):
    out = []
    for r in sorted(rs, key=lambda r: abs(r["p"] - 0.5)):
        f = fav(r)
        rt = r["ratings"].get("cook") or "–"
        rt = re.sub(r"\s*\(.*$|,.*$", "", rt)
        if r["winner"]:
            hit = r["winner"] == f
            cls = "hit" if hit else "miss"
            mark = "<span class='verdict hit'>✓ Called it</span>" if hit else "<span class='verdict miss'>✗ Missed</span>"
            res = (f"<span class='chip {side(r, r['winner'])}'>{esc(r['winner_name'])} won</span>"
                   + (f" <span class='dim'>({esc(r['status'])})</span>" if r["status"] not in ("called", "final", "certified") else ""))
        else:
            cls, mark, res = "", "<span class='verdict wait'>Pending</span>", "<span class='dim'>–</span>"
        if r["margin"] is not None:
            e = (r["margin"] - r["mean"]) * dsign(r)
            err = f"<span class='{'pt D' if e > 0 else 'pt R' if e < 0 else ''}'>{e:+.1f}</span>"
        else:
            err = "<span class='dim'>–</span>"
        out.append(f"<tr class='{cls}'><td class='key'>{esc(r['key'])}</td><td>{who(r, r['a'])} vs {who(r, r['b'])}</td>"
                   f"<td class='fav'>{odds_bar(r)}{who(r, f)} {pct(max(r['p'], 1 - r['p']))}</td><td class='num'>{margin_html(r, r['mean'])}</td>"
                   f"<td class='dim'>{esc(rt)}</td><td>{res}</td><td class='num'>{margin_html(r, r['margin'])}</td>"
                   f"<td class='num'>{err}</td><td>{mark}</td></tr>")
    return "".join(out)


def frac(t):
    return f"{t[0]} of {t[1]}" if t[1] else "–"


def pending(t, total):
    """How many of a group are still uncalled, so a partial count isn't read as the whole group."""
    return f"; {total} in all, {total - t[1]} not yet called" if total > t[1] else f"; all {total} called"


RACE_HEAD = ("<thead><tr><th>Race</th><th>Candidates</th><th>Our favorite</th><th>Forecast margin</th><th>Cook</th><th>Result</th>"
             "<th>Actual margin</th><th>Error (+ = D better)</th><th></th></tr></thead>")


def section(ch, title, rs, note=""):
    s = score(rs)
    brier = f"{s['brier']:.3f}" if s["brier"] is not None else "–"
    bias = f"{s['bias']:+.1f}" if s["bias"] is not None else "–"
    mae = f"{s['mae']:.1f}" if s["mae"] is not None else "–"
    ex = s["experts"]
    expert_rows = "".join(
        f"<tr><td>{name}</td><td class='num'>{frac(ex[k][:2])}</td><td class='num'>{ex[k][2] if s['called'] else '–'}</td></tr>"
        for k, name in (("cook", "Cook Political Report"), ("sabato", "Sabato's Crystal Ball"), ("inside", "Inside Elections")))
    cal = "".join(f"<tr><td>{lo:.0%}–{min(hi, 1):.0%}</td><td class='num'>{n}</td><td class='num'>{e:.1f}</td><td class='num'>{w}</td></tr>"
                  for lo, hi, n, e, w in calibration(rs))
    upsets = ", ".join(f"<b>{esc(r['key'])}</b> ({who(r, r['winner'], r['winner_name'])} won; we gave {pct(r['p'] if r['winner'] == r['a'] else 1 - r['p'])})"
                       for r in s["upsets"]) or "none so far"
    shown = rs if ch != "house" else [r for r in rs if 0.02 < r["p"] < 0.98 or r in s["upsets"]]
    # Called races left out of the main table (House seats we gave over 98%), so the called count and the lists agree.
    safe = [r for r in rs if r["winner"] and r not in shown]
    safe_called = (f"""<details class="safe"><summary>Safe seats called ({len(safe)}): races we gave over 98%</summary>
<div class="scroll"><table class="small">{RACE_HEAD}<tbody>{race_rows(safe)}</tbody></table></div></details>"""
                   if safe else "")
    n_fixed = sum(1 for r in hou["races"] if r.get("fixed"))
    counted = (f"<b>{s['called']} of {s['n']}</b><span>contested races called ({n_fixed} more were decided before Nov 3)</span>"
               if ch == "house" else f"<b>{s['called']} / {s['n']}</b><span>races called</span>")
    return f"""
<h2>{title}</h2>
<div class="summary">
  <div class="card">{counted}</div>
  <div class="card"><b class="{'good' if s['called'] and not s['upsets'] else 'warn' if s['upsets'] else ''}">{frac((s['right'], s['called']))}</b><span>favorite won</span></div>
  <div class="card"><b class="{'warn' if s['upsets'] else ''}">{len(s['upsets'])}</b><span>upsets (our underdog won)</span></div>
  <div class="card"><b>{frac(s['close'])}</b><span>called too-close races (20–80%) right{pending(s['close'], s['close_n'])}</span></div>
  <div class="card"><b>{frac(s['clear'])}</b><span>called clearer races right{pending(s['clear'], s['n'] - s['close_n'])}</span></div>
  <div class="card"><b>{brier}</b><span>Brier score (0 perfect, 0.25 coin flip)</span></div>
  <div class="card"><b class="{'pt D' if (s['bias'] or 0) > 0 else 'pt R' if (s['bias'] or 0) < 0 else ''}">{bias}</b><span>average margin error, + = Democrats did better ({s['counted']} counted)</span></div>
  <div class="card"><b>{mae}</b><span>average absolute margin error (pts)</span></div>
</div>
<p class="note{' upsets' if s['upsets'] else ''}">Upsets: {upsets}.{note}</p>
<div class="grid2">
  <div class="panel"><h3>Calibration: did our favorites win as often as we said?</h3>
    <table class="small"><thead><tr><th>Our favorite's chance</th><th>Races called</th><th>Wins we expected</th><th>Wins</th></tr></thead><tbody>{cal}</tbody></table></div>
  <div class="panel"><h3>Against the race ratings and a plain polling average</h3>
    <table class="small"><thead><tr><th>Source</th><th>Leaning races called right</th><th>Toss-ups (no call)</th></tr></thead><tbody>
    <tr><td>This forecast</td><td class='num'>{frac((s['right'], s['called']))}</td><td class='num'>{'0' if s['called'] else '–'}</td></tr>
    {expert_rows}
    <tr><td>Polling-average leader</td><td class='num'>{frac(s['polls'])}</td><td class='num'>–</td></tr></tbody></table></div>
</div>
<div class="scroll" style="margin-top:12px"><table class="small">{RACE_HEAD}<tbody>{race_rows(shown)}</tbody></table></div>{safe_called}"""


by = {ch: [r for r in RACES if r["ch"] == ch] for ch in ("senate", "house", "governors")}
n_called = sum(1 for r in RACES if r["winner"])
frozen = SRC == FROZEN
stamp = json.loads((FROZEN / "manifest.json").read_text())["frozen_at"] if frozen else None


def pt(iso):
    """A UTC timestamp in Pacific time, e.g. "9:00 a.m. PT on Nov 3" (PST, UTC-8, from Nov 1)."""
    t = datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=8)
    return f"{t:%-I:%M} {'a.m.' if t.hour < 12 else 'p.m.'} PT on {t:%b %-d}"


stamp = pt(stamp) if stamp else None
banner = (f"Scoring the forecast frozen at {esc(stamp)}; later updates can't change it."
          if frozen else "Not frozen yet: the forecast freezes at 9:00 a.m. PT on Nov 3, and from then on this page scores only the frozen copy.")
MAJORITY = {"Senate": 51, "House": 218, "Governors": 26}  # Senate: a 50-50 tie goes to Republicans (VP Vance)


def seat_bar(name, label, d, r, total, q):
    at = lambda k: f"{k / total * 100:.2f}%"
    left = total - d - r
    return f"""<div class="seatrow">
  <div class="seathead"><b>{name}</b> <span class="dim">{label}</span>
    <span class="tally"><span class="pt D">D {d}</span> · <span class="dim">{left} not yet called</span> · <span class="pt R">R {r}</span></span></div>
  <div class="seatbar" role="img" aria-label="{name}: Democrats {d}, Republicans {r}, {left} not yet called">
    <i class="D" style="width:{at(d)}"></i><i class="R" style="width:{at(r)}"></i>
    <span class="range" style="left:{at(q['10'] - 0.5)};width:{at(q['90'] - q['10'] + 1)}"></span>
    <span class="tick med" style="left:{at(q['50'] - 0.5)}"></span>
    <span class="tick maj" style="left:{at(MAJORITY[name] - 0.5)}"></span>
  </div>
  <div class="seatkey dim"><span class="k med"></span>Forecast median {q['50']} D (80% range {q['10']}–{q['90']}) · <span class="k maj"></span>Majority {MAJORITY[name]}</div>
</div>"""


seat_rows = "".join(seat_bar(*row) for row in seats())


def scenarios():
    """Polling-miss scenarios in both directions from the frozen inputs (scenarios.json). The overview published only the
    shifts toward Republicans; the shifts toward Democrats were computed after the election with the same simulations."""
    f = HERE / "scenarios.json"
    if not f.exists():
        return ""
    sc = json.loads(f.read_text())
    now = {name: (d, total - d - r) for name, _, d, r, total, _ in seats()}
    rows = [("-3", "R+3", "Published Nov 3"), ("-2", "R+2", "Published Nov 3"), ("0", "Forecast", "Published Nov 3"),
            ("2", "D+2", "Added Nov 4, after the election"), ("3", "D+3", "Added Nov 4, after the election")]
    def cell(v, name):
        p_d, p_r, d, _ = v
        p, who = (p_d, "D") if p_d >= p_r else (p_r, "R")
        return f'<td class="num"><b>{d}</b> <span class="dim">· <span class="pt {who}">{who} {pct(p)}</span></span></td>'
    body = "".join(
        f'<tr{" class=\"base\"" if k == "0" else ""}><td class="key">{lab}</td>'
        + "".join(cell(sc[k][ch], name) for ch, name in (("senate", "Senate"), ("house", "House"), ("governors", "Governors")))
        + f'<td class="dim">{when}</td></tr>' for k, lab, when in rows)
    body += ('<tr class="result"><td class="key">Result so far</td>'
             + "".join(f'<td class="num"><b>{d}</b>{f" <span class=\"dim\">+ {left} uncalled</span>" if left else ""}</td>'
                       for d, left in (now[n] for n in ("Senate", "House", "Governors")))
             + '<td class="dim">AP calls</td></tr>')
    return f"""<h2>Polling-miss scenarios, both directions</h2>
<div class="panel scen"><table><thead><tr><th>Every race shifted</th><th class="num">Senate</th><th class="num">House</th><th class="num">Governors</th><th>When</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="note">Each cell is the median Democratic seats (the Senate counts independents with Democrats) and the favored party's chance of
control: 51 Senate seats (a 50–50 tie goes to Republicans), 218 House seats, 26 governorships. The overview showed only what happens if the
polls overstate Democrats (R+2, R+3), because generic-ballot polls had overstated Democrats in 7 of the last 10 cycles. A balanced page would
have shown both directions. The D+2 and D+3 rows use the same frozen inputs, simulations and seed as the published rows, which this
rerun reproduces exactly, but they were computed on Nov 4, after the results were known. The frozen overview is unchanged.
For the House, every shift comes on top of the 1-point shading toward Republicans already in the forecast.</p>"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>2026 Midterm Scorecard</title>
<style>{css}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums }} .note {{ color:var(--muted); font-size:13px }}
.banner {{ background:var(--conf-bg); color:var(--conf); border-radius:8px; padding:8px 12px; margin:0 0 16px; font-size:13px; font-weight:600 }}
.dim {{ color:var(--muted) }}
.pt {{ font-weight:600 }} .pt.D {{ color:var(--dem) }} .pt.R {{ color:var(--rep) }} .pt.I {{ color:var(--ind) }}
.chip {{ display:inline-block; padding:1px 9px; border-radius:10px; font-weight:700; white-space:nowrap }}
.chip.D {{ background:var(--dem-bg); color:var(--dem) }} .chip.R {{ background:var(--rep-bg); color:var(--rep) }} .chip.I {{ background:var(--ind-bg); color:var(--ind) }}
.verdict {{ display:inline-block; padding:1px 9px; border-radius:10px; font-size:12px; font-weight:700; white-space:nowrap }}
.verdict.hit {{ background:var(--conf-bg); color:var(--conf) }} .verdict.miss {{ background:var(--deep); color:var(--card) }}
.verdict.wait {{ color:var(--muted); border:1px dashed var(--line); font-weight:600 }}
tr.hit td.key {{ box-shadow:inset 3px 0 var(--conf) }}
tr.miss td {{ background:var(--deep-bg) }} tr.miss td.key {{ box-shadow:inset 3px 0 var(--deep) }}
td.key {{ font-weight:600; white-space:nowrap }} td.fav {{ white-space:nowrap }}
.odds {{ display:inline-flex; width:48px; height:6px; border-radius:3px; overflow:hidden; gap:1px; margin-right:8px; vertical-align:1px }}
.odds i.D, .seatbar i.D {{ background:var(--dem-mark) }} .odds i.R, .seatbar i.R {{ background:var(--rep-mark) }} .odds i.I {{ background:var(--ind-mark) }}
.card b.good {{ color:var(--conf) }} .card b.warn {{ color:var(--deep) }}
.note.upsets {{ background:var(--deep-bg); color:var(--fg); border-radius:8px; padding:8px 12px }}
.seats {{ display:grid; gap:18px }}
details.safe {{ margin-top:10px; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:4px 12px }}
details.safe summary {{ font-size:13px; padding:6px 0 }} details.safe[open] summary {{ margin-bottom:6px }}
.seathead {{ display:flex; flex-wrap:wrap; gap:4px 10px; align-items:baseline; margin-bottom:12px }} .tally {{ margin-left:auto; font-variant-numeric:tabular-nums }}
.seatbar {{ position:relative; height:22px; border-radius:6px; overflow:visible;
  background:repeating-linear-gradient(135deg, var(--line) 0 6px, transparent 6px 12px); box-shadow:inset 0 0 0 1px var(--line) }}
.seatbar i {{ position:absolute; top:0; bottom:0 }} .seatbar i.D {{ left:0; border-radius:6px 0 0 6px }} .seatbar i.R {{ right:0; border-radius:0 6px 6px 0 }}
.seatbar .range {{ position:absolute; top:-7px; height:4px; border-radius:2px; background:var(--muted); opacity:.35 }}
.seatbar .tick {{ position:absolute; width:0; top:-8px; bottom:-4px }}
.seatbar .tick.med {{ border-left:2px solid var(--fg) }} .seatbar .tick.maj {{ border-left:2px dashed var(--muted) }}
.scen {{ overflow-x:auto }} .scen table {{ width:100%; border-collapse:collapse }} .scen th, .scen td {{ padding:6px 10px; white-space:nowrap }}
tr.base td {{ background:var(--conf-bg) }} tr.result td {{ border-top:2px solid var(--line); font-weight:600 }}
.seatkey {{ font-size:12px; margin-top:8px }} .seatkey .k {{ display:inline-block; width:0; height:11px; margin:0 5px -1px 0 }}
.seatkey .k.med {{ border-left:2px solid var(--fg) }} .seatkey .k.maj {{ border-left:2px dashed var(--muted); margin-left:6px }}
</style></head><body><main>
{site.nav('scorecard.html')}
<h1>How the forecast did</h1>
<p class="lede">The final forecast against the results, race by race. Winners follow AP race calls. Margins are AP's count, shown once
AP estimates at least 95% of the expected vote is in; they still move as ballots are counted, so they are replaced with state election
office figures about a week after the election and again at certification.
{n_called} of {len(RACES)} races called so far{f" (updated {esc(pt(RES['_updated']))})" if RES.get('_updated') else ""}.</p>
<p class="banner">{banner}</p>
<h2>Seats</h2>
<div class="panel seats">{seat_rows}</div>
<p class="note">Seats won include seats not up this year and House seats decided before November. The Senate counts independents with Democrats.</p>
{scenarios()}
{section("senate", "Senate", by["senate"])}
{section("house", "House", by["house"], " The table lists races the forecast gave between 2% and 98%, plus any upset; called safe seats are listed below it."
        " Louisiana's six races are scored by party, because the frozen forecast listed each side as a field of candidates ("
        + "; ".join(f"{esc(r['key'])}: {esc(r['fields'][0].replace(';', ','))} vs {esc(r['fields'][1].replace(';', ','))}"
                  for r in by["house"] if r.get("fields")) + "). The winner shown is AP's.")}
{section("governors", "Governors", by["governors"])}
<p class="note" style="margin-top:20px">How to read this: the Brier score averages the squared gap between our chance and what happened
(1 if the first-listed candidate won, 0 if not), so it rewards being confident and right and punishes being confident and wrong.
Margin error is the actual margin minus our forecast margin, signed so a positive number means Democrats did better than forecast.
Races decided by ranked-choice voting use the final round; Georgia runoffs are scored on the eventual winner and the Nov 3 margin.</p>
<footer>Forecasts, not predictions of certainty: a 70% favorite loses 3 times in 10 in simulations.</footer>
</main></body></html>"""
(HERE / "scorecard.html").write_text(page)
print(f"scorecard.html written: {n_called} of {len(RACES)} races called; scoring {'frozen' if frozen else 'current (not frozen)'} forecast")
