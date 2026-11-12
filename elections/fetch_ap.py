#!/usr/bin/env python3
"""Fill results.json from AP's live election-results feed (the one behind AP's embeddable results widgets).

Usage: python3 fetch_ap.py [--dry-run]
       python3 fetch_ap.py --count-to review/ap_count.json
  --count-to writes AP's current count for every race to that file instead (same shape as results.json, margins at any share
  counted, ranked-choice races at their first-round shares, note = percent of expected vote in), plus AP's national House vote
  to national_vote.json beside it. results.json is not touched. The wings head-to-head and the upset review read these files.
For each scored race it finds the AP race (same state and office, both our candidates on AP's ballot) and records:
  winner     our surname for AP's declared winner (AP marks it in progress.json: winner "X", calledAt); for the Louisiana House races,
             where the model lists several names per side, the side of the winner's party, with winner_name for display
  margin     AP's count, first-listed minus second-listed share of the total vote, only once AP estimates at least
             MARGIN_EEVP percent of the expected vote is in; otherwise null (an early count says little about the final margin).
             Ranked-choice races are left null: AP's first-round shares aren't the final-round margin.
  status     "called" once AP calls it, back to "pending" if AP withdraws the call; note carries AP's tabulation state and expected vote counted
Entries marked "final" or "certified", or filled from a source other than AP, are left alone.
Margins from AP are provisional: they are replaced by state election office figures at the one-week recheck and at certification.
Run build_scorecard.py afterwards.
"""
import gzip
import json
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
FEED = "https://interactives.apelections.org/election-results/data-live/2026-11-03/results/national/"
OFFICE = {"senate": "U.S. Senate", "house": "U.S. House", "governors": "Governor"}
MARGIN_EEVP = 95
SOURCE = "AP election results feed"
DRY = "--dry-run" in sys.argv
COUNT_TO = Path(sys.argv[sys.argv.index("--count-to") + 1]) if "--count-to" in sys.argv else None
if COUNT_TO:
    MARGIN_EEVP = 0


def get(name):
    req = urllib.request.Request(FEED + name, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)  # served gzipped either way


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())


def same(ours, ap_last):
    """Our surname vs AP's last name, allowing for suffixes and compound names ("Sullivan Jr." vs "Sullivan")."""
    a, b = norm(ours), norm(ap_last)
    return bool(a) and bool(b) and (a == b or a.startswith(b) or b.startswith(a) or a.endswith(b) or b.endswith(a))


def party_ok(ours, ap_party):
    """Our D/R/I against AP's party code; I covers every non-major-party label."""
    return {"D": ap_party == "Dem", "R": ap_party == "GOP"}.get(ours, ap_party not in ("Dem", "GOP"))


meta, prog = get("metadata.json"), get("progress.json")
# House races where the frozen model lists several candidates per side (Louisiana's crowded fields): scored by party.
PARTY_SIDE = {("house", r["district"]) for r in json.loads((HERE / "frozen" / "house_model.json").read_text())["races"]
              if not r.get("fixed") and ";" in (r.get("dem") or "") + (r.get("rep") or "")}
names = {v["stateName"]: v["statePostal"] for v in prog.values()}
results = json.loads((HERE / "results.json").read_text())
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
by_state = {}
for rid, m in meta.items():
    by_state.setdefault((m.get("statePostal"), m.get("officeName")), []).append(rid)

