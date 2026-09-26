# Mappa dell'applicazione IUSENTRA

Ricognizione del 26/09/2026 (versione 2.409.0). Serve a chi lavora sul codice per sapere dove vive ogni logica, chi scrive che cosa e dove sono stati trovati i problemi. Si aggiorna quando cambia un flusso. I numeri di riga sono quelli del 26/09/2026 e servono solo come riferimento iniziale.

Legenda dello stato dei problemi:

- ✅ corretto (con la versione indicata);
- ⏳ aperto, con la correzione prevista.

## 1. Processi e job periodici

Il processo è `python -m pct.scheduler_worker`, che avvia `pct/scheduler.py:start_scheduler`. È un APScheduler con fuso Europe/Rome e le impostazioni predefinite `misfire 300s`, `coalesce`, `max_instances=1`. I modelli dei job e la console Pianificazioni sono in `pct/scheduler_registry.py:default_scheduler_templates`. Gli esiti si registrano in `intelligence/scheduler_registry.sqlite`.

| Job | Cadenza | Legge | Scrive |
|---|---|---|---|
| `mailbox_sync_runtime` | ogni 15 min | IMAP PEC e posta ordinaria | casella JSON e allegati del tenant |
| `pec_audit_pipeline_workers` | ogni 5 min | casella → `email/pec_audit.sqlite` | fasi parse→classify→ocr→signcheck→validate→link, scadenze automatiche, notifiche, piano del giorno |
| `agenda_scadenziario_notifications` | ogni 5 min | agenda, scadenziario | `notifications.db`, Web Push |
| `legal_notification_relata_presidio` | ogni 15 min | documenti dei fascicoli, PEC | notifiche, scadenziario |
| `fascicoli_document_economic_presidio` | ogni 15 min | fascicoli, fatturazione | pagamenti del fascicolo, proforme, stato «definito» |
| `archivio_letture_automatico` | ogni 10 min | registro letture, testi SQL/OCR/nativi, PEC | `letture_fatti`, consegne ai presìdi, catalogo, RAG |
| `catalogo_seconda_lettura_lex` | ogni 2 min | catalogo documentale, Ollama | catalogo, audit, catena probatoria (`AI_OUTPUT_RECORDED`) |
| `scheduler_registry_reload` | ogni minuto | registro, coda `letture_eventi` | thread di lettura, run manuali |
| `collaudo_lettore` | 04:10 | corpus OCR | `intelligence/collaudo_lettore.json` |
| `studio_daily_operational_plan` | 05:30 e incrementale | proiezioni già calcolate | piano del giorno («Oggi») |
| `lex_sentenza_economia_auto` | 03:25 | file del tenant | economia delle sentenze |
| `local_ai_maintenance` | ogni 30 min, solo se attivo | documenti | `local_ai.db` (RAG) |

Gli altri job riguardano calendari, polling dei depositi, PEC di cancelleria, Polisweb, backup, fonti legali e attività notturne.

Gli altri processi:

- `app`: Gunicorn con gevent, 3 worker;
- `ocr-worker`: coda `ocr_jobs.db`, motore unico `legal_ocr/motore`;
- `rq-worker`: profilo di hardening;
- `redis`, `caddy`, `ollama`.

## 2. Letture: registro, motori, presìdi

- **Registro delle letture** (`pct/registro_letture/`): inventario, impronte, `da_leggere`, eventi, fatti, consegne, anomalie. Gli eventi applicativi (`documento_aggiornato`, `documento_rimosso`, `pec_collegata`) sono in `web/services/registro_letture_runtime.py`.
- **Motore documenti** (`pct/archivio_letture/motore_documenti.py:leggi_testo`, v16):
  - date e istituti;
  - domanda, prove di notifica, ruoli;
  - importi e prospetti a tabella;
  - parti dell'epigrafe e controllo economico.

  I fatti passano poi per il collaudo (`collaudo.py`) e la pertinenza.
