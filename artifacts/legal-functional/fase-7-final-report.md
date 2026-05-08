# Fase 7 - Report funzionale finale

## 1-5. Stato e workflow

Stato iniziale: bridge promuovibili ma workflow sensibili ancora legati a route storiche. Stato finale: bridge promuovibili convertiti in React read-only reale, senza mascherare i workflow non migrati.

Workflow verificati: Cliente-Fascicolo, Documenti, Telematico, Agenda/Scadenziario, PEC/Messaggi, Tariffario/Preventivi, Template/Redazione, Lex AI, Regia, Multi-tenant/Audit.

Workflow completi lato React in questa tranche: consultazione template, catalogo, redazione quadro operativo, giurisprudenza metadati, Legal Intelligence/news/mediazione/ricerca legale.

Workflow incompleti: deposito end-to-end, editor/generazione atto, dettaglio giurisprudenza, sincronizzazione fonti, portali telematici, dettagli/export economici.

## 6-8. Bug funzionali

Bug trovati: CTA legacy primarie e contratti `writes=legacy_routes` su route che potevano essere read-only React. Bug corretti: rimozione CTA e cambio contratti a `writes=none`. Bug rimasti: route legacy ad alto rischio non convertite.

## 9-12. Endpoint, client, componenti, backend

Endpoint modificati: nessuno. Client API aggiunti/re-export: documents, telematico, comunicazioni, lex, legalIntelligence, templates. Componenti React aggiunti: stati, wizard, compliance, document badge, channel card, message list, LexPanel. Backend modificato: bridge read-only per contratti e link sicuri.

## 13-15. Test

Test aggiunti: `tests/test_legal_sources_registry.py`. Test passati iniziali: typecheck e gate React. Test finali completi tracciati nel report conclusivo.

## 16-19. Gap

Rischi residui: compliance telematica, tariffe complete per tutte le aree, workflow PEC completa, verifica browser end-to-end. Coverage gap legali/tariffari/telematici documentati nei report compliance.

## 20. Prossima fase consigliata

Completare API dedicate per impostazioni sensibili, portali e dettagli/export solo dopo specifiche ufficiali e test end-to-end.

## Aggiornamento finale 2026-05-08

- Redazione Atti: tutti i template, inclusi quelli personali/runtime privi di binding, ricevono un compilatore guidato prudente e non restano fuori dal filtro "Solo modelli con redazione guidata".
- Test Redazione Atti eseguiti: `tests/test_template_atti_workspace.py` e `tests/test_template_atti_master_catalog.py` verdi.
- Workflow Local Signer/PST: corretta la perdita dei metadati ufficiali della busta. I documenti ricevuti dal payload Local Signer/PST vengono conservati sempre; `mantieni_albero_originale` controlla solo se portare l'albero in UI con `preserve_pst_tree`/`auto_pst_acquire`.
- Test PolisWeb/Local Signer eseguiti e verdi nei batch fase 06 telematico; aggiunte verifiche che senza `mantieni_albero_originale` i metadati restano salvati ma l'albero non viene aperto in UI.
- Fase 07 Lex/Legal completata: batch 10-17 rieseguiti verdi dopo i fix; batch 9 isolato in sotto-shard/item per i test lenti, con esito verde.
- Pytest monolitico non dichiarato verde: completamento effettuato con shard/sotto-shard e timeout per job.
