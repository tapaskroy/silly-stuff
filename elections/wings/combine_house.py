#!/usr/bin/env python3
"""Apply the roll-call rules (RULES.md) to every member-elect in house_incoming.json, in place.

Each entry carries the research agent's reading (agent_wing; for Democrats econ and, when no 2026 vote decides it, israel).
Recorded votes override it: Democrats by the 2026 Massie Israel-aid amendment, Republicans by the 2025 Greene Ukraine-ban amendment,
then the 2024 Ukraine supplemental. Newcomers (returning false) have no votes. Rerun after adding a newly called member.
Usage: python3 wings/combine_house.py   (prints any member whose wing changes)
"""
import json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

W = Path(__file__).parent
V = W / "votes"


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower() if c.isalpha())


def roll(f):
    """{(state, normalized surname): vote} from a clerk.house.gov roll-call file."""
    t = (V / f).read_text()
    out, seen = {}, Counter()
    for m in re.finditer(r'<legislator [^>]*?party="(\w)" state="(\w\w)"[^>]*>(.*?)</legislator>\s*<vote>(.*?)</vote>', t):
        party, st, name, vote = m.groups()
        sur, _, first = name.split(" (")[0].partition(", ")  # "Scott, Austin" when two members share a surname
        seen[(st, norm(sur))] += 1
        out[(st, norm(sur))] = vote
        if first:
            out[(st, norm(first + sur))] = vote
    for k, n in seen.items():
        if n > 1:
            out[k] = None  # ambiguous surname: only the first-name key matches
    return out


ISRAEL26 = roll("2026_243.xml")   # Massie amendment to strip $3.3B in Israel military aid (Jul 15, 2026): Yea = against the aid
ISRAEL24 = roll("2024_152.xml")   # H.R. 8034 Israel supplemental (Apr 20, 2024)
UKR24 = roll("2024_151.xml")      # H.R. 8035 Ukraine supplemental: Nay = against the aid
UKR25 = roll("2025_209.xml")      # Greene amendment barring Ukraine aid in the FY26 defense bill (Jul 18, 2025): Yea = against the aid
OBJ = [roll("2021_010.xml"), roll("2021_011.xml")]  # objections to Arizona's and Pennsylvania's electoral votes, Jan 6, 2021


def vote(table, m):
    if not m.get("returning"):
        return None  # a newcomer can share a surname with a departing member (Trever and Troy Nehls)
    st = m["district"].split("-")[0]
    words = [w for w in re.sub(r"\(.*?\)|,? (Jr|Sr|II|III)\.?$", "", m["name"]).split() if w]
    keys = [words[0] + words[-1]] + [" ".join(words[-3:]), " ".join(words[-2:]), words[-1]]  # first+last, then compound surnames
    for k in keys:
        v = table.get((st, norm(k)))
        if v:
            return v
    return None



DECISIVE = ("Yea", "Aye", "Nay", "No")


def apply(m):
    """The member's wing and the reason, from votes where they decide it, else the agents' reading."""
    if m["party"] == "D":
        v26, v24 = vote(ISRAEL26, m), vote(ISRAEL24, m)
        if v26 in ("Yea", "Aye"):
            israel, basis = "critical", "2026 vote on the Massie Israel-aid amendment"
        elif v26 in ("Nay", "No"):
            israel, basis = "supports", "2026 vote on the Massie Israel-aid amendment"
        else:
            israel = m.get("israel", "unknown")
            basis = (f"no Yea/Nay on the 2026 Massie amendment ({v26}): endorsements and statements" if v26
                     else "newcomer or no 2026 vote: endorsements and statements")
        left = m.get("econ") == "left"
        return dict(israel=israel, israel_vote_2026=v26, israel_vote_2024=v24, wing="Progressive" if left and israel != "supports" else "Mainstream",
                    wing_without_israel_rule="Progressive" if left else "Mainstream", basis=basis)
    u24, u25 = vote(UKR24, m), vote(UKR25, m)
    obj = [vote(o, m) for o in OBJ]
    out = dict(ukraine_2024=u24, ukraine_ban_2025=u25, objected_2021=any(o in ("Yea", "Aye") for o in obj) if any(obj) else None)
    if u25 in ("Yea", "Aye"):
        out.update(wing="Nationalist", basis="voted for the 2025 Greene amendment barring Ukraine aid")
    elif u24 in ("Yea", "Aye"):
        out.update(wing="Mainstream", basis="voted for the 2024 Ukraine aid and against the 2025 ban" if u25 in ("Nay", "No")
                   else f"voted for the 2024 Ukraine aid; {'did not vote on' if u25 else 'no recorded vote on'} the 2025 ban")
    elif not m.get("returning"):
        out.update(wing=m["agent_wing"], basis="newcomer: placed on platform and endorsements")
    elif u24 in ("Nay", "No") and u25 in ("Nay", "No"):
        out.update(wing=m["agent_wing"], basis="mixed record (opposed the 2024 aid, not the 2025 ban): placed on other policies")
    elif u25 in ("Nay", "No"):
        out.update(wing=m["agent_wing"], basis=f"{'no' if not u24 else u24 + ' on the'} 2024 Ukraine aid vote, against the 2025 ban: placed on other policies")
    elif u24 in ("Nay", "No"):
        out.update(wing=m["agent_wing"], basis="opposed the 2024 aid, no recorded vote on the 2025 ban: placed on other policies")
    else:
        out.update(wing=m["agent_wing"], basis="no deciding Ukraine vote on record: placed on other policies")
    return out


if __name__ == "__main__":
    f = W / "house_incoming.json"
    members = json.loads(f.read_text())
    changed = []
    for m in members:
        new = apply(m)
        if new["wing"] != m.get("wing"):
            changed.append((m["district"], m["name"], m.get("wing"), new["wing"]))
        m.update(new)
    f.write_text(json.dumps(members, indent=1, ensure_ascii=False))
    print(len(members), "members;", Counter((m["party"], m["wing"]) for m in members))
    for c in changed:
        print("  wing changed:", *c)
