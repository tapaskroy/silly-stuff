"""Shared page chrome for the three sheets as published at tapaskroy.me/elections/midterms2026/ (unlisted)."""

# Unlisted pages: keep them out of search results. Nothing on the site links here.
ROBOTS = '<meta name="robots" content="noindex, nofollow">'
SHEETS = [("index.html", "Overview"), ("senate.html", "Senate"), ("house.html", "House"), ("governors.html", "Governors"), ("scorecard.html", "Scorecard")]


def nav(current):
    """Relative links between the sheets; works locally and on the site."""
    links = " · ".join(f'<b>{label}</b>' if href == current else f'<a href="{href}" style="color:inherit">{label}</a>'
                       for href, label in SHEETS)
    return f'<nav style="font-size:13px;color:var(--muted);margin:0 0 12px">2026 midterms: {links}</nav>'


def history(current):
    """The page's update history from update_history.json, newest first. refresh.py adds an entry on every rerun."""
    import html
    import json
    from datetime import date
    from pathlib import Path
    f = Path(__file__).parent / "update_history.json"
    entries = [e for e in (json.loads(f.read_text()) if f.exists() else []) if current in e["pages"]]
    if not entries:
        return ""
    items = "".join(
        f'<li style="margin:0 0 10px"><b>{date.fromisoformat(e["date"]).strftime("%b %-d, %Y")}</b> · {html.escape(e["why"])}'
        + ("<ul style=\"margin:4px 0 0;padding-left:18px\">"
           + "".join(f"<li>{html.escape(x)}</li>" for x in e["pages"][current]) + "</ul>" if e["pages"][current] else "")
        + "</li>"
        for e in sorted(entries, key=lambda e: e["date"], reverse=True))
    return (f'<details class="history" open style="margin:24px 0 0;font-size:13px">'
            f'<summary style="cursor:pointer;font-weight:600">Update history ({len(entries)})</summary>'
            f'<ol style="list-style:none;padding:0;margin:10px 0 0">{items}</ol></details>')
