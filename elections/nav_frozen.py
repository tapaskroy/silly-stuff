#!/usr/bin/env python3
"""Write the four forecast pages for publishing: the frozen copies with the current nav links added, and nothing else changed.

The pages in frozen/ stay byte-for-byte as published on Nov 3 (frozen/manifest.json has their hashes). The only edit is the nav bar:
links to results pages added after the freeze (site_chrome.SHEETS after Scorecard) are inserted after the Scorecard link. The script
checks that taking the inserted links back out gives the frozen file exactly.
Usage: python3 nav_frozen.py   (publish_site.sh runs it)
"""
from pathlib import Path

import site_chrome as site

HERE = Path(__file__).parent
END = '<a href="scorecard.html" style="color:inherit">Scorecard</a></nav>'
LATER = site.SHEETS[[h for h, _ in site.SHEETS].index("scorecard.html") + 1:]
ADD = "".join(f' · <a href="{h}" style="color:inherit">{label}</a>' for h, label in LATER)

for page in ("index.html", "senate.html", "house.html", "governors.html"):
    frozen = (HERE / "frozen" / page).read_text()
    assert frozen.count(END) == 1, f"{page}: expected one nav ending in Scorecard"
    live = frozen.replace(END, END[:-len("</nav>")] + ADD + "</nav>")
    assert live.replace(ADD, "", 1) == frozen, f"{page}: more than the nav changed"
    (HERE / page).write_text(live)
    print(f"{page}: frozen copy + nav links {[label for _, label in LATER]}")
