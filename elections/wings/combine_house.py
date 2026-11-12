# Combine the agents' per-member research and apply one rule to every member, using House roll calls where they exist.
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


members = []
for f in sorted(W.glob("out*.json")):
    members += json.loads(f.read_text())

rows = []
for m in members:
    s = m.get("signals", {})
    r = {"district": m["district"], "name": m["name"], "party": m["party"], "returning": m.get("returning"),
         "agent_wing": m["wing"], "confidence": m.get("confidence"), "evidence": m.get("evidence"), "sources": m.get("sources", [])}
    if m["party"] == "D":
        v26, v24 = vote(ISRAEL26, m), vote(ISRAEL24, m)
        if v26 in ("Yea", "Aye"):
            israel = "critical"
        elif v26 in ("Nay", "No"):
            israel = "supports"
        else:  # no 2026 vote (newcomer): fall back to the agent's reading of endorsements and statements
            israel = s.get("israel", "unknown")
        left = s.get("economic") == "left"
        r.update(econ=("left" if left else s.get("economic", "unknown")), israel=israel, israel_vote_2026=v26, israel_vote_2024=v24,
                 wing="Progressive" if left and israel != "supports" else "Mainstream",
                 wing_without_israel_rule="Progressive" if left else "Mainstream")
    else:
        u24, u25 = vote(UKR24, m), vote(UKR25, m)
        obj = [vote(o, m) for o in OBJ]
        r.update(ukraine_2024=u24, ukraine_ban_2025=u25, objected_2021=any(o in ("Yea", "Aye") for o in obj) if any(obj) else None,
                 immigration=s.get("immigration"), wing=m["wing"])
    rows.append(r)

(W / "wings.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
print(len(rows), "members")
print(Counter((r["party"], r["wing"]) for r in rows))
d = [r for r in rows if r["party"] == "D"]
print("D without the Israel rule:", Counter(r["wing_without_israel_rule"] for r in d))
print("D changed from agent call:", [(r["district"], r["agent_wing"], "->", r["wing"]) for r in d if r["agent_wing"] != r["wing"]])
print("D returning with no 2026 vote found:", [(r["district"], r["name"]) for r in d if r["returning"] and not r["israel_vote_2026"]])
rr = [r for r in rows if r["party"] == "R"]
print("R returning with no 2024/2025 vote found:", [(r["district"], r["name"]) for r in rr if r["returning"] and not (r["ukraine_2024"] or r["ukraine_ban_2025"])])

# Republicans: one rule where the votes decide it, the agents' reading of policies where they don't.
for r in rows:
    if r["party"] != "R":
        continue
    if r["returning"] and r["ukraine_ban_2025"] == "Aye":
        r["wing"], r["basis"] = "Nationalist", "voted for the 2025 Greene amendment barring Ukraine aid"
    elif r["returning"] and r["ukraine_2024"] == "Yea":
        r["wing"], r["basis"] = "Mainstream", "voted for the 2024 Ukraine aid and against the 2025 ban"
    else:
        r["wing"] = r["agent_wing"]
        r["basis"] = ("mixed record (opposed the 2024 aid, not the 2025 ban): placed on other policies" if r["returning"]
                      else "newcomer: placed on platform and endorsements")
for r in rows:
    if r["party"] == "D":
        r["basis"] = ("2026 vote on the Massie Israel-aid amendment" if r["israel_vote_2026"] else "newcomer or no 2026 vote: endorsements and statements")
(W / "wings.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
print("final:", Counter((r["party"], r["wing"]) for r in rows))
print("by new/returning:", Counter((r["party"], r["wing"], "returning" if r["returning"] else "new") for r in rows))
