# Fase 0 — Baseline governata e contratto anti-regressione

**Stato:** verifiche locali complete — commit, push e rilascio remoto in corso
**Data:** 23/08/2026 — Europe/Rome
**Baseline di codice:** `68ab5ea3a483d46d0d70ab2a386a6ebf9afd959b` (`feat: aggiunge presidi telematici e scadenze`)
**Release candidata:** `2.278.66`

## Obiettivo della fase

Congelare una baseline riproducibile prima delle fasi di prodotto e correggere solo difetti già osservabili che renderebbero inattendibile l'audit: validità dell'orario esposto e reattività dei probe primari. Nessuna nuova area di prodotto, record di studio o azione legale è stata creata o modificata.

## Inventario verificato

| Area | Evidenza | Stato |
| --- | --- | --- |
| Copia locale reale | `iusentra-app` è l'unico container applicativo; `http://127.0.0.1:8080/api/pronto` risponde `ok`, fuso `Europe/Rome` e release `2.278.66`. | PASS |
| Route prodotto | `tools/react-migration/route-manifest.json`: 118 route, 101 `react_operational_full`, 17 `legacy_operational`; rischio: 18 critico, 58 alto, 42 medio. | Registrato |
| Worktree di partenza | Nessun diff tracciato prima dell'intervento della fase sul commit di baseline indicato. | PASS |
| Fonte dei dati | La baseline usa SQLite/PostgreSQL come fonte operativa con JSON solo come mirror/bootstrapping governato; non viene introdotto alcun nuovo fallback JSON. | PASS per il perimetro toccato |
| Browser reale | Panoramica caricata su `127.0.0.1:8080`; click materiale sul collegamento “Vai a Scadenze e Termini” ha aperto `/scadenziario` con dati del tenant. | PASS iniziale |
| Repository piano giornaliero | Il repository derivato `intelligence/daily_plan.db` del tenant `studio-montagnese` è stato recuperato senza perdita delle righe estraibili, con backup immutabile e successivo ciclo schedulato senza errori. | PASS |

## Difetti emersi e correzione minima

### Orari di udienza non validi

La verifica materiale dello Scadenziario ha evidenziato il valore non valido `29:10` accanto a una trattazione. Il bridge React ripubblicava qualunque stringa di origine senza verificarne l'intervallo orario.

Correzione implementata:

* il bridge ammette solo valori `00:00`–`23:59`, normalizzati in `HH:MM`;
* il dato originale non viene riscritto né perso dal repository; l'API non lo ripubblica come orario attendibile;
* la UI mostra `Orario da verificare` e nel dettaglio spiega l'azione richiesta, senza inventare un orario;
* il contratto API espone `hearingTimeVerificationRequired`.

Guardrail: `test_react_scadenziario_bridge_non_pubblica_orari_udienza_non_validi`.

### Probe e telemetria al primo avvio

Il benchmark ha individuato che il test misurava il dettaglio diagnostico `/api/health` come health primario e che `/api/metriche/runtime` poteva inizializzare la fonte SQL solo per leggere il contatore audit. Questo gonfiava artificialmente i tempi di avvio e ritardava la prima superficie di telemetria.

Correzione implementata:

* il benchmark misura `/api/pronto`, cioè il readiness endpoint utilizzato dal deploy locale e pubblico;
* la telemetria non avvia un bootstrap SQL solo per un conteggio diagnostico; fino a SQL disponibile espone `audit_events_status=deferred_until_sql_ready`, poi legge il conteggio corrente SQL.
* PostgreSQL resta fonte SQL immediatamente interrogabile per la telemetria: l'assenza del file SQLite locale non ritarda né azzera le statistiche dell'ambiente cloud.

Guardrail: `test_runtime_metrics_non_avvia_bootstrap_sql_solo_per_telemetria` e `test_runtime_metrics_legge_statistiche_su_postgresql_senza_attendere_file_sqlite`.

### Recupero governato del repository del piano giornaliero

Durante il riavvio locale è emerso un errore reale del job `daily_plan_incremental_refresh`: `database disk image is malformed`. L'audit ha isolato il problema a `data/tenants/tenant-8bf98719c459/intelligence/daily_plan.db`; `studio.db`, PEC, fascicoli, notifiche, ricerca e preventivi hanno superato `PRAGMA quick_check`.

