# Diari d'entrenador

Registre cronològic curt d'ajustos i decisions preses en converses amb l'entrenador
(canvis de sessió, fatiga detectada, lesions, imprevistos, etc.). Entrades més noves a dalt.

## 2026-08-07 (4)
Preferència permanent de format (afegida a CLAUDE.md): les sessions sempre amb el màxim
detall — córrer amb ritme+distància+FC, bici amb distància+ritme, natació amb sèrie completa
en metres (piscina de 25m, l'atleta té tot el material), gimnàs amb exercicis/sèries/reps
concrets (es fa al mateix lloc que la piscina, sessions combinades sense desplaçament).
Reescrita la setmana 2 amb aquest nivell de detall.

## 2026-08-07 (3)
Muntada l'automatització diària. Es va provar primer al núvol (repositori privat a GitHub
+ rutina de Claude Code programada a les 11h), però es va descartar: no hi ha manera
d'afegir secrets/variables d'entorn (GARMIN_EMAIL/PASSWORD) a l'entorn del núvol des de
la interfície actual, així que la rutina mai podria sincronitzar Garmin. Rutina desactivada
(`trig_01SjMdcf2qkTD4QpGZGs6A2F`) per si en el futur s'habilita aquesta opció.
En comptes d'això, `daily_checkin.py` corre localment via `launchd` cada dia a les 11:00:
sincronitza Garmin, compara la sessió prevista d'ahir amb les activitats reals, i notifica
un resum pel Mac. Tot queda local, sense credencials fora d'aquest ordinador.

## 2026-08-07 (2)
Revisada la setmana 1 real (sincronització Garmin): només córrer (4 sessions, ~2h20 total),
sense natació/bici/gimnàs — setmana de viatge (Barcelona/Ares/Sant Cugat), confirmat per
l'atleta com a correcte, no una manca de sincronització. No es compensa, es continua amb
normalitat. Definida la setmana 2 (10-16 ago) centrada en recuperar les 3 disciplines +
gimnàs, ja amb les zones de córrer del test de laboratori (Z2 <140bpm). És l'última setmana
de base abans que comenci Construcció 1 (17/8).

## 2026-08-07
L'atleta ha compartit un informe de laboratori (LabSportSalud, prova del 07/01/2025) amb
llindars ventilatoris de córrer (VT1/VT2) fets amb anàlisi de gasos — molt més fiables que
l'estimació per %FCmax que teníem. VO2max i FCmax de la prova coincideixen gairebé amb els
valors actuals de Garmin, així que les zones semblen encara vàlides tot i tenir 19 mesos.
Actualitzat `athlete_profile.md` amb les zones completes de FC i ritme de córrer, i avisat
a `training_plan.md` que des de la setmana 2 cal fer-les servir en lloc de l'estimació vella.
Pendent: test de llindar/FTP de bici (encara no en tenim cap de fiable).

## 2026-07-30
Definits: dia de descans (dimecres), sense lesions, zones estimades a partir de FC màx.
observada (192bpm) i d'un esforç recent de llindar (5,68km a 4:17/km, FC164, 04/06). Estat
de forma via Garmin: VO2max 56,8, training status "Productiu", càrrega "BALANCED" — bon
punt de partida. Escrita la setmana 1 (3-9 ago) dia a dia a `training_plan.md`. Fase 1
renombrada de "recuperació" a "consolidació": l'atleta ja porta setmanes entrenant amb
normalitat des del Walchsee, no calia tractar-ho com a recuperació post-cursa.

## 2026-07-29
Correcció de data (avui era 29 de juliol, no 8; el pla es va reescriure a 12 setmanes
enlloc de 15). Primera sincronització de Garmin amb èxit després de detectar que el
compte configurat inicialment (Gmail) era incorrecte — el compte real amb l'històric és
pau.chicharro@hotmail.com. Activitats recents ja disponibles (córrer, bici, natació,
força, HIIT). Pendent: sincronitzar Strava per a l'històric llarg.

## 2026-07-08
Configuració inicial del projecte: definit objectiu (Challenge Barcelona Triatló 2026,
olímpica), macrocicle de 15 setmanes esbossat, i integració de dades pendent de primera
sincronització amb Garmin i Strava.
