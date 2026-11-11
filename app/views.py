"""Páginas HTML de la app: estilos comunes y vista de detalle de actividad."""

import json
import zlib
from html import escape

import db
import enrich

RUN = enrich.RUN
RIDE = enrich.RIDE
SWIM = ("Swim",)

CSS = """
:root{color-scheme:light;
 --page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
 --grid:#e1e0d9;--axis:#c3c2b7;--border:rgba(11,11,11,.10);--accent:#fc4c02;--line:#2a78d6;
 --z1:#86b6ef;--z2:#5598e7;--z3:#2a78d6;--z4:#1c5cab;--z5:#104281;--zt1:#0b0b0b;--zt2:#fff;--zt3:#fff;--zt4:#fff;--zt5:#fff;--good:#006300;--bad:#d03b3b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
 --grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--line:#3987e5;
 --z1:#184f95;--z2:#1c5cab;--z3:#2a78d6;--z4:#5598e7;--z5:#9ec5f4;--zt1:#fff;--zt2:#fff;--zt3:#fff;--zt4:#0b0b0b;--zt5:#0b0b0b;--good:#0ca30c;--bad:#e66767}}
:root[data-theme="dark"]{color-scheme:dark;
 --page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
 --grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--line:#3987e5;
 --z1:#184f95;--z2:#1c5cab;--z3:#2a78d6;--z4:#5598e7;--z5:#9ec5f4;--zt1:#fff;--zt2:#fff;--zt3:#fff;--zt4:#0b0b0b;--zt5:#0b0b0b;--good:#0ca30c;--bad:#e66767}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--page);color:var(--ink);
 max-width:900px;margin:0 auto;padding:1.5rem 16px 4rem;line-height:1.45}
a{color:var(--line)} h1{font-size:1.6rem;margin:.2rem 0} h2{font-size:1.15rem;margin:2rem 0 .3rem}
.muted{color:var(--muted)} .ink2{color:var(--ink2)} .err{color:var(--bad)}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:.8rem 1.2rem;border-radius:6px;text-decoration:none;font-weight:600}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem;margin:.6rem 0}
.explain{color:var(--ink2);font-size:.9rem;margin:.2rem 0 .6rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.6rem}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:.7rem .8rem}
.tile .v{font-size:1.35rem;font-weight:600} .tile .l{font-size:.8rem;color:var(--ink2)}
.tile .h{font-size:.75rem;color:var(--muted);margin-top:.2rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}
td,th{padding:.35rem .5rem;border-bottom:1px solid var(--grid);text-align:left;white-space:nowrap}
th{color:var(--ink2);font-weight:600}
tr.click{cursor:pointer} tr.click:hover{background:var(--surface)}
.zbar{display:flex;height:28px;gap:2px;border-radius:4px;overflow:hidden;margin:.4rem 0}
.zbar div{display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:600;min-width:0;overflow:hidden}
.sw{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;vertical-align:-1px;margin-right:.35rem}
.metric{display:grid;grid-template-columns:9rem 1fr;gap:.2rem 1rem;padding:.6rem 0;border-bottom:1px solid var(--grid)}
.metric:last-child{border-bottom:0}
.metric .v{font-size:1.2rem;font-weight:600} .metric .n{font-weight:600}
.verdict{font-size:.85rem;font-weight:600}
@media (max-width:560px){.metric{grid-template-columns:1fr}}
.chart{position:relative;margin:.2rem 0 .8rem}
.chart .t{font-size:.85rem;font-weight:600;margin-bottom:.1rem}
.chart svg{display:block;width:100%;height:140px;touch-action:none}
#readout{position:sticky;top:0;z-index:2;background:var(--surface);border:1px solid var(--border);
 border-radius:8px;padding:.4rem .7rem;font-size:.85rem;font-variant-numeric:tabular-nums;min-height:2.1rem}
details{margin:.4rem 0} summary{cursor:pointer;color:var(--ink2)}
code{font-size:.85em}
"""


def page(body, title="Entrenador de triatlón", head=""):
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style>{head}</head><body>{body}</body></html>"""


# ----------------------------------------------------------------- formateo

def fmt_dur(s):
    if s is None:
        return "–"
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_pace(speed_ms, sport):
    """Ritmo legible según deporte: min/km (correr), min/100 m (nadar), km/h (bici)."""
    if not speed_ms:
        return "–"
    if sport in SWIM:
        return f"{fmt_dur(100 / speed_ms)} /100m"
    if sport in RUN or sport in ("Walk", "Hike"):
        return f"{fmt_dur(1000 / speed_ms)} /km"
    return f"{speed_ms * 3.6:.1f} km/h"


def fmt_dist(m, sport):
    if not m:
        return "–"
    return f"{m:.0f} m" if sport in SWIM else f"{m / 1000:.2f} km"


SPORT_ES = {"Run": "Carrera", "TrailRun": "Trail", "Ride": "Bici", "VirtualRide": "Rodillo",
            "GravelRide": "Gravel", "MountainBikeRide": "BTT", "Swim": "Natación",
            "WeightTraining": "Gimnasio", "Workout": "Entreno", "Hike": "Excursión",
            "Walk": "Caminar", "AlpineSki": "Esquí", "Yoga": "Yoga",
            "HighIntensityIntervalTraining": "HIIT", "Tennis": "Tenis", "NordicSki": "Esquí nórdico",
            "BackcountrySki": "Esquí de travesía", "Rowing": "Remo", "Elliptical": "Elíptica"}


def sport_es(s):
    return SPORT_ES.get(s, s or "?")


# ------------------------------------------------------------ explicaciones

def _verdict(text, good):
    color = "var(--good)" if good else "var(--bad)" if good is False else "var(--ink2)"
    icon = "✓" if good else "!" if good is False else "·"
    return f'<div class="verdict" style="color:{color}">{icon} {escape(text)}</div>'


def metrics_block(m, sport):
    """Cada métrica con: valor, qué es, y cómo leerla en esta actividad."""
    rows = []

    def add(name, value, what, verdict=""):
        rows.append(f'<div class="metric"><div><div class="n">{name}</div><div class="v">{value}</div></div>'
                    f'<div><div class="explain" style="margin:0">{what}</div>{verdict}</div></div>')

    if m.get("trimp_edwards") is not None:
        t = m["trimp_edwards"]
        level = "suave" if t < 50 else "moderada" if t < 120 else "alta" if t < 250 else "muy alta"
        add("Carga (TRIMP)", f"{t:.0f}",
            "Cuánto «pesa» la sesión para el cuerpo. Suma los minutos en cada zona multiplicados por "
            "el nº de zona (1 min en Z4 cuenta como 4 en Z1). Sumando las de la semana se ve si la carga "
            "sube demasiado rápido.", _verdict(f"Carga {level}", None))
    if m.get("decoupling_pct") is not None:
        d = m["decoupling_pct"]
        if d < -5:
            good, txt = None, ("Negativo: la 2ª mitad te salió más «barata» que la 1ª. Suele ser por el terreno "
                               "(más bajada al final), un calentamiento largo o un ritmo progresivo; no indica fatiga.")
        elif d < 5:
            good, txt = True, "Menos del 5 %: base aeróbica sólida para esta duración"
        else:
            good, txt = False, "Más del 5 %: hubo deriva (cansancio, calor, deshidratación o terreno/series)"
        add("Desacople aeróbico", f"{d:+.1f} %",
            "Compara cuánto ritmo sacas por pulsación en la 1ª mitad frente a la 2ª. Si en la 2ª mitad "
            "la FC sube para el mismo ritmo (deriva cardíaca), el número es positivo. Solo tiene sentido "
            "en esfuerzos constantes de más de 20 min; con cuestas o series varía por el terreno.",
            _verdict(txt, good))
    if m.get("efficiency_factor") is not None:
        unit = "W por pulsación" if (m.get("watts_np") and sport in RIDE) else "metros/min por pulsación"
        add("Factor de eficiencia", f"{m['efficiency_factor']:.2f}",
            f"Rendimiento por latido ({unit}). No se juzga solo: hay que compararlo entre sesiones "
            "parecidas. Si sube con el tiempo a la misma FC, estás mejorando la forma aeróbica.")
    if m.get("hr_max_60s") is not None:
        add("FC máx. sostenida 60 s", f"{m['hr_max_60s']:.0f} ppm",
            "La FC media más alta que mantuviste durante un minuto entero. Es más fiable que la FC "
            "máxima puntual, que muchas veces es un pico falso del sensor."
            + (f" (Máximo puntual registrado: {m['hr_max']} ppm.)" if m.get("hr_max") else ""))
    if m.get("cadence_avg") is not None:
        c = m["cadence_avg"]
        if sport in RUN:
            add("Cadencia media", f"{c:.0f} pasos/min",
                "Pasos por minuto contando las dos piernas. Una cadencia alta (≈170-185) suele ir con "
                "una zancada más eficiente y menos impacto.",
                _verdict("Buena cadencia" if c >= 168 else "Algo baja: podrías acortar la zancada", c >= 168))
        elif sport in SWIM:
            add("Frecuencia de brazada", f"{c:.0f} brazadas/min",
                "Brazadas por minuto que contó el reloj. Comparada entre sesiones al mismo ritmo, "
                "menos brazadas = más deslizamiento y mejor técnica.")
        elif sport in RIDE:
            add("Cadencia media", f"{c:.0f} rpm", "Pedaladas por minuto. En llano, 80-95 rpm suele ser lo más eficiente.")
    if m.get("watts_np") is not None:
        add("Potencia normalizada", f"{m['watts_np']:.0f} W" + (" (potencia de carrera del Garmin)" if sport in RUN else ""),
            "Los vatios que «equivalen» a lo que te costó la salida, teniendo en cuenta los cambios de "
            f"ritmo. Potencia media real: {m.get('watts_avg', 0):.0f} W.")
    if m.get("temp_avg") is not None:
        add("Temperatura media", f"{m['temp_avg']:.0f} °C",
            "Medida por el reloj (en la muñeca suele marcar algo de más). El calor sube la FC y el desacople.")
    if not rows:
        return '<p class="muted">Sin métricas: esta actividad no tiene datos segundo a segundo (o no llevaba pulsómetro).</p>'
    return '<div class="card">' + "".join(rows) + "</div>"


def zones_block(m, zones, source, sport=None):
    secs = m.get("hr_zone_s")
    if not secs or not sum(secs):
        return '<p class="muted">Sin datos de frecuencia cardíaca en esta actividad.</p>'
    total = sum(secs)
    names = ["Z1 Regenerativa", "Z2 Aeróbica suave", "Z3 Aeróbica media", "Z4 Tempo / umbral", "Z5 Por encima de umbral"]
    bar = "".join(
        f'<div style="flex:{s};background:var(--z{i+1});color:var(--zt{i+1})" title="{names[i]}: {fmt_dur(s)}">'
        f'{round(s/total*100) if s/total >= .08 else ""}{"%" if s/total >= .08 else ""}</div>'
        for i, s in enumerate(secs) if s > 0)
    rng = []
    for i, (lo, hi) in enumerate(zones or []):
        rng.append(f"&lt;{hi}" if i == 0 else f"≥{lo}" if hi >= 900 else f"{lo}-{hi - 1}")
    rows = "".join(
        f'<tr><td><span class="sw" style="background:var(--z{i+1})"></span>{names[i]}</td>'
        f'<td>{rng[i] if i < len(rng) else ""} ppm</td><td>{fmt_dur(s)}</td><td>{s/total*100:.0f} %</td></tr>'
        for i, s in enumerate(secs))
    note = (" <i>Ojo: son zonas de carrera; nadando o en bici la FC suele ir 5-15 ppm más baja al mismo "
            "esfuerzo, así que aquí la zona real es algo más alta de lo que marca.</i>") if sport and sport not in RUN else ""
    src = {"manuales": "tus zonas de la prueba de esfuerzo", "strava": "tus zonas configuradas en Strava"}.get(
        source or "", source or "")
    return f"""<p class="explain">Cuánto tiempo pasaste en cada intensidad, según {escape(src)}.
