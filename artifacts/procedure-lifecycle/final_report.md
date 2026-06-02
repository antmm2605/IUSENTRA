# Report finale Procedure Lifecycle Knowledge Pipeline

Data: 21 maggio 2026
Commit verificato localmente: `e17df23a` più integrazione report finale.

## Stati finali protetti

| Stato | Punto di ingresso protetto | Evidenza richiesta |
| --- | --- | --- |
| `VERIFIED` | `digital_signature_events.verification_status` | Aggiornamento solo da `record_signature_result`, con `signer_detected` e `hash_after`. |
| `READY` | `telematic_deposit_packages.deposit_status` | `xsd_code` attivo nel catalogo ministeriale, `DatiAtto.xml`, busta/pacchetto collegato e firme richieste `VERIFIED`. |
| `OFFICE_ACCEPTED` | `telematic_deposit_packages.deposit_status` | Ricevuta `ACCETTAZIONE_DEPOSITO` collegata al pacchetto. |
| `OFFICE_REJECTED` | `telematic_deposit_packages.deposit_status` | Ricevuta `RIFIUTO_DEPOSITO` o `ERRORE_TECNICO` collegata al pacchetto. |
| `TECHNICAL_ERROR` | `telematic_deposit_packages.deposit_status` | Ricevuta `ERRORE_TECNICO` collegata al pacchetto. |
| `PROOF_ACQUIRED` | `notification_events.status` | Bundle probatorio verificato in `notification_proof_bundles`, con destinatari, PEC inviata, relata, RAC/RdAC per ogni destinatario, link a evidenze hashate e audit. |
| `PROOF_DEPOSIT_REQUIRED` | `notification_events.status` | Stessa catena probatoria verificata della notifica, più obbligo di deposito prova ancora aperto. |
| `PROOF_DEPOSITED` | `notification_events.status` | Bundle `DEPOSITO_PROVA_NOTIFICA` verificato, DatiAtto.xml, busta, ricevuta deposito, esito ufficio `OFFICE_ACCEPTED` e riferimenti ricevuta per destinatario. |
| `FIRMATO` | `fascicolo_workflow_instances.current_step_code` | Firma digitale richiesta in stato `VERIFIED`, se la procedura o gli eventi firma la richiedono. |
| `DEPOSITO_ACCETTATO` | `fascicolo_workflow_instances.current_step_code` | Ricevuta `ACCETTAZIONE_DEPOSITO` collegata a un pacchetto del fascicolo. |
| `DEPOSITO_RIFIUTATO` | `fascicolo_workflow_instances.current_step_code` | Ricevuta `RIFIUTO_DEPOSITO` o `ERRORE_TECNICO` collegata a un pacchetto del fascicolo. |
| `NOTIFICA_EFFETTUATA` | `fascicolo_workflow_instances.current_step_code` | Evento notifica `SENT`, `DELIVERED` o stato prova già validato. |
| `PROVA_NOTIFICA_ACQUISITA` | `fascicolo_workflow_instances.current_step_code` | Catena probatoria notifica completa e verificata, non documento singolo. |
| `CHIUSA` / `COMPLETED` | `fascicolo_workflow_instances.current_step_code/status` | Nessun obbligo post-accettazione pendente. |

## Relazione proof_bundle_id

`proof_bundle_id` non è mai prova sufficiente da solo. Dal 2 giugno 2026 il
repository accetta gli stati prova notifica solo se il valore punta a
`notification_proof_bundles.bundle_id`, il bundle è `VERIFIED`, appartiene allo
stesso fascicolo e alla stessa notifica, e la matrice in
`docs/specs/ministero/NOTIFICHE_PEC_MATRICE_PROBATORIA_2026-06-02.md` è
completa.

Il controllo dereferenzia destinatari, ricevute, relata, deposito prova,
riferimenti DatiAtto e link a `evidence_documents` con hash SHA-256. La stessa
relazione minima è replicata nei trigger SQLite anti-bypass: il trigger non
accetta più una riga generica in `evidence_documents` come prova notifica.

## Test negativi e positivi aggiunti

- Negativo create: `repo.create_notification_event(... status='PROOF_ACQUIRED', proof_bundle_id='missing-proof')` fallisce e crea `notification_create_blocked`.
- Negativo update: `repo.update_notification_event(... status='PROOF_ACQUIRED', proof_bundle_id='missing-proof', source='notification_proof_validation')` fallisce e crea `notification_update_blocked`.
- Positivo: `PROOF_ACQUIRED` passa solo con `proof_bundle_id` che punta a un bundle probatorio verificato, con ruoli evidenza distinti e ricevute positive per destinatario; coperto anche l'update successivo del solo `proof_bundle_id`.
- `PROOF_ACQUIRED`, `PROOF_DEPOSITED` e `PROVA_NOTIFICA_ACQUISITA` non passano senza catena probatoria completa, né tramite repository, né tramite workflow runtime, né tramite update SQL diretto.
- Stati sconosciuti: coperti enum firma, deposito, notifica, obblighi e workflow con errore controllato.
- Bypass controllati: update SQL diretto, repository helper generico, `apply_generated_sql`, publish SQL, import payload, ricevute, workflow transition manuale, script CLI e fixture permissive.

## Audit

Le azioni critiche bloccate dal repository scrivono audit prima di sollevare errore:

- `signature_event_update_blocked`;
- `deposit_package_update_blocked`;
- `notification_create_blocked`;
- `notification_update_blocked`;
- `workflow_instance_create_blocked`;
- `workflow_transition_blocked`.

L'audit viene sanificato: niente PIN, password, token, cookie, path sensibili, email, CF, IBAN o telefoni non mascherati.

## Coverage e gate

- Soglie coverage non modificate: `config/coverage-procedure-lifecycle.ini` mantiene `branch = True` e `fail_under = 100`.
- Nessuna nuova esclusione `pragma: no cover` o `pragma: no branch` introdotta nel perimetro.
- Coverage nuovi/modificati: 1774 statement, 0 missed; 558 branch, 0 partial; totale 100%.
- Pytest mirato: 33/33 passati.
- Compile mirato: OK sui moduli lifecycle, firma, deposito, notifica, evidence, coverage e repository.

## Rami difensivi coperti

Coperti i rami: mapping incerto `needs_review`, XSD mancante/inattivo, firma richiesta non `VERIFIED`, ricevuta accettazione assente, prova notifica assente, chiusura con obblighi pendenti, fonte professional con quote lunga, fonte professional senza principio estratto, fonte interna con PII, stato sconosciuto, fallback source/retrieval non configurato, audit mancante su azione critica, SQL diretto, `apply_generated_sql`, publish SQL, import payload e fixture.

## Regressioni trovate e corrette

- Coverage ha individuato un ramo non coperto sull'update del solo `proof_bundle_id`; aggiunto test negativo e positivo dedicato.
- I deploy doppi dopo le 17:00 italiane hanno mostrato falsi rossi su `/legal-intelligence/` quando la rotta era ancora in warm-up; il workflow Hetzner ora usa retry governati su `/api/pronto` e sulle rotte pubbliche.
- Nessun bypass residuo aperto sui final state protetti nel perimetro testato.
