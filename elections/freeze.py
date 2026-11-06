#!/usr/bin/env python3
"""Freeze the final forecast: copy the model outputs, poll files and published pages into frozen/ with a SHA-256
manifest. The scorecard scores only what is in frozen/, so nothing published after the freeze can change the grade.

Usage: python3 freeze.py
Refuses before the agreed freeze time (Nov 3, 2026, 9:00 a.m. PT) and refuses to overwrite an existing freeze.
"""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "frozen"
FREEZE_AT = datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc)  # 9:00 PST
FILES = ["senate_model.json", "house_model.json", "gov_model.json",
         "senate_polls.json", "house_polls.json", "gov_polls.json", "house_data.json", "update_history.json",
         "index.html", "senate.html", "house.html", "governors.html"]

now = datetime.now(timezone.utc)
if now < FREEZE_AT:
    sys.exit(f"Too early: the freeze is set for {FREEZE_AT.isoformat()} (9:00 a.m. PT); it is {now.isoformat(timespec='seconds')}.")
if OUT.exists():
    sys.exit("frozen/ already exists; the forecast is frozen once. Remove it by hand only if the freeze itself was wrong.")
OUT.mkdir()
manifest = {"frozen_at": now.isoformat(timespec="seconds"), "files": {}}
for f in FILES:
    shutil.copy2(HERE / f, OUT / f)
    manifest["files"][f] = hashlib.sha256((OUT / f).read_bytes()).hexdigest()
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
print(f"Frozen {len(FILES)} files at {manifest['frozen_at']} into {OUT.name}/")
