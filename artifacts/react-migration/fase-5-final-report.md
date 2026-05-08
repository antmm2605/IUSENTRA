# Fase 5 - Report finale chiusura bridge e hardening

## 1. Stato iniziale

Manifest iniziale dichiarato: 53 route, 18 full, 2 partial, 8 bridge, 25 legacy; 258 template Jinja, 130 UI primaria; 189 CTA legacy dichiarate dalla tranche precedente.

## 2. Stato finale

Manifest finale: 53 route, 26 full, 2 partial, 0 bridge, 25 legacy; audit reale anti-mascheramento: 27 full, 1 bridge, 25 legacy; CTA `?_legacy=1` rilevate: 81.

## 3-11. Numeri

- Route totali: 53
- Full React: 18 -> 26
- Partial: 2 -> 2
- Bridge: 8 -> 0
- Legacy: 25 -> 25
- Template Jinja UI primaria: 130 -> 130
- Template fallback tecnico: 36 -> 36
- CTA `_legacy=1`: 189 dichiarate -> 81 rilevate
- CTA `_legacy=1` primarie rimaste nelle full promosse: 0

## 12. Route convertite

`/template-atti`, `/template-atti/catalogo`, `/redazione-atti`, `/giurisprudenza`, `/legal-intelligence`, `/legal-intelligence/news`, `/legal-intelligence/mediazione`, `/ricerca-legale`.

## 13-14. Route rimaste legacy/bridge e motivo

Legacy: impostazioni sensibili, editor/export documentale, dettagli economici, checklist deposito e portali. Motivo: segreti, file, certificati, conformita e POST storici non ancora coperti da API JSON dedicate. Bridge: nessuno nel manifest; `/statistiche` resta partial e bridge reale.

## 15-19. Design system e API

Duplicati rimossi: nessuno. Componenti creati/modificati: registry icone, stati, skeleton, wizard, compliance, document badge, channel card, message list, LexPanel. Client API aggiunti come re-export governati: documents, telematico, comunicazioni, lex, legalIntelligence, templates. CSS aggiornato in `iusentra-design-system.css`. Registry icone aggiunto in `frontend/src/design/icons.tsx`.

## 20-22. Accessibilita, responsive, backend

Aggiornati report responsive/accessibilita. Backend toccato solo nei bridge read-only React per rimuovere `writes=legacy_routes` e CTA legacy primarie; nessun motore telematico/documentale riscritto.

## 23-30. Test, regressioni, branch

Test iniziali eseguiti: `npm run typecheck` verde; `node scripts/react-migration/run-full-react-migration.mjs` verde. Test completi e deploy sono tracciati nel report finale di sessione. Branch: `Codex/legal-electronic-filing-kIxcV`. Commit e PR: da compilare a fine sessione.

## Aggiornamento finale 2026-05-08

- Gate frontend: `npm test`, `npm run typecheck`, `npm run build` verdi.
- Gate React: `node scripts/react-migration/run-full-react-migration.mjs` verde dopo build; `node scripts/react-migration/run-legal-ui-checks.mjs` verde.
- Pytest completo monolitico non e' verde perche' va in timeout; il gate e' stato verificato con shard/sotto-shard, con timeout per job, e i timeout larghi sono stati isolati.
- Pytest shardati completati: core CI 10/10 con sotto-shard per i batch lenti; fase 02 React UI; fase 03 core business con batch lenti spezzati per file/item; fase 04 storage; fase 05 documenti; fase 06 telematico con item-batch; fase 07 Lex/Legal con batch 10-17 finali verdi e batch 9 isolato per item; fase 08 e2e verde; fase 09 misc verde.
- Fix anti-regressione: alias professionali canonici ripristinati, `strumenti-operativi` servito come React, route legacy usate nei test storici solo con `?_legacy=1`.
- Branch operativo: `Codex/legal-electronic-filing-kIxcV`; sincronizzazione con `claude/legal-electronic-filing-kIxcV` e commit finale da eseguire dopo questo aggiornamento report.
