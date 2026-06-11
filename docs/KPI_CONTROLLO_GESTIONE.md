# KPI / Controllo di gestione (issue #35)

Stato: **motore di calcolo backend (prima fase)**. Trasforma `/statistiche` da
dashboard decorativa a cabina direzionale: gli indicatori sono calcolati dai dati
reali dello studio, non finti. Il wiring ai repository tenant-aware e il drilldown
React sono il passo successivo; il motore qui è puro e testato.

## Motore (`pct/kpi/engine.py`)

`compute_kpis(*, fascicoli, scadenze, udienze, parcelle, timesheet, now)` →
report KPI. Tutte le soglie temporali usano **`Europe/Rome`** (regola
obbligatoria del progetto: mai confronti naive/aware; date IT e ISO accettate).

## KPI calcolati

| Area | Indicatori |
|---|---|
| Pratiche | aperte, chiuse, totale, valore totale |
| Scadenze | critiche (≤7gg, incluse scadute), scadute, totali aperte |
| Udienze | prossimi 30 / 60 / 90 giorni |
| Economia | parcelle emesse, incassato, insoluto, insoluto scaduto, **WIP** (valore lavoro non fatturato) |
| Tempo | minuti totali, minuti non fatturati, per fascicolo, **per professionista** (produttività) |
| Marginalità | ricavi per cliente (parcelle pagate) |
| Rischio operativo | score per fascicolo (scadenze scadute ×2 + udienza imminente ×3) → basso/medio/alto |

## Contratti dati (chiavi attese, tolleranti a formati misti)

- **fascicoli**: `id, stato (aperto/chiuso/archiviato), valore, cliente_id`
- **scadenze**: `id, fascicolo_id, data, completata (bool)`
- **udienze**: `id, fascicolo_id, data_ora`
- **parcelle**: `id, cliente_id, importo, stato (pagata/insoluta/emessa), scadenza_pagamento`
- **timesheet**: `id, fascicolo_id, utente_id, minuti, fatturabile, fatturato, tariffa_oraria`

Importi in formato IT (`1.234,56`) o tecnico (`1234.56`); date IT (`gg/mm/aaaa`)
o ISO. Campi mancanti non fanno crashare il calcolo (valori neutri).

## Prossimi PR

- Runtime tenant-aware che carica i dati dai repository reali e serve
  `/api/v1/ui/statistiche` con export sicuro.
- Drilldown React per area, periodo e professionista; chiusura issue #35 lato UI.
