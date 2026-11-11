"""Sincronización horaria en el Mac: GitHub ↔ app ↔ Garmin.

Pensado para que el plan se pueda cambiar desde el móvil con una sesión de
Claude Code en la nube (claude.ai/code), que solo toca el repositorio. Cuando
el Mac está encendido, esto (launchd, cada hora):

  1. git pull: trae los cambios hechos desde la nube.
  2. Si el JSON del plan cambió → lo importa en la app (BD) y regenera el markdown.
     Si data/fitness.json trae un VDOT nuevo (test registrado desde la nube) → a la BD.
  3. Garmin: sube / actualiza / borra los entrenos de los próximos 7 días.
  4. Regenera la web pública y sube a GitHub lo que haya cambiado aquí
     (p. ej. un test apuntado en la app del Mac, o el estado de las sesiones).

Uso: .venv/bin/python app/plan_sync.py      (venv principal: tiene garminconnect)
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
import db  # noqa: E402
import plan_tool  # noqa: E402

PUBLISHED = ["data/training_plan.md", "data/fitness.json", "data/activity_days.json", "docs/index.html"]


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def notify(title, msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg[:200]}" with title "{title}"'],
                   capture_output=True)


def active_plan_file():
    """El JSON de data/plans/ que corresponde al plan activo (o el más reciente)."""
    aid = db.all_athletes()[0]["id"]
    row = db.active_plan(aid)
    files = sorted((ROOT / "data" / "plans").glob("*.json"), key=lambda f: f.stat().st_mtime)
    if row:
        name = json.loads(row["plan_json"])["goal"]["name"]
        same = [f for f in files if json.loads(f.read_text()).get("goal", {}).get("name") == name]
        if same and same[-1] == files[-1]:
            return same[-1]
    return files[-1] if files else None


def main():
    print(f"\n== {datetime.now():%Y-%m-%d %H:%M} plan_sync ==", flush=True)
    db.init()
    aid = db.all_athletes()[0]["id"]

    # 1. Cambios desde la nube
    try:
        git("pull", "--rebase", "--autostash", "-q")
    except RuntimeError as e:
        print(f"git pull falló: {e}")
        subprocess.run(["git", "rebase", "--abort"], cwd=ROOT, capture_output=True)
        notify("Entrenador: conflicto", "No he podido traer los cambios de GitHub (ver app/plan_sync.log)")
        return 1

    # 1b. Actividades y bienestar de Garmin
    try:
        import garmin_source
        import garmin_sync
        client = garmin_source.login()
        garmin_source.sync(days=3, client=client)
        garmin_sync.sync_wellness(client, 3)
    except Exception as e:
        print(f"Garmin (actividades) falló: {e}")

    # 2. Plan y VDOT → app
    path = active_plan_file()
    plan = json.loads(path.read_text())
    row = db.active_plan(aid)
    changed = not row or json.loads(row["plan_json"]) != plan
    if changed:
        errs = plan_tool.validate(plan)
        if errs:
            print("Plan inválido, no lo importo:\n- " + "\n- ".join(errs))
            notify("Entrenador: plan inválido", f"{path.name}: {errs[0]}")
            return 1
        plan_tool.import_plan(path, aid)
        print(f"Plan importado desde {path.name}")
    else:
        plan_tool.sync_fitness(aid)
    plan_tool.write_markdown(aid)

    # 3. Garmin (próximos 7 días)
    try:
        import garmin_workouts
        n = garmin_workouts.sync_window(7)
        if n and changed:
            notify("Plan actualizado", f"Cambios del plan aplicados y {n} entrenos actualizados en Garmin")
    except Exception as e:
        print(f"Garmin falló: {e}")

    # 4. Web pública + subir lo generado aquí
    subprocess.run([str(ROOT / ".venv" / "bin" / "python"), "generate_site.py"], cwd=ROOT, capture_output=True)
    git("add", *[p for p in PUBLISHED if (ROOT / p).exists()])
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        git("commit", "-q", "-m", "Sincronització automàtica del pla (Mac)\n\n"
            "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        git("push", "-q")
        print("Cambios publicados en GitHub")
    else:
        print("Nada que publicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
