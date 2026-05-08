# Fase 8 - Report finale compliance

## 1-3. Stato e moduli

Stato iniziale: fonti e compliance diffuse tra documentazione, codice e specifiche. Stato finale: aggiunto registro fonti ufficiali e report compliance dedicati. Moduli verificati: tariffario, preventivi, documenti, telematico, PEC/comunicazioni, Lex AI, Legal Intelligence, template atti, privacy/sicurezza, multi-tenant.

## 4-6. Fonti

Fonti censite: Normattiva, Gazzetta Ufficiale, Ministero Giustizia, PST, specifiche PCT, Giustizia Amministrativa, Giustizia Tributaria, SIGP, CNF, DM55/2014, DM147/2022, L.247/2012, DM44/2011, GDPR. Fonti mancanti: versioni applicabili di dettaglio per singolo portale/rito quando non c'e' validazione automatica. Normative collegate in registry.

## 7-11. Coverage

Coverage tariffario: DM55/DM147 censiti, calcoli non modificati. Coverage telematico: canali distinti e manual review dove necessario. Coverage documentale: stati non verificato/conforme separati. Coverage Lex: assenza fonti esplicita. Coverage template: metadati e compatibilita portale non dichiarati conformi senza regole.

## 12-17. Bug e fallback

Bug compliance trovati: contratti bridge read-only ancora marcati `legacy_routes` e CTA legacy primarie. Corretti. Bug rimasti: workflow sensibili legacy. Rischi residui: XSD, portali, PEC reale, tenant completo, tabelle tariffarie complete. Fallback dichiarati: manual review e route legacy ad alto rischio.

## 18-21. Endpoint, UI, test

Endpoint modificati: nessuno. UI compliance aggiornata con componenti e copy. Test aggiunti: `tests/test_legal_sources_registry.py`. Test passati/falliti tracciati nel report finale di sessione.

## 22-25. Regressioni, branch, commit, PR

Regressioni note: nessuna introdotta rilevata dai gate eseguiti. Branch: `Codex/legal-electronic-filing-kIxcV`. Commit e PR da compilare a fine sessione.

## Aggiornamento finale 2026-05-08

- Registro fonti ufficiali presente in `pct/data/legal_sources_registry.json`; test `tests/test_legal_sources_registry.py` verde.
- Telematico/PST: nessuna automazione non autorizzata introdotta; mantenuto il comportamento per cui `mantieni_albero_originale` governa la UI, non la persistenza dei metadati ufficiali.
- Redazione Atti: nessun modello resta senza redazione guidata; i fallback sono prudenziali e tracciati nel dominio, non dati inventati in UI.
- Compliance UI/gate: `run-full-react-migration` e `run-legal-ui-checks` verdi dopo build; 0 CTA legacy primarie nelle route full promosse; 0 mock/demo nelle route full.
- Test: frontend completo verde; pytest verificato con shard/sotto-shard. Il monolite completo non viene presentato come verde perche' va in timeout.
