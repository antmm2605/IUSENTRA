# Ricerca legale e archivio giurisprudenza, intervento UI 19/08/2026

## Perimetro

- Ricerca Legale React: tab principali, filtri, elenco risultati, pannello dettaglio e azione a tutto schermo.
- Archivio Giurisprudenza React: intestazione, filtri, griglia risultati, pannello dettaglio e azione a tutto schermo.

## Modifiche

- Rimossi i sottotitoli duplicati dalle tab di Ricerca Legale: restano solo `Ricerca`, `Aggiornamenti`, `Mediazione`.
- Aggiunto il comando `Tutto schermo` nella pagina Ricerca Legale e nell'Archivio Giurisprudenza.
- Compattati filtri e risultati, con pannello dettaglio non più schiacciato nelle larghezze medie.
- Uniformate alcune etichette visibili in italiano: `News` diventa `Aggiornamenti`, `Lex Chat AI` diventa `Assistente Lex`, le etichette tecniche vengono ripulite quando sono mostrate all'avvocato.
- Sistemata la vista Mediazione per evitare colonne strette e pannelli sovrapposti.

## Verifiche previste

- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run build`
- `python tools/codex_harness/run_codex_quality_gate.py --mode ui-support`
- Prova visiva reale su `http://127.0.0.1:8080` dopo rebuild Docker locale, con apertura pagine, scroll, hover/focus e click `Tutto schermo`.

## Stato

- In attesa di rebuild locale e verifica materiale su `127.0.0.1:8080`.
