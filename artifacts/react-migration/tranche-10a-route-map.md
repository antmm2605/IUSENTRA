# Tranche 10A - Route legacy map

Data: 2026-05-07

## Metodo

Analisi eseguita su `AGENTS.md`, `docs/`, `docs/specs/ministero/`, `deploy/hetzner/`, `ops/`, `.github/`, `tools/CODEX_SUPPORT_STACK.md`, handler Flask, template Jinja, manager `pct/` e test correlati. `rg` non era utilizzabile nella sessione locale per `Accesso negato`; la ricerca e' stata completata con `Select-String` sugli stessi path richiesti.

## /giurisprudenza

- Handler legacy: `web/blueprints/giurisprudenza.py`
- Funzione: `index`
- Template: `web/templates/giurisprudenza/index.html`
- Repository/manager: `get_giurisprudenza()`, `GestioneGiurisprudenza.catalogo_fonti`, `statistiche`, `storage_stats`, `tassonomia`, `filtri`, `cerca`, `recent_sync_runs`
- Permessi: sessione utente (`_richiedi_login`), nessun permesso granulare ulteriore rilevato
- Form presenti: filtri GET, sync POST, import URL POST, import materiale POST multipart, classificazione suggerita via fetch POST legacy
- POST presenti: si, solo legacy
- Action form: `giurisprudenza.sync`, `giurisprudenza.importa_url`, `giurisprudenza.importa_materiale`, `giurisprudenza.classificazione_suggerita`
- Method form: GET e POST
- CSRF: nessun token esplicito rilevato nei template legacy
- Upload: si, import materiale
- Download/export/PDF/DOCX: dettaglio legacy puo esporre documenti e contenuti collegati; non migrato
- Import/classificazione/AI/Lex/generazione: import e classificazione presenti nel legacy; React non li espone
- Crawler/scraper/fonti esterne: il manager legacy contiene logiche di acquisizione fonti; React non invoca acquisizioni
- Workflow approvazione: classificazione e completamento scheda restano legacy
- Dati sensibili: nessun segreto nel payload React; testo completo e file restano fuori dal bridge
- Decisione: sbloccabile solo come archivio/metadati React.

## /giurisprudenza/nuova

- Handler legacy: `web/blueprints/giurisprudenza.py`
- Funzione: `nuova`
- Template: `web/templates/giurisprudenza/form.html`
- Repository/manager: `get_giurisprudenza().empty_record`, `salva_da_form`
- Permessi: sessione utente (`_richiedi_login`)
- Form presenti: scheda sentenza/provvedimento
- POST presenti: si
- Action/method: route corrente, GET/POST
- CSRF: nessun token esplicito rilevato
- Upload/download/import/classificazione: classificazione e import collegati al workflow di scheda
- AI/Lex/generazione: contenuti redazionali e classificazioni restano controllati dal legacy
- Decisione: resta legacy per inserimento, import fonte, classificazione e POST auditato.

## /giurisprudenza/*

- Handler legacy: `dettaglio`, `modifica`, `sync`, `classificazione_suggerita`, `importa_url`, `importa_materiale`
- Template: `giurisprudenza/dettaglio.html`, `giurisprudenza/form.html`
- Repository/manager: `get`, `related`, `judgment_text_versions`, `raw_documents`, `practice_links`, `salva_da_form`, import e classificazione legacy
- Permessi: sessione utente
- Form/POST/upload/download: presenti nei sottopercorsi legacy
- PDF/DOCX/raw/testo completo: disponibili solo nel dettaglio/manager legacy, non nel payload React
- Decisione: resta legacy per dettaglio sentenza, testo completo, file, classificazione, import e audit.

## /legal-intelligence

- Handler legacy: `web/blueprints/legal_intelligence.py`
- Funzione: `index`
- Template: `web/templates/legal_intelligence/index.html`
- Repository/manager: `get_legal_intelligence().build_dashboard_snapshot`, `get_legal_update_pipeline().dashboard_snapshot`, `LegalIntelligenceDailyEngine.dashboard_snapshot`, fascicoli, clienti, agenda, scadenziario, tabelle normative
- Permessi: sessione utente (`_richiedi_login`)
- Form presenti: sync tabelle, monitor fonti, controllo giornaliero, rigenera indice assistito, approvazione update
- POST presenti: si, solo legacy
- Action form: `/legal-intelligence/sync/esegui`, `/monitor/esegui`, `/daily/esegui`, `/daily/rigenera-indice-ai`, `/daily/update/<id>/approva`
- Method form: POST
- CSRF: nessun token esplicito rilevato nei template legacy
- Import/classificazione/AI/Lex/generazione: pipeline e indice assistito restano legacy
- Fonti esterne: monitor fonti gestito solo da legacy
- Workflow approvazione: presente e non migrato
- Decisione: sbloccabile solo come dashboard read-only React.

## /legal-intelligence/news

- Handler legacy: `news`
- Template: `web/templates/legal_intelligence/news.html`
- Repository/manager: `get_legal_update_pipeline().repository.list_news`, `list_matters`, `dashboard_snapshot`
- Permessi: sessione utente
- Form presenti: filtri GET
- POST/upload/import/export: non nella route exact
- Link dettaglio: `/legal-intelligence/news/<slug>` resta legacy
- Decisione: sbloccabile come elenco news gia presenti nel backend.

## /legal-intelligence/mediazione

- Handler legacy: `registro_mediazione`
- Template: `web/templates/legal_intelligence/mediazione.html`
- Repository/manager: `get_legal_intelligence().mediazione_registry_snapshot`
- Permessi: sessione utente
- Form presenti: filtri GET, sync POST e import POST nei sottopercorsi
- POST/upload/import: restano legacy su `/mediazione/sync` e `/mediazione/import`
- Fonti esterne: aggiornamento registro gestito dal legacy
- Decisione: sbloccabile come consultazione registro gia disponibile nel backend.

## /legal-intelligence/*

- Handler legacy: news detail, monitor, daily, approvazione, diff, sync, mediazione sync/import, API snapshot/tabelle/news
- Template: `news_detail.html`, `daily_diff.html`, template admin collegati
- POST/import/approvazione/AI: presenti
- Decisione: resta legacy salvo exact `/news` e `/mediazione`.

## /ricerca-legale

- Handler legacy: `web/blueprints/terminology_aliases.py`
- Funzione: `ricerca_legale`
- Template: nessuno; redirect a `legal_intelligence.index`
- Permessi: ereditati dalla destinazione legacy
- Form/POST/upload/download/import: assenti
- Decisione: sbloccabile come alias/hub React verso Legal Intelligence.

## /ricerca-legale/*

- Handler legacy specifico: non rilevato
- Decisione: resta non React/legacy per evitare sblocco di sottopercorsi non governati.

## /checklist

- Handler legacy: `web/bootstrap/checklist_routes.py`
- Funzione: `checklist_atti`
- Template: `web/templates/checklist/lista.html`
- Repository/manager: catalogo checklist atti/deposito
- Permessi: sessione utente
- Workflow collegati: wizard, upload documenti e controlli deposito su route correlate
- Decisione: resta legacy.

## /deposito/checklist

- Handler legacy: `web/bootstrap/deposito_routes.py`
- Funzione: `deposito_checklist`
- Template: `web/templates/deposito_checklist.html`
- Repository/manager: checklist deposito e contesto telematico
- Permessi: sessione utente
- Workflow collegati: deposito telematico, allegati, firme, Local Signer
- Decisione: resta legacy e nessuna route telematica viene sbloccata.
