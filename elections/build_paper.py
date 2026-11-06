#!/usr/bin/env python3
"""Render paper.md to midterms2026_forecast_paper.pdf with typeset math.

Markdown goes through `marked` (the copy bundled with the blog skill); $...$ and $$...$$ are kept out of the
Markdown pass and typeset by KaTeX in headless Chrome, which then prints the PDF.
Usage: python3 build_paper.py
"""
import html
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
MARKED = Path.home() / ".claude/skills/blog-tapaskroy/node_modules"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KATEX = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9"

src = (HERE / "paper.md").read_text()

# Pull math out before Markdown sees it (underscores and backslashes would be mangled), then put it back.
math = []


def stash(m, display):
    math.append((m.group(1).strip(), display))
    return f"@@MATH{len(math) - 1}@@"


src = re.sub(r"\$\$(.+?)\$\$", lambda m: stash(m, True), src, flags=re.S)
src = re.sub(r"(?<![\\$])\$([^$\n]+?)\$", lambda m: stash(m, False), src)

body = subprocess.run(["node", "-e", "const {marked}=require('marked');let s='';process.stdin.on('data',d=>s+=d)"
                       ".on('end',()=>process.stdout.write(marked.parse(s)))"],
                      input=src, capture_output=True, text=True, check=True,
                      env={**os.environ, "NODE_PATH": str(MARKED)}).stdout


def unstash(m):
    tex, display = math[int(m.group(1))]
    tag = "div" if display else "span"
    return f'<{tag} class="tex" data-display="{str(display).lower()}">{html.escape(tex)}</{tag}>'


body = re.sub(r"<p>\s*@@MATH(\d+)@@\s*</p>", unstash, body)  # display math on its own line
body = re.sub(r"@@MATH(\d+)@@", unstash, body)

page = f"""<!doctype html><html><head><meta charset="utf-8"><title>A Transparent Poll-Based Forecast of the 2026 U.S. Midterm Elections</title>
<link rel="stylesheet" href="{KATEX}/katex.min.css">
<script src="{KATEX}/katex.min.js"></script>
<style>
@page {{ size: letter; margin: 0.85in 0.9in; }}
body {{ font-family: "Charter", "Georgia", serif; font-size: 10.5pt; line-height: 1.45; color: #111; }}
h1 {{ font-size: 20pt; line-height: 1.2; margin: 0 0 6pt; }}
h1 + p em {{ font-size: 11pt; color: #333; }}
.byline {{ color: #444; font-size: 10pt; margin: 4pt 0 18pt; }}
h2 {{ font-size: 13pt; margin: 18pt 0 6pt; break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }}
p {{ margin: 0 0 7pt; text-align: justify; hyphens: auto; }}
ul, ol {{ margin: 0 0 8pt; padding-left: 20pt; }} li {{ margin-bottom: 3pt; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 6pt 0 10pt; break-inside: avoid; }}
th, td {{ border-top: 0.5pt solid #999; padding: 3pt 5pt; text-align: left; vertical-align: top; }}
thead th {{ border-top: 1pt solid #111; border-bottom: 0.75pt solid #111; }}
tbody tr:last-child td {{ border-bottom: 1pt solid #111; }}
div.tex {{ margin: 8pt 0 10pt; }}
figure {{ margin: 10pt 0; break-inside: avoid; }} figure img {{ width: 100%; }}
figcaption {{ font-size: 9pt; color: #333; margin-top: 4pt; }}
.katex {{ font-size: 1.05em; }}
</style></head><body>
{body}
<script>
document.querySelectorAll('.tex').forEach(el => katex.render(el.textContent, el,
  {{displayMode: el.dataset.display === 'true', throwOnError: true, output: 'html'}}));
document.title = 'typeset ' + document.querySelectorAll('.katex').length;
</script></body></html>"""
out_html = HERE / "paper.html"
out_html.write_text(page)
pdf = HERE / "midterms2026_forecast_paper.pdf"
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                f"--print-to-pdf={pdf}", out_html.as_uri()], check=True, capture_output=True)
print(f"{pdf.name}: {len(math)} formulas, {pdf.stat().st_size // 1024} KB")
