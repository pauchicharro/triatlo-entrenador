"""Genera docs/index.html: pagina de consulta mobil del pla d'entrenament.

Es regenera localment (on Garmin funciona) i es publica via GitHub Pages
quan es fa push. La marca de fet/no fet es calcula automaticament comparant
cada sessio amb les activitats de Garmin ja sincronitzades -- no hi ha cap
casella per marcar a ma ni cap backend.
"""

import csv
import html
from datetime import date
from pathlib import Path

import plan_parser

ROOT = Path(__file__).parent
TRAINING_PLAN = ROOT / "data" / "training_plan.md"
ACTIVITIES_CSV = ROOT / "data" / "garmin" / "activities.csv"
OUT_DIR = ROOT / "docs"
OUT_FILE = OUT_DIR / "index.html"

RACE_DATE = date(2026, 10, 24)

DISCIPLINE_LABELS = {
    "natacio": "Natació",
    "bici": "Bici",
    "correr": "Córrer",
    "gimnas": "Gimnàs",
}


def load_activities():
    if not ACTIVITIES_CSV.exists():
        return []
    with open(ACTIVITIES_CSV, newline="") as f:
        return list(csv.DictReader(f))


def activities_on(all_activities, day_str):
    return [a for a in all_activities if (a.get("startTimeLocal") or "").startswith(day_str)]


def row_status(row, all_activities, today):
    session = row["session"]
    session_low = session.lower()

    if "descans" in session_low:
        return "rest", "Descans"
    if row["date"] > today:
        return "upcoming", "Pendent"
    if row["date"] == today:
        return "today", "Avui"

    planned = plan_parser.disciplines_in_text(session)
    if not planned:
        return "unknown", "—"

    actual = plan_parser.actual_disciplines(activities_on(all_activities, row["date"].isoformat()))
    missing = planned - actual
    if not missing:
        return "done", "Fet"
    if missing == planned:
        return "missed", "No detectat"
    done_str = ", ".join(DISCIPLINE_LABELS[d] for d in sorted(planned - missing))
    missing_str = ", ".join(DISCIPLINE_LABELS[d] for d in sorted(missing))
    return "partial", f"Fet: {done_str} · Falta: {missing_str}"


def discipline_class(session_text):
    discs = plan_parser.disciplines_in_text(session_text)
    if "natacio" in discs and len(discs) == 1:
        return "swim"
    if "bici" in discs and len(discs) == 1:
        return "bike"
    if "correr" in discs and len(discs) == 1:
        return "run"
    if discs:
        return "mixed"
    return "neutral"


