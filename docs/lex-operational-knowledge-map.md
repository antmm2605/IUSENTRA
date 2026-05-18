# Lex AI Operational Knowledge Map

## Scopo

Questa mappa descrive le sorgenti operative reali che Lex AI puo' interrogare in IUSENTRA. Il principio di progetto e' semplice: Lex non legge file a caso, non usa dati finti e non deduce dati gestionali dal prompt. Ogni risposta su clienti, fascicoli, scadenze, agenda, preventivi, documenti, messaggi o altri dati riservati deve passare da tool deterministici, tenant corrente, permessi utente e audit.

Il layer operativo resta governato da feature flag, fail-closed in multi-studio e compatibile con Flask, App V2/React, JSON, SQLite e PostgreSQL dove gia' previsto. Dal 2026-05-15 e' attivo di default nel bounded workflow Lex, con opt-out esplicito per rollback.

Aggiornamento 2026-05-17: il registro operativo non e' piu' solo una mappa di lettura. I template della console pianificazioni alimentano micro-agenti Lex interni che girano di notte o su comando (`lex-agenti-operativi`) e salvano `lex_operational_agents.json`. Ogni agente ispeziona solo archivi tenant-aware, non compie azioni dispositive e marca l'esito `Da verificare` quando mancano archivi, documenti indicizzati o fonti citabili. Il perimetro copre clienti/soggetti, agenda/scadenze, preventivi/parcelle/tariffario, PEC, posta ordinaria, fascicoli/documenti/timeline, editor normale/professionale con chat Lex, citazioni Cassazione, PCT, fatturazione/SDI, portale cliente, GDPR/antiriciclaggio, AI locale/RAG e integrazioni native.

Aggiornamento 2026-05-18: le domande operative reali sono diventate gate obbligatori. `Dammi la scheda cliente ...` deve restituire la scheda cliente con recapiti e fascicoli reali autorizzati; `Dammi la scheda soggetto ...` e `Quali sono le parti del fascicolo?` devono leggere soggetti, assistiti, controparti e ruoli processuali reali; `Qual è l'ultima PEC?` deve leggere la casella PEC tenant-aware senza filtro sul testo della domanda e mostrare oggetto, mittente, destinatari, data, cartella e numero allegati. Il bridge HTTP deve tenere queste letture nel workflow `operational_knowledge` anche quando il profilo le classifica come `pec_comunicazioni`. L'indicizzazione documentale deve inoltre dichiarare i file non letti: i `.pdf.p7m` leggibili vengono trattati come PDF interni o estratti tramite CAdES, i `.txt` vengono letti come testo puro e i `.eml` vengono indicizzati con oggetto, mittente, destinatari, data, corpo e allegati supportati; errori e formati non supportati arrivano alla pagina fascicolo come avvisi per-file. Le bozze di diffida/messa in mora devono uscire come documento leggibile anche quando il modello produce una riga piatta: il backend normalizza titolo, destinatario, oggetto, sezioni, chiusura e dati da completare prima della risposta e il click sul titolo/pulsante della bozza in chat salva il documento nel fascicolo e apre subito l'editor professionale.

Aggiornamento 2026-05-18, caso pilota fonti pubbliche: `Questione Penale Pendente del ricorso R.G. 9926/2026` è la prova obbligatoria prima di scalare il generatore corpus. Il layer operativo deve recuperare scheda Cassazione, allegato, OCR e discrepanza R.G., poi rispondere alla domanda dell'avvocato con sintesi, natura dell'atto, punto di diritto, motivi/censure, articoli, udienza, ricorrente/relatore, PDF, stato e limiti. Le domande sugli articoli possono attivare `web_libero`, che resta separato dalle fonti ufficiali e non viene promosso a corpus.

Aggiornamento 2026-05-18, `Web libero` chat Lex: quando il flag manuale è attivo, il router deve usare solo la ricerca web libera della singola richiesta, senza fonti DB/fascicolo come contesto di risposta, senza allowlist ufficiale, senza blocco da fonte autorizzata e senza warning visibili. I risultati restano `web_libero`, `verified_reference=false`, `saved_to_db=false`; controllo e responsabilità professionale spettano all'avvocato.