La mayoría del entrenamiento de resistencia debería ir en Z1-Z2; Z4-Z5 son los días de calidad.{note}</p>
<div class="zbar" role="img" aria-label="Distribución por zonas">{bar}</div>
<div class="scroll"><table><tr><th>Zona</th><th>FC</th><th>Tiempo</th><th>%</th></tr>{rows}</table></div>"""


def laps_block(laps, sport):
    if not laps or len(laps) < 2:
        return ""
    has_hr = any(l.get("average_heartrate") for l in laps)
    has_cad = any(l.get("average_cadence") for l in laps) and sport not in SWIM
    mult = 2 if sport in RUN else 1
    head = ("<tr><th>#</th><th>Distancia</th><th>Tiempo</th><th>Ritmo</th>"
            + ("<th>FC media</th><th>FC máx</th>" if has_hr else "")
            + ("<th>Cadencia</th>" if has_cad else "") + "<th>Desnivel</th></tr>")
    rows = ""
    for i, l in enumerate(laps, 1):
        rows += (f"<tr><td>{i}</td><td>{fmt_dist(l.get('distance'), sport)}</td>"
                 f"<td>{fmt_dur(l.get('moving_time'))}</td><td>{fmt_pace(l.get('average_speed'), sport)}</td>"
                 + (f"<td>{round(l['average_heartrate']) if l.get('average_heartrate') else '–'}</td>"
                    f"<td>{round(l['max_heartrate']) if l.get('max_heartrate') else '–'}</td>" if has_hr else "")
                 + (f"<td>{round((l.get('average_cadence') or 0) * mult) or '–'}</td>" if has_cad else "")
                 + f"<td>{l.get('total_elevation_gain') or 0:.0f} m</td></tr>")
    what = ("Cada «vuelta» es un tramo que el reloj separó: por botón (series), por distancia automática "
            "o, en natación, por intervalo. Aquí se ve si mantuviste el ritmo o si fuiste cayendo.")
    return f'<h2>Vueltas / series ({len(laps)})</h2><p class="explain">{what}</p><div class="scroll"><table>{head}{rows}</table></div>'


def splits_block(splits, sport):
    if sport not in RUN or not splits or len(splits) < 2:
        return ""
    rows = "".join(
        f"<tr><td>{s.get('split')}</td><td>{fmt_dur(s.get('moving_time'))}</td>"
        f"<td>{fmt_pace(s.get('average_speed'), sport)}</td>"
        f"<td>{round(s['average_heartrate']) if s.get('average_heartrate') else '–'}</td>"
        f"<td>{s.get('elevation_difference') or 0:+.0f} m</td></tr>" for s in splits)
    return (f'<h2>Parciales por kilómetro</h2><p class="explain">Lo que tardaste en cada km. Útil para ver si '
            f'empezaste demasiado rápido o si acabaste fuerte (parciales negativos).</p>'
            f'<div class="scroll"><table><tr><th>Km</th><th>Tiempo</th><th>Ritmo</th><th>FC</th><th>Desnivel</th></tr>{rows}</table></div>')


def best_block(best, sport):
    if not best:
        return ""
    def rank(b):
        r = b.get("pr_rank")
        return "🏅 Récord personal" if r == 1 else f"{r}º mejor de siempre" if r else ""
    rows = "".join(
        f"<tr><td>{escape(b.get('name',''))}</td><td>{fmt_dur(b.get('moving_time'))}</td>"
        f"<td>{fmt_pace(b['distance']/b['moving_time'] if b.get('moving_time') else None, sport)}</td>"
        f"<td>{rank(b)}</td></tr>"
        for b in best)
    return (f'<h2>Mejores esfuerzos</h2><p class="explain">El tramo más rápido de cada distancia dentro de esta '
            f'actividad (no tiene por qué ser el principio). Sirven para seguir tu forma sin hacer un test.</p>'
            f'<div class="scroll"><table><tr><th>Distancia</th><th>Tiempo</th><th>Ritmo</th><th></th></tr>{rows}</table></div>')


# ------------------------------------------------------------------ gráficas

def chart_series(streams, sport, max_points=700):
    """Reduce las series a ~700 puntos y las prepara para dibujarlas en el navegador."""
    if not streams or "time" not in streams:
        return None
    t = streams["time"]["data"]
    n = len(t)
    step = max(1, n // max_points)
    idx = list(range(0, n, step))
    dist = streams.get("distance", {}).get("data")
    out = {"t": [t[i] for i in idx], "d": [round(dist[i]) for i in idx] if dist else None, "series": []}

    def pick(key, smooth=0):
        d = streams.get(key, {}).get("data")
        if not d:
            return None
        if smooth:  # media móvil centrada de `smooth` muestras, para quitar el ruido del GPS/sensor
            h, out_, acc, cnt = smooth // 2, [], 0.0, 0
            vals = [x if x is not None else 0 for x in d]
            pref = [0.0]
            for x in vals:
                pref.append(pref[-1] + x)
            for i in idx:
                a_, b_ = max(0, i - h), min(len(vals), i + h + 1)
                out_.append((pref[b_] - pref[a_]) / (b_ - a_))
            return out_
        return [d[i] for i in idx]

    hr = pick("heartrate")
    if hr:
        out["series"].append({"key": "hr", "name": "Frecuencia cardíaca", "unit": "ppm", "data": hr,
                              "help": "Las bandas de fondo son tus zonas."})
    v = pick("velocity_smooth", 30)
    if v and sport not in SWIM:
        if sport in RUN or sport in ("Walk", "Hike"):
            pace = [round(1000 / x / 60, 3) if x and x > 1000 / 60 / 15 else None for x in v]  # descarta >15 min/km
            out["series"].append({"key": "pace", "name": "Ritmo", "unit": "min/km", "data": pace,
                                  "invert": True, "fmt": "pace", "help": "Más arriba = más rápido. Suavizado 30 s."})
        else:
            out["series"].append({"key": "speed", "name": "Velocidad", "unit": "km/h",
                                  "data": [round(x * 3.6, 1) if x is not None else None for x in v]})
    alt = pick("altitude")
    if alt and sport not in SWIM:
        out["series"].append({"key": "alt", "name": "Altitud", "unit": "m", "data": alt})
    cad = pick("cadence", 30)
    if cad and sport not in SWIM and any(cad):  # en natación la cadencia del stream no es útil
        mult = 2 if sport in RUN else 1
        out["series"].append({"key": "cad", "name": "Cadencia", "unit": "pasos/min" if mult == 2 else "rpm",
                              "data": [round(c * mult, 1) if c else None for c in cad],
                              "help": "Suavizada 30 s."})
    w = pick("watts", 30)
    if w and any(w):
        out["series"].append({"key": "w", "name": "Potencia", "unit": "W", "data": w,
                              "help": "Si no llevas potenciómetro, es una estimación de Strava (poco fiable)."})
    return out if out["series"] else None


CHART_JS = r"""
(function(){
const D = JSON.parse(document.getElementById('series-data').textContent);
const Z = JSON.parse(document.getElementById('zones-data').textContent);
const root = document.getElementById('charts'), readout = document.getElementById('readout');
const fmtT = s => { s=Math.round(s); const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=s%60;
  return (h? h+':'+String(m).padStart(2,'0') : m)+':'+String(x).padStart(2,'0'); };
const fmtPace = v => { if(v==null) return '–'; const m=Math.floor(v), s=Math.round((v-m)*60); return m+':'+String(s).padStart(2,'0'); };
const fmtV = (s,v) => v==null ? '–' : s.fmt==='pace' ? fmtPace(v) : (Math.abs(v)>=100? Math.round(v) : Math.round(v*10)/10);
const X = D.t, W = 900, H = 140, PL = 44, PR = 8, PT = 8, PB = 20;
const xmax = X[X.length-1] || 1;
const xs = t => PL + (t / xmax) * (W-PL-PR);
const charts = [];
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs, parent) => { const e=document.createElementNS(NS,tag); for(const k in attrs) e.setAttribute(k,attrs[k]); if(parent) parent.appendChild(e); return e; };

function niceTicks(lo, hi, n){ const span=hi-lo||1, step0=span/n, mag=Math.pow(10,Math.floor(Math.log10(step0)));
  const step=[1,2,2.5,5,10].map(f=>f*mag).find(s=>s>=step0); const out=[]; for(let v=Math.ceil(lo/step)*step; v<=hi+1e-9; v+=step) out.push(+v.toFixed(6)); return out; }

D.series.forEach(s => {
  const vals = s.data.filter(v => v!=null);
  if (!vals.length) return;
  const sorted = [...vals].sort((a,b)=>a-b);
  // recorta el 1 % extremo para que un pico del sensor no aplaste la gráfica
  let lo = sorted[Math.floor(sorted.length*0.01)], hi = sorted[Math.ceil(sorted.length*0.99)-1];
  if (s.key==='hr' && Z) { lo = Math.min(lo, Z[1][0]-5); }
  const pad=(hi-lo)*0.08||1; lo-=pad; hi+=pad;
  const ys = v => s.invert ? PT + (v-lo)/(hi-lo)*(H-PT-PB) : H-PB - (v-lo)/(hi-lo)*(H-PT-PB);
  const wrap = document.createElement('div'); wrap.className='chart';
  wrap.innerHTML = '<div class="t">'+s.name+' <span class="muted" style="font-weight:400">('+s.unit+')'+(s.help? ' · '+s.help:'')+'</span></div>';
  const svg = el('svg', {viewBox:`0 0 ${W} ${H}`, preserveAspectRatio:'none', role:'img', 'aria-label':s.name});
  wrap.appendChild(svg); root.appendChild(wrap);
  if (s.key==='hr' && Z) Z.forEach((z,i) => { const a=Math.max(z[0],lo), b=Math.min(z[1],hi); if (b<=a) return;
     el('rect',{x:PL,width:W-PL-PR,y:Math.min(ys(a),ys(b)),height:Math.abs(ys(b)-ys(a)),fill:`var(--z${i+1})`,opacity:.18},svg); });
  niceTicks(lo,hi,3).forEach(v => { el('line',{x1:PL,x2:W-PR,y1:ys(v),y2:ys(v),stroke:'var(--grid)','stroke-width':1,'vector-effect':'non-scaling-stroke'},svg);
     const tx=el('text',{x:PL-6,y:ys(v)+4,'text-anchor':'end','font-size':11,fill:'var(--muted)'},svg); tx.textContent=fmtV(s,v); });
  niceTicks(0,xmax/60,6).forEach(m => { const tx=el('text',{x:xs(m*60),y:H-5,'text-anchor':'middle','font-size':11,fill:'var(--muted)'},svg); tx.textContent=m+"'"; });
  let d='', pen=false;
  s.data.forEach((v,i) => { if (v==null || (i && X[i]-X[i-1] > 120)) { pen=false; if (v==null) return; }
     const vv=Math.max(lo,Math.min(hi,v)); d += (pen?'L':'M')+xs(X[i]).toFixed(1)+','+ys(vv).toFixed(1); pen=true; });
  el('path',{d, fill:'none', stroke:'var(--line)','stroke-width':2,'vector-effect':'non-scaling-stroke','stroke-linejoin':'round'},svg);
  const cross = el('line',{y1:PT,y2:H-PB,stroke:'var(--ink2)','stroke-width':1,'vector-effect':'non-scaling-stroke',visibility:'hidden'},svg);
  const dot = el('circle',{r:4,fill:'var(--line)',stroke:'var(--surface)','stroke-width':2,visibility:'hidden'},svg);
  charts.push({s, svg, cross, dot, ys, lo, hi});
});

function show(i){
  const parts = ['<b>'+fmtT(X[i])+'</b>' + (D.d? ' · '+(D.d[i]/1000).toFixed(2)+' km':'')];
  charts.forEach(c => { const v=c.s.data[i]; const x=xs(X[i]);
    c.cross.setAttribute('x1',x); c.cross.setAttribute('x2',x); c.cross.setAttribute('visibility','visible');
    if (v!=null){ c.dot.setAttribute('cx',x); c.dot.setAttribute('cy',c.ys(Math.max(c.lo,Math.min(c.hi,v)))); c.dot.setAttribute('visibility','visible'); }
    else c.dot.setAttribute('visibility','hidden');
    parts.push(c.s.name+': <b>'+fmtV(c.s,v)+'</b> '+c.s.unit); });
  readout.innerHTML = parts.join(' &nbsp;·&nbsp; ');
}
function hide(){ charts.forEach(c=>{c.cross.setAttribute('visibility','hidden'); c.dot.setAttribute('visibility','hidden');});
  readout.innerHTML='<span class="muted">Pasa el dedo o el ratón por las gráficas para ver los valores en cada momento.</span>'; }
charts.forEach(c => {
  const move = ev => { const r=c.svg.getBoundingClientRect(); const px=(ev.clientX-r.left)/r.width*W;
    const t=(px-PL)/(W-PL-PR)*xmax; let lo=0, hi=X.length-1; while(hi-lo>1){const m=(lo+hi)>>1; if(X[m]<t) lo=m; else hi=m;}
    show(Math.abs(X[lo]-t)<Math.abs(X[hi]-t)?lo:hi); };
  c.svg.addEventListener('pointermove', move); c.svg.addEventListener('pointerdown', move);
  c.svg.addEventListener('pointerleave', hide);
});
hide();
})();
"""


# ----------------------------------------------------------- página actividad

def activity_page(athlete_id, activity_id):
    a = db.get_activity_full(athlete_id, activity_id)
    if not a:
        return None
    sport = a["sport_type"]
    raw = json.loads(a["raw"] or "{}")
    m = json.loads(a["metrics"]) if a["metrics"] else {}
    zones, _ = enrich.hr_zones_for(athlete_id)

    def tile(label, value, hint=""):
        return (f'<div class="tile"><div class="l">{label}</div><div class="v">{value}</div>'
                + (f'<div class="h">{hint}</div>' if hint else "") + "</div>")

    tiles = [
        tile("Distancia", fmt_dist(a["distance_m"], sport)),
        tile("Tiempo en movimiento", fmt_dur(a["moving_time_s"]),
             f"Total con paradas: {fmt_dur(a['elapsed_time_s'])}" if a["elapsed_time_s"] else ""),
        tile("Ritmo medio" if sport in RUN + SWIM else "Velocidad media", fmt_pace(a["average_speed"], sport)),
    ]
    if a["average_heartrate"]:
        tiles.append(tile("FC media", f"{a['average_heartrate']:.0f} ppm",
                          f"Máx. puntual {a['max_heartrate']:.0f}" if a["max_heartrate"] else ""))
    if a["elevation_gain_m"] and sport not in SWIM:
        tiles.append(tile("Desnivel +", f"{a['elevation_gain_m']:.0f} m"))
    if a["calories"]:
        tiles.append(tile("Calorías", f"{a['calories']:.0f} kcal", "Estimadas por el reloj"))
    if a["perceived_exertion"]:
        tiles.append(tile("Esfuerzo percibido", f"{a['perceived_exertion']:.0f}/10", "Lo que apuntaste en Strava"))
    if a["suffer_score"]:
        tiles.append(tile("Esfuerzo relativo", f"{a['suffer_score']:.0f}", "Índice propio de Strava"))

    enriched = a["enrich_status"] is not None
    if not enriched:
        pending = ('<div class="card"><b>Detalle pendiente.</b> <span class="ink2">Esta actividad aún está en la cola '
                   'de descarga (Strava limita las llamadas, vamos de la más reciente a la más antigua). '
                   'De momento solo tenemos el resumen.</span></div>')
    else:
        pending = ""

    laps = json.loads(a["laps"]) if a["laps"] else []
    splits = json.loads(a["splits_metric"]) if a["splits_metric"] else []
    best = json.loads(a["best_efforts"]) if a["best_efforts"] else []
    streams = enrich.unpack(a["streams"]) if a["streams"] else None
    series = chart_series(streams, sport)

    charts_html, head = "", ""
    if series:
        charts_html = (
            '<h2>Segundo a segundo</h2><p class="explain">Lo que grabó el reloj durante la actividad. '
            'El eje horizontal son los minutos desde que empezaste (incluidas las paradas; donde paraste, la línea se corta).</p>'
            '<div id="readout"></div><div id="charts"></div>'
            f'<script type="application/json" id="series-data">{json.dumps(series)}</script>'
            f'<script type="application/json" id="zones-data">{json.dumps(zones)}</script>'
            f'<script>{CHART_JS}</script>')

    raw_keys = ""
    if streams:
        names = {"time": "tiempo", "distance": "distancia", "latlng": "posición GPS", "altitude": "altitud",
                 "velocity_smooth": "velocidad", "heartrate": "frecuencia cardíaca", "cadence": "cadencia",
                 "watts": "potencia", "temp": "temperatura", "moving": "en movimiento sí/no",
                 "grade_smooth": "pendiente"}
        n = len(streams.get("time", {}).get("data", []))
        keys = ", ".join(names.get(k, k) for k in streams)
        raw_keys = f"<p>Series segundo a segundo ({n} muestras cada una): {escape(keys)}.</p>"

    desc = f'<p class="ink2">“{escape(a["description"])}”</p>' if a["description"] else ""
    device = " · ".join(x for x in [a["device_name"], "rodillo/cinta" if a["trainer"] else None] if x)
    detail_keys = len(json.loads(zlib.decompress(a["detail"]))) if a["detail"] else 0

    body = f"""<p><a href="/">← Volver</a></p>
