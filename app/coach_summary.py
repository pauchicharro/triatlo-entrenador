"""Resumen para el entrenador de IA a partir de app.db.

Convierte todo lo descargado (detalle, streams, métricas) en lo que un
entrenador necesita para planificar, y lo escribe en data/app_summary.md:

  1. Cobertura de los datos (qué parte del histórico tiene detalle).
  2. Estado de carga: forma (CTL), fatiga (ATL) y frescura (TSB).
  3. Últimas 12 semanas: volumen por deporte, carga y distribución de intensidad.
  4. Alertas: saltos bruscos de volumen/carga.
  5. Tendencias de forma: eficiencia y desacople (carrera y bici), ritmo de natación.
  6. Mejores marcas recientes vs. históricas.
  7. Últimos 21 días sesión a sesión, con vueltas/series.

Uso:  app/.venv/bin/python app/coach_summary.py [--athlete ID] [--out ruta]
"""

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import db
import enrich

ROOT = Path(__file__).parent.parent
DEFAULT_OUT = ROOT / "data" / "app_summary.md"

RUN, RIDE, SWIM = enrich.RUN, enrich.RIDE, ("Swim",)
GYM = ("WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining", "Yoga")


def disc(sport):
    if sport in SWIM:
        return "swim"
    if sport in RIDE:
        return "bike"
    if sport in RUN:
        return "run"
    if sport in GYM:
        return "gym"
    return "other"


DISC_ES = {"swim": "Natación", "bike": "Bici", "run": "Carrera", "gym": "Gimnasio/HIIT", "other": "Otros"}


def fmt_dur(s):
    if s is None:
        return "–"
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}" if h else f"{m}:{sec:02d}"


def fmt_pace(speed, sport):
    if not speed:
        return "–"
    if sport in SWIM:
        s = 100 / speed
        return f"{int(s // 60)}:{int(s % 60):02d}/100m"
    if sport in RUN or sport in ("Walk", "Hike"):
        s = 1000 / speed
        return f"{int(s // 60)}:{int(s % 60):02d}/km"
    return f"{speed * 3.6:.1f}km/h"


def day(a):
    return (a["start_date_local"] or "")[:10]


def load_activities(athlete_id):
    with db.connect() as conn:
        return conn.execute(
            """SELECT a.id, a.name, a.sport_type, a.start_date_local, a.distance_m, a.moving_time_s,
                      a.elevation_gain_m, a.average_heartrate, a.average_speed, a.enrich_status,
                      d.perceived_exertion, d.laps, d.best_efforts, d.description, d.trainer,
                      m.metrics, m.trimp_edwards
               FROM activities a
               LEFT JOIN activity_details d ON d.activity_id=a.id
               LEFT JOIN activity_metrics m ON m.activity_id=a.id
               WHERE a.athlete_id=? ORDER BY a.start_date_local""",
            (athlete_id,),
        ).fetchall()


def activity_load(a, zones):
    """(TRIMP, estimada?) — si no hay streams, se aproxima con la FC media."""
    if a["trimp_edwards"] is not None:
        return a["trimp_edwards"], False
    mins = (a["moving_time_s"] or 0) / 60
    hr = a["average_heartrate"]
    if hr and zones:
        z = next((i + 1 for i, (lo, hi) in enumerate(zones) if lo <= hr < hi), 5)
        return mins * z, True
    # sin FC: suponemos Z2 para resistencia y Z1 para el resto
    return mins * (2 if disc(a["sport_type"]) in ("swim", "bike", "run") else 1), True


# ------------------------------------------------------------------ secciones

