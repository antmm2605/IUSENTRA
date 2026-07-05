# Incarico operativo 2026-07-05: clienti, soggetti, sentenze, email e lettura documenti

## Richiesta

Verificare e correggere su `https://app.iusentra.it`:

- modifica cliente `FBA5C7FF`: il salvataggio mostra conferma ma non persiste realmente;
- anagrafiche cliente: inserendo il comune la UI deve suggerire il comune e compilare automaticamente CAP e provincia;
- soggetti e parti: stessa logica comune/CAP/provincia sia in creazione sia in modifica/salvataggio;
- fascicoli: la sezione `Sentenze — controllo economico` deve leggere automaticamente i documenti del fascicolo, analizzare sentenze, crediti liquidati ex artt. 91/93 c.p.c., contributo unificato e dati utili per Agenda, Scadenziario, notifiche, web push e parcelle;
- email PEC ed email ordinaria: su tablet/mobile deve apparire prima l'elenco; cliccando una email deve aprirsi una finestra/pannello di lettura della email selezionata;
- documenti su mobile: serve un lettore compatto per visualizzare i documenti senza costringere l'avvocato a uscire dal flusso.

## Strategia tecnica

La strategia primaria è correggere i flussi reali già presenti, non creare motori paralleli:

1. riprodurre il difetto sulla produzione Hetzner e leggere log/API/database in sola lettura;
2. individuare il punto esatto tra React, API JSON, repository SQL/PostgreSQL e mirror JSON che mostra successo senza persistenza;
3. riusare un solo servizio di lookup comuni per clienti e soggetti, con normalizzazione di comune, CAP e provincia;
4. collegare il controllo economico sentenze al reader documentale del fascicolo, alla pipeline Document AI/OCR e al motore `pct/fascicolo_sentenza_economica.py` / `pct/sentenza_economic_*`;
5. mantenere l'analisi incrementale e performante: solo documenti nuovi/modificati o non ancora presidiati, niente rilettura pesante dell'intero archivio a ogni caricamento;
6. migliorare la UI responsive di comunicazioni e documenti dentro i componenti React esistenti;
7. blindare con test mirati e prove visive su produzione e, dopo riallineamento, su Docker locale `127.0.0.1:8080`.

## Superfici e file da presidiare

- Clienti React/API: `frontend/src/components/AnagraficaClientiPage.tsx`, `frontend/src/components/NuovoClientePage.tsx`, `web/services/react_clienti_bridge.py`, `web/bootstrap/clienti_routes.py`.
- Soggetti React/API: `frontend/src/components/SoggettiPage.tsx`, `web/services/react_soggetti_bridge.py`, `web/bootstrap/soggetti_routes.py`, `pct/soggetti.py`.
- Comuni/CAP/province: database/script esistenti collegati a `scripts/build_uffici_giudiziari_comuni_db.py`, `scripts/audit_uffici_giudiziari_comuni_db.py` e API territoriali già presenti.
- Fascicoli/sentenze/documenti: `frontend/src/components/FascicoliPage.tsx`, `pct/fascicolo_sentenza_economica.py`, `pct/sentenza_economic_workflow.py`, `pct/sentenza_economic_repository.py`, `web/services/sentenza_economic_runtime.py`.
- PEC/email responsive: `frontend/src/components/EmailPecPage.tsx`, `frontend/src/components/EmailPecPage.css`, `frontend/src/features/comunicazioni/*`, `web/services/react_email_bridge.py`, `web/blueprints/email_ordinaria.py`.

## Vincoli

- Fonte dati operativa: SQLite locale o PostgreSQL produzione; JSON solo mirror/cache.
- Nessun invio PEC reale, nessun SMTP server-side per depositi/notifiche legali.
- Nessun fallback legacy come soluzione finale.
- Date, orari e importi visibili in formato italiano, fuso `Europe/Rome`.
- Prove finali su produzione richiesta dall'utente e poi su copia locale reale `127.0.0.1:8080`.
- Se la sessione browser autenticata non è disponibile, il lavoro resta aperto per la prova visiva autenticata anche con test automatici verdi.

## Stato iniziale osservato