- **Motore PEC**: `motore_pec.py`.
- **Orchestrazione** (`web/services/archivio_letture_runtime.py:leggi_fascicolo`), chiamata da tre punti:
  - il job dello scheduler;
  - la coda eventi;
  - il worker OCR.
- **Consegna ai presìdi** (`consegna_presidi_runtime.py`): scadenziario, agenda, parti.
- **Viste per i presìdi** (`pct/archivio_letture/presidi.py`):
  - `udienze_e_termini`;
  - `prove_notifica_per_oggetto`;
  - `importi_letti`;
  - `prospetti_letti`;
  - `eventi_letti`;
  - `da_confermare_ora`.
- **Tabelle in due forme** (`legal_ocr/tabelle.py`): blocco `[TABELLA …]` nell'indice documentale e nel motore unico; prospetti riconosciuti nelle righe del testo.
- **Catalogo documentale** (`pct/document_intelligence/catalog_*`): regole, poi seconda lettura di Lex (catalogo chiuso, citazione verificata) con la provenienza sigillata (`pct/provenienza_ai.py`).
- **Regia del fascicolo** (`pct/practice_engine/`, `evaluator.build_regia_payload`): checklist, prontezza al deposito, fase di deposito.

## 3. PEC in ingresso

`pct/pec_pipeline.py` (circa 17.000 righe): `ingest_mime` → `parse_pec_message` → `build_validation_report` (evento, profilo processuale, `build_deadline_proposal`, termine legale) → collegamento al fascicolo → `schedule_deadline` / bozze (`create_draft_date_proposals`).

Regole della 2.409.0:

- un'udienza o un termine letti nel testo entrano da soli in agenda solo se la PEC viene da un ufficio (`pec_profilo_ufficio.fonte_certa`, `fonte_dalla_busta`); dagli altri mittenti restano in bozza;
- l'HTML nascosto non arriva alle regole (`html_visibile`);
- le udienze revocate si scartano (`data_superata`).

Il flusso di deposito, firma e invio PEC è congelato dal 09/09/2026 (`AGENTS.md`).

## 4. Lex AI

- **Ingresso**: `POST /api/assistente/chat` (`lex/routes.py`) → `lex/orchestrator_http.chat_response` → `lex/http_bounded_bridge.build_bounded_http_payload` (con `LEX_GOVERNED_ONLY=1`) → `lex/orchestrator_workflow.run_workflow`: router → contesto → pre-guard → retrieval → provider → post-guard → formatter.
- **Intent**: `_resolve_workflow_hint` / `_resolve_intent` nel bridge, poi `lex/router.py:resolve_workflow`.
- **Fonti** (`lex/retrieval/source_router.py`):
  - sempre: StudioDatabase e GuidaPratica;
  - con un fascicolo: Fascicoli e Documenti;
  - con token legali: Normative, Giurisprudenza, LexMemory, OfficialWeb.
- **Guardie** (`lex/guards/`): hallucination, citation, legal_reference, evidence_relevance, grounding, italian_language, privacy, legal_answer_quality.
- **Modelli**: chat `gemma3:1b` in produzione (`deploy/hetzner/docker-compose.hetzner.yml`); workflow `temperature 0.1`, `num_ctx 4096`; editor AI tramite `lex/gateway` (predefinito `llama3.1:8b`).

## 5. Template e atti

Tre percorsi:

- **A. Chat Lex, workflow `atto_da_template`**: `pct/template_atti_lex_service.run_template_act_workflow` → `compilatore_atti.prefill_payload` / `render_compiled_act`.
- **B. Pagina Template**: `web/blueprints/template_atti.py` con `_studio_config_for_prefill` e `_build_parti_template_context`.
- **C. Editor «Nuovo atto con Lex»**: `pct/editor_ai/service.generate_editor_draft` → `LexGateway`.

## 6. Aree utente

