"""Garmin Connect como fuente de actividades de la app (sustituye a Strava).

Para cada actividad nueva del reloj guarda, con el mismo formato que usábamos
con Strava (así métricas, gráficas, plan y resumen no cambian):
  - resumen (tabla activities) + el JSON completo de Garmin (carga de
    entrenamiento, Training Effect, dinámica de carrera…)
  - vueltas (lapDTOs), parciales por km y mejores esfuerzos (calculados de las series)
  - series segundo a segundo (FC, velocidad, cadencia, potencia, altitud, GPS…)
  - métricas calculadas (zonas, TRIMP, desacople, eficiencia…)

Las actividades que ya estaban en la app desde Strava (abril 2026 →) no se
duplican: se reconocen por la hora de inicio y solo se les añade el resumen de Garmin.

Uso:  app/.venv/bin/python app/garmin_source.py [--days 14] [--since 2026-04-01]
"""

import argparse
import json
import sys
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402
import enrich  # noqa: E402

GARMIN_ID_OFFSET = 10 ** 12  # ids de la app para actividades que solo vienen de Garmin

SPORT = {
    "running": "Run", "street_running": "Run", "track_running": "Run", "treadmill_running": "Run",
    "trail_running": "TrailRun", "virtual_run": "VirtualRun",
    "cycling": "Ride", "road_biking": "Ride", "gravel_cycling": "GravelRide", "mountain_biking": "MountainBikeRide",
    "indoor_cycling": "VirtualRide", "virtual_ride": "VirtualRide",
    "lap_swimming": "Swim", "open_water_swimming": "Swim",
    "strength_training": "WeightTraining", "hiit": "HighIntensityIntervalTraining", "cardio": "Workout",
    "indoor_cardio": "Workout", "yoga": "Yoga", "pilates": "Yoga",
    "walking": "Walk", "hiking": "Hike", "resort_skiing_snowboarding_ws": "AlpineSki", "resort_skiing": "AlpineSki",
    "tennis": "Tennis", "tennis_v2": "Tennis", "padel": "Padel", "paddelball": "Padel", "pickleball": "Padel", "multi_sport": "Workout", "rowing": "Rowing", "indoor_rowing": "Rowing",
}
TRAINER = {"treadmill_running", "indoor_cycling", "virtual_ride", "lap_swimming", "indoor_rowing"}

BEST_DISTANCES = [("400m", 400), ("1/2 mile", 805), ("1K", 1000), ("1 mile", 1609), ("2 mile", 3219),
                  ("5K", 5000), ("10K", 10000), ("15K", 15000), ("Half-Marathon", 21097)]


def _pack(o):
    return zlib.compress(json.dumps(o, separators=(",", ":")).encode())


def login():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from garmin_sync import login as _login
    return _login()


def _local_iso(a):
    """'2026-11-08 19:19:43' → '2026-11-08T19:19:43Z' (mismo formato que guardaba Strava)."""
    return (a.get("startTimeLocal") or "").replace(" ", "T")[:19] + "Z"


# ----------------------------------------------------------------- series

def streams_from_details(details, sport):
    """Convierte get_activity_details de Garmin al formato de streams de Strava."""
    if not details or not details.get("activityDetailMetrics"):
        return None
    idx = {m["key"]: m["metricsIndex"] for m in details["metricDescriptors"]}
    rows = [r["metrics"] for r in details["activityDetailMetrics"]]

    def col(key):
        i = idx.get(key)
        return [r[i] if i is not None and i < len(r) else None for r in rows] if i is not None else None

    ts = col("directTimestamp")
    if not ts or ts[0] is None:
        return None
    t0 = ts[0]
    time_s = [int(round(((x or t0) - t0) / 1000)) for x in ts]
    out = {"time": {"data": time_s}}

    def put(name, data):
        if data and any(v is not None for v in data):
            out[name] = {"data": data}

    put("distance", col("sumDistance"))
    put("heartrate", col("directHeartRate"))
    put("velocity_smooth", col("directSpeed"))
    put("altitude", col("directElevation"))
    put("watts", col("directPower"))
    put("temp", col("directAirTemperature"))
    # Cadencia: la app usa la convención de Strava (una pierna en carrera) y la dobla al mostrar
    cad = col("directRunCadence") if sport in enrich.RUN else (col("directBikeCadence") or col("directSwimCadence"))
    put("cadence", cad)
    lat, lng = col("directLatitude"), col("directLongitude")
    if lat and lng:
        put("latlng", [[a, b] if a is not None and b is not None else None for a, b in zip(lat, lng)])
    mov = col("sumMovingDuration")
    if mov:
        put("moving", [i == 0 or (mov[i] or 0) > (mov[i - 1] or 0) for i in range(len(mov))])
    for key, name in (("directGroundContactTime", "gct"), ("directVerticalOscillation", "vertical_osc"),
                      ("directStrideLength", "stride"), ("directRespirationRate", "respiration")):
        put(name, col(key))
    return out


