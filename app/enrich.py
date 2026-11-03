"""Enriquecimiento de actividades: detalle completo + series temporales + métricas.

La lista de /athlete/activities solo da un resumen. Para que el entrenador
pueda decidir bien, por cada actividad descargamos:

  1. Detalle (/activities/{id}): vueltas (laps), parciales por km, mejores
     esfuerzos, calorías, RPE, descripción, dispositivo, material...
  2. Streams (/activities/{id}/streams): las series segundo a segundo de FC,
     velocidad, cadencia, vatios, altitud, pendiente, GPS, temperatura.
  3. Métricas derivadas (calculadas aquí, sin coste de API): tiempo en cada
     zona de FC, TRIMP, desacople aeróbico, factor de eficiencia...

Strava limita las llamadas (por defecto ~100 lecturas/15 min y ~1000/día),
así que esto va despacio y es reanudable: empieza por lo más reciente y, si
se corta, sigue donde lo dejó.

Uso:  .venv/bin/python enrich.py            # todos los atletas, hasta acabar
      .venv/bin/python enrich.py --recompute # recalcula métricas sin llamar a Strava
"""

import argparse
import fcntl
import json
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import requests

import db
import strava

STREAM_KEYS = "time,distance,latlng,altitude,velocity_smooth,heartrate,cadence,watts,temp,moving,grade_smooth"

# Ritmo prudente para no comernos el límite: 2 llamadas por actividad,
# ~90 llamadas cada 15 min → ~45 actividades / 15 min.
MIN_SECONDS_BETWEEN_CALLS = 9.5

def _pack(obj):
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode())


def unpack(blob):
    return json.loads(zlib.decompress(blob)) if blob else None


# --------------------------------------------------------------------------- API

_last_call = [0.0]


def _api_get(path, token, params=None):
    """GET con espera entre llamadas y reintento automático al pasar el límite."""
    while True:
        wait = MIN_SECONDS_BETWEEN_CALLS - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            resp = requests.get(strava.API + path, headers={"Authorization": f"Bearer {token}"},
                                params=params or {}, timeout=60)
        except requests.RequestException as e:
            # cortes de red puntuales: esperamos un poco y reintentamos
            # (sin esto, un solo timeout paraba toda la descarga)
            print(f"  error de red ({e.__class__.__name__}); reintento en 60 s…", flush=True)
            time.sleep(60)
            continue
        if resp.status_code >= 500:
            print(f"  Strava {resp.status_code}; reintento en 60 s…", flush=True)
            time.sleep(60)
            continue
        if resp.status_code == 429:
            # Las ventanas de Strava reinician en los cuartos de hora (y el
            # diario a medianoche UTC). Esperamos al siguiente cuarto.
            now = time.time()
            sleep_s = 900 - (now % 900) + 15
            print(f"  límite de Strava alcanzado; espero {sleep_s/60:.0f} min…", flush=True)
            time.sleep(sleep_s)
            continue
        return resp


def fetch_zones(athlete_id, token):
    resp = _api_get("/athlete/zones", token)
    if resp.status_code == 200:
        db.save_athlete_zones(athlete_id, resp.json(), "strava")
        return True
    return False  # sin permiso profile:read_all → zonas estimadas


# ---------------------------------------------------------------------- métricas

def hr_zones_for(athlete_id):
    """Límites de zonas de FC [(min, max), ...] del atleta.

    Preferimos las zonas que el atleta tiene configuradas en Strava. Si no hay,
    las estimamos con % de FC máx. Como FC máx NO usamos el máximo puntual de
    cada actividad (los pulsómetros de muñeca dan picos falsos de 215-230),
    sino la FC media más alta sostenida 60 s en carrera/bici de los últimos
    2 años, calculada de los streams.
    """
    z = db.get_athlete_zones(athlete_id)
    if z and z["source"] == "manual":  # fijadas a mano (p. ej. de una prueba de esfuerzo)
        cuts = unpack(z["zones"])
        return list(zip(cuts[:-1], cuts[1:])), "manuales"
    if z and z["source"] == "strava":
        hr = (unpack(z["zones"]) or {}).get("heart_rate", {})
        ranges = [(b["min"], b["max"] if b["max"] > 0 else 999) for b in hr.get("zones", [])]
        if ranges:
            return ranges, "strava"
    hrmax = db.estimated_hr_max(athlete_id)
    if not hrmax:
        return None, None
    cuts = [0, 0.60, 0.70, 0.80, 0.90, 9.99]
    return [(round(hrmax * cuts[i]), round(hrmax * cuts[i + 1])) for i in range(5)], f"estimadas (FCmáx≈{hrmax})"


