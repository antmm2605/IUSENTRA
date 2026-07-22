# Isolamento PEC multi-tenant — verifica del 22/07/2026

## Risultato tecnico

Il repository PEC non usa più fallback che leggono o riassegnano messaggi appartenenti a un tenant diverso. Il contratto applicato è fail-closed:

- `ingest_mime` deduplica esclusivamente entro `tenant_id`;
- ogni nuovo ID messaggio deriva deterministicamente da tenant e SHA-256 del MIME, senza esporre lo slug in chiaro;
- `get_message_row` interroga esclusivamente la coppia `tenant_id`/`id` e restituisce `KeyError` per un record estraneo;
- `ids_by_header_message_ids` applica sempre il filtro tenant prima del lookup dell'header `Message-ID`;
- l'apertura/inizializzazione dello schema non adotta più automaticamente le righe storiche `default` e non modifica la proprietà dei record.

## Compatibilità legacy

Gli ID legacy non vengono riscritti. Un record storico resta accessibile quando il suo `tenant_id` coincide con quello del repository; una nuova ingestione dello stesso MIME da parte dello stesso tenant restituisce quell'ID come duplicato. Se il record appartiene a `default` o a un altro tenant, non viene letto, adottato o modificato. Un'eventuale attribuzione storica deve essere eseguita in futuro con una migrazione separata, esplicita, verificata e auditata, mai durante GET, bootstrap o ingestione.

## Struttura SQLite/PostgreSQL

Non è stata necessaria alcuna migrazione distruttiva. Entrambi gli schemi mantengono:

- chiave primaria globale `id`;
- unicità `(tenant_id, mime_sha256)`;
- unicità `(tenant_id, account_email, message_id_header, mime_sha256)`;
- indice `(tenant_id, message_id_header)` per il lookup isolato e rapido.

L'indice è stato allineato nei file schema SQLite e PostgreSQL; lo schema runtime SQLite lo possedeva già.

## Casi coperti

1. Due tenant non predefiniti, stesso database audit, stesso MIME, stesso header e stessa casella: vengono creati due record con ID distinti.
2. La seconda ingestione nello stesso tenant viene riconosciuta come duplicato del solo record proprietario.
3. Ogni tenant può leggere e trovare per header esclusivamente il proprio record.
4. Il tentativo di leggere l'ID dell'altro tenant fallisce senza cambiare il proprietario.
5. Un ID legacy dello stesso tenant resta accessibile e deduplicabile.
6. I tenant `default` e studio nello stesso database restano distinti; i rispettivi job vengono elaborati solo dal proprietario.

## Verifiche

Test dedicati:

```text
python -m pytest -q tests/test_pec_pipeline_tenant_isolation.py
```

Esito: 4 test superati.

Compatibilità mirata iniziale:

```text
python -m pytest -q tests/test_pec_pipeline_tenant_isolation.py tests/test_pec_audit_pipeline.py::test_pec_pipeline_deduplicates_by_message_id_and_mime_hash tests/test_pec_audit_pipeline.py::test_pec_pipeline_non_riassegna_record_default_ad_altro_tenant tests/test_pec_audit_pipeline.py::test_pec_pipeline_processa_solo_job_del_tenant_proprietario tests/test_pec_audit_pipeline.py::test_pec_source_detail_isola_il_tenant_e_resta_sola_lettura tests/test_pec_audit_pipeline.py::test_pec_repository_non_adotta_automaticamente_righe_legacy_default
```

Esito: 9 test superati.

Sono stati inoltre eseguiti 6 test di compatibilità su riepiloghi per header, corpo PEC, audit operativo, API multi-studio e recupero SQLite; esito: 6 superati.

La modifica è backend e non introduce una nuova superficie UI. Non è stata quindi eseguita in questo sotto-incarico una prova visuale su `127.0.0.1:8080`; la campagna end-to-end finale resta affidata al task principale.
