# Calcolatore termini processuali nello scadenziario

Il modulo aggiunge allo `/scadenziario` un assistente di calcolo professionale e verificabile, pensato come supporto operativo e non come sostituzione della conferma dell'avvocato.

## Superfici

- UI React: `/scadenziario`, sezione `Calcolatore termini processuali`.
- API:
  - `GET /api/v1/ui/scadenziario/termini/templates`
  - `POST /api/v1/ui/scadenziario/termini/calculate`
  - `POST /api/v1/ui/scadenziario/termini/explain`
  - `POST /api/v1/ui/scadenziario/termini/validate`
  - `GET /api/v1/ui/scadenziario/termini/audit`
  - `POST /api/v1/ui/scadenziario/termini/override`
  - `POST /api/v1/ui/scadenziario/termini/crea-scadenza`

## Regole coperte

- art. 155 c.p.c.: dies a quo escluso, computo a mesi secondo calendario comune, proroga se la scadenza cade in giorno festivo e proroga del sabato per atti fuori udienza;
- L. 742/1969: sospensione feriale 1-31 agosto quando applicabile;
- sabato parametrico tramite `extend_saturday`, per non applicarlo in modo globale a udienze e attivita giudiziarie;
- sospensione feriale parametrica tramite `ferial_suspension_policy`: `applies`, `excluded`, `partial`, `manual_review`;
- termini a ritroso e termini liberi con `requiresLegalReview=true`.

## Audit e versioning

Ogni calcolo registra:

- `template_version`
- `ruleset_version`
- `calendar_version`
- `engine_version`
- input e output canonici
- `immutable_hash` SHA-256 su JSON canonico

L'hash non usa valori non riproducibili nel trigger; `created_at` e' un campo del record ed entra nel payload canonico salvato.

## Storage

Schemi governati:

- SQLite: `pct/sql/20260430_termini_processuali.sql`
- PostgreSQL: `pct/sql/20260430_termini_processuali_postgres.sql`

Tabelle principali:

- `deadline_templates`
- `deadline_audit_logs`
- `official_holidays`
- `calendar_versions`
- `deadline_notification_logs`

Runtime attuale: repository JSON tenant-aware per continuita e repository SQLite testato. Lo schema PostgreSQL e' pronto per cutover tenant-aware insieme al programma storage.

## Promemoria PEC

Il calcolo produce un piano idempotente T-30, T-15, T-7, T-1 e T-0 con chiave SHA-256. L'invio reale deve usare la configurazione PEC dello studio e conservare ricevute, allegati, metadati e hash secondo le policy di conservazione documentale.

## Import calendario ufficiale

Il comando operativo per importare un CSV verificato e':

```bash
python tools/import_istat_calendar.py calendario_2026.csv --year 2026 --db data/scadenziario/termini_processuali.json --backend json --source "CSV ufficiale" --source-url "https://www.istat.it/"
```

Il CSV deve contenere almeno `date` e `description`; `type` e' opzionale. Il comando calcola sempre il checksum SHA-256 del file e puo' validarlo con `--sha256`.

## Limite professionale

I template coprono i casi ordinari e sono estendibili. Rito speciale, materia urgente, sospensione parziale, calcolo a ritroso, termine libero o override manuale attivano sempre la revisione professionale.