RUN = ("Run", "TrailRun", "VirtualRun")
RIDE = ("Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide")


def _max_rolling(t, vals, window_s):
    """Máximo de la media móvil de `vals` en ventanas de `window_s` segundos."""
    best, j, acc = None, 0, 0.0
    for i in range(len(t)):
        acc += vals[i] or 0
        while t[i] - t[j] >= window_s:
            acc -= vals[j] or 0
            j += 1
        if t[i] - t[0] >= window_s - 1:
            avg = acc / (i - j + 1)
            best = avg if best is None or avg > best else best
    return best


def compute_metrics(streams, zones, sport_type, device_watts=False):
    """Métricas útiles para el entrenador a partir de las series temporales."""
    if not streams:
        return {}
    t = streams.get("time", {}).get("data") or []
    hr = streams.get("heartrate", {}).get("data")
    v = streams.get("velocity_smooth", {}).get("data")
    moving = streams.get("moving", {}).get("data")
    cad = streams.get("cadence", {}).get("data")
    watts = streams.get("watts", {}).get("data")
    temp = streams.get("temp", {}).get("data")
    alt = streams.get("altitude", {}).get("data")
    m = {"samples": len(t)}
    if len(t) < 2:
        return m

    # dt de cada muestra (Strava a veces graba cada 1 s, a veces cada x s);
    # tope de 30 s para no contar pausas como tiempo de esfuerzo.
    dt = [0] + [min(max(t[i] - t[i - 1], 0), 30) for i in range(1, len(t))]
    is_moving = [bool(x) for x in moving] if moving else [True] * len(t)

    def mean(vals, weights):
        num = sum(a * w for a, w in zip(vals, weights) if a is not None)
        den = sum(w for a, w in zip(vals, weights) if a is not None)
        return num / den if den else None

    w_mov = [d if mv else 0 for d, mv in zip(dt, is_moving)]
    m["moving_s"] = sum(w_mov)

    if hr:
        if zones:
            secs = [0] * len(zones)
            for h, d, mv in zip(hr, dt, is_moving):
                if not mv or not h:
                    continue
                for i, (lo, hi) in enumerate(zones):
                    if lo <= h < hi or (i == len(zones) - 1 and h >= lo):
                        secs[i] += d
                        break
            m["hr_zone_s"] = secs
            # TRIMP de Edwards: minutos en cada zona × nº de zona (1..5)
            m["trimp_edwards"] = round(sum(s / 60 * (i + 1) for i, s in enumerate(secs)), 1)
        m["hr_avg"] = round(mean(hr, w_mov) or 0, 1)
        m["hr_max"] = max(h for h in hr if h)
        hr60 = _max_rolling(t, hr, 60)
        if hr60:
            m["hr_max_60s"] = round(hr60, 1)

    if v:
        m["speed_avg_ms"] = round(mean(v, w_mov) or 0, 3)

    # Desacople aeróbico (Pa:HR): compara velocidad/FC (o vatios/FC) de la
    # 1ª mitad con la 2ª. <5 % = base aeróbica sólida en esa duración.
    # Solo carrera y bici (en natación la velocidad del reloj no es fiable), y
    # vatios solo si vienen de un potenciómetro real, no los estimados por Strava.
    out = watts if (watts and device_watts and sport_type in RIDE) else v
    if hr and out and sport_type in RUN + RIDE and m["moving_s"] >= 20 * 60:
        half = m["moving_s"] / 2
        acc, idx = 0, len(t)
        for i, w in enumerate(w_mov):
            acc += w
            if acc >= half:
                idx = i
                break
        def ef(a, b):
            o = mean(out[a:b], w_mov[a:b]); h = mean(hr[a:b], w_mov[a:b])
            return o / h if o and h else None
        ef1, ef2 = ef(0, idx), ef(idx, len(t))
        if ef1 and ef2:
            m["decoupling_pct"] = round((ef1 - ef2) / ef1 * 100, 1)
        efall = ef(0, len(t))
        if efall:
            # Factor de eficiencia: (m/min ó W) por pulsación. Sube cuando mejora la forma.
            m["efficiency_factor"] = round(efall * (60 if out is v else 1), 3)

    if cad:
        c = mean([x if x else None for x in cad], w_mov)
        if c:
            # Strava da la cadencia de carrera en pasos/min de UNA pierna
            m["cadence_avg"] = round(c * (2 if sport_type in ("Run", "TrailRun", "VirtualRun") else 1), 1)
    if watts and device_watts:
        m["watts_avg"] = round(mean(watts, w_mov) or 0, 1)
        # Potencia normalizada (media móvil 30 s ^4)
        if len(watts) >= 30:
            roll = [sum(watts[i - 30:i]) / 30 for i in range(30, len(watts) + 1)]
            m["watts_np"] = round((sum(x ** 4 for x in roll) / len(roll)) ** 0.25, 1)
    if temp:
        m["temp_avg"] = round(sum(temp) / len(temp), 1)
    if alt:
        m["alt_min"], m["alt_max"] = round(min(alt), 1), round(max(alt), 1)
    return m


