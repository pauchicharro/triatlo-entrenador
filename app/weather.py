"""Previsión del tiempo para planificar la semana (Open-Meteo, gratis y sin clave).

Escribe data/weather.md con la previsión diaria (hasta 16 días) para la ciudad
donde entrena el atleta, más avisos para correr: nieve, hielo (lluvia con
temperaturas bajo cero), frío fuerte, viento y calor. Lo leen el ajuste
semanal y el chat del entrenador.

Uso:  python3 app/weather.py [--days 10]
"""

import argparse
import json
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "weather.md"
CITY, LAT, LON, TZ = "Múnich", 48.137, 11.575, "Europe/Berlin"

# Códigos WMO → texto corto
WMO = {0: "despejado", 1: "casi despejado", 2: "nubes y claros", 3: "nublado", 45: "niebla", 48: "niebla con escarcha",
       51: "llovizna débil", 53: "llovizna", 55: "llovizna fuerte", 56: "llovizna helada", 57: "llovizna helada fuerte",
       61: "lluvia débil", 63: "lluvia", 65: "lluvia fuerte", 66: "lluvia helada", 67: "lluvia helada fuerte",
       71: "nieve débil", 73: "nieve", 75: "nieve fuerte", 77: "granos de nieve", 80: "chubascos débiles",
       81: "chubascos", 82: "chubascos fuertes", 85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
       95: "tormenta", 96: "tormenta con granizo", 99: "tormenta con granizo fuerte"}
DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def fetch(days):
    vars_ = ("weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_min,precipitation_sum,"
             "snowfall_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max")
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily={vars_}"
           f"&timezone={TZ.replace('/', '%2F')}&forecast_days={days}")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)["daily"]


def warnings(d, i, prev_snow):
    w = []
    code, tmin, tmax = d["weather_code"][i], d["temperature_2m_min"][i], d["temperature_2m_max"][i]
    snow, rain, wind = d["snowfall_sum"][i] or 0, d["precipitation_sum"][i] or 0, d["wind_gusts_10m_max"][i] or 0
    feels = d["apparent_temperature_min"][i]
    if snow >= 5:
        w.append(f"❄️ NIEVE {snow:.0f} cm: no hacer series fuera (cinta o mover)")
    elif snow >= 1:
        w.append(f"❄️ nieve {snow:.0f} cm: suelo resbaladizo")
    if code in (56, 57, 66, 67) or (rain >= 1 and tmin <= 0):
        w.append("🧊 riesgo de HIELO")
    elif prev_snow >= 3 and tmax <= 1:
        w.append("🧊 nieve del día anterior sin derretir (hielo/nieve pisada)")
    if feels is not None and feels <= -10:
        w.append(f"🥶 sensación {feels:.0f} °C")
    if wind >= 50:
        w.append(f"💨 rachas {wind:.0f} km/h")
    if tmax >= 27:
        w.append(f"🔥 {tmax:.0f} °C: correr temprano")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    args = ap.parse_args()
    d = fetch(args.days)
    lines = [f"# Previsión del tiempo — {CITY}",
             f"_Open-Meteo, generado {datetime.now():%Y-%m-%d %H:%M}. No editar a mano (`app/weather.py`)._", "",
             "Fiabilidad: buena a 3 días, orientativa a 5-7, poco fiable más allá. "
             "Si un día dice NIEVE o HIELO, las series y el umbral van en cinta o se mueven a otro día; "
             "los rodajes suaves se pueden hacer con cuidado (zapatilla con agarre, más lento, por FC).", ""]
    prev_snow = 0
    for i, day in enumerate(d["time"]):
        dt = date.fromisoformat(day)
        txt = WMO.get(d["weather_code"][i], f"código {d['weather_code'][i]}")
        line = (f"- **{DAYS[dt.weekday()]} {dt:%d/%m}**: {txt}, {d['temperature_2m_min'][i]:.0f}/{d['temperature_2m_max'][i]:.0f} °C"
                f" · precip. {d['precipitation_sum'][i] or 0:.1f} mm ({d['precipitation_probability_max'][i] or 0}%)"
                f" · nieve {d['snowfall_sum'][i] or 0:.1f} cm · rachas {d['wind_gusts_10m_max'][i] or 0:.0f} km/h")
        w = warnings(d, i, prev_snow)
        if w:
            line += " → " + "; ".join(w)
        lines.append(line)
        prev_snow = d["snowfall_sum"][i] or 0
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[5:]))


if __name__ == "__main__":
    main()
