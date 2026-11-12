#!/usr/bin/env python3
"""Build wings.html: the incoming House and Senate sorted into four party wings, and which wings gained or lost seats.

Reads wings/: house_incoming.json and senate_incoming.json (every member-elect in a called seat, with the wing and the basis
for it), house_departing.json and senate_departing.json (sitting members who won't be back, classified the same way).
The research behind each entry is in wings/research/; wings/combine_house.py applied the roll-call rules to the House.
Seats still uncalled, and departing members whose successor isn't called yet, are left out of both sides of the comparison.
Usage: python3 build_wings.py
"""
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
W = HERE / "wings"
css = (HERE / "page.css").read_text()
esc = html.escape
load = lambda f: json.loads((W / f).read_text())

KEYS = [("D", "Progressive"), ("D", "Mainstream"), ("R", "Nationalist"), ("R", "Mainstream")]
CLS = {("D", "Progressive"): "dp", ("D", "Mainstream"): "dm", ("R", "Nationalist"): "rn", ("R", "Mainstream"): "rm"}
LABEL = {("D", "Progressive"): "Progressive Democrats", ("D", "Mainstream"): "Mainstream Democrats",
         ("R", "Nationalist"): "Nationalist Republicans", ("R", "Mainstream"): "Mainstream Republicans"}
side = lambda p: "D" if p in ("D", "I") else "R"  # independents (Sanders, King) caucus with Democrats

CH = {}
for ch, inc, dep in (("House", "house_incoming.json", "house_departing.json"), ("Senate", "senate_incoming.json", "senate_departing.json")):
    inc, dep = load(inc), [x for x in load(dep) if not x.get("excluded")]
    ret = Counter((side(r["party"]), r["wing"]) for r in inc if r["returning"])
    new = Counter((side(r["party"]), r["wing"]) for r in inc if not r["returning"])
    gone = Counter((side(r["party"]), r["wing"]) for r in dep)
    CH[ch] = {"inc": inc, "dep": dep, "before": {k: ret[k] + gone[k] for k in KEYS}, "after": {k: ret[k] + new[k] for k in KEYS},
              "new": new, "gone": gone}
total = {k: (CH["House"]["before"][k] + CH["Senate"]["before"][k], CH["House"]["after"][k] + CH["Senate"]["after"][k]) for k in KEYS}


def party_share(c, when, k):
    """A wing's share of its own party's seats in that chamber."""
    n = sum(c[when][j] for j in KEYS if j[0] == k[0])
    return c[when][k] / n if n else 0


def comp_bar(c, when):
    n = sum(c[when].values())
    segs = "".join(f'<i class="{CLS[k]}" style="width:{c[when][k] / n * 100:.2f}%" title="{LABEL[k]}: {c[when][k]}"></i>' for k in KEYS)
    return f'<div class="comp" role="img" aria-label="{", ".join(f"{LABEL[k]} {c[when][k]}" for k in KEYS)}">{segs}</div>'


def change_table(ch):
    c = CH[ch]
    peak = max(abs(c["after"][k] - c["before"][k]) for k in KEYS) or 1
    rows = ""
    for k in KEYS:
        b, a = c["before"][k], c["after"][k]
        net = a - b
        bar = (f'<span class="net"><i class="{CLS[k]} {"up" if net > 0 else "down"}" style="width:{abs(net) / peak * 50:.1f}%"></i></span>')
        rows += (f'<tr><td><span class="sw {CLS[k]}"></span>{LABEL[k]}</td><td class="num">{b}</td><td class="num">{c["gone"][k]}</td>'
                 f'<td class="num">{c["new"][k]}</td><td class="num">{a}</td><td class="num"><b>{net:+d}</b></td><td class="barcell">{bar}</td>'
                 f'<td class="num dim">{party_share(c, "before", k):.0%} → {party_share(c, "after", k):.0%}</td></tr>')
    nb, na = sum(c["before"].values()), sum(c["after"].values())
    return f"""<div class="panel">
<div class="comprow"><span class="dim">Outgoing ({nb} seats)</span>{comp_bar(c, "before")}</div>
<div class="comprow"><span class="dim">Incoming ({na} seats)</span>{comp_bar(c, "after")}</div>
<div class="scroll" style="margin-top:14px"><table class="small"><thead><tr><th>Wing</th><th class="num">Outgoing</th><th class="num">Leaving</th>
<th class="num">Arriving</th><th class="num">Incoming</th><th class="num">Change</th><th></th><th class="num">Share of own party</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>"""


