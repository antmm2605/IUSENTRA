# Sentenza Economic Control V1

Controllo economico-probatorio delle sentenze civili: prima di alimentare qualunque
contesto economico, il sistema **dimostra** che la sentenza appartiene al fascicolo,
poi estrae spese liquidate, distrazione e contributo unificato, e propone azioni
**solo da confermare**. Feature flag default-off: `features.sentenzaEconomicControl`
(strumenti Lex: `lex.economicContextTools`).

## Base normativa (fonti certe)

| Tema | Norma |
|---|---|
| Condanna alle spese liquidate a favore della parte | art. 91 c.p.c. |
| Distrazione a favore del difensore antistatario (credito diretto avvocato) | art. 93 c.p.c. |
| Comunicazione di deposito ≠ decorrenza termini brevi | art. 133 / art. 325 c.p.c. |
| Rimborso forfettario spese generali (15%) | D.M. 55/2014 |
| Contributo unificato (scaglioni, controllo, invito al pagamento) | D.P.R. 115/2002 artt. 9, 13, 14, 15, 16, 248 |
| Gratuito patrocinio (decreto di pagamento, prenotazione a debito) | D.P.R. 115/2002 artt. 82-85 |

Le keyword operative vivono nel ruleset versionato `pct/data/economic_legal_rules_v2026_07.json`
(ambito **civile**; penale/PAT/PTT richiedono ruleset separati).

## Flusso

1. **Identità** (`build_identity_match`): uguaglianza RG **esatta** + punteggio
   cliente/ufficio (riuso scorer presidio PEC). RG diverso ⇒ non si alimenta nulla.
2. **Lettura economica** (`extract_economics`): tipo provvedimento, esito, condanna/
   compensazione/distrazione, importi (riuso `legal_regex`). Beneficiario del credito:
   `avvocato` solo con distrazione, altrimenti `cliente`/`erario`/`incerto`.
3. **Contributo unificato** (`assess_contributo_unificato`): stato (pagato/esente/
   prenotato a debito/mancante/insufficiente/da integrare/incerto), importo atteso dai
   soli scaglioni `normative_tables`. Mai "pagato" dal solo nome file.
4. **Contesto/Dashboard** (incr.2): blocco `source=sentenza_economic_audit` pass-through +
   KPI/worklist additivi nella dashboard economica del fascicolo.
5. **Lex** (incr.3): 5 tool read-only governati; Lex non deduce importi e si astiene se
   RG non combacia.
6. **Attivazione** (incr.4/5): manuale (avvocato) via `/api/v1/ui/sentenza-economic/*` e
   automatica dal presidio PEC su `deposito_sentenza` (solo anteprima).
7. **Parcella** (incr.5): un credito **confermato** diventa `Parcella` `origine="sentenza"`.

## Regole anti-errore (hardcoded)

1. RG sentenza ≠ RG fascicolo ⇒ non alimentare; revisione umana.
2. Mai "credito avvocato" senza distrazione/antistatario.
3. "Condanna alle spese" ≠ parcella emessa.
4. Mai parcella/fattura definitiva senza conferma avvocato.
5. CU "pagato" mai dal solo nome file (serve importo + IUV/data).
6. Mai importi CU hardcoded: solo `normative_tables` versionate.
7. Mai regole civili su penale/PAT/PTT.
8. Nessun dato fiscale/cliente nelle notifiche push.
9. Mai chiudere un alert CU senza ricevuta o stato esente/prenotato a debito.
10. Termine breve impugnazione mai dalla sola comunicazione di deposito.

## Persistenza

- SQLite/PostgreSQL gemelli (`pct/sql/20260702_sentenza_economic*.sql`): tabelle
  `sentenza_economic_audits`, `contributo_unificato_audits`, `fascicolo_economic_events`,
  `sentenza_economic_audit_events`. Isolate per `tenant_id`, whitelist colonne.
- Registro probatorio firmato a catena di hash (`sentenza_economic_decisions.jsonl`,
  riuso `ComplianceDecisionLog`): attach verificato, conferma credito, parcella generata.
- Percorso tenant `SENTENZA_ECONOMIC_DB`, risolto fail-closed.

## Sicurezza

`tenant_id` sempre server-side; nessun path nelle risposte; nessun testo sentenza/PII
nei log; documenti cifrati letti solo in memoria; RBAC (`fatturazione.leggi/scrivi`,
Lex `ai.usa` + permessi sorgente).

## File

- Dominio: `pct/sentenza_economic_audit.py`, `pct/sentenza_economic_repository.py`,
  `pct/sentenza_economic_dashboard.py`, `pct/sentenza_economic_workflow.py`,
  `pct/data/economic_legal_rules_v2026_07.json`, `pct/sql/20260702_sentenza_economic*.sql`.
- Web: `web/services/sentenza_economic_runtime.py`, `web/blueprints/api_v1_sentenza_economic.py`.
- Lex: `lex/tools/economic_context_tools.py`, sorgente `EconomicJudgmentSource`.
- Test: `tests/test_sentenza_economic_{audit,repository,dashboard,runtime,workflow}.py`,
  `tests/test_lex_economic_context_tools.py`.

