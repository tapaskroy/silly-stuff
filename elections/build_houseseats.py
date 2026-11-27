#!/usr/bin/env python3
"""House seats and House popular vote by state, from AP's live results feed: writes houseseats.json and houseseats.html.

Seats: AP's calls (winner "X" in progress.json). Votes: every candidate's AP count, summed by party.
Checks before writing (the build stops if one fails):
  - the state vote sums equal AP's own national House aggregate (the race with state "US");
  - each race's candidate counts add up to AP's reported total;
  - every called race in results.json has the same winning party here.
Usage: python3 build_houseseats.py
"""
import gzip
import html
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
FEED = "https://interactives.apelections.org/election-results/data-live/2026-11-03/results/national/"
PARTY = {"Dem": "D", "GOP": "R"}


def get(name):
    req = urllib.request.Request(FEED + name, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)


meta, prog = get("metadata.json"), get("progress.json")
house = {k: v for k, v in meta.items() if v.get("officeName") == "U.S. House"}
nid = next(k for k, v in house.items() if v["statePostal"] == "US")
per_state = Counter(v["statePostal"] for k, v in house.items() if k != nid)
assert sum(per_state.values()) == 435, sum(per_state.values())

S = defaultdict(Counter)
names, notes = {}, defaultdict(list)
own = {}  # district -> winning party, for the cross-check
for k, m in house.items():
    if k == nid:
        continue
    st, p = m["statePostal"], prog[k]
    names[st] = p["stateName"]
    dist = f"{st}-{m['seatNum']}" if per_state[st] > 1 else f"{st}-AL"
    cands = p.get("candidates", [])
    total = sum(c.get("voteCount", 0) or 0 for c in cands)
    reported = m.get("parameters", {}).get("vote", {}).get("total")
    assert reported is None or total == reported, f"{dist}: candidate counts {total} != AP total {reported}"
    S[st]["seats"] += 1
    for c in cands:
        S[st]["v" + PARTY.get(m["candidates"][c["candidateID"]]["party"], "O")] += c.get("voteCount", 0) or 0
    won = [c for c in cands if c.get("winner") == "X"]
    if won:
        own[dist] = PARTY.get(m["candidates"][won[0]["candidateID"]]["party"], "O")
        S[st][own[dist]] += 1
    else:
        S[st]["U"] += 1
        notes[st].append(f"{dist} not called yet (AP: {m.get('raceCallStatus')})")
    parties = Counter(PARTY.get(c["party"], "O") for c in m["candidates"].values())
    label = ", ".join(f"{c['last']} ({PARTY.get(c['party'], 'other')})" for c in m["candidates"].values())
    if len(m["candidates"]) == 1:
        notes[st].append(f"{dist}: {label} unopposed" + ("; no votes counted" if total == 0 else ""))
    elif not parties["R"] or not parties["D"]:
        notes[st].append(f"{dist}: no {'Republican' if not parties['R'] else 'Democrat'} on the ballot ({label})")
    if m.get("rankedChoice"):  # AP counts the first round only, called or not
        notes[st].append(f"{dist}: ranked-choice; these are first-round counts")

# Check 1: the state sums equal AP's national aggregate.
nat = {PARTY.get(meta[nid]["candidates"][c["candidateID"]]["party"], "O"): c["voteCount"] for c in prog[nid]["candidates"]}
summed = {x: sum(s["v" + x] for s in S.values()) for x in "DRO"}
assert summed == nat, f"state sums {summed} != AP national {nat}"
# Check 2: every called race we score has the same winning party.
res = json.loads((HERE / "results.json").read_text())["house"]
for d, x in res.items():
    if x.get("status") == "called":
        side = dict((s.rsplit(" (", 1)[0], s.rsplit("(", 1)[1].rstrip(")")) for s in x["candidates"].split(" vs "))
        assert own.get(d) == side[x["winner"]], f"{d}: AP feed winner party {own.get(d)} != results.json {side[x['winner']]}"
assert not any(s["O"] for s in S.values()), "a third-party winner: add a column for it"

