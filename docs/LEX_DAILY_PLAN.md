# Lex Oggi — Piano del giorno (Daily Plan)

Aggiornato: 02/08/2026 — versione applicativa: vedere `pct/__init__.py`.

## Obiettivo

Rispondere, per ogni avvocato dello studio e per la data scelta, alla domanda:
**"quali attività devo svolgere in quel giorno, in quest'ordine, con quale
motivo, fonte, fascicolo, scadenza e azione disponibile"**. Non è una chat che interroga i
database: è una pipeline deterministica che aggrega segnali operativi già
governati e li materializza in un piano leggibile. Lex spiega e sintetizza;
non decide priorità, termini o associazioni.

## Architettura

```
Collettori (PEC audit, presidio fascicoli, agenda, scadenziario, economico)
   → OperationalSignal (normalizzazione + redazione PII)
   → correlazione (link forti scadenziario_id/agenda_id; link deboli → revisione)
   → deduplicazione (sha256 tenant|fascicolo|azione|evento|data — evidenze conservate)
   → priority engine deterministico P0–P3 (regole R1–R9, spiegabili)
   → assegnazione (referente → agenda → responsabile → PEC → dominus → coda studio)
   → pianificazione giornata (blocchi agenda, prep udienze, budget 75%)
   → repository materializzato (SQLite/PostgreSQL tenant-aware)
   → GET = sola lettura snapshot (zero scan, zero OCR, zero LLM)
```

Bounded context: `pct/daily_plan/` (clock, models, collectors/, correlation,
deduplication, priority_engine, assignment, scheduling, repository, service,
serializers). Wiring web: `web/services/daily_plan_runtime.py`,
`web/services/react_daily_plan_bridge.py`, `web/blueprints/api_v1_daily_plan.py`.
UI: `frontend/src/pages/daily-plan/` su route `/oggi`, con scelte rapide
`Oggi`, `Domani`, `Dopodomani` e campo data. Le date future restano nel query
param `date=AAAA-MM-GG`; il refresh genera realmente il giorno selezionato.

## Modello dati (pct/sql/20260711_daily_plan*.sql)

| Tabella | Ruolo | Chiavi |
|---|---|---|
| `operational_signals` | proiezione tenant-wide dei segnali | unique `(tenant_id, dedupe_key)`; idx status+due, fascicolo, source |
| `daily_plan_items` | attività per giorno/utente | unique `(tenant_id, target_date, dedupe_key)`; idx utente+data+priorità+rank |
| `daily_plan_snapshots` | header piano per utente (versione, copertura, sintesi Lex cache) | unique `(tenant_id, target_date, user_id)` |
| `daily_plan_source_watermarks` | cursore/stato per fonte | PK `(tenant_id, source_type)` |
| `daily_plan_jobs` | coda refresh (202 dalla POST) | idempotency unique parziale; job `running` oltre 45 minuti chiuso e liberato automaticamente |
| `dirty_entities` | entità cambiate per il refresh incrementale | PK `(tenant_id, entity_type, entity_id)` |
| `daily_plan_action_log` | azioni utente idempotenti | idempotency unique parziale |

`tenant_id` è in tabella E nel file per-tenant (parità PostgreSQL, pattern
`PecAuditRepository`). Ogni query applicativa filtra per tenant (fail-closed).

## Fonti (solo dati già materializzati)

| Collettore | Legge | Non fa mai |
|---|---|---|
| PEC | `PecAuditRepository` (termini candidati, udienze, pagamenti, messaggi da presidiare, esiti) | inviare PEC, leggere corpo grezzo, eseguire istruzioni contenute nei messaggi |
| Presidio fascicoli | azioni P0–P3 di `build_fascicolo_operational_presidio` da testi già estratti + pagamenti fast | OCR/estrazioni nuove |
| Agenda | impegni del giorno selezionato (blocchi fissi normalizzati in `Europe/Rome` prima del calcolo slot), udienze entro 48h, conflitti | modifiche agenda |
| Scadenziario | scadenze aperte INCLUSE le arretrate, entro 14 giorni | calcolo termini |
| Economico | preventivi senza riscontro, parcelle in bozza, insoluti | fatture definitive |
| Salute fonti | copertura complete/stale/unavailable → avvisi | nascondere i gap |

Un piano vuoto con fonti non aggiornate viene dichiarato incompleto, mai
"nessuna attività".

## Priorità (deterministiche, spiegabili)

R1 perentoria scaduta/in scadenza nel giorno → P0 · R2 rifiuto/errore telematico → P0 ·
R3 udienza nel giorno o bloccante in scadenza → P0 · R4 perentoria ≤3g → P1 ·
R5 scadenza odierna/arretrata → P1 · R6 udienza ≤48h o bloccante ≤7g → P1 ·
R8 hint del presidio (P0/P1) · R7 ≤14g → P2 · R9 organizzativa → P3.
La regola scattata e il motivo in italiano restano sull'attività
(`priority_rule`, `priority_reason`). Rank secondario totale e stabile →
rigenerazione idempotente (stessa `plan_version`).