def laps_from_splits(splits, sport):
    out = []
    for i, l in enumerate((splits or {}).get("lapDTOs") or []):
        cad = l.get("averageRunCadence")
        out.append({
            "lap_index": i, "split": i + 1, "distance": l.get("distance") or 0,
            "moving_time": int(round(l.get("movingDuration") or l.get("duration") or 0)),
            "elapsed_time": int(round(l.get("elapsedDuration") or l.get("duration") or 0)),
            "average_speed": l.get("averageSpeed"), "max_speed": l.get("maxSpeed"),
            "average_heartrate": l.get("averageHR"), "max_heartrate": l.get("maxHR"),
            # Garmin da pasos/min de las dos piernas; la app guarda una (convención Strava)
            "average_cadence": (cad / 2 if cad and sport in enrich.RUN else l.get("averageBikeCadence") or cad),
            "total_elevation_gain": l.get("elevationGain") or 0,
            "average_watts": l.get("averagePower"),
        })
    return out


def splits_per_km(streams):
    """Parciales por km a partir de las series (como splits_metric de Strava)."""
    if not streams or "distance" not in streams:
        return []
    t, d = streams["time"]["data"], streams["distance"]["data"]
    hr = (streams.get("heartrate") or {}).get("data")
    alt = (streams.get("altitude") or {}).get("data")
    mov = (streams.get("moving") or {}).get("data")
    out, start, k = [], 0, 1
    for i in range(1, len(d)):
        if d[i] is None:
            continue
        if d[i] >= k * 1000 or i == len(d) - 1:
            seg = range(start + 1, i + 1)
            mt = sum(t[j] - t[j - 1] for j in seg if not mov or mov[j]) if seg else 0
            dist = (d[i] or 0) - (d[start] or 0)
            hrs = [hr[j] for j in seg if hr and hr[j]]
            out.append({"split": k, "distance": dist, "moving_time": mt,
                        "average_speed": dist / mt if mt else None,
                        "average_heartrate": sum(hrs) / len(hrs) if hrs else None,
                        "elevation_difference": (alt[i] - alt[start]) if alt and alt[i] is not None and alt[start] is not None else 0})
            start, k = i, k + 1
    return [s for s in out if s["distance"] >= 100]


def best_efforts(streams):
    """Tramo más rápido de cada distancia (como best_efforts de Strava), con dos punteros."""
    if not streams or "distance" not in streams:
        return []
    t, d = streams["time"]["data"], streams["distance"]["data"]
    pts = [(ti, di) for ti, di in zip(t, d) if di is not None]
    out = []
    for name, dist in BEST_DISTANCES:
        if not pts or pts[-1][1] - pts[0][1] < dist:
            break
        best, j = None, 0
        for i in range(len(pts)):
            while j < len(pts) and pts[j][1] - pts[i][1] < dist:
                j += 1
            if j >= len(pts):
                break
            el = pts[j][0] - pts[i][0]
            if best is None or el < best:
                best = el
        if best:
            out.append({"name": name, "distance": dist, "moving_time": best, "elapsed_time": best})
    return out


# ---------------------------------------------------------------- importar

def _existing_by_start(athlete_id, start_iso, sport):
    """Misma actividad ya guardada: mismo deporte y inicio con <20 min de diferencia
    (la misma salida grabada por dos aparatos no empieza exactamente a la vez)."""
    t = datetime.fromisoformat(start_iso[:19])
    lo, hi = (t - timedelta(minutes=20)).isoformat(), (t + timedelta(minutes=20)).isoformat()
    disc = _disc(sport)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, garmin_id, sport_type, start_date_local FROM activities "
            "WHERE athlete_id=? AND substr(start_date_local,1,19) BETWEEN ? AND ?",
            (athlete_id, lo, hi)).fetchall()
    rows = [r for r in rows if _disc(r["sport_type"]) == disc]
    return min(rows, key=lambda r: abs((datetime.fromisoformat(r["start_date_local"][:19]) - t).total_seconds())) if rows else None


def _disc(sport):
    if sport in enrich.RUN:
        return "run"
    if sport in enrich.RIDE:
        return "bike"
    return sport


GARMIN_EXTRAS = ("activityTrainingLoad", "aerobicTrainingEffect", "anaerobicTrainingEffect", "vO2MaxValue",
                 "avgGroundContactTime", "avgVerticalOscillation", "avgStrideLength", "avgRespirationRate",
                 "avgGradeAdjustedSpeed", "differenceBodyBattery", "trainingEffectLabel")


