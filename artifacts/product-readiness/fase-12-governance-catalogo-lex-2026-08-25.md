# Fase 12, governance Lex nel catalogo documentale

## Perimetro di questa consegna

Questa consegna realizza il tratto operativo del percorso
**documento → Lex → fonti → revisione** nel fascicolo React. Non dichiara da
sola esauriti gli altri obiettivi della Fase 12 del programma strategico,
quali il registro globale dei modelli, la policy tenant completa, i benchmark
e la coda di approvazione multidocumento. Li conserva come perimetro di fase
successivo, senza presentare il catalogo come un sostituto.

## Regola introdotta

Una classificazione proposta da Lex può essere confermata soltanto quando:

1. il catalogo SQL possiede almeno una prova della classificazione;
2. l'avvocato ha aperto **Prova e fonti** per quel documento nella sessione;
3. la richiesta di revisione invia l'attestazione esplicita di lettura.

Se manca la prova, la conferma è rifiutata dal runtime. L'avvocato può
aggiornare l'indice oppure usare **Correggi catalogo**, che resta una
classificazione manuale distinta e auditata. La regola non usa il nome file o
i metadati del portale come prova del contenuto.

## Dati, API e audit

- La conferma continua a usare il catalogo SQL tenant-aware esistente. Non è
  stata introdotta alcuna nuova fonte JSON né modificato il modello dati.
- L'endpoint React di revisione riceve `evidence_acknowledged` e il runtime
  verifica la presenza delle evidenze prima di salvare l'esito.
- L'evento `document_catalog.reviewed` registra, oltre alla lunghezza della
  nota, l'attestazione di lettura, il numero delle evidenze e le loro
  tipologie. Il dato è nel payload audit già supportato da SQLite e
  PostgreSQL, senza divergenza di schema.
- La superficie mostra prima **Prova e fonti**, poi il comando di conferma. Il
  pulsante resta leggibile ma disabilitato con una causa esplicita; il focus
  da tastiera mantiene il contorno visibile.

## Verifiche eseguite

- Test API della revisione con `evidence_acknowledged`.
- Test runtime: rifiuto della conferma senza prova; audit con attestazione,
  quantità e tipi delle evidenze quando la prova esiste.
- Test statico React: stato di lettura, messaggio esplicito, payload e blocco
  del pulsante prima della lettura.
- Typecheck TypeScript.
- Prova reale su `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`:
  20 documenti indicizzati e proposti; `decretoGenerico.pdf` ha mostrato
  estratti indicizzati, segnali procedurali e cinque fonti ufficiali del
  profilo. **Apri la prova nel lettore** ha aperto il PDF nel lettore interno.
  Prima della lettura il comando di conferma era disabilitato; dopo
  l'apertura era abilitato. Non è stata confermata né modificata alcuna
  classificazione del fascicolo di prova.

## Rilascio

Il commit, il push dei branch gemelli e il deploy Hetzner seguono i gate
mirati e la prova locale. Il rilascio è registrato solo dopo la verifica del
commit remoto, del container applicativo unico e della readiness pubblica.