| Area | Route e pagina | API | Bridge e dati |
|---|---|---|---|
| Panoramica | `/` `DashboardPage` | `GET /api/v1/ui/dashboard` | `_collect_dashboard_payload`; cache `react_dashboard_cache` e Redis |
| Controllo studio | `/workspace-intelligente` `RegiaOperativaPage` | `/dashboard`, `/letture/panoramica` | come sopra |
| Oggi | `/oggi` `OggiPage` | `api_v1_daily_plan.py` | `react_daily_plan_bridge` |
| Ricerca studio | `/global-search` | `/global-search`, `/api/global-search*` | `search/index.db` per tenant |
| Fascicoli | `/fascicoli` `FascicoliPage` | `/fascicoli`, `/fascicoli/<id>` e sezioni, `/lettura`, `/letture*`, `/regia`, `/checklist`, `/depositi/*`, `/obblighi-notifica`, `/provenienza-ai` | `react_fascicoli_bridge`, registro letture, practice engine |
| Clienti | `/clienti` | `/clienti*` | `react_clienti_bridge` |
| Soggetti e parti | `/soggetti` | `/soggetti*` | `react_soggetti_bridge`; ReGIndE, IPA, INI-PEC |
| Agenda | `/agenda` | `/agenda` e route legacy in `dashboard_routes.py` | `react_agenda_bridge` (appuntamenti e scadenze) |
| Comunicazioni | `/email`, `/email-ordinaria`, `/messaggi`, `/notifiche-legali` | `/email*`, `/messaggi`, `/notifiche-legali/*` | `react_email_bridge`, `pec_audit.sqlite` |
| Scadenze | `/scadenziario` | `/scadenziario*` | `react_scadenziario_bridge` |
| Servizi telematici | `/telematico`, `/pst`, `/pat`, `/pdp` | `/telematico*`, `/pat/moduli/*` | `react_telematico_bridge`, `telematico/workflow.db` |
| Studio, Sito, Impostazioni, Amministrazione | pagine omonime | `/studio`, `/sito-studio*`, `/impostazioni*`, `/amministrazione*` | bridge omonimi |

## 7. Problemi trovati il 26/09/2026

Ogni voce ha una correzione prevista; lo stato si aggiorna qui.

### Sicurezza

