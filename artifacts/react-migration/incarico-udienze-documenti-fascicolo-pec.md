# Incarico: udienze e collegamenti da documenti fascicolo

Ultimo aggiornamento: 03/07/2026.

Questo file va riletto dopo ogni compattazione insieme ad `AGENTS.md`, `artifacts/data-flow/incarico-operativo-permanente.md` e, quando il lavoro tocca PEC/PST/agenda, `artifacts/react-migration/polisweb-studio-telematico-end-to-end.md`.

## Obiettivo

IUSENTRA deve controllare automaticamente i documenti presenti nel fascicolo e individuare eventuali udienze, trattazioni scritte, collegamenti audiovisivi e link di collegamento. Quando il fascicolo non ha gia' una scadenza prefissata o una scadenza importata dal presidio PEC/PST, il dato deve alimentare in modo deduplicato:

- fascicolo e dettaglio documenti;
- agenda;
- scadenziario;
- notifiche operative;
- notifiche web push, solo dopo persistenza reale e se il browser/studio e' abilitato.

Il controllo e' un doppio presidio rispetto alla PEC: non deve sovrascrivere o duplicare scadenze gia' fissate da PEC, PolisWeb/PST o inserimento manuale. Deve intervenire solo dove manca una prossima scadenza reale.

## Regole funzionali

- Leggere documenti fascicolo e testi OCR/AI gia' disponibili, senza ricorrere a scansioni pesanti dell'intero archivio a ogni ciclo.
- Estrarre data, ora, tipo evento, luogo/modalita', link remoto e documento sorgente.
- Riconoscere link Teams, Zoom, Meet, Webex e URL generici citati come collegamento di udienza o audiovisivo.
- Validare il link come URL apribile e salvarlo come dato strutturato; non basta lasciarlo nelle note testuali.
- Sincronizzare solo fascicoli senza scadenza prefissata o senza evento gia' equivalente in agenda/scadenziario.
- Usare chiavi di deduplica stabili: tenant, fascicolo, documento, data/ora, link normalizzato, provider.
- Conservare la fonte: documento, pagina/estratto quando disponibile, data analisi, motivo di creazione o salto.
- Non creare dati finti se l'estrazione e' incerta: in quel caso generare un esito da presidiare, non una scadenza operativa.
- Il provider del nuovo controllo deve essere distinto ma collegato al presidio PEC, ad esempio `fascicolo_documenti_audit`, mantenendo compatibilita' con `pec_audit`.

## Prestazioni

- Il job deve essere incrementale: processare solo nuovi documenti o documenti modificati dall'ultimo hash/analisi.
- I lotti devono essere piccoli e tracciati, con motivo esplicito se un documento viene saltato.
- Nessun job deve rileggere tutto l'archivio a ogni esecuzione.
- Un errore su un fascicolo o documento non deve bloccare gli altri, ma deve essere visibile nel report operativo.

## Prove richieste

- Test unitari per estrazione data/ora/link.
- Test integrazione su agenda e scadenziario con fascicolo senza scadenza.
- Test che impedisce duplicazione quando la scadenza e' gia' presente.
- Test che il link remoto viene salvato e rimane cliccabile.
- Test del job incrementale: secondo giro senza modifiche deve saltare i documenti gia' presidiati.
- Prova visiva su server reale `https://app.iusentra.it`: fascicolo, documento sorgente, agenda/scadenziario/notifiche collegate, link visibile e funzionante.
- Prova locale reale su `http://127.0.0.1:8080` dopo deploy locale.

## Stato

- Implementato a livello codice il 03/07/2026:
  - il presidio documentale usa il provider `fascicolo_documenti_audit`;
  - il job PEC scheduler e' attivo di default con lotto piccolo `IUSENTRA_PEC_DOCUMENT_PRESIDIO_LIMIT=10`;
  - il limite del job si applica ai documenti nuovi o modificati, non al numero di fascicoli, cosi' i fascicoli gia' presidiati vengono saltati e il giro arriva ai nuovi arrivi;
  - prima di indicizzare Lex AI il servizio controlla `data_prossima_udienza`, `data_prima_udienza`, attivita' future del fascicolo e scadenziario aperto: se esiste una scadenza futura, non crea duplicati e registra `skipped_prefixed_deadline`;
  - Agenda e Scadenziario riconoscono sia il vecchio provider `documento_fascicolo_lex` sia il nuovo `fascicolo_documenti_audit`;
  - il report operativo espone `provider`, `document_budget`, `processed_new_documents`, `pending_new_or_changed_documents`, `skipped_prefixed_deadline`, `notification_jobs`.

- Test automatici mirati gia' eseguiti:
  - `python -m pytest tests/test_pec_audit_pipeline.py::test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag tests/test_pec_audit_pipeline.py::test_presidio_documentale_salta_fascicolo_gia_presidiato_e_processa_successivo -q`;
  - `python -m pytest tests/test_scheduler.py::test_pec_audit_pipeline_job_restituisce_report_operativo tests/test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests/test_pec_auto_acquire.py::test_notifica_scadenze_automatiche_agli_utenti_dello_studio tests/test_react_scadenziario_additions.py::test_react_scadenziario_bridge_non_sintetizza_presidio_documentale_lex_come_pec_generica -q`.

- Verifica locale reale eseguita il 03/07/2026:
  - rebuild Docker locale `app` e `scheduler-worker`;
  - `http://127.0.0.1:8080/api/pronto` risponde `ok=true`, timezone `Europe/Rome`, versione `2.253.152`;
  - container `iusentra-app` e `iusentra-scheduler` healthy;
  - job reale `pec_audit_pipeline_workers` eseguito automaticamente alle `08:35`: log `worker limit=20, documenti Lex limit=10`, esito `0 job completati, 0 errori, documenti=39/2, notifiche=0/0`;
  - DB audit locale `pec_audit.sqlite` aggiornato con eventi `pec.document_presidio.checked` e `scan_mode=incremental_new_or_changed_only`;
  - prova visiva autenticata su `http://127.0.0.1:8080/scadenziario?vista=pec`: pagina `Scadenziario Legale` caricata, contatori coerenti, nessuna nuova scadenza per il giro locale perche' i documenti analizzati non contenevano candidati operativi futuri.

- Da completare prima della chiusura: commit/push branch gemelli, deploy Hetzner, verifica job vivo su server, prova visiva su `https://app.iusentra.it`, controlli container/API e igiene repository.
