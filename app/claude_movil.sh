#!/bin/zsh
# Abre una sesión de Claude Code en este proyecto que se puede usar desde la
# app de Claude del móvil (o claude.ai/code): Remote Control.
# La sesión corre en este Mac (Garmin, Strava, app, ficheros); el móvil es la pantalla.
# `caffeinate` evita que el Mac se duerma mientras está abierta.
#
# Uso:  zsh app/claude_movil.sh          (Ctrl+C para cerrarla)
#       zsh app/claude_movil.sh -c       (reengancharse a la última sesión, <4 h)

cd /Users/pauchicharro/Documents/Claude || exit 1
CLAUDE_BIN=$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)
if [[ -z "$CLAUDE_BIN" ]]; then
  echo "No encuentro Claude Code (extensión de VS Code)."
  exit 1
fi
exec caffeinate -i "$CLAUDE_BIN" remote-control --name "Entrenador" --permission-mode auto "$@"