1. ✅ (2.410.0) `richiedi_login` salta ogni endpoint il cui nome inizia con `api_` o `portale` (`auth_runtime.py`). Fuori da `/api/` restano aperti `portale_config`, `portale_attiva` e `portale_revoca`.
2. ✅ (2.410.0) Il portale legacy usava un unico `PORTALE_DB` per tutti gli studi: le pagine dello studio usano il percorso dello studio e il portale pubblico ricava lo studio dal token del link.
3. ✅ (2.410.0) Un utente disattivato conserva la sessione; il cambio della password non chiude le sessioni aperte.
4. ✅ (2.410.0) Codice 2FA senza limite di tentativi e confrontato senza `compare_digest`.
5. ✅ (2.410.0) SSRF su CalDAV: l'URL del server non viene validato.
6. ✅ (2.410.0; anche `corpo_html` dei messaggi, ora filtrato con `html_sicuro`) Stored XSS nelle pagine legacy (note del soggetto, snippet della ricerca).
7. ✅ (2.410.0) In produzione manca `PCT_SECRET_KEY`: viene dato solo un avviso.
8. ✅ (2.410.0) Operazioni amministrative (verifica, VACUUM, export) autorizzate con `utenti.leggi`; l'export lascia file temporanei.
9. ✅ (2.410.0; anche le rotte legacy dell'agenda e il download dei documenti) Scritture senza controllo di permesso:
   - `POST /clienti/delete`, `/soggetti/delete`, `/email/bulk-action`;
   - fatti e anomalie non verificati come appartenenti al fascicolo;
   - voci di «Oggi» non verificate come appartenenti all'utente.
10. ✅ (2.410.0: ogni scrittura con sessione rifiuta Origin/Referer di altri siti; i webhook PayPal, SumUp e Satispay valgono solo se il gestore conferma la transazione; il ritorno Stripe/PayPal verifica link e importo. Resta `unsafe-inline` nella CSP delle pagine legacy) CSRF verificato solo su una lista; CSP con `unsafe-inline`; webhook di pagamento senza firma.

### Integrità dei dati e sincronizzazione

11. ✅ (2.410.0) Job che restituiscono `None` dopo un'eccezione risultano «completati» in console.
12. ✅ (2.410.0) Errori SQL diventano chiusure: le PEC risultano «non più collegate», le impronte vuote fanno dichiarare un fascicolo «fermo».
13. ✅ (2.410.0) Il collegamento automatico di una PEC non chiama `pec_collegata`: la lettura arriva fino a 24 ore dopo.
14. ✅ (2.410.0: il worker OCR riapre il ciclo e accoda l'evento; lo scheduler consegna entro un minuto) I fatti letti dal worker OCR non vengono consegnati ai presìdi.
15. ✅ (2.410.0) `run_pending_jobs` della pipeline PEC fa SELECT e poi UPDATE senza guardia: un job può partire due volte.
16. ✅ (2.410.0: si salvano solo i fascicoli toccati) Il presidio economico salva l'intera tabella dei fascicoli da una fotografia iniziale e può perdere le modifiche fatte nel frattempo.
17. ✅ (2.410.0: l'udienza spostata sposta la scadenza «udienza»; gli altri termini ricevono una nota da verificare; l'appuntamento eliminato o annullato scollega senza cancellare) Modificare o eliminare un'udienza in agenda non aggiorna la scadenza collegata.
18. ✅ (2.410.0) La Panoramica calcola «oggi» sull'ora del server e non su Europe/Rome (`_parse_datetime`).
19. ✅ (2.410.0: unica misura `crediti_aperti`, parcelle emesse e non pagate di ogni anno, bozze escluse) Tre valori diversi di «da incassare».

### Prestazioni

20. ✅ (2.410.0: audit caricato solo quando si legge o si scrive un evento) Autenticazione: a ogni richiesta viene caricato l'audit (fino a 10.000 eventi) e `tenants.json` è letto più volte.
21. ✅ (2.410.0: scrittura atomica e chiave di cache con nanosecondi e dimensione) `pct/cache.py` decifra e rifà il parsing a ogni lettura; le scritture non sono atomiche.
22. ✅ (2.410.0: il riallineamento telematico si ripete solo se i fascicoli dei portali cambiano; la scansione PDF delle scadenze decifra i documenti. La scansione resta nella richiesta, con limite di tempo) `GET /telematico` riscrive SQLite a ogni apertura; `GET /scadenziario/pdf-scadenze/anteprima` legge i PDF nella richiesta.
23. ✅ (verificato: ogni sezione carica solo i propri dati) Ogni sezione del dettaglio fascicolo ricostruisce l'intero payload.
24. ✅ (2.410.0: invalidazione per studio e tra worker) La cache della Panoramica si invalida per tutti gli studi; la cache della lista fascicoli vale per singolo worker.
25. ✅ (2.410.0) `/oggi` scarica anche la Panoramica.

### Lex AI

26. ✅ (2.410.0) Una bozza riscritta dalla guardia della lingua può scavalcare il blocco di una guardia successiva.
27. ✅ (2.410.0) Il fallback in inglese produce una diffida generica.
28. ✅ (2.410.0) `HallucinationGuard` blocca solo nei workflow strict e non riconosce «articolo», «artt.», «Cass.», «L.», «d.P.R.».
29. ✅ (2.410.0: `PrivacyGuard` documentata per il modello locale; `GroundingGuard` non dà più fiducia «alta» a fonti non classificate; errore della chat = astensione 503) `PrivacyGuard` non fa nulla; `EvidenceRelevanceGuard` e `GroundingGuard` sono troppo permissive.
30. ✅ (2.410.0) Il router confronta sottostringhe: «pat» per patrocinio, «tar» per presentare, «n. 1234» per giurisprudenza.
31. ✅ (2.410.0) Nelle lettere i template deterministici non leggono la controparte del fascicolo.

### Template e atti

32. ✅ (2.410.0) Nel percorso A:
    - le parti sono tutti i soggetti dello studio;
    - il firmatario è il primo utente;
    - la configurazione dello studio è vuota.
33. ✅ (2.410.0: renderer dedicati per decreto ingiuntivo, precetto, procure, memorie 171-ter, comparsa, messa in mora, diffida, nota di iscrizione a ruolo; importi mai copiati dal valore della causa; date mancanti come «[data da indicare]»; nessun campo compilato viene scartato) I renderer omettono campi obbligatori (per esempio nel ricorso per decreto ingiuntivo) e tutti gli importi valgono il valore della causa.
34. ✅ (2.410.0: senza modello la bozza si compila dal modello dell'atto; il gateway usa l'Ollama e il modello del runtime) Editor AI:
    - senza il testo del modello;
    - fallback vuoto anche con dati noti;
    - modello del gateway non allineato al runtime.
35. ✅ (2.410.0: le analisi sono «indicazioni» che non entrano nel testo; le riscritture passano dal modello locale e sono scartate se contengono dati non presenti nel passaggio) Le azioni Lex della pagina Template producono meta-testo che sostituisce la prima frase dell'atto.

### Trovati durante le correzioni (2.410.0)

36. ✅ `GestioneClienti.nuovo` scartava i campi con `default_factory` (sede, recapiti): i contatti arrivati dal sito dello studio e la residenza dei clienti importati andavano persi.
37. ✅ L'indirizzo del cliente perdeva la parentesi di chiusura della provincia («70126 Bari (BA»).
38. ✅ La scansione PDF delle scadenze leggeva i documenti cifrati come testo vuoto.
39. ✅ Il gateway di Lex puntava a `127.0.0.1` e a un modello non installato: in Docker ogni chiamata dell'editor AI falliva.
40. ✅ Lex, senza modello o con fonti estranee, rispondeva elencando impostazioni dello studio o schede del catalogo come «dato certo»: ora calcola termini e contributo con i motori di IUSENTRA e si astiene quando nessuna fonte riguarda la domanda.
41. ✅ La pagina Ricerca studio aveva il pulsante «Ricerche recenti» inerte e mostrava zero risultati quando l'aggiornamento dell'indice falliva.
42. ✅ `web/preventivi.py`, copia non registrata del blueprint pagamenti con i webhook non verificati, è stata rimossa.
43. ✅ `pct/search_index.py`: la funzione di escape era finita tra il decoratore `@dataclass` e la classe (errore di import, trovato dai test prima del rilascio).

## 8. Verifiche eseguite

- Test automatici: suite completa `tests/` e `lex/tests/` (esito nel messaggio di rilascio); nuovi test `tests/test_revisione_2410_{sicurezza,integrita,template,lex}.py`.
- Sonda sugli accessi: ogni rotta sotto `/api/` interrogata senza sessione; resta aperto solo `/api/v1/` (descrizione pubblica dell'API).
- Generazione reale di undici atti da un fascicolo di prova (decreto ingiuntivo, citazione, comparsa, precetto, diffida, messe in mora, procure, memoria 171-ter, nota di iscrizione a ruolo) e rendering di tutti i 192 modelli del catalogo senza errori.
- Domande reali a Lex (termini di appello, 171-ter, opposizione a decreto ingiuntivo, contributo unificato, articolo di codice, giurisprudenza).
- Non eseguita in questa sessione la verifica nel browser sulla macchina dello studio (AGENTS.md): va fatta dopo il deploy.