def section_coverage(acts, zones, zsrc, today):
    total = len(acts)
    done = sum(1 for a in acts if a["enrich_status"] is not None)
    since = (today - timedelta(days=90)).isoformat()
    recent = [a for a in acts if day(a) >= since]
    recent_done = sum(1 for a in recent if a["enrich_status"] is not None)
    oldest_detail = min((day(a) for a in acts if a["enrich_status"] is not None), default=None)
    zt = ", ".join(f"Z{i+1} {'<' + str(hi) if i == 0 else ('≥' + str(lo) if hi >= 900 else f'{lo}-{hi-1}')}"
                   for i, (lo, hi) in enumerate(zones or []))
    lines = [
        "## 1. Cobertura de los datos",
        f"- Actividades en el histórico (Strava): **{total}** ({day(acts[0]) if acts else '–'} → {day(acts[-1]) if acts else '–'}).",
        f"- Con detalle completo (vueltas + streams + métricas): **{done}/{total}**"
        + (f", desde {oldest_detail}." if oldest_detail else "."),
        f"- Últimos 90 días con detalle: **{recent_done}/{len(recent)}**."
        + ("" if recent_done == len(recent) else
           " ⚠️ Faltan sesiones recientes por descargar: las métricas de carga de esas sesiones son estimadas a partir de la FC media."),
        f"- Zonas de FC usadas ({zsrc}): {zt}. Son zonas de **carrera**; en bici/natación la FC va más baja al mismo esfuerzo.",
    ]
    return "\n".join(lines)


def section_load(acts, zones, today):
    daily = defaultdict(float)
    est_days = set()
    start = today - timedelta(days=365)
    for a in acts:
        d = day(a)
        if d < start.isoformat():
            continue
        load, est = activity_load(a, zones)
        daily[d] += load
        if est:
            est_days.add(d)
    ctl = atl = 0.0
    hist = []
    d = start
    while d <= today:
        L = daily.get(d.isoformat(), 0.0)
        ctl += (L - ctl) / 42
        atl += (L - atl) / 7
        hist.append((d, ctl, atl, ctl - atl))
        d += timedelta(days=1)
    cur = hist[-1]

    def at(days_ago):
        return hist[-1 - days_ago] if days_ago < len(hist) else None

    tsb = cur[3]
    if tsb < -30:
        state = "fatiga muy alta (riesgo de sobreentrenamiento si se mantiene)"
    elif tsb < -10:
        state = "fatiga productiva (bloque de carga)"
    elif tsb <= 5:
        state = "equilibrado"
    else:
        state = "fresco (descansado / en tapering o perdiendo forma si se alarga)"
    lines = [
        "## 2. Estado de carga (modelo forma-fatiga con TRIMP de Edwards)",
        "CTL = forma (media exponencial 42 días de la carga diaria), ATL = fatiga (7 días), TSB = CTL − ATL (frescura). "
        "Unidades TRIMP, no TSS: compáralas entre sí, no con valores de TrainingPeaks.",
        "",
        "| Momento | CTL (forma) | ATL (fatiga) | TSB (frescura) |",
        "|---|---|---|---|",
    ]
    for label, n in (("Hoy", 0), ("Hace 7 días", 7), ("Hace 14 días", 14), ("Hace 28 días", 28), ("Hace 56 días", 56), ("Hace 90 días", 90)):
        h = at(n)
        if h:
            lines.append(f"| {label} ({h[0].isoformat()}) | {h[1]:.0f} | {h[2]:.0f} | {h[3]:+.0f} |")
    ramp = cur[1] - (at(7) or cur)[1]
    lines += ["",
              f"- Estado actual: **TSB {tsb:+.0f} → {state}**.",
              f"- Rampa de forma: CTL {ramp:+.1f}/semana "
              + ("(⚠️ subida rápida, >8/semana)" if ramp > 8 else "(bajando: pérdida de forma o descarga)" if ramp < -3 else "(progresión sostenible)") + "."]
    est_recent = [d for d in est_days if d >= (today - timedelta(days=42)).isoformat()]
    if est_recent:
        lines.append(f"- {len(est_recent)} días de las últimas 6 semanas usan carga estimada (sin streams todavía).")
    return "\n".join(lines)


def week_start(dstr):
    d = date.fromisoformat(dstr)
    return (d - timedelta(days=d.weekday())).isoformat()