Il piano giornaliero è una proiezione materializzata, ma il recupero non ha scartato lo stato esistente: dopo aver fermato esclusivamente `iusentra-app` e `iusentra-scheduler`, è stata conservata una copia con hash SHA-256 nel percorso tenant-aware `backup/daily_plan_recovery/phase0_20260823_153000/`. SQLite `.recover` ha rigenerato tutte le sette tabelle e tutti gli indici previsti; la copia validata ha conservato 825 segnali, 900 attività, 16 snapshot, 5 watermark, 7 job e 330 elementi dirty. Lo scambio è stato atomico; la copia corrotta e il dump SQL restano disponibili nel backup, senza cancellare fonti core né documenti.

Il database attivo ha poi superato `PRAGMA quick_check=ok`. Il recovery automatico e il ciclo che aveva segnalato il difetto hanno entrambi terminato correttamente: alle 15:23 Europe/Rome il job incrementale ha elaborato 1 studio con 0 errori. Il journal locale resta in modalità `DELETE`, coerente con il bind mount Docker/Windows già governato nel progetto.

## Baseline delle prestazioni

`python tools/performance_smoke.py --strict --repeat 3` ha superato le soglie nel run finale con mediana:

| Metrica | Mediana |
| --- | ---: |
| Avvio a freddo | 2.110,19 ms |
| Login | 10,27 ms |
| Readiness `/api/pronto` | 0,84 ms |
| Metriche runtime | 80,04 ms |
| Costruzione contesto Lex | 0,01 ms |
| Retrieval Lex | 0,01 ms |

Questi valori sono il riferimento di non-regressione per le fasi che modificano bootstrap, storage, shell, rendering o osservabilità. Il dettaglio `/api/health` resta diagnostico e non è usato come check primario di disponibilità.

## Matrice anti-regressione della Fase 0

| Controllo | Evidenza | Stato |
| --- | --- | --- |
| Versione coerente | `pct`, setup, Docker label, Railway, OpenAPI e package frontend su `2.278.66`. | PASS |
| Contratto API orari | Test mirato dell'orario non valido passato. | PASS |
| Telemetria cold start | Test mirato passato, benchmark a tre campioni passato. | PASS |
| Integrità e budget | `test_ci_no_regression_contract.py`, `test_packaging_consistency.py`, `test_utf8_integrity.py`, `test_performance_budget.py`: 25 passati. | PASS |
| TypeScript | `pnpm --dir frontend typecheck` passato. | PASS |
| Build e Docker locale | `pnpm --filter @iusentra/studio build:vite`; Docker `--no-cache`; `iusentra-app`, scheduler e OCR healthy; `/api/pronto` sulla release `2.278.66`. | PASS |
| Browser reale post-release | Su `127.0.0.1:8080/scadenziario`: nessun `29:10`, avviso `Orario da verificare` visibile; scroll completo e controllo desktop, tablet 1024×768 e mobile 390×844. Il link `Cabina` ha mantenuto hover leggibile e ha aperto la route con click materiale. Dopo il recovery, click materiale su `Visualizza fonte` e `Apri originale` ha caricato l'originale nel lettore interno IUSENTRA. | PASS |
| Scheduler e integrità dati locale | `daily_plan_startup_recovery` e `daily_plan_incremental_refresh` reali hanno concluso senza errori; `daily_plan.db` attivo ha `quick_check=ok`. | PASS |
| Codex quality gate supporto | I profili `ui-support` e `code` rifiutano per policy i file prodotto e i bump SemVer obbligatori; non sono gate applicativi della release. L'esito è documentato e non sostituisce i guardrail di prodotto elencati sopra. | N/A |
| Commit, push, Hetzner | In esecuzione dopo l'accettazione locale; da registrare nel report di rilascio. | IN CORSO |

## Evidenza visiva materiale

Nel browser reale visibile, autenticato sulla copia Docker dell'utente:

* la Panoramica ha aperto lo Scadenziario tramite click materiale;
* lo Scadenziario ha mostrato il badge giallo `Orario da verificare` senza esporre l'orario impossibile della fonte;
* la pagina è stata scorsa dall'alto fino al fondo su desktop e mobile; sui breakpoint 1024×768 e 390×844 l'avviso è rimasto nel layout e non è emerso overflow orizzontale;
* il passaggio del mouse su `Cabina` ha conservato contrasto e cursore di azione; il successivo click materiale ha aperto `/workspace-intelligente`;
* dopo il recovery del repository giornaliero, il passaggio del mouse su `Visualizza fonte` ha mantenuto contrasto e cursore, il click materiale ha aperto il modal interno e `Apri originale` ha caricato il documento nel lettore senza uscire da IUSENTRA.

## Regola di prosecuzione

La Fase 1 non si apre finché non saranno PASS il commit/push gemello e il deploy Hetzner sullo stesso commit. Gli altri gap funzionali del programma restano tracciati nelle rispettive fasi, senza essere dichiarati risolti da questa baseline.