now = datetime.now(timezone.utc)
eevp = prog[nid].get("eevp")
pct = lambda a, b: round(100 * a / b, 1) if b else None
rows = []
for st in sorted(S, key=lambda s: (-S[s]["seats"], names[s])):  # most seats first
    s = S[st]
    vt = s["vD"] + s["vR"] + s["vO"]
    rows.append(dict(state=names[st], postal=st, seats=s["seats"], D=s["D"], R=s["R"], uncalled=s["U"],
                     D_seat_pct=pct(s["D"], s["D"] + s["R"]), R_seat_pct=pct(s["R"], s["D"] + s["R"]),
                     D_votes=s["vD"], R_votes=s["vR"], other_votes=s["vO"],
                     D_vote_pct=pct(s["vD"], vt), R_vote_pct=pct(s["vR"], vt), other_vote_pct=pct(s["vO"], vt), notes=notes[st]))
T = {x: sum(r[x] for r in rows) for x in ("seats", "D", "R", "uncalled", "D_votes", "R_votes", "other_votes")}
VT = T["D_votes"] + T["R_votes"] + T["other_votes"]
T.update(D_seat_pct=pct(T["D"], T["D"] + T["R"]), R_seat_pct=pct(T["R"], T["D"] + T["R"]),
         D_vote_pct=pct(T["D_votes"], VT), R_vote_pct=pct(T["R_votes"], VT), other_vote_pct=pct(T["other_votes"], VT))
(HERE / "houseseats.json").write_text(json.dumps({"_source": "AP election results feed", "as_of": now.isoformat(timespec="seconds"),
                                                   "national_eevp": eevp, "total": T, "states": rows}, indent=1))

AS_OF = now.strftime("%b %-d, %Y")
f = lambda x: "—" if x is None else f"{x:.1f}%"
n = lambda x: f"{x:,}"


def bar(d, r, o=0):
    t = d + r + o
    return ("" if not t else f'<span class="pbar">' + "".join(
        f'<i class="{c}" style="width:{100 * v / t:.2f}%"></i>' for c, v in (("dem", d), ("ind", o), ("rep", r)) if v) + "</span>")


def gap(r):
    if r["D_seat_pct"] is None:
        return '<td class="num muted" data-v="">—</td>'
    g = r["D_seat_pct"] - r["D_vote_pct"]
    return f'<td class="num {"dem" if g > 0 else "rep" if g < 0 else ""}" data-v="{g:.1f}">{"D" if g > 0 else "R" if g < 0 else ""}{"+" if g else ""}{abs(g):.1f}</td>'


def row(r, total=False):
    tip = html.escape("; ".join(r.get("notes") or []))
    mark = f' <sup class="fn" title="{tip}">{"*"}</sup>' if tip else ""
    name = "<b>Total</b>" if total else f'{html.escape(r["state"])}{mark}'
    return (f'<tr{" class=tot" if total else ""}><td class="st" data-v="{"~" if total else html.escape(r["state"])}">{name}</td>'
            f'<td class="num" data-v="{r["seats"]}">{r["seats"]}</td>'
            f'<td class="num dem" data-v="{r["D"]}">{r["D"]}</td><td class="num rep" data-v="{r["R"]}">{r["R"]}</td>'
            f'<td class="num muted" data-v="{r["uncalled"]}">{r["uncalled"] or ""}</td>'
            f'<td class="num" data-v="{r["D_seat_pct"] if r["D_seat_pct"] is not None else ""}">{f(r["D_seat_pct"])}</td>'
            f'<td class="num" data-v="{r["R_seat_pct"] if r["R_seat_pct"] is not None else ""}">{f(r["R_seat_pct"])}</td>'
            f'<td>{bar(r["D"], r["R"])}</td>'
            f'<td class="num" data-v="{r["D_vote_pct"]}">{f(r["D_vote_pct"])}</td><td class="num" data-v="{r["R_vote_pct"]}">{f(r["R_vote_pct"])}</td>'
            f'<td class="num muted" data-v="{r["other_vote_pct"]}">{f(r["other_vote_pct"])}</td>'
            f'<td>{bar(r["D_votes"], r["R_votes"], r["other_votes"])}</td>{gap(r)}</tr>')