def member_rows(rs, key):
    out = []
    for r in sorted(rs, key=lambda r: r.get(key) or ""):
        name = esc(r["name"]) + (' <span class="dim">(I)</span>' if r["party"] == "I" else "")
        new = "" if r["returning"] else '<span class="tag">new</span>'
        out.append(f'<tr><td class="key">{esc(r.get(key) or "")}</td><td>{name} {new}</td><td class="dim">{esc(r.get("confidence") or "")}</td>'
                   f'<td class="dim">{esc(r.get("basis") or "")}</td></tr>')
    return "".join(out)


def lists(ch, key):
    inc = CH[ch]["inc"]
    blocks = ""
    for k in KEYS:
        rs = [r for r in inc if side(r["party"]) == k[0] and r["wing"] == k[1]]
        blocks += (f'<details class="list"><summary><span class="sw {CLS[k]}"></span>{LABEL[k]} <span class="dim">({len(rs)}; '
                   f'{sum(not r["returning"] for r in rs)} new)</span></summary><div class="scroll"><table class="small">'
                   f'<thead><tr><th>{"District" if key == "district" else "State"}</th><th>Member</th><th>Confidence</th><th>Basis</th></tr></thead>'
                   f'<tbody>{member_rows(rs, key)}</tbody></table></div></details>')
    dep = CH[ch]["dep"]
    drows = "".join(f'<tr><td class="key">{esc(x.get(key) or "")}</td><td>{esc(x["name"])}</td><td><span class="sw {CLS[(side(x["party"]), x["wing"])]}"></span>'
                    f'{LABEL[(side(x["party"]), x["wing"])]}</td><td class="dim">{esc(x.get("why_leaving") or "")}</td></tr>'
                    for x in sorted(dep, key=lambda x: x.get(key) or ""))
    blocks += (f'<details class="list"><summary>Leaving: outgoing members not in the new {ch} <span class="dim">({len(dep)})</span></summary>'
               f'<div class="scroll"><table class="small"><thead><tr><th>{"District" if key == "district" else "State"}</th><th>Member</th>'
               f'<th>Wing</th><th>Why</th></tr></thead><tbody>{drows}</tbody></table></div></details>')
    return blocks


H, S = CH["House"], CH["Senate"]
hlost = Counter(x["wing"] for x in H["dep"] if side(x["party"]) == "R" and x.get("why_leaving", "").startswith("lost general"))
n_low = sum(r.get("confidence") == "low" for c in CH.values() for r in c["inc"])
net = {k: total[k][1] - total[k][0] for k in KEYS}
# New House Democrats by the party of the member who left the same district (approximate where districts were renumbered)
prev = {x["district"]: side(x["party"]) for x in load("house_departing.json")}
newd = Counter((r["wing"], prev.get(r["district"])) for r in H["inc"] if r["party"] == "D" and not r["returning"])
flips = newd[("Mainstream", "R")] + newd[("Progressive", "R")]
d = lambda ch, k: CH[ch]["after"][k] - CH[ch]["before"][k]


# Head to head: the two nominees in every competitive race (rated Likely, Lean, Tilt or Toss-up), paired by wing (wings/matchups.py)
MU = load("matchups.json")
RES = json.loads((HERE / "results.json").read_text())
AS_OF = datetime.fromisoformat(RES["_updated"]).strftime("%b %-d, %Y")
S_OPEN = sum(x.get("status") != "called" for x in RES["senate"].values())
PARTIAL = sorted((r for r in MU if r["counted"] < 90),  # natural order: AZ-2 before AZ-10; at-large seats (AK-AL) first in their state
                 key=lambda r: (r["district"].split("-")[0], int(r["district"].split("-")[1]) if r["district"].split("-")[-1].isdigit() else 0))
PAIRS = [("Progressive", "Nationalist"), ("Mainstream", "Mainstream"), ("Progressive", "Mainstream"), ("Mainstream", "Nationalist")]
HC = [r for r in MU if r["chamber"] == "House"]
UPS = [r for r in MU if r["upset"]]
mean = lambda xs: sum(xs) / len(xs) if xs else 0


def se(xs):
    if len(xs) < 2:
        return 0
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1) / len(xs)) ** 0.5


def in_pair(rs, p):
    return [r for r in rs if (r["d_wing"], r["r_wing"]) == p]


def pair_label(p):
    return (f'<span class="sw {CLS[("D", p[0])]}"></span>{p[0]} D <span class="dim">vs</span> '
            f'<span class="sw {CLS[("R", p[1])]}"></span>{p[1]} R')


