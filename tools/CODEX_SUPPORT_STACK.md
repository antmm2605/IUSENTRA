# Codex Support Stack - IUSENTRA

Questo documento riassume gli strumenti di supporto a Codex per IUSENTRA.

## Componenti

### MetaHarness

Percorso:

```text
tools/metaharness/
```

Serve a migliorare:

- istruzioni;
- harness;
- script;
- workflow;
- validazioni;
- qualita' del lavoro Codex.

Non e' una dipendenza runtime.

### Autoresearch-lite

Percorso:

```text
tools/autoresearch-lite/
```

Serve a disciplinare il ciclo:

```text
baseline -> modifica piccola -> misura -> keep/discard
```

Non esegue loop autonomi.
Non crea branch.
Non installa dipendenze.

### Open Design support

Percorso:

```text
tools/open-design-support/
```

Serve a migliorare:

- UI/UX;
- design system;
- skill grafiche;
- prototipi;
- coerenza visiva;
- integrazione Jinja/React.

Open Design resta esterno alla repo IUSENTRA.

### Codex Harness

Percorso:

```text
tools/codex_harness/
```

Serve a controllare:

- scope;
- dipendenze;
- AGENTS.md;
- Open Design support;
- qualita' minima prima del report.

## Uso consigliato per ogni task Codex

1. Leggere `AGENTS.md`.
2. Definire scope.
3. Se task sperimentale, usare autoresearch-lite.
4. Se task UI/UX, leggere Open Design support.
5. Eseguire modifiche piccole.
6. Eseguire test/verifiche pertinenti.
7. Eseguire quality gate.
8. Classificare il risultato.
9. Produrre report finale.

## Comando quality gate per task tooling

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode dev-tooling
```

Il gate Codex Harness controlla soprattutto modifiche a strumenti/supporto e puo'
fallire correttamente su tranche applicative che toccano file protetti richiesti
dalle regole di release, come version bump in `pct/__init__.py`, `setup.py`,
`Dockerfile` e `railway.toml`. In questi casi non sostituisce i gate CI
applicativi (`Lint + syntax`, `Pytest core`, `Coverage moduli critici`) eseguiti
su Python 3.12 in GitHub Actions.

## Comando quality gate per supporto UI

```powershell
python tools/codex_harness/run_codex_quality_gate.py --mode ui-support
```

## Regola finale

Questi strumenti servono a rendere Codex piu' preciso, controllato e professionale.
Non autorizzano modifiche libere al prodotto.
