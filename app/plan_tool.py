"""Carga, valida y publica planes de entrenamiento.

El plan es un JSON con un formato fijo (el "contrato"). Hoy lo escribe
Claude Code en data/plans/; mañana lo devolverá la API de Claude con el mismo
formato (structured output), y nada más de la app tendrá que cambiar.

Formato:
{
  "goal":   {"name": "San Silvestre", "race_date": "2026-12-31", "distance_m": 10000,
             "target_time_s": 2400},
  "fitness": {"vdot": 47.0, "source": "estimación inicial…"},     # opcional
  "summary": "Texto corto con la idea del plan",
  "phases": [{"name": "Base", "from": "2026-11-03", "to": "2026-11-29", "focus": "…"}],
  "templates": {"gymA": {"title": "…", "duration_min": 40, "blocks": [...]}},   # opcional
  "revisions": [{"date": "2026-11-08", "summary": "Qué cambió y por qué (1-2 líneas)"}],
  "sessions": [
    {"date": "2026-11-03", "sport": "run",            # run|swim|bike|gym|rest|race
     "title": "Rodaje suave + rectas",
     "key": false,                                    # sesión clave de la semana
     "intensity": "E",                                # intensidad principal (E/M/T/I/R/CUR/RP)
     "distance_km": 8, "distance_m": null, "duration_min": 45,
     "blocks": [{"name": "Calentamiento", "short": "2 km E", "text": "2 km a {E}"}, …],
                                                      # short = versión de una línea (la vista compacta
                                                      # de natación/gimnasio muestra las series con él)
     "steps": [...],                                  # opcional: pasos para el reloj (ver app/garmin_workouts.py;
                                                      # app/steps_from_text.py los genera desde los bloques de carrera)
     "template": "gymLower",                          # opcional: hereda bloques de la plantilla
     "focus": "Tren inferior",                        # gimnasio: Tren superior | Tren inferior | Cuerpo completo
     "why": "Para qué sirve esta sesión",
     "notes": "Consejos"}
  ]
}

En los textos, {E} {M} {T} {I} {R} {CUR} {RP} se sustituyen al mostrar el plan
por los ritmos que salen del VDOT actual (ver paces.py).

Uso:
  app/.venv/bin/python app/plan_tool.py import data/plans/san_silvestre_2026.json
  app/.venv/bin/python app/plan_tool.py vdot 48.5 "Test 5K 08/11: 20:51"
  app/.venv/bin/python app/plan_tool.py vdot-from-race 5000 20:51 "Test 5K" --date 2026-11-08
  app/.venv/bin/python app/plan_tool.py markdown        # reescribe data/training_plan.md

Sin base de datos (sesión de Claude Code en la nube): python3 app/plan_tool.py render <json>
y python3 app/plan_tool.py vdot-offline 5000 19:56 "Test 5K" --date 2026-11-05
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import db
import paces

ROOT = Path(__file__).parent.parent
TRAINING_PLAN_MD = ROOT / "data" / "training_plan.md"
# Historial de VDOT versionado en git: así una sesión de Claude Code en la nube
# (sin app/app.db) puede regenerar el plan con los ritmos correctos.
FITNESS_FILE = ROOT / "data" / "fitness.json"
SPORTS = {"run", "swim", "bike", "gym", "rest", "race"}
CODES = {"E", "M", "T", "I", "R", "CUR", "RP", None}


def validate(plan):
    errors = []
    g = plan.get("goal") or {}
    for k in ("name", "race_date", "distance_m"):
        if not g.get(k):
            errors.append(f"goal.{k} falta")
    templates = plan.get("templates") or {}
    seen = set()
    for i, s in enumerate(plan.get("sessions") or []):
        where = f"sesión {i} ({s.get('date')})"
        try:
            date.fromisoformat(s.get("date", ""))
        except ValueError:
            errors.append(f"{where}: fecha inválida")
        if s.get("sport") not in SPORTS:
            errors.append(f"{where}: sport '{s.get('sport')}' no válido")
        if s.get("intensity") not in CODES:
            errors.append(f"{where}: intensity '{s.get('intensity')}' no válida")
        if s.get("template") and s["template"] not in templates:
            errors.append(f"{where}: plantilla '{s['template']}' no existe")
        tf = (templates.get(s.get("template") or "") or {}).get("focus")
        if s.get("sport") == "gym" and (s.get("focus") or tf) not in ("Tren superior", "Tren inferior", "Cuerpo completo"):
            errors.append(f"{where}: el gimnasio necesita focus = Tren superior | Tren inferior | Cuerpo completo")
        if not s.get("blocks") and not s.get("template") and s.get("sport") not in ("rest",):
            errors.append(f"{where}: sin bloques (hay que detallar la sesión)")
        seen.add(s.get("date"))
    if not plan.get("sessions"):
        errors.append("no hay sesiones")
    return errors


def expand(plan, s):
    """Sesión con los bloques de su plantilla ya incorporados."""
    s = dict(s)
    t = (plan.get("templates") or {}).get(s.get("template") or "")
    if t:
        s["blocks"] = (s.get("blocks_before") or []) + t.get("blocks", []) + (s.get("blocks") or [])
        s.setdefault("duration_min", t.get("duration_min"))
        s.setdefault("title", t.get("title"))
        s.setdefault("focus", t.get("focus"))
        if t.get("steps") and not s.get("steps"):
            s["steps"] = t["steps"]  # pasos para el reloj (natación, bici)
    return s


def import_plan(path, athlete_id, generator="claude-code"):
    plan = json.loads(Path(path).read_text())
    errs = validate(plan)
    if errs:
        raise SystemExit("Plan inválido:\n- " + "\n- ".join(errs))
    g = plan["goal"]
    with db.connect() as conn:
        conn.execute("UPDATE goals SET active=0 WHERE athlete_id=?", (athlete_id,))
        cur = conn.execute(
            "INSERT INTO goals (athlete_id, name, race_date, distance_m, target_time_s) VALUES (?,?,?,?,?)",
            (athlete_id, g["name"], g["race_date"], g["distance_m"], g.get("target_time_s")))
        goal_id = cur.lastrowid
        conn.execute("UPDATE plans SET active=0 WHERE athlete_id=?", (athlete_id,))
        cur = conn.execute("INSERT INTO plans (athlete_id, goal_id, generator, plan_json) VALUES (?,?,?,?)",
                           (athlete_id, goal_id, generator, json.dumps(plan, ensure_ascii=False)))
        plan_id = cur.lastrowid
        seq = {}
        for s in plan["sessions"]:
            s = expand(plan, s)
            seq[s["date"]] = seq.get(s["date"], 0) + 1
            conn.execute(
                "INSERT INTO plan_sessions (plan_id, date, seq, sport, title, key_session, session) VALUES (?,?,?,?,?,?,?)",
                (plan_id, s["date"], seq[s["date"]], s["sport"], s.get("title"), int(bool(s.get("key"))),
                 json.dumps(s, ensure_ascii=False)))
    f = plan.get("fitness")
    if f and f.get("vdot") and not db.current_vdot(athlete_id) and not fitness_history():
        db.set_vdot(athlete_id, f["vdot"], f.get("source", "estimación inicial"))
    sync_fitness(athlete_id)
    return plan_id


# ------------------------------------------------------------- VDOT (fichero)

def fitness_history():
    return json.loads(FITNESS_FILE.read_text()) if FITNESS_FILE.exists() else []


def fitness_add(vdot, source, day=None):
    h = fitness_history()
    h.append({"date": day or date.today().isoformat(), "vdot": vdot, "source": source})
    h.sort(key=lambda r: r["date"])
    FITNESS_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def set_vdot_everywhere(athlete_id, vdot, source, day=None):
    """Guarda un VDOT nuevo en la BD local y en data/fitness.json (que va a git)."""
    db.set_vdot(athlete_id, vdot, source, day)
    fitness_add(vdot, source, day)


def sync_fitness(athlete_id):
    """Fichero ↔ BD: añade a cada lado lo que le falte (p. ej. un test registrado en la nube)."""
    in_db = {(r["set_on"], round(r["vdot"], 1)) for r in db.vdot_history(athlete_id)}
    in_file = {(r["date"], round(r["vdot"], 1)) for r in fitness_history()}
    for r in fitness_history():
        if (r["date"], round(r["vdot"], 1)) not in in_db:
            db.set_vdot(athlete_id, r["vdot"], r["source"], r["date"])
    for r in db.vdot_history(athlete_id):
        if (r["set_on"], round(r["vdot"], 1)) not in in_file:
            fitness_add(r["vdot"], r["source"], r["set_on"])


def current_paces(athlete_id):
    v = db.current_vdot(athlete_id)
    g = db.active_goal(athlete_id)
    if not v:
        return None
    return paces.zone_paces(v["vdot"], g["target_time_s"] if g else None, g["distance_m"] if g else 10000)


# ---------------------------------------------------------- markdown / web

DAYS_CA = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"]
SPORT_CA = {"run": "Córrer", "swim": "Natació", "bike": "Bici", "gym": "Gimnàs", "rest": "Descans", "race": "Cursa (córrer)"}


def session_line(s, pz):
    head = f"**{SPORT_CA[s['sport']]}"
    if s["sport"] == "run" and s.get("duration_min"):
        head += f" {s['duration_min']}min"
    elif s.get("distance_km"):
        head += f" {s['distance_km']:g}km"
    elif s.get("distance_m"):
        head += f" {s['distance_m']:g}m"
    elif s.get("duration_min"):
        head += f" {s['duration_min']}min"
    head += f"** — {s.get('title', '')}" + (f" ({s['focus']})" if s.get("focus") else "")
    blocks = " ".join(f"{b.get('name')}: {paces.render_text(b.get('text', ''), pz) if pz else b.get('text', '')}."
                      for b in s.get("blocks") or [])
    return (head + (". " + blocks if blocks else "")).replace("|", "/").replace("..", ".")


def write_markdown(athlete_id):
    """Reescribe data/training_plan.md desde el plan activo de la BD."""
    plan_row = db.active_plan(athlete_id)
    if not plan_row:
        raise SystemExit("No hay plan activo")
    v = db.current_vdot(athlete_id)
    return render_markdown(json.loads(plan_row["plan_json"]), v["vdot"] if v else None, v["source"] if v else "")


def render_markdown(plan, vdot=None, vdot_source=""):
    """data/training_plan.md a partir del JSON y un VDOT (sin base de datos)."""
    g = plan["goal"]
    pz = paces.zone_paces(vdot, g.get("target_time_s"), g["distance_m"]) if vdot else None
    sessions = [expand(plan, s) for s in plan["sessions"]]
    by_day = {}
    for s in sessions:
        by_day.setdefault(s["date"], []).append(s)
    first = date.fromisoformat(min(by_day))
    last = date.fromisoformat(max(by_day))
    monday = first - timedelta(days=first.weekday())

    tt = paces.fmt_time(g["target_time_s"]) if g.get("target_time_s") else "–"
    out = [f"# Pla d'entrenament — {g['name']} ({g['distance_m']/1000:g}km, {g['race_date']})", "",
           "_Generat automàticament des de `data/plans/*.json` (`app/plan_tool.py`). "
           "No editar a mà: edita el JSON i regenera._", "",
           f"Objectiu: **{tt}**. {plan.get('summary', '')}", ""]
    if pz:
        out += [f"**Ritmes actuals** (VDOT {vdot:.1f}, {vdot_source}; es recalculen quan canvia el VDOT):", "",
                "| Intensitat | Ritme | FC |", "|---|---|---|"]
        for code in ("E", "M", "T", "I", "R", "CUR", "RP"):
            if code in pz:
                out.append(f"| {code} — {pz[code]['name']} | {pz[code]['text']} | {pz[code]['hr']} |")
        out.append("")
    out += ["## Fases", "", "| Fase | Dates | Focus |", "|---|---|---|"]
    for ph in plan.get("phases") or []:
        out.append(f"| {ph['name']} | {ph['from']} → {ph['to']} | {ph.get('focus', '')} |")
    out.append("")
    week = 1
    d = monday
    while d <= last:
        days = [d + timedelta(days=i) for i in range(7)]
        if any(x.isoformat() in by_day for x in days):
            phase = next((ph["name"] for ph in plan.get("phases") or [] if ph["from"] <= days[-1].isoformat() and ph["to"] >= d.isoformat()), "")
            out += [f"## Setmana {week} ({d.day}/{d.month} - {days[-1].day}/{days[-1].month}) — {phase}", "",
                    "| Dia | Sessió |", "|---|---|"]
            for x in days:
                ss = by_day.get(x.isoformat())
                if not ss:
                    continue
                txt = " + ".join(session_line(s, pz) for s in ss)
                out.append(f"| {DAYS_CA[x.weekday()]} {x.day}/{x.month} | {txt} |")
            out.append("")
            week += 1
        d += timedelta(days=7)
    TRAINING_PLAN_MD.write_text("\n".join(out), encoding="utf-8")
    return TRAINING_PLAN_MD


def _secs(t):
    parts = [int(x) for x in t.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("import"); pi.add_argument("path")
    pv = sub.add_parser("vdot"); pv.add_argument("value", type=float); pv.add_argument("source")
    pr = sub.add_parser("vdot-from-race", help="calcula el VDOT de un test/carrera y lo guarda")
    pr.add_argument("distance_m", type=float); pr.add_argument("time", help="mm:ss o h:mm:ss")
    pr.add_argument("source"); pr.add_argument("--date")
    sub.add_parser("markdown")
    sub.add_parser("validate").add_argument("path")
    prd = sub.add_parser("render", help="SIN base de datos (nube): regenera training_plan.md desde el JSON + data/fitness.json")
    prd.add_argument("path")
    pvo = sub.add_parser("vdot-offline", help="SIN base de datos (nube): añade un test a data/fitness.json")
    pvo.add_argument("distance_m", type=float); pvo.add_argument("time"); pvo.add_argument("source"); pvo.add_argument("--date")
    p.add_argument("--athlete", type=int)
    args = p.parse_args()
    if args.cmd == "validate":
        errs = validate(json.loads(Path(args.path).read_text()))
        print("OK" if not errs else "\n".join(errs))
        return
    if args.cmd in ("render", "vdot-offline"):
        if args.cmd == "vdot-offline":
            v = round(paces.vdot_from_race(args.distance_m, _secs(args.time)), 1)
            fitness_add(v, f"{args.source}: {args.distance_m/1000:g} km en {paces.fmt_time(_secs(args.time))}", args.date)
            print(f"VDOT {v} añadido a {FITNESS_FILE} (predicción 10K {paces.fmt_time(paces.predict_time(v, 10000))})")
            plans = sorted((ROOT / "data" / "plans").glob("*.json"), key=lambda f: f.stat().st_mtime)
            path = plans[-1]
        else:
            path = Path(args.path)
        plan = json.loads(path.read_text())
        errs = validate(plan)
        if errs:
            raise SystemExit("Plan inválido:\n- " + "\n- ".join(errs))
        h = fitness_history()
        last = h[-1] if h else (plan.get("fitness") or {})
        print(f"Escrito {render_markdown(plan, last.get('vdot'), last.get('source', ''))}")
        return
    db.init()
    athletes = db.all_athletes()
    aid = args.athlete or (athletes[0]["id"] if len(athletes) == 1 else None)
    if not aid:
        raise SystemExit("Indica --athlete ID")
    if args.cmd == "import":
        pid = import_plan(args.path, aid)
        print(f"Plan {pid} importado")
        print(f"Escrito {write_markdown(aid)}")
    elif args.cmd == "vdot":
        set_vdot_everywhere(aid, args.value, args.source)
        print(f"VDOT {args.value} guardado; ritmos recalculados")
        print(f"Escrito {write_markdown(aid)}")
    elif args.cmd == "vdot-from-race":
        secs = _secs(args.time)
        v = round(paces.vdot_from_race(args.distance_m, secs), 1)
        set_vdot_everywhere(aid, v, f"{args.source}: {args.distance_m/1000:g} km en {paces.fmt_time(secs)}", args.date)
        print(f"VDOT {v} guardado (predicción 10K {paces.fmt_time(paces.predict_time(v, 10000))})")
        print(f"Escrito {write_markdown(aid)}")
    elif args.cmd == "markdown":
        print(f"Escrito {write_markdown(aid)}")


if __name__ == "__main__":
    sys.exit(main())
