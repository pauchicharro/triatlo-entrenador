"""Ritmos de entrenamiento y predicciones de carrera (modelo VDOT de Jack Daniels).

El plan (lo genere Claude Code o, más adelante, la API) NO lleva ritmos fijos:
cada bloque dice a qué intensidad va (E, M, T, I, R, RP…) y esta parte los
convierte en min/km a partir del VDOT actual del atleta. Así, cuando el
atleta mejora (p. ej. tras un test de 5 km), todos los ritmos futuros del
plan se actualizan solos.

Fórmulas (Daniels & Gilbert, 1979):
  VO2(v)      = -4.60 + 0.182258·v + 0.000104·v²          (v en m/min)
  %VO2max(t)  = 0.8 + 0.1894393·e^(-0.012778·t) + 0.2989558·e^(-0.1932605·t)   (t en min)
  VDOT        = VO2(v) / %VO2max(t)
"""

import math

# Intensidades de Daniels como % del VDOT (rango bajo-alto)
INTENSITIES = {
    "E": ("Suave", (0.62, 0.70), "Rodaje cómodo, conversacional. La base de todo."),
    "M": ("Maratón", (0.80, 0.82), "Ritmo sostenido, cómodo-exigente."),
    "T": ("Umbral", (0.87, 0.89), "Duro pero controlado: podrías aguantarlo ~1 h. Mejora la resistencia a la fatiga."),
    "I": ("Intervalos", (0.97, 1.00), "Series de 3-5 min a tope controlado. Sube el VO2máx."),
    "R": ("Repeticiones", (1.05, 1.08), "Rápido y corto (200-400 m) con recuperación completa. Economía y velocidad."),
}

# FC de referencia por intensidad (zonas de la prueba de esfuerzo; ver athlete_zones)
HR_HINT = {"E": "<140", "M": "140-150", "T": "160-173", "I": ">175", "R": "no mirar FC", "RP": "170-180", "CUR": "170-180"}


def vo2(v):
    return -4.60 + 0.182258 * v + 0.000104 * v * v


def pct_max(t):
    return 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)


def vdot_from_race(dist_m, secs):
    t = secs / 60
    return vo2(dist_m / t) / pct_max(t)


def velocity_for_vo2(target):
    """Invierte VO2(v): devuelve v (m/min)."""
    a, b, c = 0.000104, 0.182258, -4.60 - target
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def pace_s_per_km(vdot, pct):
    return 1000 / velocity_for_vo2(vdot * pct) * 60


def predict_time(vdot, dist_m):
    """Tiempo (s) para una distancia con ese VDOT (búsqueda binaria)."""
    lo, hi = 60.0, 6 * 3600.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if vdot_from_race(dist_m, mid) > vdot:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def vdot_from_threshold_pace(s_per_km):
    """VDOT cuyo ritmo T (88 %) coincide con un ritmo de umbral medido en laboratorio."""
    v = 1000 / s_per_km * 60
    return vo2(v) / 0.88


def fmt(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def fmt_time(s):
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def zone_paces(vdot, goal_time_s=None, goal_dist_m=10000):
    """Diccionario {código: {name, lo, hi, text, hr, desc}} con los ritmos en s/km.

    Además de las de Daniels:
      CUR = ritmo de 10K que predice el VDOT actual
      RP  = ritmo objetivo de carrera (si hay tiempo objetivo)
    """
    out = {}
    for code, (name, (p_lo, p_hi), desc) in INTENSITIES.items():
        slow, fast = pace_s_per_km(vdot, p_lo), pace_s_per_km(vdot, p_hi)
        out[code] = {"name": name, "slow": slow, "fast": fast,
                     "text": f"{fmt(fast)}-{fmt(slow)}/km" if abs(slow - fast) >= 3 else f"{fmt(fast)}/km",
                     "hr": HR_HINT[code], "desc": desc}
    cur = predict_time(vdot, goal_dist_m) / (goal_dist_m / 1000)
    out["CUR"] = {"name": "Ritmo 10K actual", "slow": cur, "fast": cur, "text": f"{fmt(cur)}/km",
                  "hr": HR_HINT["CUR"], "desc": "El ritmo al que hoy podrías correr un 10K a tope."}
    if goal_time_s:
        rp = goal_time_s / (goal_dist_m / 1000)
        out["RP"] = {"name": "Ritmo objetivo", "slow": rp, "fast": rp, "text": f"{fmt(rp)}/km",
                     "hr": HR_HINT["RP"], "desc": "El ritmo de tu tiempo objetivo en carrera."}
    return out


def render_text(text, paces):
    """Sustituye {E}, {T}, {RP}… en el texto de una sesión por el ritmo real."""
    for code, p in paces.items():
        text = text.replace("{" + code + "}", p["text"])
    return text
