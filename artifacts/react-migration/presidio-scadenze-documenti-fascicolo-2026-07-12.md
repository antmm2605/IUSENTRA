# Presidio scadenze dai documenti del fascicolo - 12 luglio 2026

## Obiettivo

Il fascicolo già acquisito non deve essere riletto integralmente a ogni ciclo. Ogni documento nuovo o modificato deve invece essere indicizzato e controllato, anche quando il fascicolo possiede già altre scadenze. La lista fascicoli deve mostrare soltanto la prossima scadenza futura, senza trasformare una data trascorsa in un falso evento imminente.

## Casi reali verificati

| Fascicolo | Documento | SHA-256 | Termine letto | Esito atteso |
| --- | --- | --- | --- | --- |
| `DE674F4F`, RG 901/2026, Gramuglia Caterina | `Decreto fissazione udienza (3).PDF` | `fc4377c12b0066edfd3e6bced4ddf47046373a7b0c59971b9c8cb0a4d9c00dce` | deposito note il 06/10/2026 alle 14:00 | prossima scadenza 06/10/2026 |
| `2EE71A39`, RG 1394/2026, Monea Mariano | `Decreto fissazione udienza (originale notificato) (1).pdf` | `6be728327257cdd44b194aabf035fbaa953d1a343848e516bffa7776b26eeb38` | deposito note il 02/07/2026 | documento letto e scadenza storica, nessuna prossima scadenza |

I file locali coincidono per impronta con i documenti indicizzati nel tenant di produzione. Entrambi sono PDF testuali di una pagina ed estratti con `pdfplumber` senza OCR.

## Cause individuate

1. Il parser riconosceva formule come `entro il` o `per il`, ma non la formula reale `nel giorno` usata nel decreto Gramuglia.
2. Lo stato del lotto documentale non distingueva in modo persistente un fascicolo completo da uno elaborato solo in parte; un fascicolo parziale poteva quindi essere superato da altri lotti.
3. La presenza di una scadenza futura già registrata poteva escludere l'intero fascicolo, lasciando senza controllo documenti aggiunti successivamente.
4. L'elenco fascicoli non deve avviare OCR o indicizzazione sincrona: l'operazione rallenterebbe il caricamento e potrebbe moltiplicare il lavoro su centinaia di pratiche.

## Presidio implementato

- Impronta deterministica dell'inventario documentale del fascicolo, composta da identificativi, percorsi, hash, dimensioni, date e versioni dei documenti.
- Stato persistente `complete`, `partial` o `deferred` per ogni impronta del fascicolo.
- Identità di lettura per singolo documento basata su fascicolo, documento e hash: i file invariati restano acquisiti, mentre una nuova versione viene riesaminata.
- Priorità ai documenti mai letti; seguono i documenti che richiedono un nuovo passaggio del parser. Decreti, ordinanze, verbali, provvedimenti, comunicazioni, rinvii, udienze e termini sono ordinati prima degli allegati generici.
- Ripresa automatica dei fascicoli parziali fino al completamento dell'inventario.
- Nessuna esclusione del fascicolo solo perché possiede già una scadenza: ogni documento nuovo viene comunque controllato.
- Ampliamento controllato delle formule di data, incluse `nel giorno`, `per il giorno`, `fissato per`, `fissata per`, `alla data` e `in data`.
- Classificazione della formula `deposito delle note` come `Deposito note scritte ex art. 127-ter c.p.c.`.
- Deduplicazione su fascicolo, tipo evento e data: il riesame non crea una seconda scadenza.
- Indicizzazione sincrona limitata a un massimo di quattro documenti pertinenti soltanto quando l'utente apre esplicitamente documenti o scadenze. La lista e il dettaglio iniziale riusano esclusivamente testo già indicizzato.
- Le date trascorse restano nello storico e non vengono esposte come prossima scadenza.

## Struttura dati e responsabilità

- Fonte operativa del tenant di produzione: `studio.db` SQLite; i file JSON restano mirror o compatibilità storica.
- Testi e metadati: `fascicolo_documenti_ai` e `fascicolo_documenti_ai_testi` con filtro tenant, fascicolo, documento e versione corrente.
- Stato incrementale e prova append-only: `pec_audit_log` nel repository PEC tenant-aware.
- Scadenze: tabella `scadenze`; agenda e attività sono collegate tramite i gestori applicativi, non tramite scritture ad hoc.
- La modifica non introduce nuove tabelle o colonne. La logica resta compatibile con SQLite e PostgreSQL; l'ottimizzazione di priorità basata sul catalogo SQLite è facoltativa e il percorso primario continua a funzionare quando non è disponibile.

## Prova reale in produzione

- `DE674F4F`: una sola scadenza aperta al 06/10/2026, identificativo `219a9b69-b0f6-4325-9569-32a73031bd41`; elenco React verificato con data visibile `06/10/2026`.
- `2EE71A39`: una sola scadenza storica al 02/07/2026, stato `SCADUTO`; elenco React verificato con `n.d.` come prossima scadenza.
- Il PDF Monea è stato aperto con click reale nel visualizzatore del browser e mostra materialmente il termine del 02/07/2026.
- Riesame mirato Monea con il parser corrente: un documento elaborato, zero nuove scadenze, zero errori, zero lock.
- Server al momento della prova: unico container applicativo `iusentra-app`, app e scheduler healthy, `/api/pronto` HTTP 200, versione `2.256.0`.

## Guardrail automatici

- Formula reale Gramuglia e classificazione del deposito note.
- Persistenza e ripresa di un inventario parziale.
- Precedenza di un nuovo decreto rispetto a un fascicolo parziale generico.
- Controllo di documenti nuovi anche in presenza di una scadenza già esistente.
- Nessuna indicizzazione sincrona dalla lista o dal dettaglio iniziale.
- Nessuna prossima scadenza per il termine Monea già trascorso.

## Stato finale da aggiornare dopo il rilascio

Il presente documento deve essere completato con commit, gate GitHub, ricostruzione Docker locale, prova reale su `127.0.0.1:8080` e deploy ordinato sullo stesso commit prima della dichiarazione conclusiva.
