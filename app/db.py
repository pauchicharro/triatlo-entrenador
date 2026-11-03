"""Base de datos SQLite de la app.

Diseñada ya pensando en varios usuarios: cada atleta tiene sus propios tokens
y cada actividad apunta a su atleta. Para el piloto basta SQLite (un solo
fichero); al escalar se cambia por Postgres sin tocar mucho más.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS athletes (
    id              INTEGER PRIMARY KEY,      -- id de atleta en Strava
    firstname       TEXT,
    lastname        TEXT,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT NOT NULL,
    expires_at      INTEGER NOT NULL,         -- epoch (segundos)
    scope           TEXT,
    sync_status     TEXT DEFAULT 'pending',   -- pending | syncing | done | error
    sync_message    TEXT,
    last_synced_at  TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activities (
    id                  INTEGER PRIMARY KEY,  -- id de actividad en Strava
    athlete_id          INTEGER NOT NULL REFERENCES athletes(id),
    name                TEXT,
    sport_type          TEXT,
    start_date_local    TEXT,
    distance_m          REAL,
    moving_time_s       INTEGER,
    elevation_gain_m    REAL,
    average_heartrate   REAL,
    max_heartrate       REAL,
    average_speed       REAL,
    raw                 TEXT                  -- JSON completo, por si luego necesitamos más campos
);

CREATE INDEX IF NOT EXISTS idx_activities_athlete_date
    ON activities (athlete_id, start_date_local);

-- Detalle completo de cada actividad (/activities/{id}) + series temporales.
-- Las columnas sueltas son las más usadas; el resto está en detail (JSON
-- comprimido con zlib) y streams (idem), para no perder nada.
CREATE TABLE IF NOT EXISTS activity_details (
    activity_id         INTEGER PRIMARY KEY REFERENCES activities(id),
    elapsed_time_s      INTEGER,
    calories            REAL,
    perceived_exertion  REAL,       -- RPE 1-10 si el atleta lo apunta
    suffer_score        REAL,       -- "esfuerzo relativo" de Strava
    workout_type        INTEGER,    -- carrera/tirada larga/entreno (Strava)
    average_cadence     REAL,
    average_watts       REAL,
    weighted_average_watts REAL,
    kilojoules          REAL,
    max_speed           REAL,
    average_temp        REAL,
    trainer             INTEGER,    -- rodillo / cinta
    device_name         TEXT,
    gear_id             TEXT,
    description         TEXT,
    laps                TEXT,       -- JSON: vueltas / series del reloj
    splits_metric       TEXT,       -- JSON: parciales por km
    best_efforts        TEXT,       -- JSON: mejores marcas (400 m, 1 km, 5 km…)
    detail              BLOB,       -- JSON completo comprimido
    streams             BLOB,       -- series temporales comprimidas
    fetched_at          TEXT DEFAULT (datetime('now'))
);

-- Métricas calculadas a partir de los streams (no gastan API).
CREATE TABLE IF NOT EXISTS activity_metrics (
    activity_id         INTEGER PRIMARY KEY REFERENCES activities(id),
    hr_z1_s INTEGER, hr_z2_s INTEGER, hr_z3_s INTEGER, hr_z4_s INTEGER, hr_z5_s INTEGER,
    trimp_edwards       REAL,
    decoupling_pct      REAL,       -- desacople aeróbico 1ª vs 2ª mitad
    efficiency_factor   REAL,
    cadence_avg         REAL,       -- carrera en pasos/min (dos piernas)
    watts_np            REAL,
    temp_avg            REAL,
    zones_source        TEXT,
    metrics             TEXT        -- JSON con todo lo calculado
);

-- Objetivo (carrera) del atleta. Solo uno activo a la vez.
CREATE TABLE IF NOT EXISTS goals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    athlete_id      INTEGER NOT NULL REFERENCES athletes(id),
    name            TEXT NOT NULL,
    race_date       TEXT NOT NULL,
    distance_m      REAL NOT NULL,
    target_time_s   INTEGER,
    active          INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Historial de VDOT (forma en carrera): de él salen todos los ritmos del plan.
CREATE TABLE IF NOT EXISTS fitness (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    athlete_id  INTEGER NOT NULL REFERENCES athletes(id),
    vdot        REAL NOT NULL,
    source      TEXT,           -- "estimación inicial", "test 5K 08/11"...
    set_on      TEXT DEFAULT (date('now'))
);

-- Plan generado (por Claude Code ahora; por la API más adelante). El JSON
-- completo es la fuente; plan_sessions es la versión "aplanada" para consultar.
CREATE TABLE IF NOT EXISTS plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    athlete_id  INTEGER NOT NULL REFERENCES athletes(id),
    goal_id     INTEGER REFERENCES goals(id),
    generator   TEXT,
    plan_json   TEXT NOT NULL,
    active      INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id     INTEGER NOT NULL REFERENCES plans(id),
    date        TEXT NOT NULL,
    seq         INTEGER NOT NULL,       -- orden dentro del día
    sport       TEXT NOT NULL,          -- run | swim | bike | gym | rest | race
    title       TEXT,
    key_session INTEGER DEFAULT 0,
    session     TEXT NOT NULL           -- JSON de la sesión
);
CREATE INDEX IF NOT EXISTS idx_plan_sessions_date ON plan_sessions (plan_id, date);

CREATE TABLE IF NOT EXISTS athlete_zones (
    athlete_id  INTEGER PRIMARY KEY REFERENCES athletes(id),
    zones       BLOB,
    source      TEXT,
    fetched_at  TEXT DEFAULT (datetime('now'))
);
"""