## Limiti residui

- Pagina React dedicata di gestione: wiring successivo (la superficie visiva è già la
  dashboard economica del fascicolo). Aggancio del trigger PEC nel runtime del presidio
  live: la funzione `run_pec_economic_trigger` è pronta e testata, l'innesto nel loop PEC
  segue quando si abilita il flag in produzione.

## Incassi manuali e separazione dei capi economici — 20/10/2026

La registrazione della cassa della parcella usa il repository SQL nativo di
Prima nota. L'incasso di un compenso non dimostra l'incasso del capitale
liquidato al cliente: il nuovo comando non modifica il pagamento della
liquidazione del giudice. Prima di attribuire un nuovo movimento verifica
anche che cliente della parcella e cliente del fascicolo concordino.

Il registro mantiene acconti, saldo e storni con riferimenti alla parcella e
ai movimenti originali. I riepiloghi riusano gli stessi riscontri a lotti;
il periodo mensile legge l'indice temporale e verifica soltanto gli eventi
richiesti. Un dato economico non riscontrabile non diventa uno zero, e un
errore nei riepiloghi non deve nascondere l'archivio documentale.

Gli importi storici, le decisioni manuali e i JSON originali restano preservati.
La presenza dello stato «Pagata» non autorizza a inventare un nuovo movimento
dal totale attuale del documento. La preparazione SQL conserva fonte,
impronte, backup, audit e fence di adozione, senza migrazioni nelle GET.

La candidata riguarda gli incassi delle fatture emesse. I percorsi esistenti
di saldo integrale delle bozze e delle proforme restano operativi; l'estensione
degli acconti su proforma e delle fatture d'acconto rimane un incarico aperto.
Il rilascio richiede collaudo reale, commit/push, deploy e pulizia verificata.
I singoli esiti vanno registrati nel verbale del rilascio, senza estendere
una prova positiva ai percorsi che non sono stati esercitati.

## Contratto del registro incassi — collaudo 20/10/2026


- `GET /api/fatturazione/<invoice_id>/incassi`: connessione nativa di sola
  lettura; tenant e operatore provengono dalla sessione. Nessun DDL, recupero
  documentale, OCR, adozione JSON o ricalcolo di altri fascicoli.
- `POST` sulla stessa risorsa: permessi `fatturazione.leggi` e
  `fatturazione.scrivi`, CSRF nativo,
  scope del contesto, UUID del comando e revisione del documento obbligatori.
  Operazioni ammesse: `receipt` e `reversal`; i campi aggiuntivi sono rifiutati.
- Il comando comprende movimento di Prima nota, collegamento probatorio,
  revisione/saldo della parcella, audit e outbox nella stessa transazione.
  Un recupero con lo stesso UUID restituisce lo stesso movimento senza
  registrarlo o notificarlo una seconda volta.
- La risposta conferma scope, UUID, documento, revisione iniziale e movimento.
  Il client verifica anche importo, data, metodo, nota e identità dello storno
  prima di rimuovere il comando pendente. Le incertezze dopo il commit
  restituiscono `503 outcome_not_confirmed`, senza autorizzare un nuovo invio.
- `409 revision_conflict` indica una revisione superata; `409 command_conflict`
  o `context_changed` conserva il comando originale. Solo un rifiuto esplicito
  di validazione o revisione consente di correggere l'intento senza perdere
  la bozza libera. Il documento non trovato non prova un mancato salvataggio.
- Importi in centesimi interi, date effettive ISO nel contratto e italiane
  nell'interfaccia; limiti di lunghezza, calendario e data non futura verificati
  anche nel dominio. Una registrazione è distinta da una disposizione bancaria:
  questo endpoint non trasferisce denaro.
- `OPEN`, `PARTIAL`, `PAID`, `DRAFT`, `CANCELLED`, `REVIEW` descrivono il saldo
  riscontrato. Un pagamento storico non si ricostruisce dal totale corrente
  della fattura: importi non determinabili restano `null`, con motivo.
- I movimenti probatori sono append-only: correzione tramite storno motivato,
  mai riscrittura di importo/data o cancellazione. La riconciliazione bancaria
  mantiene separati i propri riferimenti e non modifica l'impronta del fatto.
- Preparazione esplicita: `python -m tools.prepare_invoice_receipts
  --tenant-registry /data/tenants.json --backup-dir /data/backup/incassi-sql-20261020
  --check`. Codice `2`: preparazione necessaria. Applicazione solo con
  `--writers-drained`, backup verificati e controllo dei dati prima/dopo.
  Gli studi già adottati non vengono reimportati; una ripresa mantiene il
  riferimento del backup originale della Prima nota.
- Il collaudo automatico usa SQLite e PostgreSQL nativi. L'accettazione richiede
  anche il browser reale sulla copia Docker `127.0.0.1:8080`: i soli controlli
  automatici non costituiscono verifica su macchina reale né autorizzano una
  dichiarazione di rilascio.
