# Full React Audit IUSENTRA

Generato: 2026-05-08T00:00:00+02:00

## Sintesi

- Route censite: 53
- Stati manifest: react_operational_full=26, react_operational_partial=2, react_bridge=0, legacy_operational=25
- Classificazione anti-mascheramento reale: react_operational_full=27, react_bridge=1, legacy_operational=25
- Route bridge azzerate nel manifest: 8 -> 0
- CTA `?_legacy=1` complessive rilevate dal gate: 81
- CTA `?_legacy=1` primarie nelle route promosse in questa fase: 0
- Route con LegacyPostForm: 0
- Route con form HTML POST React: 0
- Route full con dati mock/demo: 0
- Bridge con `writes=legacy_routes`: 0
- Template Jinja censiti: 258
- Template Jinja UI primaria: 130
- Template Jinja fallback tecnico: 36

## Route Promosse

| Route | Stato precedente | Stato nuovo | Verifica |
| --- | --- | --- | --- |
| `/template-atti` | react_bridge | react_operational_full | lettura JSON reale, scritture none, nessuna CTA legacy primaria |
| `/template-atti/catalogo` | react_bridge | react_operational_full | catalogo metadati reale, filtri React, scritture none |
| `/redazione-atti` | react_bridge | react_operational_full | quadro operativo React read-only, azioni primarie React |
| `/giurisprudenza` | react_bridge | react_operational_full | archivio metadati/fonte React, nessun fetch esterno |
| `/legal-intelligence` | react_bridge | react_operational_full | dashboard fonti React, nessuna generazione React |
| `/legal-intelligence/news` | react_bridge | react_operational_full | news backend reali con fonte e stato |
| `/legal-intelligence/mediazione` | react_bridge | react_operational_full | registro mediazione backend, stato fonte visibile |
| `/ricerca-legale` | react_bridge | react_operational_full | alias React verso Legal Intelligence senza pipeline nuova |

## Route Non Promosse

- `/statistiche`: resta `react_operational_partial`; l'audit reale la classifica ancora come bridge per completezza degli stati.
- Route impostazioni sensibili: restano legacy per PEC, firma, Local Signer, OAuth e segreti non esponibili.
- Route wildcard economiche/documentali: restano legacy per dettaglio, export, PDF, DOCX, XML e download governati.
- Route telematiche `/polisWeb`, `/pdp`, `/pat`, `/sigit`, `/sigp`, `/portali/*`: restano legacy per conformita portali, sessioni, certificati, Local Connector e divieto di scraping.

## Componenti E Dati

- Componenti IUSENTRA aggiunti: loading/error/success/retry, skeleton, wizard stepper, compliance panel, document status badge, channel card, message list, LexPanel.
- Registry icone aggiunto: `frontend/src/design/icons.tsx`.
- Client API consolidati/re-export: documents, telematico, comunicazioni, lex, legalIntelligence, templates.
- Source registry compliance aggiunto: `pct/data/legal_sources_registry.json`.

## Gate

- `node scripts/react-migration/run-full-react-migration.mjs`: verde dopo promozione.
- `check-no-primary-legacy-links`: verde.
- `check-no-mock-data-full-react`: verde.
- `check-full-react-route-contract`: verde.

Questo audit sostituisce la tabella storica precedente. Il dettaglio macchina corrente e' in `artifacts/react-migration/anti-mascheramento-audit.json`.
