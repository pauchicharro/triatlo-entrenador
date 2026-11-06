#!/bin/zsh
# Adaptación semanal del plan (la lanza launchd los domingos a las 20:00).
#   1. Sincroniza Strava y descarga el detalle de los últimos días.
#   2. Regenera el resumen para el entrenador.
#   3. Claude Code (sin interfaz) analiza la semana, adapta el plan, lo publica.
#   4. Notificación en el Mac con el resumen.
# Probar a mano:  zsh app/weekly_replan.sh

set -u
ROOT=/Users/pauchicharro/Documents/Claude
cd "$ROOT" || exit 1
LOG="$ROOT/app/replan.log"
exec >>"$LOG" 2>&1
echo "\n===== $(date '+%Y-%m-%d %H:%M') adaptación semanal ====="

notify() {
  /usr/bin/osascript -e "display notification \"${2//\"/\\\"}\" with title \"${1//\"/\\\"}\"" || true
}

# 1-2. Datos frescos (espera hasta 30 min si el proceso de fondo está descargando)
app/.venv/bin/python app/enrich.py --sync --since-days 10 --wait 30
app/.venv/bin/python app/coach_summary.py

# 3. Claude Code: la CLI viene con la extensión de VS Code; usamos la versión más reciente instalada
CLAUDE_BIN=$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)
if [[ -z "$CLAUDE_BIN" ]]; then
  echo "No encuentro la CLI de Claude Code"
  notify "Entrenador: error" "No encuentro Claude Code para adaptar el plan"
  exit 1
fi

PLAN=$(app/.venv/bin/python -c "
import json, sys; sys.path.insert(0, 'app')
import db
p = db.active_plan(db.all_athletes()[0]['id'])
g = json.loads(p['plan_json'])['goal']
import glob
for f in sorted(glob.glob('data/plans/*.json')):
    if json.load(open(f)).get('goal', {}).get('name') == g['name']:
        print(f); break
")
TODAY=$(date +%Y-%m-%d)
NEXT_MONDAY=$(date -v+mon +%Y-%m-%d)
[[ "$NEXT_MONDAY" == "$TODAY" ]] && NEXT_MONDAY=$(date -v+7d +%Y-%m-%d)

PROMPT=$(sed -e "s|{{PLAN}}|$PLAN|g" -e "s|{{TODAY}}|$TODAY|g" -e "s|{{NEXT_MONDAY}}|$NEXT_MONDAY|g" app/weekly_replan_prompt.md)
echo "Plan: $PLAN · hoy $TODAY · próximo lunes $NEXT_MONDAY"

OUT=$("$CLAUDE_BIN" -p "$PROMPT" --max-turns 80 \
  --allowedTools "Read" "Edit" "Write" "Glob" "Grep" \
  "Bash(app/.venv/bin/python app/plan_tool.py:*)" "Bash(app/.venv/bin/python app/coach_summary.py:*)" \
  "Bash(app/.venv/bin/python app/steps_from_text.py:*)" \
  "Bash(.venv/bin/python generate_site.py:*)" "Bash(sqlite3 -readonly:*)" \
  "Bash(git add:*)" "Bash(git commit:*)" "Bash(git push:*)" "Bash(git status:*)" "Bash(git diff:*)")
STATUS=$?
echo "$OUT"

# 4. Subir a Garmin la semana nueva (y lo que haya cambiado)
.venv/bin/python app/plan_sync.py

# 5. Aviso
if [[ $STATUS -eq 0 && -n "$OUT" ]]; then
  notify "Plan de la semana adaptado" "$(echo "$OUT" | tail -3 | tr '\n' ' ' | cut -c1-220)"
else
  notify "Entrenador: error" "La adaptación semanal ha fallado (ver app/replan.log)"
fi
