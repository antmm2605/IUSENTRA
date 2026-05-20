# Pipeline inventario XSD, conoscenza procedurale e lifecycle pratica

Aggiornato: 20 maggio 2026.

## Scopo

Questa infrastruttura collega il catalogo ministeriale PST/XSD agli oggetti operativi IUSENTRA e consente di governare copertura, fonti, schede conoscitive, workflow pratica, firma, deposito, ricevute, notifica, prova e audit.

Non dichiara conformità legale finale delle singole procedure: la validazione giuridica resta in capo all'avvocato.

## Architettura

- `pct/procedure_inventory_importer.py`: legge `pct/data/pratiche_collegate_catalog.json` e importa ogni codice XSD.
- `pct/procedure_xsd_mapper.py`: propone mapping deterministici per prefissi noti e marca gli altri `needs_review`.
- `pct/procedure_coverage_ext.py`: calcola blocchi estesi, READY solo con evidenze, lifecycle, fonti e review.
- `pct/procedure_source_research.py`: costruisce piani multi-fonte governati per famiglia XSD e registra evidenze sintetiche tracciate.
- `pct/procedure_knowledge_pipeline.py`: gestisce fonti multi-sorgente e schede originali IUSENTRA.
- `pct/procedure_lifecycle.py`: template minimi per famiglie XSD e state machine della pratica.
- `pct/digital_signature_workflow.py`: registra richiesta, esito e verifica firma; non firma automaticamente.
- `pct/telematic_deposit_workflow.py`: gestisce pacchetto, stato deposito, ricevute e stub connettore.
- `pct/post_acceptance_obligations.py`: genera obblighi successivi conservativi.
- `pct/notification_workflow.py`: governa notifica, relata, prova e stub invio.
- `pct/evidence_vault.py`: registra evidenze, hash e collegamenti.
- `pct/procedure_lifecycle_repository.py`: repository SQLite e audit deterministico.

## Tabelle Nuove

La migration `pct/sql/20260520_procedure_lifecycle_knowledge_pipeline.sql` crea:

- `legal_ministerial_xsd_objects`
- `legal_procedure_xsd_map`
- `legal_procedure_source_evidence`
- `procedure_knowledge_cards`
- `procedure_lifecycle_templates`
- `procedure_lifecycle_steps`
- `fascicolo_workflow_instances`
- `fascicolo_workflow_events`
- `digital_signature_events`
- `telematic_deposit_packages`
- `telematic_deposit_receipts`
- `post_acceptance_obligations`
- `notification_events`
- `evidence_documents`
- `procedure_audit_log`

La migration è idempotente e compatibile SQLite.

## Import XSD

Il catalogo PST/XSD è il registro canonico degli oggetti depositabili. L'importer mappa:

- `areas[].area` su `xsd_area_code`
- `areas[].label` su `xsd_area_label`
- `items[].codice` su `xsd_family_code`
- `items[].label` su `xsd_family_label`
- `children[].codice` su `xsd_code`
- `children[].label` su `xsd_label`

Gli item senza `children` vengono importati come codice autonomo, senza perdere voci.

Comandi:

```powershell
python -m pct.procedure_inventory_importer --db intelligence/legal_coverage.db --catalog pct/data/pratiche_collegate_catalog.json --dry-run
python -m pct.procedure_inventory_importer --db intelligence/legal_coverage.db --catalog pct/data/pratiche_collegate_catalog.json --apply
```

## Mapping XSD/Procedure

Le regole iniziali riconoscono:

- `010` ingiunzione ante causam
- `050` ingiunzione societaria, finanziaria, bancaria e creditizia
- `030` sfratti
- `011`, `012`, `014`, `015`, `017`, `019`, `051`, `052`, `053`, `055`, `059` cautelari
- `020` possessorie

Se non esiste procedura operativa compatibile nel registry, viene creato solo un mapping proposto `needs_review`; nessun codice XSD viene inventato e nessun mapping incerto diventa `validated`.

## Coverage e Gap

La coverage estesa aggiunge blocchi:

`xsd_object`, `xsd_mapping`, `source_evidence`, `knowledge_card`, `lifecycle_template`, `lifecycle_steps`, `signature_rules`, `deposit_rules`, `receipt_rules`, `acceptance_rules`, `post_acceptance_rules`, `notification_rules`, `relata_rules`, `proof_deposit_rules`, `evidence_rules`.

Una procedura/codice XSD non è `READY` se mancano mapping, lifecycle, regole deposito/firma/ricevute/notifica/evidenze o review umana richiesta.

I gap vengono accodati in `coverage_gap_queue` con payload contenente `xsd_code`, `xsd_label`, `procedure_code`, blocchi mancanti, azione richiesta, rischio e review umana.

## Fonti Multi-Sorgente

Sono supportate fonti:

- ufficiali
- giurisprudenziali
- professionali
- interne
- tecniche
- prassi locali
- banche dati licenziate