def recompute_metrics(athlete_id):
    zones, src = hr_zones_for(athlete_id)
    n = 0
    for row in db.activities_with_streams(athlete_id):
        db.save_metrics(row["id"], compute_metrics(unpack(row["streams"]), zones, row["sport_type"],
                                                   bool(row["device_watts"])), src)
        n += 1
    return n


# ---------------------------------------------------------------------- trabajo

def enrich_athlete(athlete_id, max_activities=None, log=print):
    """Descarga detalle + streams de las actividades pendientes (más recientes primero)."""
    # Cerrojo en fichero: si el servidor y el script de terminal coinciden,
    # solo uno trabaja (así no gastamos el doble de llamadas a Strava).
    lock = open(Path(__file__).parent / f".enrich-{athlete_id}.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return
    try:
        token = strava.valid_access_token(athlete_id)
        z = db.get_athlete_zones(athlete_id)
        if (not z or z["source"] != "manual") and not (z and z["source"] == "strava") \
                and fetch_zones(athlete_id, token):
            recompute_metrics(athlete_id)  # recalcula lo ya guardado con las zonas reales

        pending = db.activities_pending_enrichment(athlete_id)
        total = len(pending)
        log(f"Atleta {athlete_id}: {total} actividades por enriquecer")
        for i, row in enumerate(pending[:max_activities] if max_activities else pending, 1):
            token = strava.valid_access_token(athlete_id)  # se refresca si caduca
            aid = row["id"]

            r = _api_get(f"/activities/{aid}", token, {"include_all_efforts": "true"})
            if r.status_code == 404:
                db.mark_enriched(aid, "no encontrada")
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Strava {r.status_code}: {r.text[:200]}")
            detail = r.json()

            streams = None
            if not detail.get("manual"):
                rs = _api_get(f"/activities/{aid}/streams", token,
                              {"keys": STREAM_KEYS, "key_by_type": "true"})
                if rs.status_code == 200:
                    streams = rs.json()
                elif rs.status_code != 404:
                    raise RuntimeError(f"Strava {rs.status_code}: {rs.text[:200]}")

            db.save_detail(aid, detail, _pack(detail), _pack(streams) if streams else None)
            zones, src = hr_zones_for(athlete_id)
            db.save_metrics(aid, compute_metrics(streams, zones, row["sport_type"],
                                                 bool(detail.get("device_watts"))), src)
            db.mark_enriched(aid, "ok" if streams else "sin streams")
            if i % 10 == 0 or i == total:
                log(f"  {i}/{total} · {row['start_date_local'][:10]} {row['sport_type']}")
        recompute_metrics(athlete_id)  # zonas ya con todos los datos → recalcular (local, rápido)
        db.set_enrich_status(athlete_id, None)
    except Exception as e:
        db.set_enrich_status(athlete_id, str(e))
        log(f"  error: {e}")
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--recompute", action="store_true", help="recalcula métricas con los streams guardados")
    p.add_argument("--max", type=int, help="máximo de actividades por atleta en esta pasada")
    p.add_argument("--zones", help="fija zonas de FC a mano: ATLETA_ID:130,140,150,175 (inicio de Z2..Z5)")
    args = p.parse_args()
    db.init()
    if args.zones:
        aid, cuts = args.zones.split(":")
        db.save_athlete_zones(int(aid), [0] + [int(c) for c in cuts.split(",")] + [999], "manual")
        print(f"Atleta {aid}: {recompute_metrics(int(aid))} actividades recalculadas con zonas manuales")
        return
    for a in db.all_athletes():
        if args.recompute:
            print(f"Atleta {a['id']}: {recompute_metrics(a['id'])} actividades recalculadas")
        else:
            enrich_athlete(a["id"], args.max, log=lambda s: print(s, flush=True))


if __name__ == "__main__":
    sys.exit(main())