def strip(rs, lo, hi, base):
    """One row per matchup: each race a dot at how far the Democrat beat the forecast, the matchup's mean with a ±1 standard error band."""
    x = lambda v: (min(max(v, lo), hi) - lo) / (hi - lo) * 100
    ticks = range(int(lo // 5 * 5 + 5), int(hi) + 1, 5)
    out = ""
    for p in PAIRS:
        g = in_pair(rs, p)
        vs = [r["vs_forecast"] for r in g]
        dots = ""
        for i, r in enumerate(sorted(g, key=lambda r: r["vs_forecast"])):
            tip = (f'{r["district"]}: {r["d"]} ({p[0]} D) vs {r["r"]} ({p[1]} R). Forecast D {r["forecast_margin"]:+.1f}, result D '
                   f'{r["margin"]:+.1f} ({r["counted"]}% counted): Democrat {r["vs_forecast"]:+.1f} vs. forecast. Won: {r["winner"]}'
                   + (" (upset)" if r["upset"] else ""))
            dots += (f'<i class="dot {"dem" if r["winner"] == "D" else "rep"}" style="left:{x(r["vs_forecast"]):.2f}%;top:{6 + (i % 5) * 6}px" '
                     f'data-t="{esc(tip)}"></i>')
        band = ""
        if vs:
            m, s = mean(vs), se(vs)
            band = (f'<b class="band" style="left:{x(m - s):.2f}%;width:{x(m + s) - x(m - s):.2f}%"></b>'
                    f'<b class="mean" style="left:{x(m):.2f}%" data-t="{esc(f"Average {m:+.1f} (±{s:.1f}), {len(vs)} races")}"></b>')
        grid = "".join(f'<u style="left:{x(t):.2f}%"{" class=zero" if t == 0 else ""}></u>' for t in ticks)
        out += (f'<div class="mrow"><div class="mlab">{pair_label(p)}<span class="dim mn">{len(g)} race{"s" if len(g) != 1 else ""}'
                f'{f" · avg {mean(vs):+.1f}" if vs else ""}</span></div>'
                f'<div class="strip">{grid}<u class="all" style="left:{x(base):.2f}%"></u>{band}{dots}</div></div>')
    axis = "".join(f'<span style="left:{x(t):.2f}%">{t:+d}</span>' for t in ticks)
    return out + f'<div class="mrow"><div></div><div class="maxis">{axis}</div></div>'


def matchup_table(rs, upsets=False):
    body = ""
    for p in PAIRS:
        g = in_pair(rs, p)
        if not g:
            body += f'<tr><td>{pair_label(p)}</td><td class="num">0</td>' + '<td class="num dim">–</td>' * (5 if not upsets else 4) + "</tr>"
            continue
        vs, pres = [r["vs_forecast"] for r in g], [r["vs_pres"] for r in g if r["vs_pres"] is not None]
        mid = (f'<td class="num">{sum(r["winner"] == "D" for r in g)}</td>' if not upsets else "")
        tail = (f'<td class="num">{sum(r["upset"] for r in g)} of {sum(r["p_d"] < 0.5 for r in g)}</td>' if not upsets else
                f'<td class="dim">{", ".join(r["district"] for r in sorted(g, key=lambda r: -r["vs_forecast"]))}</td>')
        body += (f'<tr><td>{pair_label(p)}</td><td class="num">{len(g)}</td>{mid}<td class="num">{mean([r["forecast_margin"] for r in g]):+.1f}</td>'
                 f'<td class="num"><b>{mean(vs):+.1f}</b> <span class="dim">{f"±{se(vs):.1f}" if len(vs) > 1 else ""}</span></td><td class="num">{mean(pres):+.1f}</td>{tail}</tr>')
    head = ("<th>Matchup</th><th class=num>Races</th>" + ("<th class=num>Democrat won</th>" if not upsets else "")
            + "<th class=num>Forecast D margin</th><th class=num>D beat forecast by</th><th class=num>D vs. 2024 pres.</th>"
            + ("<th class=num>Upsets / R favored</th>" if not upsets else "<th>Races</th>"))
    return f'<div class="scroll"><table class="small mu"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def senate_rows():
    rs = sorted([r for r in MU if r["chamber"] == "Senate"], key=lambda r: PAIRS.index((r["d_wing"], r["r_wing"])))
    return "".join(f'<tr><td class="key">{esc(r["district"])}</td><td>{esc(r["d"])} <span class="dim">({r["d_wing"]})</span></td>'
                   f'<td>{esc(r["r"])} <span class="dim">({r["r_wing"]})</span></td><td class="num">{r["forecast_margin"]:+.1f}</td>'
                   f'<td class="num">{r["margin"]:+.1f}</td><td class="num"><b>{r["vs_forecast"]:+.1f}</b></td>'
                   f'<td class="{"dem" if r["winner"] == "D" else "rep"}">{r["d"] if r["winner"] == "D" else r["r"]}{" (upset)" if r["upset"] else ""}</td></tr>'
                   for r in rs)


allv = [r["vs_forecast"] for r in MU]
LO, HI = min(-10, min(allv) - 1), max(allv) + 1
hc_avg, up_avg = mean([r["vs_forecast"] for r in HC]), mean([r["vs_forecast"] for r in UPS])
pm = {p: mean([r["vs_forecast"] for r in in_pair(HC, p)]) for p in PAIRS}
um = {p: mean([r["vs_forecast"] for r in in_pair(UPS, p)]) for p in PAIRS}
vs_nat, vs_main = ([r["vs_forecast"] for r in HC if r["r_wing"] == w] for w in ("Nationalist", "Mainstream"))
rfav = lambda p: [r for r in in_pair(HC, p) if r["p_d"] < 0.5]
_a, _b = ([r["vs_forecast"] for r in in_pair(HC, p)] for p in (("Mainstream", "Nationalist"), ("Mainstream", "Mainstream")))
z = (mean(_a) - mean(_b)) / (se(_a) ** 2 + se(_b) ** 2) ** 0.5
urate = {p: (sum(r["upset"] for r in rfav(p)), len(rfav(p))) for p in PAIRS}


def card(k, desc, test, examples):
    hb, ha = H["after"][k], S["after"][k]
    return f"""<div class="card wing {CLS[k]}"><h3><span class="sw {CLS[k]}"></span>{LABEL[k]}</h3>
<div class="counts"><span><b>{hb}</b> House</span><span><b>{ha}</b> Senate</span><span class="dim">{net[k]:+d} seats vs. the outgoing Congress</span></div>
<p>{desc}</p><p class="test"><span class="lab">How a member lands here:</span> {test}</p><p class="dim ex">{examples}</p></div>"""


cards = "".join([
    card(("D", "Progressive"),
         "The party's left. Progressives want a large expansion of public programs: Medicare for All, Green New Deal-scale climate "
         "spending, tuition-free college, higher taxes on the wealthy and on corporations. Most belong to the Congressional Progressive "
         "Caucus, and their backers include Bernie Sanders, Justice Democrats, the Working Families Party, Our Revolution and Sunrise. "
         "On Israel they favor conditioning or cutting U.S. military aid.",
         "a left economic program, and no vote to keep military aid to Israel. In the House the Israel test is the July 15, 2026 vote "
         "on the Massie amendment to strip $3.3 billion in Israel military aid; in the Senate, the April 15, 2026 vote on S.J.Res. 32 to "
         "block an arms sale to Israel.",
         "Examples: Bernie Sanders, Elizabeth Warren, Alexandria Ocasio-Cortez, Greg Casar; new: Abdul El-Sayed, Peggy Flanagan, Brad Lander."),
    card(("D", "Mainstream"),
         "Everyone else in the Democratic caucus, from leadership-aligned liberals to the New Democrat Coalition and Blue Dog moderates. "
         "They tend to build on existing programs (the Affordable Care Act, targeted tax credits) rather than replace them, are more "
         "open to business and fiscal caution, and back security aid to Israel. Under this page's rule, members with a left economic "
         "record who voted to keep Israel aid are counted here.",
         "everyone else in the Democratic caucus: members without a left economic program, and members with one who voted to keep Israel aid.",
         "Examples: Hakeem Jeffries, Mark Warner, Rosa DeLauro, Ritchie Torres; new: Roy Cooper, Sherrod Brown, Zack Mullock."),
    card(("R", "Nationalist"),
         "The America First wing. These members are skeptical of foreign aid and long-term commitments abroad, and want immigration cut "
         "beyond the party's baseline: ending birthright citizenship, cutting legal immigration, mass deportation. They back tariffs and "
         "put cultural and religious issues at the center of their platforms, and many objected to certifying the 2020 election. This "
         "isn't the same thing as the Freedom Caucus, whose hardliners fight mostly over spending and House procedure.",
         "a vote to bar Ukraine aid: in the House the July 2025 Greene amendment, and in the Senate the April 2024 Ukraine aid "
         "package. Members whose votes are mixed, and newcomers, are placed on their platforms and backers. A Trump endorsement alone "
         "doesn't decide it.",
         "Examples: Josh Hawley, Mike Lee, Ted Cruz, Andy Biggs (outgoing); new: Barry Moore, Harriet Hageman (Senate), Anthony Constantino."),
    card(("R", "Mainstream"),
         "Traditional conservatives. They want tax cuts and deregulation, and back a strong defense, NATO and aid to allies, including "
         "the 2024 Ukraine aid. They are more aligned with business and more open to trade, and include the Republican Main Street "
         "Caucus and the Problem Solvers. They are still conservative on immigration; what separates them from the Nationalists is "
         "mostly foreign policy, trade and tone.",
         "a vote for the 2024 Ukraine aid without a vote to bar it later. Members with no record are placed on their platforms and "
         "backers.",
         "Examples: John Thune, Mike Rounds, Shelley Moore Capito, Brian Fitzpatrick (outgoing); new: Kurt Alme, Andy Barr (Senate)."),
])

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>Party Wings, New Congress</title>
<style>{css}
:root {{ --dp:#1f5fbf; --dm:#8fb3ea; --rn:#c0392b; --rm:#eda59b; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --dp:#5b95ef; --dm:#2c4f86; --rn:#e0604f; --rm:#7f3b33; }} }}
:root[data-theme="dark"] {{ --dp:#5b95ef; --dm:#2c4f86; --rn:#e0604f; --rm:#7f3b33; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums }} .dim {{ color:var(--muted) }} .note {{ color:var(--muted); font-size:13px }}
.sw {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:7px; vertical-align:0 }}
.sw.dp, .comp i.dp, .net i.dp {{ background:var(--dp) }} .sw.dm, .comp i.dm, .net i.dm {{ background:var(--dm) }}
.sw.rn, .comp i.rn, .net i.rn {{ background:var(--rn) }} .sw.rm, .comp i.rm, .net i.rm {{ background:var(--rm) }}
.wings {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px }}
.card.wing {{ text-align:left; padding:14px 16px }} .card.wing h3 {{ margin:0 0 6px; font-size:16px }}
.card.wing p {{ font-size:14px; line-height:1.5; margin:8px 0 0 }} .card.wing .test {{ font-size:13px }} .card.wing .lab {{ font-weight:700 }} .card.wing .ex {{ font-size:12px }}
.counts {{ display:flex; flex-wrap:wrap; gap:4px 14px; font-size:13px }} .counts b {{ font-size:18px }}
.comprow {{ display:grid; grid-template-columns:140px 1fr; gap:10px; align-items:center; font-size:13px; margin:6px 0 }}
.comp {{ display:flex; height:18px; gap:2px; border-radius:5px; overflow:hidden }} .comp i {{ display:block }}
.net {{ display:block; position:relative; height:10px; min-width:120px }}
.net i {{ position:absolute; top:0; bottom:0; border-radius:3px }} .net i.up {{ left:50% }} .net i.down {{ right:50% }}
.net::after {{ content:""; position:absolute; left:50%; top:-3px; bottom:-3px; border-left:1px solid var(--muted) }}
td.barcell {{ width:28% }} td.key {{ font-weight:600; white-space:nowrap }}
.tag {{ font-size:11px; font-weight:700; color:var(--conf); background:var(--conf-bg); border-radius:8px; padding:0 6px; margin-left:4px }}
details.list {{ margin-top:8px; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:4px 12px }}
details.list summary {{ font-size:14px; font-weight:600; padding:6px 0; cursor:pointer }} details.list[open] summary {{ margin-bottom:6px }}
.findings li {{ margin:0 0 8px; line-height:1.5 }}
.mrow {{ display:grid; grid-template-columns:260px 1fr; gap:4px 12px; align-items:center; margin:2px 0 }}
.mlab {{ font-size:13px; font-weight:600 }} .mlab .mn {{ display:block; font-weight:400; font-size:12px; margin-left:17px }}
.strip {{ position:relative; height:42px; border-bottom:1px solid var(--line) }}
.strip u {{ position:absolute; top:0; bottom:0; border-left:1px dashed var(--line) }} .strip u.zero {{ border-left:1px solid var(--muted) }}
.strip u.all {{ border-left:2px dashed var(--muted); opacity:.7 }}
.strip .band {{ position:absolute; top:2px; bottom:2px; background:var(--muted); opacity:.18; border-radius:3px }}
.strip .mean {{ position:absolute; top:0; bottom:0; width:4px; margin-left:-2px; background:var(--fg); border-radius:2px }}
.strip .dot {{ position:absolute; width:9px; height:9px; margin-left:-4.5px; border-radius:50%; box-shadow:0 0 0 1.5px var(--card) }}
.strip .dot.dem {{ background:var(--dem-mark) }} .strip .dot.rep {{ background:var(--rep-mark) }}
.strip [data-t]:hover {{ outline:2px solid var(--fg); z-index:2 }}
.maxis {{ position:relative; height:16px; font-size:11px; color:var(--muted) }} .maxis span {{ position:absolute; transform:translateX(-50%) }}
td.dem {{ color:var(--dem) }} td.rep {{ color:var(--rep) }} #tip {{ max-width:340px }} table.mu td:first-child {{ white-space:nowrap }}
@media (max-width:560px) {{ .comprow, .mrow {{ grid-template-columns:1fr; gap:4px }} }}
</style></head><body><main>
{site.nav("wings.html")}
<h1>The party wings of the new Congress</h1>
<p class="lede">Every member-elect of the incoming House and Senate, sorted into four groups: two per party, by their votes and
stated policies. Then the incoming Congress is compared with the outgoing one to see which wings gained seats and which lost them.
Based on AP race calls through {AS_OF}: {len(H["inc"])} of 435 House seats and {len(S["inc"])} of 100 Senate seats. The rest
are still being counted.</p>

<h2>The four groups</h2>
<div class="wings">{cards}</div>

<h2>Who gained and who lost</h2>
<ul class="findings">
<li><b>Mainstream Democrats gained the most:</b> {net[("D", "Mainstream")]:+d} seats ({d("House", ("D", "Mainstream")):+d} House,
{d("Senate", ("D", "Mainstream")):+d} Senate). The Democrats who flipped Republican seats were mostly mainstream candidates: of
the {flips} new House Democrats who took a seat a Republican held, {newd[("Mainstream", "R")]} are Mainstream, from Zack Mullock
(NJ-2) to Pia Dandiya (FL-22). In the Senate, so are Roy Cooper (North Carolina), Sherrod Brown (Ohio), Josh Turek (Iowa), Adam
Hamilton (Kansas), Annie Andrews (South Carolina) and Scott Colom (Mississippi). Mainstream Democrats are now the largest bloc in the House,
{H["after"][("D", "Mainstream")]} of {sum(H["after"].values())} called seats.</li>
<li><b>Mainstream Republicans lost the most:</b> {net[("R", "Mainstream")]:+d} seats ({d("House", ("R", "Mainstream")):+d} House,
{d("Senate", ("R", "Mainstream")):+d} Senate). They held more of the competitive seats, so the wave hit them hardest: of the
{sum(hlost.values())} House Republicans who lost their general elections, {hlost["Mainstream"]} were Mainstream and
{hlost["Nationalist"]} Nationalist. In the Senate, Collins, Tillis, Cornyn, Ernst, Cassidy and Hyde-Smith are all leaving; their successors
are Democrats or Nationalist Republicans.</li>
<li><b>Progressive Democrats grew too:</b> {net[("D", "Progressive")]:+d} seats ({d("House", ("D", "Progressive")):+d} House,
{d("Senate", ("D", "Progressive")):+d} Senate). In the House, {newd[("Progressive", "D")]} of the
{sum(v for (w, _), v in newd.items() if w == "Progressive")} new progressives succeeded other Democrats, mostly in safe seats, and
{newd[("Progressive", "R")]} won Republican-held seats. The five new progressive senators won open Democratic seats (Michigan,
Minnesota, Illinois) or Republican-held ones (Maine, Texas). In the Senate they grew fastest, from {S["before"][("D", "Progressive")]} to
{S["after"][("D", "Progressive")]}, and are now {party_share(S, "after", ("D", "Progressive")):.0%} of the Democratic caucus, up from
{party_share(S, "before", ("D", "Progressive")):.0%}. In the House their share of the caucus barely moved
({party_share(H, "before", ("D", "Progressive")):.0%} to {party_share(H, "after", ("D", "Progressive")):.0%}).</li>
<li><b>Nationalist Republicans lost seats but gained ground inside their party:</b> {net[("R", "Nationalist")]:+d} seats overall
({d("House", ("R", "Nationalist")):+d} House, {d("Senate", ("R", "Nationalist")):+d} Senate). Because Mainstream Republicans lost
more, Nationalists are now a bigger share of a smaller conference: {party_share(H, "after", ("R", "Nationalist")):.0%} of House
Republicans (from {party_share(H, "before", ("R", "Nationalist")):.0%}) and {party_share(S, "after", ("R", "Nationalist")):.0%} of
Senate Republicans (from {party_share(S, "before", ("R", "Nationalist")):.0%}).</li>
</ul>

<h3>House</h3>
{change_table("House")}
<h3>Senate</h3>
{change_table("Senate")}
<p class="note">"Outgoing" is the current Congress and "incoming" the new one, counting only called seats. Members leaving seats whose
successors aren't called yet are left out of both sides, {"as are the " + str(S_OPEN) + " uncalled Senate seats" if S_OPEN != 1 else "as is the uncalled Senate seat"}. Members who switch chambers count as
leaving one and arriving in the other: Barry Moore, Julia Letlow, Andy Barr, Kevin Hern and Harriet Hageman (House to Senate, all
Republicans) and Chris Pappas (Democrat). "Share of own party" is the wing's share of its party's seats in that chamber.
Independents Bernie Sanders and Angus King are counted with the Democrats.</p>

<h2>Head to head: who did better against whom</h2>
<p>Every competitive race, meaning one the forecast didn't rate Safe for either party (Likely, Lean, Tilt or Toss-up), with both
nominees sorted into wings: {len(HC)} called House races and {len(MU) - len(HC)} Senate races. Win counts mostly reflect how red or
blue the seats were, since Progressive-vs-Nationalist races were fought on much redder ground. So the yardstick here is how far the
Democrat beat the forecast margin, the pre-election expectation for that seat, which already counts its lean, incumbency and polls.
A bigger number means the Democrat did better than expected, so the Republican did worse.</p>
<ul class="findings">
<li><b>The wave lifted every matchup.</b> On average, House Democrats beat the forecast by {hc_avg:+.1f} points, and every matchup
landed between {min(pm.values()):+.1f} and {max(pm.values()):+.1f}. Next to a 7-point wave, the wings mattered a little, not a lot.</li>
<li><b>Mainstream Democrats against Nationalist Republicans was the best matchup for Democrats</b> ({pm[("Mainstream", "Nationalist")]:+.1f}),
and <b>Progressive Democrats against Nationalist Republicans the weakest</b> ({pm[("Progressive", "Nationalist")]:+.1f}, only
{len(in_pair(HC, ("Progressive", "Nationalist")))} races). Against the same Mainstream Democrats, Nationalist Republicans fell
{pm[("Mainstream", "Nationalist")] - pm[("Mainstream", "Mainstream")]:.1f} points further behind the forecast than Mainstream
Republicans did. Overall, Democrats beat the forecast by {mean(vs_nat):+.1f} against Nationalists and {mean(vs_main):+.1f} against
Mainstream Republicans.</li>
<li><b>Progressive Democrats did about as well as Mainstream ones against Mainstream Republicans</b>
({pm[("Progressive", "Mainstream")]:+.1f} vs. {pm[("Mainstream", "Mainstream")]:+.1f}), but worse against Nationalists
({pm[("Progressive", "Nationalist")]:+.1f} vs. {pm[("Mainstream", "Nationalist")]:+.1f}). The Progressive rows rest on few races,
{len(in_pair(HC, ("Progressive", "Mainstream")))} and {len(in_pair(HC, ("Progressive", "Nationalist")))}, so one race can swing them.
CA-22 (Randy Villegas over David Valadao, only {next(r["counted"] for r in HC if r["district"] == "CA-22")}% counted) alone lifts the
Progressive-vs-Mainstream average by {pm[("Progressive", "Mainstream")] - mean([r["vs_forecast"] for r in in_pair(HC, ("Progressive", "Mainstream")) if r["district"] != "CA-22"]):.1f} points.</li>
<li><b>How sure is this?</b> Not very. The gap between the best and worst matchups is about {max(pm.values()) - min(pm.values()):.1f}
points, and the race-to-race spread is about 5 points. Only the Mainstream-vs-Nationalist edge over Mainstream-vs-Mainstream rests on
enough races to mean much ({len(in_pair(HC, ("Mainstream", "Nationalist")))} and {len(in_pair(HC, ("Mainstream", "Mainstream")))}),
and even it is about {z:.1f} standard errors: suggestive, not proven.</li>
</ul>

<h3>House: competitive races ({len(HC)})</h3>
<div class="panel">
<p class="note" style="margin:0 0 8px">How far the Democrat beat the forecast margin, in points. Each dot is a race: blue where the Democrat
won, red where the Republican won. The dark tick is the matchup's average, the shaded band ±1 standard error, and the dashed line the
average of all {len(HC)} races ({hc_avg:+.1f}).</p>
{strip(HC, LO, HI, hc_avg)}
</div>
{matchup_table(HC)}

<h3>The upsets ({len(UPS)})</h3>
<p>The {len(UPS)} races the favorite lost: {sum(r["chamber"] == "House" for r in UPS)} in the House plus the Senate races in {" and ".join(r["district"] for r in UPS if r["chamber"] == "Senate")}.
Every one was a Democrat beating a favored Republican.</p>
<ul class="findings">
<li><b>The pattern repeats, more sharply.</b> Upsets with a Mainstream Democrat against a Nationalist Republican were the biggest
misses ({um[("Mainstream", "Nationalist")]:+.1f} vs. the forecast). Upsets where both nominees were Mainstream missed by
{um[("Mainstream", "Mainstream")]:+.1f}. Nationalist Republicans who lost as favorites tended to lose by a lot, while Mainstream ones
tended to lose narrowly.</li>
<li><b>But Nationalists weren't upset more often.</b> Of the House races where the Republican was favored, Democrats pulled the upset in
{urate[("Mainstream", "Nationalist")][0]} of {urate[("Mainstream", "Nationalist")][1]} Mainstream-vs-Nationalist races and
{urate[("Mainstream", "Mainstream")][0]} of {urate[("Mainstream", "Mainstream")][1]} Mainstream-vs-Mainstream races, about a third
each. Progressives pulled {urate[("Progressive", "Mainstream")][0]} of {urate[("Progressive", "Mainstream")][1]} against Mainstream
Republicans and {urate[("Progressive", "Nationalist")][0]} of {urate[("Progressive", "Nationalist")][1]} against Nationalists.</li>
<li><b>Most upset winners were Mainstream Democrats:</b> {sum(r["d_wing"] == "Mainstream" for r in UPS)} of {len(UPS)}, mostly
because they were the nominees in most of the Republican-leaning seats in play.</li>
</ul>
<div class="panel">
{strip(UPS, LO, HI, up_avg)}
</div>
{matchup_table(UPS, upsets=True)}

<h3>Senate ({len(MU) - len(HC)} competitive races)</h3>
<p>Too few races to average by matchup, so here they are one by one. Senate Democrats beat the forecast by much less than House
Democrats ({mean([r["vs_forecast"] for r in MU if r["chamber"] == "Senate"]):+.1f} on average): the Senate forecasts were closer.
The widest misses the other way were two independents, in Idaho and South Dakota, and Jeff Merkley in Oregon.</p>
<div class="scroll"><table class="small"><thead><tr><th>State</th><th>Democrat or independent</th><th>Republican</th>
<th class="num">Forecast</th><th class="num">Result</th><th class="num">D beat forecast by</th><th>Winner</th></tr></thead>
<tbody>{senate_rows()}</tbody></table></div>
<p class="note">Margins are AP's count as of {AS_OF} (Democrat or independent minus Republican; Maine's is the first round), and will move
as counting finishes. {len(PARTIAL)} races are still under 90% counted ({", ".join(f'{r["district"]} {r["counted"]}%' for r in PARTIAL)}). Losing nominees were classified with the same rules as members: losing incumbents from their records, everyone else
from platforms and endorsements. Many losing Democratic nominees in red seats left little record, and those default to Mainstream at low
confidence. Dropping every low-confidence placement leaves too few races to compare, so treat the Progressive rows especially loosely.</p>

<h2>Every member</h2>
<h3>House ({len(H["inc"])} called seats)</h3>
{lists("House", "district")}
<h3>Senate ({len(S["inc"])} called seats)</h3>
{lists("Senate", "state")}

<h2>Method and caveats</h2>
<ul class="note findings">
<li><b>Two wings per party, on purpose.</b> This scheme is simple. It folds moderates and leadership loyalists into "Mainstream", and
it puts libertarians like Rand Paul with the Nationalists because of their foreign-aid votes. Both parties have more factions than this.</li>
<li><b>Votes decide where they can.</b> For sitting members, the wing comes from recorded roll calls: the Israel votes above for
Democrats, the Ukraine votes above for Republicans (sources: clerk.house.gov, and Voteview for the Senate). Where the votes don't
settle it (for example, a Republican who opposed the 2024 aid but not the 2025 ban), the member is placed on other policies: immigration,
trade, caucus memberships, 2020 election objections.</li>
<li><b>Newcomers are provisional.</b> Members with no voting record are placed on their platforms, endorsements and backers;
{n_low} of the placements are marked low confidence. Caucuses form in December and January, and some newcomers will vote differently
than they campaigned.</li>
<li><b>The Israel rule is a choice, and it matters in the House.</b> Without it, the House would have more Progressive Democrats, because
a number of members with left economic records voted to keep the Israel aid in July 2026. In the Senate, it moves only one senator
(Richard Blumenthal).</li>
<li><b>Research by AI agents, checked against the roll calls.</b> Each member was researched from public sources, and the wing was then
recomputed from the recorded votes with one rule for everyone. Caucus memberships and endorsements came partly from Wikipedia and may
contain errors. Three California seats (CA-4, CA-7 and CA-40) were same-party races, and those entries show the current leader.</li>
</ul>
</main><div id="tip"></div>
<script>
const tip = document.getElementById("tip");
document.addEventListener("pointerover", e => {{ const t = e.target.closest("[data-t]"); if (!t) return;
  tip.textContent = t.dataset.t; tip.style.display = "block"; }});
document.addEventListener("pointermove", e => {{ if (tip.style.display !== "block") return;
  tip.style.left = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8) + "px"; tip.style.top = (e.clientY + 14) + "px"; }});
document.addEventListener("pointerout", e => {{ if (e.target.closest("[data-t]")) tip.style.display = "none"; }});
</script></body></html>
"""
(HERE / "wings.html").write_text(page)
print("wings.html written:", {LABEL[k]: (H["after"][k], S["after"][k]) for k in KEYS})