## Deduplicazione

`sha256(tenant | fascicolo | tipo_azione | evento_canonico | data_Rome)`.
Un termine presente in PEC, documento e scadenziario collassa sull'evento
`scadenziario:<id>` → UNA attività con tutte le evidenze (cap 10). Mai fusi
fascicoli diversi o date diverse. La confidence cresce solo tra fonti
indipendenti; i conflitti (perentorietà, responsabili, orari) marcano
`needs_review` invece di sparire. Le associazioni PEC-fascicolo deboli
(score < 0.75) perdono il fascicolo dalla chiave, confidence ≤ 0.6, revisione.

## Assegnazione

Referente fascicolo → avvocato agenda → responsabile scadenza (id verificato)
→ presa in carico PEC → dominus → coda "Da assegnare" (mai scomparsa).
Le etichette testuali si risolvono in utenti reali senza indovinare: gli
ambigui restano in coda con l'etichetta visibile.

## Scheduler

| Job | Cron | Note |
|---|---|---|
| `studio_daily_operational_plan` | 05:30 Europe/Rome | riconciliazione completa della data corrente, un piano per utente attivo per tenant |
| `daily_plan_incremental_refresh` | minuti 7, 22, 37, 52 | consuma le richieste manuali; dirty entities con esecuzioni programmate attive; dopo le 06:00 recupera automaticamente gli snapshot odierni mancanti |

Entrambi usano `max_instances=1` e `coalesce=True`. La generazione mattutina e
le dirty entities richiedono `lex.dailyPlan.enabled` +
`lex.dailyPlan.scheduledRuns` (default attivo); il consumer incrementale resta
disponibile con il solo flag principale per smaltire le richieste manuali. La
finestra 05:30–05:59 è riservata al cron anche in caso di misfire; da 06:00,
se il servizio automatico si avvia tardi, controlla solo gli snapshot attesi e
avvia una ricostruzione completa esclusivamente quando uno manca. Il recupero
rispetta la disattivazione o l'orario personalizzato nella console
Pianificazioni e condivide un mutex con cron e primo giro incrementale. La
data corrente è sempre prioritaria: una coda di date future non può ritardare
né sostituire il piano delle 05:30. I job rimasti `running` oltre 45 minuti
vengono chiusi come interrotti, liberando una nuova richiesta. Il controllo
non legge OCR, PDF, ZIP o fascicoli durante la GET e non ripete ricostruzioni
per uno snapshot valido, anche vuoto. Nessuna scrittura applicativa.
Hook best-effort: il presidio PEC marca dirty i fascicoli/messaggi toccati.

## API (`/api/v1/ui/daily-plan*`)

| Endpoint | Note |
|---|---|
| `GET /daily-plan?date=&user=` | snapshot con ETag per tenant, utente, data, versione e timestamp → 304; `user` altrui solo admin |
| `GET /daily-plan/coverage` | watermark e stato fonti |
| `GET /daily-plan/items/<id>` | dettaglio lazy: evidenze + spiegazione priorità |
| `GET /daily-plan/backlog?cursor=&limit=` | keyset, `total_matching`/`truncated` sempre presenti |
| `GET /daily-plan/jobs/<id>` | stato tenant-aware e `Cache-Control: no-store` della richiesta: `queued`, `running`, `done`, `failed`; nessun report tecnico o fonte sensibile |
| `POST /daily-plan/refresh` | 202, riceve `date=AAAA-MM-GG`, accoda job con chiave univoca per click e richiede una run immediata del servizio automatico; restituisce `job_id`, `run_id` e stato effettivo del dispatch; se la pianificazione è disattivata chiude subito il job con messaggio comprensibile, senza polling ingannevole; date passate rifiutate; `mode=full` solo admin; `Idempotency-Key` |
| `POST /daily-plan/items/<id>/action` | stato (accept/complete/delegate/snooze/reject, replay idempotente) o proposta approvabile (create_task/create_deadline/create_calendar_proposal/create_pec_draft) |

RBAC: lettura `agenda.leggi` + `scadenziario.leggi`; tenant sempre lato
server; parametri riservati (tenant_id, path, token…) rifiutati; audit su
refresh e azioni. Il GET non esegue MAI collettori, OCR o LLM.

## Supporto operativo all'avvocato

La pagina non è una lista generica: per ogni attività mostra priorità e regola,
termine, tipo di intervento, fascicolo, cliente, assegnatario, fascia proposta,
durata, stato, fonti e attendibilità. Il pannello lazy rende visibili il
perché della priorità, il contesto di pianificazione, lo stato aggiornato e le
fonti verificabili con data/ora italiana e link interno. Agenda e fonti restano
materializzate: il dettaglio aggiuntivo non innesca scansioni o analisi.

## Approvazioni (Fase 12)

