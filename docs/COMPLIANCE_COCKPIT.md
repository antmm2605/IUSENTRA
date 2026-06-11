# Compliance Cockpit — cabina di conformità dello studio

Stato: **prima fase (backend)**. Trasforma le regole di sicurezza/deontologia in
workflow usabili dall'avvocato: conflitto di interessi, antiriciclaggio/KYC e
registro decisioni append-only verificabile. GDPR e audit probatorio riusano i
moduli privacy/audit già presenti.

## Moduli (`pct/compliance/`)

### Conflitto di interessi — `conflicts.py`
Base: Codice Deontologico Forense (art. 24, 37, 68). Rileva:
- **DIRETTO**: il nuovo cliente è già controparte in un fascicolo; oppure la
  controparte proposta è già nostro cliente (match per codice fiscale).
- **POTENZIALE**: stesso gruppo di una controparte esistente; match solo per
  nome (senza CF) da verificare.

`build_conflict_report(candidate_client, candidate_counterparty, existing)` →
`ConflictReport` con `clear/hasDirect/hasPotential` e l'elenco dei findings con
il fascicolo di riferimento. La decisione finale resta all'avvocato (waiver
tracciato nel registro).

### Antiriciclaggio / KYC — `kyc.py`
Base: D.Lgs. 231/2007 (adeguata verifica, titolare effettivo, approccio basato
sul rischio). `assess_risk(factors)` calcola livello **basso/medio/alto** da
fattori spiegabili (PEP, paese a rischio, contante elevato, titolare effettivo
non identificato per persone giuridiche, settore a rischio, rapporto a distanza)
con motivazioni. `document_expiry_status(...)` controlla la scadenza del
documento (scaduto / in scadenza ≤30gg / valido). `KycRecord.assess()` indica se
l'adeguata verifica è completa e se serve la **verifica rafforzata** (rischio
alto). Nessuna decisione automatica: è supporto tracciabile.

### Registro decisioni — `decisions.py`
`ComplianceDecisionLog` registra ogni decisione (waiver conflitto, esito KYC,
scelta GDPR) in JSONL **append-only** con **hash-chain** (riusa le primitive
probatorie della pipeline OCR): `verify_chain()` ricalcola la catena e rileva
qualsiasi manomissione. Filtrabile per tenant.

## Sicurezza

- Nessuna PII in chiaro non necessaria nelle viste pubbliche (`to_public`).
- Il registro è immutabile e verificabile (catena di hash + `previous_hash`).
- Tenant-aware: il chiamante passa `tenant_id`; le decisioni sono filtrabili per studio.

## Prossimi PR

- GDPR cockpit: collega registro trattamenti, consensi, data retention, richieste
  accesso/cancellazione e data breach log (su `pct/privacy.py` esistente).
- API `/api/v1/ui/compliance/*` e UI React (conflitti, KYC, registro decisioni,
  export firmato).
- Persistenza KYC tenant-aware + allegati protetti del documento identificativo.