def render():
    weeks = plan_parser.parse_all_weeks(TRAINING_PLAN)
    all_activities = load_activities()
    today = date.today()
    days_to_race = (RACE_DATE - today).days

    week_blocks = []
    current_week_idx = None
    for i, week in enumerate(weeks):
        week_dates = [r["date"] for r in week["rows"]]
        if week_dates and week_dates[0] <= today <= week_dates[-1]:
            current_week_idx = i

    for i, week in enumerate(weeks):
        rows_html = []
        for row in week["rows"]:
            status_class, status_label = row_status(row, all_activities, today)
            disc_class = discipline_class(row["session"])
            rows_html.append(f"""
            <li class="day-card {disc_class}">
              <div class="day-head">
                <span class="day-label">{html.escape(row['day_label'])}</span>
                <span class="status status-{status_class}">{html.escape(status_label)}</span>
              </div>
              <p class="session-text">{html.escape(row['session'])}</p>
            </li>""")

        is_current = (i == current_week_idx)
        open_attr = " open" if is_current or current_week_idx is None else ""
        current_badge = ' <span class="current-badge">setmana actual</span>' if is_current else ""
        week_blocks.append(f"""
        <details class="week" {open_attr}>
          <summary>{html.escape(week['title'])}{current_badge}</summary>
          <ul class="day-list">{''.join(rows_html)}</ul>
        </details>""")

    generated_at = date.today().isoformat()

    html_doc = f"""<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Entrenador triatló — Pau</title>
<style>
  :root {{
    --bg: #F3F5F4; --surface: #FFFFFF; --surface-2: #EAEEEC;
    --text: #12201D; --text-2: #4B5B57; --muted: #7C8A86;
    --border: rgba(18,32,29,0.12);
    --swim: #0F6E56; --swim-bg: #E1F5EE;
    --bike: #9C6110; --bike-bg: #FAEEDA;
    --run: #B0431C; --run-bg: #FAECE7;
    --neutral-bg: #F1EFE8;
    --done: #0F6E56; --done-bg: #E1F5EE;
    --missed: #B0431C; --missed-bg: #FAECE7;
    --upcoming: #7C8A86; --upcoming-bg: #EAEEEC;
    --rest: #185FA5; --rest-bg: #E6F1FB;
    --partial: #9C6110; --partial-bg: #FAEEDA;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #10161A; --surface: #182022; --surface-2: #1E2729;
      --text: #ECF3F0; --text-2: #9FB0AC; --muted: #71807C;
      --border: rgba(236,243,240,0.13);
      --swim: #4ED1A2; --swim-bg: rgba(78,209,162,0.15);
      --bike: #E4A23C; --bike-bg: rgba(228,162,60,0.15);
      --run: #F0805A; --run-bg: rgba(240,128,90,0.15);
      --neutral-bg: rgba(156,154,146,0.12);
      --done: #4ED1A2; --done-bg: rgba(78,209,162,0.15);
      --missed: #F0805A; --missed-bg: rgba(240,128,90,0.15);
      --upcoming: #9C9A92; --upcoming-bg: rgba(156,154,146,0.15);
      --rest: #74ABDF; --rest-bg: rgba(116,171,223,0.15);
      --partial: #E4A23C; --partial-bg: rgba(228,162,60,0.15);
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 640px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
  header {{ margin-bottom: 1.5rem; }}
  .eyebrow {{ font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin: 0 0 4px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subline {{ font-size: 14px; color: var(--text-2); margin: 0; }}
  .countdown {{ font-family: ui-monospace, "SF Mono", monospace; font-size: 15px; color: var(--text-2); margin-top: 8px; }}
  details.week {{
    background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px;
    margin-bottom: 12px; overflow: hidden;
  }}
  summary {{
    padding: 14px 16px; font-weight: 600; font-size: 15px; cursor: pointer;
    list-style: none; display: flex; align-items: center; gap: 8px;
  }}
  summary::-webkit-details-marker {{ display: none; }}
  summary::before {{ content: "▸"; color: var(--muted); font-size: 12px; transition: transform 0.15s; }}
  details[open] summary::before {{ transform: rotate(90deg); }}
  .current-badge {{
    font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.02em;
    background: var(--rest-bg); color: var(--rest); padding: 2px 8px; border-radius: 6px;
  }}
  .day-list {{ list-style: none; margin: 0; padding: 0 12px 12px; }}
  .day-card {{
    border-radius: 10px; padding: 10px 12px; margin-top: 8px; background: var(--neutral-bg);
  }}
  .day-card.swim {{ background: var(--swim-bg); }}
  .day-card.bike {{ background: var(--bike-bg); }}
  .day-card.run {{ background: var(--run-bg); }}
  .day-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
  .day-label {{ font-size: 13px; font-weight: 600; color: var(--text-2); }}
  .status {{
    font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; white-space: nowrap;
  }}
  .status-done {{ background: var(--done-bg); color: var(--done); }}
  .status-missed {{ background: var(--missed-bg); color: var(--missed); }}
  .status-partial {{ background: var(--partial-bg); color: var(--partial); }}
  .status-upcoming {{ background: var(--upcoming-bg); color: var(--upcoming); }}
  .status-rest {{ background: var(--rest-bg); color: var(--rest); }}
  .status-unknown {{ background: var(--upcoming-bg); color: var(--upcoming); }}
  .status-today {{ background: var(--rest-bg); color: var(--rest); }}
  .session-text {{ font-size: 14px; line-height: 1.5; margin: 6px 0 0; color: var(--text); }}
  footer {{ margin-top: 2rem; font-size: 12px; color: var(--muted); text-align: center; }}
  footer a {{ color: var(--text-2); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">Entrenador de triatló · Pau Chicharro</p>
    <h1>Challenge Barcelona Triatló — Olímpica</h1>
    <p class="subline">24-25 d'octubre de 2026</p>
    <p class="countdown">{days_to_race} dies fins a la cursa</p>
  </header>
  {''.join(reversed(week_blocks))}
  <footer>
    Generat el {generated_at} · <a href="https://github.com/pauchicharro/triatlo-entrenador">codi font</a>
  </footer>
</div>
</body>
</html>
"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html_doc, encoding="utf-8")
    print(f"Pagina generada a {OUT_FILE}")


if __name__ == "__main__":
    render()
