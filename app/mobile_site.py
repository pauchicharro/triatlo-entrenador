"""Versión móvil de la app, accesible desde cualquier sitio (GitHub Pages) y CIFRADA.

El repositorio es público, así que la página publicada no contiene datos en
claro: el HTML con el plan, los entrenos, la recuperación… se cifra con
AES-256-GCM (clave derivada de una contraseña con PBKDF2) y se descifra en el
navegador del móvil con WebCrypto. La contraseña está en .env (MOBILE_PASSWORD);
el enlace con #k=<contraseña> la lleva en el fragmento, que nunca sale del móvil.

Se regenera desde el Mac (plan_sync.py, cada hora con la app abierta) y muestra
cuándo se actualizó por última vez: sirve aunque el Mac esté apagado.

Uso:  app/.venv/bin/python app/mobile_site.py     → docs/entrenos/index.html
"""

import base64
import json
import os
import secrets
import sys
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402
import paces as P  # noqa: E402
import plan_tool  # noqa: E402
import views  # noqa: E402

ROOT = Path(__file__).parent.parent
OUT = ROOT / "docs" / "entrenos" / "index.html"
ENV = ROOT / ".env"
ITER = 250_000


def password():
    """MOBILE_PASSWORD de .env; si no existe, se crea una y se guarda."""
    from dotenv import dotenv_values
    pw = dotenv_values(ENV).get("MOBILE_PASSWORD")
    if not pw:
        pw = secrets.token_urlsafe(9)
        with open(ENV, "a") as f:
            f.write(f"\n# Contraseña de la versión móvil cifrada (docs/entrenos)\nMOBILE_PASSWORD={pw}\n")
    return pw


def encrypt(plaintext, pw):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())
    ct = AESGCM(key).encrypt(iv, plaintext.encode(), None)  # ct || tag (lo mismo que espera WebCrypto)
    b = lambda x: base64.b64encode(x).decode()
    return {"salt": b(salt), "iv": b(iv), "ct": b(ct), "iter": ITER}


# ------------------------------------------------------------- contenido

def _blocks_html(s, pz):
    out = ""
    for b in s.get("blocks") or []:
        out += (f'<div class="blk"><b>{escape(b.get("name", ""))}</b>'
                f'<div>{escape(P.render_text(b.get("text", ""), pz) if pz else b.get("text", ""))}</div>'
                f'{views.exercise_imgs(b, "../ex/")}</div>')
    if s.get("notes"):
        out += f'<p class="note">💡 {escape(P.render_text(s["notes"], pz) if pz else s["notes"])}</p>'
    return out


def _session_html(r, s, pz, st, open_=False):
    sport = r["sport"]
    if sport == "rest":
        return f'<div class="ses rest">{views.SPORT_LABEL["rest"]} <span class="muted">{escape(s.get("notes") or "")}</span></div>'
    label, (code, txt) = views.SPORT_LABEL[sport], (st[0], st[1])
    pace = f' · {s["intensity"]} {pz[s["intensity"]]["text"]}' if sport in ("run", "race") and pz and s.get("intensity") in pz else ""
    tag = f' <span class="chip">{escape(s["focus"])}</span>' if s.get("focus") else ""
    chip = views._chip(code, txt) if code != "todo" else ""
    key = ' <span class="k">CLAVE</span>' if r["key_session"] else ""
    head = (f'<b>{label}</b> {escape(s.get("title") or "")}{tag}{key} '
            f'<span class="muted">{views._size(s)}{pace}</span> {chip}')
    series = ""
    if sport == "swim":
        series = f'<div class="series2">{escape(" · ".join(b.get("short") or b.get("name", "") for b in s.get("blocks") or []))}</div>'
    return f'<details class="ses"{" open" if open_ else ""}><summary>{head}{series}</summary>{_blocks_html(s, pz)}</details>'


