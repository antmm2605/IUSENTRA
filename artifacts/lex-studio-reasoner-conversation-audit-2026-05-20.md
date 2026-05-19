# Lex Studio Reasoner - Audit conversazionale 2026-05-20

Versione: 2.245.63.

## Obiettivo

Rendere Lex una conversazione professionale tra colleghi: l'avvocato può fare una domanda ampia, ricevere fonti interne e poi proseguire con follow-up brevi senza dover ripetere ogni volta PEC, fascicolo, documento o cliente. La memoria non è addestramento grezzo: usa solo riferimenti interni già mostrati nella risposta precedente.

## Matrice positiva

Domande coperte dal gate:

- `ultima PEC ricevuta`
- `ultima PEC ricevuta` con contesto fascicolo
- `spiegami la PEC selezionata e gli allegati`
- `ultima email ordinaria ricevuta`
- `quali soggetti sono collegati a questa pratica`
- `chi è la controparte del fascicolo Rossi`
- `dammi la scheda cliente Rossi`
- `quali fascicoli ha il cliente Rossi`
- `costruisci la timeline del fascicolo Rossi`
- `analizza i documenti del fascicolo Rossi e dimmi i punti importanti`
- `quali scadenze urgenti ho questa settimana`
- `cosa ho in agenda questa settimana`
- `fammi il riepilogo del fascicolo Rossi`
- `verifica pagamenti e fatture del cliente Rossi`
- `usa tutto il contesto studio e dimmi le priorità`
- `scrivi risposta alla PEC di Rossi`

## Matrice negativa

- Fascicolo inesistente: Lex non ricade su PEC/email globali e dichiara assenza di fonte collegata.
- Utente senza `messaggi.leggi`: Lex non mostra fonti PEC/email.
- Cliente ambiguo: Lex non sceglie a caso e chiede chiarimento o mostra opzioni.

## Conversazione tra colleghi

Sequenza provata:

1. `ultima PEC ricevuta`
2. `e gli allegati?`
3. `preparami una risposta`
4. `fammi il riepilogo del fascicolo Rossi`
5. `chi è la controparte?`
6. `e le scadenze?`
7. `Dammi la scheda cliente Rossi`
8. `quali fascicoli ha?`

Ogni turno deve restare su fonti studio, produrre risposta utile e mantenere i link operativi apribili. La bozza nasce solo al turno 3, perché l'avvocato l'ha chiesta.

## Soglia 90%

È stato aggiunto un audit end-to-end su 30 turni consecutivi con soglia minima 90%. Il primo rilancio ha prodotto 73%, intercettando regressioni reali su:

- follow-up documenti;
- priorità studio filtrate da query sporca;
- agenda globale catturata dal cliente precedente;
- preventivo/conferimento/template assorbiti dalla conversazione precedente;
- PEC del fascicolo assorbita dal riferimento cliente;
- risposta sulle fonti interne troppo negativa.

Correzioni applicate:

- riconosciute nuove domande operative esplicite anche dentro una conversazione;
- aggiunte stopword operative per preventivi/template/priorità;
- reso il riepilogo fonti interne utile anche senza risultati da fonti legali;
- migliorata la dicitura documenti fascicolo.

Risultato finale: audit `test_lex_studio_reasoner_colleague_conversation_score_reaches_90_percent` verde.

## Pratica web professionale

Lex può navigare risultati pubblici su siti di studi legali e contenuti rivolti ad avvocati con `source_mode=pratica_professionale`. Il risultato è marcato `knowhow_professionale`, serve per prassi, lessico, struttura e spunti operativi, ma non è fonte vincolante.

Regole:

- nessun addestramento grezzo;
- nessuna pubblicazione automatica nel corpus o negli aggiornamenti legali;
- nessuna promozione a fonte ufficiale;
- nessuna contraddizione dell'avvocato sulla base di questi risultati;
- per correggere l'avvocato serve fonte primaria verificata con confidenza almeno 99%.

## Fase 4 - Web live e audit 99%

Il motore web locale non si ferma più se DuckDuckGo HTML non restituisce risultati live: il fallback prova Google pubblico, Yahoo ed Ecosia. Il parser elimina pagine dei motori di ricerca, URL locali, risultati vuoti e titoli sporchi; conserva invece motore, dominio, URL, titolo ed estratto.

È stato aggiunto un audit web/RAG al 99% su cento somministrazioni verso conversazione con l'avvocato. Ogni turno verifica che:

- la query venga arricchita per siti di studio legale e contenuti per avvocati;
- il contenuto acquisito entri negli item RAG;
- il tipo resti `knowhow_professionale`;
- `verified_reference` resti falso;
- l'evidence pack non venga marcato sufficiente;
- le fonti non entrino tra le trusted source;
- la risposta di confronto contenga fonti, limiti e richiesta di fonte primaria per affermazioni di diritto.

## Fase 5 - Linguaggio giuridico e date italiane