def section_weeks(acts, zones, today, n=12):
    first = (today - timedelta(days=today.weekday()) - timedelta(weeks=n - 1)).isoformat()
    W = defaultdict(lambda: {"h": defaultdict(float), "km": defaultdict(float), "load": 0.0,
                             "z": [0] * 5, "n": 0})
    for a in acts:
        d = day(a)
        if d < first:
            continue
        w = W[week_start(d)]
        k = disc(a["sport_type"])
        w["h"][k] += (a["moving_time_s"] or 0) / 3600
        w["km"][k] += (a["distance_m"] or 0) / 1000
        w["load"] += activity_load(a, zones)[0]
        w["n"] += 1
        m = json.loads(a["metrics"]) if a["metrics"] else {}
        for i, s in enumerate(m.get("hr_zone_s") or []):
            w["z"][i] += s
    lines = ["## 3. Últimas 12 semanas",
             "Horas (km) por deporte · carga TRIMP · distribución de intensidad por FC (solo sesiones con streams).",
             "",
             "| Semana (lunes) | Ses. | Natación | Bici | Carrera | Gim. | Total h | Carga | Z1-2 | Z3 | Z4-5 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    weeks = []
    for i in range(n):
        ws = (date.fromisoformat(first) + timedelta(weeks=i)).isoformat()
        w = W[ws]
        tot_h = sum(w["h"].values())
        zt = sum(w["z"])
        zz = (f"{(w['z'][0]+w['z'][1])/zt*100:.0f}% | {w['z'][2]/zt*100:.0f}% | {(w['z'][3]+w['z'][4])/zt*100:.0f}%"
              if zt else "– | – | –")

        def c(k, km=True):
            h = w["h"].get(k, 0)
            if not h:
                return "–"
            return f"{h:.1f}h ({w['km'][k]:.{1 if k == 'swim' else 0}f})" if km else f"{h:.1f}h"
        cur = " (en curso)" if ws == (today - timedelta(days=today.weekday())).isoformat() else ""
        lines.append(f"| {ws}{cur} | {w['n']} | {c('swim')} | {c('bike')} | {c('run')} | {c('gym', False)} | "
                     f"{tot_h:.1f} | {w['load']:.0f} | {zz} |")
        weeks.append((ws, tot_h, w["load"], bool(cur)))
    # alertas de saltos (solo semanas completas)
    alerts = []
    full = [w for w in weeks if not w[3]]
    for prev, cur in zip(full, full[1:]):
        if prev[1] >= 3 and cur[1] > prev[1] * 1.3:
            alerts.append(f"- ⚠️ Semana {cur[0]}: volumen +{(cur[1]/prev[1]-1)*100:.0f}% respecto a la anterior "
                          f"({prev[1]:.1f}h → {cur[1]:.1f}h).")
        if prev[2] >= 200 and cur[2] > prev[2] * 1.3:
            alerts.append(f"- ⚠️ Semana {cur[0]}: carga +{(cur[2]/prev[2]-1)*100:.0f}% ({prev[2]:.0f} → {cur[2]:.0f}).")
    lines += ["", "**Alertas de progresión (>30% semana a semana):**"] + (alerts or ["- Ninguna."])
    return "\n".join(lines)


def section_trends(acts, today):
    since = (today - timedelta(days=183)).isoformat()
    by = defaultdict(lambda: defaultdict(list))
    swim = defaultdict(list)
    for a in acts:
        d = day(a)
        if d < since:
            continue
        mo = d[:7]
        k = disc(a["sport_type"])
        m = json.loads(a["metrics"]) if a["metrics"] else {}
        if k in ("run", "bike") and not a["trainer"] and (a["moving_time_s"] or 0) >= 20 * 60:
            if m.get("efficiency_factor"):
                by[k][mo].append((m["efficiency_factor"], m.get("decoupling_pct"), a["average_heartrate"]))
        if k == "swim" and a["average_speed"] and (a["distance_m"] or 0) >= 800:
            swim[mo].append((a["average_speed"], a["average_heartrate"]))
    lines = ["## 4. Tendencias de forma (últimos 6 meses, por mes)",
             "Factor de eficiencia (EF) = metros/min por pulsación (sube = mejor forma aeróbica). "
             "Desacople = deriva de la FC en la 2ª mitad (<5% = buena base aeróbica a esa duración). "
             "Solo sesiones ≥20 min al aire libre; mezcla rodajes y series, así que mira la tendencia, no un mes suelto.",
             ""]
    for k in ("run", "bike"):
        if not by[k]:
            continue
        lines += [f"**{DISC_ES[k]}**", "", "| Mes | Sesiones | EF medio | Desacople mediano | FC media |", "|---|---|---|---|---|"]
        for mo in sorted(by[k]):
            v = by[k][mo]
            efs = [x[0] for x in v]
            decs = sorted(x[1] for x in v if x[1] is not None)
            hrs = [x[2] for x in v if x[2]]
            lines.append(f"| {mo} | {len(v)} | {sum(efs)/len(efs):.2f} | "
                         f"{(f'{decs[len(decs)//2]:+.1f}%' if decs else '–')} | {(f'{sum(hrs)/len(hrs):.0f}' if hrs else '–')} |")
        lines.append("")
    if swim:
        lines += ["**Natación** (sesiones ≥800 m)", "", "| Mes | Sesiones | Ritmo medio | FC media |", "|---|---|---|---|"]
        for mo in sorted(swim):
            v = swim[mo]
            sp = sum(x[0] for x in v) / len(v)
            hrs = [x[1] for x in v if x[1]]
            lines.append(f"| {mo} | {len(v)} | {fmt_pace(sp, 'Swim')} | {(f'{sum(hrs)/len(hrs):.0f}' if hrs else '–')} |")
    return "\n".join(lines)


def section_best(acts, today):
    targets = ["400m", "1K", "1 mile", "5K", "10K", "Half-Marathon"]
    best = {t: {} for t in targets}
    cut90 = (today - timedelta(days=90)).isoformat()
    cut365 = (today - timedelta(days=365)).isoformat()
    for a in acts:
        if a["sport_type"] not in RUN or not a["best_efforts"]:
            continue
        for b in json.loads(a["best_efforts"]):
            name = b.get("name")
            if name not in best or not b.get("moving_time"):
                continue
            t = b["moving_time"]
            for key, cut in (("90d", cut90), ("365d", cut365), ("all", "")):
                if day(a) >= cut and (key not in best[name] or t < best[name][key][0]):
                    best[name][key] = (t, day(a))
    rows = [t for t in targets if best[t]]
    if not rows:
        return "## 5. Mejores marcas en carrera\nTodavía no hay actividades con detalle que incluyan mejores esfuerzos."
    lines = ["## 5. Mejores marcas en carrera (de los «mejores esfuerzos» de Strava)",
             "Solo cuentan actividades con detalle descargado; el histórico completo se irá rellenando.", "",
             "| Distancia | Últimos 90 días | Último año | Histórico (con detalle) |", "|---|---|---|---|"]
    for t in rows:
        cell = lambda k: f"{fmt_dur(best[t][k][0])} ({best[t][k][1]})" if k in best[t] else "–"
        lines.append(f"| {t} | {cell('90d')} | {cell('365d')} | {cell('all')} |")
    return "\n".join(lines)


def section_recent(acts, zones, today, days=21):
    since = (today - timedelta(days=days)).isoformat()
    recent = [a for a in acts if day(a) >= since]
    lines = [f"## 6. Últimos {days} días, sesión a sesión", ""]
    for a in reversed(recent):
        sp = a["sport_type"]
        m = json.loads(a["metrics"]) if a["metrics"] else {}
        load, est = activity_load(a, zones)
        z = m.get("hr_zone_s")
        zstr = ""
        if z and sum(z):
            zstr = " · zonas " + "/".join(f"{s/sum(z)*100:.0f}" for s in z) + "% (Z1..Z5)"
        dist = (f"{a['distance_m']:.0f}m" if sp in SWIM else f"{a['distance_m']/1000:.1f}km") if a["distance_m"] else ""
        bits = [dist, fmt_dur(a["moving_time_s"])]
        if a["distance_m"] and sp not in GYM:
            bits.append(fmt_pace(a["average_speed"], sp))
        if a["average_heartrate"]:
            bits.append(f"FC {a['average_heartrate']:.0f}")
        if a["elevation_gain_m"] and sp not in SWIM and a["elevation_gain_m"] > 50:
            bits.append(f"+{a['elevation_gain_m']:.0f}m")
        bits.append(f"carga {load:.0f}{' (est.)' if est else ''}")
        if m.get("decoupling_pct") is not None:
            bits.append(f"desacople {m['decoupling_pct']:+.1f}%")
        if m.get("efficiency_factor") and sp not in SWIM:
            bits.append(f"EF {m['efficiency_factor']:.2f}")
        if m.get("cadence_avg") and sp in RUN:
            bits.append(f"cad {m['cadence_avg']:.0f}")
        if m.get("watts_np") and sp in RIDE:
            bits.append(f"NP {m['watts_np']:.0f}W")
        if m.get("temp_avg") is not None and sp not in SWIM:
            bits.append(f"{m['temp_avg']:.0f}°C")
        if a["perceived_exertion"]:
            bits.append(f"RPE {a['perceived_exertion']:.0f}")
        if a["trainer"] and disc(sp) in ("bike", "run"):  # en natación "trainer" = piscina
            bits.append("rodillo/cinta")
        lines.append(f"- **{day(a)} {DISC_ES[disc(sp)] if disc(sp) != 'other' else sp}** «{a['name']}»: "
                     + " · ".join(b for b in bits if b) + zstr)
        if a["description"]:
            lines.append(f"  - Nota del atleta: «{a['description'].strip()[:200]}»")
        laps = json.loads(a["laps"]) if a["laps"] else []
        # Las vueltas automáticas cada km/5km ya están resumidas arriba; listamos las que parecen series
        auto = len({round(l.get("distance") or 0, -1) for l in laps[:-1]}) <= 1
        if 1 < len(laps) <= 30 and not (auto and sp not in SWIM):
            ls = []
            for l in laps:
                if not l.get("distance"):  # vuelta de 0 m = descanso entre series
                    ls.append(f"(desc. {fmt_dur(l.get('elapsed_time') or l.get('moving_time'))})")
                    continue
                s = f"{l['distance']:.0f}m" if sp in SWIM else f"{l['distance']/1000:.2f}km"
                s += f" {fmt_dur(l.get('moving_time'))}"
                s += f" {fmt_pace(l.get('average_speed'), sp)}"
                if l.get("average_heartrate"):
                    s += f" FC{l['average_heartrate']:.0f}"
                ls.append(s)
            lines.append("  - Vueltas: " + " | ".join(ls))
    if not recent:
        lines.append("Sin actividades.")
    return "\n".join(lines)


def section_plan(athlete_id, today):
    """Objetivo, forma (VDOT) y cumplimiento del plan: la base del reajuste semanal."""
    import paces
    import plan_tool
    import views
    g = db.active_goal(athlete_id)
    plan = db.active_plan(athlete_id)
    if not g or not plan:
        return "## 0. Objetivo y plan\nNo hay plan activo en la app."
    v = db.current_vdot(athlete_id)
    pz = plan_tool.current_paces(athlete_id)
    days = (date.fromisoformat(g["race_date"]) - today).days
    pred = paces.predict_time(v["vdot"], g["distance_m"])
    need = paces.vdot_from_race(g["distance_m"], g["target_time_s"]) if g["target_time_s"] else None
    lines = ["## 0. Objetivo y plan (app)",
             f"- **{g['name']}** ({g['distance_m']/1000:g} km) el {g['race_date']} → faltan {days} días.",
             f"- Objetivo: {paces.fmt_time(g['target_time_s']) if g['target_time_s'] else '–'}"
             + (f" (VDOT necesario {need:.1f})" if need else "") + ".",
             f"- Forma actual: VDOT **{v['vdot']:.1f}** ({v['source']}) → predicción {paces.fmt_time(pred)}.",
             "- Historial VDOT: " + "; ".join(f"{r['set_on']} {r['vdot']:.1f}" for r in db.vdot_history(athlete_id)) + ".",
             "- Ritmos actuales: " + " · ".join(f"{c} {pz[c]['text']}" for c in ("E", "M", "T", "I", "R", "CUR", "RP") if c in pz) + ".",
             "- Plan: `data/plans/*.json` (fuente), importado con `app/plan_tool.py import`.", ""]
    rows = db.plan_sessions(plan["id"], (today - timedelta(days=14)).isoformat(), (today + timedelta(days=7)).isoformat())
    acts = db.activities_between(athlete_id, (today - timedelta(days=15)).isoformat(), (today + timedelta(days=8)).isoformat())
    st = views.match_sessions(rows, acts, today)
    past = [r for r in rows if r["date"] < today.isoformat()]
    if past:
        counted = [r for r in past if r["sport"] != "rest"]
        done = sum(1 for r in counted if st[r["id"]][0] == "done")
        key_done = sum(1 for r in counted if r["key_session"] and st[r["id"]][0] in ("done", "partial"))
        key_all = sum(1 for r in counted if r["key_session"])
        lines += [f"**Cumplimiento últimos 14 días:** {done}/{len(counted)} sesiones hechas completas; "
                  f"sesiones clave hechas {key_done}/{key_all}.", ""]
        for r in past:
            s = json.loads(r["session"])
            stt, lab, a, det = st[r["id"]]
            real = ""
            if a:
                real = (f" → real: {a['name']} {((a['distance_m'] or 0)/1000):.1f}km {fmt_dur(a['moving_time_s'])}"
                        f" {fmt_pace(a['average_speed'], a['sport_type']) if a['distance_m'] else ''}"
                        f" FC {a['average_heartrate'] or 0:.0f}")
            lines.append(f"- {r['date']} {r['sport']}{' (CLAVE)' if r['key_session'] else ''} «{s.get('title','')}» "
                         f"[{s.get('intensity') or '-'}]: {lab}{real}{(' — ' + det) if det else ''}")
        lines.append("")
    nxt = [r for r in rows if r["date"] >= today.isoformat()]
    if nxt:
        lines.append("**Próximos 7 días (plan):** " + " · ".join(
            f"{r['date'][5:]} {r['sport']} {json.loads(r['session']).get('title','')}" for r in nxt))
    return "\n".join(lines)


def build(athlete_id, today=None):
    today = today or date.today()
    acts = load_activities(athlete_id)
    zones, zsrc = enrich.hr_zones_for(athlete_id)
    athlete = db.get_athlete(athlete_id)
    head = (f"# Resumen de entrenamiento para el entrenador — {athlete['firstname']} {athlete['lastname']}\n\n"
            f"_Generado automáticamente por `app/coach_summary.py` el {datetime.now():%Y-%m-%d %H:%M} a partir de "
            f"`app/app.db` (Strava: detalle, streams y métricas calculadas). No editar a mano._")
    parts = [head,
             section_plan(athlete_id, today),
             section_coverage(acts, zones, zsrc, today),
             section_load(acts, zones, today),
             section_weeks(acts, zones, today),
             section_trends(acts, today),
             section_best(acts, today),
             section_recent(acts, zones, today)]
    return "\n\n".join(parts) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--athlete", type=int, help="id de atleta (por defecto, el único que haya)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()
    athletes = db.all_athletes()
    aid = args.athlete or (athletes[0]["id"] if len(athletes) == 1 else None)
    if not aid:
        raise SystemExit("Hay varios atletas: indica --athlete ID")
    Path(args.out).write_text(build(aid), encoding="utf-8")
    print(f"Escrito {args.out}")


if __name__ == "__main__":
    main()
