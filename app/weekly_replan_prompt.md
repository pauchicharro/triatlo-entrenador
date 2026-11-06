Eres el entrenador de este proyecto (sigue CLAUDE.md). Hoy es domingo y toca la **adaptación semanal
del plan**. Trabajas sin supervisión: no preguntes nada, decide como entrenador y deja todo publicado.

Ya se han sincronizado las actividades de Strava y se ha regenerado `data/app_summary.md`.
El JSON del plan activo es: {{PLAN}}. Hoy: {{TODAY}}. El próximo lunes: {{NEXT_MONDAY}}.

## 1. Analiza (sin inventar datos)
- Lee `data/athlete_profile.md`, `data/app_summary.md` (sobre todo la sección 0: cumplimiento de los últimos
  14 días, sesiones clave, rodajes con FC alta; y carga CTL/ATL/TSB, saltos de volumen, distribución por zonas)
  y el JSON del plan.
- Si quieres ver una sesión concreta (vueltas, ritmos de las series), consulta `app/app.db` con sqlite3 en
  modo solo lectura (tablas activities, activity_details.laps, activity_metrics.metrics).
- Si hay datos de Garmin recientes en `data/garmin/` (sueño, training status), tenlos en cuenta.

## 2. Tests
Si esta semana el plan tenía un test o carrera a tope y se hizo, saca el tiempo de la parte a tope (vuelta
o «mejor esfuerzo» de esa distancia en activity_details.best_efforts) y regístralo:
`app/.venv/bin/python app/plan_tool.py vdot-from-race <metros> <mm:ss> "<qué fue>" --date <YYYY-MM-DD>`.
Todos los ritmos del plan se recalculan solos. Comenta si el objetivo de tiempo sigue siendo realista.

## 3. Adapta el plan (edita el JSON)
- Cambia SOLO sesiones con fecha ≥ {{NEXT_MONDAY}}. Las pasadas no se tocan (sirven para medir el cumplimiento).
- La semana que empieza el {{NEXT_MONDAY}} debe quedar completamente detallada; ajusta las siguientes si hace
  falta. Reglas: subida de km de carrera ≤10-15 % por semana; si hubo fatiga, sesiones clave saltadas, FC alta
  en rodajes o TSB muy negativo, baja carga en vez de recuperar lo perdido; si todo fue bien, sigue el plan.
  No muevas la carrera ni elimines tests sin un motivo claro.
- Respeta las restricciones: miércoles descanso completo, máx. 2 h/día entre semana, **2 días de gimnasio por
  semana y siempre el mismo día que natación** (están en el mismo sitio: p. ej. lunes natación + tren inferior,
  viernes natación + tren superior), sin tren inferior el día antes de un test o sesión clave (cada semana, pierna el lunes o el viernes según cuál de los dos días siguientes NO sea clave; si ambos lo son, el lunes con RPE ≤7 y sin pliometría); gimnasio con
  `focus` (Tren superior / Tren inferior), natación con bloques que tengan `short` (series en una línea),
  carrera con intensidades en códigos ({E}, {T}, {I}, {R}, {CUR}, {RP}), nunca ritmos fijos.
- Las sesiones de carrera, natación y bici deben llevar `steps` (se suben al reloj): para carrera,
  `app/.venv/bin/python app/steps_from_text.py {{PLAN}} --write` los genera desde los bloques; revisa lo que diga
  «SIN CONVERTIR» y escríbelos a mano. Natación y bici los heredan de su plantilla.
- Mantén el formato del JSON (ver docstring de `app/plan_tool.py`). Añade al final de `revisions`:
  `{"date": "{{TODAY}}", "summary": "<1-2 líneas: qué cambió y por qué>"}` (aunque no cambie nada).

## 4. Publica
1. `app/.venv/bin/python app/plan_tool.py validate {{PLAN}}` (corrige hasta que diga OK)
2. `app/.venv/bin/python app/plan_tool.py import {{PLAN}}`
3. Añade una entrada breve (3-5 líneas, en catalán como el resto) al principio de `data/log.md` con la fecha de hoy.
4. `.venv/bin/python generate_site.py`
5. `git add data/plans data/training_plan.md data/log.md docs/index.html` y `git commit` (mensaje en catalán,
   con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), y `git push`.

## 5. Respuesta final
Como mucho 3 líneas en castellano, sin markdown (se usa como notificación): cómo fue la semana y el cambio
principal de la siguiente.
