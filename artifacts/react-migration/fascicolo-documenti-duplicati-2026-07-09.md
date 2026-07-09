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
- Aggiunta chiave semantica per PDF processuali con stesso nome e stesso tipo:
  - vale solo per PDF di atti/provvedimenti processuali;
  - non vale per PEC/EML, XML, P7M, ricevute o allegati tecnici;
  - se il contenuto non è byte-identico, la copia assorbita viene conservata nello storico versioni del documento principale.
- Aggiunto script operativo tenant-aware: `scripts/repair_fascicolo_document_duplicates.py`.
- Dopo prova reale su server è stato aggiunto un guardrail di persistenza: la riconciliazione documentale salva solo i fascicoli modificati e non esegue più un full-replace della tabella `fascicoli`.
- Dopo ulteriore controllo è stato aggiunto anche il riallineamento del mirror `fascicoli/fascicoli.json` dopo ogni salvataggio parziale SQL: SQLite resta la fonte di verità, il JSON viene rigenerato solo come mirror, così audit e ripartenze non leggono più un conteggio vecchio.
- Il report della riconciliazione ora espone `source_of_truth=sqlite` quando opera su `studio.db`, così è visibile se una procedura sta lavorando sul database reale o su un mirror storico.

## Verifiche automatiche locali

Comandi eseguiti:

```powershell
python -m py_compile pct\fascicoli.py web\services\fascicoli_runtime.py scripts\repair_fascicolo_document_duplicates.py
python -m py_compile pct\fascicoli.py pct\polisWeb.py web\services\telematico_runtime.py
python -m ruff check --output-format=github --select E9,F63,F7,F82 pct\fascicoli.py web\services\fascicoli_runtime.py scripts\repair_fascicolo_document_duplicates.py tests\test_fascicoli.py
python -m ruff check --output-format=github --select E9,F63,F7,F82 pct\fascicoli.py pct\polisWeb.py web\services\telematico_runtime.py tests\test_fascicoli.py tests\test_polisweb.py
python -m pytest tests/test_fascicoli.py::test_aggiungi_documento_non_duplica_stesso_contenuto tests/test_fascicoli.py::test_aggiungi_documento_non_duplica_pdf_stesso_nome_tipo_conserva_versione tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_assorbe_record_e_riferimenti tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_pdf_stesso_nome_conserva_versione tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_sql_non_riscrive_tutta_tabella tests/test_fascicoli.py::test_riconcilia_doppioni_cliente_rg_unisce_documenti_e_pagamenti -q
python -m pytest tests/test_fascicoli.py::test_fascicolo_serializza_metadati_sync_portale tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_sql_non_riscrive_tutta_tabella tests/test_polisweb.py::test_importa_fascicolo_popola_cliente_parti_e_attivita tests/test_polisweb.py::test_importa_fascicolo_esistente_sincronizza_cliente_parti_e_attivita tests/test_polisweb.py::test_acquisizione_pst_collega_fascicolo_esistente_con_iddfa_specifico tests/test_polisweb.py::test_api_acquisizione_local_matches_pst_arricchisce_risultati_local_signer -q
python -m pytest tests/test_fascicoli.py::test_fascicolo_serializza_metadati_sync_portale tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_sql_non_riscrive_tutta_tabella tests/test_fascicoli.py::test_riconcilia_documenti_duplicati_pdf_stesso_nome_conserva_versione tests/test_polisweb.py::test_importa_fascicolo_popola_cliente_parti_e_attivita tests/test_polisweb.py::test_importa_fascicolo_esistente_sincronizza_cliente_parti_e_attivita tests/test_polisweb.py::test_acquisizione_pst_collega_fascicolo_esistente_con_iddfa_specifico tests/test_polisweb.py::test_api_acquisizione_local_matches_pst_arricchisce_risultati_local_signer -q
pnpm --filter @iusentra/studio typecheck
```

Esito: pass.

## Import fascicolo da Studio Telematico / PST

Controllo richiesto: quando si importa o si aggiorna un fascicolo dal portale, IUSENTRA deve collegare il download al fascicolo già presente e non creare una nuova pratica se esiste già la stessa posizione.

Correzione applicata:

- il fascicolo conserva in persistenza i metadati ufficiali di aggancio: `codice_ufficio_portale`, `id_fascicolo_portale`, `tipo_registro`, `registro_portale`, `servizio_pst`, `sub_procedimento`, `id_dfa`, `ruolo_polisweb`;
- la chiave esterna PST non è più solo `ufficio/numero/anno/procedimento` quando il portale espone dati più forti: include anche `sub`, `dfa` e `id` del fascicolo portale;
- l'import guidato React e il percorso Local Signer/browser producono la stessa chiave forte;
- `ClientPolisWeb.importa_fascicolo` e `sincronizza_fascicolo_esistente` scrivono gli stessi metadati anche fuori dal runtime React;
- il matching automatico ora usa prima `source_external_id`, poi RG/anno/ufficio; se la selezione ha discriminanti portale, l'aggancio è automatico solo se coincidono o se c'è un unico fascicolo locale ancora non marcato dal portale;
- se più fascicoli locali condividono RG/ufficio e il portale dà `idDfa/subprocedimento`, il sistema non sceglie a caso.

