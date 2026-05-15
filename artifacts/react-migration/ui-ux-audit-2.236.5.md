# Audit UI/UX 2.236.5 - rifinitura correttiva

Data: 2026-05-15

## Perimetro

- Ricerca Studio: `/global-search`, componente `frontend/src/components/RicercaStudioPage.tsx`.
- Controlli Atti: `/deposito/checklist`, componente `frontend/src/components/TelematicoSurfacePage.tsx`.
- Audit visuale: `scripts/react-migration/visual-load-audit.mjs`.
- Stile condiviso ricerca: `frontend/src/index.css`.

## Problemi corretti

### Pagina: Ricerca Studio / `/global-search`

#### Problemi importanti

- Erano presenti sigle e metriche tecniche visibili (`FTS5`, tempi in millisecondi, scorciatoia `Ctrl K`) non adatte al linguaggio professionale di uno studio legale.
- File coinvolti: `frontend/src/components/RicercaStudioPage.tsx`, `frontend/src/index.css`.
- Correzione applicata: microcopy operativo (`Indice avanzato`, `Aggiorna ricerca`, `archivio reale`), hint compatto `Cerca`, font-size stabile della barra ricerca.

#### Controlli superati

- Testi italiani professionali.
- Nessun avviso visuale residuo nell'audit 2.236.5.
- Nessun overflow desktop/mobile.

### Pagina: Controlli Atti / `/deposito/checklist`

#### Problemi importanti

- La checklist e lo stato Local Signer citavano il browser, formulazione percepibile come tecnica per l'utente finale.
- File coinvolti: `frontend/src/components/TelematicoSurfacePage.tsx`.
- Correzione applicata: testi convertiti in `postazione in uso` e `Da verificare dal PC`.

#### Controlli superati

- Linguaggio italiano operativo.
- Nessun impatto su logica telematica, API o permessi.

### Gate visuale

#### Miglioramenti consigliati

- L'audit segnalava pagine operative come povere di collegamenti anche quando avevano molte azioni reali su pulsanti, tab e controlli.
- File coinvolti: `scripts/react-migration/visual-load-audit.mjs`.
- Correzione applicata: warning `collegamenti_o_azioni_da_arricchire` solo quando mancano sia collegamenti sia azioni.

## Verifiche

- `npm --prefix frontend run typecheck`: OK.
- `npm --prefix frontend run test`: OK.
- `node frontend/scripts/check-react-contracts.mjs`: OK.
- `node scripts/react-migration/check-route-gate.mjs`: OK.
- `node scripts/react-migration/check-full-react-route-contract.mjs`: OK.
- `python -m pytest -q tests/test_packaging_consistency.py tests/test_release_readiness.py --tb=short`: OK.
- `npm --prefix frontend run build`: OK.
- Docker locale no-cache: app, scheduler, OCR e Redis healthy; `/api/pronto` 200 `versione=2.236.5`.
- Chrome CDP autenticato: audit completo 91/92 OK con timeout isolato `/soggetti/nuovo` mobile; retry mirato OK in 761 ms.

## Patch per priorita'

1. Fase 1, visualizzazione: nessuna rottura rilevata nelle rotte corrette.
2. Fase 2, testi tagliati o illeggibili: rimosse sigle e metriche tecniche dalla barra Ricerca Studio.
3. Fase 3, disallineamenti: font-size ricerca reso stabile e hint trattato come elemento compatto.
4. Fase 4, contrasto: nessuna modifica necessaria.
5. Fase 5, mobile: hint ricerca nascosto nei breakpoint stretti per preservare spazio.
6. Fase 6, spazio morto: nessuna modifica strutturale necessaria.
7. Fase 7, coerenza: testi Controlli Atti allineati al vocabolario professionale IUSENTRA.
