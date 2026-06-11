# Migration Center — import multi-gestionale (anteprima/dry-run)

Stato: **prima fase (PR 1/N)** — motore di import backend in sola anteprima.
Nessun dato reale viene scritto finché il commit non è approvato con un sink
esplicito (non ancora collegato ai repository). Obiettivo prodotto: togliere allo
studio la paura di perdere fascicoli/clienti/scadenze/fatture quando migra da un
altro gestionale.

## Flusso

```
adapter.parse(raw, kind, mapping)      # sorgente -> record di staging (no write)
   -> apply_validation                 # campi obbligatori, CF, date, importi
   -> mark_duplicates(existing_keys)    # dedup per chiave naturale + hash contenuto
   -> StagingArea.summary()/preview()   # anteprima sicura (no path, no segreti)
   -> build_commit_plan                 # cosa verrebbe creato / saltato (con motivo)
   -> execute_commit(sink, dry_run)     # default dry-run: nessuna scrittura
   -> RollbackLedger / execute_rollback # annulla le creazioni di un run
```

## Moduli (`pct/importers/`)

| File | Responsabilità |
|---|---|
| `base.py` | `RecordKind`, `StagedRecord` (con `content_sha256`), `ValidationIssue`, protocollo `ImportAdapter` |
| `registry.py` | registrazione/lookup adapter; `generic_csv` disponibile da subito |
| `validators.py` | campi obbligatori per tipo, CF (via `pct.codice_fiscale.decodifica`), date, importi |
| `dedup.py` | chiave naturale per tipo (CF/P.IVA, RG/anno, numero fattura…) + dedup intra-batch e vs studio |
| `staging.py` | orchestrazione parse→valida→dedup, `summary()`/`preview()` |
| `commit.py` | `build_commit_plan` (dry-run) + `execute_commit(sink, dry_run)` |
| `rollback.py` | `RollbackLedger` + `execute_rollback(sink)` |
| `adapters/generic_csv.py` | adapter CSV generico con mapping colonna→campo |

## Sicurezza / fonti certe

- **Dry-run di default**: `execute_commit` senza sink o con `dry_run=True` non scrive nulla; anche `dry_run=False` con sink assente resta sicuro (ritorna il piano).
- **Niente invenzioni**: record senza campi obbligatori o con CF non valido restano `invalid` e non vengono mai committati.
- **Anteprima redatta**: `to_public()/preview()` non espongono path filesystem né segreti.
- **Tenant-aware**: il `RecordSink` reale (PR successivo) viene iniettato dal chiamante già nel contesto tenant corretto; il client non sceglie mai tenant/path.
- **Rollback**: ogni run che scrive registra le creazioni; il rollback le annulla in ordine inverso.

## Sink reali (wiring)

| Sink | Modulo | Stato |
|---|---|---|
| Clienti | `web/services/import_center_runtime.py` (`ClientiRecordSink`) | **collegato** a `GestioneClienti` (tenant-aware): `create`/`delete`, dedup contro i clienti esistenti (`existing_client_keys`), commit/rollback reali; dry-run di default |
| Fascicoli / Scadenze / Fatture / Documenti | — | prossimi PR |

Il `GestioneClienti` è iniettato dal chiamante già nel contesto tenant corretto;
il sink non sceglie il tenant. `import_clienti_from_staging(gestione, staging, dry_run=True)`
simula; con `dry_run=False` scrive i clienti validi non duplicati e popola il
RollbackLedger per l'eventuale annullamento.

## Prossimi PR

1. Sink reali per fascicoli/scadenze/fatture/documenti + persistenza run e audit append-only.
2. Adapter gestionali: Studio Telematico (rifattorizzato), Cliens, Kleos, Netlex/EasyLex, Quadra/PCT.
3. API `/api/v1/ui/import-center/*` (runs/analyze/preview/dry-run/commit/rollback) e UI React (Import Center, dettaglio run, mapping).

## Esempio

```python
from pct.importers import build_staging, build_commit_plan, RecordKind

staging = build_staging("generic_csv", csv_bytes, kind=RecordKind.CLIENTE, existing_keys=existing)
print(staging.summary())          # {'valid': N, 'invalid': N, 'duplicate': N, ...}
plan = build_commit_plan(staging)  # anteprima: cosa entrerebbe
print(plan.to_public())
```
