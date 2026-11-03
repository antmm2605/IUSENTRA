# Sequenza notturna e semaforo dei motori

Codice: `pct/scheduler_notturno/` (catena) e `pct/semaforo_motori/` (semaforo). Test:
`tests/test_scheduler_notturno.py`, `tests/test_semaforo_motori.py`.

## Perché (misura del 03/11/2026, server CPX42 16 GB)

- Memoria: 13,0 GB usati su 15,6, swap 5,7 GB su 8. Ollama 8,5 GB (due `llama-server` caricati insieme,
  CPU 795% alle 16:10, di giorno), scheduler-worker 2,5 GB (RSS 2,2 GB + 1,6 GB in swap), app 0,7 GB, OCR 3 MB.
- Chiusure per memoria esaurita (kernel) il 03/11: 13:22 Ollama, 14:47 scheduler-worker, 15:20 Ollama, 16:08 Ollama.
- Causa: le corsie (`pct/scheduler_corsie.py`) già facevano girare un lavoro lungo alla volta *dentro* lo scheduler,
  ma nulla coordinava scheduler, worker OCR e letture in sfondo dell'app; la seconda lettura del catalogo
  (AI locale ogni 2 minuti) e l'indicizzazione RAG delle sentenze tenevano Ollama sempre caricato di giorno; i
  lavori notturni erano a orari fissi sparsi e si alternavano ai lavori frequenti (letture ogni 10 minuti,
  presidio economico ogni 15). Errori collegati: «database is locked» su RAG e registro.

## Semaforo dei motori (giorno e notte)

Un solo motore pesante alla volta su tutto il server: SQLite in `/data/intelligence/semaforo_motori.sqlite`
(condiviso dai container), titolare con affitto di 120 s rinnovato ogni 30 s (se il processo muore il semaforo si
libera da solo), coda ordinata per priorità e arrivo. Lo usano: lavori pesanti dello scheduler (tutti quelli della
sequenza), worker OCR (un documento per turno), letture del fascicolo in sfondo e lettura scadenze PDF dell'app.
Le richieste web non lo usano mai. Priorità: 10 OCR e letture di documenti appena caricati; 11-12 PEC e PEC nel
fascicolo; 53-58 le altre fasi in ordine. Di giorno un lavoro pianificato aspetta al massimo 15 minuti, poi
salta al giro successivo. Console Pianificazioni: `semaforo_motori.testo` («In corso: X; in coda: Y, Z»).
Spegnimento d'emergenza: `PCT_SEMAFORO_MOTORI=0`.

## Sequenza dalle 21:30 (Europe/Rome)

Il lavoro `sequenza_notturna` gira ogni minuto dalle 21:30 alle 07:30 ed esegue **un passo per giro**: il successivo
parte solo quando il precedente è finito. Avanzamento ed esiti in `scheduler_registry.sqlite` (tabelle
`notte_avanzamento`, `notte_passi`) e nella console (`sequenza_notturna`). Un passo che fallisce si scrive e la
catena prosegue; dopo le 07:30 non parte nulla e la notte seguente riprende dal passo rimasto. Prima di ogni passo
si controlla la memoria libera (attesa massima 20 minuti). Fuori dalla catena, di notte, i lavori della sequenza
non partono ai loro vecchi orari; la catena spenta dalla console li restituisce ai loro orari.

| Fase | Lavori | Dipende da | Note |
|---|---|---|---|
| 1 Caselle e presidio PEC | mailbox_sync_runtime, pec_audit_pipeline_workers, poll_pec_cancelleria, polling_esiti_deposito | — | restano anche di giorno (leggeri) |
| 2 PEC nel fascicolo e notifiche L. 53/1994 | pec_fascicolo_documenti_recupero (fino a 40 min), legal_notification_relata_presidio | 1 | |
| 3 OCR dei documenti nuovi | attesa della coda del worker OCR (max 90 min) | 1-2 | AI locale scaricata prima |
| 4 Letture e sentenze | archivio_letture_automatico (fino a 60 min), letture_recupero_completo (sabato sera), lex_sentenza_economia_auto, collaudo_lettore | 3 | |
| 5 Scadenze, notifiche, economia | aggiorna_scadute, aggiorna_parcelle_scadute, agenda_scadenziario_notifications, fascicoli_document_economic_presidio, profili_procedurali_riconvalida, patrocinio_adeguamento_bimestrale | 4 | |
| 6 Indici e Lex (AI locale) | catalogo_seconda_lettura_lex (fino a 45 min), lex_operational_agents_nightly, lex_dataset_nightly, rag_rispezzatura_notturna (fino a 60 min), lex_autonomous_learning_nightly, local_ai_maintenance, workspace_intelligence_snapshot | 4-5 | Ollama caricato solo qui, scaricato a fine fase (keep_alive=0) |
| 7 Fonti ufficiali | legal_official_archives_daily, legal_updates_batch, cassazione_sentenzeweb_nightly, corte_costituzionale_opendata_weekly (venerdì sera), mediazione_sources_refresh, sync_tabelle_normative_daily, sync_uffici, pst_certificati_cifratura_weekly (sabato sera), legal_monitor_daily, legal_sources_daily_check | — | indipendenti dai fascicoli |
| 8 Manutenzione e backup | censimento_spazio_notturno, utf8_integrity_nightly, operational_backup_nightly, backup_giornaliero | tutte | backup solo se abilitato |

Il piano del giorno (`studio_daily_operational_plan`, 05:30) resta al suo orario nella stessa corsia lunga, quindi
non si sovrappone. Durate: la console mostra la media misurata delle ultime 7 notti per fase
(`durata_media_minuti`); prima misura attesa dalla notte del 03-04/11/2026.

Variabili: `PCT_SEQUENZA_NOTTURNA=0` (spegne la catena), `PCT_NOTTE_INIZIO` / `PCT_NOTTE_FINE` (default 21:30 /
07:30).

Base: art. 3 D.M. 44/2011 e art. 20 CAD (integrità delle letture, che non devono essere interrotte da chiusure per
memoria esaurita).

## AI locale: un modello alla volta e riserva (decisione del 03/11/2026)

- `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KEEP_ALIVE=2m`, `LEX_EMBED_KEEP_ALIVE=2m`, seconda lettura del catalogo con
  `PCT_LEX_CATALOGO_KEEP_ALIVE` (default 2m): il modello si scarica poco dopo l'uso.
- Se il modello principale non riesce (errore, tempo scaduto, memoria) si scarica e si avvia il modello di riserva
  (`pct/ai_riserva.py`); l'esito va nella tabella `ai_esiti` del registro e in console (`sequenza_notturna.ai_riserva`).
- Limite di memoria del solo container Ollama: `IUSENTRA_OLLAMA_MEM_LIMIT` (default 7g) e `oom_score_adj: 500`;
  app, scheduler-worker e ocr-worker restano senza limite. Con un modello più grande di 4B alzare il limite nel .env.
- La seconda lettura del catalogo con l'AI gira solo di notte, nella fase 6.