- Worktree locale pulita.
- Branch locale: `Codex/legal-electronic-filing-kIxcV`.
- Browser integrato aperto su `https://app.iusentra.it/clienti/FBA5C7FF/modifica` reindirizza a login, quindi la prova visiva autenticata non è ancora disponibile nella scheda Codex.
- La diagnosi server/API/log deve proseguire su Hetzner senza toccare volumi o dati applicativi.

## Prove richieste prima del report positivo

- Salvataggio modifica cliente su produzione con ricarica e verifica reale della persistenza.
- Autocomplete comune e auto-compilazione CAP/provincia su cliente e soggetto/parte.
- Controllo economico sentenze su fascicolo reale con lettura documenti e popolamento automatico della sezione.
- Email PEC ed email ordinaria su desktop/tablet/mobile: elenco, apertura dettaglio, lettura contenuto e allegati senza overflow.
- Lettore documenti mobile su fascicolo reale.
- Test automatici mirati, build React, UTF-8, audit dati dove toccato, commit/push branch gemelli, deploy Hetzner, container unico `iusentra-app`, `/api/pronto` produzione.

## Stato implementazione 2026-07-05

- Diagnosi produzione eseguita in sola lettura: il cliente `FBA5C7FF` risulta nel tenant `studio-legale-giuseppe-montagnese` su SQLite; il browser integrato non era autenticato e la pagina produzione ha reindirizzato a login, quindi la prova visiva autenticata resta da eseguire.
- Correzione anti falso-verde: `submitFormJson` ora rifiuta risposte non JSON o redirect a login, così un HTML di login non può più produrre toast `salvato`.
- Clienti e soggetti: normalizzazione server-side unica con `web/services/territorio_forms.py`; Comune italiano compilato da form o autocomplete, CAP/provincia corretti in salvataggio per cliente, sede legale, domicilio e soggetti/parti.
- UI cliente/soggetto: `NuovoClientePage` usa autocomplete Comuni su API `/api/v1/ui/territorio/comuni`, compila CAP/provincia e conserva anche `dom_cap`.
- Persistenza clienti: recapiti legacy `email_principale`/`telefono_principale` vengono riletti ma il salvataggio SQL usa i campi canonici `email`/`telefono`.
- Sentenze: `build_sentenza_economic_payload` avvia lettura incrementale dei documenti candidati già indicizzati via Document AI/OCR/search index, senza limite fisso sui primi documenti; salva audit/eventi economici e alimenta il riepilogo `Sentenze — controllo economico`.
- Email PEC/email ordinaria: su tablet/mobile l'elenco resta la vista primaria e la selezione apre `iu-mail-reader-pane` come pannello di lettura con comando `Elenco`.
- Fascicoli/documenti mobile: il modal anteprima documenti è ora etichettato `Lettore documento` e su mobile/tablet occupa il viewport con toolbar compatta e iframe a piena altezza.

## Guardrail automatici eseguiti

- `npm --prefix frontend run typecheck` -> passato.
- `python -m pytest -q tests/test_react_shell.py::test_react_comunicazioni_email_messaggi_collegate_nav_e_shell tests/test_react_shell.py::test_react_clienti_nuovo_e_soggetti_collegati_nav_api_lex_cf tests/test_react_shell.py::test_submit_form_json_non_accetta_html_come_successo tests/test_react_shell.py::test_post_modifica_cliente_json_normalizza_comune_e_persiste tests/test_react_shell.py::test_post_modifica_soggetto_json_normalizza_comune_e_persiste tests/test_territorio_italia.py tests/test_clienti.py::test_cliente_from_dict_accetta_alias_recapiti_legacy` -> passato.
- `python -m pytest -q tests/test_react_fascicoli_sentenze_economiche.py tests/test_sentenza_economic_runtime.py` -> passato.

## Stato verifica reale

- Non verificato su macchina reale autenticata e non ancora verificato su `https://app.iusentra.it` autenticato dopo deploy.
- Da completare prima di report positivo: build React, bump versione, commit/push branch gemelli, check GitHub, deploy Hetzner, container unico `iusentra-app`, `/api/pronto`, prova produzione autenticata e prova locale reale `127.0.0.1:8080` su cliente, soggetti, fascicolo/sentenze, email responsive e lettore documenti.

## Aggiornamento correttivo 2026-07-05 - evidenze automatiche e lettore mobile