def _activity_html(a):
    sp = a["sport_type"]
    m = json.loads(a["metrics"]) if a["metrics"] else {}
    z = m.get("hr_zone_s")
    bar = ""
    if z and sum(z):
        bar = ('<div class="zbar">' + "".join(
            f'<div style="flex:{v};background:var(--z{i+1})"></div>' for i, v in enumerate(z) if v) + "</div>")
    bits = [views.fmt_dur(a["moving_time_s"])]
    if a["distance_m"]:
        bits.append(views.fmt_dist(a["distance_m"], sp))
        if sp not in ("WeightTraining", "HighIntensityIntervalTraining", "Workout"):
            bits.append(views.fmt_pace(a["average_speed"], sp))
    if a["average_heartrate"]:
        bits.append(f"FC {a['average_heartrate']:.0f}")
    if m.get("trimp_edwards") is not None:
        bits.append(f"carga {m['trimp_edwards']:.0f}")
    if m.get("garmin_trainingEffectLabel"):
        bits.append(str(m["garmin_trainingEffectLabel"]).lower().replace("_", " "))
    laps = json.loads(a["laps"]) if a["laps"] else []
    lap_html = ""
    rows = [l for l in laps if l.get("distance")]
    if 1 < len(rows) <= 40 and sp in views.RUN + views.SWIM:
        lap_html = ("<details><summary class='muted'>Vueltas</summary><table>" + "".join(
            f"<tr><td>{views.fmt_dur(l.get('moving_time'))}</td><td>{views.fmt_dist(l.get('distance'), sp)}</td>"
            f"<td>{views.fmt_pace(l.get('average_speed'), sp)}</td>"
            f"<td>{('FC ' + str(round(l['average_heartrate']))) if l.get('average_heartrate') else ''}</td></tr>"
            for l in rows) + "</table></details>")
    d = a["start_date_local"] or ""
    return (f'<div class="act"><div><b>{views.DAYS_ES[date.fromisoformat(d[:10]).weekday()]} {int(d[8:10])}/{int(d[5:7])}</b> '
            f'{escape(views.sport_es(sp))} · {escape((a["name"] or "")[:40])}</div>'
            f'<div class="muted">{" · ".join(bits)}</div>{bar}{lap_html}</div>')


def _recovery_html(today):
    wdir = ROOT / "data" / "garmin" / "wellness"
    rows = ""
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        f = wdir / f"{d}.json"
        if not f.exists():
            continue
        try:
            w = json.loads(f.read_text())
        except ValueError:
            continue
        sl = (w.get("sleep") or {}).get("dailySleepDTO") or {}
        hrv = (w.get("hrv") or {}).get("hrvSummary") or {}
        bb = w.get("body_battery")
        bb = bb[0] if isinstance(bb, list) and bb else {}
        score = ((sl.get("sleepScores") or {}).get("overall") or {}).get("value")
        rows += (f"<tr><td>{int(d[8:10])}/{int(d[5:7])}</td>"
                 f"<td>{(sl.get('sleepTimeSeconds') or 0)/3600:.1f} h{f' ({score})' if score else ''}</td>"
                 f"<td>{hrv.get('lastNightAvg') or '–'} <span class='muted'>({hrv.get('weeklyAvg') or '–'})</span></td>"
                 f"<td>{bb.get('charged') or '–'}</td></tr>")
    if not rows:
        return "<p class='muted'>Sin datos de Garmin recientes.</p>"
    return ("<table><tr><th>Día</th><th>Sueño (nota)</th><th>VFC (media 7 d)</th><th>Body Battery</th></tr>"
            + rows + "</table>")