<div class="muted">{sport_es(sport)} · {(a['start_date_local'] or '')[:10]} {(a['start_date_local'] or '')[11:16]}{(' · ' + escape(device)) if device else ''}</div>
<h1>{escape(a['name'] or '')}</h1>{desc}
{pending}
<h2>Resumen</h2>
<div class="tiles">{''.join(tiles)}</div>
{('<h2>Zonas de frecuencia cardíaca</h2>' + zones_block(m, zones, a['zones_source'], sport)) if enriched else ''}
{('<h2>Métricas para el entrenador</h2><p class="explain">Calculadas aquí a partir de los datos segundo a segundo. '
  'Son las que usará el entrenador para decidir si vas cansado, si estás mejorando y cuánta carga llevas.</p>'
  + metrics_block(m, sport)) if enriched else ''}
{charts_html}
{laps_block(laps, sport)}
{splits_block(splits, sport)}
{best_block(best, sport)}
<h2>Qué hay guardado de esta actividad</h2>
<div class="card ink2" style="font-size:.9rem">
<p>Resumen de la lista de Strava: {len(raw)} campos.</p>
{f'<p>Detalle completo: {detail_keys} campos (vueltas, parciales, mejores esfuerzos, segmentos, material…).</p>' if detail_keys else '<p>Detalle completo: pendiente.</p>'}
{raw_keys or ('<p>Series segundo a segundo: no hay (actividad manual o sin sensores).</p>' if enriched else '')}
<p class="muted">Estado: {escape(a['enrich_status'] or 'pendiente de descarga')} · id Strava <a href="https://www.strava.com/activities/{a['id']}">{a['id']}</a></p>
</div>"""
    return page(body, title=a["name"] or "Actividad", head=head)


# ------------------------------------------------------------------- portada

DISC = [("swim", "Natación", "var(--c1)"), ("bike", "Bici", "var(--c2)"),
        ("run", "Carrera", "var(--c3)"), ("gym", "Gimnasio", "var(--c4)")]

HOME_CSS = """
:root{--c1:#2a78d6;--c2:#eb6834;--c3:#1baf7a;--c4:#eda100}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--c1:#3987e5;--c2:#d95926;--c3:#199e70;--c4:#c98500}}
:root[data-theme="dark"]{--c1:#3987e5;--c2:#d95926;--c3:#199e70;--c4:#c98500}
.legend{display:flex;flex-wrap:wrap;gap:.3rem 1rem;font-size:.85rem;color:var(--ink2);margin:.3rem 0}
.prog{height:8px;background:var(--grid);border-radius:4px;overflow:hidden;margin:.4rem 0}
.prog div{height:100%;background:var(--line)}
.mini{display:flex;height:10px;width:80px;gap:1px;border-radius:2px;overflow:hidden}
.filters{display:flex;flex-wrap:wrap;gap:.4rem;margin:.5rem 0}
.filters a{padding:.25rem .7rem;border:1px solid var(--border);border-radius:999px;text-decoration:none;color:var(--ink2);font-size:.85rem}
.filters a.on{background:var(--ink);color:var(--page)}
#wtip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--border);border-radius:6px;
 padding:.35rem .55rem;font-size:.8rem;display:none;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.12)}
