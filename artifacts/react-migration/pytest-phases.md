# Pytest per fasi - inventario iniziale

Generato per sostituire il feedback opaco del comando monolitico locale con
blocchi eseguibili separatamente.

## Comandi

```bash
python scripts/run_pytest_phases.py --list
python scripts/run_pytest_phases.py --core-list
python scripts/run_pytest_phases.py --suite-list
python scripts/run_pytest_phases.py --core-shard 6 --core-total-shards 10 --core-subshard 2 --core-total-subshards 16 --core-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --suite signer --suite-shard 2 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --phase react-migration --timeout-minutes 20
python scripts/run_pytest_phases.py --phase 02-react-ui --item-batch-size 20 --timeout-minutes 5
python scripts/run_pytest_phases.py --phase full --timeout-minutes 30 --report artifacts/react-migration/pytest-phases-run.json
```

## Conteggi

| Fase | File |
| --- | ---: |
| `00-ci-contracts` | 18 |
| `01-flask-core` | 17 |
| `02-react-ui` | 21 |
| `03-core-business` | 43 |
| `04-storage` | 13 |
| `05-documents` | 27 |
| `06-telematico` | 25 |
| `07-lex-ai` | 80 |
| `08-e2e` | 5 |
| `09-misc` | 13 |

## Nota gate

Questo inventario non rende verde la suite: serve a eseguire e diagnosticare.
La suite backend e' verde solo quando tutte le fasi richieste passano, oppure
quando la CI equivalente su Python 3.12 e' verde.

## Stato shard 2026-05-09

Formula operativa mantenuta nei report: `pytest completo monolitico non è verde perché va in timeout; il gate è stato verificato con shard/sotto-shard, con timeout per job, e i timeout larghi sono stati isolati.`

Le fasi `00-ci-contracts`, `01-flask-core`, `02-react-ui`, `03-core-business`, `04-storage`, `05-documents`, `06-telematico`, `07-lex-ai`, `08-e2e` e `09-misc` sono state verificate tramite report JSON in `artifacts/react-migration/pytest-20260509-*.json` e storico dettagliato in `pytest-confirmed-ok.md`.

Timeout larghi isolati e non dichiarati verdi monolitici:
- `03-core-business`: batch workflow lenti confermati con item singoli.
- `07-lex-ai`: follow-up lenti e Local AI API context confermati con sotto-shard singoli.

## Pytest core CI

Il workflow GitHub Actions divide `Pytest core` in 10 shard principali generati
dal runner con `--core-shard`. Le fasi lente usano sotto-fasi a livello di test
item con timeout pytest di 5 minuti: fase 5 in 6 parti, fase 6 in 16 parti,
fase 9 in 6 parti, observability e OCR in 3 parti ciascuna. Il check aggregato
finale resta `Pytest core` e fallisce se una qualunque parte fallisce. Anche le
suite CI `coverage-critical`, `signer`, `quality-overlay`, `release-readiness`
ed `e2e-nightly` sono censite dal runner.

Inventario JSON: `artifacts/react-migration/pytest-core-shards.json`.
Inventario suite CI: `artifacts/react-migration/ci-test-suites.json`.