Lex deve rispondere come collega di studio, non come chatbot generico. Le date visibili nelle risposte professionali devono usare giorno, mese scritto in italiano e anno; quando la fonte contiene anche ora e minuti, l'ora viene conservata in forma leggibile.

Esempi attesi:

- `17 maggio 2026`;
- `21 maggio 2026 alle 10:00`;
- `1 gennaio 1980`;
- `10 gennaio 2026`.

L'audit dedicato esegue cento turni conversazionali su PEC, email, allegati, fascicolo, documenti, soggetti, scadenze, agenda, pagamenti, scheda cliente, privacy, timeline, preventivi, conferimenti e template. Ogni turno fallisce se contiene date ISO visibili, formule da chatbot o risposte senza contesto professionale. Soglia richiesta: 99%.

## Correzioni validate

- `active_context.case_id` e `active_context.client_id` sono applicati anche fuori dall'arricchimento HTTP.
- `studio_context_overview` non filtra più via tutte le fonti quando la domanda non contiene una singola entità.
- `draft_communication` usa prima retrieval governato PEC/email, poi compone la bozza.
- Le parole colloquiali non contaminano la query entità.
- Le comunicazioni vengono filtrate per fascicolo/cliente quando lo scope è presente.
- I follow-up scelgono il fascicolo come riferimento operativo quando la domanda parla di parti, scadenze, agenda, timeline o pagamenti, anche se la risposta precedente conteneva link a documenti.

## Gate eseguiti

| Comando | Esito |
| --- | --- |
| `python -m pytest tests\test_lex_operational_knowledge.py::test_lex_studio_reasoner_real_question_audit_matrix tests\test_lex_operational_knowledge.py::test_lex_studio_reasoner_negative_question_audit_matrix tests\test_lex_operational_knowledge.py::test_lex_studio_reasoner_colleague_conversation_audit tests\test_lex_operational_knowledge.py::test_lex_draft_request_to_pec_uses_governed_context_before_drafting -q --tb=short` | OK, 4/4 |
| `python -m pytest tests\test_lex_operational_knowledge.py::test_lex_studio_reasoner_colleague_conversation_score_reaches_90_percent -q --tb=short` | OK, soglia 90% superata |
| `python -m pytest tests\test_lex_operational_knowledge.py tests\test_lex_widget_contract.py tests\test_lex_studio_database_source.py tests\test_lex_ai_quality_framework.py tests\test_lex_professional_upgrade.py lex\tests\test_official_web.py -q --tb=short` | OK, 151/151 |
| `python -m pytest lex\tests\test_official_web.py::test_search_free_public_web_accetta_risultati_pubblici_non_allowlist lex\tests\test_official_web.py::test_search_free_public_web_usa_google_pubblico_oltre_duckduckgo lex\tests\test_official_web.py::test_search_free_public_web_usa_fallback_pubblico_se_duckduckgo_blocca lex\tests\test_official_web.py::test_search_free_public_web_usa_ecosia_se_altri_motori_non_restituiscono_risultati tests\test_lex_professional_upgrade.py::test_gateway_pratica_professionale_naviga_siti_per_avvocati_senza_farne_fonte_vincolante tests\test_lex_professional_upgrade.py::test_gateway_pratica_professionale_scarta_risultati_vuoti tests\test_lex_professional_upgrade.py::test_gateway_pratica_professionale_alimenta_rag_lex_senza_promozione_a_fonte tests\test_lex_professional_upgrade.py::test_audit_pratica_web_rag_conversazione_avvocato_raggiunge_99_percento -q --tb=short` | OK, 8/8 con audit 99% |
| Live check `search_free_public_web(...)` su opposizione decreto ingiuntivo/mediazione/condominio | OK, 5 risultati pubblici live |
| Live check `run_public_legal_research(..., source_mode='pratica_professionale')` | OK, 5 risultati `knowhow_professionale`, 0 ufficiali |
| `python -m pytest tests\test_lex_operational_knowledge.py::test_lex_studio_reasoner_legal_language_and_dates_audit_reaches_99_percent tests\test_lex_ai_quality_framework.py::test_guard_legale_blocca_date_tecniche_visibili_nelle_risposte_professionali tests\test_lex_ai_quality_framework.py::test_guard_legale_accetta_date_in_formato_italiano -q --tb=short` | OK, audit 99% e guardia date verde |
| `python -m compileall lex\operational_knowledge tests\test_lex_operational_knowledge.py` | OK |
| `python -m ruff check lex\operational_knowledge\query_router.py lex\operational_knowledge\service.py lex\operational_knowledge\integration.py lex\operational_knowledge\unified_chat.py lex\operational_knowledge\response_composer.py lex\operational_knowledge\serializers.py lex\guards\legal_answer_quality_guard.py lex\research\public_legal_research_gateway.py tests\test_lex_operational_knowledge.py tests\test_lex_widget_contract.py tests\test_lex_studio_database_source.py tests\test_lex_ai_quality_framework.py tests\test_lex_professional_upgrade.py` | OK |
