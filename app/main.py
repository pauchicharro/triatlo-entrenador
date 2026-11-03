"""Servidor web del entrenador de triatlón (piloto).

Arrancar:  cd app && .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000   (0.0.0.0 = accesible desde el móvil en la WiFi de casa)
Abrir:     http://localhost:8000 (Mac) · móvil: en el Mac pulsa 📱 (/movil) y escanea el QR (misma WiFi)
"""

import os
import secrets
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

load_dotenv(Path(__file__).parent.parent / ".env")  # reutilizamos el .env del proyecto

import db  # noqa: E402
import enrich  # noqa: E402
import strava  # noqa: E402
import views  # noqa: E402

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
REDIRECT_URI = f"{BASE_URL}/callback"

app = FastAPI(title="Entrenador de triatlón")
# La sesión es una cookie firmada: el navegador guarda "soy el atleta X" y
# no la puede falsificar sin conocer SESSION_SECRET.
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
# max_age: la sesión dura 180 días (que el móvil no tenga que volver a vincularse cada dos semanas)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=180 * 24 * 3600)
db.init()


def page(body):
    return HTMLResponse(views.page(body))


@app.get("/", response_class=HTMLResponse)
def home(request: Request, sport: str = None, offset: int = 0):
    athlete_id = request.session.get("athlete_id")
    athlete = db.get_athlete(athlete_id) if athlete_id else None
    if not athlete:
        return page("""<h1>Entrenador de triatlón</h1>
<p>Conecta tu cuenta de Strava para importar tu histórico.</p>
<p><a class="btn" href="/login">Conectar con Strava</a></p>""")
    return HTMLResponse(views.home_page(athlete, sport, max(0, offset)))


@app.get("/activity/{activity_id}", response_class=HTMLResponse)
def activity(request: Request, activity_id: int):
    athlete_id = request.session.get("athlete_id")
    html = views.activity_page(athlete_id, activity_id) if athlete_id else None
    if not html:
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(html)


def _athlete(request):
    aid = request.session.get("athlete_id")
    return aid if aid and db.get_athlete(aid) else None


@app.get("/plan", response_class=HTMLResponse)
def plan(request: Request, w: int = None):
    aid = _athlete(request)
    return HTMLResponse(views.plan_page(aid, week=w)) if aid else RedirectResponse("/", status_code=303)


@app.get("/prevision", response_class=HTMLResponse)
def prevision(request: Request):
    aid = _athlete(request)
    return HTMLResponse(views.forecast_page(aid)) if aid else RedirectResponse("/", status_code=303)


@app.get("/plan/sesion/{session_id}", response_class=HTMLResponse)
def plan_session(request: Request, session_id: int):
    aid = _athlete(request)
    html = views.session_page(aid, session_id) if aid else None
    return HTMLResponse(html) if html else RedirectResponse("/plan", status_code=303)


@app.get("/ritmos", response_class=HTMLResponse)
def ritmos(request: Request):
    aid = _athlete(request)
    return HTMLResponse(views.paces_page(aid)) if aid else RedirectResponse("/", status_code=303)


@app.post("/ritmos/test")
async def ritmos_test(request: Request):
    import paces
    from datetime import date
    aid = _athlete(request)
    if not aid:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    try:
        parts = [int(x) for x in str(form.get("time", "")).strip().split(":")]
        secs = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
        dist = float(form.get("distance_m"))
        if not (60 <= secs <= 6 * 3600):
            raise ValueError
    except (ValueError, IndexError, TypeError):
        return HTMLResponse(views.paces_page(aid, '<p class="err">Tiempo no válido: usa mm:ss (p. ej. 21:30).</p>'))
    vdot = round(paces.vdot_from_race(dist, secs), 1)
    day = form.get("day") or date.today().isoformat()
    note = str(form.get("note") or "").strip()[:80]
    src = f"{note + ': ' if note else ''}{dist/1000:g} km en {paces.fmt_time(secs)} ({day})"
    db.set_vdot(aid, vdot, src, day)
    return HTMLResponse(views.paces_page(aid, f'<p class="st-done"><b>✓ Nuevo VDOT {vdot}</b>: ritmos del plan actualizados.</p>'))


# ------------------------------------------------- abrir la app en el móvil
# El login de Strava solo admite un dominio de callback (localhost). Para el
# móvil, el Mac (ya identificado) genera un enlace firmado de un solo uso que
# caduca en 10 min; al abrirlo, el móvil queda con la misma sesión.

