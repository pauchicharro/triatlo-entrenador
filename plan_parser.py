"""Parsing compartit de data/training_plan.md.

Fet servir tant per daily_checkin.py (comparacio dia a dia) com per
generate_site.py (pagina web amb totes les setmanes). Nomes llegeix taules
sota capcaleres "## Setmana N" -- la resta del fitxer (macrocicle, notes)
s'ignora per aquest parsing estructurat.
"""

import re
from datetime import date

PLAN_YEAR = 2026

WEEK_HEADER_RE = re.compile(r"^##\s*(Setmana\s+\d+.*)$", re.IGNORECASE)
TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")
DAY_MONTH_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

DISCIPLINE_KEYWORDS = {
    "natacio": ["natació", "natacio", "swim"],
    "bici": ["bici", "cicl"],
    "correr": ["córrer", "correr", "cursa", "run"],
    "gimnas": ["gimnàs", "gimnas", "força", "forca"],
}
ACTIVITY_TYPE_TO_DISCIPLINE = {
    "lap_swimming": "natacio",
    "open_water_swimming": "natacio",
    "cycling": "bici",
    "running": "correr",
    "strength_training": "gimnas",
    "multi_sport": None,  # compta com a totes, gestionat especialment
}


def _clean(text):
    return BOLD_RE.sub(r"\1", text)


def parse_all_weeks(training_plan_path):
    """Retorna [{title, rows: [{date, day_label, session}]}] en ordre del fitxer."""
    if not training_plan_path.exists():
        return []

    weeks = []
    current = None

    for line in training_plan_path.read_text().splitlines():
        stripped = line.strip()

        wh = WEEK_HEADER_RE.match(stripped)
        if wh:
            current = {"title": wh.group(1).strip(), "rows": []}
            weeks.append(current)
            continue
        if stripped.startswith("## ") and not wh:
            current = None
            continue
        if current is None:
            continue

        m = TABLE_ROW_RE.match(stripped)
        if not m:
            continue
        day_cell, session_cell = m.group(1), m.group(2)
        if day_cell.lower().startswith("dia") or set(day_cell) <= {"-", " "}:
            continue
        dm = DAY_MONTH_RE.search(day_cell)
        if not dm:
            continue
        day_num, month_num = int(dm.group(1)), int(dm.group(2))
        try:
            row_date = date(PLAN_YEAR, month_num, day_num)
        except ValueError:
            continue
        current["rows"].append({
            "date": row_date,
            "day_label": day_cell,
            "session": _clean(session_cell),
        })

    return weeks


def find_plan_row_for_date(training_plan_path, target_date):
    matches = [
        row["session"]
        for week in parse_all_weeks(training_plan_path)
        for row in week["rows"]
        if row["date"] == target_date
    ]
    return matches[-1] if matches else None


def disciplines_in_text(text):
    text_low = text.lower()
    found = set()
    for disc, keywords in DISCIPLINE_KEYWORDS.items():
        if any(k in text_low for k in keywords):
            found.add(disc)
    return found


def actual_disciplines(activities):
    found = set()
    for a in activities:
        disc = ACTIVITY_TYPE_TO_DISCIPLINE.get(a.get("activityType"))
        if disc:
            found.add(disc)
        elif a.get("activityType") == "multi_sport":
            found |= {"natacio", "bici", "correr"}
    return found