"""


def weekly_chart(rows):
    from datetime import date, timedelta
    by = {}
    for r in rows:
        by.setdefault(r["week"], {})[r["disc"]] = r["hours"]
    if not by:
        return ""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    weeks = [(monday - timedelta(weeks=i)).isoformat() for i in range(25, -1, -1)]
    data = [{"w": w, **{k: round(by.get(w, {}).get(k, 0), 2) for k, _, _ in DISC}} for w in weeks]
    W, H, PL, PB, PT = 900, 200, 34, 22, 8
    tot = [sum(d[k] for k, _, _ in DISC) for d in data]
    ymax = max(max(tot), 1)
    ymax = (int(ymax) + 2) // 2 * 2
    bw = (W - PL) / len(data)
    ys = lambda h: H - PB - h / ymax * (H - PB - PT)
    svg = []
    for v in range(0, ymax + 1, max(1, ymax // 4)):
        svg.append(f'<line x1="{PL}" x2="{W}" y1="{ys(v):.1f}" y2="{ys(v):.1f}" stroke="var(--grid)"/>'
                   f'<text x="{PL-6}" y="{ys(v)+4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{v} h</text>')
    for i, d in enumerate(data):
        x = PL + i * bw + 3
        base = 0
        segs = [(k, d[k], c) for k, _, c in DISC if d[k] > 0]
        for j, (k, h, c) in enumerate(segs):
            y0, y1 = ys(base), ys(base + h)
            gap = 2 if j < len(segs) - 1 else 0  # separación de 2 px entre segmentos
            rx = 4 if j == len(segs) - 1 else 0
            svg.append(f'<rect x="{x:.1f}" y="{y1:.1f}" width="{bw-6:.1f}" height="{max(y0-y1-gap,0.5):.1f}" fill="{c}" rx="{rx}"/>')
            base += h
        if i % 4 == 1 or i == len(data) - 1:
            dd = d["w"]
            svg.append(f'<text x="{x + (bw-6)/2:.1f}" y="{H-6}" text-anchor="middle" font-size="11" fill="var(--muted)">{dd[8:10]}/{dd[5:7]}</text>')
        svg.append(f'<rect class="hit" data-i="{i}" x="{PL + i*bw:.1f}" y="{PT}" width="{bw:.1f}" height="{H-PB-PT}" fill="transparent"/>')
    legend = "".join(f'<span><span class="sw" style="background:{c}"></span>{n}</span>' for _, n, c in DISC)
    names = {k: n for k, n, _ in DISC}
    js = f"""<script>(function(){{const D={json.dumps(data)},N={json.dumps(names)};
const box=document.getElementById('wbox'),tip=document.getElementById('wtip');
const f=h=>{{const m=Math.round(h*60);return Math.floor(m/60)+'h '+String(m%60).padStart(2,'0')+'m'}};
box.querySelectorAll('.hit').forEach(r=>{{r.addEventListener('pointermove',e=>{{const d=D[+r.dataset.i];
let t=0,html='<b>Semana del '+d.w.slice(8,10)+'/'+d.w.slice(5,7)+'</b>';
for(const k in N){{t+=d[k];if(d[k]>0)html+='<br>'+N[k]+': '+f(d[k]);}}
tip.innerHTML=html+'<br><b>Total: '+f(t)+'</b>';tip.style.display='block';
const b=box.getBoundingClientRect();let x=e.clientX-b.left+12;if(x>b.width-160)x-=180;
tip.style.left=x+'px';tip.style.top=(e.clientY-b.top-10)+'px';}});
r.addEventListener('pointerleave',()=>tip.style.display='none');}});}})();</script>"""
    return (f'<h2>Horas por semana (últimos 6 meses)</h2><p class="explain">Tu volumen de entrenamiento '
            f'semana a semana (sin contar otros deportes como esquí, tenis o caminar). Es lo primero que mira un entrenador: si la carga sube de forma progresiva '
            f'o hay saltos bruscos que pueden acabar en lesión.</p>'
            f'<div class="legend">{legend}</div>'
            f'<div id="wbox" style="position:relative"><svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;display:block" '
            f'role="img" aria-label="Horas por semana y disciplina">{"".join(svg)}</svg><div id="wtip"></div></div>{js}')


def _local_hhmm(utc_text):
    """'2026-11-03 20:11:32' (UTC, de SQLite) → '21:11' en hora local."""
    from datetime import datetime, timezone
    if not utc_text:
        return "–"
    try:
        return datetime.fromisoformat(utc_text).replace(tzinfo=timezone.utc).astimezone().strftime("%H:%M")
    except ValueError:
        return utc_text[11:16]


def home_page(athlete, sport_filter=None, offset=0):
    from html import escape as e
    aid = athlete["id"]
    status = athlete["sync_status"]
    refresh = '<meta http-equiv="refresh" content="3">' if status == "syncing" else ""
    p = db.enrich_progress(aid)
    done, total = p["done"] or 0, p["total"] or 0
    pct = done / total * 100 if total else 0
    err = athlete["enrich_error"]

    sync_card = f"""<div class="card">