noted = "".join(f'<li><b>{html.escape(r["state"])}</b>: {html.escape("; ".join(r["notes"]))}.</li>' for r in rows if r["notes"])
H = ["State", "Seats", "D won", "R won", "Uncalled", "D seats", "R seats", "Seats", "D vote", "R vote", "Other", "Vote", "Seat − vote gap"]
SORT = [1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1]
head = "".join(f'<th{(" class=\"num desc\"" if i == 1 else " class=num") if 0 < i < 13 and SORT[i] else ""}{" data-sort" if SORT[i] else ""}>{h}</th>' for i, h in enumerate(H))
css = (HERE / "page.css").read_text()
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{site.ROBOTS}
<title>House Seats by State</title>
<style>{css}
table.main {{ min-width:1000px }} table.main > thead th {{ white-space:nowrap }} th[data-sort] {{ cursor:pointer; user-select:none }}
th[data-sort]:hover {{ color:var(--fg) }} th.asc::after {{ content:" ▲" }} th.desc::after {{ content:" ▼" }}
table.main > tbody > tr > td {{ padding:6px 10px; vertical-align:middle }} table.main > thead th.num, td.num {{ text-align:right }}
tr.tot td {{ padding:8px 10px; border-top:2px solid var(--fg); font-weight:700; vertical-align:middle }} sup.fn {{ color:var(--deep); cursor:help }}
.pbar {{ width:110px }} ul.notes li {{ margin:0 0 4px }}
</style></head><body><main>
{site.nav("houseseats.html")}
<h1>House seats and House vote, state by state</h1>
<p class="lede">For each state: the seats each party won in the 2026 House elections, as a share of the seats AP has called, and
each party's share of all votes cast for House candidates. The last column shows how far the Democratic share of seats sits
above (D+) or below (R+) the Democratic share of the vote. AP count as of {AS_OF}, with about {eevp:.1f}% of the expected
national vote in. Click a column heading to sort.</p>
<div class="summary">
<div class="card"><b class="dem">{T["D"]}</b><span>Democratic seats ({f(T["D_seat_pct"])} of called)</span></div>
<div class="card"><b class="rep">{T["R"]}</b><span>Republican seats ({f(T["R_seat_pct"])} of called)</span></div>
<div class="card"><b>{T["uncalled"]}</b><span>seats not yet called</span></div>
<div class="card"><b>D {f(T["D_vote_pct"])}</b><span>national House vote ({n(T["D_votes"])})</span></div>
<div class="card"><b>R {f(T["R_vote_pct"])}</b><span>national House vote ({n(T["R_votes"])})</span></div>
</div>
<div class="wrap"><table class="main" id="t"><thead><tr>{head}</tr></thead>
<tbody>{"".join(row(r) for r in rows)}</tbody><tfoot>{row(T, total=True)}</tfoot></table></div>
<div class="method" style="margin-top:16px"><b>Reading the vote shares.</b> A state's vote share counts every House race in it,
so races without a candidate from one party pull that party's share down: California's top-two system puts two Democrats (or
two Republicans) on some ballots, and unopposed incumbents get every vote, or none at all where the state doesn't count unopposed
races. States marked <sup class="fn">*</sup> have such races (hover the mark, or see the list below). Seat shares leave out
uncalled seats. The counts are AP's and will move a little as states certify.
<ul class="notes">{noted}</ul>
<b>Checks.</b> The state vote totals add up exactly to AP's own national House count, every race's candidate counts add up to
AP's total for that race, and every called race matches the winner on the scorecard.</div>
<footer>Source: AP election results. Data: <a href="houseseats.json" style="color:inherit">houseseats.json</a>.</footer>
</main>
<script>
document.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => {{
  const i = [...th.parentNode.children].indexOf(th), tb = document.querySelector("#t tbody");
  const asc = !th.classList.contains("desc") && th.classList.contains("asc") ? false : !th.classList.contains("asc");
  document.querySelectorAll("th[data-sort]").forEach(h => h.classList.remove("asc", "desc"));
  th.classList.add(asc ? "asc" : "desc");
  const key = tr => {{ const v = tr.children[i].dataset.v; return v === "" ? null : isNaN(+v) ? v : +v; }};
  [...tb.rows].sort((a, b) => {{ const x = key(a), y = key(b);
    if (x === null) return 1; if (y === null) return -1;
    return (typeof x === "string" ? x.localeCompare(y) : x - y) * (asc ? 1 : -1); }}).forEach(r => tb.appendChild(r));
}}));
</script></body></html>"""
(HERE / "houseseats.html").write_text(page)
print(f"houseseats.html written: D {T['D']}, R {T['R']}, uncalled {T['uncalled']}; vote D {f(T['D_vote_pct'])} R {f(T['R_vote_pct'])}; all checks passed")
