"""Sube sesiones del plan a Garmin Connect como entrenos estructurados.

El reloj (Forerunner 965) los recibe al sincronizar y guía la sesión paso a
paso, con avisos de ritmo. Usa la API no oficial de Garmin Connect (la misma
sesión que garmin_sync.py, tokens en ~/.garminconnect). Para escalar a otros
usuarios haría falta la Training API oficial de Garmin.

Cada sesión necesita el campo opcional `steps` en el JSON del plan:
  "steps": [
    {"type": "warmup",   "dist_m": 2000, "intensity": "E"},
    {"type": "repeat",   "reps": 3, "steps": [
        {"type": "interval", "dist_m": 1600, "intensity": "T"},
        {"type": "recovery", "time_s": 60}]},
    {"type": "interval", "time_s": 20, "note": "Recta progresiva"},
    {"type": "cooldown", "dist_m": 1500, "intensity": "E"}]
  type: warmup | interval | recovery | rest | cooldown | repeat
  duración: dist_m o time_s (sin ninguno = hasta pulsar vuelta)
  intensity: código de ritmo (E, M, T, I, R, CUR, RP) → objetivo de ritmo en el reloj
  natación: stroke (free | back | breast | fly | drill | any) y equipment (fins | pull_buoy |
  paddles | kickboard); la piscina es de 25 m. Los descansos van como {"type": "rest", "time_s": 15}.

Uso (con el venv principal, que tiene garminconnect):
  .venv/bin/python app/garmin_workouts.py --date 2026-11-03            # sube y programa
  .venv/bin/python app/garmin_workouts.py --date 2026-11-03 --dry-run  # solo muestra el JSON
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402
import paces  # noqa: E402
import plan_tool  # noqa: E402

STEP_TYPES = {"warmup": (1, "warmup"), "cooldown": (2, "cooldown"), "interval": (3, "interval"),
              "recovery": (4, "recovery"), "rest": (5, "rest"), "repeat": (6, "repeat")}
SPORTS = {"run": (1, "running"), "race": (1, "running"), "bike": (2, "cycling"), "swim": (4, "swimming")}
STROKES = {"any": (1, "any_stroke"), "back": (2, "backstroke"), "breast": (3, "breaststroke"),
           "drill": (4, "drill"), "fly": (5, "fly"), "free": (6, "free")}
EQUIPMENT = {"fins": (1, "fins"), "kickboard": (2, "kickboard"), "paddles": (3, "paddles"),
             "pull_buoy": (4, "pull_buoy")}
PREFIX = "[Plan] "  # para reconocer (y poder borrar) los entrenos que sube la app


def _step(st, order, pz):
    if st["type"] == "repeat":
        children, n = [], order
        for c in st["steps"]:
            n += 1
            children.append(_step(c, n, pz))
        return {"type": "RepeatGroupDTO", "stepOrder": order,
                "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
                "numberOfIterations": st["reps"], "smartRepeat": False,
                "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
                "endConditionValue": float(st["reps"]), "workoutSteps": children}
    tid, tkey = STEP_TYPES[st["type"]]
    if st.get("dist_m"):
        end, val = {"conditionTypeId": 3, "conditionTypeKey": "distance"}, float(st["dist_m"])
    elif st.get("time_s"):
        end, val = {"conditionTypeId": 2, "conditionTypeKey": "time"}, float(st["time_s"])
    else:
        end, val = {"conditionTypeId": 1, "conditionTypeKey": "lap.button"}, None
    out = {"type": "ExecutableStepDTO", "stepOrder": order,
           "stepType": {"stepTypeId": tid, "stepTypeKey": tkey},
           "endCondition": end, "endConditionValue": val,
           "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}}
    code = st.get("intensity")
    if code and pz and code in pz:
        # Objetivo de ritmo: Garmin lo quiere como velocidad (m/s), de lenta a rápida
        slow, fast = pz[code]["slow"], pz[code]["fast"]
        if abs(slow - fast) < 6:  # ritmo único → margen de ±3 s/km para que el reloj no pite sin parar
            slow, fast = slow + 3, fast - 3
        out["targetType"] = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
        out["targetValueOne"] = round(1000 / slow, 3)
        out["targetValueTwo"] = round(1000 / fast, 3)
    if st.get("stroke"):
        i, k = STROKES[st["stroke"]]
        out["strokeType"] = {"strokeTypeId": i, "strokeTypeKey": k}
    if st.get("equipment"):
        i, k = EQUIPMENT[st["equipment"]]
        out["equipmentType"] = {"equipmentTypeId": i, "equipmentTypeKey": k}
    desc = st.get("note") or (f"{code} {pz[code]['text']}" if code and pz and code in pz else "")
    if desc:
        out["description"] = desc[:120]
    return out


def _count(steps):
    return sum(1 + (_count(s["steps"]) if s["type"] == "repeat" else 0) for s in steps)


def build_workout(session, pz):
    sid, skey = SPORTS[session["sport"]]
    steps, order = [], 0
    for st in session["steps"]:
        order += 1
        steps.append(_step(st, order, pz))
        if st["type"] == "repeat":
            order += _count(st["steps"])
    name = PREFIX + paces.render_text(session.get("title") or "", pz)
    desc = " · ".join(paces.render_text(b.get("text", ""), pz) for b in session.get("blocks") or [])
    w = {"workoutName": name[:80], "description": desc[:1000],
         "sportType": {"sportTypeId": sid, "sportTypeKey": skey},
            "workoutSegments": [{"segmentOrder": 1, "sportType": {"sportTypeId": sid, "sportTypeKey": skey},
                                 "workoutSteps": steps}]}
    if session["sport"] == "swim":
        w["poolLength"] = 25.0
        w["poolLengthUnit"] = {"unitId": 1, "unitKey": "meter", "factor": 100.0}
    return w


def sessions_for(day):
    aid = db.all_athletes()[0]["id"]
    plan = db.active_plan(aid)
    rows = db.plan_sessions(plan["id"], day, day)
    return aid, [json.loads(r["session"]) for r in rows]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    aid, sessions = sessions_for(args.date)
    pz = plan_tool.current_paces(aid)
    todo = [s for s in sessions if s.get("steps") and s["sport"] in SPORTS]
    if not todo:
        raise SystemExit(f"No hay sesiones con pasos estructurados el {args.date}")
    if args.dry_run:
        for s in todo:
            print(json.dumps(build_workout(s, pz), ensure_ascii=False, indent=1))
        return

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from garmin_sync import login
    client = login()
    for s in todo:
        w = build_workout(s, pz)
        # Si ya subimos uno con el mismo nombre para ese día, lo sustituimos
        for old in client.garth.connectapi("/workout-service/workouts", params={"start": 0, "limit": 100}) or []:
            if old.get("workoutName") == w["workoutName"]:
                client.garth.request("DELETE", "connectapi", f"/workout-service/workout/{old['workoutId']}", api=True)
        created = client.garth.post("connectapi", "/workout-service/workout", json=w, api=True).json()
        wid = created["workoutId"]
        client.garth.post("connectapi", f"/workout-service/schedule/{wid}", json={"date": args.date}, api=True)
        print(f"✓ Subido y programado el {args.date}: {w['workoutName']} (id {wid})")


if __name__ == "__main__":
    main()
