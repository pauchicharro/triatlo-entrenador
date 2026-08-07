"""Check-in diari: sincronitza Garmin, compara previst vs fet, i notifica.

Funciona en dos entorns amb el mateix codi:
  - Local (launchd, Mac): notifica amb una notificacio del sistema (osascript).
  - GitHub Actions (cloud): notifica publicant un comentari a l'issue
    "Check-in diari" del repositori (GitHub ja avisa l'usuari amb les seves
    notificacions habituals). Detectat automaticament via la variable
    d'entorn GITHUB_ACTIONS, o forcat amb --mode local|github.

Logica (determinista, sense IA):
  1. Sincronitza Garmin (ultims 2 dies).
  2. Localitza, dins de data/training_plan.md, la fila de la setmana que
     correspon a AVUI i a AHIR (parsejant nomes seccions "## Setmana N",
     no tot el fitxer a cegues, per evitar falsos positius entre setmanes).
  3. Compara les disciplines previstes ahir amb els tipus d'activitat
     realment sincronitzats ahir (natacio/bici/correr/gimnas).
  4. Revisa senyals d'alarma al training status de Garmin (carrega
     desequilibrada, estat "unproductive"/"overreaching", etc.).
  5. Escriu un resum a data/garmin/daily_checkin.log (local) i notifica.

Si alguna cosa falla (sync, parsing), ho diu explicitament en comptes de
notificar dades inventades o silenciar l'error.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
_venv_python = ROOT / ".venv" / "bin" / "python"
VENV_PYTHON = _venv_python if _venv_python.exists() else Path(sys.executable)
ACTIVITIES_CSV = ROOT / "data" / "garmin" / "activities.csv"
WELLNESS_DIR = ROOT / "data" / "garmin" / "wellness"
TRAINING_PLAN = ROOT / "data" / "training_plan.md"
CHECKIN_LOG = ROOT / "data" / "garmin" / "daily_checkin.log"

WEEK_HEADER_RE = re.compile(r"^##\s*Setmana\s+\d+.*$", re.IGNORECASE)
TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")
DAY_MONTH_RE = re.compile(r"(\d{1,2})/(\d{1,2})")

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
    "multi_sport": None,  # counts as everything, handled specially
}


ISSUE_TITLE = "Check-in diari"


def notify_local(title, message):
    message = message.replace('"', "'").replace("\\", "")
    title = title.replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        log(f"AVIS: la notificació del sistema ha fallat: {e.stderr}")


def notify_github(title, body):
    try:
        find = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--search", f'"{ISSUE_TITLE}" in:title',
             "--json", "number,title", "--jq", ".[0].number"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        issue_number = find.stdout.strip()
        if not issue_number:
            create = subprocess.run(
                ["gh", "issue", "create", "--title", ISSUE_TITLE,
                 "--body", "Aquest issue rep un comentari cada dia amb el resum de l'entrenador."],
                cwd=ROOT, capture_output=True, text=True, check=True,
            )
            issue_number = create.stdout.strip().rstrip("/").rsplit("/", 1)[-1]

        subprocess.run(
            ["gh", "issue", "comment", issue_number, "--body", f"**{title}**\n\n{body}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        log(f"AVIS: no s'ha pogut notificar via GitHub issue: {e.stderr}")


def notify(title, message, mode):
    if mode == "github":
        notify_github(title, message)
    else:
        notify_local(title, message)


def log(text):
    print(text)
    CHECKIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKIN_LOG, "a") as f:
        f.write(text + "\n")


def sync_garmin():
    result = subprocess.run(
        [str(VENV_PYTHON), str(ROOT / "garmin_sync.py"), "--days", "2"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return result.returncode == 0, (result.stdout + result.stderr)


def find_plan_row_for_date(target_date):
    """Retorna el text de la sessio prevista per target_date, nomes cercant
    dins de taules sota capcaleres '## Setmana N', o None si no es troba."""
    if not TRAINING_PLAN.exists():
        return None

    lines = TRAINING_PLAN.read_text().splitlines()
    in_week_section = False
    matches = []

    for line in lines:
        if WEEK_HEADER_RE.match(line.strip()):
            in_week_section = True
            continue
        if line.strip().startswith("## ") and not WEEK_HEADER_RE.match(line.strip()):
            in_week_section = False
            continue
        if not in_week_section:
            continue

        m = TABLE_ROW_RE.match(line.strip())
        if not m:
            continue
        day_cell, session_cell = m.group(1), m.group(2)
        if day_cell.lower().startswith("dia") or set(day_cell) <= {"-", " "}:
            continue
        dm = DAY_MONTH_RE.search(day_cell)
        if not dm:
            continue
        day_num, month_num = int(dm.group(1)), int(dm.group(2))
        if day_num == target_date.day and month_num == target_date.month:
            matches.append(session_cell)

    return re.sub(r"\*\*(.+?)\*\*", r"\1", matches[-1]) if matches else None


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


def activities_on(day_str):
    if not ACTIVITIES_CSV.exists():
        return []
    with open(ACTIVITIES_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if (r.get("startTimeLocal") or "").startswith(day_str)]


def describe_activities(activities):
    if not activities:
        return "cap activitat registrada"
    return "; ".join(
        f"{a['activityType']} {float(a['distance'] or 0) / 1000:.1f}km "
        f"{float(a['duration'] or 0) / 60:.0f}min "
        f"(FC {a.get('averageHR') or '?'})"
        for a in activities
    )


def training_flags(today_str):
    path = WELLNESS_DIR / f"{today_str}.json"
    if not path.exists():
        return []
    try:
        data = json.load(open(path))
    except (json.JSONDecodeError, OSError):
        return []

    flags = []
    ts = (data.get("training_status") or {}).get("mostRecentTrainingLoadBalance") or {}
    for dto in (ts.get("metricsTrainingLoadBalanceDTOMap") or {}).values():
        phrase = dto.get("trainingBalanceFeedbackPhrase")
        if phrase and phrase != "BALANCED":
            flags.append(f"càrrega d'entrenament: {phrase}")

    status = (data.get("training_status") or {}).get("mostRecentTrainingStatus") or {}
    for dto in (status.get("latestTrainingStatusData") or {}).values():
        code = dto.get("trainingStatus")
        # Codis Garmin coneguts com a senyal d'alerta: 1=Detraining, 6=Overreaching, 7=Unproductive
        if code in (1, 6, 7):
            flags.append(f"training status de Garmin en codi {code} (revisar)")

    sleep = (data.get("sleep") or {}).get("dailySleepDTO") or {}
    sleep_seconds = sleep.get("sleepTimeSeconds")
    if sleep_seconds is not None and sleep_seconds < 5 * 3600:
        flags.append(f"son curt ahir a la nit ({sleep_seconds / 3600:.1f}h)")

    return flags


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["local", "github"], default=None)
    args = parser.parse_args()
    mode = args.mode or ("github" if os.environ.get("GITHUB_ACTIONS") == "true" else "local")

    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        ok, sync_output = sync_garmin()
    except Exception:
        ok, sync_output = False, traceback.format_exc()

    log(f"\n=== Check-in {today.isoformat()} (mode={mode}) ===")

    if not ok:
        log("SYNC FALLIT amb Garmin. Detall:")
        log(sync_output.strip()[-800:])
        notify("Entrenador triatló", "No he pogut sincronitzar Garmin avui — revisa credencials / connexió", mode)
        sys.exit(1)

    yest_activities = activities_on(yesterday.isoformat())
    yest_actual_desc = describe_activities(yest_activities)
    log(f"Ahir ({yesterday.isoformat()}) — fet: {yest_actual_desc}")

    yest_plan = find_plan_row_for_date(yesterday)
    mismatch_note = ""
    if yest_plan:
        log(f"Ahir — previst: {yest_plan}")
        planned_discs = disciplines_in_text(yest_plan)
        actual_discs = actual_disciplines(yest_activities)
        missing = planned_discs - actual_discs
        if missing and "descans" not in yest_plan.lower():
            mismatch_note = f"No es detecta: {', '.join(sorted(missing))} (previst ahir)"
            log(f"AVIS: {mismatch_note}")
    else:
        log("Ahir — no hi ha cap fila de pla trobada per aquesta data.")

    today_plan = find_plan_row_for_date(today)
    if today_plan:
        log(f"Avui — previst: {today_plan}")
    else:
        log("Avui — no hi ha cap sessió concreta escrita al pla per aquesta data.")

    flags = training_flags(today.isoformat())
    if flags:
        log("Avisos de Garmin: " + "; ".join(flags))

    body_parts = [f"Ahir: {yest_actual_desc}."]
    if mismatch_note:
        body_parts.append(mismatch_note + ".")
    body_parts.append(f"Avui: {today_plan or 'sense sessió definida'}.")
    if flags:
        body_parts.append("Avisos: " + "; ".join(flags))

    notify_text = " ".join(body_parts) if mode == "github" else " ".join(body_parts)[:280]
    notify("Entrenador triatló", notify_text, mode)
    log("--- notificació enviada ---")


if __name__ == "__main__":
    main()
