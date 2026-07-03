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

## Aggiornamento PEC incrementale e database audit - 03/07/2026

Verifica server: i due database `pec_audit.sqlite` trovati su Hetzner non sono una doppia copia dello stesso archivio, ma due archivi tenant-aware separati:

- `studio-legale-giuseppe-montagnese/email/pec_audit.sqlite`;
- `5adafa47-dadb-4d87-87fc-8dec71f8e3e5/email/pec_audit.sqlite` per il tenant con slug `antonella-mammola`.

Decisione tecnica: non vanno fusi in un database unico globale, perche' il presidio PEC contiene messaggi, allegati, audit, collegamenti fascicolo e stati di lavorazione dello studio. Unificare i due archivi romperebbe isolamento tenant, privacy e deduplica per studio. Il comportamento corretto e' un database audit PEC per tenant/studio attivo.

Regola prestazionale confermata:

- l'acquisizione PEC usa `pec_local_acquire_runs` come cursore incrementale e `pec_local_acquire_items` come ledger dei messaggi gia' presidiati;
- una PEC acquisita o classificata come gia' presidiata viene registrata con `status` tecnico (`ingested`, `duplicate`, `missing_mime` o stato equivalente) e non viene riletta a ogni ciclo;
- il giro successivo parte dai nuovi arrivi dopo il cursore, mantenendo un piccolo boundary solo per sicurezza contro ordinamenti instabili;
- il worker continua a lavorare i job pendenti gia' accodati senza riscaricare tutte le PEC.

Correzione 03/07/2026:

- i lock temporanei SQLite dell'indice documentale Lex AI (`database is locked`, `database table is locked`, `SQLITE_BUSY`) non vengono piu' trattati come errore duro del job PEC;
- il documento viene contato in `retry_locked_documents` e `transient_errors`, non viene marcato come `pec.document_presidio.checked` e viene ripreso automaticamente al giro successivo;
- il repository Documenti AI SQLite usa `timeout=30` e `PRAGMA busy_timeout=30000` per ridurre falsi lock;
- il registro scheduler aggiorna la riga `running` quando arriva l'esito dello stesso `job_id`/`scheduled_at`, evitando righe "in corso" residue che falsano il controllo operativo;
- il log del job PEC mostra anche documenti rinviati e errori documentali reali.

Guardrail mirati aggiunti:

- `test_presidio_documentale_lock_sqlite_rinvia_senza_marcare_letto`;
- `test_scheduler_registry_chiude_evento_scheduler_senza_running_residui`;
- test PEC cursor gia' presenti su `scan_mode=incremental`, `skipped_presided` e nuove PEC dopo cursore.

## Aggiornamento RG 1754/2026 e fascicoli analoghi - 03/07/2026 10:04

Problema reale riscontrato su produzione: il fascicolo `RG 1754/2026` aveva nel documento `Decreto fissazione udienza (originale notificato).pdf` una udienza da remoto con link Teams, ma il presidio non mostrava il dato nel fascicolo. Causa tecnica: la data dell'udienza era gia' passata rispetto al giorno corrente e il job scartava tutto il candidato prima di salvare l'attivita' documentale. Questo impediva di vedere nel fascicolo data, ora, fonte e link, pur essendo corretto non creare una nuova scadenza futura.

Regola applicata ora a tutti i fascicoli:

- se il documento contiene una udienza futura e il fascicolo non ha gia' scadenza prefissata, il flusso continua a creare scadenziario, agenda, attivita' fascicolo, notifiche e web push governate;
- se il documento contiene una udienza da remoto gia' passata, il flusso non crea scadenza futura e non alimenta agenda/scadenziario, ma registra comunque una attivita' `UDIENZA` nel fascicolo con documento sorgente, data, ora, contesto e `Link udienza audiovisiva`;
- il bridge React del fascicolo non tronca piu' la descrizione prima del link e la UI rende gli URL cliccabili con hover/focus visibili;
- il lotto incrementale privilegia i documenti che nel nome o nei metadati contengono termini come `udienza`, `fissazione`, `decreto`, `ordinanza`, `verbale`, `rinvio`, `collegamento`, `audiovisivo`, cosi' i fascicoli analoghi vengono presidiati prima senza aumentare il carico del job;
- il lotto incrementale privilegia ora anche i fascicoli che non hanno una scadenza futura visibile e contengono documenti con termini come `udienza`, `fissazione`, `decreto`, `ordinanza`, `verbale`, `rinvio`, `collegamento`, `audiovisivo`; il budget resta piccolo, ma non viene consumato prima da allegati generici di fascicoli meno urgenti;
- gli audit `pec.document_presidio.checked` creati prima di questa correzione, privi di campo `status`, con `candidates=0` e nome documento riconducibile a udienza/decreto, non sono piu' considerati lettura definitiva: vengono ripresi una volta, rivalutati con la nuova regola e poi marcati con `status=checked`;
- i documenti non indicizzabili per limite dimensione o formato non supportato vengono marcati in audit come `skipped_non_blocking`, non fanno fallire il job vivo e non vengono riletti a ogni ciclo;
- i lock SQLite restano transitori: non vengono marcati come letti e vengono ripresi al giro successivo.

Nuovi campi report:

- `past_remote_hearings_recorded`;
- `skipped_non_blocking_documents`.

Guardrail aggiunti o rilanciati:

- `test_presidio_documentale_registra_udienza_remota_passata_senza_scadenza_futura`;
- `test_presidio_documentale_file_non_indicizzabile_non_fallisce_job_e_viene_marcato`;
- `test_react_fascicoli_attivita_udienza_remota_preserva_link_cliccabile`;
- rilancio mirato di `test_presidio_documentale_lex_recupera_udienza_termine_e_metadati_rag` e `test_presidio_documentale_lock_sqlite_rinvia_senza_marcare_letto`.
