#!/usr/bin/env python3
"""Flag polls the models silently skip. Run after the three models.

A poll is skipped when its `results` keys don't match the model's candidate names (results are keyed by surname),
or when it falls outside the poll window. This lists every in-window poll that did not reach a model average.
Usage: python3 check_polls.py [--since YYYY-MM-DD]   (only report polls ending on/after that date)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
since = sys.argv[sys.argv.index("--since") + 1] if "--since" in sys.argv else ""
SETS = [("Senate", "senate_polls.json", "senate_model.json", "state", "model_params.json"),
        ("House", "house_polls.json", "house_model.json", "district", "model_params_house.json"),
        ("Governor", "gov_polls.json", "gov_model.json", "state", "model_params_gov.json")]
bad = 0
for label, pf, mf, key, params in SETS:
    polls = json.loads((HERE / pf).read_text())
    model = {r[key]: r for r in json.loads((HERE / mf).read_text())["races"]}
    window = json.loads((HERE / params).read_text())["poll_window_start"]
    for race, rec in polls.items():
        if (model.get(race) or {}).get("fixed"):
            continue  # decided by the ballot (one party, or a same-party top-two): polls are not needed
        used = {(p["pollster"], p["end"]) for p in (model.get(race) or {}).get("polls", [])}
        for p in rec.get("polls") or []:
            end = p.get("end") or ""
            if end < max(window, since) or (p["pollster"], end) in used:
                continue
            bad += 1
            m = model.get(race) or {}
            names = (m.get("challenger"), m.get("rep")) if key == "state" else (m.get("dem"), m.get("rep"))
            print(f"{label} {race}: {p['pollster']} ending {end} not used. results keys {list(p['results'])}; "
                  f"model expects {names}" + ("" if race in model else " (race not in model)"))
print(f"{bad} in-window poll(s) not used" + (f" since {since}" if since else ""))