def build_html(today=None):
    today = today or date.today()
    aid = db.all_athletes()[0]["id"]
    plan = db.active_plan(aid)
    pj = json.loads(plan["plan_json"])
    pz = plan_tool.current_paces(aid)
    g, v = db.active_goal(aid), db.current_vdot(aid)
    rows = db.plan_sessions(plan["id"])
    weeks = views._plan_weeks(rows)
    acts_all = db.activities_between(aid, (today - timedelta(days=21)).isoformat(), (today + timedelta(days=1)).isoformat())
    status = views.match_sessions(rows, db.activities_between(aid, rows[0]["date"], rows[-1]["date"]), today)

    # Cabecera
    days_left = (date.fromisoformat(g["race_date"]) - today).days
    pred = P.fmt_time(P.predict_time(v["vdot"], g["distance_m"]))
    head = (f'<p class="ink2">{escape(g["name"])} · <b>{days_left} días</b> · objetivo '
            f'<b>{P.fmt_time(g["target_time_s"]) if g["target_time_s"] else "–"}</b> · predicción <b>{pred}</b> (VDOT {v["vdot"]:.1f})</p>')

    # Hoy y mañana
    hoy = ""
    for label, d in (("Hoy", today), ("Mañana", today + timedelta(days=1))):
        ds = [r for r in rows if r["date"] == d.isoformat()]
        if ds:
            hoy += (f'<h3>{label} · {views.DAYS_ES[d.weekday()]} {d.day}/{d.month}</h3>'
                    + "".join(_session_html(r, json.loads(r["session"]), pz, status[r["id"]], open_=True) for r in ds))

    # Esta semana (y navegación a las demás)
    cur = next((i for i, (m, su, _) in enumerate(weeks) if m <= today <= su), 0)
    week_html = ""
    for i, (monday, sunday, wk) in enumerate(weeks):
        if i < cur - 1:
            continue
        km = sum((json.loads(r["session"]).get("distance_km") or 0) for r in wk if r["sport"] in ("run", "race"))
        days = ""
        for k in range(7):
            d = monday + timedelta(days=k)
            ds = [r for r in wk if r["date"] == d.isoformat()]
            if ds:
                days += (f'<div class="day{" today" if d == today else ""}"><div class="d">{views.DAYS_ES[k]} {d.day}/{d.month}</div><div>'
                         + "".join(_session_html(r, json.loads(r["session"]), pz, status[r["id"]]) for r in ds) + "</div></div>")
        phase = views._phase(pj, monday, sunday)
        week_html += (f'<details class="week"{" open" if i == cur else ""}><summary><b>Semana {i + 1}</b> · {monday.day}/{monday.month}–{sunday.day}/{sunday.month} '
                      f'<span class="muted">· {escape(phase)} · ≈{km:g} km</span>{" · <b>ESTA</b>" if i == cur else ""}</summary>{days}</details>')

    acts = "".join(_activity_html(a) for a in reversed(acts_all)) or "<p class='muted'>Sin entrenos recientes.</p>"
    rit = "".join(f"<tr><td><b>{c}</b> {pz[c]['name']}</td><td>{pz[c]['text']}</td><td class='muted'>FC {pz[c]['hr']}</td></tr>"
                  for c in ("E", "M", "T", "I", "R", "CUR", "RP") if c in pz)
    rev = (pj.get("revisions") or [])[-3:]
    revs = "".join(f"<li><b>{r['date'][8:10]}/{r['date'][5:7]}</b> {escape(r['summary'])}</li>" for r in reversed(rev))
    updated = datetime.now().strftime("%d/%m %H:%M")

    return f"""{head}
<nav class="tabs"><a href="#hoy">Hoy</a><a href="#semana">Semana</a><a href="#entrenos">Entrenos</a><a href="#recup">Recuperación</a><a href="#ritmos">Ritmos</a></nav>
<section id="hoy">{hoy or '<p class="muted">Nada planificado.</p>'}</section>
<section id="semana"><h2>Plan</h2>{week_html}
<h3>Últimas adaptaciones</h3><ul class="ink2 small">{revs}</ul></section>
<section id="entrenos"><h2>Entrenos (21 días)</h2>{acts}</section>
<section id="recup"><h2>Recuperación (Garmin)</h2>{_recovery_html(today)}</section>
<section id="ritmos"><h2>Ritmos</h2><table>{rit}</table></section>
<p class="muted small">Actualizado {updated} desde el Mac. Para cambiar algo, escribe al entrenador.</p>"""


