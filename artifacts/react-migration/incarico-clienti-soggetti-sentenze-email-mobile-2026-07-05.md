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