MIGRATIONS = [
    "ALTER TABLE activities ADD COLUMN enrich_status TEXT",   # NULL = pendiente
    "ALTER TABLE athletes ADD COLUMN enrich_error TEXT",
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)
        for sql in MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # la columna ya existe


def upsert_athlete(token):
    """Guarda (o actualiza) un atleta a partir de la respuesta de /oauth/token."""
    a = token["athlete"]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO athletes (id, firstname, lastname, access_token, refresh_token, expires_at, scope)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                firstname=excluded.firstname, lastname=excluded.lastname,
                access_token=excluded.access_token, refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at, scope=excluded.scope
            """,
            (a["id"], a.get("firstname"), a.get("lastname"), token["access_token"],
             token["refresh_token"], token["expires_at"], token.get("scope")),
        )
    return a["id"]


def get_athlete(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM athletes WHERE id = ?", (athlete_id,)).fetchone()


def update_tokens(athlete_id, access_token, refresh_token, expires_at):
    with connect() as conn:
        conn.execute(
            "UPDATE athletes SET access_token=?, refresh_token=?, expires_at=? WHERE id=?",
            (access_token, refresh_token, expires_at, athlete_id),
        )


def set_sync_status(athlete_id, status, message=None):
    with connect() as conn:
        conn.execute(
            """UPDATE athletes SET sync_status=?, sync_message=?,
               last_synced_at = CASE WHEN ?='done' THEN datetime('now') ELSE last_synced_at END
               WHERE id=?""",
            (status, message, status, athlete_id),
        )


def latest_activity_date(athlete_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT MAX(start_date_local) AS d FROM activities WHERE athlete_id=?", (athlete_id,)
        ).fetchone()
        return row["d"]


def save_activities(athlete_id, activities):
    rows = [
        (
            a["id"], athlete_id, a.get("name"), a.get("sport_type") or a.get("type"),
            a.get("start_date_local"), a.get("distance"), a.get("moving_time"),
            a.get("total_elevation_gain"), a.get("average_heartrate"),
            a.get("max_heartrate"), a.get("average_speed"), json.dumps(a),
        )
        for a in activities
    ]
    with connect() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO activities
               (id, athlete_id, name, sport_type, start_date_local, distance_m, moving_time_s,
                elevation_gain_m, average_heartrate, max_heartrate, average_speed, raw)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )


def list_activities(athlete_id, limit=50):
    with connect() as conn:
        return conn.execute(
            """SELECT * FROM activities WHERE athlete_id=?
               ORDER BY start_date_local DESC LIMIT ?""",
            (athlete_id, limit),
        ).fetchall()


def activity_summary(athlete_id):
    with connect() as conn:
        return conn.execute(
            """SELECT sport_type, COUNT(*) AS n, SUM(distance_m) AS dist, SUM(moving_time_s) AS secs,
                      MIN(start_date_local) AS first, MAX(start_date_local) AS last
               FROM activities WHERE athlete_id=? GROUP BY sport_type ORDER BY n DESC""",
            (athlete_id,),
        ).fetchall()


# ------------------------------------------------------------- enriquecimiento

def all_athletes():
    with connect() as conn:
        return conn.execute("SELECT * FROM athletes").fetchall()


def activities_pending_enrichment(athlete_id):
    with connect() as conn:
        return conn.execute(
            """SELECT id, sport_type, start_date_local FROM activities
               WHERE athlete_id=? AND enrich_status IS NULL
               ORDER BY start_date_local DESC""",
            (athlete_id,),
        ).fetchall()


def save_detail(activity_id, d, detail_blob, streams_blob):
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO activity_details
               (activity_id, elapsed_time_s, calories, perceived_exertion, suffer_score, workout_type,
                average_cadence, average_watts, weighted_average_watts, kilojoules, max_speed,
                average_temp, trainer, device_name, gear_id, description, laps, splits_metric,
                best_efforts, detail, streams)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (activity_id, d.get("elapsed_time"), d.get("calories"), d.get("perceived_exertion"),
             d.get("suffer_score"), d.get("workout_type"), d.get("average_cadence"),
             d.get("average_watts"), d.get("weighted_average_watts"), d.get("kilojoules"),
             d.get("max_speed"), d.get("average_temp"), int(bool(d.get("trainer"))),
             d.get("device_name"), d.get("gear_id"), d.get("description"),
             json.dumps(d.get("laps") or []), json.dumps(d.get("splits_metric") or []),
             json.dumps(d.get("best_efforts") or []), detail_blob, streams_blob),
        )


def save_metrics(activity_id, m, zones_source):
    z = m.get("hr_zone_s") or [None] * 5
    z = (list(z) + [None] * 5)[:5]
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO activity_metrics
               (activity_id, hr_z1_s, hr_z2_s, hr_z3_s, hr_z4_s, hr_z5_s, trimp_edwards,
                decoupling_pct, efficiency_factor, cadence_avg, watts_np, temp_avg, zones_source, metrics)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (activity_id, *z, m.get("trimp_edwards"), m.get("decoupling_pct"),
             m.get("efficiency_factor"), m.get("cadence_avg"), m.get("watts_np"),
             m.get("temp_avg"), zones_source, json.dumps(m)),
        )


def mark_enriched(activity_id, status):
    with connect() as conn:
        conn.execute("UPDATE activities SET enrich_status=? WHERE id=?", (status, activity_id))


def set_enrich_status(athlete_id, error):
    with connect() as conn:
        conn.execute("UPDATE athletes SET enrich_error=? WHERE id=?", (error, athlete_id))


def enrich_progress(athlete_id):
    with connect() as conn:
        return conn.execute(
            """SELECT COUNT(*) AS total, SUM(enrich_status IS NOT NULL) AS done,
                      SUM(enrich_status='ok') AS with_streams
               FROM activities WHERE athlete_id=?""",
            (athlete_id,),
        ).fetchone()


def save_athlete_zones(athlete_id, zones, source):
    import zlib
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO athlete_zones (athlete_id, zones, source) VALUES (?,?,?)",
            (athlete_id, zlib.compress(json.dumps(zones).encode()), source),
        )


def get_athlete_zones(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM athlete_zones WHERE athlete_id=?", (athlete_id,)).fetchone()


def estimated_hr_max(athlete_id):
    """FC máx estimada: 3er valor más alto de FC sostenida 60 s en carrera (2 años).

    Usamos el 3º y no el 1º porque los pulsómetros (sobre todo de muñeca) a veces
    se enganchan a la cadencia y dan minutos enteros falsamente altos.
    """
    with connect() as conn:
        vals = [r[0] for r in conn.execute(
            """SELECT json_extract(m.metrics,'$.hr_max_60s') AS v
               FROM activity_metrics m JOIN activities a ON a.id=m.activity_id
               WHERE a.athlete_id=? AND a.start_date_local >= date('now','-2 years')
                 AND a.sport_type IN ('Run','TrailRun') AND v BETWEEN 140 AND 210
               ORDER BY v DESC LIMIT 3""",
            (athlete_id,))]
    return round(vals[-1]) if len(vals) == 3 else None


def activities_with_streams(athlete_id):
    with connect() as conn:
        return conn.execute(
            """SELECT a.id, a.sport_type, d.streams,
                      COALESCE(json_extract(a.raw, '$.device_watts'), 0) AS device_watts
               FROM activities a
               JOIN activity_details d ON d.activity_id=a.id
               WHERE a.athlete_id=? AND d.streams IS NOT NULL""",
            (athlete_id,),
        ).fetchall()


def get_activity_full(athlete_id, activity_id):
    with connect() as conn:
        return conn.execute(
            """SELECT a.*, d.*, m.metrics, m.zones_source FROM activities a
               LEFT JOIN activity_details d ON d.activity_id=a.id
               LEFT JOIN activity_metrics m ON m.activity_id=a.id
               WHERE a.athlete_id=? AND a.id=?""",
            (athlete_id, activity_id),
        ).fetchone()


def list_activities_with_metrics(athlete_id, limit=50, offset=0, sport=None):
    q = """SELECT a.*, m.trimp_edwards, m.hr_z1_s, m.hr_z2_s, m.hr_z3_s, m.hr_z4_s, m.hr_z5_s
           FROM activities a LEFT JOIN activity_metrics m ON m.activity_id=a.id
           WHERE a.athlete_id=?"""
    args = [athlete_id]
    if sport:
        q += " AND a.sport_type=?"
        args.append(sport)
    q += " ORDER BY a.start_date_local DESC LIMIT ? OFFSET ?"
    with connect() as conn:
        return conn.execute(q, (*args, limit, offset)).fetchall()


def weekly_volume(athlete_id, weeks=26):
    """Horas por semana y disciplina (lunes como inicio de semana)."""
    with connect() as conn:
        return conn.execute(
            """SELECT date(substr(start_date_local,1,10), 'weekday 0', '-6 days') AS week,
                      CASE WHEN sport_type IN ('Swim') THEN 'swim'
                           WHEN sport_type IN ('Ride','VirtualRide','GravelRide','MountainBikeRide','EBikeRide') THEN 'bike'
                           WHEN sport_type IN ('Run','TrailRun','VirtualRun') THEN 'run'
                           WHEN sport_type IN ('WeightTraining','Workout','Crossfit','Yoga') THEN 'gym'
                           ELSE 'other' END AS disc,
                      SUM(moving_time_s)/3600.0 AS hours, SUM(distance_m)/1000.0 AS km
               FROM activities WHERE athlete_id=?
                 AND start_date_local >= date('now', ?)
               GROUP BY week, disc ORDER BY week""",
            (athlete_id, f"-{weeks * 7 + 6} days"),
        ).fetchall()


# ----------------------------------------------------------- objetivo y plan

def active_goal(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM goals WHERE athlete_id=? AND active=1 ORDER BY id DESC LIMIT 1",
                            (athlete_id,)).fetchone()


def current_vdot(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM fitness WHERE athlete_id=? ORDER BY set_on DESC, id DESC LIMIT 1",
                            (athlete_id,)).fetchone()


def vdot_history(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM fitness WHERE athlete_id=? ORDER BY set_on, id", (athlete_id,)).fetchall()


def set_vdot(athlete_id, vdot, source, set_on=None):
    with connect() as conn:
        conn.execute("INSERT INTO fitness (athlete_id, vdot, source, set_on) VALUES (?,?,?,COALESCE(?, date('now')))",
                     (athlete_id, vdot, source, set_on))


def active_plan(athlete_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM plans WHERE athlete_id=? AND active=1 ORDER BY id DESC LIMIT 1",
                            (athlete_id,)).fetchone()


def plan_sessions(plan_id, date_from=None, date_to=None):
    q, args = "SELECT * FROM plan_sessions WHERE plan_id=?", [plan_id]
    if date_from:
        q += " AND date>=?"; args.append(date_from)
    if date_to:
        q += " AND date<=?"; args.append(date_to)
    with connect() as conn:
        return conn.execute(q + " ORDER BY date, seq", args).fetchall()


def plan_session(session_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM plan_sessions WHERE id=?", (session_id,)).fetchone()


def activities_between(athlete_id, d_from, d_to):
    with connect() as conn:
        return conn.execute(
            """SELECT a.*, m.metrics, m.trimp_edwards, d.laps FROM activities a
               LEFT JOIN activity_metrics m ON m.activity_id=a.id
               LEFT JOIN activity_details d ON d.activity_id=a.id
               WHERE a.athlete_id=? AND substr(a.start_date_local,1,10) BETWEEN ? AND ?
               ORDER BY a.start_date_local""",
            (athlete_id, d_from, d_to)).fetchall()
