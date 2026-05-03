# IUSENTRA Codex Optimizer Scaffold

Questo scaffold MetaHarness e' un laboratorio controllato per migliorare istruzioni, harness e guardrail Codex di IUSENTRA.

Non e' una dipendenza runtime.
Non autorizza patch applicative automatiche.
Non autorizza run con provider reali senza autorizzazione esplicita nel task corrente.

## Perimetro

Lo scaffold deve restare dentro:

```text
tools/metaharness/iusentra-codex-optimizer/
```

Le proposte sono considerate non attendibili finche':
- il diff non e' revisionato;
- il quality gate Codex passa;
- non vengono toccati file protetti;
- non vengono modificate dipendenze runtime;
- non vengono indeboliti CI, coverage, security workflow o `AGENTS.md`.

## Run

In questa tranche non sono stati eseguiti run MetaHarness.

Qualsiasi comando `metaharness run ...`, anche con backend fittizio, deve essere autorizzato nel task corrente e deve restare limitato a harness, istruzioni e documentazione operativa.

## Uso consigliato

1. Definire baseline e perimetro.
2. Usare `tools/autoresearch-lite/` per il ciclo `baseline -> modifica piccola -> misura -> keep/discard`.
3. Usare `tools/codex_harness/` per verificare scope e dipendenze.
4. Trattare ogni output MetaHarness come proposta da revisionare manualmente.
