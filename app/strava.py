"""Cliente de la API de Strava: OAuth + descarga de actividades.

Mismo flujo que strava_sync.py, pero pensado para un servidor con varios
usuarios: los tokens de cada atleta viven en la base de datos, no en .env.
"""

import os
import time
from datetime import datetime
from urllib.parse import urlencode

import requests

import db

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API = "https://www.strava.com/api/v3"
SCOPE = "read,activity:read_all,profile:read_all"  # profile:read_all → zonas de FC


class RateLimited(Exception):
    pass


def _client():
    return os.environ["STRAVA_CLIENT_ID"], os.environ["STRAVA_CLIENT_SECRET"]


def authorize_url(redirect_uri, state):
    """URL de la página de Strava donde el usuario acepta los permisos."""
    client_id, _ = _client()
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "approval_prompt": "auto",
        "state": state,  # protección CSRF: lo comprobamos al volver
    })


def exchange_code(code):
    """Cambia el `code` que nos devuelve Strava por los tokens del atleta."""
    client_id, client_secret = _client()
    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()


def valid_access_token(athlete_id):
    """Devuelve un access token válido, refrescándolo si caduca en <5 min."""
    athlete = db.get_athlete(athlete_id)
    if athlete["expires_at"] > time.time() + 300:
        return athlete["access_token"]

    client_id, client_secret = _client()
    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": athlete["refresh_token"],
    }, timeout=20)
    resp.raise_for_status()
    t = resp.json()
    db.update_tokens(athlete_id, t["access_token"], t["refresh_token"], t["expires_at"])
    return t["access_token"]


def _get(path, token, params):
    resp = requests.get(API + path, headers={"Authorization": f"Bearer {token}"},
                        params=params, timeout=30)
    if resp.status_code == 429:
        raise RateLimited(resp.headers.get("X-RateLimit-Usage", ""))
    if resp.status_code >= 400:
        raise RuntimeError(f"Strava {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def sync_athlete(athlete_id):
    """Descarga el histórico (o solo lo nuevo) del atleta y lo guarda en la BD.

    Se ejecuta en segundo plano tras el login, para que el usuario no espere.
    """
    db.set_sync_status(athlete_id, "syncing", "Descargando actividades…")
    try:
        token = valid_access_token(athlete_id)
        params = {"per_page": 200, "page": 1}
        last = db.latest_activity_date(athlete_id)
        if last:  # sincronización incremental
            params["after"] = int(datetime.fromisoformat(last.replace("Z", "")).timestamp()) - 86400

        total = 0
        while True:
            page = _get("/athlete/activities", token, params)
            if not page:
                break
            db.save_activities(athlete_id, page)
            total += len(page)
            db.set_sync_status(athlete_id, "syncing", f"{total} actividades descargadas…")
            params["page"] += 1

        db.set_sync_status(athlete_id, "done", f"{total} actividades nuevas o actualizadas")
    except RateLimited as e:
        db.set_sync_status(athlete_id, "error", f"Límite de Strava alcanzado ({e}). Reintenta en 15 min.")
    except Exception as e:
        db.set_sync_status(athlete_id, "error", str(e))