Le azioni applicative creano una proposta monopasso nella coda approvazioni
Workflow Agents (`workflow_code=daily_plan_action`): esecuzione solo dopo
approvazione umana con `legal_skills.approva` e flag di scrittura. Whitelist
chiusa: invio PEC, firma, deposito, cancellazioni, fatture definitive e
modifiche a utenti/permessi NON sono raggiungibili. `create_pec_draft` resta
con invio bloccato per costruzione.

## Lex

- Tool read-only `daily_plan` (`lex/tools/daily_plan_tool.py`): item con
  priorità/scadenza/bloccante/perentorio/affidabilità + copertura e metadata
  di troncamento. Permessi `agenda.leggi`+`scadenziario.leggi`.
- `triage_giornaliero` legge il piano come primo passo e propone attività
  specifiche; scadenze/agenda restano come verifica.
- La sintesi (`lex/agents/synthesis.py`) usa i dati reali delle attività,
  non i conteggi. La sintesi in pagina è cache per `plan_version` con
  fallback deterministico: il Piano del giorno funziona completamente senza LLM.

## Feature flag e rollback

| Flag | Default | Effetto |
|---|---|---|
| `lex.dailyPlan.enabled` | ON | API e pagina Piano del giorno |
| `lex.dailyPlan.scheduledRuns` | ON | generazione automatica e recupero scheduler |
| `lex.dailyPlan.writeProposals` | OFF | proposte applicative dalla pagina |
| `routes.appV2.dailyPlan.home` | ON | route `/oggi` nella shell |
| `routes.appV2.dailyPlan.reviewQueue` | ON | riservato alla coda revisione |

**Rollback**: spegnere i flag (env `IUSENTRA_FF_LEX_DAILYPLAN_ENABLED=false`
ecc.). Le tabelle nuove sono proiezioni rigenerabili: nessun dato di dominio
dipende da esse.

**Rollout operativo**: `enabled` e `scheduledRuns` sono ON per default, così
il piano odierno viene preparato senza intervento umano. Il monitoraggio deve
verificare lo snapshot e l'esito schedulato; l'override esplicito del flag
resta disponibile soltanto come rollback governato. `writeProposals` resta OFF
finché lo studio non abilita la coda approvazioni.

## Prestazioni (garanzie strutturali)

- GET = 2 query indicizzate su snapshot; ETag/304 sui refetch; payload
  iniziale minimo (conteggio evidenze, dettaglio lazy); backlog keyset. La
  riapertura SQLite verifica in sola lettura gli oggetti dello schema già
  presenti e non riesegue DDL né modifica il journal durante le GET.
- La cache frontend è separata per utente e data; un nuovo timestamp di
  generazione cambia l'ETag anche quando le attività restano identiche.
- Benchmark riproducibili in `tests/test_daily_plan_perf.py` (misurati in
  questo repo: lettura ~3,5 ms/2 query su 300 attività, dedup 1500 segnali
  ~34 ms, refresh incrementale ~21 ms, zero chiamate LLM verificate con
  monkeypatch che fallisce se il gateway viene invocato).
- Proiezione condivisa: i piani personali derivano dai segnali tenant-wide,
  nessuna rianalisi per avvocato; una nuova PEC rielabora solo le entità
  toccate.

## Limiti noti

- Il presidio fascicoli nel piano usa input rapidi (testi già estratti +
  pagamenti fast, senza depositi/relata completi): il quadro integrale resta
  nel dettaglio fascicolo; gli esiti dei depositi arrivano dalla fonte PEC.
- La presa in carico PEC per utente non è ancora tracciata a livello di
  messaggio: il gancio d'assegnazione esiste ma è inattivo.
- Il reload del registro pianificazioni ricostruisce i trigger cron nel fuso
  di runtime (comportamento comune a tutti i job built-in preesistenti).

## Test

`tests/test_daily_plan_{models,repository,deduplication,priority,assignment,
scheduling,collectors,service,api,security,scheduler,perf}.py` +
`tests/test_lex_daily_plan_tool.py` + `tests/test_lex_tools_copertura.py`
(fix Fase 1). Coprono i 20 casi obbligatori del capitolato (perentoria
scaduta→P0, PEC rifiutata→P0, 3 fonti→1 attività, cross-tenant, PII nei log,
idempotenza, mezzanotte Europe/Rome, troncamenti dichiarati, ecc.).
Comprendono inoltre agenda/scadenze su data futura, trasporto della data nel
job scheduler, stato reale `queued/running/done/failed`, recupero di snapshot
mancanti, migrazione dell'orario 07:30→05:30 solo per configurazioni di sistema
e validazione API delle date passate o non valide. Il presidio di affidabilità
copre anche il rispetto di una pianificazione disabilitata o personalizzata,
la mutua esclusione fra generazione completa e recupero, la precedenza dello
snapshot della data odierna rispetto a una richiesta futura, il rilascio dei
job rimasti impropriamente `running` e la conversione corretta di eventi UTC
alla data italiana `Europe/Rome`, inclusi gli orari dei blocchi Agenda usati
per evitare sovrapposizioni nelle fasce proposte.
