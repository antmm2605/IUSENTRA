# Pytest per fasi

## Obiettivo

Il comando monolitico:

```bash
python -m pytest -q
```

resta il riferimento completo, ma in locale puo' durare troppo e finire in
timeout senza indicare quale dominio ha rallentato o fallito. Per questo la
suite puo' essere eseguita a fasi con:

```bash
python scripts/run_pytest_phases.py --list
python scripts/run_pytest_phases.py --core-list
python scripts/run_pytest_phases.py --core-shard 1 --core-total-shards 10 --timeout-minutes 10
python scripts/run_pytest_phases.py --phase react-migration --timeout-minutes 20
python scripts/run_pytest_phases.py --phase full --timeout-minutes 30 --report artifacts/react-migration/pytest-phases-run.json
```

Gli argomenti extra di pytest vanno dopo `--`:

```bash
python scripts/run_pytest_phases.py --phase 02-react-ui -- --maxfail=1 -vv
```

## Regola di rilascio

Il runner a fasi non abbassa i gate e non autorizza a dichiarare verde una
release se una fase non e' stata eseguita o e' fallita. Serve a:

- ridurre il feedback loop locale;
- isolare rapidamente il blocco lento o rotto;
- eseguire le fasi in job separati quando il runtime lo consente;
- mantenere una fase `09-misc` per evitare esclusioni silenziose.

Per dichiarare verde la suite backend locale devono passare tutte le fasi del
preset `full`, oppure un workflow CI equivalente su Python 3.12.

## Pytest core in CI

Il job GitHub Actions `Pytest core` non gira piu' come processo monolitico da
45-50 minuti. La CI usa una matrice `tests-core-shards` con 10 fasi parallele:

```bash
python scripts/run_pytest_phases.py --core-shard <1-10> --core-total-shards 10 --timeout-minutes 10
```

Ogni shard espande gli stessi target del vecchio `Pytest core`, inclusa la
directory `lex/tests`, e li ripartisce in modo stabile. Un job aggregatore
mantiene il check finale `Pytest core`: e' verde solo se tutte le 10 fasi sono
verdi. Se viene aggiunto un nuovo file sotto `lex/tests`, entra
automaticamente negli shard; i test di contratto CI verificano che non venga
perso nessun target storico.

## Preset

| Preset | Fasi |
| --- | --- |
| `react-migration` | `00-ci-contracts`, `01-flask-core`, `02-react-ui` |
| `ci-core-local` | `00-ci-contracts`, `01-flask-core`, `04-storage`, `06-telematico`, `07-lex-ai` |
| `full` | tutte le fasi, inclusa `09-misc` |

## Fasi iniziali

| Fase | File | Scopo |
| --- | ---: | --- |
| `00-ci-contracts` | 18 | Contratti CI, packaging, sicurezza minima e guardrail tecnici rapidi. |
| `01-flask-core` | 17 | Bootstrap Flask, autenticazione, sicurezza web, osservabilita' e superfici operative. |
| `02-react-ui` | 21 | Contratti React, regia, topbar, layout mobile e coerenza design system. |
| `03-core-business` | 43 | Clienti, fascicoli, agenda, preventivi, tariffario e workflow economico. |
| `04-storage` | 13 | Persistenza, migrazioni, tenant, repository SQL e parita' storage. |
| `05-documents` | 27 | Documenti, template atti, editor, firma visibile e intelligenza documentale. |
| `06-telematico` | 25 | PCT, PEC, portali telematici, SIGP, buste, Local Signer e deposito. |
| `07-lex-ai` | 80 | Lex, assistenti, fonti ufficiali, legal intelligence, coverage AI e ricerca. |
| `08-e2e` | 5 | Flussi end-to-end e golden path ufficiali. |
| `09-misc` | 13 | Test non classificati dalle regole sopra. Deve restare visibile e non ignorata. |

L'inventario JSON generato e' in
`artifacts/react-migration/pytest-phases.json`.
L'inventario dei 10 shard CI `Pytest core` e' in
`artifacts/react-migration/pytest-core-shards.json`.
