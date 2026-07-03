# PEC Legal Event Understanding V2

Aggiornato: 03/07/2026.

## Obiettivo

Il presidio PEC non deve limitarsi ad acquisire il messaggio. Dopo MIME, allegati, OCR, XML, ZIP, EML annidati, firme e report di validazione, IUSENTRA deve produrre un evento legale strutturato e auditabile per fascicolo, Agenda, Scadenziario, notifiche, web push e Lex AI.

Il modulo operativo è `pct/pec_legal_event_understanding.py`; la versione schema è `iusentra.pec.legal_event_understanding.v2`; il ruleset corrente è `pct/data/legal_pec_rules_v2026_07.json`.

## Regola primaria

Il software può proporre agenda, scadenze, attività, incassi, alert, classificazioni e memoria Lex. Non può inviare PEC, depositare atti, chiudere un deposito incompleto, calcolare come definitivo un termine ambiguo o attribuire un credito all'avvocato senza distrazione o titolo equivalente.

La sola comunicazione di deposito della sentenza non fa decorrere automaticamente il termine breve di impugnazione. Il motore crea attività di esame sentenza e lascia il calcolo conclusivo al motore deterministico e alla revisione dell'avvocato.

## Pipeline

Flusso governato:

1. PEC acquisita e deduplicata.
2. MIME conservato con hash.
3. Parser estrae corpo, HTML, href, XML, allegati, OCR, ICS ed EML annidati.
4. Classificazione legale V1 e report di validazione.
5. Motore V2 produce JSON strutturato.
6. Worker `validate` materializza il JSON nelle tabelle dedicate.
7. Agenda, Scadenziario, notifiche/web push, fascicolo e Lex usano il dato strutturato, non testo libero non verificato.

Il worker resta incrementale: usa i job pendenti e i marker già presenti, non rilegge l'archivio intero a ogni giro.
Il presidio documenti collegato alla pipeline usa lo stesso budget anche come limite di fascicoli visitati per tick: un lotto `1` può attraversare al massimo un fascicolo e registra un marker di rotazione, così i giri successivi ripartono da casi non ancora toccati invece di rileggere sempre le stesse pratiche.

## Schema prodotto

Il JSON V2 contiene:

- `input_quality`: fonti lette, OCR e warning;
- `message`: metadati PEC tenant-safe;
- `procedimento`: RG, ufficio, registro, parti e giudice se rilevati;
- `classification`: famiglia, eventi e revisione umana;
- `deadlines`: termini proposti con norma, dies a quo, durata, priorità e prova;
- `hearings`: data, ora, modalità, link, piattaforma, aula, passcode e azione agenda;
- `payments`: spese, distrazione, gratuito patrocinio, contributo unificato e beneficiario;
- `pct_receipts`: stato catena deposito PCT;
- `actions`: agenda, scadenziario, incasso, task, notifica web push e Lex;
- `lex_memory`: fatti e limiti di inferenza per il DB vettoriale;
- `audit`: versione ruleset, conteggio evidenze e criticità residue.

Per compatibilità API restano esposti anche `hearing`, `deadline` e `pct_receipt`.

## Persistenza

SQLite e PostgreSQL hanno parità strutturale nelle migrazioni:

- `pec_legal_events`;
- `pec_legal_deadlines`;
- `pec_legal_hearings`;
- `pec_legal_payments`.

La riga principale conserva `event_json` ed `event_sha256`; le tabelle figlie indicizzano solo i dati operativi necessari a controlli, filtri e job. La persistenza è idempotente per tenant, messaggio e versione parser: ogni nuova validazione rigenera il presidio derivato dal report corrente.

## Matrice eventi presidiati

Eventi riconosciuti in V2:

- comunicazioni di cancelleria;
- deposito/pubblicazione sentenza;
- sentenze con spese liquidate, distratte o compensate;
- gratuito patrocinio e liquidazioni spese di giustizia;
- udienze in presenza, da remoto, miste e note scritte;
- 127-bis, 127-ter, 171-bis, 171-ter;
- CTU, decreto ingiuntivo, cautelari, competenza, estinzione, Cassazione;
- ricevute PCT, mancata consegna, rifiuto deposito, notifica eccezione;
- contributo unificato e spese documentate;
- eventi ambigui da revisione.

