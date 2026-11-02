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
