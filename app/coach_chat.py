"""Chat con el entrenador desde la app (móvil incluido).

Cada mensaje lanza Claude Code sin interfaz en este Mac, en la carpeta del
proyecto (lee CLAUDE.md, el plan, los datos de Garmin…), con permisos solo para
lo que necesita un entrenador: leer, editar el plan, regenerar, subir a Garmin
y publicar. La conversación continúa entre mensajes (--resume) durante 12 h.
Va con la suscripción de Claude del usuario: no usa la API.
"""

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import db

ROOT = Path(__file__).parent.parent
TIMEOUT_S = 15 * 60
CONTINUE_HOURS = 12
_lock = threading.Lock()

ALLOWED_TOOLS = [
    "Read", "Edit", "Write", "Glob", "Grep",
    "Bash(app/.venv/bin/python app/plan_tool.py:*)", "Bash(app/.venv/bin/python app/coach_summary.py:*)",
    "Bash(app/.venv/bin/python app/steps_from_text.py:*)", "Bash(app/.venv/bin/python app/garmin_source.py:*)",
    "Bash(.venv/bin/python app/plan_sync.py:*)", "Bash(.venv/bin/python app/garmin_workouts.py:*)",
    "Bash(.venv/bin/python generate_site.py:*)", "Bash(sqlite3 -readonly:*)",
    "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)", "Bash(git pull:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
]

PREAMBLE = """Eres el entrenador de este proyecto (sigue CLAUDE.md). El atleta te escribe desde el chat de la app,
normalmente desde el móvil. Hoy es {today}.

- Responde en castellano, breve y directo (se lee en el móvil): sin tablas anchas; listas cortas si hace falta.
- Si te pide información, usa los datos (data/, `app/.venv/bin/python app/coach_summary.py` y luego
  data/app_summary.md, o sqlite3 -readonly app/app.db). No inventes.
- Si hay que cambiar el plan: edita el JSON de data/plans/, añade una entrada a `revisions` y a data/log.md,
  valida (`app/.venv/bin/python app/plan_tool.py validate <json>`) y publica todo con
  `.venv/bin/python app/plan_sync.py` (importa, sube los próximos 7 días a Garmin, regenera la web y hace push).
  Commit de data/plans y data/log.md antes de plan_sync.
- Carrera siempre por tiempo (minutos), salvo tests y carreras.
- Sé crítico si lo que propone no tiene sentido para su entrenamiento: dilo, con el coste y una alternativa.
- Al final di en una línea qué has cambiado (o «sin cambios»).

Mensaje del atleta:
"""


def _claude_bin():
    found = sorted(Path.home().glob(".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude"))
    return str(found[-1]) if found else None


def messages(limit=40):
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM chat_messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return list(reversed(rows))


def busy():
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE status='pending'").fetchone()[0] > 0


def _last_session():
    since = (datetime.utcnow() - timedelta(hours=CONTINUE_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    with db.connect() as conn:
        r = conn.execute("SELECT claude_session FROM chat_messages WHERE role='coach' AND claude_session IS NOT NULL "
                         "AND created_at >= ? ORDER BY id DESC LIMIT 1", (since,)).fetchone()
    return r[0] if r else None


def send(text):
    """Guarda el mensaje y lanza la respuesta en segundo plano. Devuelve False si ya hay una en curso."""
    if busy():
        return False
    with db.connect() as conn:
        conn.execute("INSERT INTO chat_messages (role, text, status) VALUES ('user', ?, 'done')", (text,))
        cur = conn.execute("INSERT INTO chat_messages (role, text, status) VALUES ('coach', '', 'pending')")
        reply_id = cur.lastrowid
    threading.Thread(target=_run, args=(text, reply_id), daemon=True).start()
    return True


def new_conversation():
    with db.connect() as conn:
        conn.execute("UPDATE chat_messages SET claude_session=NULL WHERE claude_session IS NOT NULL")
        conn.execute("INSERT INTO chat_messages (role, text, status) VALUES ('system', 'Nueva conversación', 'done')")


def _run(text, reply_id):
    with _lock:
        started = time.time()
        bin_ = _claude_bin()
        if not bin_:
            return _finish(reply_id, "No encuentro Claude Code en este Mac.", None, "error")
        session = _last_session()
        prompt = (PREAMBLE.format(today=datetime.now().strftime("%A %d/%m/%Y")) if not session else "") + text
        cmd = [bin_, "-p", prompt, "--output-format", "json", "--max-turns", "60",
               "--allowedTools", *ALLOWED_TOOLS]
        if session:
            cmd += ["--resume", session]
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT_S)
            out = json.loads(r.stdout or "{}")
            answer = out.get("result") or (r.stderr.strip()[-500:] or "Sin respuesta.")
            status = "error" if out.get("is_error") or r.returncode != 0 else "done"
            _finish(reply_id, answer, out.get("session_id"), status, time.time() - started)
        except subprocess.TimeoutExpired:
            _finish(reply_id, "He tardado demasiado y lo he cortado. Prueba a pedirlo en partes.", session, "error")
        except Exception as e:  # nunca dejar el mensaje colgado en «pensando…»
            _finish(reply_id, f"Error: {e}", session, "error")


def _finish(reply_id, text, session, status, secs=None):
    with db.connect() as conn:
        conn.execute("UPDATE chat_messages SET text=?, claude_session=?, status=?, seconds=? WHERE id=?",
                     (text, session, status, round(secs) if secs else None, reply_id))
