# IUSENTRA Update Intelligence

## Obiettivo

Il motore di aggiornamento giuridico di IUSENTRA monitora fonti ufficiali e istituzionali, acquisisce contenuti nuovi o aggiornati, li normalizza, li classifica con supporto AI, li confronta con l'archivio interno e li instrada verso review amministrativa o pubblicazione.

Il flusso operativo reale e':

1. `fonti -> fetch`
2. `staging raw`
3. `normalizzazione`
4. `analisi AI + classificazione`
5. `matching con archivio interno`
6. `review queue`
7. `pubblicazione news / archivio strutturato`
8. `audit e storico`

## Fonti iniziali

Il seed iniziale include:

- Gazzetta Ufficiale
- Normattiva
- dati.normattiva.it
- Corte costituzionale
- Cassazione Massimario
- Giustizia Amministrativa
- EUR-Lex
- Agenzia delle Entrate
- Ministero del Lavoro

Le fonti sono classificate per `trust_class`:

- `A`: fonte ufficiale primaria
- `B`: fonte istituzionale ufficiale
- `C`: fonte editoriale specialistica
- `D`: fonte non utilizzabile per aggiornamento strutturale

## Regole decisionali

Il motore usa classi chiuse:

- `NORMATIVA_NUOVA`
- `NORMATIVA_AGGIORNAMENTO`
- `GIURISPRUDENZA`
- `PRASSI`
- `NEWS`
- `COMMENTO`
- `DUPLICATO`
- `INCERTO`

Azioni possibili:

- `NEWS_ONLY`
- `NEW_NORMATIVE`
- `UPDATE_NORMATIVE`
- `NEW_CASE_LAW`
- `NEW_PRASSI`
- `DUPLICATE`
- `NEEDS_REVIEW`

Policy operative:

- le news ufficiali a basso rischio e con confidenza molto alta possono essere autopubblicate
- normativa, giurisprudenza e prassi strutturate passano in review prima della pubblicazione
- ogni aggiornamento normativo crea storico tramite `normative_versions`
- nessun contenuto editoriale secondario aggiorna da solo l'archivio normativo

## Storage e moduli

Il motore usa un archivio SQLite dedicato, derivato da `LEGAL_INTELLIGENCE_DB`:

- database: `legal_updates.db`
- export runtime: `legal_updates_repository.json`

Moduli principali:

- [pct/legal_update_repository.py](/D:/legale/hacs/pct/legal_update_repository.py)
- [pct/legal_update_ai.py](/D:/legale/hacs/pct/legal_update_ai.py)
- [pct/legal_update_pipeline.py](/D:/legale/hacs/pct/legal_update_pipeline.py)
- [web/blueprints/legal_updates_admin.py](/D:/legale/hacs/web/blueprints/legal_updates_admin.py)
- [web/blueprints/legal_intelligence.py](/D:/legale/hacs/web/blueprints/legal_intelligence.py)

## CLI

Scansione manuale:

```bash
iusentra aggiornamenti-legali
```

Scansione di fonti specifiche:

```bash
iusentra aggiornamenti-legali --source gazzetta_ufficiale --source normattiva
```

Pubblicazione automatica delle review gia approvate:

```bash
iusentra aggiornamenti-legali --publish-approved
```

## Scheduler

Job pianificati:

- Gazzetta Ufficiale: ogni ora
- Batch principale: ore 06:35, 12:35 e 18:35

La UI amministrativa dedicata e' in:

- `/admin/aggiornamenti-legali`
- `/admin/aggiornamenti-legali/review`

La UI utente dedicata e' in:

- `/legal-intelligence/news`

## Sicurezza e qualita'

- la fonte originale resta sempre salvata
- i contenuti sono deduplicati via `external_id` e `content_hash`
- ogni pubblicazione produce audit
- le relazioni strutturate non sovrascrivono lo storico
- la tassonomia materie e' chiusa e governata
