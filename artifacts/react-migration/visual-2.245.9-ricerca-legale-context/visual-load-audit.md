# Visual audit Ricerca Legale 2.245.9

Data: 2026-05-17

## Perimetro

- `http://localhost:8080/ricerca-legale/mediazione` desktop 1440x900
- `http://localhost:8080/ricerca-legale/mediazione` mobile 390x844
- `http://localhost:8080/ricerca-legale?q=D.Lgs.%2013%20marzo%202026%20n.%2039` desktop 1440x900

## Esito

| Controllo | Esito | Nota |
| --- | --- | --- |
| Container locale aggiornato | OK | `docker compose build --no-cache app scheduler-worker ocr-worker` e `docker compose up -d --no-build --force-recreate ...`; `/api/pronto` 200, versione `2.245.9`. |
| Mediazione senza blocchi non utili | OK | Non sono visibili `Presidio Lex AI`, `Mappa del contesto`, `Filtra le schede visibili`, hero, metriche, pannello aggiornamento o `Cerca collegati`. |
| Mediazione navigabile | OK | Registro e scheda laterale restano visibili; ricerca compatta nel registro; `Apri fonte originale` resta operativo. |
| Mediazione responsive | OK | Desktop e mobile senza overflow orizzontale; screenshot salvati fuori repo in `D:\iusentra\mediazione-after-desktop.png` e `D:\iusentra\mediazione-after-mobile.png`. |
| Ricerca D.Lgs. 39 | OK | Il dettaglio mostra `DECRETO LEGISLATIVO 13 marzo 2026, n. 39` e `accordi di delega`; non contiene `Tutela dei minori` o `Leggi la notizia`. |
| Archivi ufficiali mancanti | OK | La pagina dichiara `Archivio ufficiale non importato nel volume locale`, invece di fingere disponibilità. |
| Console e layout | OK | Zero errori/warning console rilevanti; zero overflow orizzontale sui viewport verificati. |

## Nota ambiente

Nel volume locale il registro mediazione importato risulta `0`, quindi la verifica non può attestare una ricerca su `ADR Center`. Il comportamento su registro vuoto è stato verificato; su ambiente con dati importati va ripetuta una ricerca su organismo reale.