## Regole di accesso

- Tenant: ricavato dal contesto Flask (`g.tenant`, `g.tenant_context_slug`, `g.data_paths`) o da contesto applicativo esplicito nei test.
- Utente: ricavato da `g.utente_corrente` o da contesto esplicito.
- Permessi: base `ai.usa`, piu' permesso dominio quando la sorgente contiene dati operativi riservati.
- Storage: usare solo repository/helper tenant-aware (`web.helpers`, `web.services.tenant_paths`, repository gia' esistenti).
- Privacy: non esporre path filesystem, segreti, token, credenziali o dati di tenant diversi.
- Web: vietato per dati cliente/studio; ammesso solo per fonti pubbliche se la policy Lex pubblica lo consente.

## Tabella sorgenti

| Sorgente | Moduli principali | Tipo dati | Chiave tenant/storage | Permessi minimi | API/repository disponibili | Stato Lex | Rischi | Test necessari |
|---|---|---|---|---|---|---|---|---|
| Clienti | `pct/clienti.py`, `web.helpers.get_clienti`, `web/services/react_clienti_bridge.py` | Anagrafiche, recapiti, documento identita', procedimenti collegati | `CLIENTI_DB`, `STUDIO_DB` | `ai.usa`, `clienti.leggi` | `GestioneClienti.get`, `tutti`, `cerca`, `get_by_codice_fiscale`, `get_by_partita_iva` | Integrato nel layer operativo: scheda cliente reale con recapiti/fascicoli | PII, ricerca ambigua, fallback tenant globale | lookup id, ricerca, scheda cliente, ambiguita', RBAC, tenant A/B |
| Soggetti e parti | `pct/soggetti.py`, `web.helpers.get_soggetti`, `lex/context/anagrafica_context.py` | Controparti, parti processuali, ruoli nel fascicolo | `SOGGETTI_DB`, `SOGGETTI_PARTI_DB` | `ai.usa`, `clienti.leggi` o `fascicoli.leggi` se legati a fascicolo | `GestioneSoggetti.get`, `tutti`, `cerca`, `parti_fascicolo`, `fascicoli_con_soggetto` | Integrato nel layer operativo: scheda soggetto reale e parti del fascicolo con ruoli | PII e legame a fascicoli non autorizzati | ricerca soggetti, parti fascicolo, negato senza permessi |
| Fascicoli | `pct/fascicoli.py`, `web.helpers.get_fascicoli`, `lex/context/fascicolo_context.py` | Pratiche, stato, ufficio, documenti, attivita', depositi | `FASCICOLI_DB`, `FASCICOLI_DOCS`, `FASCICOLI_ARCH` | `ai.usa`, `fascicoli.leggi` | `GestioneFascicoli.get`, `tutti`, `cerca`, `fascicoli_con_scadenze_imminenti` | Integrato ma non come registry unico | Path documenti, allegati, attivita' sensibili | get/search, documenti senza path, tenant isolation |
| Agenda | `pct/agenda.py`, `web.helpers.get_agenda`, `lex/context/agenda_context.py` | Appuntamenti, udienze, promemoria | `AGENDA_DB` | `ai.usa`, `agenda.leggi` | `Agenda.get`, `tutti`, `per_giorno`, `per_settimana`, `per_cliente`, `cerca` | Integrata nel retrieval | Date non normalizzate, eventi cliente sensibili | range settimana, cliente, permesso negato |
| Scadenziario | `pct/scadenziario.py`, `web.helpers.get_scadenziario`, `lex/context/scadenze_context.py` | Termini, calcoli, priorita', trace calcolo | `SCADENZIARIO_DB` | `ai.usa`, `scadenziario.leggi` | `GestioneScadenziario.get`, `tutte`, `imminenti`, `scadute`, `calcola_avanzata` | Integrato nel retrieval | Spiegazioni termine senza trace/fonti interne | scadenze fascicolo/cliente, settimana, perche' calcolo |
| Preventivi | `pct/preventivi.py`, `web.helpers.get_preventivi`, `lex/context/operational_context.py` | Preventivi, stati, voci, totali, piani pagamento | `PREVENTIVI_DB` | `ai.usa`, `fatturazione.leggi` | `get_preventivo`, `tutti_preventivi`, `preventivi_per_cliente`, `preventivi_per_fascicolo`, `select_best_preventivi_runtime` | Integrato parzialmente nel workflow economico | Importi inventati, collegamenti mancanti a cliente/fascicolo | get, cliente, fascicolo, assenza dati, no importi inventati |
| Conferimenti incarico | `pct/preventivi.py`, `web.helpers.get_preventivi` | Conferimenti, firma, compenso pattuito, collegamento preventivo | `PREVENTIVI_DB` | `ai.usa`, `fatturazione.leggi` | `get_conferimento`, `tutti_conferimenti`, `conferimenti_per_preventivo`, `conferimenti_per_cliente`, `conferimenti_per_fascicolo` | Parziale nel contesto economico | Stato firma non verificato, confusione con preventivo | get, preventivo collegato, fascicolo, gap se assente |
| Tariffario forense | `pct/tariffario.py`, `pct/motore_preventivo.py`, `pct/data/tariffario_dm147_2022.json` | Calcolo compensi, scaglioni, fasi, complessita' | Statico versionato nel repo + dati preventivo | `ai.usa`, `fatturazione.leggi` | `calcola_compenso`, cataloghi materie/gradi/fasi | Parziale nel workflow economico | Calcolo senza parametri, norma non citata come fonte pubblica | parametri completi, parametri mancanti, no stime inventate |
| Parcelle e fatturazione | `pct/fatturazione.py`, `web.helpers.get_fatturazione`, `web/services/react_fatturazione_bridge.py` | Parcelle, fatture, saldi, incassi | `FATTURAZIONE_DB` | `ai.usa`, `fatturazione.leggi` | `GestioneFatturazione.get`, `tutte`, `per_cliente`, `per_fascicolo`, `saldo_cliente`, `statistiche` | Parziale nel contesto economico | Importi sensibili, stato pagamento | cliente, fascicolo, saldo, RBAC |
| Attivita' e timesheet | `pct/timesheet.py`, `web.helpers.get_timesheet`, `pct/economic_dashboard.py` | Attivita' lavorate, ore, valore, stato fatturazione | `TIMESHEET_DB` | `ai.usa`, `fatturazione.leggi` | `GestioneTimesheet.get`, `tutte`, `per_cliente`, `per_fascicolo`, `riepilogo_cliente`, `riepilogo_fascicolo` | Da integrare | Attivita' non fatturate e valore economico sensibili | svolte non fatturate, cliente/fascicolo, permesso negato |
| Documenti fascicolo | `pct/fascicoli.py`, `pct/document_intelligence/*`, `lex/context/document_context.py`, `lex/tools/fascicolo_documents.py` | Metadati documenti, testo estratto, versioni, hash, chunk | `FASCICOLI_DOCS`, `FASCICOLI_DB`, `documenti_ai/` | `ai.usa`, `fascicoli.leggi` | `GestioneFascicoli`, `DocumentAIRepository`, `DocumentAIService.search_fascicolo_document` | Integrato con indice Lex e avvisi per-file; `.pdf.p7m` letto come PDF interno o payload CAdES, `.txt` come testo puro, `.eml` con intestazioni/corpo/allegati supportati | Path file, testo non estratto, documenti non pronti | elenco senza path, search citabile, hash/versione, p7m leggibile, txt/eml leggibili, avvisi file non letti |
| Messaggi, PEC, email ordinaria | `pct/messaggi.py`, `pct/email_client.py`, `web/services/mailbox_sync_runtime.py`, `web/services/react_email_bridge.py` | Messaggi inviati, inbox PEC, posta ordinaria, allegati | `MESSAGGI_DB`, `EMAIL_CASELLA_DB`, `EMAIL_ORDINARIA_DB` | `ai.usa`, `messaggi.leggi` | `GestioneMessaggi`, `GestioneEmailRicevute.tutte`, `get` | Integrato nel layer operativo: ultima PEC/email e inventario comunicazioni | Segreti SMTP/IMAP, allegati, PII, fallback globale email | messaggi cliente/fascicolo, ultima PEC, no segreti/path, tenant fail-closed |
| Notifiche | `pct/notifications/*`, `web/services/notifications_runtime.py`, `web/services/topbar_operational.py` | Notifiche utente, preferenze, delivery | `NOTIFICATIONS_DB` | `ai.usa` e utente corrente | `NotificationRepository.list_notifications`, `NotificationService` | Da integrare | Notifiche di altri utenti/tenant | lista utente corrente, tenant A/B |
| Portali e telematico | `pct/pst_*`, `pct/pdp_*`, `web/services/pdp_penale_runtime.py`, `lex/context/telematico_context.py`, `lex/retrieval/sources/telematico.py` | Stato portali, checklist, depositi, import, esiti | `TELEMATICO_DB`, `PDP_PENALE_DB`, `PORTALE_DB`, `EMAIL_CASELLA_DB` | `ai.usa`, `telematico.leggi` | Servizi runtime telematici, contesto Lex telematico | Integrato nel workflow telematico | Credenziali, sessioni portale, azioni dispositive | solo read-only, niente depositi automatici, audit |
| Template atti | `pct/template_atti.py`, `pct/template_atti_repository.py`, `lex/tools/template_atti_tool.py` | Template, categorie, corpo, metadata editor | `TEMPLATE_ATTI_DB`, repository SQL opzionale | `ai.usa`, `fascicoli.leggi` | `GestioneTemplateAtti.tutti`, `get`, `select_best_templates` | Integrato parzialmente | Template scambiato per documento fascicolo reale | search, get, citazione come template |
| Editor Lex e chat redazionale | `lex/tools/editor_ai.py`, `docs/EDITOR_AI_FASCICOLO.md`, API `/api/v1/ui/fascicoli/<id>/editor-ai/*` | Bozza, documento corrente, proposte modifica, export DOCX/PDF | `FASCICOLI_DB`, `FASCICOLI_DOCS`, `TEMPLATE_ATTI_DB`, `LOCAL_AI_DB` | `ai.usa`, `fascicoli.leggi` | `collect_fascicolo_context`, `generate_editor_draft`, `read_editor_document`, `propose_editor_edits`, `export_editor_document` | Governato da agente `redazione_atti_editor` | Modifiche non confermate, fonti non verificate, documenti non indicizzati | proposta pending, niente applicazione automatica, citazioni verificate |
| Citazioni Cassazione verificate | `pct/giurisprudenza.py`, `pct/legal_update_pipeline.py`, `lex/retrieval/official_web.py` | Massime, sentenze, ordinanze, riferimenti numerici | `GIURISPRUDENZA_DB`, `LEGAL_INTELLIGENCE_DB`, archivi ufficiali | `ai.usa` | ricerca fonti ufficiali, legal update repository, corpus giurisprudenza | Governato da agente `giurisprudenza_cassazione` | Numero/data/sezione inventati o non riscontrati | riferimento esatto, testo/estratto, stato `Da verificare` se manca riscontro |
| Legal intelligence | `pct/legal_intelligence.py`, `web/helpers.get_legal_intelligence`, `lex/retrieval/sources/legal_intelligence.py` | Fonti ufficiali, motori, alert, trace, dashboard | `LEGAL_INTELLIGENCE_DB`, `NORMATIVE_TABLES_DB` | `ai.usa` | `GestioneLegalIntelligence.catalogo_fonti`, `catalogo_motori`, `recent_alerts`, `build_dashboard_snapshot` | Integrata come sorgente legale | Fonte pubblica non equivalente a diritto vincolante | alert, fonte, distinzione pubblico/operativo |
| Update intelligence | `pct/legal_update_pipeline.py`, `pct/legal_update_repository.py`, `lex/retrieval/sources/legal_updates.py` | News normative, review queue, fonti, analisi | Derivato da `LEGAL_INTELLIGENCE_DB`, SQLite/PostgreSQL | `ai.usa` | `LegalUpdateRepository.search_lex_sources`, `list_news`, `list_published_*` | Integrata nel retrieval legale | Web live non autorizzato, update non revisionati | search locale, no network, stato review |
| Fonti ufficiali Legal Source Engine | `lex/legal_sources/*`, `docs/lex_ai_legal_source_engine*.md` | Normattiva, Gazzetta, giurisprudenza, prassi, fonti UE/CEDU | `data/legal_sources`, `indexes/legal_sources`, `artifacts/legal_sources` ignorati | `ai.usa`; rete off salvo flag esplicito | `LegalSourceTools`, `LegalSourceRetriever`, adapter registrati | Integrata come motore nativo locale | Nessuna citazione inventata, rete off default | search fixture/indice locale, citation policy |
| Web libero chat Lex | `lex/retrieval/official_web.py`, `lex/retrieval/sources/official_web.py`, `lex/operational_knowledge/tools.py` | Risultati pubblici non necessariamente ufficiali | Nessuno storage tenant, singola richiesta | `ai.usa` | `search_free_public_web` | Libero quando l'avvocato attiva il flag: nessuna allowlist ufficiale, nessun DB/corpus, nessun warning visibile | Confusione tra risultato web e fonte ufficiale | source_type `web_libero`, `verified_reference=false`, `saved_to_db=false`, nessuna promozione automatica |
| Audit | `pct/auth.py`, `audit/*`, `web/services/audit_surface.py`, `lex/telemetry/audit.py` | Eventi utente, azioni, esiti, AI trace | `AUDIT_DB`, `STUDIO_DB` | `ai.usa`, `ai.audit` per lettura; scrittura audit sempre interna | `GestioneUtenti.registra_evento`, `audit_log` | Telemetria Lex esistente, da estendere per query operative | PII nei dettagli, leak domanda integrale se sensibile | evento generato, esito negato, dettagli minimizzati |

## Stato integrazione Lex attuale

- `lex/context/builder.py` carica gia' sezioni strutturate per studio, agenda, scadenziario, economico, fascicolo, documenti e anagrafica.
- `lex/retrieval/source_router.py` instrada workflow operativi e legali verso source adapter distinti.
- `lex/tools/studio_data_gateway.py` offre lookup cliente/fascicolo, ma e' parziale, usa fallback tenant poco severi fuori da Flask e non copre tutte le aree operative.
- `lex/formatting/answer_builder.py` ha un percorso `studio_data_lookup`, ma non espone un registry unico, non registra audit operativo completo e non restituisce sempre fonti interne strutturate.
- `lex/legal_sources/*` fornisce il Legal Source Engine nativo per fonti ufficiali, con rete disabilitata di default.

## Implementazione introdotta

Il layer `lex/operational_knowledge/` e' il punto unico governato per:

1. Registry delle sorgenti operative.
2. Permission guard centralizzato.
3. Query router deterministico.
4. Tool interni per dati strutturati.
5. Retrieval documentale citabile quando disponibile.
6. Response composer con fonti, limiti, confidence e coverage gaps.
7. Audit degli accessi e dei blocchi.
8. Feature flag default-on con rollback esplicito.

Integrazioni runtime:

- `lex/http_bounded_bridge.py` prova il layer operativo solo quando non ci sono allegati e `LEX_OPERATIONAL_KNOWLEDGE_ENABLED` non e' spento esplicitamente; in caso di rifiuto o errore controllato ricade sul bounded workflow esistente.
- `lex/tools/registry.py` registra `operational_knowledge` come tool interno, senza endpoint pubblico nuovo.
- Le risposte operative espongono `workflow=operational_knowledge`, `provider=deterministic`, `coverage_gaps`, `permissions_applied`, `operational_objects` e `audit_event_id`.
- Le domande dispositive come invio PEC, deposito, firma, pagamento o cancellazione vengono bloccate e trasformate in richiesta di consultazione/revisione.

## Test prioritari

- Default on: query cliente/fascicolo/scadenze/preventivi usano repository reali.
- Opt-out flag off: Lex non attiva il nuovo layer.
- Tenant A/B: dati non condivisi.
- RBAC: negato senza `ai.usa` o permesso dominio.
- Privacy: nessun path, token, password o segreto in output.
- Dati assenti: risposta prudente con coverage gap.
- Dati ambigui: richiesta di restringimento.
- Web: mai usato per dati cliente/studio.
- Audit: evento `lex.operational.query` o `lex.operational.blocked` generato.
- Documenti: chunk/testo solo se indicizzato e citabile.