CSS_EXTRA = """
.tabs{position:sticky;top:0;z-index:3;display:flex;gap:.9rem;overflow-x:auto;background:var(--page);padding:.5rem 0;border-bottom:1px solid var(--grid);margin-bottom:.6rem}
.tabs a{text-decoration:none;color:var(--ink2);white-space:nowrap;font-size:.92rem}
section{scroll-margin-top:3rem;margin-bottom:1.6rem}
h2{font-size:1.1rem} h3{font-size:.95rem;margin:1rem 0 .3rem}
details.ses{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:.5rem .7rem;margin:.35rem 0}
details.ses summary{cursor:pointer;list-style:none;line-height:1.5}
details.ses summary::-webkit-details-marker{display:none}
.ses.rest{padding:.35rem 0}
.blk{padding:.35rem 0;border-top:1px solid var(--grid);font-size:.92rem}
.exi{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.4rem} .exi figure{margin:0;display:flex;gap:2px} .exi img{width:42vw;max-width:170px;height:auto;border-radius:6px;background:#fff}
.note{font-size:.88rem;color:var(--ink2);margin:.4rem 0 0}
.series2{font-size:.8rem;color:var(--ink2)}
details.week{margin:.5rem 0} details.week>summary{cursor:pointer;padding:.4rem 0}
.act{border-bottom:1px solid var(--grid);padding:.55rem 0;font-size:.92rem}
.act .zbar{height:6px;margin:.3rem 0 0}
.small{font-size:.85rem}
#lock{max-width:340px;margin:20vh auto;text-align:center}
#lock input{width:100%;padding:.7rem;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--ink);font:inherit;margin:.6rem 0}
"""

JS = r"""
const D = JSON.parse(document.getElementById('enc').textContent);
const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function unlock(pw, remember){
  try{
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({name:'PBKDF2', salt:b64(D.salt), iterations:D.iter, hash:'SHA-256'},
                                              base, {name:'AES-GCM', length:256}, false, ['decrypt']);
    const pt = await crypto.subtle.decrypt({name:'AES-GCM', iv:b64(D.iv)}, key, b64(D.ct));
    document.getElementById('app').innerHTML = new TextDecoder().decode(pt);
    document.getElementById('lock').style.display = 'none';
    if (remember) try{ localStorage.setItem('k', pw) }catch(e){}
    if (location.hash.startsWith('#k=')) history.replaceState(null, '', location.pathname);
    return true;
  }catch(e){ return false; }
}
(async () => {
  const fromHash = location.hash.startsWith('#k=') ? decodeURIComponent(location.hash.slice(3)) : null;
  let saved = null; try{ saved = localStorage.getItem('k') }catch(e){}
  if (fromHash && await unlock(fromHash, true)) return;
  if (saved && await unlock(saved, false)) return;
})();
document.getElementById('f').addEventListener('submit', async ev => {
  ev.preventDefault();
  const ok = await unlock(document.getElementById('pw').value, true);
  if (!ok) document.getElementById('err').textContent = 'Contraseña incorrecta';
});
"""


HASH_FILE = Path(__file__).parent / ".mobile_site.hash"  # fuera de git


def write(force=False):
    """Regenera la página. Si el contenido no ha cambiado, no la toca (el cifrado
    usa sal aleatoria: reescribirla siempre generaría un commit cada hora)."""
    import hashlib
    db.init()
    pw = password()
    body = build_html()
    digest = hashlib.sha256((body.rsplit('<p class="muted small">Actualizado', 1)[0] + pw).encode()).hexdigest()
    if not force and OUT.exists() and HASH_FILE.exists() and HASH_FILE.read_text() == digest:
        return None
    HASH_FILE.write_text(digest)
    payload = encrypt(body, pw)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>Mis entrenos</title>
<style>{views.CSS}{views.PLAN_CSS}{views.HOME_CSS}{CSS_EXTRA}</style></head><body>
<div id="lock"><h1>🏃 Mis entrenos</h1><p class="ink2">Página privada y cifrada.</p>
<form id="f"><input id="pw" type="password" placeholder="Contraseña" autocomplete="current-password">
<button class="btn" style="border:0;width:100%">Entrar</button></form><p id="err" class="err"></p></div>
<div id="app"></div>
<script type="application/json" id="enc">{json.dumps(payload)}</script>
<script>{JS}</script></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    out = write(force="--force" in sys.argv)
    print(f"Escrito {out}" if out else "Sin cambios")
