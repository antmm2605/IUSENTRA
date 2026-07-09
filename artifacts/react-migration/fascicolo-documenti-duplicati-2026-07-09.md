# Fascicoli - riconciliazione documenti duplicati

Data: 09/07/2026

## Obiettivo operativo

Eliminare dalla vista fascicolo i record documento uguali presenti più volte nello stesso fascicolo, senza cancellare file fisici, prove, allegati o metadati utili. La bonifica deve essere ripetibile sul tenant reale e la logica deve impedire che nuovi caricamenti/import dello stesso contenuto generino altri doppioni.

## Analisi dati reale

Tenant controllato sul server Hetzner: `studio-legale-giuseppe-montagnese`.

Fonte di verità: SQLite del tenant (`studio.db`), tabella `fascicoli`, campo `documenti_json`.

Audit preliminare:

- fascicoli analizzati: 333;
- documenti nei fascicoli: 13620;
- fascicoli con record documento duplicati: 275;
- record documento duplicati extra rilevati: 1150;
- caso visibile segnalato: fascicolo `9B9DF2A1`, `Spagnolo Sara c. MIM`, con più documenti QuickOrganizer ripetuti nella sezione `Provvedimenti`/documenti.

## Correzione implementata

- Aggiunto hash stabile del contenuto originale (`hash_contenuto_sha256`) ai documenti del fascicolo.
- Il caricamento documentale ora blocca il duplicato quando lo stesso contenuto è già presente, anche se il file salvato su disco è stato cifrato o rinominato.
- Aggiunta riconciliazione non distruttiva dei record già duplicati:
  - mantiene un documento principale;
  - assorbe metadati mancanti, tag, fonte, classificazione portale, riferimenti PST e firma;
  - aggiorna riferimenti interni di depositi PCT e attività processuali;
  - registra un avanzamento pratica `Riconciliazione automatica documenti duplicati`;
  - non cancella i file fisici.
- Aggiunto script operativo tenant-aware: `scripts/repair_fascicolo_document_duplicates.py`.

## Verifiche automatiche locali

Comandi eseguiti:

```powershell
python -m py_compile pct\fascicoli.py web\services\fascicoli_runtime.py scripts\repair_fascicolo_document_duplicates.py
python -m ruff check --output-format=github --select E9,F63,F7,F82 pct\fascicoli.py web\services\fascicoli_runtime.py scripts\repair_fascicolo_document_duplicates.py
python -m pytest tests/test_fascicoli.py::test_aggiungi_documento_non_duplica_stesso_contenuto tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_assorbe_record_e_riferimenti tests/test_fascicoli.py::test_riconcilia_doppioni_cliente_rg_unisce_documenti_e_pagamenti -q
```

Esito: pass.

## Verifiche server e UI

Da completare prima della chiusura:

- deploy Hetzner sul commit della correzione;
- dry-run dello script sul tenant `studio-legale-giuseppe-montagnese`;
- esecuzione reale della riconciliazione sul tenant;
- controllo DB dopo bonifica;
- apertura reale su `https://app.iusentra.it/fascicoli/9B9DF2A1#documenti` e verifica visiva della sezione documenti;
- controllo che nuovi upload/import non generino duplicati dello stesso contenuto.

## Code scanning

Il gate `Code scanning results / CodeQL` del PR GitHub va ricontrollato dopo il push. La correzione dei documenti è stata mantenuta stretta per non aggiungere nuovi sorgenti di path traversal o bypass tenant.
