# MetaHarness per IUSENTRA

## Scopo

MetaHarness e' usato come strumento esterno di sviluppo per migliorare il modo in cui Codex lavora sulla repository IUSENTRA.

Non e' una dipendenza runtime.
Non deve essere aggiunto a `requirements.txt`, `requirements/base.txt`, `requirements/dev.txt`, `pyproject.toml` o `setup.py`.

## Obiettivi consentiti

MetaHarness puo' essere usato per:
- migliorare `AGENTS.md`;
- migliorare istruzioni Codex;
- migliorare script di bootstrap, test e validazione;
- confrontare workflow Codex diversi;
- valutare harness e guardrail;
- generare proposte da revisionare manualmente;
- ridurre errori di scope;
- migliorare la qualita' dei report finali;
- supportare il ciclo autoresearch-lite;
- supportare il flusso Open Design per UI/UX senza toccare runtime.

## Obiettivi non consentiti senza autorizzazione esplicita

MetaHarness non deve:
- modificare codice business;
- modificare route Flask o blueprint;
- modificare modelli, repository, storage o migrazioni;
- modificare Lex AI;
- modificare portali telematici;
- modificare UI prodotto;
- aggiungere dipendenze runtime;
- indebolire CI, coverage, security workflow o quality gates;
- eseguire provider reali senza autorizzazione nel task corrente.

## Installazione

Comando realmente usato:

```powershell
py -3.12 -m pip install --user superagentic-metaharness
```

## Verifica

Il comando `metaharness --help` non funziona perche' lo script utente non e' nel `PATH`.

Comando funzionante:

```powershell
& 'C:\Users\antmm\AppData\Roaming\Python\Python312\Scripts\metaharness.exe' --help
```

## Scaffold MetaHarness

Lo scaffold puo' essere creato solo dentro:

```text
tools/metaharness/iusentra-codex-optimizer/
```

Comando:

```powershell
& 'C:\Users\antmm\AppData\Roaming\Python\Python312\Scripts\metaharness.exe' scaffold coding-tool tools/metaharness/iusentra-codex-optimizer
```

Lo scaffold non autorizza run con provider reali.

## Run vietati senza autorizzazione

Non eseguire senza autorizzazione esplicita:

```powershell
metaharness run ...
```

con:

- Hosted Codex;
- Codex provider reale;
- Gemini;
- altri provider reali;
- API key;
- run che generano patch applicative.

## Relazione con autoresearch-lite

MetaHarness serve a ottimizzare harness, istruzioni e workflow.

`tools/autoresearch-lite/` serve invece a disciplinare il ciclo sperimentale:

```text
baseline -> modifica piccola -> misura -> keep/discard
```

## Relazione con Open Design support

`tools/open-design-support/` contiene design system, skill e prompt UI/UX per aiutare Codex a produrre interfacce migliori.

MetaHarness puo' aiutare a valutare se queste istruzioni migliorano davvero il comportamento di Codex, ma non deve applicare patch grafiche automatiche senza review.

## Regola finale

MetaHarness e' uno strumento di sviluppo esterno.
Non e' una dipendenza runtime di IUSENTRA.