- Il controllo economico della lista fascicoli e del dettaglio ora usa anche le evidenze automatiche lette dai documenti indicizzati del fascicolo. Le ricevute PagoPA/contributo unificato popolano importo, stato, data e documento fonte; le sentenze compatibili con RG/parti possono proporre liquidazione, spese/esborsi e parcella; le sentenze non riconciliate restano fuori dal totale automatico.
- `Prossima scad.` viene arricchita automaticamente dai documenti del fascicolo quando non esiste una scadenza già collegata, riusando la logica di estrazione date processuali da PEC/documenti e validando RG o parti del fascicolo.
- Il lettore documenti mobile non dipende più dal viewer PDF nativo del telefono. Per gli URL `/fascicoli/<id>/documenti/<id>/visualizza?viewer=mobile` il backend genera una pagina HTML interna con immagini PNG delle pagine PDF, servite dalla stessa route autenticata e tenant-aware.
- Nelle liste Clienti, Soggetti e Fascicoli le azioni principali sono state spostate nella cella principale della riga e i rail laterali scendono sotto la tabella nei viewport intermedi, così le colonne operative restano leggibili.

Guardrail automatici eseguiti:

- `python -m py_compile web/bootstrap/fascicoli_document_helpers.py web/bootstrap/fascicoli_document_routes.py web/services/react_fascicoli_bridge.py web/services/sentenza_economic_runtime.py` -> passato.
- `python -m pytest -q tests/test_polisweb.py::test_visualizza_documento_pdf_mobile_renderizza_pagine_png` -> passato.
- `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_react_shell.py::test_post_modifica_cliente_json_normalizza_comune_e_persiste` -> passato.
- `python -m pytest -q tests/test_react_fascicoli_sentenze_economiche.py tests/test_sentenza_economic_runtime.py` -> passato.
- `npm --prefix frontend run typecheck` -> passato.

Stato verifica reale:

- Browser integrato collegato e predisposto per prove visive reali desktop/tablet/mobile.
- Da completare prima del report positivo: rebuild locale reale `127.0.0.1:8080`, prova visiva su produzione dopo deploy, prova visiva locale sulla stessa versione, commit/push branch gemelli, deploy Hetzner, container unico `iusentra-app`, `/api/pronto` produzione e igiene repository.

## Aggiornamento correttivo 2026-07-05 - navigazione editor libero e verifica visiva locale

- L'`Editor libero` è stato aggiunto come voce autonoma nella navigazione Studio e come azione primaria nella pagina `Editor professionale`, con apertura diretta di `/template-atti/editor`.
- Il contratto dati/React censisce ora la voce `Editor libero` su `/template-atti/editor`, così il menu non resta solo grafico.
- Prova reale locale su `http://127.0.0.1:8080/editor-professionale`: pulsante `Editor libero` visibile, click eseguito, apertura di `/template-atti/editor`, vista `Documento libero` caricata con foglio vuoto e nessun errore console. Durante la prova post-build è emerso un blocco reale su `Caricamento compilazione`: è stato aggiunto un fallback governato per la modalità editor libero con timeout sulla fetch del compilatore, poi la prova è stata ripetuta sulla build Docker reale con asset `TemplateAttiPage-Dz0IqbYS.js`.
- Prova reale locale su `http://127.0.0.1:8080/clienti`: le icone `Apri scheda cliente`, `Modifica cliente`, `Apri cartella cliente` ed `Elimina cliente` risultano centrate e uniformi a `34x34`, come richiesto dall'utente.
- Prova reale locale su `http://127.0.0.1:8080/fascicoli?vista=economica`: il fascicolo `RG 466/2023` mostra popolamento automatico di contributo, spese/esborsi, liquidazione, parcella e `Prossima scad.` dai documenti indicizzati.
- Prova reale locale su `http://127.0.0.1:8080/fascicoli/DC5BF1DB#documenti` in viewport mobile `390x844`: click su `Anteprima interna`, modal `Lettore documento` aperto, URL interno `/fascicoli/DC5BF1DB/documenti/1D095D8B/visualizza?viewer=mobile`, pagine PDF renderizzate come immagini dentro il lettore e nessun errore console.
- Prova reale locale diretta su `/fascicoli/DC5BF1DB/documenti/1D095D8B/visualizza?viewer=mobile`: prima pagina caricata in modo eager, immagine completa, larghezza documento senza overflow orizzontale.

## Aggiornamento correttivo 2026-07-06 - performance vista economica automatica

