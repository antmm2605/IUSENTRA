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
python scripts/run_pytest_phases.py --suite-list
python scripts/run_pytest_phases.py --core-shard 6 --core-total-shards 10 --core-subshard 2 --core-total-subshards 16 --core-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --suite signer --suite-shard 2 --suite-total-shards 4 --suite-subdivide-items --timeout-minutes 5
python scripts/run_pytest_phases.py --phase react-migration --timeout-minutes 20
python scripts/run_pytest_phases.py --phase 02-react-ui --item-batch-size 20 --timeout-minutes 5
python scripts/run_pytest_phases.py --phase full --timeout-minutes 30 --report artifacts/react-migration/pytest-phases-run.json
```

Gli argomenti extra di pytest vanno dopo `--`:

```bash
python scripts/run_pytest_phases.py --phase 02-react-ui -- --maxfail=1 -vv
python scripts/run_pytest_phases.py --phase 02-react-ui --batch-size 1 --timeout-minutes 10 -- --maxfail=1 -vv
python scripts/run_pytest_phases.py --phase 02-react-ui --item-batch-size 1 --timeout-minutes 5 -- --maxfail=1 -vv
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

## Regola permanente per nuovi test

Qualsiasi nuovo test, file di test o suite CI deve nascere gia' compatibile con
lo split a 5 minuti: va registrato nel runner `scripts/run_pytest_phases.py`,
in una suite CI shardata o in una matrice equivalente. Nessun nuovo comando
pytest/job operativo deve superare 5 minuti. Se un controllo rischia di
superare quel limite, va diviso subito in piu' test item, shard, fixture piu'
leggere o job paralleli, mantenendo lo stesso perimetro di verifica.

## Pytest core in CI

Il job GitHub Actions `Pytest core` non gira piu' come processo monolitico da
45-50 minuti. La CI usa una matrice `tests-core-shards` con 10 fasi principali.
Le fasi lente sono divise a livello di singolo test item con budget massimo di
5 minuti per comando pytest: fase 5 in 6 parti, fase 6 in 16 parti, fase 9 in 6
parti. Anche le fasi 7 e 8, che contengono `tests/test_observability_runtime.py`
e `tests/test_ocr_worker.py`, sono divise in 3 sotto-fasi per evitare blocchi
opachi su observability/OCR.

```bash
python scripts/run_pytest_phases.py --core-shard <1-10> --core-total-shards 10 \
  --core-subshard <n> --core-total-subshards <m> --core-subdivide-items \
  --timeout-minutes 5
```

Ogni shard espande gli stessi target del vecchio `Pytest core`, inclusa la
directory `lex/tests`, e li ripartisce in modo stabile. Un job aggregatore
mantiene il check finale `Pytest core`: e' verde solo se tutte le 10 fasi sono
verdi. Se viene aggiunto un nuovo file sotto `lex/tests`, entra
automaticamente negli shard; i test di contratto CI verificano che non venga
perso nessun target storico.

Per file molto lunghi, usare `--item-batch-size`: il runner espande i test item
visibili via AST e li lancia a gruppi piccoli. Questa modalita' e' diagnostica:
non sostituisce il preset `full`, ma evita che un singolo file lento impedisca
di capire quale test stia consumando tempo.

## Altre suite CI con limite 5 minuti

Lo stesso runner governa anche le altre suite test eseguite dai workflow:

| Suite | Shard CI | Modalita' |
| --- | ---: | --- |
| `coverage-critical` | 12 | Test item + artefatti coverage combinati nell'aggregatore `Coverage moduli critici`. |
| `signer` | 4 per sistema operativo | Test item, con aggregatore `Local Signer e PKCS#11`. |
| `e2e-smoke` | 1 | Comando isolato con timeout pytest 5 minuti. |
| `quality-overlay` | 3 | File mirati dell'overlay qualita'. |
| `release-readiness` | 1 | Test readiness isolato con timeout 5 minuti. |
| `e2e-nightly` | 4 | Un file E2E per shard, con aggregatore nightly. |

Il frontend React e' diviso in tre job paralleli (`test`, `typecheck`,
`build:vite`) con aggregatore `Frontend React CI`; il typecheck resta un gate
separato, quindi il build Vite non duplica il controllo TypeScript.

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
L'inventario delle suite CI aggiuntive e' in
`artifacts/react-migration/ci-test-suites.json`.
