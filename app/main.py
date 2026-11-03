"""Servidor web del entrenador de triatlón (piloto).

Arrancar:  cd app && .venv/bin/uvicorn main:app --reload --port 8000
Abrir:     http://localhost:8000
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
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET") or secrets.token_hex(32))
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
def plan(request: Request):
    aid = _athlete(request)
    return HTMLResponse(views.plan_page(aid)) if aid else RedirectResponse("/", status_code=303)


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
