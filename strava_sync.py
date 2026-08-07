"""Sincronitza l'historic d'activitats de Strava a data/strava/.

Primer ús: cal crear una app a https://www.strava.com/settings/api amb
Authorization Callback Domain = localhost, i posar STRAVA_CLIENT_ID /
STRAVA_CLIENT_SECRET a .env. El script obrirà el navegador per autoritzar
i desarà el refresh token a .env automàticament.

Fa servir l'API REST de Strava directament (via `requests`) en lloc de
stravalib, per evitar conflictes de versió de pydantic amb la llibreria
de Garmin.
"""

import csv
import json
import os
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
ENV_PATH = ROOT / ".env"
DATA_DIR = ROOT / "data" / "strava"
ACTIVITIES_DIR = DATA_DIR / "activities"
ACTIVITIES_CSV = DATA_DIR / "activities.csv"
REDIRECT_PORT = 8000
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/authorized"

OAUTH_TOKEN_URL = "https://www.strava.com/oauth/token"
OAUTH_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"

CSV_FIELDS = [
    "id", "name", "type", "start_date_local", "distance_m",
    "moving_time_s", "total_elevation_gain_m", "average_heartrate",
    "max_heartrate", "average_speed",
]


def _capture_auth_code():
    code = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            code["value"] = qs.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Autoritzat! Ja pots tancar aquesta pestanya.")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", REDIRECT_PORT), Handler)
    server.handle_request()
    return code.get("value")


def _update_env(key, value):
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def authenticate():
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    if not client_id or not client_secret:
        raise SystemExit(
            "Cal STRAVA_CLIENT_ID i STRAVA_CLIENT_SECRET a .env "
            "(crea una app a https://www.strava.com/settings/api)."
        )

    if not refresh_token:
        params = {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "read_all,activity:read_all",
            "approval_prompt": "auto",
        }
        url = requests.Request("GET", OAUTH_AUTHORIZE_URL, params=params).prepare().url
        print(f"Obrint navegador per autoritzar: {url}")
        webbrowser.open(url)
        code = _capture_auth_code()
        if not code:
            raise SystemExit("No s'ha rebut el codi d'autoritzacio.")

        resp = requests.post(OAUTH_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        token = resp.json()
        _update_env("STRAVA_REFRESH_TOKEN", token["refresh_token"])
        return token["access_token"]

    resp = requests.post(OAUTH_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    token = resp.json()
    if token.get("refresh_token") and token["refresh_token"] != refresh_token:
        _update_env("STRAVA_REFRESH_TOKEN", token["refresh_token"])
    return token["access_token"]


def fetch_activities(access_token, after=None):
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": 100, "page": 1}
    if after:
        params["after"] = int(datetime.fromisoformat(after.replace("Z", "+00:00")).timestamp())

    activities = []
    while True:
        resp = requests.get(ACTIVITIES_URL, headers=headers, params=params)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        activities.extend(page)
        params["page"] += 1
    return activities


def sync_activities(access_token):
    ACTIVITIES_DIR.mkdir(parents=True, exist_ok=True)

    existing = {}
    last_date = None
    if ACTIVITIES_CSV.exists():
        with open(ACTIVITIES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                existing[row["id"]] = row
                if row["start_date_local"] and (
                    last_date is None or row["start_date_local"] > last_date
                ):
                    last_date = row["start_date_local"]

    activities = fetch_activities(access_token, after=last_date)

    for data in activities:
        activity_id = str(data["id"])
        with open(ACTIVITIES_DIR / f"{activity_id}.json", "w") as f:
            json.dump(data, f, indent=2)

        existing[activity_id] = {
            "id": activity_id,
            "name": data.get("name"),
            "type": data.get("type") or data.get("sport_type"),
            "start_date_local": data.get("start_date_local"),
            "distance_m": data.get("distance"),
            "moving_time_s": data.get("moving_time"),
            "total_elevation_gain_m": data.get("total_elevation_gain"),
            "average_heartrate": data.get("average_heartrate"),
            "max_heartrate": data.get("max_heartrate"),
            "average_speed": data.get("average_speed"),
        }

    rows = sorted(existing.values(), key=lambda r: r.get("start_date_local") or "")
    with open(ACTIVITIES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(activities)} activitats noves, {len(rows)} en total a {ACTIVITIES_CSV}")


if __name__ == "__main__":
    strava_access_token = authenticate()
    sync_activities(strava_access_token)