def _pair_serializer():
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(SESSION_SECRET, salt="pair-device")


def _lan_hosts():
    import socket
    hosts = []
    try:
        import subprocess
        name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip()
        if name:
            hosts.append(f"{name}.local")
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        hosts.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return hosts


@app.get("/movil", response_class=HTMLResponse)
def movil(request: Request):
    import io
    import time
    import qrcode
    import qrcode.image.svg
    aid = _athlete(request)
    if not aid:
        return RedirectResponse("/", status_code=303)
    token = _pair_serializer().dumps({"aid": aid, "n": secrets.token_hex(4), "t": int(time.time())})
    links = [f"http://{h}:8000/pair/{token}" for h in _lan_hosts()]
    if not links:
        return page('<p class="err">No encuentro la red local del Mac.</p>')
    buf = io.BytesIO()
    qrcode.make(links[-1], image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2).save(buf)
    svg = buf.getvalue().decode().replace("<svg ", '<svg style="width:260px;height:260px;background:#fff;border-radius:8px" ', 1)
    alts = "".join(f'<li><a href="{escape(u)}">{escape(u.split("/pair/")[0])}</a></li>' for u in links)
    return HTMLResponse(views.page(f"""{views.nav('')}<h1>Abrir en el móvil</h1>
<p class="ink2">Con el móvil conectado a la <b>misma WiFi</b>, escanea el código con la cámara. Entrarás con tu sesión,
sin volver a conectar Strava. El código caduca en 10 minutos y solo sirve una vez.</p>
<div style="margin:1rem 0">{svg}</div>
<p class="explain">Si el código no abre, envíate uno de estos enlaces y ábrelo en el móvil (mismo código, distinto
nombre del Mac):</p><ul class="explain">{alts}</ul>
<p class="explain">Consejo: una vez dentro, en Safari pulsa Compartir → «Añadir a pantalla de inicio».</p>""",
        title="Abrir en el móvil", head=f"<style>{views.PLAN_CSS}</style>"))


_used_pair_tokens = set()


@app.get("/pair/{token}")
def pair(request: Request, token: str):
    from itsdangerous import BadSignature, SignatureExpired
    try:
        data = _pair_serializer().loads(token, max_age=600)
    except SignatureExpired:
        return page('<p class="err">El código ha caducado. Genera otro en el Mac (Abrir en el móvil).</p>')
    except BadSignature:
        return page('<p class="err">Código no válido.</p>')
    if token in _used_pair_tokens or not db.get_athlete(data["aid"]):
        return page('<p class="err">Este código ya se ha usado. Genera otro en el Mac.</p>')
    _used_pair_tokens.add(token)
    request.session["athlete_id"] = data["aid"]
    return RedirectResponse("/", status_code=303)


@app.get("/login")
def login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(strava.authorize_url(REDIRECT_URI, state))


@app.get("/callback")
def callback(request: Request, background: BackgroundTasks,
             code: str = None, state: str = None, error: str = None, scope: str = ""):
    if error:
        return page(f'<p class="err">Strava ha denegado el acceso: {escape(error)}</p><a href="/">Volver</a>')
    if not state or state != request.session.pop("oauth_state", None):
        return page('<p class="err">Estado OAuth inválido. Vuelve a intentarlo.</p><a href="/">Volver</a>')
    if "activity:read" not in scope:
        return page('<p class="err">Necesitamos permiso para leer tus actividades. '
                    'Marca la casilla de actividades al autorizar.</p><a href="/login">Reintentar</a>')

    token = strava.exchange_code(code)
    athlete_id = db.upsert_athlete(token)
    request.session["athlete_id"] = athlete_id
    background.add_task(strava.sync_athlete, athlete_id)  # el histórico se descarga en segundo plano
    background.add_task(enrich.enrich_athlete, athlete_id)  # y luego el detalle de cada actividad
    return RedirectResponse("/", status_code=303)


@app.get("/sync")
def sync(request: Request, background: BackgroundTasks):
    athlete_id = request.session.get("athlete_id")
    if athlete_id and db.get_athlete(athlete_id):
        background.add_task(strava.sync_athlete, athlete_id)
        background.add_task(enrich.enrich_athlete, athlete_id)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
