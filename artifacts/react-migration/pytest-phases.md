# Pytest per fasi - inventario iniziale

Generato per sostituire il feedback opaco del comando monolitico locale con
blocchi eseguibili separatamente.

## Comandi

```bash
python scripts/run_pytest_phases.py --list
python scripts/run_pytest_phases.py --core-list
python scripts/run_pytest_phases.py --core-shard 1 --core-total-shards 10 --timeout-minutes 10
python scripts/run_pytest_phases.py --phase react-migration --timeout-minutes 20
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

## Pytest core CI

Il workflow GitHub Actions divide `Pytest core` in 10 shard paralleli generati
dal runner con `--core-shard`. Il check aggregato finale resta `Pytest core` e
fallisce se una delle 10 fasi fallisce.

Inventario JSON: `artifacts/react-migration/pytest-core-shards.json`.
