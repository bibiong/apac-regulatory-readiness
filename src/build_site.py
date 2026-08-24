#!/usr/bin/env python3
"""Generate the static tracker site from the YAML dataset.

    python3 src/build_site.py

One index with a deadline board and a filterable instrument table, plus one page per
jurisdiction. No build step, no dependencies beyond PyYAML — the dataset is the source of
truth and the site is a view of it, so the site can never disagree with the data.
"""
from __future__ import annotations

import html
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tracker" / "data"
OUT = ROOT / "site"

ACCENT, INK = "#B26136", "#17140F"

def flag(code: str) -> str:
    """Country marker as a text badge rather than a flag emoji.

    Regional-indicator flag emoji do not render at all on Windows and render
    inconsistently elsewhere, which would put an empty box beside every jurisdiction
    for a meaningful share of readers. A two-letter badge renders identically on
    every platform and reads as a dataset rather than as decoration.
    """
    return f'<span class="cc">{esc(code)}</span>' if code else ""

STATUS_LABEL = {
    "in_force": "In force", "partially_in_force": "Partially in force",
    "passed": "Passed, not commenced", "draft": "Draft",
    "consultation": "Consultation", "superseded": "Superseded",
}

THEME_LABEL = {
    "age_assurance": "Age assurance", "content_takedown": "Content takedown",
    "data_protection": "Data protection", "scam_fraud": "Scam & fraud",
    "transparency_reporting": "Transparency reporting", "licensing": "Licensing",
    "ai_synthetic_media": "AI & synthetic media", "localisation": "Localisation",
}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --accent:#B26136;--accent-deep:#8F4A26;--accent-soft:#F0E2D6;
  --ink:#17140F;--ink-2:#45403A;--ink-3:#756E65;
  --bg:#FBFAF8;--card:#FFFFFF;
  --line:rgba(23,20,15,.13);--line-soft:rgba(23,20,15,.07);
}
@media (prefers-color-scheme:dark){
  :root{--ink:#F2EFEA;--ink-2:#C4BEB5;--ink-3:#8E877D;--bg:#141210;--card:#1C1917;
        --line:rgba(242,239,234,.15);--line-soft:rgba(242,239,234,.08);--accent-soft:#3A2A1F}
}
body{background:var(--bg);color:var(--ink);
  font:400 16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:0 clamp(1rem,4vw,2.5rem)}
header.top{border-bottom:1px solid var(--line);padding:2.5rem 0 2rem;margin-bottom:2.5rem}
h1{font-size:clamp(1.6rem,3.4vw,2.4rem);line-height:1.15;letter-spacing:-.02em;font-weight:700}
h2{font-size:1.25rem;letter-spacing:-.01em;margin:2.5rem 0 1rem;font-weight:600}
h3{font-size:1.02rem;font-weight:600;margin:0 0 .35rem}
p{color:var(--ink-2);max-width:74ch}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.eyebrow{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);
  font-weight:600;margin-bottom:.7rem}
.lede{font-size:1.05rem;margin-top:.9rem}
.meta{color:var(--ink-3);font-size:.84rem;margin-top:1rem}
/* Cell borders rather than a gap-background: with 5 stats in an auto-fit grid the
   wrapped row leaves an empty cell, and a container-coloured background paints it as
   a grey block on narrow viewports. Per-cell borders leave the gap invisible. */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  background:var(--card);border:1px solid var(--line);margin:2rem 0;border-radius:6px;overflow:hidden}
.stat{background:var(--card);padding:1rem 1.1rem;
  border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.stat b{display:block;font-size:1.5rem;letter-spacing:-.02em;color:var(--accent)}
.stat span{font-size:.76rem;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;font-size:.9rem;margin:1rem 0}
th{text-align:left;font-size:.71rem;text-transform:uppercase;letter-spacing:.09em;
  color:var(--ink-3);padding:.6rem .7rem;border-bottom:1.5px solid var(--line);font-weight:600}
td{padding:.72rem .7rem;border-bottom:1px solid var(--line-soft);vertical-align:top;color:var(--ink-2)}
td.name{color:var(--ink);font-weight:500}
.tbl{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--card)}
.pill{display:inline-block;font-size:.7rem;padding:.16rem .5rem;border-radius:99px;
  border:1px solid var(--line);white-space:nowrap;color:var(--ink-2)}