<div class="{'err' if status=='error' else 'ink2'}">Garmin: <b>{e(athlete['sync_message'] or status)}</b>
 · última sincronización {_local_hhmm(athlete['last_synced_at'])} (automática cada 15 min)
 · <a href="/sync">sincronizar ahora</a> · <a href="/logout">salir</a></div>
<div style="margin-top:.6rem"><b>Histórico de Strava: {done} de {total} actividades con detalle</b> ({pct:.0f} %)</div>
<div class="prog"><div style="width:{pct:.1f}%"></div></div>
<div class="explain">Las actividades nuevas llegan de Garmin con todo el detalle. Del histórico antiguo de Strava se
descargan solo resumen y vueltas (modo ligero), poco a poco.
{('<span class="err">Último error: ' + e(err) + '</span>') if err else ''}</div></div>"""

    explainer = """<details class="card"><summary><b>¿Qué datos guardamos de cada actividad?</b></summary>
<ol class="ink2" style="font-size:.9rem;padding-left:1.2rem">
<li><b>Resumen</b> (de la lista de Strava): fecha, deporte, distancia, tiempo, desnivel, FC media y máxima, velocidad.</li>
<li><b>Detalle</b>: las vueltas/series que marcó el reloj, los parciales por km, tus mejores esfuerzos (400 m, 1 km, 5 km…),
calorías, esfuerzo percibido, descripción, dispositivo y material.</li>
<li><b>Segundo a segundo</b>: frecuencia cardíaca, ritmo, cadencia, potencia, altitud, pendiente, GPS y temperatura
durante toda la actividad.</li>
<li><b>Métricas calculadas</b> por la app: tiempo en cada zona de FC, carga (TRIMP), desacople aeróbico, eficiencia…
Son lo que el entrenador usa para decidir.</li></ol>
<p class="explain">Pulsa cualquier actividad de la lista para ver todo esto explicado.</p></details>"""

    sports = [r["sport_type"] for r in db.activity_summary(aid)]
    filt = '<div class="filters">' + f'<a href="/" class="{"on" if not sport_filter else ""}">Todas</a>' + "".join(
        f'<a href="/?sport={e(s)}" class="{"on" if s == sport_filter else ""}">{e(sport_es(s))}</a>'
        for s in sports[:8]) + "</div>"

    rows = ""
    acts = db.list_activities_with_metrics(aid, 50, offset, sport_filter)
    for a in acts:
        z = [a[f"hr_z{i}_s"] or 0 for i in range(1, 6)]
        zt = sum(z)
        mini = ('<div class="mini" title="Distribución por zonas de FC">' + "".join(
            f'<div style="flex:{s};background:var(--z{i+1})"></div>' for i, s in enumerate(z) if s) + "</div>") if zt else ""
        st = "✓" if a["enrich_status"] == "ok" else "·" if a["enrich_status"] else '<span class="muted">⏳</span>'
        sp = a["sport_type"]
        rows += (f'<tr class="click" onclick="location.href=\'/activity/{a["id"]}\'">'
                 f'<td>{(a["start_date_local"] or "")[:10]}</td><td>{e(sport_es(sp))}</td>'
                 f'<td><a href="/activity/{a["id"]}">{e((a["name"] or "")[:40])}</a></td>'
                 f'<td>{fmt_dist(a["distance_m"], sp)}</td><td>{fmt_dur(a["moving_time_s"])}</td>'
                 f'<td>{fmt_pace(a["average_speed"], sp) if a["distance_m"] else "–"}</td>'
                 f'<td>{round(a["average_heartrate"]) if a["average_heartrate"] else "–"}</td>'
                 f'<td>{round(a["trimp_edwards"]) if a["trimp_edwards"] is not None else "–"}</td>'
                 f'<td>{mini}</td><td>{st}</td></tr>')
    q = f"sport={e(sport_filter)}&" if sport_filter else ""
    pager = ""
    if offset:
        pager += f'<a href="/?{q}offset={max(0, offset-50)}">← más recientes</a> '
    if len(acts) == 50:
        pager += f' <a href="/?{q}offset={offset+50}">más antiguas →</a>'

    summary = "".join(
        f"<tr><td>{e(sport_es(r['sport_type']))}</td><td>{r['n']}</td>"
        f"<td>{(r['dist'] or 0)/1000:,.0f} km</td><td>{(r['secs'] or 0)/3600:,.0f} h</td>"
        f"<td>{(r['first'] or '')[:10]}</td></tr>"
        for r in db.activity_summary(aid))

    from datetime import date as _d
    body = f"""{refresh}{nav('/')}<h1>Hola, {e(athlete['firstname'] or '')} 👋</h1>
{today_card(aid, _d.today())}
{sync_card}
{explainer}
{weekly_chart(db.weekly_volume(aid)) if not offset and not sport_filter else ''}
<h2>Actividades</h2>
<p class="explain">Pulsa una para ver todo el detalle. <b>Carga</b> = TRIMP (cuánto pesó la sesión).
La barrita es el tiempo en cada zona de FC (de <span class="sw" style="background:var(--z1)"></span>Z1 a
<span class="sw" style="background:var(--z5)"></span>Z5). ✓ = detalle completo descargado, ⏳ = en cola.</p>
{filt}
<div class="scroll"><table><tr><th>Fecha</th><th>Tipo</th><th>Nombre</th><th>Dist.</th><th>Tiempo</th><th>Ritmo</th>
<th>FC</th><th>Carga</th><th>Zonas</th><th></th></tr>{rows}</table></div>
<p>{pager}</p>
<h2>Todo tu histórico por deporte</h2>
<div class="scroll"><table><tr><th>Deporte</th><th>Nº</th><th>Distancia</th><th>Tiempo</th><th>Desde</th></tr>{summary}</table></div>"""
    return page(body, head=f"<style>{HOME_CSS}</style><style>{PLAN_CSS}</style>")


# ------------------------------------------------------------------- plan

import plan_tool  # noqa: E402
import paces as P  # noqa: E402
from datetime import date as _date, timedelta as _td  # noqa: E402

PLAN_CSS = """
.nav{display:flex;gap:1rem;margin-bottom:1rem;font-size:.95rem}
.nav a{text-decoration:none;color:var(--ink2)} .nav a.on{color:var(--ink);font-weight:600}
.chip{display:inline-block;font-size:.75rem;font-weight:600;padding:.1rem .45rem;border-radius:999px;border:1px solid var(--border);white-space:nowrap}
.st-done{color:var(--good)} .st-partial{color:#b07a00} .st-miss{color:var(--bad)} .st-todo{color:var(--muted)} .st-today{color:var(--line)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .st-partial{color:#fab219}}
:root[data-theme="dark"] .st-partial{color:#fab219}
.week{margin:1.2rem 0}
.week h3{font-size:1rem;margin:.2rem 0}
.day{display:grid;grid-template-columns:5.5rem 1fr;gap:.6rem;padding:.45rem 0;border-bottom:1px solid var(--grid);align-items:start}
.day.today{background:var(--surface);border-radius:8px;padding:.45rem .5rem}
.day .d{color:var(--ink2);font-size:.85rem;font-variant-numeric:tabular-nums}
.sess{display:flex;gap:.5rem;align-items:baseline;flex-wrap:wrap;padding:.1rem 0}
.sess a{text-decoration:none;color:var(--ink)} .sess a:hover{text-decoration:underline}
.sess .k{font-size:.72rem;color:var(--accent);font-weight:700}
.sport{font-size:.8rem;color:var(--ink2);min-width:4.5rem}
.block{padding:.55rem 0;border-bottom:1px solid var(--grid)} .block:last-child{border-bottom:0}
.block .n{font-weight:600}
.hero{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.6rem}
.pz td:first-child{font-weight:600}
.series{font-size:.8rem;color:var(--ink2);margin:0 0 .2rem 5rem}
@media (max-width:560px){.series{margin-left:0}}
.weeknav{display:flex;align-items:center;gap:.8rem;margin:.6rem 0 .4rem}
.weeknav>a,.weeknav>span{font-size:1.4rem;text-decoration:none;padding:0 .3rem}
.kmbar{position:relative;height:6px;background:var(--grid);border-radius:3px;margin-top:.2rem;width:120px}
.kmbar div{position:absolute;left:0;top:0;height:6px;border-radius:3px;background:var(--line);opacity:.35}
.kmbar div.done{background:var(--good);opacity:1;height:6px}
table.fc td{vertical-align:top;white-space:normal} table.fc td.keys{font-size:.85rem;min-width:14rem}
table.fc tr.now td{background:var(--surface)}
"""

SPORT_LABEL = {"run": "🏃 Carrera", "swim": "🏊 Natación", "bike": "🚴 Bici", "gym": "🏋️ Gimnasio",
               "rest": "😴 Descanso", "race": "🏁 CARRERA"}
DAYS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def nav(on):
    items = [("/", "Inicio"), ("/plan", "Plan"), ("/prevision", "Previsión"), ("/ritmos", "Ritmos")]
    return ('<div class="nav">' + "".join(
        f'<a href="{h}" class="{"on" if h == on else ""}">{t}</a>' for h, t in items)
        + '<a href="/movil" class="movil" title="Abrir en el móvil" style="margin-left:auto">📱</a></div>')


def _disc(sport_type):
    if sport_type in SWIM:
        return "swim"
    if sport_type in RIDE:
        return "bike"
    if sport_type in RUN:
        return "run"
    if sport_type in ("WeightTraining", "Workout", "Crossfit", "HighIntensityIntervalTraining", "Yoga"):
        return "gym"
    return "other"


def match_sessions(sessions, acts, today):
    """Empareja sesiones planificadas con actividades reales y decide su estado.

    Dos pasadas: primero cada sesión con una actividad del MISMO día; después,
    las que quedan sin pareja con actividades sobrantes del día anterior o
    siguiente (sesión movida). Así una sesión saltada no "roba" la actividad
    que pertenece a la sesión del día de al lado.

    Devuelve {session_id: (estado, etiqueta, actividad|None, detalle)}.
    estado ∈ done | partial | miss | todo | today | rest_ok | rest_broken
    """
    by = {}
    for a in acts:
        by.setdefault(((a["start_date_local"] or "")[:10], _disc(a["sport_type"])), []).append(a)
    used, pairs, out = set(), {}, {}
    parsed = {row["id"]: json.loads(row["session"]) for row in sessions}
    want = {row["id"]: ("run" if row["sport"] in ("run", "race") else row["sport"]) for row in sessions}

    def take(row, day):
        c = [a for a in by.get((day, want[row["id"]]), []) if a["id"] not in used]
        if not c:
            return None
        a = max(c, key=lambda x: x["moving_time_s"] or 0)
        used.add(a["id"])
        return a

    active = [r for r in sessions if r["sport"] != "rest"]
    for row in active:                                   # 1ª pasada: mismo día
        a = take(row, row["date"])
        if a:
            pairs[row["id"]] = (a, "")
    for row in active:                                   # 2ª pasada: movidas ±1 día
        if row["id"] in pairs or row["date"] > today.isoformat():
            continue
        for delta in (-1, 1):
            dd = (_date.fromisoformat(row["date"]) + _td(days=delta)).isoformat()
            a = take(row, dd)
            if a:
                pairs[row["id"]] = (a, f" (hecha el {dd[8:10]}/{dd[5:7]})")
                break

    for row in sessions:
        s, d, sport = parsed[row["id"]], row["date"], row["sport"]
        if sport == "rest":
            trained = [a for (k, disc), v in by.items() if k == d and disc in ("run", "bike", "swim") for a in v]
            if d > today.isoformat():
                out[row["id"]] = ("todo", "Descanso", None, "")
            elif trained:
                out[row["id"]] = ("rest_broken", "⚠ Entrenaste", None, "Era día de descanso.")
            else:
                out[row["id"]] = ("rest_ok", "✓ Descansado", None, "")
            continue
        if row["id"] not in pairs:
            if d > today.isoformat():
                out[row["id"]] = ("todo", "Pendiente", None, "")
            elif d == today.isoformat():
                out[row["id"]] = ("today", "Hoy", None, "")
            else:
                out[row["id"]] = ("miss", "✗ No hecha", None, "")
            continue
        a, moved = pairs[row["id"]]
        # ¿Se cumplió? Distancia (correr/nadar) o duración (bici/gimnasio)
        if sport in ("run", "race") and s.get("distance_km"):
            ratio = (a["distance_m"] or 0) / 1000 / s["distance_km"]
        elif sport == "swim" and s.get("distance_m"):
            ratio = (a["distance_m"] or 0) / s["distance_m"]
        elif s.get("duration_min"):
            ratio = (a["moving_time_s"] or 0) / 60 / s["duration_min"]
        else:
            ratio = 1
        detail = ""
        if s.get("intensity") == "E" and sport in ("run", "bike") and (a["average_heartrate"] or 0) > 145:
            detail = f"FC media {a['average_heartrate']:.0f}: más intenso de lo previsto (debía ser suave, <140)."
        if ratio >= 0.85:
            st, lab = ("partial", "◐ Hecha, más intensa" + moved) if detail else ("done", "✓ Hecha" + moved)
        else:
            st, lab = "partial", f"◐ {'Parcial' if ratio >= 0.5 else 'Corta'} ({ratio*100:.0f}%)" + moved
        out[row["id"]] = (st, lab, a, detail)
    return out


def _chip(st, lab):
    cls = {"done": "st-done", "rest_ok": "st-done", "partial": "st-partial", "rest_broken": "st-partial",
           "miss": "st-miss", "today": "st-today"}.get(st, "st-todo")
    return f'<span class="chip {cls}">{escape(lab)}</span>'


def _size(s):
    if s.get("distance_km"):
        return f"{s['distance_km']:g} km"
    if s.get("distance_m"):
        return f"{s['distance_m']:g} m"
    if s.get("duration_min"):
        return f"{s['duration_min']} min"
    return ""


def goal_card(athlete_id, today):
    g = db.active_goal(athlete_id)
    v = db.current_vdot(athlete_id)
    if not g:
        return ""
    days = (_date.fromisoformat(g["race_date"]) - today).days
    pred = P.predict_time(v["vdot"], g["distance_m"]) if v else None
    need = P.vdot_from_race(g["distance_m"], g["target_time_s"]) if g["target_time_s"] else None
    gap = ""
    if pred and g["target_time_s"]:
        diff = pred - g["target_time_s"]
        gap = (f"Te faltan <b>{P.fmt_time(diff)}</b> para el objetivo (VDOT {v['vdot']:.1f} → necesitas {need:.1f})."
               if diff > 0 else "¡Tu forma actual ya da para el objetivo!")
    return f"""<div class="hero">
<div class="tile"><div class="l">Objetivo</div><div class="v">{escape(g['name'])}</div><div class="h">{g['race_date'][8:10]}/{g['race_date'][5:7]} · {g['distance_m']/1000:g} km</div></div>
<div class="tile"><div class="l">Faltan</div><div class="v">{days} días</div><div class="h">{days//7} semanas</div></div>
<div class="tile"><div class="l">Tiempo objetivo</div><div class="v">{P.fmt_time(g['target_time_s']) if g['target_time_s'] else '–'}</div><div class="h">{P.fmt(g['target_time_s']/(g['distance_m']/1000)) + '/km' if g['target_time_s'] else ''}</div></div>
<div class="tile"><div class="l">Predicción con tu forma de hoy</div><div class="v">{P.fmt_time(pred) if pred else '–'}</div><div class="h">VDOT {v['vdot']:.1f} · <a href="/ritmos">ver ritmos</a></div></div>
</div><p class="explain">{gap} La predicción se actualiza con cada test.</p>"""


def today_card(athlete_id, today):
    plan = db.active_plan(athlete_id)
    if not plan:
        return ""
    pz = plan_tool.current_paces(athlete_id)
    rows = db.plan_sessions(plan["id"], today.isoformat(), (today + _td(days=1)).isoformat())
    acts = db.activities_between(athlete_id, (today - _td(days=1)).isoformat(), (today + _td(days=1)).isoformat())
    status = match_sessions(rows, acts, today)
    html = ""
    for label, d in (("Hoy", today), ("Mañana", today + _td(days=1))):
        ss = [r for r in rows if r["date"] == d.isoformat()]
        if not ss:
            continue
        items = ""
        for r in ss:
            s = json.loads(r["session"])
            st, lab, _, _ = status[r["id"]]
            items += (f'<div class="sess"><span class="sport">{SPORT_LABEL[r["sport"]]}</span>'
                      f'<a href="/plan/sesion/{r["id"]}"><b>{escape(paces_text(s.get("title") or "", pz))}</b></a>'
                      f'<span class="muted">{_size(s)}</span>{_chip(st, lab) if label == "Hoy" else ""}</div>')
        html += f'<div style="margin:.3rem 0"><div class="muted" style="font-size:.85rem">{label}</div>{items}</div>'
    return f'<div class="card">{html}<div style="margin-top:.4rem"><a href="/plan">Ver el plan completo →</a></div></div>' if html else ""


def paces_text(t, pz):
    return P.render_text(t, pz) if pz else t


def _plan_weeks(rows):
    """[(lunes, domingo, [filas])] de las semanas que tienen sesiones."""
    first = _date.fromisoformat(rows[0]["date"])
    last = _date.fromisoformat(rows[-1]["date"])
    out, monday = [], first - _td(days=first.weekday())
    while monday <= last:
        sunday = monday + _td(days=6)
        wk = [r for r in rows if monday.isoformat() <= r["date"] <= sunday.isoformat()]
        if wk:
            out.append((monday, sunday, wk))
        monday += _td(days=7)
    return out


def _phase(pj, monday, sunday):
    return next((p["name"] for p in pj.get("phases", []) if p["from"] <= sunday.isoformat() and p["to"] >= monday.isoformat()), "")


def _run_km(acts, monday, sunday):
    return sum((a["distance_m"] or 0) / 1000 for a in acts
               if monday.isoformat() <= (a["start_date_local"] or "")[:10] <= sunday.isoformat() and _disc(a["sport_type"]) == "run")


def compact_session(r, s, pz, st):
    """Una sesión en una línea (+ series de natación en una segunda línea corta)."""
    sport = r["sport"]
    if sport == "rest":
        return f'<div class="sess"><span class="sport">{SPORT_LABEL["rest"]}</span>{_chip(*st[:2]) if st[0] != "todo" else ""}</div>'
    extra = ""
    if sport in ("run", "race") and pz and s.get("intensity") in pz:
        extra = f'<span class="muted">{s["intensity"]} {pz[s["intensity"]]["text"]}</span>'
    tag = f'<span class="chip">{escape(s["focus"])}</span>' if s.get("focus") else ""
    line = (f'<div class="sess"><span class="sport">{SPORT_LABEL[sport]}</span>'
            f'<a href="/plan/sesion/{r["id"]}">{escape(s.get("title") or "")}</a>{tag}'
            f'<span class="muted">{_size(s)}</span>{extra}'
            + ('<span class="k">CLAVE</span>' if r["key_session"] else "")
            + (_chip(*st[:2]) if st[0] != "todo" else "") + "</div>")
    if sport == "swim":
        series = " · ".join(b.get("short") or b.get("name", "") for b in s.get("blocks") or [])
        line += f'<div class="series">{escape(series)}</div>'
    return line


def plan_page(athlete_id, today=None, week=None):
    today = today or _date.today()
    plan = db.active_plan(athlete_id)
    if not plan:
        return page(nav("/plan") + "<h1>Plan</h1><p>No hay ningún plan activo todavía.</p>")
    pj = json.loads(plan["plan_json"])
    pz = plan_tool.current_paces(athlete_id)
    rows = db.plan_sessions(plan["id"])
    weeks = _plan_weeks(rows)
    cur = next((i for i, (m, su, _) in enumerate(weeks) if m <= today <= su),
               0 if today < weeks[0][0] else len(weeks) - 1)
    i = cur if week is None else max(0, min(len(weeks) - 1, week - 1))
    monday, sunday, wk = weeks[i]
    acts = db.activities_between(athlete_id, (monday - _td(days=1)).isoformat(), (sunday + _td(days=1)).isoformat())
    status = match_sessions(wk, acts, today)

    days_html = ""
    for k in range(7):
        d = monday + _td(days=k)
        ds = [r for r in wk if r["date"] == d.isoformat()]
        if not ds:
            continue
        items = "".join(compact_session(r, json.loads(r["session"]), pz, status[r["id"]]) for r in ds)
        days_html += (f'<div class="day{" today" if d == today else ""}"><div class="d">{DAYS_ES[k]} {d.day}/{d.month}'
                      f'{"<br><b>HOY</b>" if d == today else ""}</div><div>{items}</div></div>')

    g = db.active_goal(athlete_id)
    v = db.current_vdot(athlete_id)
    head = ""
    if g:
        days_left = (_date.fromisoformat(g["race_date"]) - today).days
        pred = P.fmt_time(P.predict_time(v["vdot"], g["distance_m"])) if v else "–"
        head = (f'<p class="ink2">{escape(g["name"])} · faltan <b>{days_left} días</b> · objetivo '
                f'<b>{P.fmt_time(g["target_time_s"]) if g["target_time_s"] else "–"}</b> · predicción hoy <b>{pred}</b></p>')
    plan_km = sum((json.loads(r["session"]).get("distance_km") or 0) for r in wk if r["sport"] in ("run", "race"))
    done = f" · hechos {_run_km(acts, monday, sunday):.0f}" if monday <= today else ""
    prev = f'<a href="/plan?w={i}">‹</a>' if i > 0 else '<span class="muted">‹</span>'
    nxt = f'<a href="/plan?w={i + 2}">›</a>' if i < len(weeks) - 1 else '<span class="muted">›</span>'
    back = f' · <a href="/plan">volver a esta semana</a>' if i != cur else ""
    rev = (pj.get("revisions") or [])[-1:] 
    rev_html = (f'<p class="muted" style="font-size:.85rem">Última adaptación ({rev[0]["date"][8:10]}/{rev[0]["date"][5:7]}): '
                f'{escape(rev[0]["summary"])}</p>') if rev else ""
    body = f"""{nav('/plan')}{head}
<div class="weeknav">{prev}<div><b>Semana {i + 1}</b> · {monday.day}/{monday.month} – {sunday.day}/{sunday.month}
<span class="muted">· {escape(_phase(pj, monday, sunday))} · {plan_km:g} km carrera{done}{back}</span></div>{nxt}</div>
{days_html}{rev_html}"""
    return page(body, title="Plan", head=f"<style>{PLAN_CSS}</style>")


def forecast_page(athlete_id, today=None):
    """El plan completo tal y como está hoy (tras la última adaptación)."""
    today = today or _date.today()
    plan = db.active_plan(athlete_id)
    if not plan:
        return page(nav("/prevision") + "<p>No hay plan activo.</p>")
    pj = json.loads(plan["plan_json"])
    pz = plan_tool.current_paces(athlete_id)
    rows = db.plan_sessions(plan["id"])
    weeks = _plan_weeks(rows)
    acts = db.activities_between(athlete_id, weeks[0][0].isoformat(), weeks[-1][1].isoformat())
    status = match_sessions(rows, acts, today)
    maxkm = max(sum((json.loads(r["session"]).get("distance_km") or 0) for r in wk if r["sport"] in ("run", "race"))
                for _, _, wk in weeks) or 1

    trs = ""
    for n, (monday, sunday, wk) in enumerate(weeks, 1):
        km = sum((json.loads(r["session"]).get("distance_km") or 0) for r in wk if r["sport"] in ("run", "race"))
        past = monday <= today
        done_km = _run_km(acts, monday, sunday) if past else 0
        keys = []
        for r in wk:
            if not r["key_session"]:
                continue
            s = json.loads(r["session"])
            pace = f' <span class="muted">{pz[s["intensity"]]["text"]}</span>' if pz and s.get("intensity") in pz else ""
            mark = {"done": " ✓", "partial": " ◐", "miss": " ✗"}.get(status[r["id"]][0], "")
            keys.append(f'<a href="/plan/sesion/{r["id"]}">{escape(s.get("title") or "")}</a>{pace}{mark}')
        cnt = [status[r["id"]][0] for r in wk if r["sport"] != "rest" and r["date"] < today.isoformat()]
        comp = f'{sum(1 for c in cnt if c == "done")}/{len(cnt)}' if cnt else ""
        bar = (f'<div class="kmbar"><div style="width:{km / maxkm * 100:.0f}%"></div>'
               + (f'<div class="done" style="width:{min(done_km, km * 1.5) / maxkm * 100:.0f}%"></div>' if past else "") + "</div>")
        is_now = monday <= today <= sunday
        trs += (f'<tr class="{"now" if is_now else ""}"><td><a href="/plan?w={n}">S{n}</a></td>'
                f'<td>{monday.day}/{monday.month}</td><td>{escape(_phase(pj, monday, sunday))}</td>'
                f'<td>{km:g}{f" <span class=muted>({done_km:.0f})</span>" if past else ""}{bar}</td>'
                f'<td class="keys">{"<br>".join(keys)}</td><td>{comp}</td></tr>')
    revs = "".join(f"<li><b>{r['date'][8:10]}/{r['date'][5:7]}</b> {escape(r['summary'])}</li>"
                   for r in reversed(pj.get("revisions") or []))
    g = pj["goal"]
    body = f"""{nav('/prevision')}<h1>Previsión hasta la carrera</h1>
<p class="ink2">El plan completo tal y como está hoy. Cada domingo se adapta con lo que hiciste la semana anterior.</p>
<div class="scroll"><table class="fc"><tr><th></th><th>Lunes</th><th>Fase</th><th>Km carrera</th><th>Sesiones clave</th><th>Hechas</th></tr>{trs}</table></div>
<p class="muted" style="font-size:.85rem"><span class="sw" style="background:var(--line)"></span>planificado
<span class="sw" style="background:var(--good);margin-left:.8rem"></span>hecho · ritmos con tu VDOT actual</p>
<h2>Adaptaciones</h2><ul class="ink2" style="font-size:.9rem;padding-left:1.2rem">{revs or '<li>Ninguna todavía.</li>'}</ul>"""
    return page(body, title="Previsión", head=f"<style>{PLAN_CSS}</style>")


def session_page(athlete_id, session_id, today=None):
    today = today or _date.today()
    row = db.plan_session(session_id)
    plan = db.active_plan(athlete_id)
    if not row or not plan or row["plan_id"] != plan["id"]:
        return None
    s = json.loads(row["session"])
    pz = plan_tool.current_paces(athlete_id)
    d = _date.fromisoformat(row["date"])
    acts = db.activities_between(athlete_id, (d - _td(days=1)).isoformat(), (d + _td(days=1)).isoformat())
    same_day = db.plan_sessions(plan["id"], (d - _td(days=1)).isoformat(), (d + _td(days=1)).isoformat())
    st, lab, act, detail = match_sessions(same_day, acts, today)[row["id"]]

    blocks = "".join(f'<div class="block"><div class="n">{escape(b.get("name",""))}</div>'
                     f'<div>{escape(paces_text(b.get("text",""), pz))}</div></div>' for b in s.get("blocks") or [])
    codes = sorted({c for b in s.get("blocks") or [] for c in (pz or {}) if "{" + c + "}" in b.get("text", "")},
                   key=lambda c: ["E", "M", "T", "I", "R", "CUR", "RP"].index(c))
    legend = "".join(f"<tr><td>{c} · {pz[c]['name']}</td><td>{pz[c]['text']}</td><td>FC {pz[c]['hr']}</td><td class='ink2'>{pz[c]['desc']}</td></tr>"
                     for c in codes) if pz else ""

    did = ""
    if act:
        sp = act["sport_type"]
        m = json.loads(act["metrics"]) if act["metrics"] else {}
        laps = json.loads(act["laps"]) if act["laps"] else []
        lap_rows = ""
        if 1 < len(laps) <= 40 and row["sport"] in ("run", "race", "swim"):
            for i, l in enumerate(laps, 1):
                if not l.get("distance"):
                    continue
                lap_rows += (f"<tr><td>{i}</td><td>{fmt_dist(l.get('distance'), sp)}</td><td>{fmt_dur(l.get('moving_time'))}</td>"
                             f"<td>{fmt_pace(l.get('average_speed'), sp)}</td>"
                             f"<td>{round(l['average_heartrate']) if l.get('average_heartrate') else '–'}</td></tr>")
        z = m.get("hr_zone_s")
        zl = ""
        if z and sum(z):
            zl = " · zonas " + " / ".join(f"Z{i+1} {v/sum(z)*100:.0f}%" for i, v in enumerate(z) if v)
        did = f"""<h2>Lo que hiciste</h2><div class="card">
<div>{_chip(st, lab)} <a href="/activity/{act['id']}"><b>{escape(act['name'] or '')}</b></a></div>
<p class="ink2" style="margin:.4rem 0">{fmt_dist(act['distance_m'], sp)} · {fmt_dur(act['moving_time_s'])} ·
{fmt_pace(act['average_speed'], sp) if act['distance_m'] else ''} · FC {round(act['average_heartrate']) if act['average_heartrate'] else '–'}{zl}</p>
{f'<p class="st-partial" style="margin:.2rem 0">{escape(detail)}</p>' if detail else ''}
{('<p class="explain">Compara cada vuelta con los ritmos que pedía la sesión (arriba).</p><div class="scroll"><table><tr><th>#</th><th>Dist.</th><th>Tiempo</th><th>Ritmo</th><th>FC</th></tr>' + lap_rows + '</table></div>') if lap_rows else ''}
</div>"""
    elif row["date"] <= today.isoformat():
        did = f'<h2>Lo que hiciste</h2><div class="card">{_chip(st, lab)} <span class="ink2">No encuentro ninguna actividad que encaje en Strava (ese día ni el anterior/siguiente). Si la hiciste, sincroniza desde la portada.</span></div>'

    body = f"""{nav('/plan')}<p><a href="/plan">← Plan</a></p>
<div class="muted">{SPORT_LABEL[row['sport']]} · {DAYS_ES[d.weekday()]} {d.day}/{d.month}/{d.year}{' · <b style="color:var(--accent)">SESIÓN CLAVE</b>' if row['key_session'] else ''}</div>
<h1>{escape(s.get('title') or '')}</h1>
<div class="tiles">{''.join(f'<div class="tile"><div class="l">{k}</div><div class="v">{v}</div></div>' for k, v in (("Volumen", _size(s)), ("Duración aprox.", f"{s['duration_min']} min" if s.get('duration_min') else ''), ("Intensidad principal", f"{s['intensity']} · {pz[s['intensity']]['name']}" if pz and s.get('intensity') in (pz or {}) else '')) if v)}</div>
{f'<p class="ink2"><b>Para qué:</b> {escape(paces_text(s["why"], pz))}</p>' if s.get('why') else ''}
<h2>La sesión</h2><div class="card">{blocks or '<span class="muted">Descanso.</span>'}</div>
{f'<p class="ink2"><b>Consejo:</b> {escape(paces_text(s["notes"], pz))}</p>' if s.get('notes') else ''}
{('<h2>Ritmos de esta sesión</h2><p class="explain">Calculados con tu VDOT actual. Si cambia (tras un test), se actualizan solos.</p><div class="scroll"><table class="pz"><tr><th>Intensidad</th><th>Ritmo</th><th>FC</th><th>Qué es</th></tr>' + legend + '</table></div>') if legend else ''}
{did}"""
    return page(body, title=s.get("title") or "Sesión", head=f"<style>{PLAN_CSS}</style>")


def paces_page(athlete_id, msg=""):
    pz = plan_tool.current_paces(athlete_id)
    hist = db.vdot_history(athlete_id)
    g = db.active_goal(athlete_id)
    if not pz:
        return page(nav("/ritmos") + "<p>Aún no hay VDOT.</p>")
    rows = "".join(f"<tr><td>{c}</td><td>{pz[c]['name']}</td><td><b>{pz[c]['text']}</b></td><td>{pz[c]['hr']}</td><td class='ink2'>{pz[c]['desc']}</td></tr>"
                   for c in ("E", "M", "T", "I", "R", "CUR", "RP") if c in pz)
    v = hist[-1]["vdot"]
    preds = "".join(f"<tr><td>{n}</td><td>{P.fmt_time(P.predict_time(v, dm))}</td><td>{P.fmt(P.predict_time(v, dm)/(dm/1000))}/km</td></tr>"
                    for n, dm in (("5K", 5000), ("10K", 10000), ("Media maratón", 21097.5)))
    h = "".join(f"<tr><td>{r['set_on']}</td><td>{r['vdot']:.1f}</td><td class='ink2'>{escape(r['source'] or '')}</td></tr>" for r in reversed(hist))
    body = f"""{nav('/ritmos')}<h1>Tus ritmos</h1>
<p class="explain">Todo el plan está escrito con intensidades (E, T, I…), no con ritmos fijos. Aquí se convierten en
min/km a partir de tu <b>VDOT</b>: un número que resume tu forma en carrera (método de Jack Daniels). Cuando haces un
test y el VDOT cambia, cambian todos los ritmos del plan.</p>
<div class="scroll"><table class="pz"><tr><th></th><th>Intensidad</th><th>Ritmo</th><th>FC</th><th>Qué es</th></tr>{rows}</table></div>
<h2>Qué predice tu VDOT ({v:.1f})</h2>
<div class="scroll"><table><tr><th>Distancia</th><th>Tiempo</th><th>Ritmo</th></tr>{preds}</table></div>
{f'<p class="explain">Para tu objetivo ({P.fmt_time(g["target_time_s"])} en {g["distance_m"]/1000:g} km) necesitas VDOT {P.vdot_from_race(g["distance_m"], g["target_time_s"]):.1f}.</p>' if g and g["target_time_s"] else ''}
<h2>Registrar un test o una carrera</h2>
<p class="explain">Cuando hagas un test (o una carrera a tope), apunta la distancia y el tiempo: la app calcula tu nuevo
VDOT y todos los ritmos del plan se actualizan. Usa el tiempo de la parte a tope, sin calentamiento.</p>
<form method="post" action="/ritmos/test" class="card" style="display:flex;flex-wrap:wrap;gap:.6rem;align-items:end">
<label>Distancia<br><select name="distance_m" style="padding:.4rem">
<option value="3000">3 km</option><option value="5000" selected>5 km</option><option value="10000">10 km</option><option value="21097.5">Media maratón</option></select></label>
<label>Tiempo (mm:ss o h:mm:ss)<br><input name="time" required placeholder="21:30" style="padding:.4rem;width:8rem"></label>
<label>Fecha<br><input type="date" name="day" style="padding:.4rem"></label>
<label>Nota<br><input name="note" placeholder="Test 5K pista" style="padding:.4rem;width:12rem"></label>
<button class="btn" style="border:0;padding:.55rem 1rem;cursor:pointer">Guardar</button></form>
{msg}
<h2>Historial</h2><div class="scroll"><table><tr><th>Fecha</th><th>VDOT</th><th>Origen</th></tr>{h}</table></div>"""
    return page(body, title="Ritmos", head=f"<style>{PLAN_CSS}</style>")



# ---------------------------------------------------------- enlace público

def publicize(html, token):
    """Convierte una página del plan en su versión pública de solo lectura:
    los enlaces apuntan a /c/<token>/…, sin menú privado ni enlaces a actividades."""
    import re
    base = f"/c/{token}"
    html = re.sub(r'<div class="nav">.*?</div>',
                  f'<div class="nav"><a href="{base}">Plan</a><a href="{base}/prevision">Previsión</a></div>', html, count=1, flags=re.S)
    html = html.replace('href="/plan/sesion/', f'href="{base}/sesion/')
    html = html.replace('href="/plan?w=', f'href="{base}?w=').replace('href="/plan"', f'href="{base}"')
    html = html.replace('href="/prevision"', f'href="{base}/prevision"')
    html = re.sub(r'<a href="/activity/\d+">(.*?)</a>', r'\1', html)
    html = re.sub(r'<a href="/ritmos">(.*?)</a>', r'\1', html)
    html = re.sub(r'<a href="https://www\.strava\.com[^"]*">(.*?)</a>', r'\1', html)
    return html
