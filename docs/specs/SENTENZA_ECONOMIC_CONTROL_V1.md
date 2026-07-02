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
