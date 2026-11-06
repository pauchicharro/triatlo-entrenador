# Perfil de l'atleta

## Objectiu principal
- **Cursa**: San Silvestre 10K, **31 de desembre de 2026** (córrer, 10 km).
- **Temps objectiu de l'atleta**: sub-40:00 (4:00/km, VDOT 51,9). Test de 5 km del 5/11: **19:56 → VDOT 50,0** (predicció 10K 41:20). Sub-40 demana VDOT 51,9: ambiciós però plausible. Re-test el 5/12.
- **Bloc**: 3/11 - 31/12 (8 setmanes), centrat en córrer (4 dies/setmana) natació 2 dies/setmana sempre combinada amb gimnàs (dilluns tren inferior, divendres tren superior; mateix lloc), bici només a la setmana de descàrrega. Pla: `data/plans/san_silvestre_2026.json`.
- Objectiu anterior (completat 25/10/2026): Challenge Barcelona Triatló, olímpica. Pla arxivat a `data/plans/2026_challenge_barcelona.md`.
- Volum de córrer recent baix (12-23 km/setmana a set-oct), per això la progressió de km és gradual.

## Experiència
- 10 anys fent triatló.
- Acaba de completar el Challenge Walchsee (mitjà Ironman, 28/06/2026): 1,89km natació / 78,05km bici (1005m desnivell) / 20,80km córrer, 4:56:01. Ritme de gestió de l'esforç molt bo (FC progressiva 133→156→168 per disciplina). Anàlisi completa a `data/garmin/activities/23406635364.json`.
- Base aeròbica sòlida; repte actual és afinar ritme/velocitat per a la distància, més curta, olímpica.

## Estat de forma (Garmin, 30/07/2026)
- **VO2max**: 56,8 (running) — nivell molt bo.
- **Training status**: Productiu, balanç de càrrega "BALANCED" (aeròbic baix/alt i anaeròbic dins de rang objectiu) — no hi ha senyals de sobreentrenament ni detraining.
- **FC màxima observada** (90 dies): 192 bpm.
- **HRV**: no disponible via API per aquest compte/dispositiu (Forerunner 965) — fem servir training status + son com a senyals de recuperació en el seu lloc.

## Zones de córrer (prova de laboratori, LabSportSalud, 07/01/2025)

Prova incremental en tapís amb anàlisi de gasos (llindars ventilatoris VT1/VT2, no estimació).
**Té ~19 mesos i és només de córrer** (sense bici ni natació), però el VO2max i la FCmax que
dona coincideixen gairebé exactament amb els valors que Garmin calcula ara mateix (VO2max
55,6 vs 56,8 actual; FCmax 190 vs 192 observat), així que sembla que la forma física de base
s'ha mantingut molt estable i les zones segueixen sent una referència vàlida.

**Punts clau:**
- VO2max: 55,6 ml/kg/min (4,12 l/min) — 9% per sobre de l'esperat per edat/sexe.
- VT1 (llindar aeròbic): FC 151bpm (79% FCmax) · ritme 5:13/km · VO2 36,2 ml/kg/min (65%)
- VT2 (llindar anaeròbic): FC 173bpm (91% FCmax) · ritme 4:06/km · VO2 41,7 ml/kg/min (75%)
- VO2max assolit a: FC 190bpm · ritme 3:02/km

**Zones de FC (córrer):**
| Zona | FC (bpm) | %FCmax | RPE | Substrat |
|---|---|---|---|---|
| Z1 Regenerativa | <130 | 50-70% | 0-2 | Greixos |
| Z2 Mixt lleuger / FatMax | 130-140 | 70-79% | 3-4 | Greix + glucosa |
| Z3 Mixt intens | 140-150 | 79-84% | 5-6 | Glucosa + greix |
| Z4 Tempo / MLSS (VT1-VT2) | 150-175 | 84-89% | 6-8 | Glucosa + greix |
| Z5 Umbral anaeròbic (>VT2) | 175-186 | 89-95% | 8-9 | Glucosa |
| Z6 VO2max / PAM-VAM | 186-190 | 95-100% | 9-10 | Glucosa |

**Zones de ritme (córrer, min/km):**
| Zona | Ritme |
|---|---|
| Z1 Regenerativa | <6:15 |
| Z2 Mixt lleuger | 6:15-5:45 |
| Z3 Mixt intens | 5:45-5:20 |
| Z4 Tempo/MLSS | 5:20-4:10 |
| Z5 U.Anaeròbic | 4:10-3:20 |
| Z6 VO2max | 3:20-3:00 |
| Z7 Capacitat anaeròbica | <3:00 (esprints <45s) |

**Recomanacions del laboratori** (a tenir en compte al dissenyar setmanes): ~80% del volum
aeròbic per sota de 150bpm (polaritzat), amb un mínim d'1-2 sessions/setmana a intensitat
Z5/Z6 (>VT2, per sobre de 4:10/km) per no perdre capacitat glucolítica anaeròbica. Reforçar
treball de força/excèntric complementari. Hidratació ≥1L/h si fa >22°C i >60% humitat.

## Bici i natació
Sense test de llindar/FTP formal. Velocitat mitjana en rodades aeròbiques recents
~28-31km/h a FC~140 — consistent amb Z2-Z3 de córrer aplicat a bici, però és una estimació
feble. Recomanable fer un test de 20min de bici en les properes setmanes per tenir zones
igual de fiables que les de córrer.

## Dispositius / fonts de dades
- Garmin (Forerunner 965) des d'abril de 2026.
- Abans d'abril de 2026 feia servir Suunto — aquest històric només és accessible via Strava (pendent de sincronitzar).

## Disponibilitat
- Entre setmana: màxim 2h/dia.
- Cap de setmana: més flexible.
- **Dia de descans complet: dimecres.**
- Vol incloure sessions de gimnàs (força) regularment.

## Lesions / limitacions
- Cap de coneguda.

## Notes obertes
- PRs oficials per disciplina/distància (només tenim el registre de Garmin, no resultats de cursa oficials).
- Test de llindar/FTP formal de bici (les zones de bici actuals són una estimació feble, a diferència de les de córrer, que ja tenen una prova de laboratori).
- Valdria la pena repetir la prova de laboratori (l'última és de gener 2025) ara que hi ha més volum acumulat, per confirmar si les zones han canviat.

## Font
Informe de valoració fisiològica (LabSportSalud), prova del 07/01/2025: composició corporal,
espirometria, prova incremental en tapís amb llindars ventilatoris VT1/VT2. Document original
a `~/Downloads/Informe rendimiento Pau Chicharro.pdf` (no es guarda còpia dins del projecte
perquè conté dades personals identificatives que no calen per entrenar).