Test aggiunti:

- serializzazione/persistenza dei metadati portale sul fascicolo;
- import nuovo da PolisWeb con metadati portale salvati;
- sincronizzazione di fascicolo esistente senza creare duplicati;
- match tra due fascicoli con stesso RG/ufficio ma `idDfa` diverso, verificando che venga scelto quello corretto.

## Ripristino controllato durante verifica server

Durante la seconda bonifica server è emerso che il salvataggio full-replace poteva riscrivere `studio.db` partendo da un mirror JSON ridotto. È stato ripristinato subito lo snapshot temporaneo integro `/tmp/iusentra-dedupe-semantic-pre-20260709084200.db`.

Verifica dopo ripristino:

- `fascicoli` in SQLite: 333;
- mirror `fascicoli/fascicoli.json`: 333 record;
- fascicolo `9B9DF2A1` presente;
- `https://app.iusentra.it/api/pronto`: 200.

La correzione successiva elimina il rischio alla radice: il salvataggio della riconciliazione è ora parziale sui soli fascicoli toccati e rigenera il mirror dopo il commit SQL.

Dry-run server dopo il ripristino, prima della bonifica definitiva:

- fascicoli analizzati: 333;
- fascicoli con duplicati: 230;
- record documento duplicati da assorbire: 869;
- la bonifica definitiva deve essere eseguita dopo il deploy del guardrail mirror, non con la versione precedente.

## Verifiche server e UI

Eseguite sul server Hetzner `https://app.iusentra.it`, tenant `studio-legale-giuseppe-montagnese`, commit `ffe1f50e`.

Deploy:

- branch server: `Codex/legal-electronic-filing-kIxcV`;
- commit server: `ffe1f50e81deaf076ad3ddbbfa8e625a3f268eaf`;
- container applicativo unico: `iusentra-app`;
- app, scheduler e OCR: healthy;
- `/api/pronto`: `ok=true`, versione `2.254.17`.

Bonifica reale documenti:

- dry-run prima dell'applicazione: `source_of_truth=sqlite`, 333 fascicoli analizzati, 230 fascicoli con duplicati, 869 record documento da assorbire;
- applicazione reale: `source_of_truth=sqlite`, 869 record assorbiti;
- dry-run dopo applicazione: 333 fascicoli analizzati, 0 fascicoli con duplicati, 0 record documento da assorbire;
- controllo SQLite dopo bonifica: 333 fascicoli;
- controllo mirror `fascicoli/fascicoli.json` dopo bonifica: 333 record.

Verifica fascicolo reale `9B9DF2A1`:

- apertura autenticata su `https://app.iusentra.it/fascicoli/9B9DF2A1#documenti`;
- tempo reload autenticato fino alla sezione fascicolo/documenti: circa 3,65 secondi;
- `Documenti e atti`: 44;
- `Indicizzazione Lex`: totali 44, pronti 44, in coda 0, in corso 0, errori 0, da aggiornare 0, ultimo indice presente;
- sezione `Provvedimenti`: `Sentenza Cassazione.PDF` una sola volta, `Sentenza_Tribunale_Vicenza_20-04-2023.PDF` una sola volta;
- i due nomi ancora ripetuti nel controllo grezzo sono comunicazioni/prove distinte, con hash e identificativi diversi (`DatiAtto.xml.p7m` da due documenti portale diversi e due consegne PEC QuickOrganizer diverse), quindi non vanno assorbiti come duplicati.

Verifica vista economica reale:

- apertura autenticata su `https://app.iusentra.it/fascicoli?vista=economica`;
- tempo caricamento stabile dopo attesa del payload: circa 1,7 secondi;
- totale visibile: 300 fascicoli;
- card `DOPPIONI`: 0, `nessun gruppo rilevato`;
- Betti Alice / `RG 3685/2026`: contributo `€ 49,00`, pagato, liquidazione `€ 1.100,00`, parcella `€ 1.654,03`;
- Alfano Giuseppe / `RG 1100/2026`: contributo `€ 49,00`, pagato;
- Romeo Maria / `RG 1428/2026` e Tescione Ada Giulia / `RG 1477/2026`: contributo valorizzato secondo ricevuta o autocertificazione, non più `Da verificare` generico;
- cambio pagina 1 -> 2: circa 0,88 secondi, payload economico presente;
- pagina finale: `Pagina 12 di 12 - 300 fascicoli`, `DOPPIONI 0`, righe `RG da acquisire` visibili e motivate.

Nota UI osservata: il pulsante testuale `... 12` richiede un assestamento prima che la riga `Pagina 12 di 12` venga letta; il comando finale ha comunque portato alla pagina 12. Se si vuole rifinire ulteriormente la UX, conviene separare graficamente ellissi e numero pagina finale.

## Code scanning

Il gate `Code scanning results / CodeQL` del PR GitHub va ricontrollato dopo ogni push. La correzione dei documenti è stata mantenuta stretta per non aggiungere nuovi sorgenti di path traversal o bypass tenant.
