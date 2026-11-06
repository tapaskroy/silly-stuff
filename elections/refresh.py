#!/usr/bin/env python3
"""Re-run all three forecasts after new polls are added, record the update, rebuild the pages, and report what moved.

Usage: python3 refresh.py --why "New polls released Oct 22-27." [--as-of YYYY-MM-DD]
  --as-of defaults to today and must not be after the election.
  --why is the reason shown in each page's update history; the list of what changed is generated.
Changes are measured against the latest snapshot in .snap/ dated before as-of; a same-day rerun compares against
the same baseline and replaces that day's history entry.
Does not publish: run ./publish_site.sh after reviewing the report.
"""
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


as_of = arg("--as-of", date.today().isoformat())
why = arg("--why")
if not why:
    sys.exit('Give the reason for this update, e.g. --why "New polls released Oct 22-27."')
PARAMS = ["model_params.json", "model_params_house.json", "model_params_gov.json"]
MODELS = ["senate_model.json", "house_model.json", "gov_model.json"]
POLLS = {"senate_model.json": "senate_polls.json", "house_model.json": "house_polls.json", "gov_model.json": "gov_polls.json"}
PAGE = {"senate_model.json": "senate.html", "house_model.json": "house.html", "gov_model.json": "governors.html"}
# .snap/<as-of>/ holds the models and poll files as published for that date. The baseline is the latest earlier
# snapshot, so a same-day rerun still reports against the last published update.
SNAP = HERE / ".snap"
earlier = sorted(d for d in SNAP.iterdir() if d.is_dir() and d.name < as_of) if SNAP.exists() else []
if not earlier:
    sys.exit(f"No snapshot before {as_of} in .snap/ to compare against.")
prev_dir = earlier[-1]
old_as_of = prev_dir.name
for f in PARAMS:
    p = json.loads((HERE / f).read_text())
    assert as_of <= p.get("election", "2026-11-03"), "as-of date is after the election"
    p["as_of"] = as_of
    (HERE / f).write_text(json.dumps(p, indent=1, ensure_ascii=False))


def run(script):
    out = subprocess.run([sys.executable, script], cwd=HERE, capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"{script} failed:\n{out.stderr}")
    print(f"{script}: {out.stdout.strip().splitlines()[0] if out.stdout.strip() else 'ok'}")


for script in ["senate_model.py", "house_model.py", "governor_model.py"]:
    run(script)


def load(d, name):
    return json.loads((d / name).read_text())


def pct(p):
    return ">99%" if p >= 0.995 else "<1%" if p <= 0.005 else f"{p:.0%}"


def change(a, b):
    return f"unchanged at {a}" if a == b else f"{a} → {b}"


def day(iso):
    return date.fromisoformat(iso).strftime("%b %-d") if iso else "?"


def senate_median(dist):
    """Smallest seat count that half the simulations reach or fall below (as on the Senate page)."""
    cum = 0.0
    for k in sorted(dist, key=int):
        cum += dist[k]
        if cum >= 0.5:
            return int(k)


def headline(name, m):
    """(control chance, median seats as shown on the pages, short labels)."""
    if name == "senate_model.json":
        return m["control"]["separate"]["D"], senate_median(m["seat_dist_d_plus_i"]), \
            "Senate: Democratic control", "median D + independent seats"
    if name == "house_model.json":
        return m["p_dem_control"], m["pct"]["50"], "House: Democratic control", "median Democratic seats"
    return m["p_d_majority"], m["pct"]["50"], "Governors: Democrats 26+", "median Democratic governors"


def new_polls(name):
    """Polls added to the chamber's poll file since the baseline, by race."""
    old, new = load(prev_dir, POLLS[name]), load(HERE, POLLS[name])
    seen = {(k, p.get("pollster"), p.get("end")) for k, v in old.items() for p in (v.get("polls") or [])}
    added = {}
    for k, v in new.items():
        for p in v.get("polls") or []:
            if (k, p.get("pollster"), p.get("end")) not in seen:
                added.setdefault(k, []).append(p)
    return added


entry = {"date": as_of, "why": why, "pages": {"index.html": []}}
print(f"\nChanges since the last run (as of {old_as_of} -> {as_of}):")
for name in MODELS:
    old, new = load(prev_dir, name), load(HERE, name)
    (op, oe, label, elab), (np_, ne, _, _) = headline(name, old), headline(name, new)
    added = new_polls(name)
    n_added = sum(len(v) for v in added.values())
    head = f"{label} {change(pct(op), pct(np_))}; {elab} {change(oe, ne)}."
    print(f"  {head}  ({n_added} new polls)")
    lines = [head]
    entry["pages"]["index.html"].append(f"{head} {n_added} new poll{'s' if n_added != 1 else ''}.")
    key = "district" if name == "house_model.json" else "state"
    pk = "p_dem" if name == "house_model.json" else "p_challenger"
    cand = (lambda r: r["dn"]) if name == "house_model.json" else (lambda r: r["challenger"])
    before = {r[key]: r for r in old["races"]}
    for r in new["races"]:
        o = before.get(r[key])
        if not o or r.get("fixed"):  # skip House seats decided before November (e.g. D-vs-D top-two)
            continue
        flipped = (o[pk] > 0.5) != (r[pk] > 0.5)
        if flipped or abs(r[pk] - o[pk]) >= 0.05 or r[key] in added:
            tag = " LEADER CHANGED" if flipped else ""
            print(f"    {r[key]}: {o[pk]:.0%} -> {r[pk]:.0%} (polls {o.get('n_polls', 0)} -> {r.get('n_polls', 0)}){tag}")
            src = "; ".join(f"{p['pollster']} (ended {day(p.get('end'))})" for p in added.get(r[key], []))
            lines.append(f"{r[key]}: {cand(r)} {change(pct(o[pk]), pct(r[pk]))}"
                         + (" (leader changed)" if flipped else "")
                         + (f". New: {src}." if src else ". No new polls; moved with the rest of the model."))
    entry["pages"][PAGE[name]] = lines

hist_file = HERE / "update_history.json"
hist = [e for e in (json.loads(hist_file.read_text()) if hist_file.exists() else []) if e["date"] != as_of]
hist_file.write_text(json.dumps(hist + [entry], indent=1, ensure_ascii=False))
print(f"\nupdate_history.json: entry for {as_of} written.")

for script in ["build_senate.py", "build_house.py", "build_governor.py", "build_index.py"]:
    run(script)
snap = SNAP / as_of
snap.mkdir(exist_ok=True)
for m in MODELS + list(POLLS.values()):
    shutil.copy(HERE / m, snap / m)
print(flush=True)
subprocess.run([sys.executable, "check_polls.py"], cwd=HERE)