problems, called, changed = [], [], 0
for ch, races in results.items():
    if ch.startswith("_"):
        continue
    for key, x in races.items():
        # results.json keeps final, certified and non-AP entries as they are; the count file always takes AP's current count
        if not COUNT_TO and (x.get("status") in ("final", "certified") or x.get("source") not in (None, SOURCE)):
            continue
        (a, pa), (b, pb) = [(s.rsplit(" (", 1)[0], s.rsplit("(", 1)[1].rstrip(")")) for s in x["candidates"].split(" vs ")]
        party = {a: pa, b: pb}
        st, seat = (key.split("-") if ch == "house" else (names.get(key), None))
        if (ch, key) in PARTY_SIDE:  # several names per side in the model: match the seat, score by the winner's party
            cands = [rid for rid in by_state.get((st, OFFICE[ch]), []) if str(meta[rid].get("seatNum")) == seat]
        else:
            cands = [rid for rid in by_state.get((st, OFFICE[ch]), [])
                     if sum(any(same(o, c["last"]) for c in meta[rid]["candidates"].values()) for o in (a, b)) == 2]
        if ch == "house" and len(cands) > 1:
            cands = [rid for rid in cands if str(meta[rid].get("seatNum")) == seat] or cands
        if len(cands) != 1:
            problems.append(f"{ch} {key} ({a} vs {b}): {len(cands)} AP matches")
            continue
        m, p = meta[cands[0]], prog.get(cands[0], {})
        share = {c["candidateID"]: c.get("votePct", 0) for c in p.get("candidates", [])}
        if (ch, key) in PARTY_SIDE:
            side = {o: [c for c in m["candidates"].values() if c["party"] == {"D": "Dem", "R": "GOP"}[party[o]]] for o in (a, b)}
        else:
            # Two AP candidates can share a surname (Nevada's two Fords, Alaska's two Sullivans): prefer the party match, then the exact name.
            ap = {o: max((c for c in m["candidates"].values() if same(o, c["last"])),
                         key=lambda c: (party_ok(party[o], c["party"]), norm(o) == norm(c["last"]))) for o in (a, b)}
            if ap[a]["candidateID"] == ap[b]["candidateID"] or not all(party_ok(party[o], ap[o]["party"]) for o in (a, b)):
                problems.append(f"{ch} {key}: AP candidates {ap[a]['last']} ({ap[a]['party']}) / {ap[b]['last']} ({ap[b]['party']}) don't fit {a} ({pa}) / {b} ({pb})")
                continue
            side = {o: [ap[o]] for o in (a, b)}
        # AP marks the call in the vote-count feed: winner "X" (and "R" for a runoff spot, which is not a win) plus calledAt.
        calls = {c["candidateID"]: c for c in p.get("candidates", []) if c.get("winner") == "X"}
        winners = [dict(c, winnerDateTime=calls[i].get("calledAt")) for i, c in m["candidates"].items() if i in calls]
        eevp = p.get("eevp", 0) or 0
        new = dict(x)
        new["note"] = f"{eevp:.0f}" if COUNT_TO else f"AP: {m.get('raceCallStatus')}; {m.get('tabulationStatus')}; {eevp:.0f}% of expected vote in"
        if winners:
            won = winners[0]
            w = [o for o in (a, b) if any(c["candidateID"] == won["candidateID"] for c in side[o])]
            if not w:
                problems.append(f"{ch} {key}: AP winner {won['last']} ({won['party']}) is on neither side ({a} {pa} / {b} {pb})")
                continue
            new.update(winner=w[0], status="called", called_by="AP", source=SOURCE,
                       called_at=won.get("winnerDateTime") or x.get("called_at") or now)
            if norm(won["last"]) != norm(w[0]):
                new["winner_name"] = won["last"]
            if x.get("winner") != w[0]:
                called.append(f"{ch} {key}: {won['last']} ({won['party']})")
        elif x.get("winner"):  # AP withdrew its call: stop scoring the race until AP calls it again
            problems.append(f"{ch} {key}: AP withdrew its call for {x['winner']} ({m.get('raceCallStatus')}); race set back to pending")
            new.update(winner=None, status="pending", called_by=None, called_at=None)
            new.pop("winner_name", None)
        total = {o: sum(share.get(c["candidateID"], 0) for c in side[o]) for o in (a, b)}
        new["margin"] = (round(total[a] - total[b], 1)
                         if winners and eevp >= MARGIN_EEVP and (COUNT_TO or not m.get("rankedChoice")) else None)
        if new != x:
            changed += 1
            races[key] = new

results["_updated"] = now
results["_sources"] = (f"Winners: AP race calls. Margins: AP's count once {MARGIN_EEVP}%+ of the expected vote is in, "
                       "replaced by state election office figures at the one-week recheck and at certification.")
if COUNT_TO:
    COUNT_TO.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    # AP's national House vote: the U.S. House race with state "US"
    nid = next(k for k, v in meta.items() if v.get("officeName") == OFFICE["house"] and v.get("statePostal") == "US")
    pct = {meta[nid]["candidates"][c["candidateID"]]["party"]: c for c in prog[nid]["candidates"]}
    (COUNT_TO.parent / "national_vote.json").write_text(json.dumps(
        {"_source": "AP national U.S. House vote aggregate (the race with state 'US' in AP's results feed)", "as_of": now,
         "eevp": prog[nid].get("eevp"), "dem_pct": pct["Dem"]["votePct"], "rep_pct": pct["GOP"]["votePct"],
         "other_pct": pct.get("Oth", {}).get("votePct"), "dem_votes": pct["Dem"]["voteCount"], "rep_votes": pct["GOP"]["voteCount"]}, indent=1))
elif not DRY:
    (HERE / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
print(f"{'(dry run) ' if DRY else ''}{changed} entries updated; {len(called)} new calls")
for c in called:
    print("  called:", c)
for p in problems:
    print("  CHECK:", p)