Regola anti-copia: le fonti professionali esterne usano `summary_only`, richiedono `extracted_principle`, link o titolo, e `original_quote_short` non può superare 500 caratteri. La scheda riformula in modo autonomo i principi operativi e conserva link, tipo fonte e data di verifica.

Il primo layer operativo usa fonti ufficiali e tecniche tracciate per creare una base in review in funzione della pratica selezionata (`xsd_code`, label, famiglia e area):

- PST download XSD e file ufficiali del Processo Civile Telematico;
- specifiche tecniche PCT pubblicate sul Portale Servizi Telematici;
- Normattiva/Codice di procedura civile per tutte le pratiche XSD generate: monitorie, sfratti, cautelari, possessorie, famiglia, contenzioso civile, Giudice di pace, appello/TRAP, successioni, diritti reali, revocazione e lavoro/previdenza;
- D.L. 179/2012 art. 16-bis per il presidio deposito telematico;
- L. 53/1994 art. 3-bis per il presidio notifica PEC in proprio.

Le fonti professionali possono essere aggiunte dall'avvocato o da un operatore autorizzato come evidenza `professional`, ma la pipeline non le copia e non le promuove automaticamente a fonte validata.

Ogni piano fonte contiene sempre almeno un presidio Normattiva/Codice di procedura civile e poi riferimenti specifici della pratica scelta. Per le famiglie non ancora specializzate viene usato un presidio CPC generale e il risultato resta `needs_review`, senza dichiarare copertura giuridica completa.

## Scheda Originale IUSENTRA

La knowledge card contiene almeno presupposti, documenti, termini, competenza, atto, allegati, firma, deposito, ricevute, accettazione, adempimenti successivi, notifiche, relata, prova, errori ricorrenti, rischi, scelte strategiche, fonti e data verifica.

La pubblicazione è bloccata se manca fonte ufficiale o tecnica, se la card non è approvata, se esistono errori bloccanti o se la review avvocato è richiesta e non completata.

## Lifecycle Pratica

La state machine copre apertura, classificazione, documenti, redazione, review, firma, busta, deposito, ricevute, accettazione/rifiuto, provvedimento, notifica, relata, prova, deposito prova, monitoraggio e chiusura.

Regole severe:

- `FIRMATO` richiede firma verificata quando la firma è richiesta.
- `DEPOSITO_ACCETTATO` richiede ricevuta `ACCETTAZIONE_DEPOSITO`.
- `NOTIFICA_EFFETTUATA` richiede evento notifica `SENT`.
- `PROVA_NOTIFICA_ACQUISITA` richiede evidenza documentale.
- `CHIUSA` è bloccata se esistono obblighi post-accettazione pendenti.

## Firma, Deposito e Notifica

La firma digitale è solo workflow: richiesta, esito e verifica strutturale. Non vengono conservati PIN, password, token o credenziali.

Il deposito telematico crea e valida pacchetti, registra invio stub, ricevute ed esiti. Nessun deposito reale avviene senza connettore autorizzato.

La notifica registra destinatario, fonte indirizzo, atto, relata, invio stub, consegna e prova. `PROOF_ACQUIRED` richiede evidenza collegata.

## Audit

Ogni mutazione critica produce `procedure_audit_log` con entità, azione, attore, sorgente, JSON prima/dopo, diff e `event_hash` deterministico.

## Test e Coverage

Test mirati:

```powershell
python -m pytest tests/test_procedure_inventory_importer.py tests/test_procedure_xsd_mapper.py tests/test_procedure_coverage_ext.py tests/test_procedure_source_research.py tests/test_procedure_knowledge_pipeline.py tests/test_procedure_lifecycle.py tests/test_digital_signature_workflow.py tests/test_telematic_deposit_workflow.py tests/test_post_acceptance_obligations.py tests/test_notification_workflow.py tests/test_evidence_vault.py tests/test_procedure_lifecycle_repository.py
```

Coverage severa nuovi moduli:

```powershell
python -m coverage run --rcfile=config/coverage-procedure-lifecycle.ini -m pytest tests/test_procedure_inventory_importer.py tests/test_procedure_xsd_mapper.py tests/test_procedure_coverage_ext.py tests/test_procedure_source_research.py tests/test_procedure_knowledge_pipeline.py tests/test_procedure_lifecycle.py tests/test_digital_signature_workflow.py tests/test_telematic_deposit_workflow.py tests/test_post_acceptance_obligations.py tests/test_notification_workflow.py tests/test_evidence_vault.py tests/test_procedure_lifecycle_repository.py
python -m coverage report --rcfile=config/coverage-procedure-lifecycle.ini --fail-under=100
```

Il layer multi-fonte è incluso nel gate mirato tramite `tests/test_procedure_source_research.py`.

## Limiti

- Nessun scraping massivo.
- Nessun login automatico su portali giudiziari.
- Nessun deposito reale non autorizzato.
- Nessun invio PEC reale.
- Nessuna firma digitale reale.
- Nessuna conservazione di PIN, password, token o credenziali.
- Nessun aggiramento di paywall o robots.
- Nessuna copia lunga di contenuti professionali esterni.