.pill.live{background:var(--accent-soft);border-color:transparent;color:var(--accent-deep)}
.pill.soon{border-color:var(--accent);color:var(--accent)}
.conf{font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3)}
.conf.low{color:var(--accent-deep)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:1.3rem 1.4rem;margin-bottom:1rem}
.jgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:1rem;margin:1.5rem 0}
.jcard{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:1.1rem 1.2rem;
  display:block;color:inherit}
.jcard:hover{border-color:var(--accent);text-decoration:none}
.jcard .n{font-size:1.7rem;line-height:1}
.jcard .c{font-size:1rem;font-weight:600;color:var(--ink);margin:.5rem 0 .2rem}
.jcard .s{font-size:.8rem;color:var(--ink-3)}
.ob{border-left:2px solid var(--accent-soft);padding:.1rem 0 .1rem .9rem;margin:.7rem 0}
.ob .clk{color:var(--accent-deep);font-weight:600;font-size:.82rem}
.note{background:var(--accent-soft);border-radius:6px;padding:.9rem 1.1rem;margin:1rem 0;
  font-size:.9rem;color:var(--ink-2)}
@media (prefers-color-scheme:dark){.note{background:#241A13}}
.src{font-size:.82rem;color:var(--ink-3)}
footer{border-top:1px solid var(--line);margin-top:3.5rem;padding:1.8rem 0 3rem;
  font-size:.82rem;color:var(--ink-3);display:flex;flex-wrap:wrap;gap:1rem;justify-content:space-between}
.back{font-size:.85rem;display:inline-block;margin-bottom:1.2rem}
.cc{display:inline-block;font:600 .68rem/1.35 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  letter-spacing:.08em;padding:.12rem .36rem;border:1px solid var(--line);border-radius:4px;
  color:var(--ink-3);vertical-align:.06em}
.jcard .n .cc{font-size:.95rem;padding:.2rem .5rem;color:var(--accent-deep);
  border-color:var(--accent);letter-spacing:.1em}

"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def load() -> list[dict]:
    out = []
    for p in sorted(DATA.glob("*.yaml")):
        out.extend(yaml.safe_load(p.read_text()) or [])
    return out


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v in (None, ""):
        return None
    return datetime.strptime(str(v), "%Y-%m-%d").date()


def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="A maintained, cited dataset of platform-relevant regulation across ten APAC jurisdictions.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='18' fill='%2317140F'/><text y='72' x='50' text-anchor='middle' font-family='Helvetica,Arial' font-weight='600' font-size='58' fill='%23B26136'>A</text></svg>">
<style>{CSS}</style></head><body>
<div class="wrap">{body}
<footer>
  <div>APAC Regulatory Readiness · Brenda Ong · <a href="{up}../DISCLAIMER.md">Disclaimer</a></div>
  <div>Not legal advice. Verify against cited primary sources.</div>
</footer>
</div></body></html>"""


def build():
    entries = load()
    today = date.today()
    OUT.mkdir(exist_ok=True)

    by_j: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_j[e["jurisdiction"]].append(e)

    # ---- deadline board: every dated event still ahead of us
    upcoming = []
    for e in entries:
        for d in e.get("deadlines") or []:
            dt = as_date(d["date"])
            if dt and dt >= today:
                upcoming.append((dt, e, d))
    upcoming.sort(key=lambda x: x[0])

    in_force = sum(1 for e in entries if e["status"] in ("in_force", "partially_in_force"))
    clocks = sum(1 for e in entries for o in e["obligations"] if o.get("clock"))

    b = ['<header class="top">',
         '<div class="eyebrow">APAC Regulatory Readiness</div>',
         '<h1>Platform Regulation Tracker</h1>',
         '<p class="lede">A maintained, cited dataset of platform-relevant regulation across ten '
         'Asia-Pacific jurisdictions — instrument, regulator, status, obligations, clocks, '
         'penalty exposure and primary sources. Every entry carries the date it was last '
         'verified and a confidence rating earned by the strength of its sources.</p>',
         f'<p class="meta">Generated {today.isoformat()} from '
         f'<code>tracker/data/</code>. The dataset is the source of truth; this page is a view of it.</p>',
         '</header>']

    b.append('<div class="stats">')
    for val, lab in [(len(entries), "Instruments"), (len(by_j), "Jurisdictions"),
                     (in_force, "In force"), (clocks, "Statutory clocks"),
                     (len(upcoming), "Dated events ahead")]:
        b.append(f'<div class="stat"><b>{val}</b><span>{esc(lab)}</span></div>')
    b.append('</div>')

    b.append("<h2>Deadline board</h2>")
    b.append("<p>Every dated event still ahead, across all ten jurisdictions. This is the "
             "artefact the whole tracker exists to produce: one calendar, not ten news feeds.</p>")
    if upcoming:
        b.append('<div class="tbl"><table><thead><tr><th>Date</th><th>In</th>'
                 '<th>Event</th><th>Instrument</th><th>Certainty</th></tr></thead><tbody>')
        for dt, e, d in upcoming:
            days = (dt - today).days
            cert = d.get("certainty", "fixed")
            pill = "live" if cert == "fixed" else "soon"
            b.append(
                f'<tr><td class="name">{dt.strftime("%d %b %Y")}</td>'
                f'<td>{days}d</td><td>{esc(d["event"])}</td>'
                f'<td>{flag(e.get("jurisdiction_code",""))} '
                f'<a href="jurisdictions/{esc(e["jurisdiction"].lower().replace(" ","-"))}.html">'
                f'{esc(e["instrument"])}</a></td>'
                f'<td><span class="pill {pill}">{esc(cert)}</span></td></tr>')
        b.append("</tbody></table></div>")
    else:
        b.append("<p>No dated events ahead in the current dataset.</p>")

    b.append("<h2>Jurisdictions</h2>")
    b.append('<div class="jgrid">')
    for j in sorted(by_j):
        es = by_j[j]
        code = es[0].get("jurisdiction_code", "")
        live = sum(1 for e in es if e["status"] in ("in_force", "partially_in_force"))
        slug = j.lower().replace(" ", "-")
        b.append(f'<a class="jcard" href="jurisdictions/{slug}.html">'
                 f'<div class="n">{flag(code)}</div>'
                 f'<div class="c">{esc(j)}</div>'
                 f'<div class="s">{len(es)} instrument{"s" if len(es)!=1 else ""} · {live} in force</div></a>')
    b.append("</div>")

    b.append("<h2>All instruments</h2>")
    b.append('<div class="tbl"><table><thead><tr><th>Jurisdiction</th><th>Instrument</th>'
             '<th>Regulator</th><th>Status</th><th>Themes</th><th>Confidence</th>'
             '<th>Verified</th></tr></thead><tbody>')
    for e in sorted(entries, key=lambda x: (x["jurisdiction"], x["instrument"])):
        slug = e["jurisdiction"].lower().replace(" ", "-")
        themes = ", ".join(THEME_LABEL.get(t, t) for t in e["themes"])
        conf = e.get("confidence", "medium")
        lv = as_date(e["last_verified"])
        b.append(
            f'<tr><td>{flag(e.get("jurisdiction_code",""))} {esc(e["jurisdiction"])}</td>'
            f'<td class="name"><a href="jurisdictions/{slug}.html#{esc(e["id"])}">{esc(e["instrument"])}</a></td>'
            f'<td>{esc(e["regulator"])}</td>'
            f'<td><span class="pill">{esc(STATUS_LABEL.get(e["status"], e["status"]))}</span></td>'
            f'<td>{esc(themes)}</td>'
            f'<td><span class="conf {"low" if conf=="low" else ""}">{esc(conf)}</span></td>'
            f'<td>{lv.isoformat() if lv else "—"}</td></tr>')
    b.append("</tbody></table></div>")

    b.append('<div class="note"><b>How to read the confidence column.</b> '
             '<i>High</i> means the instrument text itself was read. <i>Medium</i> means a '
             'regulator publication. <i>Low</i> means secondary reporting only — treat those '
             'entries as a prompt to go and check, not as an answer. The validator refuses a '
             'confidence rating the cited sources do not support.</div>')

    (OUT / "index.html").write_text(page("APAC Platform Regulation Tracker", "\n".join(b)))

    # ---- per-jurisdiction pages
    jdir = OUT / "jurisdictions"
    jdir.mkdir(exist_ok=True)
    for j, es in by_j.items():
        code = es[0].get("jurisdiction_code", "")
        p = ['<a class="back" href="../index.html">← All jurisdictions</a>',
             '<header class="top">',
             '<div class="eyebrow">Jurisdiction</div>',
             f'<h1>{flag(code)} {esc(j)}</h1>',
             f'<p class="lede">{len(es)} tracked instrument{"s" if len(es)!=1 else ""}.</p>',
             '</header>']
        for e in sorted(es, key=lambda x: x["instrument"]):
            p.append(f'<div class="card" id="{esc(e["id"])}">')
            p.append(f'<h3>{esc(e["instrument"])}</h3>')
            if e.get("instrument_local"):
                p.append(f'<p class="src">{esc(e["instrument_local"])}</p>')
            bits = [f'<span class="pill">{esc(STATUS_LABEL.get(e["status"], e["status"]))}</span>',
                    f'<span class="pill">{esc(e["regulator_full"] or e["regulator"])}</span>']
            for t in e["themes"]:
                bits.append(f'<span class="pill">{esc(THEME_LABEL.get(t,t))}</span>')
            p.append('<p style="margin:.6rem 0">' + " ".join(bits) + "</p>")

            cm, ps = as_date(e.get("commenced")), as_date(e.get("passed"))
            line = []
            if ps:
                line.append(f"Passed {ps.strftime('%d %b %Y')}")
            if cm:
                line.append(f"Commenced {cm.strftime('%d %b %Y')}")
            if line:
                p.append(f'<p class="src">{esc(" · ".join(line))}</p>')

            p.append("<h4 style='margin:1rem 0 .3rem;font-size:.78rem;text-transform:uppercase;"
                     "letter-spacing:.09em;color:var(--ink-3)'>Obligations</h4>")
            for o in e["obligations"]:
                p.append('<div class="ob">')
                p.append(f'<div>{esc(" ".join(o["summary"].split()))}</div>')
                sub = [f'<b>{esc(o["ref"])}</b>', esc(", ".join(o["owner_function"]))]
                p.append(f'<div class="src">{" · ".join(sub)}</div>')
                if o.get("clock"):
                    p.append(f'<div class="clk">Clock: {esc(o["clock"])}</div>')
                if o.get("evidence_required"):
                    p.append(f'<div class="src">Evidence: {esc(" ".join(o["evidence_required"].split()))}</div>')
                p.append("</div>")

            pen = e.get("penalty") or {}
            if pen.get("max_financial") or pen.get("non_financial"):
                p.append("<h4 style='margin:1rem 0 .3rem;font-size:.78rem;text-transform:uppercase;"
                         "letter-spacing:.09em;color:var(--ink-3)'>Penalty exposure</h4>")
                if pen.get("max_financial"):
                    p.append(f'<p>{esc(pen["max_financial"])}</p>')
                if pen.get("basis"):
                    p.append(f'<p class="src">{esc(" ".join(str(pen["basis"]).split()))}</p>')
                if pen.get("personal_liability"):
                    p.append('<p class="src"><b>Personal liability in scope.</b></p>')
                if pen.get("non_financial"):
                    p.append(f'<p class="src">{esc(" ".join(str(pen["non_financial"]).split()))}</p>')

            sigs = e.get("enforcement_signals") or []
            if sigs:
                p.append("<h4 style='margin:1rem 0 .3rem;font-size:.78rem;text-transform:uppercase;"
                         "letter-spacing:.09em;color:var(--ink-3)'>Enforcement signals</h4>")
                for s in sigs:
                    sd = as_date(s["date"])
                    p.append(f'<p class="src">{sd.strftime("%d %b %Y") if sd else ""} — '
                             f'{esc(" ".join(s["signal"].split()))} '
                             f'[<a href="{esc(s["source"])}">source</a>]</p>')

            if e.get("meta_exposure"):
                p.append(f'<div class="note">{esc(" ".join(e["meta_exposure"].split()))}</div>')
            if e.get("notes"):
                p.append(f'<p style="margin-top:.8rem">{esc(" ".join(e["notes"].split()))}</p>')

            p.append("<h4 style='margin:1rem 0 .3rem;font-size:.78rem;text-transform:uppercase;"
                     "letter-spacing:.09em;color:var(--ink-3)'>Sources</h4>")
            for s in e["sources"]:
                p.append(f'<p class="src"><a href="{esc(s["url"])}">{esc(s["title"])}</a> '
                         f'<span class="pill">{esc(s["kind"])}</span></p>')
            lv = as_date(e["last_verified"])
            p.append(f'<p class="src" style="margin-top:.8rem">Confidence '
                     f'<b>{esc(e.get("confidence","medium"))}</b> · last verified '
                     f'{lv.isoformat() if lv else "—"} by {esc(e["verified_by"])}</p>')
            p.append("</div>")

        slug = j.lower().replace(" ", "-")
        (jdir / f"{slug}.html").write_text(page(f"{j} — APAC Regulation Tracker", "\n".join(p), depth=1))

    print(f"built site/index.html and {len(by_j)} jurisdiction pages -> {OUT}")


if __name__ == "__main__":
    build()
