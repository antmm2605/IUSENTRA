# Letture unificate — tranche 2.342.0

Data: 21/09/2026

Questa nota raccoglie lo stato verificato della tranche di unificazione dei
consumer. Riporta risultati aggregati e non contiene dati privati, identificativi
di studio o contenuti dei log.

## Fatti verificati

- Undici job periodici derivativi duplicati sono sospesi con audit. Restano
  separati i consumer necessari a Agenda/Scadenziario e PEC, insieme ai flussi di
  ricezione, sicurezza e backup.
- Dodici registrazioni di run orfane sono state riconciliate soltanto quando la
  coppia `job + scheduled_at` aveva già un run terminale provato. Non sono stati
  inventati completamenti.
- Due sorgenti PEC usano la revisione persistita; due EML binari sono stati
  riacquisiti mantenendo invariati gli originali.
- Il pilot SQL del catalogo copre 33 fascicoli e 319 embedding dopo la
  riparazione del confine di validità. L'invariante osservato è 6,951 secondi
  con zero letture catalogo/RAG.
- Il dettaglio fascicolo non ricarica più tutti i 336 fascicoli per il contesto
  economico. La richiesta isolata è passata da 1,864 a 1,377 secondi.
- Il GET letture consulta il registro e non avvia il worker. Il GET fascicolo e
  il runtime sentenze usano il repository mirato.
- Il pilot Docling copre cinque documenti reali con OCR disattivato. Il gate
  MiniCPM resta un pilot; Gemma non è stato modificato.
- Verifiche: 151 test isolati nel verbale finale; 72 test mirati del perimetro
  fascicolo/sentenze/loader; 1 prova di forza del loader mirato. Tutti gli esiti
  indicati sono passati nei rispettivi ambienti isolati.

## Stato aperto

- I vecchi GET che hanno mostrato 64–121 secondi e i 503 di upstream non sono
  dichiarati risolti. La riduzione isolata del percorso economico è un risultato
  mirato, non una prova end-to-end di produzione.
- La candidata produzione 2.342.0 è sana, ma restano aperti commit, riallineamento
  locale e campagna visuale reale.
- Il batch autorizzato di dieci documenti sequenziali non è ancora stato
  lanciato.
- Restano da trattare il contaminante RAG globale legacy da 12 GB, 28 orfani OCR
  e gli errori storici non applicati.
- Il flusso deposito/firma/PEC congelato il 09/09/2026 resta fuori perimetro e
  invariato.

## Riferimenti operativi

- [Masterplan](../../ROADMAP_ENTERPRISE_100.md)
- [Registro letture](../../docs/REGISTRO_LETTURE.md)
- [Pytest confermati](pytest-confirmed-ok.md)
- [Pytest aperti](pytest-open-issues.md)
- [Pipeline Lex](../../docs/LEX_STUDIO_LLM_DATASET_PIPELINE.md)
- [Mappa route React](tranche-2a-route-map.md)
- [Audit prodotto](audit.md)
- [Matrice storage](../../docs/STORAGE_MATRIX.md)
- [Piano migrazione storage](../../docs/STORAGE_MIGRATION_PLAN.md)


## Verifica finale parziale del 21/09/2026

Browser reale produzione: 33 documenti pronti e catalogati; decreto originale letto nel lettore interno, note al 06/10/2026 ore 14:00. Rilettura controllata 33 documenti e 6 PEC in 41,055 secondi; archivio 48 dati verificati, nessuna udienza derivata dalla formula note in sostituzione. Apertura pannelli, fonte e scroll fino al fondo verificati. Restano aperti controllo degli appuntamenti storici, responsive completo, collaudo locale aggiornato, CI e passata complessiva. Il confronto degli altri record fascicolo trova 334 identici su 335; il caso 5E864356 risulta modificato durante la sessione e richiede attribuzione distinta. Non attestata integrità immutata di tutti i 335.

Guardrail locali: typecheck, packaging, Ruff essenziale, hook e contratti React superati; 5 test RAG, riacquisizione e migrazione PEC superati dopo chiusura esplicita delle connessioni SQLite nel migratore. Nessuna modifica a depositi o invii PEC. Procedura backfill sequenziale a gruppi di 10 predisposta; avvio ed esito vanno verificati separatamente.
