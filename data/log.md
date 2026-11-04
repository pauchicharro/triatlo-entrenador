# Diari d'entrenador

Registre cronològic curt d'ajustos i decisions preses en converses amb l'entrenador
(canvis de sessió, fatiga detectada, lesions, imprevistos, etc.). Entrades més noves a dalt.







## 2026-11-04
A petició de l'atleta, natació 2000 m + gimnàs tren superior passa de dijous 5/11 a avui dimecres 4/11;
el dijous queda com a descans complet (just abans del test de 5 km de divendres).
## 2026-11-03 (5)
Rodatge de 7,7 km fet (5:49/km, FC 121). L'atleta podrà entrenar algun dia del cap de setmana fora:
afegit rodatge de recuperació de 6 km el dissabte 7/11 (o diumenge), després del test de divendres.
Dimecres segueix sent descans complet.
## 2026-11-03 (4)
Gimnàs sempre el mateix dia que natació (mateix lloc): dilluns natació + tren inferior, divendres
natació + tren superior; dijous només rodatge. Cap de setmana 7-8/11 fora → test de 5 km avançat a
divendres 6/11 (dijous 5: natació + tren superior, sense cames). Bici només a la setmana de descàrrega
(dijous 3/12). Progressió de km més suau a les setmanes 2-4 (29/35/41 km). Avui (3/11) ha fet gimnàs
33' a migdia; el rodatge de 8 km segueix pendent.
## 2026-11-03 (3)
A petició de l'atleta, dos dies de gimnàs cada setmana: afegit tren superior el 6/11, 3/12 i 24/12
(setmanes 1, 5 i 8, que només en tenien un). Setmana de cursa (28-31/12) sense gimnàs per arribar fresc.
## 2026-11-03 (2)
Gimnàs reestructurat: dilluns **tren inferior** (força + pliometria), dijous **tren superior + core**
(abans: força i core/pliometria, sense tren superior). Natació amb sèries en una línia a l'app. Activada
l'adaptació automàtica del pla cada diumenge (`app/weekly_replan.sh`). En l'assaig, el reajust ja va
detectar que la setmana 2 puja +33% de km de córrer (24→32): es corregirà diumenge 8/11 amb el test.
## 2026-11-03
Nou objectiu: San Silvestre 10K (31/12), temps desitjat sub-40. Les dades (millors esforços i
curses de 2026, VDOT 44-46,5) indiquen ~44:00 ara mateix; sub-40 requereix VDOT ~52 → objectiu
mantingut però els ritmes d'entrenament surten de la forma actual (VDOT inicial 46,5), no de
l'objectiu. Test de 5 km el 8/11 i re-test el 5/12 per recalcular. Pla de 8 setmanes creat a
`data/plans/san_silvestre_2026.json` (primer pla fet amb el nou format de l'app): córrer 4
dies/setmana amb progressió 24→46 km (venia de 12-23 km/setmana), natació 1-2/setmana, bici suau
cada 2 setmanes, gimnàs A (força) + B (core/pliometria), descans dimecres. Pla de la Challenge
Barcelona arxivat.
## 2026-08-08
Afegit un segon `launchd` (`com.pauchicharro.triatlocoach.sync`) que sincronitza Garmin i
publica la web cada 30 minuts entre les 7:00 i les 22:30, en mode `--silent` (sense
notificació, per no repetir el mateix avís cada mitja hora). L'avís complet de les 11:00 es
manté igual. Objectiu: que la web reflecteixi els entrenaments poc després de sincronitzar
el rellotge amb Garmin Connect, sense esperar al check-in diari. Garmin no ofereix webhooks
a l'API no oficial, així que és sondeig freqüent, no un avís instantani real.

## 2026-08-07 (7)
Confirmat definitivament: Garmin bloqueja per IP les peticions de login des dels runners de
GitHub Actions (error 429 persistent, sense canviar després de 40 minuts d'espera — no és
un límit temporal). No és arreglable des del nostre codi. Workflow `daily-checkin.yml`
desactivat (`gh workflow disable`) per no generar avisos d'error diaris inútils; es queda
al repositori per si mai canvia la política de Garmin. **La sincronització de Garmin només
és fiable des d'una IP residencial (el Mac local, via launchd), que és on ha de continuar
corrent.**

## 2026-08-07 (6)
Garantit que la web mai es quedi desactualitzada: el check-in diari (`daily_checkin.py`)
ara regenera i publica `docs/index.html` sol cada vegada que corre, i a `CLAUDE.md` hi ha
la norma que jo (l'entrenador) també ho he de fer sempre que editi `training_plan.md` en
una conversa.

## 2026-08-07 (5)
Publicada la pàgina web del pla a pauchicharro.github.io/triatlo-entrenador (GitHub Pages,
repositori fet públic perquè el pla gratuït no permet Pages en repos privats — sense dades
sensibles, només el pla d'entrenament). Es genera localment amb `generate_site.py` i marca
Fet/No detectat automàticament comparant amb Garmin, sense caselles manuals.
Completades amb sèries concretes les sessions de natació de la setmana 1 que havien quedat
genèriques (abans d'establir l'estàndard de detall).

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