def merge_garmin_extras(activity_id, a):
    """Añade a las métricas de la actividad lo que da Garmin y Strava no (carga, Training Effect…)."""
    with db.connect() as conn:
        row = conn.execute("SELECT metrics FROM activity_metrics WHERE activity_id=?", (activity_id,)).fetchone()
        m = json.loads(row["metrics"]) if row and row["metrics"] else {}
        for k in GARMIN_EXTRAS:
            if a.get(k) is not None:
                m["garmin_" + k] = a[k]
        if row:
            conn.execute("UPDATE activity_metrics SET metrics=? WHERE activity_id=?", (json.dumps(m), activity_id))
        else:
            conn.execute("INSERT INTO activity_metrics (activity_id, metrics) VALUES (?,?)", (activity_id, json.dumps(m)))


def import_activity(client, athlete_id, a, log=print):
    gid = a["activityId"]
    tkey = (a.get("activityType") or {}).get("typeKey") or ""
    if tkey == "multi_sport" or a.get("isParent"):
        # Triatlón: la actividad "madre" engloba los segmentos, que llegan por separado.
        # Importarla contaría la carga dos veces.
        return False
    sport = SPORT.get(tkey, tkey.replace("_", " ").title().replace(" ", ""))
    start = _local_iso(a)
    ex = _existing_by_start(athlete_id, start, sport)
    if ex:  # ya estaba (de Strava o de una pasada anterior): solo enlazamos el resumen de Garmin
        if not ex["garmin_id"]:
            with db.connect() as conn:
                conn.execute("UPDATE activities SET garmin_id=?, garmin_json=? WHERE id=?", (gid, _pack(a), ex["id"]))
            merge_garmin_extras(ex["id"], a)
        return False

    aid = GARMIN_ID_OFFSET + gid
    summary = {"id": aid, "name": a.get("activityName"), "sport_type": sport, "type": sport,
               "start_date_local": start, "distance": a.get("distance"),
               "moving_time": int(round(a.get("movingDuration") or a.get("duration") or 0)),
               "total_elevation_gain": a.get("elevationGain"), "average_heartrate": a.get("averageHR"),
               "max_heartrate": a.get("maxHR"), "average_speed": a.get("averageSpeed"), "source": "garmin"}
    db.save_activities(athlete_id, [summary])

    details = splits = None
    try:
        details = client.get_activity_details(gid, maxchart=10000)
    except Exception as e:
        log(f"  sin series ({e})")
    try:
        splits = client.get_activity_splits(gid)
    except Exception:
        pass
    streams = streams_from_details(details, sport)
    laps = laps_from_splits(splits, sport)
    detail = dict(a, laps=laps, splits_metric=splits_per_km(streams), best_efforts=best_efforts(streams),
                  elapsed_time=int(round(a.get("elapsedDuration") or a.get("duration") or 0)),
                  calories=a.get("calories"), device_name=a.get("deviceName") or "Garmin",
                  average_cadence=(a.get("averageRunningCadenceInStepsPerMinute") or 0) / 2 or a.get("averageBikingCadenceInRevPerMinute"),
                  average_watts=a.get("avgPower"), weighted_average_watts=a.get("normPower"),
                  max_speed=a.get("maxSpeed"), trainer=tkey in TRAINER, manual=a.get("manualActivity"),
                  description=a.get("description"), workout_type=None, suffer_score=None,
                  perceived_exertion=None, gear_id=None, kilojoules=None, average_temp=None)
    db.save_detail(aid, detail, _pack(detail), _pack(streams) if streams else None)
    zones, src = enrich.hr_zones_for(athlete_id)
    m = enrich.compute_metrics(streams, zones, sport, bool(a.get("avgPower")))
    db.save_metrics(aid, m, src)
    merge_garmin_extras(aid, a)  # extras de Garmin que Strava no daba
    with db.connect() as conn:
        conn.execute("UPDATE activities SET garmin_id=?, garmin_json=?, enrich_status=? WHERE id=?",
                     (gid, _pack(a), "ok" if streams else "sin streams", aid))
    log(f"  + {start[:16]} {sport} «{a.get('activityName')}»")
    return True


def sync(days=14, since=None, log=print, client=None):
    """Trae las actividades de Garmin de los últimos `days` días (o desde `since`)."""
    db.init()
    athlete_id = db.all_athletes()[0]["id"]
    client = client or login()
    start = since or (date.today() - timedelta(days=days)).isoformat()
    acts = client.get_activities_by_date(start, date.today().isoformat())
    new = sum(1 for a in sorted(acts, key=lambda x: x.get("startTimeLocal") or "")
              if import_activity(client, athlete_id, a, log))
    msg = f"Garmin: {new} actividades nuevas ({len(acts)} revisadas desde {start})"
    db.set_sync_status(athlete_id, "done", msg)
    log(msg)
    return new


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--since")
    p.add_argument("--wellness", action="store_true", help="también sueño, VFC, Body Battery y estado de entrenamiento")
    args = p.parse_args()
    client = login()
    sync(args.days, args.since, client=client)
    if args.wellness:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import garmin_sync
        garmin_sync.sync_wellness(client, min(args.days, 14))


if __name__ == "__main__":
    main()