La modalità udienza viene estratta da testo, HTML `href`, allegati, ICS ed evidenze già prodotte dal report. Se l'udienza è da remoto o mista ma il link manca, la priorità diventa `P0`.

## Regole economiche

- `condanna alle spese` senza distrazione: beneficiario parte, non avvocato.
- `distrae`, `antistatario`, `in favore dell'avv.`: credito diretto dell'avvocato.
- `compensa le spese`: nessun incasso automatico.
- gratuito patrocinio/DPR 115/2002/SIAMM/LSG: workflow spese di giustizia con revisione umana.
- contributo unificato viene distinto dagli esborsi: un importo indicato come `€ 21,50 per esborsi` non viene trattato come contributo unificato.

## Regole udienze

- Presenza: aula, piano, indirizzo e giudice se disponibili.
- Remoto: link, piattaforma, meeting ID e passcode; Microsoft Teams è riconosciuto e verificato come dominio attendibile.
- Mista: mantiene sia aula sia link.
- Note scritte 127-ter: crea presidio per opposizione e deposito note.
- 127-bis: crea presidio per richiesta di udienza in presenza entro 5 giorni dalla comunicazione.

## Fail closed

Il presidio impone revisione umana quando:

- OCR o fonti testuali sono insufficienti;
- l'evento è ambiguo;
- il termine è decadenziale o normativamente sensibile;
- manca il link di udienza remota;
- la catena PCT non è completa;
- esistono errori PCT/PEC bloccanti;
- il canale è penale, PAT, PTT o SIGIT senza ruleset dedicato.

Le web push non espongono dati sensibili: usano solo titoli sintetici, per esempio `P0 - Udienza da remoto senza link trovato`.

## Test obbligatori

Copertura minima in `tests/test_pec_legal_event_understanding.py`:

- sentenza senza distrazione;
- sentenza con distrazione;
- spese compensate;
- gratuito patrocinio;
- contributo unificato distinto da esborsi;
- udienza Teams da `href`;
- udienza remota senza link;
- udienza in presenza;
- udienza mista;
- note scritte 127-ter;
- presidio 127-bis;
- catena PCT incompleta;
- canale PDP penale senza regole civili automatiche;
- persistenza reale da worker `validate` nelle quattro tabelle V2.

Test collegati:

- `tests/test_pec_hearing_understanding.py`;
- `tests/test_pec_legal_workflow.py`;
- `tests/test_pec_legal_deadline_cablaggio.py`;
- `tests/test_pec_audit_pipeline.py`;
- `tests/test_pec_auto_acquire.py`;
- `tests/test_scheduler.py`.

## Fonti normative/tecniche

Fonti primarie usate per impostare le regole:

- art. 133 c.p.c. e coordinamento con art. 325 c.p.c.;
- artt. 91 e 93 c.p.c.;
- artt. 127-bis, 127-ter, 171-bis, 171-ter c.p.c.;
- provvedimento DGSIA 7 dicembre 2023 sulle udienze civili da remoto e Microsoft Teams;
- DPR 115/2002 per gratuito patrocinio e spese di giustizia;
- specifiche PCT/PST già presidiate dalla pipeline PEC audit-grade.

## Stato 03/07/2026

Implementato:

- motore V2 deterministico;
- ruleset JSON versionato;
- persistenza SQLite/PostgreSQL;
- integrazione nel worker `validate` e nel refresh report;
- test mirati su matrice eventi, udienze, termini, pipeline e scheduler.
- guardrail prestazionale sul presidio documenti: budget applicato anche ai fascicoli visitati e marker di rotazione `pec.document_presidio.checked`.

Da rieseguire a ogni modifica futura:

```powershell
python -m pytest tests\test_pec_legal_event_understanding.py tests\test_pec_hearing_understanding.py tests\test_pec_legal_workflow.py tests\test_pec_legal_deadline_cablaggio.py -q
python -m pytest tests\test_pec_audit_pipeline.py -k "pec_pipeline_ingests_synthetic_dataset_with_audit_grade_storage or pec_audit_header_summaries_support_lightweight_mode or lex_operational_tools_expose_pec_audit_control_context" -q
python -m pytest tests\test_pec_auto_acquire.py::test_worker_pec_rispetta_budget_documentale_scheduler tests\test_scheduler.py::test_pec_audit_pipeline_job_restituisce_report_operativo -q
python -m pytest tests\test_utf8_integrity.py -q
```