- Causa rilevata sulla copia Docker reale: la vista `/fascicoli?vista=economica` popolava correttamente i dati automatici, ma preparava sempre il fallback `extracted_text.json` dei documenti prima di sapere se servisse. Questo causava scansioni ripetute dello storage Document AI durante il caricamento lista.
- Correzione: `web/services/react_fascicoli_bridge.py` non pre-carica più le righe estratte; `pct/fascicolo_document_catalog.py` prova prima repository Document AI, SQLite e JSON indicizzato, e solo in assenza di righe usa il fallback sui file estratti limitandolo al singolo `fascicolo_id`.
- Guardrail anti-regressione: aggiunti test che impediscono la scansione fallback quando il repository ha già i testi e verificano che il fallback riceva `fascicolo_ids=[id_fascicolo]`.
- Misura prima del fix su container reale: API economica circa `10,66 s`, con `document_ai_extracted_rows_by_fascicolo` responsabile di circa `9,10 s`.
- Misura dopo il fix su container reale: API interna circa `2,27 s`; HTTP reale `127.0.0.1:8080` circa `1,62-1,70 s` per `/api/v1/ui/fascicoli?page=1&page_size=25&sort=rg&view=economica`; la vista operativa resta circa `1,33 s`.
- Prova visiva reale locale desktop `1365x768`: `/fascicoli?vista=economica` carica senza login, overlay, errori console o overflow orizzontale. Il fascicolo `RG 466/2023` mantiene `Prossima scad. 10/03/2026`, contributo `€ 98,00`, spese/esborsi `€ 125,00`, liquidazione `€ 1.500,00` e parcella `€ 2.028,20`.
- Prova visiva reale locale mobile `390x844`: `/fascicoli/DC5BF1DB#documenti`, scroll fino a `Documenti e atti`, click reale su `Anteprima interna`, modal `Lettore documento` con iframe interno `/fascicoli/DC5BF1DB/documenti/1D095D8B/visualizza?viewer=mobile`, pagina 1 e pagina 2 renderizzate come immagini. Verifica diretta del viewer: `3` immagini, `2` già caricate nel primo viewport, zero overflow orizzontale e zero errori console.

Guardrail automatici eseguiti:

- `python -m py_compile pct\fascicolo_document_catalog.py web\services\react_fascicoli_bridge.py web\blueprints\api_v1_react.py web\services\storage_runtime.py` -> passato.
- `python -m pytest -q tests/test_storage_strategy.py::test_sqlite_runtime_seed_check_usa_immutable_se_readonly_fallisce tests/test_storage_strategy.py::test_sqlite_runtime_non_rilancia_migrazione_se_db_core_ha_fascicoli tests/test_react_shell.py::test_react_fascicoli_lista_operativa_non_avvia_document_ai_automatico tests/test_react_shell.py::test_react_fascicoli_lista_popola_economia_e_scadenza_da_documenti tests/test_react_shell.py::test_react_fascicoli_economia_usa_candidati_documentali_senza_fallback_totale tests/test_fascicolo_document_catalog.py::test_document_ai_texts_for_catalog_riusa_cache_extracted_files tests/test_fascicolo_document_catalog.py::test_document_ai_texts_for_catalog_non_scansiona_fallback_se_repo_ha_testi tests/test_fascicolo_document_catalog.py::test_document_ai_texts_for_catalog_fallback_limitato_al_fascicolo` -> passato.
- `python -m pytest -q tests/test_react_shell.py::test_react_fascicoli_suite_completa_route_componenti_e_lex tests/test_polisweb.py::test_visualizza_documento_pdf_mobile_renderizza_pagine_png` -> passato.
- `python -m pytest -q tests/test_react_fascicoli_sentenze_economiche.py tests/test_sentenza_economic_runtime.py` -> passato.
- `python -m pytest -q tests/test_utf8_integrity.py` -> passato.
- `npm --prefix frontend run typecheck` -> passato.
- `python tools/codex_harness/run_codex_quality_gate.py --mode ui-support` -> non applicabile come verde di prodotto: il gate ha bloccato correttamente file prodotto in `web/`, `pct/`, `frontend/` e `tests/` perché non è una patch di solo supporto UI. Lo stato positivo viene quindi fondato sui gate applicativi sopra e sulle prove reali.
